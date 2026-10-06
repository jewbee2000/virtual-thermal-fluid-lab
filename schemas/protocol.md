# Firmware protocol v1 (frozen before M3)

Educational SIL/peripheral demonstration. No hardware execution or hard-real-time
claim. Same bounded C codec/core on host and Pico; Python implements a matching
codec using an independent standard-library checksum oracle.

M4's unreleased device-clock/intent/diagnostic extension is frozen separately in
docs/MCU_CONTRACT.md before target implementation. M3 host support remains the
base records below; target execution and extension gates are tracked in tasks.json.

```
F|1|TYPE|epoch|seq|clock|time_us|PAYLOAD*CCCC\n
```

ASCII, LF only, <=256 bytes including LF. `epoch`/`seq` uint32, `time_us` uint64;
clock V=virtual simulation or D=device monotonic. Decimal integers canonical:
no whitespace, plus, leading zeros, exponent, negative zero or overflow. Signed
int32 allowed only for observed values/configured sensor minima. Exact field
count and enum bounds; other records rejected. Checksum exactly four uppercase
hex digits covering F through last payload byte, excluding star/checksum/LF.

CRC-16/XMODEM: poly0x1021, init0, no reflection, xorout0. Published check
ASCII123456789 ->31C3. Primary [Redis implementation/vector](https://raw.githubusercontent.com/redis/redis/8.2/src/crc16.c),
independent Python [binascii.crc_hqx(bytes,0)](https://docs.python.org/3.12/library/binascii.html#binascii.crc_hqx).
Write the C bit-loop implementation against these parameters; tests use literal
goldens, not just production round trips. CRC is accidental-corruption detection,
not authentication; this bench does not expose live control over the internet.

## Fixed records

Commas below mean separate pipe fields, not literal commas.

| Type | Payload | Path |
| --- | --- | --- |
| B | firmware_version,mode | Startup, epoch0, DISARMED |
| H | profile | Reliable session binding:1 tank,2 thermal |
| C | Fixed configuration fields below | Reliable complete config before arming |
| O | channel,validity_flags,value_i | Experimental observation link |
| S | operation,heat_demand_ppm | Reliable host STEP; header advances virtual clock |
| Q | lease_us,heat_ppm,pump_ppm,valve_ppm,state,reason | Experimental requested-command link |
| A | command_seq,status | Experimental acknowledgement link |
| R | command_seq,state,reason,valid_mask,stale_mask,max_age_us,operation_result | Reliable STEP reply; seq echoes STEP |

Mode:0 host SIL,1 MCU virtual-plant link,2 MCU peripheral. States:0 DISARMED,
1 RUNNING,2 TRIPPED. Reasons:0 none,1 separate_trip,2 wall_hot,3 liquid_hot,
4 invalid_input,5 range_input,6 stale_input. Operation results:0 no transition,
1 successful operation,2 rejected operation. ACK status0 accepted,1 rejected.
Firmware version integer100 for initial0.1.0. Unknown enums reject.

Configuration payload order (version1):

```
profile|config_version|config_id|tick_us|stale_us|lease_us|
kp_scaled|ki_scaled|ff_ppm|normal_valve_ppm|target_i|
min_control_i|max_control_i|min_temp_mK|max_temp_mK|
hot_trip_mK|wall_trip_mK
```

config_id is a manifest identifier; retain full SHA256 of complete configuration
in provenance. Config changes require a new DISARMED session. Gains scale1e6;
divide by1e6 for SI gain. Tank error metres, thermal error m3/s. Commands ppm
0..1000000. Tick1..1000000us, stale/lease1..10000000us; gain0..1e12,
temperature fields0..1000000mK. Checked arithmetic/field relationships and frame
length matter; no ignored override or partial configuration may permit ARM.

Frozen defaults: tick100000us, stale300000us, lease300000us. Tank kp3000000,
ki60000, ff315500ppm, normal_valve650000ppm, target500000um, range0..1000000um.
Thermal kp2000000000 and ki200000000 (SI2000s/m3,200/m3), ff527498ppm
(derived nominal curve/target), normal_valve650000ppm, target150000uL/s,
flow range0..500000uL/s, temperature range273150..368150mK, hot trip338150mK,
wall trip358150mK. These gains are assumed demonstration choices, frozen before
tracking/refinement outcomes. Record quantization (command rounding <=.5ppm,
temperature <=.5mK, flow <=.5uL/s) rather than claim unquantized identity.
The150000uL/s target equals1.5e-4m3/s=9L/min; micro-litre conversion is1e9
per cubic metre. This unit conversion is frozen before firmware execution.
Tank unused thermal fields must be zero. Independent high-switch threshold lives
in the sensor adapter configuration and full manifest, not hidden plant access in
the C core. The core sees only the separate Boolean channel.

Feedforward is configured from declared nominal model/target, not a fault-modified
resistance. Runtime core receives no plant object or injector labels. Preserve M1
configurable tank gains/range/drain and sensor threshold via the explicit adapter;
reject unsupported overrides instead of silently substituting compiled defaults.

## Channels and clocks

| ID | Channel | Wire conversion |
| --- | --- | --- |
| 1 | tank level | m=value/1e6 (micrometres) |
| 2 | volume flow | m3/s=value/1e9 (microlitres/second) |
| 3 | hot liquid | K=value/1000 |
| 4 | cooled liquid | K=value/1000 |
| 5 | hot wall | K=value/1000 |
| 6 | separate trip input | exactly0/1 |

Validity bit0 valid,bit1 missing,others0: legal values1 valid,0 invalid,2 missing.
Missing uses value0; invalid/missing quality must not become a fresh valid sample.
Masks use bit(channel-1). Tank requires1/6; thermal requires2â€“6. One frame per
channel preserves independent age. Fresh flow does not refresh temperatures;
plausible fresh frozen data are not diagnosed by freshness.

Host stages <=32 fixed observations before STEP. Validate sample<=STEP time and
sequence/epoch before cache mutation; receipt time is delivery STEP. Source sample
time governs virtual freshness even on delayed arrivals. Reliable S advances time
when all O records are dropped. Source and receipt clocks are recorded explicitly.
Device timer provides independent progression; external S rejected on MCU. MCU
freshness uses local monotonic receipt/acquisition time, source timestamps only
ordering/diagnostics unless synchronization is established. Never subtract V from
D; hardware latency claims need actual capture. Peripheral mode rejects external
replacement of HAL channels and records each channel's source.

## Ordering, state and leases

Track sequence separately per observed channel and per command/ACK/driver stream.
Experimental acceptance delta=uint32(new-last),0<delta<0x80000000.
Reject duplicate/reorder/half-range; ffffffff->0 wraps. Reliable S must be exactly
next sequence and advance by configured tick; first STEP is sequence0 at wire time0.
On a host restart during a campaign, the adapter declares a session origin in
absolute simulation microseconds. Wire V time is absolute time minus that origin.
Evidence retains both absolute time and session origin/epoch. Samples acquired
before the new origin are rejected or reacquired; an old sample cannot be given
a fresh timestamp to fit the new session. This translation is an explicit clock
relationship, not a hardware clock synchronization claim.
Driver uses nonzero session epoch, increments on process restart, skips zero on
wrap, and logs capture ID. A new H must be half-range-newer by the same uint32
ordering rule. An old H cannot reset the current session.
MCU announces epoch0 and waits for handshake. Repeated identical H idempotent;
deliberate new epoch clears integrator/history/command lease, returns DISARMED.
Repeated identical configuration in the same session is idempotent; changed
configuration is rejected until a new session. A repeated H cannot change profile.
Old epoch cannot refresh anything. Session epoch is not a measured unique hardware
boot identity. H1 must document actual reset-cause/boot/session observation policy.

Operations0 hold,1 ARM,2 RESET. Valid config, all required valid/fresh/in-range
inputs, separate trip clear and temperatures below trips are required for ARM or
RESET. ARM is legal only from DISARMED and RESET only from TRIPPED. An asserted
trip at startup keeps DISARMED with heat/pump off and rejects ARM. RESET clears
trip into DISARMED; a subsequent ARM is mandatory. A rejected operation never
clears a latch. No reconnect
rearm. Sensor bounds inclusive; trips >=; stale when age>stale_us. Latch reason
priority:separate_trip,wall_hot,liquid_hot,invalid_input,range_input,stale_input.
Retain first latched reason; invalid config prevents arming. Reset integrator on
disarm/trip/reset; PI saturation uses conditional anti-windup.

PI update order: compute raw=feedforward+kp*error+previous_integrator. Integrate
ki*error*tick only if raw is in[0,1], or the error drives an out-of-range raw value
toward that interval. Compute output using the updated integrator, bound the
requested command to[0,1], and quantize nearest-half-up to ppm. This command
saturation never clips a plant state. Configured control minima/maxima must be
strictly ordered and contain target. Thermal control minimum is nonnegative;
temperature minimum<trip limits<=temperature maximum. Tank temperature fields
are zero. Invalid/missing observations immediately change quality while retaining
the last-good sample timestamp for age diagnostics; they cannot refresh validity.

Thermal DISARMED requests heat0,pump0,valve1; RUNNING explicit heat demand,
flow PI/ff,normal valve; TRIPPED heat0,pump1,valve1. Tank DISARMED/TRIPPED requests
heat0,pump0,configured gravity drain. Heat always0 for tank. Applied faults occur
after requests/fallbacks. Command ACK acknowledges intent only.

Host sends Q then R after every STEP and flushes. Experimental Q injection occurs
after raw subprocess receipt; R is reliable liveness. Loss of Q tests lease hold/
expiry, loss of A leaves accepted commands/expiry unchanged, missing R/EOF/process
death is run failure with retained last state and reaped child, no Python fallback.
V command expiry=Q.time_us+lease_us with checked addition; equality expires.
Reject expired-on-arrival command. At expiry thermal requests0/1/1; tank0 pump
and configured drain. Faults still apply. Received ACK never extends a lease.

## Bounded transport checks

Operational defaults:startup5wall seconds,STEP reply1wall second,frame assembly
500wall milliseconds. Read via bounded reader thread/queue so partial read cannot
block timeout enforcement. MCU assembly uses local monotonic500ms. At oversize/
timeout enter discard-until-LF; reject unfinished EOF. Bad frames do not refresh
observations/leases. Binary host stdin/stdout on Windows; diagnostics only stderr.

Independent golden frames calculated with binascii, frozen before C implementation:

```
F|1|H|1|0|V|0|1*7A87\n
F|1|O|1|0|V|0|1|1|250000*6EF2\n
F|1|O|1|0|V|0|6|1|0*0FE2\n
F|1|S|1|0|V|0|1|0*AFD1\n
F|1|A|1|0|V|0|0|0*0493\n
```

Oracles:all split points/byte-at-time; CRLF/non-ASCII/overflow/extra-field rejection;
256/257 length; timeout/EOF+LF recovery; CRC reject without refresh; channel ages;
age300000 fresh/300001 stale; old arrival notfresh; sequencewrap/duplicate/halfrange;
old epoch/restart DISARMED; RESET then ARM; trips/lease equality; lost Q vs lost A
vs missing R; actuator faults after expiry. Golden frames alone are codec fixtures,
not an executed board transcript. M4/M5 close additional protocol/campaign gates.
