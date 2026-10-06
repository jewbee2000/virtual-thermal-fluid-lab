# Virtual Thermal Fluid Lab requirements and acceptance contract

Contract version 1. Frozen 2026-10-06 before corrected or thermal campaign results.
Authority: Walter's current request and `Codex_Implementation_Plan.md`. The starter
T01–T08 roadmap and Bash/WSL onboarding are historical references. The coordinator
owns this contract. Changes require a reason, an evidence impact statement, and
renewed relevant checks; a failing result alone is never a reason to relax a gate.

Intended use: an educational engineering portfolio test bench answering what a
controller observes, requests, and actually achieves when circulation or heat
rejection fails. Parameters are assumed unless explicitly assigned another
pedigree. This is not Endurance's plant model or a safety certification.

## Requirements, rationale, and gates

| ID | Required behavior and rationale | Acceptance and evidence | Milestone |
| --- | --- | --- | --- |
| ENV-01 | Native Windows development with locked scientific dependencies, to reproduce the user's workstation experience | Python 3.12; unchanged NumPy 2.3.5, SciPy 1.17.0, Matplotlib 3.10.8 and lock; actual `uv sync --locked`, unit suite and seven tank scenarios; record executable/platform versions | M0 |
| GOV-01 | One code writer per checkout; bounded review; durable progress | Archive original tasks, replace stale prompts; coordinator-owned tasks with dependencies, criteria, actual commands, artifacts, commits, limitations; read-only physics and test reviews | M0–M7 |
| BASE-01 | Preserve the atmospheric tank as a mechanistic benchmark | Existing 20 tests and seven scenarios reproduced before changes; analytic fill/drain/lag/full/empty tests preserved; equations and assumed parameters unchanged | M0–M1 |
| INPUT-01 | Identical strict validation at file and Python execution boundaries prevents accidental experimental drift | Versioned scenario/model/controller configs; reject unknown fields, duplicate JSON keys, booleans as numbers, nonfinite/out-of-range values, invalid seeds/outcomes/timing; useful errors; negative fixtures | M1 |
| TIME-01 | Deterministic virtual clock, held commands, and explicit exogenous event order | Integer microseconds for ticks; no random draws in ODEs; split at exogenous events; sample/receipt/age/clock recorded; terminal snapshot distinguished from controller tick; seeded repeat identical data on same machine | M1, M5 |
| PROV-01 | Reports identify the executed model and solver, including failures | Immutable run solver config; actual method/rtol/per-state atol/max step, seed, units, Python/libs/lock hash, scenario/source hashes, explicit project-root Git revision/dirty status, controller hash, artifact hashes; stable POSIX path encoding and LF policy; wrong-cwd/custom-atol tests | M1–M5 |
| DOMAIN-01 | Stop at model validity boundaries and preserve diagnostic evidence | Tank empty/full and thermal lower/upper/actuator events; stopped object cannot resume; solver/process failure preserves last accepted state and partial trace; no clipping into a passing outcome | M1–M5 |
| EVAL-01 | Expectations, containment, completion and assessability are separate judgments | Per-rule PASS/FAIL/NOT_APPLICABLE/UNASSESSABLE; no-trip latch rule NOT_APPLICABLE; characterization requires complete horizon; incomplete/corrupt evidence cannot pass; expected boundary hazard can pass expectation while containment is FAILED | M1, M5 |
| TANK-01 | Preserve baseline control thresholds as educational design targets | R01 last30s error <.02m; R02 residual <1e-9m3; R03/R04 no nominal trip/boundary; R05 dropout trip <=.5s after fault; R06 high-switch bias trip; R07 peak <.95m without boundary; R08 stuck pump high trip then full boundary; R09 characterization complete; R10 zero pump requested after a trip; R11 blockage peak <.65m without boundary | M1 |
| MODEL-01 | Closed single-phase liquid loop with hot wall, two mixed inventories, heat sink and quasi-steady pump intersection | Derive equations and units from balances; freeze plan coefficients with assumed pedigree; independent pressure substitution residual <1e-8; zero-speed/closed/restricted branches tested; finite positive normal properties, zero physical coefficients allowed in analytic limits | M2 |
| PHYS-01 | Independent solutions test implementation rather than repeating it | Constant heating and exponential cooling max error <1e-5K under tightened tolerances; energy conservation for P=0/UAc=0 and no-flow internal exchange; imposed-flow steady state within .01K after demonstrated settling; independent linear-system comparison; thermal events and persistence | M2 |
| NUM-01 | Separate integration accuracy from digital scheduling sensitivity | Fixed-tick rtol ladder 1e-5/1e-7/1e-9 vs tighter DOP853, per-state normalized tolerances; separate noise-free .20/.10/.05s tick ladder; .10 vs .05s selected thermal peak delta <.1K and trip delta <=.1s; tank peak delta <.002m and trip delta <=.1s; retain all failures and explain discontinuities | M2, M5 |
| PEAK-01 | Containment uses continuous-time information | Dense derivative extrema or conservative rate/sample bound, prominently distinguish sampled peak from conservative bound; never justify a continuous hazard margin solely with tick maximum | M1–M5 |
| CORE-01 | Actual portable C11 logic used in both host SIL and MCU | One core with fixed-size state, no heap/wall clock/files/Python/plant truth in tick path; tank and thermal profiles; shared PI/supervisor machinery; anti-windup, equality, reason priority, arming/reset/latching; Python baseline labeled separately with no silent fallback | M3–M4 |
| CTRL-01 | Topology-specific shutdown based only on observed I/O | Configured tank limits/drain/gains; thermal DISARMED heat0/pump0/valve1, RUNNING flow PI+feedforward and explicit heat demand, TRIPPED heat0/pump1/valve1; required freshness/range/validity and independent trip input; valid explicit reset required; fault labels never enter core | M1, M3 |
| WIRE-01 | Bounded inspectable transport advances time even on dropped sensor data | LF ASCII frames <=256 bytes; explicit version/type/epoch/sequence/clock/time/validity and checksum coverage; integer units; published checksum vector and Python/C golden frames; partial/oversize/corrupt/truncated/timeout/EOF recovery; Windows binary streams; STEP every tick independent of experimental link | M3–M4 |
| LINK-01 | Failures must not falsely refresh evidence or imply physical actuation | Drop/duplicate/delay/reorder/corrupt/truncate/restart tests, wrap and epoch policy; old arrival not fresh; bounded reader timeout and reaped failed child; command sequence/lease/ack; fallback after expiry still subject to actuator faults; lost ack distinct from lost command and process death | M3–M5 |
| MCU-01 | Real target code exercises low-level interfaces | RP2040 default; periodic timer marks bounded main-loop work; overrun counts; ADC/GPIO/serial/watchdog/monotonic HAL; separate synthetic-link and peripheral modes; cross-build compiler/SDK revision/log/ELF/map/flash/RAM evidence. Board execution status remains NOT_EXECUTED until captured | M4 |
| CAMP-01 | Fault scenarios expose observability and failed containment | Required plan cases: nominal heat, restriction, lost rejection, flow dropout, biased/frozen temperature+separate trip, bad link, restart, near-tick event, tank stuck pump; stuck heat5000W+UAc0 at60s over1200s must trip then reach upper boundary while cooling requested; independent long-case prediction before frozen execution | M5 |
| PERF-01 | Practical demo budget supported by actual laptop measurements | Record wall time, simulated/wall ratio, peak memory and protocol latency; proposed 240s demo <60 wall s/<512MiB. Freeze selected campaign/budget after corrected baseline; profile failures before optimization; no real-time claim | M5 |
| WEB-01 | Static inspectable visualization is usable without simulation tools | Shared playback/pause/scrub cursor; topology diagram; temperature/flow units/limits/truth-observed toggles; requested/applied/actual tracks; event timeline, metrics/status/failed-rule explanations; break data gaps and show quality/age; absolute-time comparison; keyboard/contrast/mobile; raw downloads and provenance; screenshot fallback | M6 |
| HW-01 | Hardware packet prepares a meaningful experiment without fabricating evidence | Pin/voltage/interface documentation, fixture and instrumentation design, acquisition/capture checklist; H1 optional executed ADC/GPIO/timer/watchdog/serial evidence and photos; H2 separate whole-run calibration and holdout validation | M6, H1–H2 |
| BUILD-01 | Portability is demonstrated by executed builds | Windows/MSVC and Linux/GCC host/CTest and campaign CI, Linux parser/core sanitizers, Pico cross-build; pinned tools/actions and actual run links; fresh Windows checkout reproduces install/build/campaign/replay | M3–M7 |
| RELEASE-01 | Public claims are gated by reproducible source and artifacts | Private working repo `jewbee2000/virtual-thermal-fluid-lab` if available; source/asset rights+license established; tracked-file audit, fresh reproduction, passing required gates; then public v0.1.0 with immutable curated evidence and replay bundle | M7 |
| SITE-01 | Case study is published through the existing verified website workflow | Match recent live article to fresh site source and deployment branch/workflow; 900–1400 word article and 2–4 release-derived figures; preview desktop/mobile/math/downloads, reviewable PR when supported, pipeline success and actual live URL verified | M7 |
| CLAIM-01 | Evidence categories stay honest | Physical validation NOT_STARTED without measured holdout; cross-build != executed board; no hardware/measured/Endurance digital-twin/safety-certification/hard-real-time claims; claims ledger and checkpoint after each milestone | All |

## Frozen starting parameters and scope

Tank parameters remain `docs/MODEL.md` defaults. Thermal coefficients, initial
conditions, flow target, temperature trips, controller tick and stale interval
remain the table in the revised plan. Reviewer hand calculations are retained
before thermal implementation. Thermal gains, wire ordering/epoch rules,
per-state numerical error scales, lower temperature bound, and exact selected
refinement cases must be documented before their corresponding tests/campaigns.
No CFD, phase change, power cycle, live internet control, generic plugin framework,
or probabilistic reliability claim is required.

Characterization requires a complete horizon: this implements the starter's own
R09 prose and corrects its unconditional boolean. R10 is inapplicable without a
trip; it does not gain an empty-list pass. These are semantic repairs, not weaker
thresholds. A required expectation that is unassessable fails the overall gate.

## Instruction reconciliation

| Starter instruction | Resolution and reason |
| --- | --- |
| Kickoff begins ONLY T01 and pauses before T02 | Replace with M0/M1 first, then proceed autonomously through required milestones; current user explicitly authorized this |
| Thermal optional T07, firmware absent, visualization plot-only | Superseded by MODEL-01/CORE-01/MCU-01/WEB-01 and M2–M6 |
| Generic adapter and uncertainty campaign first | Defer until two concrete models and their test questions establish need |
| Linux/WSL/CLI setup first | Native Windows and existing desktop app; Linux CI supplies portability evidence |
| No account setup/publication needed for baseline | Baseline remains local; user's explicit request authorizes new private GitHub development and eventual gated publication |
| Optional calibration | Preserve H2 as separate measurement gate; no simulated result can close it |
| Custom CLI agent configuration required | Optional historical files only; desktop delegation uses available runtime roles |

Review assistance is not physical validation. `tasks.json` is the execution record;
this document and revised plan define acceptance. Missing equipment or credentials
may block dependent gates while independent implementation continues.

M5 NUM-01 clarification frozen before integrated outcomes: terminal tick runs
compare peaks on identical matching preterminal keys/common gap, excluding roots.
Require matching boundary presence/kind and fractional boundary-time delta<=.10s
as an additional educational timing target. Keep full95C/1m peaks as hazard data;
their equality cannot by itself establish convergence. Existing .1K/.002m peak
and .10s trip limits are unchanged. See CAMPAIGN.md for review rationale.
