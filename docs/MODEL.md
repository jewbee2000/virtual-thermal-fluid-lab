# Model contract and hand derivation

The atmospheric tank equations below remain the preserved benchmark. Required
thermal-loop derivation and domain policy are in THERMAL_MODEL.md. Both are
assumed educational models; physical validation NOT_STARTED. Revised milestones
and execution acceptance are REQUIREMENTS.md and Codex_Implementation_Plan.md.

## Physical layout

A supply reservoir (treated as an unlimited external boundary) feeds an ideal controllable metering pump. The pump discharges into an open vertical tank. A variable outlet drains to a separate external reservoir at atmospheric pressure. A level transmitter feeds the PI controller; an independent high-level switch feeds the supervisor. This is a through-flow topology, not a closed loop. The code does not model either external reservoir's inventory.

## States and equations

The states are `h` (m), `q_p` (m³/s), `z` (dimensionless valve opening), `V_in` and `V_out` (m³). Inputs `u_p` and `u_v` lie in [0,1]. Density is constant so volume conservation is equivalent to mass conservation:

\[
A\dot h=q_p-q_d,\quad q_d=C_d a_o z\sqrt{2gh}.
\]

The drain law follows a quasi-steady Bernoulli velocity estimate with an empirical discharge factor [S3]. `z` linearly scales effective area; it is not a vendor valve Cv/Kv characteristic. Both surfaces see atmospheric pressure. Surface velocity is neglected relative to outlet velocity. Pipe resistance and inertance are omitted.

\[
\tau_p\dot q_p=Q_{max}u_p-q_p,\quad \tau_v\dot z=u_v-z,
\quad\dot V_{in}=q_p,\quad\dot V_{out}=q_d.
\]

These actuator lags are deliberately assumed first-order approximations, not derived pump dynamics. A gravity flow law plus an ideal metering pump is self-consistent for a bench abstraction. It cannot predict deadhead pressure, cavitation, pump curve operating points, backflow, or power consumption.

The independent conservation residual is:

\[
r_V=A(h-h_0)-(V_{in}-V_{out}).
\]

Because these quantities are integrated in one augmented ODE, this residual is an implementation consistency check, not an independent proof of physical correctness. Analytic trajectories provide stronger independent checks.

| Quantity | Default | Pedigree |
| --- | --- | --- |
| Tank area A | 0.05 m² | Chosen: approximately 252 mm inside diameter |
| Tank height | 1.0 m | Chosen; 50 L capacity |
| Effective full-open outlet area a_o | 0.0001 m² | Chosen; approximately 11.3 mm equivalent diameter |
| Discharge coefficient C_d | 0.62 | Illustrative assumption, must be measured |
| Gravity g | 9.80665 m/s² | Conventional standard gravity; local variation ignored |
| Pump maximum flow | 0.0004 m³/s = 24 L/min | Chosen ideal flow source |
| Pump / valve time constants | 1.0 / 0.5 s | Chosen lag assumptions |
| Initial / target level | 0.25 / 0.50 m | Chosen scenario conditions |
| Normal drain opening | 0.65 | Chosen normalized opening |
| High switch / full boundary | 0.80 / 1.00 m | Chosen educational thresholds |
| Controller tick | 0.10 s | Chosen; tested against 0.05 s |

At h=0.5 m and z=0.65, the nominal drain flow is about 0.0001262 m³/s, or 7.57 L/min. Required ideal pump command is about 0.3155. The controller uses Kp=3 m⁻¹ and Ki=0.06 (m·s)⁻¹ with that approximate feedforward bias. These are demonstration gains, to be reviewed rather than treated as experimentally tuned.

## Timing and boundaries

At tick t_k: sample I/O, apply the supervisor, calculate commands, inject active actuator faults, log, then integrate over [t_k,t_(k+1)] with commands held constant. A fault scheduled at 60 s is applied at that tick. Configurations must align duration and fault time with ticks. Internal solver steps and controller ticks are different clocks. Random sensor noise is generated only at ticks, never inside the ODE right-hand side.

RK45 is the default. Vector absolute tolerances respect differently scaled states. `max_step` is at most 0.05 s. Empty and full are terminal events; no clipping of accepted levels or continued simulation outside the domain. SciPy warns that event crossings can be missed inside a large step [S4]. This model therefore uses a step cap and boundary benchmark tests. The `max(h,0)` used only in the drain formula keeps solver trial evaluations real near an empty event; it does not authorize negative accepted levels.

Initial level must be strictly inside the tank. Full overflow physics, empty-tank restart, finite reservoirs and check valves are future work. Endpoints logged at a terminal boundary retain the preceding held command and last sampled measurement; they are plant snapshots, not new controller samples.

## Shutdown and observability

Shutdown is latched. A bad or stale sample or an independent high switch requests zero pump flow. Drain command remains 0.65 to preserve gravity drainage for this topology. The actual pump state decays with its time constant; flow does not vanish instantly. A stuck-on pump ignores the zero command. A blocked valve may ignore its command too.

Controllers receive only `Observation`; they never receive the Plant object. The runner computes switch activation from truth as an emulated separate channel. Independence here is an interface property; hardware common-cause failures are not represented.

A plausible frozen value with fresh timestamps cannot reliably be identified from freshness alone. Fault injection may know the fault, but the controller must not be given that knowledge. Add genuinely separate observability (flow measurement, position feedback, redundant level, or a calibrated residual) before promising diagnosis.

Validity domain: open tank, constant density, single phase, assumed pump and valve characteristics, 0<h<1 m, nonnegative forward drain flow. No claims about Endurance's actual plant, subsea pressure, phase change, thermal efficiency, pressure safety, or industrial safety integrity follow from this model.
