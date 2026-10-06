# M5 frozen integrated campaign

Frozen before integrated C-controller outcomes on 2026-10-06. Authority:
REQUIREMENTS.md, THERMAL_MODEL.md and schemas/protocol.md. A read-only physics
review supplied the independent calculations below. All coefficients, gains,
sensor independence and fault magnitudes are assumed educational choices.
Physical validation remains NOT_STARTED.

## Common configuration and independent acceptance

Use the same compiled C core for tank and thermal SIL, with no Python fallback.
Default tick is 100000 us; stale and command lease intervals are 300000 us.
All runs are noise-free for this campaign and refinements. Demand changes and
faults use absolute integer microseconds, split plant integration exactly at each
event, and take effect for observations sampled at or after that time. An event
between ticks changes held applied inputs immediately but cannot invent an
extra controller tick. Random sampling remains outside ODE functions.

Cold start C: Tw=Th=Tc=293.15 K, speed0, opening0.65; heat demand0 until20 s,
then5000 W. Warm start W: Tw317.7911483254 K, Th301.1244816587 K, Tc293.15 K,
speed0.5274982823, opening0.65; heat demand5000 W from the explicit ARM at0.
ARM at0 follows valid acquisition. Channel6 is an ideal emulated independent
wall-temperature switch: true Tw>=358.15 K. Its software interface separation
does not establish hardware common-cause independence. Primary observed trips
remain Th>=338.15 K and Tw>=358.15 K.

Thermal rules, distinct from the preserved tank R01-R11:

| Rule | Frozen acceptance |
| --- | --- |
| TH01 | Nominal/restriction final30 s observed and true flow errors <=3e-6 m3/s (2% of target); full window required |
| TH02 | Valid traces, including an intentionally terminal boundary trace, have augmented energy residual <1e-3 J; this is a consistency check |
| TH03 | Required recoverable runs finish the declared horizon without a domain boundary or process/solver failure |
| TH04 | Post-trip C requests heat0/pump1/valve1; trip stays latched without an explicit valid RESET then ARM |
| TH05 | Dropout/delay trips at the first tick strictly later than last valid source time+stale interval, within stale+one tick of injection |
| TH06 | Fresh plausible freeze/bias is not mislabeled as stale; the genuine separate switch produces a separate_trip latch in the specified concealed-temperature case |
| TH07 | Recoverable cases have a conservative continuous maximum of every true temperature <359.15 K (86 C); raw numerical error qualification stays visible |
| TH08 | Valid delayed observations retain original source time and cannot become fresh because they arrived now; reordered/duplicate/corrupt records cannot mutate caches; expired delayed commands cannot renew leases; recovery follows the frozen frame/sequence rules |
| TH09 | Scheduled restart preserves absolute time, starts a new DISARMED epoch, invalidates the old lease and rearms only at62 s |
| TH10 | Long stuck-heat/lost-sink case trips then reaches an upper boundary by585.3 s absolute despite cooling requests; containment is FAILED even if expectation passes |
| TH11 | Reduced rejection raises each true temperature by >=5 K from prefault value, with final30 s flow within2% and no trip/boundary |
| TH12 | Restriction reduces true flow immediately, then increases requested and actual speed while retaining nominal feedforward |

Required rule applicability is case-specific. A missing/corrupt trace or shortened
characterization is UNASSESSABLE and cannot pass. No-trip latch/shutdown rules are
NOT_APPLICABLE. Expectation, horizon completion, containment and assessability
remain separate. Explanations identify what observed data support, without
giving the controller injector labels or true plant state.

The86 C criterion is frozen before outcomes. For these ordered starts and
nonnegative heat/flow, Tw>=Th>=Tc and sink<=Tc. At the maximum wall temperature,
dTw/dt<=5000/10000=.5 K/s. An ideal85 C wall switch, maximum refinement tick.2 s
and.3 s command lease add at most.25 K before heat actually becomes zero.
The global maximum cannot subsequently rise under the reduced model's maximum
principle. The86 C criterion leaves.75 K beyond that timing allowance. General
per-state domain rate bounds are retained with every held interval as diagnostics.
For the global maximum M=max(Tw,Th,Tc), its upper Dini derivative is at most
P/Cw<=.5 K/s whenever all states remain at or above the constant sink: a maximal
wall has nonpositive exchange; a maximal hot liquid has nonpositive exchange and
circulation; a maximal cooled liquid has nonpositive circulation and rejection.
This proof does not depend on temperature ordering. Use sampled global maximum
plus.5 K/s times the largest actual sample gap, including exact event/terminal
samples, for TH07 and global peak comparisons. This bound excludes numerical
error. It is sharper than the generic per-state diagnostic bounds, which could
otherwise introduce a tick-dependent bound difference unrelated to trajectory
accuracy. The proof and method were accepted before integrated outcomes, without
changing the.1 K refinement criterion. The criterion
does not apply to the stuck-applied-heat hazard and is not a physical safety rating.

## Specific runs

| Case | Start / horizon | Injection and required evidence |
| --- | --- | --- |
| nominal_heat_step | C /240 s | Heat step20 s; TH01-03, TH07; no trip |
| restriction | W /240 s | At60 s Kpipe6e11->2.4e12 Pa s2/m6; TH01-03, TH07, TH12; no trip |
| reduced_rejection | W /600 s | At60 s UAc500->125 W/K; TH02-03, TH07, TH11; no trip |
| flow_dropout | W /120 s | Drop only flow observations over[60,65) s; reliable STEP and other channels continue; TH02-05, TH07 |
| frozen_temperature | W /600 s | At60 s UAc0; hot301124 mK and wall317791 mK observations remain fresh and frozen; other channels genuine; TH02-04, TH06-07 |
| biased_temperature | W /600 s | At60 s UAc0 and hot/wall bias-20 K; other channels genuine; TH02-04, TH06-07 |
| delayed_flow | W /120 s | Delay flow records400000 us over[60,61) s, preserve source time; TH02-05, TH07-08 |
| reordered_flow | W /90 s | At60.1 s deliver newer60.1 s sample then held60.0 s sample; old record rejected, no trip; TH02-03, TH07-08 |
| corrupt_flow | W /90 s | At60 s flip one flow payload byte without updating CRC; next tick is valid; rejection/recovery, no trip; TH02-03, TH07-08 |
| truncated_flow | W /90 s | At60 s cut one flow body but retain LF; rejection/recovery next tick, no trip; TH02-03, TH07-08 |
| dropped_command | W /120 s | Drop Q over[60,61) s; hold last accepted command until lease equality, then actual adapter fallback0/1/1; core state/request remains separately visible; TH02-03, TH07-08 |
| delayed_command | W /120 s | Delay Q400000 us over[60,61) s; expired arrivals rejected, cannot renew lease; TH02-03, TH07-08 |
| dropped_ack | W /120 s | Drop ACK over[60,61) s; accepted command and lease unchanged; TH02-03, TH07-08 |
| planned_restart | W /120 s | Restartat60 s; session_origin_us60000000, first new wire STEP0/time0 is DISARMED0/0/1, explicit ARM at62 s; TH02-03, TH07, TH09 |
| stuck_heat_lost_sink | C /1200 s | At60 s force applied5000 W and UAc0 regardless of requests; TH02, TH04, TH10; prominently FAILED containment |
| near_tick_before | W /120 s | Flow dropout starts60099000 us for5 s,1 ms before60.1 s; TH02-05, TH07; exact event splitting |
| near_tick_after | W /120 s | Flow dropout starts60101000 us for5 s,1 ms after60.1 s; same rules; explain one-tick phase change |
| tank C regression | Original seven cases | Original R01-R11 applied to C-profile execution; preserve Python benchmark separately, including stuck-pump trip then full with failed containment |

Transport fixtures separately test dropped/duplicate/half-range/wrapped sequences,
partial-byte assembly, oversize input and stale/hot equality. A no-LF stream that
swallows reliable STEP, an alive blocked child, unexpected EOF and process death
must end as bounded run failures with partial trace and reaped child. They cannot
be reported as contained sensor dropout. Deliberate restart is an explicit
experiment operation; unexpected death is a failure.

Command ACK acknowledges accepted intent, never motion or heat removal. Applied
fallbacks remain subject to actuator faults. Trace source/receipt time, epochs,
wire bytes/disposition, requests, accepted/leased values, fault-modified inputs,
speed/opening and physical outputs separately. Reacquire samples after restart;
pre-origin samples and old epochs cannot become fresh. Preserve both absolute
simulation time and session-local wire time, linked by session_origin_us.

Independent hand predictions: restriction initially scales Q by about.638 and
needs steady speed about.827, within the normalized command range. Reduced-sink
equilibrium at target Q is Tc50 C, Th57.974482 C, Tw74.641148 C;600 s is not a new
equilibrium gate. The existing long-hazard energy bound is independent of flow:
total capacity30900 J/K and stuck5000 W imply mean rise.1618123 K/s and at least
one95 C state by585.3 s absolute if states at fault remain at or above10 C.

## Refinement and performance

At fixed tick.1 s, use RK45 rtol1e-5/1e-7/1e-9 against DOP8531e-11 for nominal,
frozen-temperature rescue, and long hazard. Retain the M2 seven per-state scales;
tightest normalized maximum<=1 on matching absolute samples before termination.
Compare event times separately and record differences rather than pretending
terminal snapshots are common controller ticks.

Tick ladder.20/.10/.05 s covers nominal, restriction, frozen-temperature rescue,
both near-tick dropouts and long hazard. Fixed absolute events and no noise.
Between.10 and.05 s: conservative continuous peak delta<.1 K and trip delta<=.1 s.
For the tank, retain peak delta<.002 m and trip delta<=.1 s, using nominal and
stuck-pump cases. Record tracking, per-state trajectory differences and boundary
time differences; identical95 C terminal peaks alone are not convergence evidence.
No monotonic convergence requirement is invented near discontinuities.

The selected performance gate is the complete nominal240 s C-controller demo:
under60 wall seconds and under512 MiB conservative process-family peak memory.
Record laptop/OS/compiler identity, simulation/wall ratio and protocol latency
distribution. Also record the entire fault suite's elapsed time and memory; it
has longer, differing horizons and is not silently compared to the240 s budget.
Run the isolated performance measurement after profiling/corrections, without
concurrent test loads. No hard-real-time or worst-case execution-time claim.
