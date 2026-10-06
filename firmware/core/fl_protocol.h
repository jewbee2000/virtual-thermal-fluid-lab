#ifndef FL_PROTOCOL_H
#define FL_PROTOCOL_H
#include "fl_core.h"
#define FL_FRAME_MAX 256u
#define FL_FIELDS_MAX 17u
typedef struct { uint64_t magnitude; bool negative; } fl_value;
typedef struct {
    char type, clock;
    uint32_t epoch, sequence;
    uint64_t time_us;
    size_t count;
    fl_value values[FL_FIELDS_MAX];
} fl_frame;
typedef struct {
    char bytes[FL_FRAME_MAX]; size_t length;
    uint64_t started_ms; bool discard, started;
} fl_stream;
typedef enum { FL_STREAM_NONE=0, FL_STREAM_FRAME=1, FL_STREAM_REJECTED=2 } fl_stream_result;
uint16_t fl_crc16(const unsigned char *bytes, size_t length);
bool fl_frame_valid(const fl_frame *frame);
bool fl_frame_decode(const char *bytes, size_t length, fl_frame *frame);
size_t fl_frame_encode(const fl_frame *frame, char bytes[FL_FRAME_MAX+1u]);
void fl_frame_u(fl_frame *frame, size_t index, uint64_t value);
void fl_frame_i(fl_frame *frame, size_t index, int32_t value);
int32_t fl_frame_i32(const fl_frame *frame, size_t index);
bool fl_frame_config(const fl_frame *frame, fl_config *config);
void fl_stream_init(fl_stream *stream);
bool fl_stream_expire(fl_stream *stream, uint64_t now_ms);
fl_stream_result fl_stream_byte(fl_stream *stream, unsigned char byte, uint64_t now_ms, fl_frame *frame);
bool fl_stream_eof(fl_stream *stream);
#endif
