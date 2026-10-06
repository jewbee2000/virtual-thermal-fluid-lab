# Scientific verification and physical validation

Current authority: docs/REQUIREMENTS.md and Codex_Implementation_Plan.md, required
M0–M7. Original T02/T07 references below are historical. Native Windows M0 reran
20 tests and seven scenarios on 2026-10-06; actual logs: evidence/M0. Physical
validation remains NOT_STARTED and board execution NOT_EXECUTED. M1 corrects
R09 unconditional success and R10 vacuous passes without relaxing thresholds.

Use NASA-STD-7009B as a credibility checklist, not a certification claim [S1]. The project-specific thresholds below are authored here. Freeze them before examining new scenario outcomes; document any revision and its reason.

## Tests already implemented

| Requirement | Oracle and acceptance | Meaning |
| --- | --- | --- |
| R01 | Nominal last 30 s stay within 0.02 m of target | Educational control requirement |
| R02 | Volume residual <1e-9 m³ | Conservation implementation consistency |
| R03–R04 | No nominal trip or domain exit | Baseline behavior |
| R05 | Dropout trips within 0.5 s of injection | Timestamp freshness contract |
| R06–R07 | Bias ramp trips high switch; peak <0.95 m, no domain exit | Containment for this modeled fault |
| R08 | Stuck-on pump triggers high switch, then reaches full boundary | Test exposes an uncontained hazard |
| R09 | Characterization run completes and records outcome | Exploratory; NOT a safety pass criterion |
| R10 | All commands after trip request zero pump | Latched command behavior |
| R11 | Blocked outlet remains below 0.65 m without domain exit | Closed-loop containment; fault diagnosis not required |

Independent numerical benchmarks in `tests/test_science.py`:

- Constant-flow fill: h(t)=h0+Qt/A, absolute comparison at 1e-10 m precision.
- Gravity drain with no inflow: h(t)=[sqrt(h0)-kt/(2A)]², k=C_d a_o sqrt(2g), evaluated before the empty time. Comparison at 1e-8 m precision.
- Empty time: t_empty=2A sqrt(h0)/k, agreement within 0.01 s using tightened tolerances.
- Pump step: q(t)=Qmax u[1-exp(-t/tau_p)]; integrated inlet volume=Qmax u[t-tau_p(1-exp(-t/tau_p))].
- Full time under constant fill: t_full=A(H-h0)/Q; verify event time rather than clipping.
- RK45 vs DOP853 at tighter tolerances: state difference <1e-7 in the current test. Because states have mixed units, this simple cross-check must later become per-state normalized tolerances.
- Nominal controller tick refinement 0.10→0.05 s: compare matching timestamps, maximum level difference <0.002 m. This changes the digital controller as well as communication timing; it is separate from numerical solver refinement.
- Anti-windup recovery, deterministic seeded replay, bad timestamps, invalid samples and latched stop behavior.

## Next verification gate

T02 adds a solver tolerance ladder (rtol 1e-5, 1e-7, 1e-9 with corresponding scaled atols) at fixed controller tick, and a separate communication/tick ladder (0.20, 0.10, 0.05 s). Compare peak level, integral absolute error, trip time and boundary time. At minimum, require 0.10 vs 0.05 s peak differences <0.002 m and trip differences ≤0.10 s for chosen scenarios; justify tighter thresholds from hazard margins. Do not demand every difference shrink monotonically near discontinuities.

Add single and combined faults, setpoint changes, threshold equality, and faults just before/after a tick. Start with pairwise fault combinations, then target combinations suggested by hazards. Keep classification of detection, stop command, containment, and physical safety separate.

## Physical validation experiment (not performed)

Use a low-energy ambient-water rig only after approving its topology and reviewing spill/electrical protection. No pressure or heated hardware is required for this project. A transparent vessel, low-voltage pump, tubing, outlet restriction, separate level/high switch, scale or graduated collection vessel and timestamps are sufficient classes of equipment. Select actual components after defining ranges and calibrating sensors; there is no shopping requirement for the software phase.

1. Measure tank volume against height at multiple points; estimate effective area and geometry departures.
2. Calibrate the level sensor using known heights. Record reference uncertainty, repeatability, hysteresis, resolution and sensor sample/filter latency.
3. Run drain-only trials at three initial heights and three fixed openings, with three repeats each: 27 traces. Fit effective `C_d*a_o*z` or a monotone opening curve. Level-only data cannot identify C_d and a_o separately; fix one from geometry or fit their product.
4. At three pump settings, collect volume over measured intervals; repeat each. Perform steps while measuring flow separately where feasible, then estimate lag. A true centrifugal pump requires pressure/head measurements and a different model.
5. Freeze calibration parameters and choose entirely separate runs for validation: unseen starting levels, pump steps and drain changes. Preserve whole runs as groups; do not randomly split neighboring time samples between fit and holdout.
6. Report held-out RMSE, peak error, timing error and residual plots against time, level and command. NIST cautions that a large R² alone does not establish adequacy [S7]. Correlated residuals indicate missing dynamics or measurement effects.
7. Predeclare provisional physical acceptance: level RMSE ≤0.01 m, maximum error ≤0.03 m and event timing error ≤max(0.5 s, 5% of event time). These are proposed project goals, not standards. If reference uncertainty prevents resolving them, improve measurement or revise the intended use openly.

Use bounded nonlinear least squares, consistent units, and physically positive parameters. Estimate parameter uncertainty by resampling independent runs (or a justified block bootstrap), not individual time points under autocorrelation. Inspect parameter correlations and sensitivity before interpreting estimates.

## Uncertainty and credibility status

Separate measurement uncertainty, parameter uncertainty, model discrepancy and numerical error. NIST TN1297 covers Type A/B measurement uncertainty and combining components [S8]; it does not make arbitrary simulation ranges into measured probabilities.

Before hardware data exist, use a declared sensitivity grid such as area ±5%, effective outlet coefficient ±20%, pump capacity ±20%, actuator lag 0.5–3 s, sensor bias ±0.01 m and transport delay 0–0.3 s. Those are hypothetical stress ranges, not confidence intervals. Start one-factor-at-a-time plus meaningful corners; introduce Latin-hypercube/global analysis once interactions justify it. Preserve seeds and parameter sets. Report peak level, trip latency, tracking error, boundary exits and detection misses.

For an actual probabilistic campaign, document how distributions and correlations were estimated. Zero failures in N independent draws yields an approximate 95% upper failure-probability bound of 3/N only for that declared sampling distribution, not for all possible hardware faults. A Monte Carlo pass cannot eliminate structural model error.

Current status: analytical verification implemented; code checks executed in the packaged environment; physical validation NOT_STARTED; independent human review pending; uncertainty campaign planned. Agent agreement is review assistance, not independent empirical evidence.
