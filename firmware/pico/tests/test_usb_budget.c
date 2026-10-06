#include "tusb.h"
#include <stdio.h>
static unsigned receives; static bool queue_full=true,nonzero_timeout;
bool osal_queue_receive(osal_queue_t queue,void *data,uint32_t timeout_ms) {
    (void)queue; (void)data; receives++; if(timeout_ms!=0u) nonzero_timeout=true;
    return queue_full;
}
int main(void) {
    unsigned pass;
    for(pass=0u;pass<1000u;pass++) {
        unsigned before=receives; tud_task_ext(UINT32_MAX,false);
        if(receives-before!=8u || nonzero_timeout) return 1;
    }
    queue_full=false; tud_task_ext(UINT32_MAX,false);
    if(receives!=8001u) return 2;
    puts("1000 continuously replenished USB passes bounded at 8 receives; empty pass returned"); return 0;
}
