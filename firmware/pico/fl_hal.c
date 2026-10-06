/* Indicator-only fixture: no GPIO controls a pump, valve or heater. */
#include "fl_hal.h"
#include "pico/stdlib.h"
#include "hardware/adc.h"
void fl_hal_init(void) {
    const unsigned inputs[]={FL_TRIP_PIN,FL_ARM_PIN,FL_RESET_PIN}; unsigned i;
    adc_init(); adc_gpio_init(FL_ADC_PIN); adc_select_input(0u);
    for(i=0u;i<3u;i++) { gpio_init(inputs[i]); gpio_set_dir(inputs[i],GPIO_IN); gpio_pull_up(inputs[i]); }
    gpio_init(FL_LED_PIN); gpio_set_dir(FL_LED_PIN,GPIO_OUT); gpio_put(FL_LED_PIN,false);
}
bool fl_hal_adc(uint16_t *raw) {
    uint64_t started=time_us_64(); unsigned polls;
    hw_set_bits(&adc_hw->cs,ADC_CS_START_ONCE_BITS);
    for(polls=0u;polls<10000u;polls++) {
        if((adc_hw->cs & ADC_CS_READY_BITS)!=0u) {
            if((adc_hw->cs & ADC_CS_ERR_BITS)!=0u) return false;
            *raw=(uint16_t)adc_hw->result; return *raw<=4095u;
        }
        if(time_us_64()-started>=100u) return false;
        tight_loop_contents();
    }
    return false;
}
bool fl_hal_trip(void) { return gpio_get(FL_TRIP_PIN); }
bool fl_hal_arm_pressed(void) { return !gpio_get(FL_ARM_PIN); }
bool fl_hal_reset_pressed(void) { return !gpio_get(FL_RESET_PIN); }
void fl_hal_indicator(fl_state state,uint64_t now) {
    gpio_put(FL_LED_PIN,state==FL_RUNNING || (state==FL_TRIPPED && (now/250000u)%2u!=0u));
}
