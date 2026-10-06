# M2 native Windows thermal verification

Actual execution on 2026-10-06. The full unit suite passed 78 tests in 20.507 s,
including the original tank tests and 23 thermal tests. All seven preserved tank
scenario expectations passed. The thermal benchmark command was:

```powershell
uv run python scripts/verify_thermal.py --out artifacts/M2
```

It passed ten checks and exported eleven raw CSVs, retained here byte-for-byte
with verification.json, manifest.json and the inspected figure. The manifest
records the executed solver/configuration and source hash
b73cd947f1345fa8ad8a21dfc2796e7d7b5f09c72faf468eca245985272a0413,
revision eda4ee1ac3a218517375a4d6d1f83394ee72fbd4, dirty=true. This accurately
describes the precommit execution; it is not relabeled as a clean later commit.

The independent imposed-flow matrix comparison error was 9.09e-13 K; equilibrium
error after 1200 s was 0.000109133 K. The tightest normalized solver error was
0.0001234 against the frozen per-state scales. Nonmonotonic errors at this small
scale remain in the report. A 240 s cold-start run is a transient demonstration,
not the equilibrium acceptance check.

The reported 13.226 s host duration occurred while other checks ran concurrently;
it is an observed duration, not the isolated M5 performance benchmark. These
are numerical verification results using assumed parameters. Physical validation
is NOT_STARTED and board execution is NOT_EXECUTED. Controller integration is M5.
The lower-bound cooling example approaches the sink asymptotically; the synthetic
lower-root test verifies guard/diagnostic behavior without inventing a finite
physical crossing. Read-only physics review is recorded separately.
