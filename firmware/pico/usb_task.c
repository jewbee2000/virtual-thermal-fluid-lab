/* Bound the pinned TinyUSB device queue drain without modifying its checkout.
 * Included vendor source retains its MIT copyright/license header. */
#include "tusb.h"
#define FL_USB_EVENTS_PER_PASS 8u
static unsigned fl_usb_receives_remaining;
static bool fl_usb_queue_receive(osal_queue_t queue,void *data,uint32_t timeout_ms) {
    (void)timeout_ms;
    if(fl_usb_receives_remaining==0u) return false;
    fl_usb_receives_remaining--;
    return osal_queue_receive(queue,data,0u);
}
/* The source hash and exact receive site are verified by CMake. The macro
 * routes each vendor queue receive through the bounded application budget. */
#define osal_queue_receive fl_usb_queue_receive
#define tud_task_ext fl_usb_task_drain
#include FL_TINYUSB_USBD_SOURCE
#undef tud_task_ext
#undef osal_queue_receive
void tud_task_ext(uint32_t timeout_ms,bool in_isr) {
    (void)timeout_ms; fl_usb_receives_remaining=FL_USB_EVENTS_PER_PASS;
    fl_usb_task_drain(0u,in_isr);
}
