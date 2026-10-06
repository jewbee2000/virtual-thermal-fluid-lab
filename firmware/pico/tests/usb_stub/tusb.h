#ifndef FL_USB_STUB_H
#define FL_USB_STUB_H
#include <stdbool.h>
#include <stdint.h>
typedef void *osal_queue_t;
bool osal_queue_receive(osal_queue_t queue,void *data,uint32_t timeout_ms);
void tud_task_ext(uint32_t timeout_ms,bool in_isr);
#endif
