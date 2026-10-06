/* Independent register/time stub: compile the production HAL, never its own oracle. */
#include "fl_hal.h"
#include "hardware/adc.h"
#include <stdio.h>
#include <limits.h>

fl_review_adc_hw fl_review_adc;
static uint64_t local_us,clock_stride_us,ready_after_us;
static uint32_t conversion_error,starts,time_calls,polls;
static unsigned checks,failures;

static void state(uint32_t raw,uint32_t error,uint64_t ready_after,uint64_t stride) {
    fl_review_adc.cs=0u;fl_review_adc.result=raw;
    local_us=0u;clock_stride_us=stride;ready_after_us=ready_after;
    conversion_error=error;starts=0u;time_calls=0u;polls=0u;
}
uint64_t time_us_64(void) {
    uint64_t returned=local_us;
    time_calls++;
    if(starts!=0u && returned>=ready_after_us)
        fl_review_adc.cs|=ADC_CS_READY_BITS|conversion_error;
    local_us+=clock_stride_us;
    return returned;
}
void tight_loop_contents(void) {polls++;}
void hw_set_bits(volatile uint32_t *address,uint32_t bits) {
    starts++;*address=bits;
    if(ready_after_us==0u) *address|=ADC_CS_READY_BITS|conversion_error;
}
#define CHECK(value) do {checks++;if(!(value)){failures++;printf("FAIL line%d: %s\n",__LINE__,#value);}} while(0)

int main(void) {
    static const uint32_t valid_raw[]={0u,2048u,4095u};
    size_t i;uint16_t captured;bool accepted;
    for(i=0u;i<sizeof(valid_raw)/sizeof(valid_raw[0]);i++) {
        state(valid_raw[i],0u,0u,1u);captured=UINT16_MAX;
        accepted=fl_hal_adc(&captured);
        CHECK(accepted);CHECK(captured==valid_raw[i]);CHECK(starts==1u);
    }
    for(i=0u;i<sizeof(valid_raw)/sizeof(valid_raw[0]);i++) {
        state(valid_raw[i],ADC_CS_ERR_BITS,0u,1u);captured=UINT16_MAX;
        accepted=fl_hal_adc(&captured);
        printf("READY+ERR raw%u accepted%u\n",valid_raw[i],(unsigned)accepted);
        CHECK(!accepted);CHECK(starts==1u);
    }
    state(1234u,0u,75u,25u);captured=UINT16_MAX;
    accepted=fl_hal_adc(&captured);
    CHECK(accepted);CHECK(captured==1234u);CHECK(local_us<=125u);CHECK(polls<=4u);
    state(4096u,0u,0u,1u);captured=UINT16_MAX;
    CHECK(!fl_hal_adc(&captured));
    /* A valid monotonic clock reaches the documented100us timeout. */
    state(2048u,0u,UINT64_MAX,25u);captured=UINT16_MAX;
    accepted=fl_hal_adc(&captured);
    CHECK(!accepted);CHECK(time_calls==5u);CHECK(local_us==125u);CHECK(polls==3u);
    /* The independent poll cap still terminates if the clock stops progressing. */
    state(2048u,0u,UINT64_MAX,0u);captured=UINT16_MAX;
    accepted=fl_hal_adc(&captured);
    CHECK(!accepted);CHECK(time_calls==10001u);CHECK(polls==10000u);
    printf("%u independent HAL checks, %u failures\n",checks,failures);
    return failures==0u?0:1;
}
