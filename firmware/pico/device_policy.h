#ifndef FL_DEVICE_POLICY_H
#define FL_DEVICE_POLICY_H
#include "fl_protocol.h"
#define FL_DEVICE_MIN_TICK_US 1000u
#define FL_DEVICE_TX_SLOTS 8u
typedef struct {
    bool present; char clock; uint32_t sequence, operation, heat_ppm;
    uint64_t source_us, receipt_us, expires_us;
} fl_intent;
typedef struct { bool arm_pressed, reset_pressed; uint64_t last_edge_us; bool edge_seen; } fl_gpio_edges;
typedef struct { char bytes[FL_FRAME_MAX+1u],type; size_t length; } fl_tx_slot;
typedef struct { fl_frame frame; uint64_t receipt_us; } fl_device_observation;
typedef struct {
    fl_core core; fl_intent intent; fl_gpio_edges edges;
    fl_device_observation observations[32]; size_t observation_count;
    fl_tx_slot tx[FL_DEVICE_TX_SLOTS]; size_t tx_count;
    uint32_t mode, last_session_epoch, core_tick_sequence, tick_count;
    uint32_t overruns, rx_rejected, tx_dropped, ack_sequence;
    bool session_seen, ack_seen, watchdog_reboot;
} fl_device;
uint32_t fl_saturating_add(uint32_t value,uint32_t addition);
void fl_intent_init(fl_intent *intent);
bool fl_intent_fresh(const fl_intent *intent,uint64_t now_us);
bool fl_intent_accept(fl_intent *intent,const fl_core *core,const fl_frame *frame,uint64_t receipt_us);
void fl_gpio_init(fl_gpio_edges *edges,bool arm_pressed,bool reset_pressed);
uint32_t fl_gpio_operation(fl_gpio_edges *edges,bool arm_pressed,bool reset_pressed,uint32_t serial_operation,uint64_t now_us);
void fl_device_init(fl_device *device,uint32_t mode,bool watchdog_reboot,bool arm_pressed,bool reset_pressed);
void fl_device_disconnect(fl_device *device,bool arm_pressed,bool reset_pressed);
bool fl_device_receive(fl_device *device,const fl_frame *frame,uint64_t receipt_us,bool arm_pressed,bool reset_pressed);
bool fl_device_enqueue(fl_device *device,const fl_frame *frame);
const fl_tx_slot *fl_device_tx_peek(const fl_device *device);
void fl_device_tx_pop(fl_device *device);
void fl_device_boot(fl_device *device,uint64_t now_us);
bool fl_device_tick(fl_device *device,uint64_t now_us,uint32_t due_count,bool adc_valid,uint16_t adc_raw,
                    bool trip,bool arm_pressed,bool reset_pressed,fl_output *output);
#endif
