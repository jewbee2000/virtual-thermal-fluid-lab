/* Independent recurrence/boundary oracles; this compiles the target policy itself. */
#include "device_policy.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static unsigned checks;
#define CHECK(x) do { checks++; if(!(x)) { fprintf(stderr,"check failed line %d: %s\n",__LINE__,#x); return 1; } } while(0)
static const char *config_literal="F|1|C|1|0|V|0|1|1|1|100000|300000|300000|3000000|60000|315500|650000|500000|0|1000000|0|0|0|0*EB2A\n";
static fl_config tank(void) { fl_config p={1u,1u,1u,100000u,300000u,300000u,3000000u,60000u,315500u,650000u,500000,0,1000000,0u,0u,0u,0u}; return p; }
static fl_frame frame(char type,uint32_t seq,uint64_t source,size_t count) {
    fl_frame f; memset(&f,0,sizeof(f)); f.type=type; f.clock='V'; f.epoch=1u; f.sequence=seq; f.time_us=source; f.count=count; return f;
}
static bool configure(fl_device *d,uint32_t tick,bool held_arm) {
    fl_frame h=frame('H',0u,0u,1u),c;
    fl_frame_u(&h,0u,1u);
    if(!fl_device_receive(d,&h,0u,held_arm,false) || !fl_frame_decode(config_literal,strlen(config_literal),&c)) return false;
    fl_frame_u(&c,3u,tick); return fl_device_receive(d,&c,0u,held_arm,false);
}
static bool sample(fl_device *d,uint32_t seq,uint64_t source,uint64_t receipt,uint32_t channel,int32_t value) {
    fl_frame f=frame('O',seq,source,3u); fl_frame_u(&f,0u,channel); fl_frame_u(&f,1u,1u); fl_frame_i(&f,2u,value);
    return fl_device_receive(d,&f,receipt,false,false);
}
static bool intent(fl_device *d,uint32_t seq,uint64_t source,uint64_t receipt,uint32_t operation) {
    fl_frame f=frame('U',seq,source,2u); fl_frame_u(&f,0u,operation); return fl_device_receive(d,&f,receipt,false,false);
}
static int clock_and_pi(void) {
    fl_core c; fl_config p=tank(); fl_output o;
    fl_core_init(&c); CHECK(fl_core_bind(&c,1u,1u)); CHECK(fl_core_configure(&c,&p));
    CHECK(fl_core_observe_device(&c,1u,0u,'V',UINT64_C(900000000000),1000000u,1u,1u,490000));
    CHECK(fl_core_observe_device(&c,1u,0u,'V',UINT64_C(900000000000),1000000u,6u,1u,0));
    CHECK(fl_core_step_device(&c,1u,0u,1000000u,1u,0u,true,&o));
    /* e=.01; first dt=.1 -> I=.00006, then actual dt=.3 -> I=.00024. */
    CHECK(o.state==FL_RUNNING && o.pump_ppm==345560u && o.max_age_us==0u);
    CHECK(fl_core_step_device(&c,1u,1u,1300000u,0u,0u,true,&o));
    CHECK(o.pump_ppm==345740u && o.max_age_us==300000u && o.state==FL_RUNNING);
    CHECK(fabs(c.integral-.00024)<1e-12);
    CHECK(!fl_core_step_device(&c,1u,2u,1300000u,0u,0u,true,&o));
    CHECK(!fl_core_step(&c,1u,2u,1400000u,0u,0u,&o));
    CHECK(!fl_core_observe_device(&c,1u,0u,'V',UINT64_C(900000000001),1300000u,1u,1u,0));
    CHECK(!fl_core_observe_device(&c,1u,UINT32_C(0x80000000),'V',UINT64_C(900000000001),1300000u,1u,1u,0));
    CHECK(!fl_core_observe_device(&c,1u,1u,'V',UINT64_C(899999999999),1300000u,1u,1u,0));
    CHECK(!fl_core_observe_device(&c,1u,1u,'D',UINT64_C(900000000001),1300000u,1u,1u,0));
    CHECK(!fl_core_observe_device(&c,2u,1u,'V',UINT64_C(900000000001),1300000u,1u,1u,0));
    CHECK(fl_core_step_device(&c,1u,2u,1300001u,0u,0u,false,&o));
    CHECK(o.state==FL_TRIPPED && o.reason==FL_STALE_INPUT && o.max_age_us==300001u);
    /* Host schedule remains exactly fixed and first time zero. */
    fl_core_init(&c); CHECK(fl_core_bind(&c,1u,1u)); CHECK(fl_core_configure(&c,&p));
    CHECK(!fl_core_step(&c,1u,0u,1u,0u,0u,&o)); CHECK(fl_core_step(&c,1u,0u,0u,0u,0u,&o));
    CHECK(!fl_core_step(&c,1u,1u,100001u,0u,0u,&o));
    CHECK(!fl_core_step_device(&c,1u,1u,100000u,0u,0u,true,&o));
    return 0;
}
static int intent_boundaries(void) {
    fl_device d; fl_output o; fl_frame f;
    fl_device_init(&d,1u,false,false,false); CHECK(configure(&d,100000u,false));
    CHECK(intent(&d,UINT32_MAX,UINT64_C(900000000000),1000000u,1u));
    CHECK(fl_intent_fresh(&d.intent,1299999u)); CHECK(!fl_intent_fresh(&d.intent,1300000u));
    CHECK(!intent(&d,UINT32_MAX,UINT64_C(900000000001),1000001u,0u));
    CHECK(intent(&d,0u,UINT64_C(900000000001),1000001u,0u));
    CHECK(d.intent.operation==1u); /* HOLD refresh preserves an unconsumed edge. */
    CHECK(!intent(&d,UINT32_C(0x80000000),UINT64_C(900000000002),1000002u,0u));
    CHECK(!intent(&d,1u,UINT64_C(899999999999),1000002u,0u));
    f=frame('U',1u,UINT64_C(900000000002),2u); f.clock='D'; CHECK(!fl_device_receive(&d,&f,1000002u,false,false));
    f.clock='V'; CHECK(!fl_device_receive(&d,&f,UINT64_MAX-299999u,false,false));
    CHECK(sample(&d,0u,UINT64_C(900000000000),1000000u,1u,490000));
    CHECK(sample(&d,0u,UINT64_C(900000000000),1000000u,6u,0));
    CHECK(fl_device_tick(&d,1100000u,1u,false,0u,false,false,false,&o)); CHECK(o.state==FL_RUNNING);
    CHECK(sample(&d,1u,UINT64_C(900000000001),1300001u,1u,490000));
    CHECK(sample(&d,1u,UINT64_C(900000000001),1300001u,6u,0));
    CHECK(fl_device_tick(&d,1300001u,1u,false,0u,false,false,false,&o));
    CHECK(o.state==FL_TRIPPED && o.reason==FL_INTENT_EXPIRED && d.intent.operation==0u && d.intent.heat_ppm==0u);
    /* Expired ARM and RESET reject even with all observations fresh. */
    CHECK(fl_core_step_device(&d.core,1u,2u,1300002u,2u,0u,false,&o)); CHECK(o.state==FL_TRIPPED && o.operation_result==2u);
    fl_core_init(&d.core); { fl_config p=tank(); CHECK(fl_core_bind(&d.core,1u,1u)); CHECK(fl_core_configure(&d.core,&p)); }
    CHECK(fl_core_observe_device(&d.core,1u,0u,'D',0u,0u,1u,1u,490000));
    CHECK(fl_core_observe_device(&d.core,1u,0u,'D',0u,0u,6u,1u,0));
    CHECK(fl_core_step_device(&d.core,1u,0u,0u,1u,0u,false,&o)); CHECK(o.state==FL_DISARMED && o.operation_result==2u);
    return 0;
}
static int peripheral_and_edges(void) {
    fl_device d; fl_output o; fl_frame f; fl_gpio_edges e;
    fl_gpio_init(&e,true,true); CHECK(fl_gpio_operation(&e,true,true,0u,0u)==0u);
    CHECK(fl_gpio_operation(&e,false,false,0u,100u)==0u);
    CHECK(fl_gpio_operation(&e,true,true,1u,200u)==2u);
    CHECK(fl_gpio_operation(&e,true,true,0u,300u)==0u);
    CHECK(fl_gpio_operation(&e,false,false,0u,10000u)==0u);
    CHECK(fl_gpio_operation(&e,true,false,0u,11000u)==0u); /* debounce, then held never retriggers */
    CHECK(fl_gpio_operation(&e,true,false,0u,30000u)==0u);
    CHECK(fl_gpio_operation(&e,false,false,0u,40000u)==0u);
    CHECK(fl_gpio_operation(&e,true,false,2u,60000u)==2u); /* serial RESET beats GPIO ARM */
    fl_device_init(&d,2u,true,true,false); CHECK(configure(&d,100000u,true));
    CHECK(fl_device_tick(&d,100000u,4u,true,2010u,false,true,false,&o));
    CHECK(o.state==FL_DISARMED && d.tick_count==1u && d.overruns==3u && o.max_age_us==0u);
    CHECK(d.core.channels[0].value_i==490842); /* round(2010*1e6/4095) */
    CHECK(d.core.channels[0].source_clock=='D' && d.core.channels[0].receipt_us==100000u);
    CHECK(!sample(&d,1u,200000u,200000u,1u,490000));
    f=frame('S',0u,0u,2u); fl_frame_u(&f,0u,1u); CHECK(!fl_device_receive(&d,&f,0u,false,false));
    CHECK(fl_device_tick(&d,200000u,1u,true,2010u,false,false,false,&o));
    CHECK(fl_device_tick(&d,300000u,1u,true,2010u,false,true,false,&o)); CHECK(o.state==FL_RUNNING);
    CHECK(fl_device_tick(&d,400000u,1u,true,2010u,true,false,false,&o)); CHECK(o.reason==FL_SEPARATE_TRIP);
    CHECK(fl_device_tick(&d,500000u,1u,true,2010u,false,true,true,&o)); CHECK(o.state==FL_DISARMED && o.operation_result==1u);
    CHECK(fl_device_tick(&d,600000u,1u,true,2010u,false,true,true,&o)); CHECK(o.state==FL_DISARMED && o.operation_result==0u);
    CHECK(fl_device_tick(&d,700000u,1u,false,0u,false,false,false,&o));
    CHECK(d.core.channels[0].quality==0u && o.max_age_us==100000u);
    CHECK(fl_device_tick(&d,800000u,1u,true,65535u,false,true,false,&o));
    CHECK(o.state==FL_DISARMED && o.operation_result==2u && d.core.channels[0].quality==0u && o.max_age_us==200000u);
    fl_device_disconnect(&d,true,false); CHECK(!d.core.bound && d.core.state==FL_DISARMED && d.tx_count==0u);
    f=frame('H',0u,0u,1u); fl_frame_u(&f,0u,1u); CHECK(!fl_device_receive(&d,&f,0u,true,false));
    f.epoch=2u; fl_frame_u(&f,0u,2u); CHECK(!fl_device_receive(&d,&f,0u,true,false));
    fl_frame_u(&f,0u,1u); CHECK(fl_device_receive(&d,&f,0u,true,false));
    CHECK(fl_frame_decode(config_literal,strlen(config_literal),&f)); f.epoch=2u;
    CHECK(fl_device_receive(&d,&f,0u,true,false));
    CHECK(fl_device_tick(&d,900000u,1u,true,2010u,false,true,false,&o)); CHECK(o.state==FL_DISARMED);
    return 0;
}
static int peripheral_serial_intent_rejection(void) {
    fl_device d; fl_output o; uint32_t rejected;
    fl_device_init(&d,2u,false,false,false); CHECK(configure(&d,100000u,false));
    rejected=d.rx_rejected;
    CHECK(!intent(&d,0u,0u,0u,1u));
    CHECK(!d.intent.present && d.intent.operation==0u && d.rx_rejected==rejected+1u);
    CHECK(fl_device_tick(&d,100000u,1u,true,2010u,false,false,false,&o));
    CHECK(o.state==FL_DISARMED && o.operation_result==0u);
    CHECK(fl_device_tick(&d,200000u,1u,true,2010u,false,true,false,&o));
    CHECK(o.state==FL_RUNNING); /* A newly sampled GPIO press can still arm. */
    CHECK(fl_device_tick(&d,300000u,1u,true,2010u,true,false,false,&o));
    CHECK(o.state==FL_TRIPPED && o.reason==FL_SEPARATE_TRIP);
    rejected=d.rx_rejected;
    CHECK(!intent(&d,1u,300000u,300000u,2u));
    CHECK(!d.intent.present && d.intent.operation==0u && d.rx_rejected==rejected+1u);
    CHECK(fl_device_tick(&d,400000u,1u,true,2010u,false,false,false,&o));
    CHECK(o.state==FL_TRIPPED && o.operation_result==0u);
    CHECK(fl_device_tick(&d,500000u,1u,true,2010u,false,false,true,&o));
    CHECK(o.state==FL_DISARMED && o.operation_result==1u);
    return 0;
}
static int bounded_queues_and_sources(void) {
    fl_device d; fl_frame f; fl_output o; size_t i; uint32_t rejected;
    fl_device_init(&d,1u,false,false,false); CHECK(!configure(&d,999u,false)); CHECK(!d.core.configured);
    CHECK(configure(&d,1000u,false));
    for(i=0u;i<32u;i++) CHECK(sample(&d,(uint32_t)i,UINT64_C(900000000000)+(uint64_t)i,1000000u,1u,490000));
    rejected=d.rx_rejected; CHECK(!sample(&d,32u,UINT64_C(900000000032),1000000u,6u,0));
    CHECK(d.observation_count==32u && d.rx_rejected==rejected+1u);
    CHECK(fl_device_tick(&d,1100000u,1u,false,0u,false,false,false,&o));
    CHECK(d.core.channels[0].receipt_us==1000000u && o.max_age_us==UINT64_MAX);
    CHECK(d.core.channels[0].good_freshness_us==1000000u); /* receipt, not later tick */
    /* Optional records cannot occupy the slots required for Q/R/N. */
    fl_device_init(&d,1u,false,false,false);
    f=frame('X',0u,0u,6u); f.clock='D'; fl_frame_u(&f,0u,1u); fl_frame_u(&f,1u,1u); fl_frame_u(&f,5u,1u);
    for(i=0u;i<8u;i++) CHECK(fl_device_enqueue(&d,&f));
    CHECK(!fl_device_enqueue(&d,&f) && d.tx_count==8u && d.tx_dropped==1u);
    f=frame('Q',0u,0u,6u); f.clock='D'; fl_frame_u(&f,0u,300000u);
    CHECK(fl_device_enqueue(&d,&f)); CHECK(d.tx[0].type=='Q' && d.tx_count==8u && d.tx_dropped==2u);
    f=frame('R',0u,0u,7u); f.clock='D'; CHECK(fl_device_enqueue(&d,&f)); CHECK(d.tx[1].type=='R');
    f.type='N'; fl_frame_u(&f,0u,1u); CHECK(fl_device_enqueue(&d,&f)); CHECK(d.tx[2].type=='N');
    for(i=0u;i<5u;i++) CHECK(fl_device_enqueue(&d,&f));
    CHECK(d.tx_count==8u); CHECK(!fl_device_enqueue(&d,&f));
    for(i=0u;i<8u;i++) { CHECK(fl_device_tx_peek(&d)!=NULL); fl_device_tx_pop(&d); }
    CHECK(fl_device_tx_peek(&d)==NULL); fl_device_tx_pop(&d);
    CHECK(fl_saturating_add(UINT32_MAX-1u,2u)==UINT32_MAX);
    CHECK(fl_saturating_add(1u,2u)==3u);
    return 0;
}
static int codec_literals(void) {
    const char *literals[]={"F|1|U|1|4294967295|V|900000000000|1|0*EE1A\n",
        "F|1|X|1|3|D|1000000|1|1|0|900000000000|999999|1*3752\n",
        "F|1|N|1|3|D|1000000|1|3|2|4|5|1|0*DC53\n"};
    fl_frame f; char bytes[FL_FRAME_MAX+1u]; size_t i;
    for(i=0u;i<3u;i++) { CHECK(fl_frame_decode(literals[i],strlen(literals[i]),&f));
        CHECK(fl_frame_encode(&f,bytes)==strlen(literals[i])); CHECK(strcmp(bytes,literals[i])==0); }
    CHECK(fl_frame_decode(literals[0],strlen(literals[0]),&f)); fl_frame_u(&f,0u,3u); CHECK(!fl_frame_valid(&f));
    fl_frame_u(&f,0u,1u); fl_frame_u(&f,1u,1000001u); CHECK(!fl_frame_valid(&f));
    CHECK(fl_frame_decode(literals[1],strlen(literals[1]),&f));
    f.clock='V'; CHECK(!fl_frame_valid(&f)); f.clock='D';
    fl_frame_u(&f,0u,0u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,0u,7u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,0u,1u);
    fl_frame_u(&f,1u,0u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,1u,4u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,1u,1u);
    fl_frame_u(&f,2u,2u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,2u,0u);
    fl_frame_u(&f,5u,3u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,5u,2u); fl_frame_u(&f,3u,UINT64_MAX); CHECK(fl_frame_valid(&f));
    CHECK(fl_frame_decode(literals[2],strlen(literals[2]),&f));
    f.clock='V'; CHECK(!fl_frame_valid(&f)); f.clock='D';
    fl_frame_u(&f,0u,0u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,0u,3u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,0u,1u);
    fl_frame_u(&f,5u,2u); CHECK(!fl_frame_valid(&f)); fl_frame_u(&f,5u,1u);
    fl_frame_u(&f,6u,2u); CHECK(!fl_frame_valid(&f));
    f=frame('Q',0u,0u,6u); fl_frame_u(&f,0u,1u); fl_frame_u(&f,5u,7u); CHECK(fl_frame_valid(&f));
    fl_frame_u(&f,5u,8u); CHECK(!fl_frame_valid(&f));
    f=frame('R',0u,0u,7u); fl_frame_u(&f,2u,7u); CHECK(fl_frame_valid(&f)); fl_frame_u(&f,2u,8u); CHECK(!fl_frame_valid(&f));
    return 0;
}
int main(void) {
    CHECK(clock_and_pi()==0); CHECK(intent_boundaries()==0); CHECK(peripheral_and_edges()==0);
    CHECK(peripheral_serial_intent_rejection()==0);
    CHECK(bounded_queues_and_sources()==0); CHECK(codec_literals()==0);
    printf("%u device policy checks passed\n",checks); return 0;
}
