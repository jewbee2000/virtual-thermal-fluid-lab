# M4 target contract, frozen before implementation

Frozen 2026-10-06. The M3 host supports the base records in schemas/protocol.md.
These unreleased protocol-v1 extensions are reserved for M4 and become executable
only after its shared codec/core tests and target cross-build pass. No board has
executed this firmware. The coordinator owns the contract.

## Why the target needs a clock and intent extension

Reliable host S fixes the virtual clock to exact configured tick increments.
A real device has monotonic timestamps, acquisition delays and jitter. Add a
device entry to the same C supervisor/PI implementation: first internal sequence0
accepts any device time, subsequent sequence is exactly-next and time strictly
increases. PI uses actual elapsed integer-microsecond difference, with configured
tick for the first update. The host wrapper keeps its exact V schedule unchanged.
No separate controller implementation, physical claim or model equation changes.

External S is rejected on MCU. A separate U carries operation/heat intent without
advancing device time. Device freshness uses local receipt for synthetic inputs
or local acquisition time for HAL inputs; external source clock/time are retained
for ordering and diagnostics. Never subtract unsynchronized source time from
device time. Changing a source clock within a stream requires a new session.

## Additional bounded records

Same ASCII/LF/256-byte bound and CRC as the base codec. Commas below denote pipe
fields. All counters saturate at uint32 maximum rather than silently wrapping.

| Type | Payload | Meaning and bounds |
| --- | --- | --- |
| U | operation,heat_demand_ppm | op0..2, demand0..1000000; synthetic-link intent only, independent ordered sequence, source time does not advance local clock |
| X | channel,source_kind,source_clock,source_time_us,receipt_time_us,quality | channel1..6; kind1 synthetic,2 ADC,3 GPIO; source clock0 V,1 D; both times uint64; quality0 invalid,1 valid,2 missing; header D/local time |
| N | mode,tick_count,overrun_count,rx_rejected_count,tx_dropped_count,watchdog_reboot,intent_fresh | mode1 link or2 peripheral, counts uint32, final flags0/1; header D/local time |

ADC/GPIO X records use local D acquisition and receipt. Synthetic X source time
belongs to its declared external source clock; even an external D label is not
assumed synchronized to local D. Source-kind plus clock distinguishes this case.
Q/R are emitted at local timer ticks with D timestamps; R sequence is the internal
tick sequence. The host executable rejects U and MCU-only diagnostics as inputs.
Initial firmware version stays100 for the unreleased0.1.0 candidate.

Reason7 is intent_expired, lower priority than stale_input. Synthetic U intent
lease uses local receipt+configured lease_us and expires at equality. Expiry
clears demand/pending operations, trips RUNNING to topology-safe outputs, and
prevents ARM/RESET until new valid intent. Missing intent at startup leaves
DISARMED. Peripheral GPIO operation bypasses synthetic U lease by declared policy;
tank heat is always0. ACK never extends any lease.

New H clears intent/history and returns DISARMED under existing half-range epoch
rules. Configuration remains immutable/idempotent. USB disconnect/reconnect clears
binding and pending data, announces B epoch0, and requires new H/config plus
intentional arming. Epoch is a protocol session identifier, not a measured unique
hardware boot identity. Watchdog reset cause is reported separately in N.

## Narrow HAL and supported scheduling

Pico/RP2040 only. Device supports configured tick1000..1000000 us, rejects smaller
ticks explicitly before configuration; host retains1..1000000 us support. Default
100000 us is unchanged. This is a supported interface range, not a measured timing
guarantee. Accepted config controls the repeating timer; no override is ignored.

Timer ISR marks due work and saturating missed-deadline information only. Main
loop consumes bounded work at actual monotonic64-bit time and counts overruns.
RX consumes at most256 bytes per pass, fixed32 observation staging,500 ms assembly
timeout/discard-until-LF. TX uses a fixed8-frame ring, checked nonblocking USB
capacity and whole-frame drops; prioritize B/Q/R/N ahead of optional required-
channel X diagnostics. Count dropped output. No unbounded ISR parsing or USB wait.

ADC readiness uses a100 us deadline plus a finite iteration guard; timeout is
invalid quality. ADC_CS_ERR also yields invalid quality. Read-only HAL review
found that TinyUSB's queue can be replenished while tud_task drains it. A narrow
build-local wrapper of the pinned vendor source therefore permits at most8 queue
receives per pass at timeout0. The SDK checkout is unchanged; source pin/hash and
wrapper transformation are checked and the wrapper hash retained. Sustained-queue
and ADC-error native stub checks verify these software paths, without claiming
measured device timing. Project warnings remain errors; SDK source uses its
supported compiler defaults.

Watchdog1500 ms is fed only after scheduled acquisition/control
work completes. Device64-bit SDK monotonic clock avoids a32-bit software wrap;
reboot resets its time origin. Record boot/reset evidence during H1 before any
claim about measured watchdog timing or executed peripherals.

| Pin | Declared use | Interface |
| --- | --- | --- |
| GP26 /ADC0 | Peripheral tank level emulation | Assumed0..3.3 V maps to0..1 m; knob is not a calibrated level sensor |
| GP14 | Separate trip | Active high, pull-up; GND jumper clears; disconnect asserts |
| GP15 | Explicit ARM | Active low, pull-up; new sampled press edge |
| GP16 | Explicit RESET | Active low, pull-up; new sampled press edge |
| GP25 | Onboard status LED | Indicator only; no pump, heater or valve output |

Initialize edge history from actual startup levels so a held ARM button does not
arm at boot. Operation priority: GPIO RESET, serial RESET, GPIO ARM, serial ARM.
Held buttons do not retrigger. Core still enforces state/quality/trip guards.
Peripheral mode is tank-only with HAL channels1/6; external O replacement and U
are rejected. Synthetic-link mode accepts declared external O inputs and U intent.
Every channel's source is visible. No real actuator is connected by this design.

## Independent extension literals

Calculated with Python3.12 binascii.crc_hqx(body,0) before C implementation;
these are codec fixtures, not a board transcript:

```
F|1|U|1|0|V|0|1|1000000*1C11\n
F|1|X|1|0|D|100000|1|2|1|95000|100000|1*C614\n
F|1|N|1|0|D|100000|2|1|0|0|0|0|1*DE88\n
```

Required checks add literal C/Python parity, real elapsed device PI, backward/
duplicate device time rejection, intent expiry equality/rearming and clock-source
ordering. Build both modes with the same core files and retain compiler/SDK/
TinyUSB revisions, complete log, ELF/map/bin/UF2 hashes and flash/RAM size report.
Cross-compilation cannot establish board execution, peripheral timing, fabrication
or physical model validation; those retain their separate actual statuses.
