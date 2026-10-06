#include "fl_protocol.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static unsigned checks=0u;
#define CHECK(x) do { checks++; if(!(x)) { fprintf(stderr,"check failed line %d: %s\n",__LINE__,#x); return 1; } } while(0)
static fl_config tank(void) { fl_config p={1u,1u,1u,100000u,300000u,300000u,3000000u,60000u,315500u,650000u,500000,0,1000000,0u,0u,0u,0u}; return p; }
static fl_config thermal(void) { fl_config p={2u,1u,2u,100000u,300000u,300000u,2000000000u,200000000u,527498u,650000u,150000,0,500000,273150u,368150u,338150u,358150u}; return p; }
static void samples(fl_core *c,uint32_t seq,uint64_t now) {
    unsigned i;
    if(c->profile==1u) (void)fl_core_observe(c,c->epoch,seq,now,now,1u,1u,250000);
    else for(i=2u;i<=5u;i++) (void)fl_core_observe(c,c->epoch,seq,now,now,i,1u,i==2u ? 150000 : 293150);
    (void)fl_core_observe(c,c->epoch,seq,now,now,6u,1u,0);
}
int main(void) {
    fl_core c; fl_config p=tank(); fl_output out; fl_frame f; fl_stream stream;
    const char *goldens[]={"F|1|H|1|0|V|0|1*7A87\n","F|1|O|1|0|V|0|1|1|250000*6EF2\n","F|1|O|1|0|V|0|6|1|0*0FE2\n","F|1|S|1|0|V|0|1|0*AFD1\n","F|1|A|1|0|V|0|0|0*0493\n"};
    size_t i,j; char encoded[FL_FRAME_MAX+1u];
    CHECK(fl_crc16((const unsigned char*)"123456789",9u)==0x31C3u);
    for(i=0u;i<5u;i++) {
        size_t n=strlen(goldens[i]); CHECK(fl_frame_decode(goldens[i],n,&f));
        CHECK(fl_frame_encode(&f,encoded)==n); CHECK(strcmp(encoded,goldens[i])==0);
        for(j=0u;j<n;j++) {
            size_t k; fl_stream_init(&stream);
            for(k=0u;k<n;k++) CHECK(fl_stream_byte(&stream,(unsigned char)goldens[i][k],k>=j ? 100u : 0u,&f)==(k==n-1u ? FL_STREAM_FRAME : FL_STREAM_NONE));
        }
    }
    {
        const char *config_golden="F|1|C|1|0|V|0|1|1|1|100000|300000|300000|3000000|60000|315500|650000|500000|0|1000000|0|0|0|0*EB2A\n";
        CHECK(fl_frame_decode(config_golden,strlen(config_golden),&f));
        CHECK(fl_frame_config(&f,&p)); CHECK(p.kp_scaled==3000000u && p.target_i==500000);
        fl_frame_u(&f,2u,UINT64_MAX); CHECK(!fl_frame_config(&f,&p));
        p=tank();
    }
    CHECK(!fl_frame_decode("F|1|H|1|0|V|0|1*7a87\n",21u,&f));
    CHECK(!fl_frame_decode("F|1|H|1|0|V|0|1*7A87\r\n",22u,&f));
    CHECK(!fl_frame_decode("F|1|H|1|0|V|0|2*7A87\n",21u,&f));
    CHECK(fl_frame_decode(goldens[1],strlen(goldens[1]),&f));
    f.values[2].negative=true; f.values[2].magnitude=0u;
    CHECK(!fl_frame_valid(&f)); CHECK(fl_frame_encode(&f,encoded)==0u);
    {
        const char *bad[]={"F|1|H|01|0|V|0|1*B702\n","F|1|H|1|0|V|18446744073709551616|1*D24E\n",
            "F|1|O|1|0|V|0|1|1|-2147483649*3DD6\n","F|1|H|1|0|V|0|1|0*7D9A\n"};
        for(i=0u;i<4u;i++) CHECK(!fl_frame_decode(bad[i],strlen(bad[i]),&f));
    }
    fl_stream_init(&stream); CHECK(fl_stream_byte(&stream,'F',0u,&f)==FL_STREAM_NONE);
    CHECK(!fl_stream_expire(&stream,499u)); CHECK(fl_stream_expire(&stream,500u));
    CHECK(fl_stream_byte(&stream,'\n',501u,&f)==FL_STREAM_NONE);
    CHECK(!fl_stream_eof(&stream));
    CHECK(fl_stream_byte(&stream,'F',600u,&f)==FL_STREAM_NONE); CHECK(fl_stream_eof(&stream));
    fl_stream_init(&stream);
    for(i=0u;i<255u;i++) CHECK(fl_stream_byte(&stream,'x',0u,&f)==FL_STREAM_NONE);
    CHECK(fl_stream_byte(&stream,'\n',0u,&f)==FL_STREAM_REJECTED); /* length256, invalid semantic */
    for(i=0u;i<255u;i++) CHECK(fl_stream_byte(&stream,'x',0u,&f)==FL_STREAM_NONE);
    CHECK(fl_stream_byte(&stream,'x',0u,&f)==FL_STREAM_REJECTED); CHECK(fl_stream_byte(&stream,'\n',0u,&f)==FL_STREAM_NONE);
    CHECK(fl_sequence_newer(0u,UINT32_MAX)); CHECK(!fl_sequence_newer(0x80000000u,0u));
    fl_core_init(&c); CHECK(!fl_core_bind(&c,0u,1u)); CHECK(fl_core_bind(&c,1u,1u)); CHECK(fl_core_configure(&c,&p));
    CHECK(fl_core_configure(&c,&p)); p.ff_ppm++; CHECK(!fl_core_configure(&c,&p)); p=tank();
    CHECK(fl_core_step(&c,1u,0u,0u,1u,0u,&out)); CHECK(out.state==FL_DISARMED && out.operation_result==2u);
    CHECK(!fl_core_step(&c,1u,2u,100000u,0u,0u,&out));
    samples(&c,0u,100000u); CHECK(fl_core_step(&c,1u,1u,100000u,1u,0u,&out));
    CHECK(out.state==FL_RUNNING);
    CHECK(out.pump_ppm==1000000u && c.integral==0.0);
    /* Independent recurrence e=.01,I=.06*.01*.1=.00006 -> .34556. */
    CHECK(fl_core_observe(&c,1u,1u,200000u,200000u,1u,1u,490000));
    CHECK(fl_core_observe(&c,1u,1u,200000u,200000u,6u,1u,0));
    CHECK(fl_core_step(&c,1u,2u,200000u,0u,0u,&out)); CHECK(out.pump_ppm==345560u);
    CHECK(fabs(c.integral-.00006)<1e-12);
    CHECK(fl_core_bind(&c,1u,1u)); CHECK(c.state==FL_RUNNING); CHECK(!fl_core_bind(&c,1u,2u));
    CHECK(!fl_core_observe(&c,1u,0u,200000u,200000u,1u,1u,1));
    CHECK(!fl_core_observe(&c,1u,2u,300001u,300000u,1u,1u,1));
    CHECK(!fl_core_observe(&c,1u,2u,100000u,300000u,1u,1u,1));
    CHECK(fl_core_observe(&c,1u,2u,300000u,300000u,1u,0u,0));
    CHECK(fl_core_step(&c,1u,3u,300000u,0u,0u,&out)); CHECK(out.state==FL_TRIPPED && out.reason==FL_INVALID_INPUT && out.max_age_us==100000u);
    samples(&c,3u,400000u); CHECK(fl_core_step(&c,1u,4u,400000u,1u,0u,&out)); CHECK(out.state==FL_TRIPPED && out.operation_result==2u);
    samples(&c,4u,500000u); CHECK(fl_core_step(&c,1u,5u,500000u,2u,0u,&out)); CHECK(out.state==FL_DISARMED && c.integral==0.0);
    samples(&c,5u,600000u); CHECK(fl_core_step(&c,1u,6u,600000u,1u,0u,&out)); CHECK(out.state==FL_RUNNING);
    CHECK(!fl_core_bind(&c,0u,1u)); CHECK(fl_core_bind(&c,2u,2u)); CHECK(c.state==FL_DISARMED && !c.configured);
    p=thermal(); CHECK(fl_core_configure(&c,&p)); samples(&c,0u,0u);
    CHECK(fl_core_step(&c,2u,0u,0u,1u,1000000u,&out)); CHECK(out.pump_ppm==527498u && out.heat_ppm==1000000u);
    CHECK(fl_core_observe(&c,2u,1u,100000u,100000u,5u,1u,358150));
    CHECK(fl_core_observe(&c,2u,1u,100000u,100000u,3u,1u,338150));
    CHECK(fl_core_observe(&c,2u,1u,100000u,100000u,6u,1u,1));
    CHECK(fl_core_step(&c,2u,1u,100000u,0u,1000000u,&out));
    CHECK(out.reason==FL_SEPARATE_TRIP && out.heat_ppm==0u && out.pump_ppm==FL_PPM && out.valve_ppm==FL_PPM);
    /* Exact stale boundary using a1us tick and independently held last-good0. */
    fl_core_init(&c); p=tank(); p.tick_us=1u; CHECK(fl_core_bind(&c,7u,1u)); CHECK(fl_core_configure(&c,&p)); samples(&c,0u,0u);
    CHECK(fl_core_step(&c,7u,0u,0u,1u,0u,&out));
    for(i=1u;i<=300000u;i++) CHECK(fl_core_step(&c,7u,(uint32_t)i,(uint64_t)i,0u,0u,&out));
    CHECK(out.state==FL_RUNNING && out.max_age_us==300000u);
    CHECK(fl_core_step(&c,7u,300001u,300001u,0u,0u,&out)); CHECK(out.reason==FL_STALE_INPUT);
    /*100 saturated ticks do not accumulate I; reverse error yields0 without windup. */
    fl_core_init(&c); p=tank(); CHECK(fl_core_bind(&c,8u,1u)); CHECK(fl_core_configure(&c,&p));
    for(i=0u;i<100u;i++) { samples(&c,(uint32_t)i,(uint64_t)i*100000u);
        CHECK(fl_core_step(&c,8u,(uint32_t)i,(uint64_t)i*100000u,i==0u ? 1u : 0u,0u,&out));
        CHECK(out.pump_ppm==FL_PPM && c.integral==0.0);
    }
    CHECK(fl_core_observe(&c,8u,100u,10000000u,10000000u,1u,1u,1000000));
    CHECK(fl_core_observe(&c,8u,100u,10000000u,10000000u,6u,1u,0));
    CHECK(fl_core_step(&c,8u,100u,10000000u,0u,0u,&out)); CHECK(out.state==FL_RUNNING && out.pump_ppm==0u && c.integral==0.0);
    CHECK(fl_core_observe(&c,8u,101u,10100000u,10100000u,1u,1u,1000001));
    CHECK(fl_core_step(&c,8u,101u,10100000u,0u,0u,&out)); CHECK(out.reason==FL_RANGE_INPUT);
    fl_core_init(&c); p=tank(); p.kp_scaled=0u; p.ki_scaled=24000000u; p.ff_ppm=500000u;
    CHECK(fl_core_bind(&c,9u,1u)); CHECK(fl_core_configure(&c,&p)); samples(&c,0u,0u);
    CHECK(fl_core_step(&c,9u,0u,0u,1u,0u,&out)); CHECK(out.pump_ppm==FL_PPM && fabs(c.integral-.6)<1e-12);
    CHECK(fl_core_observe(&c,9u,1u,100000u,100000u,1u,1u,750000));
    CHECK(fl_core_observe(&c,9u,1u,100000u,100000u,6u,1u,0));
    CHECK(fl_core_step(&c,9u,1u,100000u,0u,0u,&out)); CHECK(out.pump_ppm==500000u && fabs(c.integral)<1e-12);
    fl_core_init(&c); p=thermal(); CHECK(fl_core_bind(&c,10u,2u)); CHECK(fl_core_configure(&c,&p)); samples(&c,0u,0u);
    /*Q error.00015m3/s:2000*.00015=.3 and200*.00015*.1=.003. */
    CHECK(fl_core_observe(&c,10u,1u,0u,0u,2u,1u,0));
    CHECK(fl_core_step(&c,10u,0u,0u,1u,FL_PPM,&out)); CHECK(out.pump_ppm==830498u);
    printf("%u independent core/codec checks passed\n",checks); return 0;
}
