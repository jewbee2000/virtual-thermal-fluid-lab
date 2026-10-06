#ifndef FL_CORE_H
#define FL_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define FL_CHANNELS 6u
#define FL_PPM 1000000u
typedef enum { FL_DISARMED=0, FL_RUNNING=1, FL_TRIPPED=2 } fl_state;
typedef enum { FL_NONE=0, FL_SEPARATE_TRIP=1, FL_WALL_HOT=2,
    FL_LIQUID_HOT=3, FL_INVALID_INPUT=4, FL_RANGE_INPUT=5, FL_STALE_INPUT=6 } fl_reason;
typedef struct {
    uint32_t profile, version, id, tick_us, stale_us, lease_us;
    uint64_t kp_scaled, ki_scaled;
    uint32_t ff_ppm, normal_valve_ppm;
    int32_t target_i, min_control_i, max_control_i;
    uint32_t min_temp_mk, max_temp_mk, hot_trip_mk, wall_trip_mk;
} fl_config;
typedef struct {
    bool present, sequence_seen, good_seen;
    uint8_t quality;
    int32_t value_i;
    uint32_t sequence;
    uint64_t source_us, receipt_us, good_source_us;
} fl_channel;
typedef struct {
    uint32_t heat_ppm, pump_ppm, valve_ppm, command_seq;
    fl_state state;
    fl_reason reason;
    uint32_t valid_mask, stale_mask, operation_result;
    uint64_t max_age_us;
} fl_output;
typedef struct {
    uint32_t epoch, profile, last_step_seq, command_seq;
    uint64_t last_step_us;
    bool bound, configured, step_seen;
    fl_config config;
    fl_channel channels[FL_CHANNELS];
    fl_state state;
    fl_reason reason;
    double integral;
} fl_core;

/* No allocation, I/O, wall clock, plant state or fault labels in this API. */
void fl_core_init(fl_core *core);
bool fl_sequence_newer(uint32_t newer, uint32_t older);
bool fl_core_bind(fl_core *core, uint32_t epoch, uint32_t profile);
bool fl_config_valid(const fl_config *config);
bool fl_core_configure(fl_core *core, const fl_config *config);
bool fl_core_observe(fl_core *core, uint32_t epoch, uint32_t sequence,
    uint64_t sample_us, uint64_t receipt_us, uint32_t channel, uint32_t quality, int32_t value_i);
bool fl_core_step(fl_core *core, uint32_t epoch, uint32_t sequence,
    uint64_t now_us, uint32_t operation, uint32_t heat_demand_ppm, fl_output *output);
#endif
