#include "fl_protocol.h"
#include <string.h>
#include <stdio.h>
#include <inttypes.h>

uint16_t fl_crc16(const unsigned char *p, size_t n) {
    uint16_t crc=0u; size_t i; unsigned j;
    for(i=0u;i<n;i++) { crc^=(uint16_t)((uint16_t)p[i]<<8u);
        for(j=0u;j<8u;j++) crc=(uint16_t)((crc & 0x8000u)!=0u ? ((uint32_t)crc<<1u)^0x1021u : (uint32_t)crc<<1u);
    } return crc;
}
void fl_frame_u(fl_frame *f,size_t i,uint64_t v) { if(i<FL_FIELDS_MAX) { f->values[i].magnitude=v; f->values[i].negative=false; } }
void fl_frame_i(fl_frame *f,size_t i,int32_t v) { if(i<FL_FIELDS_MAX) { f->values[i].negative=v<0; f->values[i].magnitude=v<0 ? (uint64_t)(-(int64_t)v) : (uint64_t)v; } }
int32_t fl_frame_i32(const fl_frame *f,size_t i) { return f->values[i].negative ? (int32_t)(-(int64_t)f->values[i].magnitude) : (int32_t)f->values[i].magnitude; }
static bool bound(const fl_frame *f,size_t i,uint64_t max,bool sign) {
    return i<f->count && (!f->values[i].negative || sign) &&
        (!f->values[i].negative || f->values[i].magnitude!=0u) &&
        f->values[i].magnitude <= (f->values[i].negative ? UINT64_C(2147483648) : max);
}
bool fl_frame_config(const fl_frame *f,fl_config *p) {
    size_t i;
    if(f->type!='C' || f->count!=17u) return false;
    /* Public conversion never narrows an unchecked caller-constructed field. */
    for(i=0u;i<17u;i++) {
        uint64_t max=(i==6u || i==7u) ? UINT64_C(1000000000000) : UINT32_MAX;
        if(i>=10u && i<=12u) max=INT32_MAX;
        if(!bound(f,i,max,i==11u)) return false;
    }
    memset(p,0,sizeof(*p));
    p->profile=(uint32_t)f->values[0].magnitude; p->version=(uint32_t)f->values[1].magnitude;
    p->id=(uint32_t)f->values[2].magnitude; p->tick_us=(uint32_t)f->values[3].magnitude;
    p->stale_us=(uint32_t)f->values[4].magnitude; p->lease_us=(uint32_t)f->values[5].magnitude;
    p->kp_scaled=f->values[6].magnitude; p->ki_scaled=f->values[7].magnitude;
    p->ff_ppm=(uint32_t)f->values[8].magnitude; p->normal_valve_ppm=(uint32_t)f->values[9].magnitude;
    p->target_i=fl_frame_i32(f,10u); p->min_control_i=fl_frame_i32(f,11u); p->max_control_i=fl_frame_i32(f,12u);
    p->min_temp_mk=(uint32_t)f->values[13].magnitude; p->max_temp_mk=(uint32_t)f->values[14].magnitude;
    p->hot_trip_mk=(uint32_t)f->values[15].magnitude; p->wall_trip_mk=(uint32_t)f->values[16].magnitude;
    return fl_config_valid(p);
}
bool fl_frame_valid(const fl_frame *f) {
    size_t n=0u,i; fl_config p;
    if(f->clock!='V' && f->clock!='D') return false;
    switch(f->type) {
    case 'B': n=2u; break; case 'H': n=1u; break; case 'C': n=17u; break;
    case 'O': n=3u; break; case 'S': case 'U': n=2u; break; case 'Q': n=6u; break;
    case 'A': n=2u; break; case 'R': case 'N': n=7u; break; case 'X': n=6u; break; default:return false;
    }
    if(f->count!=n) return false;
    for(i=0u;i<n;i++) {
        bool sign=(f->type=='O' && i==2u) || (f->type=='C' && i==11u);
        uint64_t max=UINT32_MAX;
        if(sign || (f->type=='C' && (i==10u || i==12u))) max=INT32_MAX;
        if((f->type=='C' && (i==6u || i==7u)) || (f->type=='R' && i==5u) ||
           (f->type=='X' && (i==3u || i==4u))) max=UINT64_MAX;
        if(!bound(f,i,max,sign)) return false;
    }
    switch(f->type) {
    case 'B': return f->epoch==0u && f->values[0].magnitude==100u && f->values[1].magnitude<=2u;
    case 'H': return f->epoch!=0u && f->values[0].magnitude>=1u && f->values[0].magnitude<=2u;
    case 'C': return fl_frame_config(f,&p);
    case 'O': return f->values[0].magnitude>=1u && f->values[0].magnitude<=6u &&
        f->values[1].magnitude<=2u && (f->values[1].magnitude!=2u || f->values[2].magnitude==0u) &&
        (f->values[0].magnitude!=6u || (!f->values[2].negative && f->values[2].magnitude<=1u));
    case 'S': case 'U': return f->values[0].magnitude<=2u && f->values[1].magnitude<=FL_PPM;
    case 'Q': return f->values[0].magnitude>=1u && f->values[0].magnitude<=10000000u &&
        f->values[1].magnitude<=FL_PPM && f->values[2].magnitude<=FL_PPM && f->values[3].magnitude<=FL_PPM &&
        f->values[4].magnitude<=2u && f->values[5].magnitude<=7u;
    case 'A': return f->values[1].magnitude<=1u;
    case 'R': return f->values[1].magnitude<=2u && f->values[2].magnitude<=7u &&
        f->values[3].magnitude<=63u && f->values[4].magnitude<=63u && f->values[6].magnitude<=2u;
    case 'X': return f->clock=='D' && f->values[0].magnitude>=1u && f->values[0].magnitude<=6u &&
        f->values[1].magnitude>=1u && f->values[1].magnitude<=3u && f->values[2].magnitude<=1u && f->values[5].magnitude<=2u;
    case 'N': return f->clock=='D' && f->values[0].magnitude>=1u && f->values[0].magnitude<=2u &&
        f->values[5].magnitude<=1u && f->values[6].magnitude<=1u;
    default: return false;
    }
}
static bool decimal(const char *s,fl_value *v,bool sign) {
    uint64_t number=0u; size_t i=0u;
    v->negative=false;
    if(s[0]=='-') { if(!sign) return false; v->negative=true; i=1u; }
    if(s[i]=='\0' || (s[i]=='0' && s[i+1u]!='\0') || (v->negative && s[i]=='0')) return false;
    for(;s[i]!='\0';i++) {
        unsigned digit;
        if(s[i]<'0' || s[i]>'9') return false;
        digit=(unsigned)(s[i]-'0');
        if(number>(UINT64_MAX-digit)/10u) return false;
        number=number*10u+digit;
    }
    v->magnitude=number; return true;
}
bool fl_frame_decode(const char *bytes,size_t len,fl_frame *f) {
    char copy[FL_FRAME_MAX], *fields[24]; size_t i,count=0u,star; uint16_t checksum=0u; fl_value v;
    if(len<15u || len>FL_FRAME_MAX || bytes[len-1u]!='\n') return false;
    star=len-6u;
    if(bytes[star]!='*') return false;
    for(i=0u;i<len-1u;i++) if((unsigned char)bytes[i]<33u || (unsigned char)bytes[i]>126u) return false;
    for(i=star+1u;i<len-1u;i++) {
        char c=bytes[i]; unsigned hex;
        if(c>='0' && c<='9') hex=(unsigned)(c-'0');
        else if(c>='A' && c<='F') hex=(unsigned)(c-'A')+10u; else return false;
        checksum=(uint16_t)((checksum<<4u)|hex);
    }
    if(fl_crc16((const unsigned char*)bytes,star)!=checksum) return false;
    memcpy(copy,bytes,star); copy[star]='\0'; fields[count++]=copy;
    for(i=0u;i<star;i++) if(copy[i]=='|') { copy[i]='\0'; if(count>=24u) return false; fields[count++]=copy+i+1u; }
    if(count<8u || strcmp(fields[0],"F")!=0 || strcmp(fields[1],"1")!=0 ||
        strlen(fields[2])!=1u || strlen(fields[5])!=1u) return false;
    memset(f,0,sizeof(*f)); f->type=fields[2][0]; f->clock=fields[5][0]; f->count=count-7u;
    if(f->count>FL_FIELDS_MAX || !decimal(fields[3],&v,false) || v.magnitude>UINT32_MAX) return false;
    f->epoch=(uint32_t)v.magnitude;
    if(!decimal(fields[4],&v,false) || v.magnitude>UINT32_MAX) return false;
    f->sequence=(uint32_t)v.magnitude;
    if(!decimal(fields[6],&v,false)) return false;
    f->time_us=v.magnitude;
    for(i=0u;i<f->count;i++) if(!decimal(fields[i+7u],&f->values[i],
        (f->type=='O' && i==2u) || (f->type=='C' && i==11u))) return false;
    return fl_frame_valid(f);
}
size_t fl_frame_encode(const fl_frame *f,char bytes[FL_FRAME_MAX+1u]) {
    int written; size_t used,i; uint16_t crc;
    if(!fl_frame_valid(f)) return 0u;
    written=snprintf(bytes,FL_FRAME_MAX+1u,"F|1|%c|%" PRIu32 "|%" PRIu32 "|%c|%" PRIu64,
        f->type,f->epoch,f->sequence,f->clock,f->time_us);
    if(written<0 || (size_t)written>FL_FRAME_MAX-6u) return 0u;
    used=(size_t)written;
    for(i=0u;i<f->count;i++) {
        written=snprintf(bytes+used,FL_FRAME_MAX+1u-used,"|%s%" PRIu64,
            f->values[i].negative ? "-" : "", f->values[i].magnitude);
        if(written<0 || (size_t)written>FL_FRAME_MAX-6u-used) return 0u;
        used+=(size_t)written;
    }
    crc=fl_crc16((const unsigned char*)bytes,used);
    written=snprintf(bytes+used,FL_FRAME_MAX+1u-used,"*%04X\n",(unsigned)crc);
    return written==6 ? used+6u : 0u;
}
void fl_stream_init(fl_stream *s) { memset(s,0,sizeof(*s)); }
bool fl_stream_expire(fl_stream *s,uint64_t now) {
    if(s->started && !s->discard && now-s->started_ms>=500u) {
        s->discard=true; s->length=0u; return true;
    } return false;
}
fl_stream_result fl_stream_byte(fl_stream *s,unsigned char byte,uint64_t now,fl_frame *f) {
    (void)fl_stream_expire(s,now);
    if(s->discard) { if(byte=='\n') fl_stream_init(s); return FL_STREAM_NONE; }
    if(!s->started) { s->started=true; s->started_ms=now; }
    if(s->length>=FL_FRAME_MAX-1u && byte!='\n') { s->discard=true; s->length=0u; return FL_STREAM_REJECTED; }
    s->bytes[s->length++]=(char)byte;
    if(byte=='\n') {
        bool okay=fl_frame_decode(s->bytes,s->length,f); fl_stream_init(s);
        return okay ? FL_STREAM_FRAME : FL_STREAM_REJECTED;
    } return FL_STREAM_NONE;
}
bool fl_stream_eof(fl_stream *s) { bool unfinished=s->started || s->discard; fl_stream_init(s); return unfinished; }
