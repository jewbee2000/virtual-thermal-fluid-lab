/* Independent worst-case model: the queue is replenished after every receive. */
void tud_task_ext(uint32_t timeout_ms,bool in_isr) {
    unsigned event; (void)in_isr;
    while(osal_queue_receive((osal_queue_t)0,&event,timeout_ms)) { }
}
