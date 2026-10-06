# Native integrated campaign evidence

Executed on native Windows on 2026-10-06. The default source and criteria were
frozen at b858360 before outcomes. The actual C host SHA256 is
8152e818f72869d201f64389367621b255fc1619d56caacbab5f5d38caa552ef.
All parameters are assumed; board NOT_EXECUTED, physical validation NOT_STARTED.

`uv run python scripts/run_campaign.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/M5-frozen-campaign --repeat`
exited0: all17 thermal and seven actual-C tank expectations passed, and the
nominal raw telemetry repeated byte-for-byte. The entire differing-horizon
campaign took155.3898421s; this is not the selected240s performance gate.
Its captured source hash is12993d92d41685959d4ec07db7ffeca396eda6a7d922ae123712ff453045df85,
Gitb858360, dirtytrue (release-license preparation was uncommitted).

Independent read-only review checked251 artifact/manifest hashes, parsed357885
raw ASCII frames, reconstructed observation caches/replies for every thermal
controller tick and confirmed18 child reaps/exit0. Only the two intentionally
corrupt/truncated frames failed their checks. Last30s tracking windows have301
ticks: nominal true error1.538849566e-9 and restriction6.847618660e-7m3/s,
both below3e-6. Energy residual maximum3.464519978e-7J is below1e-3J.
Recoverable global peak bound maximum358.208801432K is below359.15K,
excluding numerical integration error. Freeze/bias rescue trips at343.9s;
dropout/near-tick trips60.3/60.4/60.5s match independent timing oracles.

The long hazard trips at346.6s yet continues applying5000W. Its wall reaches
368.15K at466.299590127s. ExpectationPASS means the predicted counterexample
occurred; completionFAIL and containmentFAILED remain explicit. Its4669-row
peak bound covers the retained prefix, not the requested1200s horizon.
The tank stuck-pump case also remains uncontained.

`uv run python scripts/refine_campaign.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/M5-frozen-refinement`
exited0: all three solver ladders, six thermal tick cases and two tank tick cases
passed (36 executions). Independent raw-grid review reproduced all nine solver
comparisons and eight tick comparisons, and372 artifact/manifest hashes matched.
Largest tightest normalized state error0.002244467945 is below1; thermal tick
peak difference at most0.033090201733K is below0.1K, trip difference at most0.05s.
Thermal/tank hazard boundary differences0.000773795126s/0.002856052254s are below0.10s.
Shared preterminal comparisons exclude roots and stop at466.2s/161.1s.

Provenance qualification: a standards-based schema audit found that derived
non-transmitted observation ages at a fractional terminal root were incorrectly
declared integer. The five schema properties were corrected to nullable numbers;
raw traces, runtime code and acceptance criteria were unchanged. Refinement
retains19 manifests at source12993d92… and17 at6d143232c9af7fcb91daf7e7628cf9bbce2392de53518835b3dfc73733655661.
Only the telemetry schema differs. Original metadata was not rewritten.
The corrected schema audit passed18 thermal exports/42263 rows; its failed
pre-correction log is retained. Two earlier audit-helper CSV decoding errors are
local in artifacts/schema-nominal-*.txt; they were corrected before this audit.

The full unit run passed128 tests in22.824s. Earlier failing fixture/schema checks
are retained with corrected logs, not claimed as successful checks. Full raw
captures live in ignored artifacts/M5-frozen-campaign and M5-frozen-refinement;
the release replay/evidence bundles supply their retained exports.

Isolated performance, final clean reproduction and CI closure follow; they are
not established by the results above.

The first isolated selected-demo measurement returned its implemented PASS:
8.6111146 wall seconds and485867520B (463.36MiB) sum of observed process peaks,
with no monitor errors. `performance.json` preserves that original result. Review
then found a Windows venv identity gap: the required launcher PID was not the
scientific interpreter PID. The interpreter's442040320B peak was observed, but
its role was not explicitly retained. The final diagnostic repair records the
actual Python owner in every C startup event and requires launcher, owner and
each actual C PID for a pass. Missing owner proof is unassessable. Thresholds
and observed-family qualification are unchanged; the final measurement reruns
after this proof repair. The original captures were not rewritten.

The final retained export audit tool passed48 thermal exports,157182 rows and484
artifact hashes using isolated jsonschema4.25.1; the simulation lock is unchanged.
Final parent-PID diagnostic checks passed130 unit tests in26.471s before the
lossless hosted packaging patch. The clean M7 reproduction rechecks the combined
release source.
