/* Transport/wall clock live here, never in the portable controller tick. */
#include "fl_protocol.h"
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#include <fcntl.h>
static uint64_t monotonic_ms(void) { return (uint64_t)GetTickCount64(); }
typedef struct {
    unsigned char bytes[FL_FRAME_MAX]; DWORD count, position;
    HANDLE ready, consumed, reader; bool eof;
} host_input;
static host_input input_state;
static DWORD WINAPI input_worker(LPVOID unused) {
    HANDLE input=GetStdHandle(STD_INPUT_HANDLE);
    (void)unused;
    for(;;) {
        if(WaitForSingleObject(input_state.consumed,INFINITE)!=WAIT_OBJECT_0) return 1u;
        input_state.position=0u;
        input_state.eof=!ReadFile(input,input_state.bytes,FL_FRAME_MAX,&input_state.count,NULL) || input_state.count==0u;
        SetEvent(input_state.ready);
        if(input_state.eof) return 0u;
    }
}
static bool input_init(void) {
    memset(&input_state,0,sizeof(input_state));
    input_state.ready=CreateEvent(NULL,TRUE,FALSE,NULL);
    input_state.consumed=CreateEvent(NULL,FALSE,TRUE,NULL);
    if(input_state.ready==NULL || input_state.consumed==NULL) return false;
    input_state.reader=CreateThread(NULL,0u,input_worker,NULL,0u,NULL);
    return input_state.reader!=NULL;
}
static int read_byte(unsigned char *b) {
    DWORD ready=WaitForSingleObject(input_state.ready,10u);
    if(ready==WAIT_TIMEOUT) return 0;
    if(ready!=WAIT_OBJECT_0 || input_state.eof) return -1;
    *b=input_state.bytes[input_state.position++];
    if(input_state.position==input_state.count) {
        ResetEvent(input_state.ready);
        SetEvent(input_state.consumed);
    }
    return 1;
}
#else
#include <unistd.h>
#include <poll.h>
#include <time.h>
static uint64_t monotonic_ms(void) { struct timespec t; (void)clock_gettime(CLOCK_MONOTONIC,&t); return (uint64_t)t.tv_sec*1000u+(uint64_t)t.tv_nsec/1000000u; }
static int read_byte(unsigned char *b) { struct pollfd p={0,POLLIN,0}; int ready=poll(&p,1u,10); if(ready<0) return -1; if(ready==0) return 0; return read(0,b,1u)==1 ? 1 : -1; }
#endif
static bool send_frame(const fl_frame *f) {
    char bytes[FL_FRAME_MAX+1u]; size_t length=fl_frame_encode(f,bytes);
    return length!=0u && fwrite(bytes,1u,length,stdout)==length && fflush(stdout)==0;
}
static fl_frame frame(char type,uint32_t epoch,uint32_t seq,uint64_t now,size_t n) {
    fl_frame f; memset(&f,0,sizeof(f)); f.type=type; f.clock='V'; f.epoch=epoch; f.sequence=seq; f.time_us=now; f.count=n; return f;
}
int main(void) {
    fl_core c; fl_stream stream; fl_frame incoming, boot=frame('B',0u,0u,0u,2u);
    fl_frame staged[32]; size_t staged_count=0u; bool ack_seen=false; uint32_t ack_seq=0u;
    unsigned char byte; int result;
#ifdef _WIN32
    if(_setmode(_fileno(stdin),_O_BINARY)==-1 || _setmode(_fileno(stdout),_O_BINARY)==-1) return 2;
    if(!input_init()) return 2;
#endif
    fl_core_init(&c); fl_stream_init(&stream); fl_frame_u(&boot,0u,100u); fl_frame_u(&boot,1u,0u);
    if(!send_frame(&boot)) return 2;
    for(;;) {
        uint64_t wall_ms=monotonic_ms();
        if(fl_stream_expire(&stream,wall_ms)) fputs("frame assembly timeout; discard until LF\n",stderr);
        result=read_byte(&byte);
        if(result<0) { if(fl_stream_eof(&stream)) { fputs("unfinished frame at EOF\n",stderr); return 3; } return 0; }
        if(result==0) continue;
        result=(int)fl_stream_byte(&stream,byte,monotonic_ms(),&incoming);
        if(result==FL_STREAM_REJECTED) { fputs("rejected frame\n",stderr); continue; }
        if(result!=FL_STREAM_FRAME) continue;
        if(incoming.clock!='V') { fputs("host requires virtual clock\n",stderr); continue; }
        if(incoming.type=='H') {
            uint32_t old_epoch=c.epoch;
            if(!fl_core_bind(&c,incoming.epoch,(uint32_t)incoming.values[0].magnitude)) fputs("rejected handshake\n",stderr);
            else if(old_epoch!=c.epoch) { staged_count=0u; ack_seen=false; }
        } else if(incoming.type=='C') {
            fl_config config;
            if(incoming.epoch!=c.epoch || !fl_frame_config(&incoming,&config) || !fl_core_configure(&c,&config)) fputs("rejected configuration\n",stderr);
        } else if(incoming.type=='O') {
            if(!c.bound || incoming.epoch!=c.epoch) fputs("rejected observation epoch\n",stderr);
            else if(staged_count>=32u) fputs("observation staging overflow\n",stderr);
            else staged[staged_count++]=incoming;
        } else if(incoming.type=='A') {
            /* ACK is diagnostic intent. It never drives PI or extends a lease. */
            if(incoming.epoch!=c.epoch || (ack_seen && !fl_sequence_newer(incoming.sequence,ack_seq))) fputs("rejected acknowledgement\n",stderr);
            else { ack_seen=true; ack_seq=incoming.sequence; }
        } else if(incoming.type=='S') {
            fl_output out; size_t i;
            /* Validate reliable schedule before any staged cache mutation. */
            bool schedule=c.configured && incoming.epoch==c.epoch &&
                ((!c.step_seen && incoming.sequence==0u && incoming.time_us==0u) ||
                (c.step_seen && incoming.sequence==c.last_step_seq+1u &&
                 UINT64_MAX-c.last_step_us>=c.config.tick_us && incoming.time_us==c.last_step_us+c.config.tick_us));
            if(!schedule || (c.profile==1u && incoming.values[1].magnitude!=0u)) { staged_count=0u; fputs("rejected STEP schedule\n",stderr); continue; }
            for(i=0u;i<staged_count;i++) {
                const fl_frame *o=&staged[i];
                if(!fl_core_observe(&c,o->epoch,o->sequence,o->time_us,incoming.time_us,
                    (uint32_t)o->values[0].magnitude,(uint32_t)o->values[1].magnitude,fl_frame_i32(o,2u))) fputs("rejected observation order/time\n",stderr);
            }
            staged_count=0u;
            if(!fl_core_step(&c,incoming.epoch,incoming.sequence,incoming.time_us,
                (uint32_t)incoming.values[0].magnitude,(uint32_t)incoming.values[1].magnitude,&out)) { fputs("rejected STEP\n",stderr); continue; }
            {
                fl_frame q=frame('Q',c.epoch,out.command_seq,incoming.time_us,6u);
                fl_frame r=frame('R',c.epoch,incoming.sequence,incoming.time_us,7u);
                fl_frame_u(&q,0u,c.config.lease_us); fl_frame_u(&q,1u,out.heat_ppm); fl_frame_u(&q,2u,out.pump_ppm);
                fl_frame_u(&q,3u,out.valve_ppm); fl_frame_u(&q,4u,(uint32_t)out.state); fl_frame_u(&q,5u,(uint32_t)out.reason);
                fl_frame_u(&r,0u,out.command_seq); fl_frame_u(&r,1u,(uint32_t)out.state); fl_frame_u(&r,2u,(uint32_t)out.reason);
                fl_frame_u(&r,3u,out.valid_mask); fl_frame_u(&r,4u,out.stale_mask); fl_frame_u(&r,5u,out.max_age_us); fl_frame_u(&r,6u,out.operation_result);
                if(!send_frame(&q) || !send_frame(&r)) return 2;
            }
        } else fputs("unsupported host input record\n",stderr);
    }
}
