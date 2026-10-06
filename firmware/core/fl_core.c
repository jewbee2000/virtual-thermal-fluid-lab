#include "fl_core.h"
#include <string.h>
#include <math.h>

void fl_core_init(fl_core *c) { memset(c, 0, sizeof(*c)); }
bool fl_sequence_newer(uint32_t n, uint32_t o) {
    uint32_t delta = n-o;
    return delta != 0u && delta < UINT32_C(0x80000000);
}
bool fl_core_bind(fl_core *c, uint32_t epoch, uint32_t profile) {
    if (epoch == 0u || (profile != 1u && profile != 2u)) return false;
    if (c->bound && epoch == c->epoch) return profile == c->profile;
    if (c->bound && !fl_sequence_newer(epoch, c->epoch)) return false;
    fl_core_init(c);
    c->bound=true; c->epoch=epoch; c->profile=profile;
    return true;
}
bool fl_config_valid(const fl_config *p) {
    if ((p->profile != 1u && p->profile != 2u) || p->version != 1u ||
        p->tick_us < 1u || p->tick_us > 1000000u || p->stale_us < 1u ||
        p->stale_us > 10000000u || p->lease_us < 1u || p->lease_us > 10000000u ||
        p->kp_scaled > UINT64_C(1000000000000) || p->ki_scaled > UINT64_C(1000000000000) ||
        p->ff_ppm > FL_PPM || p->normal_valve_ppm > FL_PPM ||
        p->target_i < 0 || p->max_control_i < 0 || p->min_control_i >= p->max_control_i || p->target_i < p->min_control_i ||
        p->target_i > p->max_control_i) return false;
    if (p->profile == 1u) return p->min_temp_mk == 0u && p->max_temp_mk == 0u &&
        p->hot_trip_mk == 0u && p->wall_trip_mk == 0u;
    return p->min_control_i >= 0 && p->min_temp_mk < p->max_temp_mk &&
        p->max_temp_mk <= 1000000u && p->hot_trip_mk > p->min_temp_mk &&
        p->hot_trip_mk <= p->max_temp_mk && p->wall_trip_mk > p->min_temp_mk &&
        p->wall_trip_mk <= p->max_temp_mk;
}
static bool same_config(const fl_config *a, const fl_config *b) {
    /* Compare fields; struct padding is deliberately irrelevant. */
    return a->profile==b->profile && a->version==b->version && a->id==b->id &&
        a->tick_us==b->tick_us && a->stale_us==b->stale_us && a->lease_us==b->lease_us &&
        a->kp_scaled==b->kp_scaled && a->ki_scaled==b->ki_scaled && a->ff_ppm==b->ff_ppm &&
        a->normal_valve_ppm==b->normal_valve_ppm && a->target_i==b->target_i &&
        a->min_control_i==b->min_control_i && a->max_control_i==b->max_control_i &&
        a->min_temp_mk==b->min_temp_mk && a->max_temp_mk==b->max_temp_mk &&
        a->hot_trip_mk==b->hot_trip_mk && a->wall_trip_mk==b->wall_trip_mk;
}
bool fl_core_configure(fl_core *c, const fl_config *p) {
    if (!c->bound || p->profile != c->profile || !fl_config_valid(p)) return false;
    if (c->configured) return same_config(&c->config,p);
    if (c->step_seen || c->state != FL_DISARMED) return false;
    c->config=*p; c->configured=true; return true;
}
bool fl_core_observe(fl_core *c, uint32_t epoch, uint32_t seq, uint64_t sample,
                    uint64_t receipt, uint32_t channel, uint32_t quality, int32_t value) {
    fl_channel *p;
    if (!c->bound || epoch != c->epoch || channel < 1u || channel > FL_CHANNELS ||
        quality > 2u || sample > receipt || (quality==2u && value!=0) ||
        (channel==6u && value!=0 && value!=1)) return false;
    p=&c->channels[channel-1u];
    if (p->sequence_seen && (!fl_sequence_newer(seq,p->sequence) || sample < p->source_us)) return false;
    p->present=true; p->sequence_seen=true; p->sequence=seq; p->quality=(uint8_t)quality;
    p->value_i=value; p->source_us=sample; p->receipt_us=receipt;
    if (quality==1u) { p->good_seen=true; p->good_source_us=sample; }
    return true;
}
static fl_reason inspect(const fl_core *c, uint64_t now, fl_output *o) {
    uint32_t required=c->profile==1u ? 33u : 62u;
    bool invalid=false, range=false, stale=false;
    size_t i;
    o->valid_mask=0u; o->stale_mask=0u; o->max_age_us=0u;
    for (i=0u;i<FL_CHANNELS;i++) {
        const fl_channel *p=&c->channels[i];
        uint32_t bit=UINT32_C(1) << i;
        uint64_t age=p->good_seen && p->good_source_us<=now ? now-p->good_source_us : UINT64_MAX;
        if (p->present && p->quality==1u) o->valid_mask |= bit;
        if (age>c->config.stale_us) o->stale_mask |= bit;
        if ((required & bit)==0u) continue;
        if (age>o->max_age_us) o->max_age_us=age;
        if (!p->present || p->quality!=1u) invalid=true;
        if (age>c->config.stale_us) stale=true;
        if (p->present && p->quality==1u) {
            if (i==0u || i==1u) {
                if (p->value_i<c->config.min_control_i || p->value_i>c->config.max_control_i) range=true;
            } else if (i>=2u && i<=4u) {
                if (p->value_i<0 || (uint32_t)p->value_i<c->config.min_temp_mk ||
                    (uint32_t)p->value_i>c->config.max_temp_mk) range=true;
            }
        }
    }
    /* Priority is fixed; invalid values never manufacture a temperature/trip. */
    if (c->channels[5].present && c->channels[5].quality==1u && c->channels[5].value_i==1) return FL_SEPARATE_TRIP;
    if (c->profile==2u) {
        if (c->channels[4].quality==1u && c->channels[4].value_i>=(int32_t)c->config.wall_trip_mk) return FL_WALL_HOT;
        if (c->channels[2].quality==1u && c->channels[2].value_i>=(int32_t)c->config.hot_trip_mk) return FL_LIQUID_HOT;
    }
    return invalid ? FL_INVALID_INPUT : range ? FL_RANGE_INPUT : stale ? FL_STALE_INPUT : FL_NONE;
}
bool fl_core_step(fl_core *c, uint32_t epoch, uint32_t seq, uint64_t now,
                  uint32_t op, uint32_t heat, fl_output *o) {
    fl_reason detected;
    if (!c->bound || !c->configured || epoch!=c->epoch || op>2u || heat>FL_PPM ||
        (c->profile==1u && heat!=0u)) return false;
    if (!c->step_seen) { if (seq!=0u || now!=0u) return false; }
    else if (seq!=c->last_step_seq+1u || UINT64_MAX-c->last_step_us<c->config.tick_us ||
             now!=c->last_step_us+c->config.tick_us) return false;
    memset(o,0,sizeof(*o));
    detected=inspect(c,now,o);
    if (c->state==FL_RUNNING && detected!=FL_NONE) { c->state=FL_TRIPPED; c->reason=detected; c->integral=0.0; }
    if (op!=0u) {
        o->operation_result=2u;
        if (detected==FL_NONE && ((op==1u && c->state==FL_DISARMED) || (op==2u && c->state==FL_TRIPPED))) {
            c->state=op==1u ? FL_RUNNING : FL_DISARMED;
            c->reason=FL_NONE; c->integral=0.0; o->operation_result=1u;
        }
    }
    o->valve_ppm=c->profile==1u ? c->config.normal_valve_ppm : FL_PPM;
    if (c->state==FL_RUNNING) {
        double scale=c->profile==1u ? 1e6 : 1e9;
        double error=((double)c->config.target_i-(double)c->channels[c->profile==1u ? 0u : 1u].value_i)/scale;
        double kp=(double)c->config.kp_scaled/1e6, ki=(double)c->config.ki_scaled/1e6;
        double raw=(double)c->config.ff_ppm/1e6+kp*error+c->integral;
        if ((raw>=0.0 && raw<=1.0) || (raw>1.0 && error<0.0) || (raw<0.0 && error>0.0))
            c->integral += ki*error*((double)c->config.tick_us/1e6);
        raw=(double)c->config.ff_ppm/1e6+kp*error+c->integral;
        o->pump_ppm=raw<=0.0 ? 0u : raw>=1.0 ? FL_PPM : (uint32_t)floor(raw*1e6+0.5);
        o->valve_ppm=c->config.normal_valve_ppm;
        o->heat_ppm=c->profile==2u ? heat : 0u;
    } else {
        c->integral=0.0;
        if (c->state==FL_TRIPPED && c->profile==2u) o->pump_ppm=FL_PPM;
    }
    o->state=c->state; o->reason=c->reason; o->command_seq=c->command_seq++;
    c->last_step_seq=seq; c->last_step_us=now; c->step_seen=true;
    return true;
}
