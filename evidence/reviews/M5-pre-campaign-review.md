# M5 review before integrated outcomes

Read-only reviewers examined the implementation and frozen criteria before the
full thermal campaign, refinement and performance measurements. This report
records their bounded scope; it is not a campaign result.

The evidence reviewer accepted the repaired runner/evaluator after executing
`uv run python -B -m unittest discover -s tests -p test_campaign.py -v`
(16 tests passed, 4.432 s), `adversarial_probes.py` and `endpoint_probe.py`.
Actual C processes supplied freshness, error-quality, lease and ACK evidence.
Nine altered telemetry records and contradictory ACK/lease records were rejected.
Removing the entire final wire transaction and retaining a coherent final
snapshot returned UNASSESSABLE for the missing scheduled controller tick.
The initially invalid fixture name was corrected; both probe outputs are retained.
Compiler/PID/layout metadata and a modified-trip release guard were checked.
These checks did not execute the full campaign or measure performance.

The physics reviewer independently confirmed the energy balance and units,
the exact event splits and held physical inputs, and the maximum-temperature
growth bound of 0.5 K/s under its stated premises. `thermal.py` remained unchanged
from M2. The bound excludes numerical error and omitted pump dissipation.
Separate ideal switch evidence shows software-channel separation; it does not
establish physical independence. Static reads, Git comparison and standalone
arithmetic succeeded; this reviewer executed no unit or campaign suite.

The reviewer found that full-run peaks at identical 95 C/1 m boundaries could
hide different trajectories. The coordinator strengthened the frozen terminal
tick refinement gate before outcomes: compare identical preterminal sample keys
and common gaps, require at least two distinct shared times, record prefix end,
and separately require matching boundary presence/kind and fractional boundary
time agreement within 0.10 s. The existing thermal/tank peak and trip criteria
remain unchanged. A new peak-bound coverage object labels the retained interval;
invalid discarded/nonfinite/unsorted evidence cannot retain a numeric bound.

Independent arithmetic reproduced nominal speed 0.527498282, pressure
18,825.443787 Pa, instantaneous restriction flow ratio 0.638160353 and required
restricted speed 0.826592063. The reduced-rejection flowing equilibrium is
50/57.974482/74.641148 C (cooled/hot/wall); this is not a 600 s equilibrium gate.
The long stuck-heat energy argument places a model upper boundary by 585.3 s
absolute under the frozen assumptions. These are predictions, not measurements.

Review sources: [DOE thermodynamics and heat transfer handbook](https://www.energy.gov/sites/default/files/2026-04/DOE-HDBK-1012-92_VOL1.pdf),
[OpenStax Bernoulli](https://openstax.org/books/university-physics-volume-1/pages/14-6-bernoullis-equation),
[pinned SciPy solve_ivp documentation](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.integrate.solve_ivp.html).

Parameters remain assumed. Physical validation NOT_STARTED; board execution
NOT_EXECUTED. The final outcome review follows actual campaign execution.
