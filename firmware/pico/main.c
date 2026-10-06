#include "device_policy.h"
#include "fl_hal.h"
#include "pico/stdlib.h"
#include "hardware/watchdog.h"
#include "hardware/sync.h"
#include "tusb.h"
static volatile uint32_t pending_ticks;
static bool due_callback(struct repeating_timer *timer) {
    (void)timer; if(pending_ticks!=UINT32_MAX) pending_ticks++; return true;
}
static uint32_t take_due(void) {
    uint32_t interrupts=save_and_disable_interrupts(),due=pending_ticks;
    pending_ticks=0u; restore_interrupts(interrupts); return due;
}
int main(void) {
    static fl_device device; fl_stream stream; struct repeating_timer timer;
    bool connected=false; uint32_t period_us=100000u;
    fl_hal_init(); fl_device_init(&device,FL_DEVICE_MODE,watchdog_enable_caused_reboot(),fl_hal_arm_pressed(),fl_hal_reset_pressed());
    fl_stream_init(&stream); tusb_init();
    if(!add_repeating_timer_us(-(int64_t)period_us,due_callback,NULL,&timer)) return 2;
    watchdog_enable(FL_WATCHDOG_MS,false);
    for(;;) {
        uint32_t due=take_due(); uint64_t now=time_us_64(); bool link;
        /* Due work has priority over each bounded RX/TX pass; no catch-up ticks. */
        if(due!=0u) {
            fl_output output; uint16_t adc_raw=0u;
            bool adc_valid=FL_DEVICE_MODE==2 ? fl_hal_adc(&adc_raw) : false;
            bool trip=fl_hal_trip(),arm=fl_hal_arm_pressed(),reset=fl_hal_reset_pressed(),stepped;
            now=time_us_64();
            stepped=fl_device_tick(&device,now,due,adc_valid,adc_raw,trip,arm,reset,&output);
            fl_hal_indicator(stepped ? output.state : FL_DISARMED,now);
            /*Completed acquisition/control/housekeeping only; no IRQ/idle feed. */
            if(!device.core.configured || stepped) watchdog_update();
        }
        tud_task_ext(0u,false); link=tud_cdc_connected();
        if(link!=connected) {
            fl_device_disconnect(&device,fl_hal_arm_pressed(),fl_hal_reset_pressed());
            fl_stream_init(&stream); tud_cdc_read_flush(); fl_hal_indicator(FL_DISARMED,now);
            if(link) fl_device_boot(&device,now);
            connected=link;
        }
        if(fl_stream_expire(&stream,now/1000u)) device.rx_rejected=fl_saturating_add(device.rx_rejected,1u);
        if(connected) {
            unsigned char bytes[FL_FRAME_MAX]; uint32_t count=tud_cdc_read(bytes,FL_FRAME_MAX),i;
            for(i=0u;i<count;i++) {
                fl_frame frame; fl_stream_result result=fl_stream_byte(&stream,bytes[i],time_us_64()/1000u,&frame);
                if(result==FL_STREAM_REJECTED) device.rx_rejected=fl_saturating_add(device.rx_rejected,1u);
                else if(result==FL_STREAM_FRAME) {
                    bool configured=device.core.configured;
                    bool accepted=fl_device_receive(&device,&frame,time_us_64(),fl_hal_arm_pressed(),fl_hal_reset_pressed());
                    if(accepted && frame.type=='C' && !configured) {
                        (void)cancel_repeating_timer(&timer); (void)take_due(); period_us=device.core.config.tick_us;
                        if(!add_repeating_timer_us(-(int64_t)period_us,due_callback,NULL,&timer)) return 3;
                    }
                }
            }
            {
                const fl_tx_slot *slot=fl_device_tx_peek(&device);
                if(slot!=NULL && tud_cdc_write_available()>=slot->length) {
                    uint32_t written=tud_cdc_write(slot->bytes,(uint32_t)slot->length);
                    if(written==slot->length) { (void)tud_cdc_write_flush(); fl_device_tx_pop(&device); }
                    else { device.tx_dropped=fl_saturating_add(device.tx_dropped,1u); fl_device_tx_pop(&device); }
                    /*Same main-loop producer: available capacity permits whole frame. */
                }
            }
        }
        tight_loop_contents();
    }
}
