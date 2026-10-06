# M1 accepted source checks, 2026-10-06

Actual writer commands (native Windows uv0.12.19, unchanged scientific lock):

```
uv run python -m unittest discover -s tests -v
uv run python scripts/run_suite.py --out artifacts/M1-work/accepted-suite
uv run fluidlab scenarios/nominal.json --out artifacts/M1-work/final-nominal --plot
```

Latest full suite55PASS/11.305s; includes all original20 and35 contract tests.
Seven scenario expectations PASS. Stuck pump remains containmentFAILED/full.
unit-tests.txt and scenario-console.txt are actual logs; suite.json, per-scenario
summary/manifest retained. Full CSV traces remain locally at accepted-suite/.
Accepted source hash6691819d7eaaae533d9e05acb15a32ad58cf865dc971a64a40b9ead1ac546713;
manifests honestly identify M0 Git revision/dirty=true because M1 was uncommitted.
The plotted nominal run preceded only the final missing-trip-time guard; its own
manifest identifies that earlier source correctly. No figure is misattributed.

An initial20-test run had19PASS/oneERROR: new domain guard rejected terminal-root
roundoff. initial-failure-record.json is an outcome record, explicitly not a
verbatim retained console log. Repair retains raw root residual and64-ulp event
tolerance, permanently stopped state; never clamps or resumes outside domain.

Read-only test reviewer repeated concrete corrupt-evidence mutations: NaN observed
value, future receipt, illegal requested/applied commands, negative physical state,
Boolean tick identities, truncated post-trip horizon, missing/wrong terminal
boundary, missing first-trip time. All can no longer earn an overall pass.
Five named domain/provenance/solver tests passed0.592s; no-fault dt=.07s
normalization remained idempotent and active unaligned injection rejected.

R09 now requires complete horizon; R10 no-trip is NOT_APPLICABLE; overall normal
expectation requires completion. A coherent expected full-boundary hazard may pass
expectation while containmentFAILED. Sampling gaps add a conservative Qmax/A
level-rise bound; numerical error remains separately limited by solver checks.

M1 changes do not establish thermal model, C/MCU execution, hardware or physical
validation. Physical validation NOT_STARTED. Revised Windows/Linux CI both passed for b105ae9:run37431609613;
retained windows-linux-ci.json. PR2 merged at175d000; M1 closed. Source/parameter/schema changes
invalidate relevant earlier artifacts; inherited examples remain historical.
