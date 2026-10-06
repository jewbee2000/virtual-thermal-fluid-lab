# Virtual Fluid Lab: research and implementation plan

HISTORICAL STARTER REFERENCE. This document preserves the original research,
roadmap and source-status statements as supplied. Its optional thermal milestone,
older M0–M7/T01–T08 completion criteria, WSL preferences and unexecuted-tooling
statements are superseded by Codex_Implementation_Plan.md, REQUIREMENTS.md,
START_HERE.md and tasks.json. Current actual evidence is under evidence/; old
examples remain inherited records. Do not execute this historical roadmap or
infer today's tooling/CI state from its dated text.

Prepared for Walter Teitelbaum. Research checked October 5, 2026 Pacific / October 6 UTC.

## The project I recommend

Build a reusable software-in-the-loop test platform around an educational pump, valve and open-tank model. The demo should answer: **when a sensor or actuator fails, what can the controller detect, what does it command, and does the modeled plant remain within its allowed domain?**

Your Poirot work already gives you experience commanding hardware, collecting data and handling device states. This project develops the parts that are less familiar: conservation-law modeling, separating simulated truth from observable I/O, virtual-time scheduling, evidence-based test oracles and physical model validation. My assessment is that these capabilities will provide a stronger interview demonstration than an elaborate fluid animation with an uncertain model.

Endurance's employer-hosted posting describes building software, controls and electrical infrastructure to validate components and subsystems for a subsea geothermal plant [S16]. That supports the connection to test infrastructure. The posting was searchable, but its JavaScript-rendered page yielded no full body during retrieval. I therefore do not assert that Endurance uses HIL, FMI, Python, Modelica, or a particular PLC stack. Our project is an independently designed learning exercise; it does not reproduce their confidential hardware.

The deliverable progresses from a small physically understandable plant to a platform that can run different models, controllers and scenarios. It has a specific definition of done: a one-command scenario suite, inspectable evidence, tests against analytic solutions, a second model adapter, and a short demonstration explaining a failure the controller cannot contain. Real-world validation is a separate optional gate with measurements.

## What the research changes about the design

| Research-backed practice | Concrete project decision | Source |
| --- | --- | --- |
| Define intended use, assumptions, verification, validation, uncertainty and review evidence | Maintain a model contract and claims ledger; label physical validation status in reports | S1–S2 |
| Derive tank accumulation from conservation; distinguish model abstraction from hardware | Start with a single open tank and document every idealization | S3, S5 |
| Choose numerical methods by stiffness and accuracy needs; handle events explicitly | RK45 baseline, DOP853 reference, later Radau if stiffness appears; terminal empty/full events | S4 |
| Saturated actuators require explicit anti-windup treatment | PI with conditional integration; separate actuator lag from command | S6 |
| Model-fit statistics alone are insufficient | Held-out whole experiments plus residual and timing analysis | S7 |
| Measurements require an uncertainty statement | Calibration records, repeat runs, Type A/B uncertainty, measurement limits | S8 |
| Co-simulation has communication points, event semantics and capability constraints | Define a stepped model interface first; treat FMI as a later adapter | S9 |
| Dependency locking supports repeatable execution | Pin tested libraries, commit uv.lock, use locked synchronization | S10 |
| Agents work well on bounded independent tasks; concurrent edits need care | One writer, read-only reviews, three-child cap, explicit task ownership | S11–S13 |
| HIL uses real DUT I/O and deterministic real-time execution | Call the baseline SIL; require a hardware and timing gate before any HIL claim | S17 |
| Fluid property tooling has explicit state/phase semantics | Use CoolProp only for a later thermodynamic model with a declared domain | S18 |

These sources support the methods. They do not prescribe this tank's dimensions, controller gains, fault timing, acceptance thresholds or roadmap estimates. Those are original project decisions provided below for review.

## Choose the smallest useful physics

Use a lumped state model rather than CFD for the first milestone. We need water inventory and slow actuator dynamics; we do not initially need the spatial velocity field or turbulence. A lumped model is suitable only while its assumptions match the question. CFD becomes useful if local mixing, heat-transfer geometry or spatial pressure losses drive an actual decision.

The first plant is an atmospheric tank with an ideal metered inflow and a gravity drain. Level rises according to inflow minus outflow. The pump flow and valve opening approach commands over finite time. This makes actuator coast and command saturation observable without pretending to model a real centrifugal pump.

The second plant introduces a finite supply reservoir and a pump operating point from a head-flow curve against system losses. The optional third adds temperature and energy balance. Subsea hydrostatic pressure, seawater materials, phase change and real heat-exchanger behavior remain outside the initial project. Higher complexity is justified by a test question and data, not by the appearance of realism.

| Option | Benefit | Cost / reason for routing |
| --- | --- | --- |
| Python + SciPy | Transparent equations, analytic checks, familiar automation environment | Recommended initial implementation; timing is virtual |
| OpenModelica / Modelica.Fluid | Physical network components and equations useful for a second implementation | Later cross-check; initialization and empty states need care [S19] |
| FMI adapter | Portable exchange with external plant/controller tools | After interface and timing contracts exist; export support varies |
| CFD solver | Spatial flow/thermal questions | Defer until a specific question needs it; validation burden grows |
| Learned surrogate | Fast approximation after a validated reference model exists | Not initial truth; quantify its added approximation error |

## System architecture

The coordinator has six boxes to keep conceptually separate:

1. **Plant:** owns true state, physical parameters and integrator. Exposes reset/advance and named outputs.
2. **I/O adapter:** produces observed signals, timestamps and independent switch channels. Injects sensor faults here.
3. **Controller:** sees observed I/O and returns requested actuator commands. No privileged truth access.
4. **Supervisor:** evaluates freshness, validity and declared high/low conditions; its latched output overrides commands.
5. **Scenario runner:** owns virtual time, command holding, fault activation and run configuration. Actuator faults alter applied commands after the supervisor.
6. **Evaluator/report writer:** accesses truth for test oracles, calculates metrics, records limitations and produces CSV/JSON/plots.

The baseline modules provide these responsibilities with a simple in-process implementation. `Observation` is a frozen dataclass. `Plant.advance()` is the current simulation boundary. Ticket T03 formalizes a Protocol for replaceable plants and I/O, adds command/schema versioning, and eliminates fixed tank-height assumptions in the supervisor. Do not split into multiple services until the in-process semantics are tested.

A future process boundary uses a sequence number, sample timestamp, monotonic receive timestamp, validity flag and command acknowledgement. Distinguish sensor freeze, dropped message, reordered message and delayed message. The controller must never infer validity solely from arrival time or trust a remote wall clock without a synchronization policy.

## Milestones and review gates

My effort estimates assume you can work regularly with agents but will inspect equations and evidence yourself. They are planning estimates, not guarantees. A credible basic demonstration is approximately 12–20 focused hours; the complete software portfolio version about 35–60 hours; hardware validation adds roughly 15–30 hours plus equipment work.

| Stage | Work and output | Gate / estimated effort |
| --- | --- | --- |
| M0: establish the baseline | Install, run provided checks, understand every state and plotted signal | Explain one hand calculation and one fault; 1–2 h |
| M1: model and requirements | Review equations, units, topology, parameter pedigree, sensors and hazard responses; freeze interfaces | T01 closed with your reviewed model contract; 2–3 h |
| M2: numerical credibility | Tolerance ladder, tick ladder, normalized solver comparison, more analytic limiting cases | Benchmarks pass and numerical errors are small relative to margins; 3–5 h |
| M3: reusable test infrastructure | Protocol adapters, strict configs, metric definitions, manifests and requirement traceability | A second simple model runs the same harness; 4–6 h |
| M4: control and fault campaigns | PI tuning rationale, state transitions, fault combinations, delays and detector limitations | Predeclared criteria and blind review of failure evidence; 5–8 h |
| M5: physical model calibration | Instrument a water rig, fit parameters on calibration runs, reserve holdouts | Physical validation report or explicit pending status; optional 15–30 h |
| M6: pressure / thermal extension | Add one justified model, validate its equations and domain, compare adapters | Independent physics review and benchmarks; 8–15 h |
| M7: portfolio demonstration | Command-line demo, plots, architecture, claims ledger and limitations | Reproduce from fresh checkout; 2–4 h |

### M1: freeze what you are testing

Before changing code, review pump type, flow directions, normal operation, safe responses and available signals. Decide whether the goal is level control, fault diagnosis or fault containment; they are different requirements. List hazards with causes, detection channels, response commands and residual risks.

The baseline's response preserves drainage and stops inlet pumping. A thermal loop might require the opposite: maintaining coolant circulation could be important. Never reuse a shutdown rule without reviewing topology. Define whether a trip can reset, who can reset it and what must be true first. The starter is permanently latched for a run.

### M2: make numerical error visible

Run open-loop analytic checks before closed-loop performance tests. Refine solver tolerances while keeping the digital control schedule fixed. Separately refine controller/communication ticks while holding other conditions constant. Record event times rather than relying on plots at coarse sample intervals.

Use state-specific absolute tolerances; a flow measured in m³/s cannot share an arbitrary tolerance with a dimensionless valve opening. Record solver status, evaluations and failures. Compare a structurally separate implementation and solver, but remember that two implementations of the same incorrect equation can agree.

### M3: turn a script into a test platform

Define `PlantAdapter.reset(config)`, `advance(dt, commands)` and observable output semantics. Add strict scenario validation, unknown-field rejection, unit/range checks and integer tick scheduling. Preserve separate requested command, applied command and physical actuator state in telemetry.

Every run should produce configuration, parameter pedigree, schema version, source hash, Git revision/dirty flag, library versions, random seed, solver/tolerance settings, clock policy, metrics, requirement results and credibility status. The starter already emits much of this; remaining strictness is T03. A plotting failure must not erase the raw trace.

Keep test expectations outside implementation logic where possible. The starter's scenario checking is intentionally small; T04 separates evaluator classes and adds reasons for skipped/unassessable criteria. Include CSV plus JSON; a database and live dashboard are optional after the workflow is useful.

### M4: exercise faults you can and cannot observe

Start with the seven supplied scenarios. Add pump degradation, valve opening mismatch, sensor delay, invalid values, packet loss, reset/arming errors and paired faults. Require a detector to use only available measurements. Use truth only to score outcomes.

Design residual-based detection only after the expected signal and uncertainty are known. A level residual from the same nominal model can be confounded by parameter error, sensor bias and actuator faults. Record false alarms, missed detections and latency, not just a favorable example.

Use both nominal and changed parameters. For a sensor freeze with fresh timestamps, deliberately demonstrate a case that remains undiagnosed. Add a genuinely separate channel to improve observability, then explain what changed. Do not give the controller the fault label.

### M5: collect evidence that can falsify the model

The experiment design and provisional acceptance criteria are in `VERIFICATION.md`. Measure geometry and sensor response first. Calibrate on complete experiments and validate on different complete experiments. Avoid fitting a model on synthetic data from itself and calling that physical validation.

Use repeated independent runs, hold out combinations of levels and commands, and examine structured residuals. A model that predicts steady-state well may still predict trip latency badly. If the physical pump depends strongly on head, reject the ideal-flow abstraction for that hardware and advance to M6.

### M6: the challenging extension

The most useful extension for this role is a **pump-and-pipe operating-point model with testable fault consequences**. Define pump pressure rise Δp_p(Q,n), static head Δp_static and losses Δp_loss(Q). Solve the operating-point condition Δp_p=Δp_static+Δp_loss. If a flow transient is needed, derive an inertance equation from momentum conservation rather than adding arbitrary lag. Use calibrated curves or manufacturer data with documented units and limits. A closed valve may raise pressure without large tank-level change; pressure measurement is then essential.

Do not extrapolate affinity laws beyond their assumptions, and distinguish gauge from absolute pressure. Cavitation requires inlet conditions and vapor pressure, and cannot be inferred from tank level alone. Add independent pressure relief/energy isolation to the conceptual hazard analysis; software trips alone are not sufficient evidence of pressure protection.

A thermal alternative is a well-mixed tank energy model with constant mass m:

`m*c_p*dT/dt = m_dot*c_p*(T_in-T) + P_heater - UA*(T-T_ambient)`

This assumes equal inlet/outlet mass flow, constant c_p and a mixed bulk temperature. If mass changes, derive `d(m*u)/dt` with inlet/outlet enthalpy flows and boundary terms. Use analytic heating/cooling cases before variable properties. CoolProp [S18] is an optional property library with explicit state/phase handling, not a validation certificate. Match the property formulation to the model's permitted pressure/temperature/phase envelope.

FMI is a later adapter, not an early dependency. FMI 3.0.2 specifies co-simulation communication steps, event processing and early-return capabilities [S9]. Check the actual exporter/importer feature matrix. FMI support does not guarantee real-time performance or semantic equivalence. Cross-compare open-loop outputs on aligned grids before closed-loop coupling.

### M7: prepare a hiring-manager demo

Use a five-minute story:

- Show a nominal run and explain the conservation equation in plain language.
- Show a biased level sensor and the separate high switch stopping inflow.
- Show a stuck-on pump where the stop command fails to contain the hazard.
- Show the independent analytic tests and a reproducible run manifest.
- Explain what measurement would most reduce uncertainty and what you would test next.

A useful headline is: “A reusable SIL fluid-control test bench with analytic verification, deterministic fault injection and explicit model-credibility evidence.” Claim “physically validated” only after the holdout gate is actually passed. Do not claim a geothermal digital twin, NASA compliance, industrial functional safety or production HIL.

## Agent orchestration plan

Use Codex's built-in subagents and Git rather than requiring Gas Town or a separate orchestration service. This is my project-specific recommendation: current official tooling already covers task delegation and narrow custom roles [S12]. The project benefits from independent research and test review, but changing the numerical contract is strongly coupled work.

The coordinator owns the backlog, contracts, integration and final evidence. An implementation agent edits one bounded subsystem. A physics reviewer derives independent oracles and challenges assumptions. A test reviewer looks for counterexamples. An evidence reviewer verifies source-to-claim mappings and report reproducibility. Cap active children at three; use readers in parallel and one source-code writer per shared checkout. Four roles do not need to run simultaneously.

Exact kickoff and role prompts are included. Use manual worktrees only if independent writers are truly necessary. Do not allow agents to merge conflicting model equations automatically. Track task status and acceptance criteria in `docs/tasks.json`; ask each agent for sources, changed files, executed checks, unresolved questions and a recommendation. One failed revision permits one repair attempt before escalation to the coordinator.

Agents assist with derivation and implementation. The final scientific checks are equations, independent analytic solutions, numerical convergence, measured data and your review. Different agent roles do not create statistical or scientific independence by themselves.

## What is ready and what remains

Ready: pinned project environment and lockfile, runnable first-order plant, controller/supervisor separation, seven scenarios, analytic and behavioral tests, report output, plots, custom agent files, prompts, backlog, experiment templates and a CI workflow.

Planned: strict schema versioning, a fully generic adapter interface, systematic refinement report, rigorous detection metrics, uncertainty campaigns, a second model, real hardware I/O, calibration and holdout validation. The starter intentionally leaves these as learning work, rather than hiding a complete black-box implementation from you.

## Annotated primary-source register

Sources establish methods; project dimensions and thresholds are our choices. No technical recommendation relies on a news article, aggregator or unsourced forum claim.

- **S1 — NASA-STD-7009B, Standard for Models and Simulations (2024, retrieved current record).** Intended use, model records, V&V, uncertainty, sensitivity and results credibility. We adapt its structure; do not assert compliance. [Standard record](https://standards.nasa.gov/standard/nasa/nasa-std-7009), [PDF](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf).
- **S2 — NASA-HDBK-7009B (2026).** Implementation guidance companion; source record checked, not an exhaustive clause review. [Handbook record](https://standards.nasa.gov/standard/NASA/NASA-HDBK-7009).
- **S3 — OpenStax / Rice University, University Physics 1, Bernoulli's Equation.** Conservation-based pressure/height/velocity relationship; empirical discharge and restrictions require separate assumptions. [Chapter](https://openstax.org/books/university-physics-volume-1/pages/14-6-bernoullis-equation).
- **S4 — SciPy solve_ivp documentation.** Nonstiff/stiff solver choices, tolerances, event crossings. Documentation retrieved as v1.18; starter uses tested v1.17 APIs for the same features. [Reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html).
- **S5 — APMonitor process-control education, Control a Water Tank Level.** A pedagogical tank mass balance and saturated controller; the proposed drain/actuator model is an extension, not copied hardware data. [Exercise](https://apmonitor.com/pdc/index.php/Main/TankLevel).
- **S6 — MathWorks, Anti-Windup Control Using PID Controller Block.** Conditional integration, back-calculation and actuator-tracking distinctions. We implement conditional integration in Python. [Documentation](https://www.mathworks.com/help/simulink/slref/anti-windup-control-using-a-pid-controller.html).
- **S7 — NIST/SEMATECH e-Handbook, How can I tell if a model fits my data?** Residual analysis and limitations of R². [Handbook](https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm).
- **S8 — NIST Technical Note 1297.** Measurement uncertainty terminology and evaluation; not a recipe for unmeasured simulation probabilities. [Guidance](https://www.nist.gov/pml/nist-technical-note-1297).
- **S9 — Modelica Association, FMI Specification 3.0.2.** Co-simulation timing and event capability semantics. [Specification](https://fmi-standard.org/docs/3.0.2/).
- **S10 — Astral uv documentation.** Installation, project environments and lockfiles. [Installation](https://docs.astral.sh/uv/getting-started/installation/), [Projects](https://docs.astral.sh/uv/guides/projects/).
- **S11 — OpenAI official Codex CLI docs.** Current installer, launching the client and account sign-in. [CLI](https://developers.openai.com/codex/cli/) (redirects to ChatGPT Learn).
- **S12 — OpenAI official Subagents docs.** Delegation, current custom-agent TOML schema, concurrency limit and model inheritance. [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).
- **S13 — OpenAI official AGENTS.md and Windows docs.** Repository instructions and native-Windows/WSL routing. [AGENTS.md](https://developers.openai.com/codex/guides/agents-md/), [Windows sandbox](https://developers.openai.com/codex/windows/).
- **S14 — Microsoft Learn, Install WSL.** Installation prerequisites and distribution selection. [Install](https://learn.microsoft.com/en-us/windows/wsl/install).
- **S15 — Microsoft Learn, WSL interoperability.** Filesystem placement for Linux and Windows workflows. [Interop](https://learn.microsoft.com/en-us/windows/dev-environment/wsl-interop).
- **S16 — Endurance Energy employer-hosted Ashby posting, Senior Test Infrastructure Software Engineer.** Employer search-index extract establishes component/subsystem test-infrastructure focus. Full rendered body not available during retrieval; exact stack unconfirmed. [Posting](https://jobs.ashbyhq.com/endurance-energy/b7ee011a-9ee3-4a96-b350-a1aac52af91f/).
- **S17 — NI, What Is Hardware-in-the-Loop?** Real controller/DUT, physical I/O and real-time simulation definition. [Guide](https://www.ni.com/en/solutions/transportation/hardware-in-the-loop/what-is-hardware-in-the-loop-.html).
- **S18 — CoolProp, High-Level Interface.** Optional thermodynamic property evaluation and state inputs; retrieved documentation is 8.0.0, library not installed or used by starter. [API](https://coolprop.org/coolprop/HighLevelAPI.html).
- **S19 — Modelica Standard Library, Tanks examples.** External equation-based benchmark candidate; indexed documentation warns about complete emptying and singular balances. Page retrieval failed, so treat detailed behavior as requiring a fresh documentation check before implementation. [Examples](https://doc.modelica.org/Modelica%204.1.0/Resources/helpDymola/Modelica_Fluid_Examples_Tanks.html).

- **S20 — Official GitHub action repositories.** CI action syntax checked against maintained publisher documentation. The workflow is supplied but has not run on GitHub. [setup-uv](https://github.com/astral-sh/setup-uv), [checkout](https://github.com/actions/checkout), [upload-artifact](https://github.com/actions/upload-artifact).

Cross-check conclusion: the baseline derivations agree with conservation and Bernoulli reasoning, and analytic tests exercise the implementation independently. No physical dataset has been collected, so scientific verification does not establish physical predictive accuracy. This is the central limitation to preserve in every demo and report.
