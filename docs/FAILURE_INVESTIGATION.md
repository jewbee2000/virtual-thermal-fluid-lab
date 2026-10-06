# Synthetic investigation: fresh temperature evidence conceals overheating

This is an executed simulation investigation with assumed parameters. It is not
a physical sensor failure, assembly trial or measured hardware result.

The symptom in `frozen_temperature` is that wall/hot truth rises after heat
rejection is lost at60s while the two primary observations remain plausible.
Three competing explanations are transport dropout, a stale cache, or a sensor
value that has stopped following the plant while continuing to send fresh packets.

The discriminating measurement is the retained raw O/Q/R traffic plus source,
receipt, last-good time and quality in the CSV. Those clocks advance, quality is
valid, and the primary values remain317.791K/301.124K. Freshness supervision
cannot identify this failure. Controllers receive only those observed channels;
plant truth and fault labels are available to the evaluator and replay.

The modeled mitigation is the separately acquired ideal wall-trip channel. It
asserts at343.9s, latches the C supervisor and requests zero heat/full pump/full
opening. The recoverable campaign's largest continuous temperature bound is
358.208801432K (85.0588C), below the frozen359.15K criterion; the bound excludes
numerical error. Separate solver/tick refinement checks numerical sensitivity.

The retest deliberately defeats physical heat-off: `stuck_heat_lost_sink` keeps
5000W applied despite a346.6s trip. It reaches the wall boundary at
466.299590127s and reports containmentFAILED/completionFAIL. The commanded
mitigation therefore succeeds only under the declared actuator assumptions.

Raw files, criteria and rule evidence are in the released campaign and replay.
A future experiment must measure sensor lag, diagnostic coverage, actuator
failure behavior and genuine channel independence. The ideal separate switch in
this software does not establish any of those physical properties.
