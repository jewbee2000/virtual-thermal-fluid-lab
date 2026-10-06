/* Platform-independent device policy; target and native checks compile this file. */
#include "device_policy.h"
#include <string.h>
uint32_t fl_saturating_add(uint32_t v,uint32_t n) { return UINT32_MAX-v<n ? UINT32_MAX : v+n; }
void fl_intent_init(fl_intent *i) { memset(i,0,sizeof(*i)); }
bool fl_intent_fresh(const fl_intent *i,uint64_t now) { return i->present && now>=i->receipt_us && now<i->expires_us; }
bool fl_intent_accept(fl_intent *i,const fl_core *c,const fl_frame *f,uint64_t receipt) {
    uint32_t op;
    if(!c->bound || !c->configured || f->type!='U' || !fl_frame_valid(f) || f->epoch!=c->epoch ||
       (c->profile==1u && f->values[1].magnitude!=0u) || UINT64_MAX-receipt<c->config.lease_us) return false;
    if(i->present && (f->clock!=i->clock || !fl_sequence_newer(f->sequence,i->sequence) ||
       f->time_us<i->source_us || receipt<i->receipt_us)) return false;
    if(!fl_intent_fresh(i,receipt)) { i->operation=0u; i->heat_ppm=0u; }
    op=(uint32_t)f->values[0].magnitude;
    if(op==2u || (op==1u && i->operation==0u)) i->operation=op;
    i->present=true; i->clock=f->clock; i->sequence=f->sequence; i->source_us=f->time_us;
    i->receipt_us=receipt; i->expires_us=receipt+c->config.lease_us;
    i->heat_ppm=(uint32_t)f->values[1].magnitude;
    return true;
}
void fl_gpio_init(fl_gpio_edges *e,bool arm,bool reset) {
    memset(e,0,sizeof(*e)); e->arm_pressed=arm; e->reset_pressed=reset;
}
uint32_t fl_gpio_operation(fl_gpio_edges *e,bool arm,bool reset,uint32_t serial,uint64_t now) {
    bool arm_edge=arm && !e->arm_pressed,reset_edge=reset && !e->reset_pressed;
    bool debounce=!e->edge_seen || (now>=e->last_edge_us && now-e->last_edge_us>=20000u);
    e->arm_pressed=arm; e->reset_pressed=reset;
    if((arm_edge || reset_edge) && debounce) { e->last_edge_us=now; e->edge_seen=true;
        if(reset_edge) return 2u;
        if(serial==2u) return 2u;
        if(arm_edge) return 1u;
    }
    return serial;
}
void fl_device_init(fl_device *d,uint32_t mode,bool reboot,bool arm,bool reset) {
    memset(d,0,sizeof(*d)); d->mode=mode; d->watchdog_reboot=reboot; fl_core_init(&d->core); fl_gpio_init(&d->edges,arm,reset);
}
void fl_device_disconnect(fl_device *d,bool arm,bool reset) {
    /* Preserve epoch history across a cable/DTR reconnect; RAM resets on boot. */
    fl_core_init(&d->core); fl_intent_init(&d->intent); d->observation_count=0u;
    d->tx_dropped=fl_saturating_add(d->tx_dropped,(uint32_t)d->tx_count); d->tx_count=0u;
    d->core_tick_sequence=0u; d->ack_seen=false; fl_gpio_init(&d->edges,arm,reset);
}
static fl_frame record(const fl_device *d,char type,uint32_t seq,uint64_t now,size_t n) {
    fl_frame f; memset(&f,0,sizeof(f)); f.type=type; f.clock='D'; f.epoch=d->core.epoch;
    f.sequence=seq; f.time_us=now; f.count=n; return f;
}
bool fl_device_enqueue(fl_device *d,const fl_frame *f) {
    fl_tx_slot slot; size_t i,position=d->tx_count;
    slot.length=fl_frame_encode(f,slot.bytes); slot.type=f->type;
    if(slot.length==0u) return false;
    if(d->tx_count==FL_DEVICE_TX_SLOTS) {
        if(f->type!='X') {
            for(i=0u;i<d->tx_count;i++) if(d->tx[i].type=='X') break;
            if(i<d->tx_count) { memmove(&d->tx[i],&d->tx[i+1u],(d->tx_count-i-1u)*sizeof(d->tx[0])); d->tx_count--; }
        }
        d->tx_dropped=fl_saturating_add(d->tx_dropped,1u);
        if(d->tx_count==FL_DEVICE_TX_SLOTS) return false;
    }
    if(f->type!='X') {
        for(position=0u;position<d->tx_count;position++) if(d->tx[position].type=='X') break;
    } else position=d->tx_count;
    memmove(&d->tx[position+1u],&d->tx[position],(d->tx_count-position)*sizeof(d->tx[0]));
    d->tx[position]=slot; d->tx_count++; return true;
}
const fl_tx_slot *fl_device_tx_peek(const fl_device *d) { return d->tx_count==0u ? NULL : &d->tx[0]; }
void fl_device_tx_pop(fl_device *d) {
    if(d->tx_count!=0u) { d->tx_count--; memmove(&d->tx[0],&d->tx[1],d->tx_count*sizeof(d->tx[0])); }
}
void fl_device_boot(fl_device *d,uint64_t now) {
    fl_frame f=record(d,'B',0u,now,2u); f.epoch=0u; fl_frame_u(&f,0u,100u); fl_frame_u(&f,1u,d->mode); (void)fl_device_enqueue(d,&f);
}
bool fl_device_receive(fl_device *d,const fl_frame *f,uint64_t receipt,bool arm,bool reset) {
    bool accepted=false;
    if(!fl_frame_valid(f)) goto rejected;
    if(f->type=='H') {
        uint32_t old_epoch=d->core.epoch,profile=(uint32_t)f->values[0].magnitude;
        if(d->mode==2u && profile!=1u) goto rejected;
        if(!d->core.bound && d->session_seen && !fl_sequence_newer(f->epoch,d->last_session_epoch)) goto rejected;
        accepted=fl_core_bind(&d->core,f->epoch,profile);
        if(accepted && old_epoch!=d->core.epoch) {
            d->last_session_epoch=d->core.epoch; d->session_seen=true; fl_intent_init(&d->intent);
            d->observation_count=0u; d->core_tick_sequence=0u; d->ack_seen=false;
            d->tx_dropped=fl_saturating_add(d->tx_dropped,(uint32_t)d->tx_count); d->tx_count=0u;
            fl_gpio_init(&d->edges,arm,reset);
        }
    } else if(f->type=='C') {
        fl_config p;
        if(f->epoch==d->core.epoch && fl_frame_config(f,&p) && p.tick_us>=FL_DEVICE_MIN_TICK_US)
            accepted=fl_core_configure(&d->core,&p);
    } else if(f->type=='O') {
        if(d->mode==1u && d->core.configured && f->epoch==d->core.epoch && d->observation_count<32u) {
            d->observations[d->observation_count].frame=*f;
            d->observations[d->observation_count++].receipt_us=receipt; accepted=true;
        }
    } else if(f->type=='U') accepted=fl_intent_accept(&d->intent,&d->core,f,receipt);
    else if(f->type=='A' && d->core.bound && f->epoch==d->core.epoch &&
        (!d->ack_seen || fl_sequence_newer(f->sequence,d->ack_sequence))) {
        d->ack_seen=true; d->ack_sequence=f->sequence; accepted=true;
    }
    /* External S and peripheral external channel replacement always reject. */
    if(accepted) return true;
rejected:
    d->rx_rejected=fl_saturating_add(d->rx_rejected,1u); return false;
}
static void channel_record(fl_device *d,uint32_t channel,uint64_t now) {
    const fl_channel *c=&d->core.channels[channel-1u];
    fl_frame x=record(d,'X',d->tick_count,now,6u);
    fl_frame_u(&x,0u,channel); fl_frame_u(&x,1u,d->mode==1u ? 1u : channel==1u ? 2u : 3u);
    fl_frame_u(&x,2u,c->source_clock=='V' ? 0u : 1u); fl_frame_u(&x,3u,c->source_us);
    fl_frame_u(&x,4u,c->receipt_us); fl_frame_u(&x,5u,c->quality); (void)fl_device_enqueue(d,&x);
}
bool fl_device_tick(fl_device *d,uint64_t now,uint32_t due,bool adc_valid,uint16_t adc_raw,
                    bool trip,bool arm,bool reset,fl_output *out) {
    uint32_t required=d->core.profile==1u ? 33u : 62u,changed=0u,op; size_t i; bool fresh;
    if(due==0u) return false;
    d->tick_count=fl_saturating_add(d->tick_count,1u); d->overruns=fl_saturating_add(d->overruns,due-1u);
    fresh=fl_intent_fresh(&d->intent,now);
    if(!fresh) { d->intent.operation=0u; d->intent.heat_ppm=0u; }
    op=d->intent.operation; d->intent.operation=0u;
    if(d->mode==2u) op=fl_gpio_operation(&d->edges,arm,reset,op,now);
    if(d->core.configured) {
        if(d->mode==2u) {
            int32_t level=adc_valid && adc_raw<=4095u ? (int32_t)(((uint32_t)adc_raw*1000000u+2047u)/4095u) : 0;
            /* Assumed illustrative ADC transfer. No measured height calibration. */
            if(fl_core_observe_device(&d->core,d->core.epoch,d->core_tick_sequence,'D',now,now,1u,
                adc_valid && adc_raw<=4095u ? 1u : 0u,adc_valid && adc_raw<=4095u ? level : 0)) changed|=1u;
            if(fl_core_observe_device(&d->core,d->core.epoch,d->core_tick_sequence,'D',now,now,6u,1u,trip ? 1 : 0)) changed|=32u;
        } else for(i=0u;i<d->observation_count;i++) {
            const fl_frame *o=&d->observations[i].frame;
            uint32_t channel=(uint32_t)o->values[0].magnitude;
            /* Delivery/acquisition age is local D. Source clocks remain separate. */
            if(fl_core_observe_device(&d->core,o->epoch,o->sequence,o->clock,o->time_us,d->observations[i].receipt_us,channel,
                (uint32_t)o->values[1].magnitude,fl_frame_i32(o,2u))) changed|=UINT32_C(1)<<(channel-1u);
            else d->rx_rejected=fl_saturating_add(d->rx_rejected,1u);
        }
    }
    d->observation_count=0u;
    if(!d->core.configured || !fl_core_step_device(&d->core,d->core.epoch,d->core_tick_sequence,now,op,
        d->intent.heat_ppm,d->mode==2u || fresh,out)) return false;
    {
        fl_frame q=record(d,'Q',out->command_seq,now,6u),r=record(d,'R',d->core_tick_sequence,now,7u);
        fl_frame n=record(d,'N',d->tick_count,now,7u);
        fl_frame_u(&q,0u,d->core.config.lease_us); fl_frame_u(&q,1u,out->heat_ppm); fl_frame_u(&q,2u,out->pump_ppm);
        fl_frame_u(&q,3u,out->valve_ppm); fl_frame_u(&q,4u,(uint32_t)out->state); fl_frame_u(&q,5u,(uint32_t)out->reason);
        fl_frame_u(&r,0u,out->command_seq); fl_frame_u(&r,1u,(uint32_t)out->state); fl_frame_u(&r,2u,(uint32_t)out->reason);
        fl_frame_u(&r,3u,out->valid_mask); fl_frame_u(&r,4u,out->stale_mask); fl_frame_u(&r,5u,out->max_age_us); fl_frame_u(&r,6u,out->operation_result);
        fl_frame_u(&n,0u,d->mode); fl_frame_u(&n,1u,d->tick_count); fl_frame_u(&n,2u,d->overruns);
        fl_frame_u(&n,3u,d->rx_rejected); fl_frame_u(&n,4u,d->tx_dropped); fl_frame_u(&n,5u,d->watchdog_reboot ? 1u : 0u);
        fl_frame_u(&n,6u,d->mode==2u || fresh ? 1u : 0u);
        (void)fl_device_enqueue(d,&q); (void)fl_device_enqueue(d,&r); (void)fl_device_enqueue(d,&n);
        for(i=0u;i<FL_CHANNELS;i++) if((changed & required & (UINT32_C(1)<<i))!=0u) channel_record(d,(uint32_t)i+1u,now);
    }
    d->core_tick_sequence++; return true;
}
