# Codex Plan for Virtual Thermal Fluid Lab

Prepared for Walter Teitelbaum on October 5, 2026, Pacific time.

Build a reproducible fluid and thermal test bench that runs a portable C controller against a Python plant, produces inspectable fault evidence, and publishes an interactive replay with an engineering case study. The purpose is to demonstrate sound software, numerical modeling, embedded engineering, and practical test judgment for Endurance Energy interviews. Retain the supplied tank model as a benchmark; make a thermal circulation model, firmware, and visualization required deliverables.

This is an implementation handoff, not a claim that the new project has been built. The original PDF and ZIP are reference material. Their prompts, environment choices, earlier personal context, and optional milestones do not override Walter's current request or this revised scope.

## Project outcome

Use the project name **Virtual Thermal Fluid Lab** and proposed repository `jewbee2000/virtual-thermal-fluid-lab`. Verify that name is available before creation. Keep the existing `abyssbench` repository separate: it checks recorded controller timing; this project supplies a mechanistic plant, executable embedded controller, and generated experiment evidence. A later trace exporter can connect them.

The flagship question is: **When circulation or heat rejection fails, what does the controller observe, what does it request, and what actually happens to the modeled temperatures?** The answer must distinguish command issuance, actuator behavior, detection, containment, and model validity.

The finished software release must include:

1. The original atmospheric tank benchmark with preserved analytic regression tests.
2. A derived, documented thermal circulation model with a pump operating point and independent numerical checks.
3. One C controller core used by both a desktop executable and one MCU target, with timer, GPIO, ADC, serial, and watchdog interfaces.
4. Deterministic scenarios covering normal operation, faults, and at least one deliberately uncontained case.
5. A static browser replay and comparison tool, with raw data and reproducible manifests.
6. Native Windows and Linux build evidence, an MCU cross-build, a tagged GitHub release, and an accurate website case study.

Executed board evidence is a separate gate and strongly recommended for the broader hands-on engineering roles. Cross-compilation demonstrates target code; a board demonstration demonstrates real peripheral integration. Physical model validation requires a separate experiment and cannot be inferred from either.

## Evaluation of the supplied plan

The original plan is a good educational controls project. Its strengths are transparent conservation equations, analytic tests, separation of true state from observations, seeded virtual time, and honest treatment of failed containment. Its completion criteria are too weak for Walter's stated portfolio goals.

| Finding | Consequence | Revised decision |
| --- | --- | --- |
| Thermal physics is optional in original T07 | The project can finish without demonstrating thermal simulation | Require the thermal loop before the flagship release |
| There is no C or embedded target | Python controller code does not demonstrate low-level firmware | Require the same C core on the desktop and MCU |
| Visualization consists of Matplotlib plots | Good evidence export, limited operational software demonstration | Require replay, comparison, event annotations, and data-quality states |
| Generic adapters and uncertainty campaigns precede the thermal use case | Scope expands before the important cross-layer example works | Build two concrete models before extracting further abstractions |
| Setup assumes Bash and favors WSL | Adds environment work to a Windows-capable package | Use native Windows first and Linux CI for portability |
| Publication is an optional final presentation step | A functioning lab may never become a usable portfolio project | Make GitHub release and website publication explicit gates |
| Simulated and measured evidence are carefully separated | Strong scientific judgment | Preserve this distinction in every report and public claim |

The archive contains 20 test methods and logs reporting that they passed. This review inspected the source and checked four supplied CSV/summary pairs; it did not rerun those tests in the pinned environment. The bundled interpreter here lacks SciPy. Reproduce the baseline in milestone M0 before treating inherited logs as current evidence.

### Initial implementation corrections

Address these before generating new headline results. File locations refer to the extracted starter.

| Location | Correction |
| --- | --- |
| `src/fluidlab/runner.py`, source hashing near lines 118–119 | Normalize relative paths with `as_posix()` and define byte ordering and encoding. Current hashes vary between Windows and POSIX. |
| `runner.py`, Git metadata near lines 113–115 | Determine the project root and use explicit Git working directory. Launching from another repository must not attribute its revision to this run. |
| `runner.py`, manifest near line 124 | Persist actual solver tolerances from one immutable run configuration. Current metadata hardcodes default absolute tolerances even when custom tolerances were used. |
| `runner.py`, scenario loading and `run()` | Validate at every public execution boundary, reject unknown fields, and enforce finite values, types, limits, seed, outcome, and timing contracts. |
| `control.py` and `runner.py` | Replace fixed tank limits, high switch, drain opening, and assumed controller settings with validated topology-specific configuration. |
| `runner.py`, evaluator | Replace unconditional characterization success and vacuous stop passes with explicit completion, applicability, and evidence statuses. |
| `runner.py`, terminal row | Label a plant boundary snapshot separately from a fresh controller sample. Retained sample time must remain visible. |
| `plant.py`, `advance()` | Latch domain termination, prevent accidental reentry, and preserve solver diagnostics and partial failure traces. |
| Peak metrics and solver comparison | Quantify continuous extrema or conservative margins; compare different state units using per-state tolerances. |
| CI and onboarding | Add Windows execution and remove mandatory CLI/custom-role/WSL setup from the desktop path. |

The original tank models an ideal metered inflow, not a centrifugal pump. Keep that description. At level 0.5 m and opening 0.65, its assumed parameters imply about 7.572 L/min drain flow and a pump command of 0.3155. Use this hand calculation in onboarding.

## Relevance to Endurance Energy

Endurance describes subsea geothermal generation and a planned Adélie demonstrator. This supports a fluid, heat transport, and instrumentation project; it does not supply the dimensions or performance parameters for this lab. Do not describe the lab as Endurance's digital twin. [Company website](https://www.enduranceenergy.com/)

Walter's exact interview posting is **Senior/Principal Software Engineer**. Its live employer page describes test and automation software spanning plant simulation, bare-metal and Linux firmware, controls, data acquisition, and operator interfaces. This is the primary role to optimize for; a Linux firmware responsibility does not require the development workstation to run Linux. [Interview posting](https://jobs.ashbyhq.com/endurance-energy/60606623-84a3-4dc1-bb57-1eacdac0a20d)

The separate test infrastructure posting explicitly describes pump/valve test systems, Python, embedded simulation, fault injection, and data acquisition and visualization. The project's combined plant, firmware, and evidence path directly exercises those responsibilities. These are employer-stated responsibilities, not a verified inventory of internal tools. [Test infrastructure role](https://jobs.ashbyhq.com/endurance-energy/b7ee011a-9ee3-4a96-b350-a1aac52af91f/)

For fluids and controls integration, emphasize instrumentation, commissioning, fault investigation, and turning a model discrepancy into a next experiment. For mechanical engineering, add a buildable fixture and explain component sizing and measurement choices. These roles value test ownership and personally building/debugging hardware. Software alone does not establish fabrication skill; use actual photographs and measured work when available. [Integration and test role](https://jobs.ashbyhq.com/endurance-energy/c83c0c43-483c-492c-b364-146f10b76036), [Mechanical role](https://jobs.ashbyhq.com/endurance-energy/34da76bd-0957-4ccb-9e50-f0d861cdea91)

Endurance's turbomachinery posting supports heat exchangers and experimental model correlation. It justifies a thermal test problem without making a full power cycle part of this project. [Turbomachinery role](https://jobs.ashbyhq.com/endurance-energy/b4c58799-0c63-4b1a-9294-28b4fe0c7d23)

## Environment and dependencies

Use the existing Codex desktop app with the agent running natively in Windows and PowerShell. This stack does not require Linux. The app officially supports native operation; WSL is useful when a concrete Linux-only dependency appears. The agent environment and integrated terminal selection are separate settings. [Windows app guidance](https://learn.chatgpt.com/docs/windows/windows-app)

| Layer | Choice | Purpose |
| --- | --- | --- |
| Scientific model | Python 3.12, NumPy, SciPy | Reuse the starter lock and inspect equations easily |
| Environment | uv and committed `uv.lock` | Reproducible dependencies without global Python setup |
| Embedded core | Portable C11 and CMake | Share actual control logic across host and target |
| Host exchange | Bounded framed byte stream over stdin/stdout | Avoid DLL, calling convention, and binding complexity |
| MCU target | Raspberry Pi Pico RP2040 by default | Supported native Windows toolchain and accessible peripherals |
| Dashboard | Static HTML, CSS, and JavaScript | Publish replay without a hosted backend |
| Charts | A maintained plotting library, pinned and bundled locally | Avoid implementing chart rendering from scratch |
| CI | Windows/MSVC, Linux/GCC, MCU cross-build | Test native development and portable behavior |

The starter requires Python `>=3.12,<3.13` and pins NumPy 2.3.5, SciPy 1.17.0, and Matplotlib 3.10.8. Keep those versions initially. Add dependencies only for a concrete need, update the lock deliberately, and document any resulting evidence invalidation. The current lock includes Windows wheels.

Install Microsoft C++ Build Tools with Desktop development with C++, Windows SDK, and CMake. Detect the installed compiler rather than forcing a Visual Studio version. Use separate host and MCU build directories. Raspberry Pi's official Pico extension supports Windows and can provision the MCU SDK/toolchain; Codex then uses those installed tools. If Walter already owns another supported MCU, adapt the HAL once and record the decision. [MSVC setup](https://learn.microsoft.com/en-us/cpp/overview/acquire-msvc?view=msvc-170), [Pico tools](https://github.com/raspberrypi/pico-vscode)

Defer Nix, Rust rewrites, CFD, OpenModelica/FMI, phase change, sCO2 cycles, RTOS, distributed cloud services, and a live internet-connected control system. Linux CI can run sanitizers without migrating the workstation. If a later dependency requires WSL2, keep its Linux checkout and environment on the Linux filesystem and build separately; never share a `.venv` or build cache across Windows and Linux.

## Architecture and ownership

```text
Scenario and virtual clock
          |
          v
Python plant -> sensor and link adapter -> C controller core
     ^                                    |
     |                                    v
applied physical inputs <- faults <- requested commands
     |
     +---- truth and experiment records ----> evaluator
                                               |
                                               v
                                 manifest, raw data, replay

The MCU target uses the same C core through a hardware HAL.
The evaluator may see truth; the controller never does.
```

Keep this as one repository with a few explicit modules. Do not build a plugin framework or service architecture first.

Suggested structure:

```text
src/fluidlab/        tank, thermal model, clock, adapters, evaluator, CLI
firmware/core/      controller, supervisor, codec, fixed-size state
firmware/host/      deterministic desktop transport and executable
firmware/pico/      timer, ADC, GPIO, UART or USB serial, watchdog HAL
schemas/            scenario, event, manifest, protocol definitions
scenarios/          tank regressions and thermal campaigns
tests/              independent physics and integration checks
web/                replay and comparison application
scripts/            builds, campaign runner, static export, evidence audit
docs/               model, decisions, tasks, claims, hardware, case study
evidence/           small curated release traces and verification reports
artifacts/          ignored generated runs and build outputs
```

At tick k, deliver due sensor/link records, sample observable inputs, run the C supervisor/controller, record requested commands, apply actuator faults, and integrate the plant with held inputs to the next tick or boundary. Use integer microseconds for scheduling. Noise is generated at sample times, never inside the ODE derivative. Split integration at exogenous events rather than moving a fault to whichever adaptive solver step occurs next.

Maintain three different clocks: simulation time, host wall time for performance, and MCU monotonic time for device execution. A UTC creation date belongs in provenance only. Do not subtract timestamps from unrelated clocks to calculate freshness. Host SIL receives explicit virtual timestamps; hardware uses local receipt time and a documented device epoch/sequence policy.

## Required thermal and hydraulic model

Model a **closed liquid circulation bench**, not a geothermal power cycle. Two well-mixed liquid volumes exchange fluid; a hot wall receives imposed heat; the cooled volume rejects heat to a constant-temperature sink. Inventory is fixed, density and heat capacity are constant, and the liquid stays within a declared single-phase domain.

### Hydraulic operating point

Let x be normalized actual pump speed and z normalized actual valve opening. For forward flow Q:

```text
Delta_p_pump = p0*x^2 - Kp*Q^2
Delta_p_system = [Kpipe + Kv/z^2]*Q^2, for z > 0
Qstar = x*z*sqrt[p0 / ((Kp + Kpipe)*z^2 + Kv)]
tau_x * dx/dt = u_pump_applied - x
tau_z * dz/dt = u_valve_applied - z
```

The rearranged Qstar formula is well behaved at z=0 and gives Q=0 without an artificial leak. For that closed branch, report pump shutoff differential pressure and do not evaluate the system's division by zero. The coefficients have units Pa s2/m6, p0 is Pa, and Q is m3/s. This is a project-defined quadratic pump approximation and quasi-steady resistance model, including an ideal sealing assumption at closure. Speed/valve lags are empirical approximations, not fluid inertance. It excludes cavitation, water hammer, and backflow.

Use the analytic intersection as one oracle. Compare pump and system pressure drops independently and require the solution to remain on the declared forward operating branch. Log flow, pump pressure, valve position, speed, and requested speed separately.

### Thermal conservation equations

Use liquid masses Mh and Mc, specific heat cp, wall heat capacity Cw, temperatures Th, Tc, Tw, sink temperature Ts, wall-to-liquid conductance UAh, and sink conductance UAc:

```text
Cw * dTw/dt    = P_applied - UAh*(Tw-Th)
Mh*cp * dTh/dt = UAh*(Tw-Th) + rho*Q*cp*(Tc-Th)
Mc*cp * dTc/dt = rho*Q*cp*(Th-Tc) - UAc*(Tc-Ts)
```

Every right-hand term has units W. The two advective terms cancel when added. Define stored energy relative to a fixed reference temperature Tref:

```text
E = Cw*(Tw-Tref) + Mh*cp*(Th-Tref) + Mc*cp*(Tc-Tref)
dE/dt = P_applied - UAc*(Tc-Ts)
```

Use kelvin internally, with explicit Celsius display conversion. Temperature differences are unchanged by that conversion. The hot wall exposes delayed heating after a heater stop request, making thermal inertia visible. Do not add pump dissipation until its magnitude changes a question; record its omission.

At positive steady flow and constant P:

```text
Tc = Ts + P/UAc
Th = Tc + P/(rho*Q*cp)
Tw = Th + P/UAh
```

These provide a hand-derived independent steady-state oracle. At Q=0 the flowing steady-state formula is invalid; use the actual no-flow equations.

### Proposed parameter starting point

These numbers are educational design choices, not measurements or Endurance data. Freeze them with units and pedigree before the campaign. They describe simulated equipment, not a physical heater shopping list.

| Parameter | Proposed value | Meaning |
| --- | --- | --- |
| rho and cp | 1000 kg/m3 and 4180 J/(kg K) | Constant-property approximation |
| Mh and Mc | 2 kg and 3 kg | Mixed liquid inventories |
| Cw | 10000 J/K | Hot wall thermal capacity |
| P maximum | 5000 W | Simulated imposed heat |
| UAh and UAc | 300 W/K and 500 W/K | Assumed conductances |
| Ts and initial temperatures | 283.15 K and 293.15 K | 10 C sink, 20 C initial state |
| p0 | 100000 Pa | Assumed pump shutoff pressure |
| Kp, Kpipe, Kv | 4e11, 6e11, 1e11 Pa s2/m6 | Assumed pump and loss coefficients |
| Normal z | 0.65 | Assumed normalized operating opening |
| Pump and valve lags | 1 s and 0.5 s | Empirical actuator assumptions |
| Flow target | 1.5e-4 m3/s | 9 L/min |
| Controller tick and stale limit | 0.1 s and 0.3 s | Initial digital timing choices |
| Hot and wall trip values | 338.15 K and 358.15 K | 65 C and 85 C illustrative trips |
| Model maximum temperature | 368.15 K | 95 C upper boundary for this educational model |

At the target flow and full 5000 W, steady Tc is 20 C, Th is about 27.97 C, and Tw is about 44.64 C. Required pump speed at z=0.65 is about 0.527498, with 18.8254 kPa differential pressure. Have a reviewer independently reproduce these values before implementation. They are useful checks, not validation of real heat transfer.

Terminating at a model boundary is a reported outcome. Never clip a temperature and continue a successful run. Add lower-domain and actuator validity checks as appropriate. All boundary and failure events retain the last actual observations and their age.

### Control and shutdown policy

The normal controller regulates flow using PI with saturation, conditional anti-windup, and a feedforward speed derived from the declared pump curve. Heat is an explicit scenario input, not secretly adjusted to make tracking look good. The controller sees observed flow, observed temperatures, configured limits, data quality, and a separate high-temperature input.

Use states DISARMED, RUNNING, and TRIPPED. Startup remains disarmed until configuration and required input channels are valid. Define intentional arming/reset transitions, integrator reset behavior, reason priority, and equality at limits. Trips latch until a valid explicit reset; reconnect never silently rearms.

| Condition | Heat request | Pump request | Valve request | Interpretation |
| --- | --- | --- | --- | --- |
| Disarmed | 0 | 0 | Open | Default startup state |
| Normal valid operation | Scenario demand within limit | Flow PI | Normal opening | Ordinary control |
| Overtemperature or required stale/invalid input | 0 | Full cooling | Open | Bench-specific removal of heat while preserving circulation |
| Actuator fault | Supervisor request unchanged | Supervisor request unchanged | Supervisor request unchanged | Fault changes applied input or physical state, which evaluator records |

This policy assumes the modeled heat source can be disconnected. An actual geothermal source would need different isolation/bypass topology. Add a stuck-on heat source combined with degraded heat rejection so the lab exposes a case where commands cannot contain the modeled hazard. Full cooling commands are not proof of actual circulation.

## Firmware and I/O contract

The C core owns controller state, supervisory transitions, integrator, configuration checks, and command arbitration. It receives a fixed-size observation structure and time delta, and returns a fixed-size command/status structure. Use explicit tank-level and thermal-flow control profiles sharing the PI and state machinery, with profile-specific required channels and stop policies. The tank profile includes observed level; the thermal profile includes flow and temperatures. It has no Python dependency, heap allocation in the tick path, wall-clock calls, file access, or plant truth. Retain the original Python PI only as a benchmark, never as a silent fallback for the flagship C path.

Use explicit-width integers at the transport boundary and checked conversion to floating point in the controller. Suggested wire units are millikelvin, microliters/second, and parts per million for normalized commands. This avoids a host-versus-MCU floating-point serialization dependency. Values and ranges belong in `schemas/protocol.md` and a generated or centrally maintained constants file.

Start with a line-delimited ASCII protocol bounded to 256 bytes per frame. Define a version, message type, boot epoch, sequence number, explicit clock identifier, timestamp, channel values, validity bitmap, and integrity check. Specify the checksum algorithm and byte coverage exactly; use published check vectors and cross-language golden frames. Use LF framing, Python byte I/O, and binary-mode C streams on Windows to prevent newline translation. Accumulate ordinary partial reads into bounded frames; reject unfinished frames on assembly timeout or end-of-stream, rather than rejecting every fragmented read. Diagnostics go to stderr on the host, never into the protocol stream. Reject oversized, malformed, unsupported, or corrupted records and recover at a frame boundary. A bad record must not refresh the last valid sample or command lease.

The desktop adapter uses stdin/stdout and flushes each complete response. Send a reliable `STEP(time_us)` for every virtual tick, carrying zero or more separately fault-injected sensor records. The C clock and freshness checks advance even when every sensor record is dropped. On hardware, the periodic timer provides that independent progression. The reliable simulation driver is distinct from the experimental sensor and command link.

The runner supervises the process with a bounded wall-time timeout, using asynchronous reads or a reader-thread/queue so an incomplete-frame read cannot block the timeout itself. Terminate and reap a failed child. A process timeout is a run failure with a preserved trace, not a sensor dropout or permission to swap in the Python controller. Inject drop, duplicate, delayed, reorder, truncation, corruption, and restart events in the declared experimental links. Test sequence wrap and boot epoch changes. Do not let a newly arrived old sample become fresh merely because it arrived now.

Define time explicitly: host SIL observations use the simulation clock, while hardware freshness uses local monotonic receipt time. Sensor/device timestamps provide ordering and diagnostics unless a synchronization relationship is established. Give commands sequence numbers, an explicit validity lease, requested values, and acknowledgements. An acknowledgement means accepted firmware intent; it does not prove motor motion or heat removal.

The actuator adapter holds the last accepted command until its configured lease expires. At expiry, this thermal bench requests heat=0, pump=1, and valve=1; the tank bench uses its own inflow-stop/drain policy. Actuator faults still apply after that fallback. Losing an acknowledgement does not undo an already accepted command or extend its lease. Killing the controller process ends the virtual run with its last state and reason preserved; it is not silently treated as successful fallback operation. Test these distinct cases.

For the RP2040 target, implement a narrow HAL:

- A periodic timer marks work due; the main loop performs bounded controller work and serial parsing. Define and count overruns rather than running unbounded work inside an interrupt.
- ADC reads a potentiometer or declared analog input; GPIO reads a separate trip/reset input and drives an LED or logic-level output. Record actual pin configuration and voltage range.
- Serial uses bounded receive/transmit buffers and the same codec as host execution.
- The watchdog is fed only after the scheduled acquisition/control work completes. Starving that path must cause a measured reset with safe startup state.
- A free-running monotonic clock supplies local timestamps. Describe wrap behavior if a 32-bit clock is used.

Provide two explicitly labeled board modes: a virtual-plant link test with synthetic process measurements, and a peripheral demonstration using real ADC/GPIO inputs. A knob is an emulated process signal, not a calibrated thermal sensor. Do not blend these input sources without recording each channel's provenance.

Cross-build evidence must include compiler version, SDK revision, build log, ELF/map, flash and RAM sizes. Board evidence adds boot ID, actual firmware hash, serial trace, timer/overrun observations, reset behavior, and a photograph or short clip. Do not claim worst-case execution time from a few average measurements. A 10 Hz host/board loop is a demonstration timing target; measure it and label a serial loop as soft real time. Hard real-time HIL remains outside the initial release.

## Scenario and evidence contracts

Create strict versioned scenario, telemetry, summary, and manifest schemas. Validate the same schema for CLI files and direct Python calls. Reject unknown fields, nonfinite numbers, booleans passed as numeric values, incompatible outcomes, and events outside the duration. Give model and controller configurations their own versions.

Telemetry records must distinguish:

- Plant samples, sensor samples, controller ticks, commands, acknowledgements, faults, trips, boundaries, and run termination.
- True Th/Tc/Tw and flow from observed sensor values, sensor quality, sample time, receipt time, clock ID, and age.
- Requested heat/pump/valve commands, fault-modified applied inputs, actual modeled speed/position, and physical outputs.
- Source sequence/epoch, controller state and reason, dropped/corrupt counts, and controller tick duration where measured.

Truth and injection labels are evaluator/replay data only. They never enter controller observations. A separate digital trip channel may be emulated from truth, but label it as an ideal independent sensor channel. Interface separation does not establish real common-cause independence.

The manifest records scenario hash, canonical source hash, explicit repository revision and dirty status, exact dependency versions and lock hash, solver/tolerances/max step, controller tick, seeds, units, input provenance, controller build/firmware hash, and artifact hashes. Hash paths with POSIX separators and file bytes as stored. Mark whether line endings are canonicalized; enforce a `.gitattributes` policy for portable source content. Same-machine replay should produce identical data where appropriate; cross-platform floats use justified tolerances rather than promised bit identity.

Use separate evaluator statuses `PASS`, `FAIL`, `NOT_APPLICABLE`, and `UNASSESSABLE`. Also report the plant outcome: contained, domain boundary reached, complete horizon, or run failure. A deliberately uncontained scenario can pass its expectation while the dashboard prominently shows **containment failed**. Incomplete or corrupt evidence cannot earn a normal pass. Preserve failures and do not overwrite a previous release trace during an ordinary demo.

## Verification and campaign gates

Freeze project thresholds before inspecting new outcomes. The numbers below are starting acceptance targets to review against signal scales and margins, not external safety standards. Any change needs a written reason and renewed relevant evidence.

### Independent numerical checks

1. Preserve analytic tank fill, drain, actuator step, empty/full event times, and seeded replay checks.
2. Pump intersection: independently substitute Q into both pressure curves. Normalized pressure residual must be below 1e-8 for the algebraic calculation; test zero speed, restrictions, and the closed branch.
3. One isolated thermal capacitance with constant heat: reproduce `T=T0+P*t/C`. For independent benchmark components, allow physical coefficients to be zero where the mathematical limit requires it.
4. One capacitance rejecting heat: reproduce exponential cooling to Ts. Aim for maximum temperature error below 1e-5 K in these simple tightened-tolerance benchmarks.
5. With P=0 and UAc=0, weighted total stored energy stays constant while internal temperatures mix. With no flow, internal wall/liquid heat transfer cancels in their combined energy balance.
6. At imposed positive Q, compare all three steady temperatures with the hand solution. Use a long-enough horizon or analytic decay estimate to distinguish remaining transient from solver error; target 0.01 K after settling.
7. The integrated heat-input/rejection residual is a consistency check, just as the tank volume residual is. Verify it, but do not present it as independent validation. Compare against analytic limits and, for the constant-flow thermal subsystem, an independently assembled linear-system solution.
8. Verify terminal temperature events, equality at trip thresholds, retained sensor age, and persistent stopped-domain behavior.

### Refinement and performance

At fixed controller tick, run an rtol ladder 1e-5, 1e-7, 1e-9 with per-state absolute tolerances, then compare against a tighter DOP853 reference. Use per-state normalized errors. If stiffness is demonstrated, document why a stiff solver is warranted and compare an appropriate reference; do not change solvers to hide a defect. SciPy documents adaptive tolerances and the possibility of missed event crossings within large steps. [SciPy solver reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)

Separately refine the controller/communication tick 0.20, 0.10, 0.05 s. Compare peak temperature, tracking error, trip time, and boundary time. Initial thermal targets are peak differences below 0.1 K and trip differences at most 0.1 s between 0.10 and 0.05 s for the selected cases. Keep tank level targets from the supplied plan unless a documented change is required. Discontinuities need not converge monotonically.

Use noise-free reference cases for refinement, or one pre-generated signal sampled consistently across tick choices. Changing the tick must not introduce a different random disturbance and then mislabel that difference as numerical error.

For peaks, examine dense solutions and derivative sign changes over held-input intervals, or publish a conservative bound from sampling and the rate of change. A tick-sampled maximum alone cannot justify a continuous-temperature containment margin.

Benchmark end-to-end suite time, simulated seconds per wall second, peak memory, and host protocol latency on the actual recorded laptop. Establish a practical release budget after the corrected baseline; a suggested goal is the selected 240 s demonstration campaign in under 60 wall seconds with under 512 MiB peak memory. This is a usability goal, not a claim of real-time plant emulation. Profile before adding parallel execution or a faster solver.

### Required scenarios

| Case | Question and expected evidence |
| --- | --- |
| Nominal heat step | Does flow settle without trips, and do thermal trajectories match the declared equilibrium? |
| Restriction increase | Does lower actual flow reduce hot-to-cold heat transport, and do observations/commands show the cause? |
| Reduced heat rejection | Do sink-side and hot-side temperatures rise despite normal measured flow? |
| Flow sensor dropout | Does loss of freshness trigger the bench shutdown policy within the specified stale window plus one tick? |
| Temperature bias or freeze | What can a single plausible signal hide, and what does a separate trip channel reveal? |
| Delayed/reordered/corrupt frames | Do invalid link records fail to refresh validity or change commands incorrectly? |
| Controller or board restart | Is startup disarmed, history segmented by epoch, and rearming intentional? |
| Heat source stuck on and lost sink | Use a 1200 s horizon, fault at 60 s, applied heat forced to 5000 W and UAc forced to zero; verify trip and eventual upper boundary despite continued cooling requests |
| Fault near a tick boundary | Are event ordering and one-tick timing differences explained? |
| Tank stuck-on pump regression | Is the original uncontained overflow still visible as an expected hazard? |

For every case, declare the observable symptom, the rule actually evaluated, the required response, and what remains unknowable. A frozen plausible sensor with fresh timestamps is not reliably diagnosed by freshness alone. If a failure is not observable, say so rather than giving the controller the injector's fault name.

Use case-specific horizons and starting states. A 240 s cold-start nominal run is a useful transient demo but is not sufficiently settled for the proposed equilibrium check, and loss of heat rejection may not reach a trip in 240 s. Use a longer convergence benchmark and the explicit long uncontained case above. Allow zero heat rejection as a fault/limiting-case coefficient while keeping the normal design coefficient positive. First verify the expected long-case trip and boundary independently, then freeze the campaign; do not shorten it until the hazard disappears merely to improve a benchmark.

Start sensitivity screening with one-factor changes and a few meaningful corners: heat load, conductances, resistance, actuator lag, sensor bias, and delay. Label ranges as hypothetical stress assumptions. A Monte Carlo campaign and probabilistic reliability claims are optional after real parameter distributions exist.

## Replay and operator visualization

The required browser tool loads exported local evidence and works on the personal website as a static replay. It does not need a public server that executes simulations or sends hardware commands.

Build one clear page with:

- A compact loop diagram labeled hot wall, hot liquid, cooled liquid, pump, valve, and heat sink. Use SVG or ordinary web code so it reflects the topology.
- Playback, pause, scrub, and scenario selection; all views share one cursor and time base.
- Temperature and flow charts with units, setpoints/limits, measured-versus-true toggles, and legible legends.
- Requested, applied, and actual actuator values on aligned tracks; step plots for commands and state transitions.
- A fault/trip event timeline, numeric peak/trip/age metrics, evaluator status, containment outcome, and a short explanation of each failed criterion.
- A visible data-quality state for stale, invalid, missing, and interpolated data. Break lines across gaps rather than making missing data look continuous.
- A side-by-side or overlay comparison of nominal and fault runs without silently aligning different fault times.
- A provenance panel with revision, model assumptions, firmware evidence level, and raw CSV/JSON download links.

Make the initial view useful in 20 seconds. Show nominal versus impaired cooling, then let the reader inspect detail. Use keyboard-operable controls, readable contrast, responsive layout, and labels in addition to color. Include a screenshot fallback for the case study.

Keep chart and source assets bundled so release replay needs no CDN or account. Define a decimation policy preserving extrema and events if traces become large. Raw exports remain full resolution. Measure load time on the released dataset; aim for less than 2 s on the recorded local setup, and record the environment rather than calling it universally fast.

## Hardware and fabrication evidence

Create a bounded hardware packet even before deciding on a water rig: a P&ID or instrumented topology drawing, I/O table, sensor ranges and sample rates, component/BOM rationale, and one simple mounting fixture drawing with material, dimensions, tolerance intent, assembly access, and cable/tube routing. Clearly mark planned versus fabricated items.

For the software release, the packet explains how the virtual system would be instrumented. For the stronger interview version, Walter builds one fixture or board mount, takes photographs, records one fit/assembly issue and its correction, and performs the MCU peripheral demonstration. Codex can draft CAD and procedures; Walter supplies physical observations and workmanship evidence.

The most valuable subsequent rig is low-energy ambient water: validate tank geometry, drain coefficient, pump flow, and MCU acquisition using independent measurements. Preserve calibration and holdout runs as separate whole experiments. The original proposed RMSE and timing targets can be used as provisional goals after measurement uncertainty is assessed. Do not silently scale the simulated 5 kW input into a real heated rig.

A useful failure investigation has a symptom, competing hypotheses, a discriminating measurement, a correction, and a retest. Include at least one in the release. Label a simulated investigation as synthetic; add a real assembly/instrumentation investigation when performed. Prior fabrication projects can be linked in a separate gallery without implying they were built for this lab.

## Milestones and task board

Estimates are focused human-plus-agent planning allowances, not guarantees of agent runtime. Plan approximately 40–65 hours for a polished software release, another 6–12 hours for board/fixture evidence after tools arrive, and additional experiment time for a water rig. Installation, hardware availability, and debugging can dominate. If the interview is imminent, publish an accurately labeled work-in-progress demonstration of the core path; do not describe deferred gates as finished.

| Milestone | Dependencies | Work and owned paths | Acceptance and retained evidence | Allowance |
| --- | --- | --- | --- | --- |
| M0 Baseline and repository | None | Import starter, setup, `AGENTS.md`, revised docs/tasks | Reproduce 20 tests and seven scenarios on Windows; record environment and inherited-vs-new evidence; initial commit and new repo | 2–4 h |
| M1 Contracts and provenance | M0 | `schemas/`, runner/evaluator, manifests, CI | Strict inputs; real solver metadata; portable hash; correct Git root; termination and evaluator states; regression evidence | 4–6 h |
| M2 Thermal plant | M1 | Thermal model, pump curve, model docs, independent checks | Derivations and limiting cases reviewed; steady state, energy, domain events, solver refinement pass | 6–10 h |
| M3 Shared C controller | M1 | `firmware/core`, `firmware/host`, host adapter | C path controls both benchmarks; anti-windup and trip/reset checks; bounded process failure; Windows/Linux builds | 5–8 h |
| M4 MCU target and protocol | M3 | `firmware/pico`, codec, HAL documentation | Target build and memory report; protocol golden frames/recovery; hardware execution separately recorded | 4–7 h |
| M5 Integrated fault campaign | M2, M3, protocol portion of M4 | Scenarios, evaluator, evidence scripts | All required scenarios; no truth leakage; uncontained case visible; tick/solver refinement; benchmark | 4–7 h |
| M6 Replay and hardware packet | Schemas M1; completion M5 | `web/`, static export, `docs/hardware` | Replay/compare correct; gaps/units/events/provenance visible; instrumentation and fixture design review | 5–8 h |
| M7 Release and case study | M4 cross-build, M5, M6 | README, curated evidence, release, website branch | Fresh checkout reproduction, CI results, five-minute demonstration, public repository and verified live article | 4–6 h |
| H1 Board and fixture evidence | M4 plus equipment | Hardware notes, photos, capture | Actual ADC/GPIO/serial/timer/watchdog run, fixture fabrication and documented correction | 6–12 h |
| H2 Water calibration | M7/H1 as useful | Whole-run datasets and experiment docs | Independent measurements, frozen calibration, held-out runs and discrepancy discussion | Optional |

M2 and M3 can proceed in parallel after M1 because their interface is frozen. M6 can begin with schema-correct fixture data before M5, but final screenshots and numbers must come from released evidence. One writer per shared checkout; use separate worktrees for genuinely independent writers.

Replace the original T01–T08 board with this milestone structure. Archive the original board as reference so an older kickoff cannot mark the project done before firmware and thermal gates. Track tasks in `docs/tasks.json` with ID, dependency, owned paths, acceptance criteria, status, commit, commands actually run, artifact paths, and unresolved limitations. Synchronize GitHub issues with those facts; do not create a second incompatible definition of done.

### Agent working instructions

Start by reading this plan and the starter source. Treat archive prompts as material to revise, not instructions to execute automatically. Review `.codex` configuration before enabling it; the desktop workflow must work without custom CLI roles. Rewrite root `AGENTS.md` to state the revised goal and stable project commands.

Use a coordinator, an implementation writer, and read-only reviewers for physics and tests/evidence. Assign bounded tasks, explicit paths, and an independent oracle. A different agent's agreement is review assistance, not measured validation. Reviewers may write disposable test output in an assigned directory but do not change production equations to make tests pass.

For each ticket: restate the criterion, implement the smallest coherent change, run relevant checks, preserve failure evidence, obtain a review for scientific or cross-layer changes, and record the result. If a check fails, diagnose it before changing the criterion. Ask Walter only for facts or physical actions that cannot be inferred, such as installed board type or an actual measured trace. Routine implementation choices and already-authorized GitHub/publication work should continue autonomously.

At the end of a work session, provide: what now works, a runnable command or view, the most important limitation, checks executed, commit/PR, and the next unfinished gate. After interruption, read the task board, current diff, and evidence manifest, then resume. Do not rebuild completed milestones from scratch.

## GitHub creation and development workflow

The connected GitHub account is `jewbee2000`. Inspection found the website repository `jewbee2000/walts_jekyll_site`. The connector supports repository reads and code/issue/PR work but exposes no repository-creation tool in this session. GitHub CLI is the practical fallback for creation and local Git transport; plugin sign-in does not establish CLI authentication.

Before creation, verify the authenticated CLI login and the proposed repository name. A permissions or network error is not evidence that the name is free. If the name already exists, inspect it and choose an unused name rather than replacing it. Create the new project as a private working repository, then make the completed portfolio release public as part of Walter's requested publication. Keep the site repository separate.

After the baseline and plan have been committed in the intended local project directory, the creation operation is:

```powershell
gh repo create jewbee2000/virtual-thermal-fluid-lab --private --source . --remote origin --push --description "Fluid and thermal simulation, portable embedded control, and reproducible fault replay"
```

Use this only from the intended project root with no conflicting origin. Check the command outcome and remote URL; do not silently push to a different repository. GitHub documents creation from local source. [Repository creation](https://cli.github.com/manual/gh_repo_create)

Use short milestone branches and reviewable commits. Open PRs for meaningful milestones with the behavior changed, its reason, relevant checks, and evidence links. Prefer the connector when it supports the action; use CLI for missing capabilities. Attach created PRs to the Codex chat using its artifact tool when available. Reconcile current branch and remote state before updating or merging; never force-push as a routine recovery tactic.

CI must execute meaningful checks on Windows and Linux: Python unit/integration suite, C host build/CTest, strict schema fixtures, and deterministic campaigns. Include a separate Pico cross-build and Linux compiler sanitizers for the bounded parser and controller. Pin tools/actions deliberately, commit lockfiles, and preserve current tool versions. A YAML workflow file is not a passing CI run; capture actual run links.

The release README leads with a 30-second demo, screenshot, the exact installation/reproduction commands, architecture, evidence, and limitations. Include license/attribution inventory; preserve source licenses and confirm redistribution rights for any imported assets. Record Walter's intended license for his new code during kickoff rather than pretending a missing source license proves unrestricted reuse.

At release, audit tracked files, rerun from a fresh checkout or built package, make the repository public, tag `v0.1.0`, and publish curated evidence plus a static replay bundle. Record the immutable commit in the article. Public replay artifacts must not depend on private GitHub links or local absolute paths.

## Website case study and publication

Walter confirmed `walter.teitelbaum.us` and GitHub account `jewbee2000`. The discovered Jekyll repository's `_config.yml` and `CNAME` match that domain, and its post layout uses `layout: post`, `title`, and `lead`. The live site already presents projects such as AbyssBench and fabrication work. Preserve that style and navigation. [Website](https://walter.teitelbaum.us/), [Site repository](https://github.com/jewbee2000/walts_jekyll_site)

Before editing, inspect a fresh clone and the actual deployment source/branch. The connector's main-branch post listing showed older example posts while the live site showed newer project posts; do not assume that writing `_posts` on the observed main branch alone will update the live site. Determine the active build/deploy workflow and match a recent live article to its source. If necessary, ask Walter one specific deployment question after inspecting available configuration.

Publish an approximately 900–1400-word engineering article titled **Testing a Thermal Fluid Loop with Simulation and Embedded Control**. Use the actual publication date, not this plan's date. Put its source and figures under the site's established paths; likely `_posts/YYYY-MM-DD-virtual-thermal-fluid-lab.md` and `assets/projects/virtual-thermal-fluid-lab/`, subject to that deployment check. Do not edit generated `_site` output unless the verified pipeline explicitly deploys a tracked built output.

The article should contain:

1. A concrete engineering problem and one actual result, stated within its evidence limits.
2. The thermal loop diagram and why a lumped model answers the selected question.
3. One independently verified equation or limiting case in plain language.
4. A fault plot showing heat, measured temperatures, actual flow, commands, and trip time.
5. How the same C controller connects to the host and MCU, with executed-vs-built evidence stated accurately.
6. A short failure investigation, tradeoff, and correction; include real hardware photos when available.
7. A replay/demo link, public source release, reproduction instructions, and the next experiment.

Use 2–4 figures derived from final release traces. Avoid invented successes, placeholder metrics, a wall of technology names, or a claim that the lab reproduces subsea operation. Explain what Walter designed, understood, tested, and physically built, and how Codex assisted. His ability to explain the design is central to the interview goal.

Generate the article from the final evidence, check it against the claims ledger, build/preview the existing Jekyll site, and inspect desktop and mobile rendering, equation layout, figures, navigation, and downloads. Create a reviewable site PR with a preview if the workflow supports it. Walter already requested eventual publication: once the release and concrete preview pass their gates, publish through the established pipeline and verify the actual live URL. Do not substitute a new hosting provider or a separate redesign.

## Definition of done and interview demonstration

The software project is complete only when the following are true:

- A clean Windows checkout reproduces installation, host firmware build, campaign, and exported replay using the documented commands. Linux CI and target cross-build have actual evidence.
- The thermal derivation, independent limiting cases, numerical refinement, and domain semantics are documented and exercised.
- The flagship campaign runs the C controller; sensor and actuator faults cannot leak truth or silently substitute another controller.
- Results identify data quality, applied-versus-requested behavior, evaluator applicability, incomplete evidence, and failed containment honestly.
- The replay is useful without installing development tools, and released raw traces/manifests match its figures and metrics.
- The public GitHub release and website article are live, connected by immutable evidence links, and verified after publication.
- Hardware execution and physical validation have their actual status prominently stated; no planned hardware is presented as built.

For the stronger hands-on portfolio, complete H1 and link a real fabrication/instrumentation example. For a mechanically oriented interview, prioritize H1/H2 over more dashboard features after the core works.

The five-minute interview sequence is: show the loop and a hand calculation; run nominal then impaired cooling; expose a stale input and the local response; show a stuck heat source that ignores the stop request; open the independent test and manifest; finish with board/fixture evidence and the next measurement that would reduce uncertainty. Explain the distinction between a verified simulation, firmware exercised on a board, and physically validated plant predictions.

## Primary setup references

Research and repository inspection were performed October 5, 2026 Pacific. Employer descriptions may change; refresh the exact role before the interview. Project coefficients and acceptance goals remain authored choices.

- [Native Windows Codex](https://learn.chatgpt.com/docs/windows/windows-app) and [Windows sandbox guidance](https://learn.chatgpt.com/docs/windows/windows-sandbox).
- [uv installation](https://docs.astral.sh/uv/getting-started/installation/) and [locked project environments](https://docs.astral.sh/uv/guides/projects/).
- [GitHub CLI authentication](https://cli.github.com/manual/gh_auth_login) and [repository creation](https://cli.github.com/manual/gh_repo_create).
- [CMake build workflow](https://cmake.org/cmake/help/latest/manual/cmake.1.html) and [CTest](https://cmake.org/cmake/help/latest/manual/ctest.1.html).
- [Raspberry Pi Pico toolchain extension](https://github.com/raspberrypi/pico-vscode).
- [SciPy solve_ivp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html). Current documentation is newer than the starter's pin; verify APIs against the pinned version before implementation.
- Supplied `Virtual_Fluid_Lab_Research_and_Plan.pdf`, especially the model, verification, and milestone sections, and `virtual-fluid-lab-starter.zip`. Preserve their useful equations and evidence while superseding the old completion criteria and setup prompts.


