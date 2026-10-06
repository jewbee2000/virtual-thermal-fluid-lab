# Integrated campaign data contract v1

Frozen before M5 integrated outcomes on 2026-10-06. CAMPAIGN.md supplies the
case definitions, threshold rationale and independent oracles. This interface
shares execution records with replay. No field overrides a required rule or
acceptance threshold. Model/controller parameters are assumed educational choices.

## API and input

`normalize_campaign(mapping) -> CampaignConfig` and `load_campaign(path)` return
immutable configuration. Reject duplicate JSON keys, unknown fields, bool as
numbers, nonfinite values, invalid ranges and unsupported versions before running.
Short inputs may omit defaults; normalized exports include every field.

`run_campaign(cfg, executable, trace_dir, *, solver=None) -> (rows, summary)`
requires the real C executable and a new trace directory; no Python fallback.
`write_campaign(out,cfg,rows,summary,executable)` exports results.
`evaluate_campaign(cfg,rows,wire_evidence)` independently judges the evidence.
Failure preserves partial accepted state and subprocess streams.

Closed normalized root: schema_version=1, topology='thermal_loop', name, case_id,
duration_us, tick_us, seed, initial, model, controller, sensor_adapter,
initial_heat_demand, events, solver. Initial has wall_temperature_k,
hot_temperature_k, cold_temperature_k, pump_speed and valve_opening. Model is
ThermalParameters v1; controller is full protocol.Configuration thermal v1 with
matching tick_us; sensor_adapter has separate_wall_trip_k; solver is
ThermalSolverConfig v1. Executed effective solver settings also appear in reports.

Events have unique event_id, type, time_us and only type-specific fields:

| type | Additional fields |
| --- | --- |
| heat_demand | command in [0,1] |
| model_coefficients | At least one nonnegative hot_conductance_w_k, sink_conductance_w_k, pipe_resistance_pa_s2_m6, valve_resistance_pa_s2_m6 |
| observation_link | channel=2, mode=drop/delay/reorder/corrupt/truncate; end_us for spans, delay_us for delay |
| observation_override | channels=[3,5], mode=freeze/bias; optional end_us; declared integer frozen values or bias_k |
| command_link | mode=drop/delay/drop_ack, end_us; delay_us for delay |
| actuator_override | At least one normalized heat_command/pump_command/valve_command; optional end_us |
| restart | nonzero newer uint32 epoch under protocol ordering policy |
| operation | operation=ARM/RESET |

Schedule fields are integer microseconds, excluding bool. Active events start
before horizon; spans obey start<end<=duration. Reject overlaps on a shared
channel/link. Operations and restarts tick-align. Other exogenous events cause
exact integration splits: pre-event sample, event application, post-event sample,
then due acquisition/control. Unique increasing sample_id orders duplicate times.
Numerical terminal roots retain fractional microseconds rather than becoming ticks.

All valve/pipe/pump quadratic resistance coefficients use Pa s²/m⁶. A draft
Pa s/m³ valve label was corrected before execution; equations/gates are unchanged.

## Fixed telemetry fieldset

JSON rows have identical closed fields. CSV uses the same columns and empty cells
for null. Null means unavailable, never fabricated zero.

| Group | Fields |
| --- | --- |
| Identity/time | schema_version, run_name, topology, sample_id, record_type, time_us, time_s, epoch, session_origin_us, wire_time_us, controller_tick_id, reply_time_us, event_ids, event_phase |
| C reply/cache | controller_state, trip_reason, operation, operation_result, valid_mask, stale_mask, max_age_us, observation_cache_source, cache_matches_reply |
| Truth | wall_temperature_k, hot_temperature_k, cold_temperature_k, flow_m3_s, pump_pressure_pa, pump_speed, valve_opening, heat_in_j, heat_rejected_j, energy_residual_j |
| Observed | observed_flow_m3_s, observed_hot_temperature_k, observed_cold_temperature_k, observed_wall_temperature_k, observed_separate_trip |
| Requests | requested_heat_command, requested_pump_command, requested_valve_command |
| Live lease | lease_heat_command, lease_pump_command, lease_valve_command, command_sequence, command_expires_us, command_expired |
| Fault-applied input | fault_heat_command, fault_pump_command, fault_valve_command, heat_demand_command, applied_heat_w |
| Coefficients | effective_hot_conductance_w_k, effective_sink_conductance_w_k, effective_pipe_resistance_pa_s2_m6, effective_valve_resistance_pa_s2_m6 |
| Stop/diagnostic | terminal_boundary, solver_diagnostic_id |

Each flow/hot/cold/wall/separate prefix also has _value_i, _quality, _sequence,
_source_time_us, _receipt_time_us, _last_good_source_time_us and _age_us.
Absent values are null. Invalid/missing samples preserve last-good source age.
Age refers to the current absolute sample time; R fields refer to reply_time_us.
An event/terminal row cannot imply new acquisition/reply. observation_cache_source
is 'reconstructed_from_retained_wire'; cache_matches_reply compares with actual R.

record_type: controller_tick/event_boundary/command_expiry/command_arrival/
terminal_boundary/solver_failure. event_ids joins declared IDs or is empty;
event_phase is null/before/after. Requested, live lease, applied physical input
and actuator state remain distinct replay tracks.

## Summary, raw audit and manifest

Closed summary root: schema_version, name, topology, case_id,
requested_duration_us, last_time_us, completed_horizon, terminal_boundary,
run_failure, solver, model, controller, scenario, metrics, evaluation,
solver_diagnostics, wire_evidence, execution. Metrics retain per-temperature
sampled peaks, global_sampled_peak_k, largest_sample_gap_s,
global_peak_upper_bound_k, energy_residual_max_j, true/observed last30 tracking
errors, integral_flow_error_m3, first trip time/reason, terminal time, independent
expected trip time, prefault temperatures, final30 means, latency and wall time.
Peak bound is null when premises/coverage fail. General interval diagnostics do
not replace the frozen global-peak proof in CAMPAIGN.md.

Evaluation has TH01–TH12 each {status,evidence}, with status PASS/FAIL/
NOT_APPLICABLE/UNASSESSABLE. expectation_pass, completion_status and
containment_status are separate. Corrupt/missing/inconsistent evidence cannot pass.
An expected boundary hazard may pass expectation while containment is FAILED.

Audit rereads retained stdin/stdout/stderr and adapter event files; independently
checks LF framing, CRC, canonical fields, O acceptance/order/last-good age and
actual Q/R pairs. Bad-frame proof requires rejected raw bytes, unchanged prior
cache, genuine subsequent sample and captured rejection. Injection labels alone
are insufficient. Q delivery, expiry and ACK are separate; delayed Q never extends
its original lease. No-LF swallowed STEP/process EOF fails rather than being
called recoverable truncation.

Manifest: schema_version, scenario, model, solver, controller, execution, clocks,
quantization, artifacts SHA256 map (excluding manifest itself). Execution records
actual binary/hash, config hash, portable source hash, C core hash, compiler/build,
Python/dependencies and explicit-root Git revision/dirty. Hash raw captures,
events, telemetry and separate config exports. Label absolute virtual time,
per-epoch V/session origin and host monotonic wall time. Never subtract V from D.

Canonical source framing remains sorted POSIX path, NUL, uint64 big-endian byte
length, then raw bytes. Coverage adds firmware/**/*.c, firmware/**/*.h,
firmware/**/*.cmake, firmware/**/CMakeLists.txt, root CMakeLists.txt and
scripts/**/*.ps1 to Python/schema/dependency inputs. Exclude generated artifacts
and external SDK/tools, recording their actual revisions/hashes separately.
Tank APIs remain compatible. Physical validation NOT_STARTED and board execution
NOT_EXECUTED remain until actual evidence changes those categories.
