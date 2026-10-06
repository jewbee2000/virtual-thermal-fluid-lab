# M6 implementation checks before integrated thermal replay

Executed natively in the isolated `thermal-lab-replay` Windows worktree based on
`7c4f770`, 2026-10-06. These are implementation checks, not the final release gate.

| Command / observation | Actual result |
| --- | --- |
| `uv sync --locked` | Passed; Python3.12.2; existing pinned dependencies/lock retained |
| `uv run python -m unittest discover -s tests -v` | 105 tests passed17.147 s;6 actual-host integration tests skipped because this isolated worktree has no built host executable |
| Same full suite with `FL_CONTROLLER_HOST` pointing to the actual coordinator MSVC host executable | 105 tests passed17.121 s, **no skips**; binary SHA256 `8152e818f72869d201f64389367621b255fc1619d56caacbab5f5d38caa552ef` |
| `uv run python scripts/run_suite.py --out artifacts/M6-tank-suite` | Seven preserved Python tank expectations passed; stuck pump `high_high`/`full` remains uncontained |
| `uv run python -m unittest discover -s tests -p test_replay_export.py -v` | 10 independent export/gap/time checks passed; last run0.306 s |
| `node --check web/replay.js`, `web/replay-model.js`, vendored uPlot JS | Passed syntax checks |
| `uv run python scripts/build_replay.py --run <actual M3 C nominal> --run <actual M3 C pump_stuck_on> --out artifacts/M6-c-tank-replay` | Passed; all retained input artifact SHA256s verified; original bytes and two PNG fallbacks exported |
| Headless native Microsoft Edge154.0.4258.53 / bundled Playwright smoke | Actual retained M3 C dataset;2 runs/4014 rows; desktop1365×1000 and mobile375×900 screenshots; no JavaScript errors or external HTTP requests; no document overflow; keyboard Home produced0 s; `telemetry.csv` downloaded |
| Initial Edge script/plot-render observations | 117.0 ms before final captions and99.2 ms after; each excludes browser startup, **not** final released thermal-dataset performance evidence |
| Actual C stuck-pump outcome browser check | At120 s displayed TRIPPED, expectationPASS, containmentFAILED; at absolute240 s with nominal comparison displayed no source sample and no extension beyond the earlier terminal boundary |
| `uv.lock` SHA256 | `76472376ec629c6fb1da220501125f413dc2944f76e75139283ea2cb3ca7bcd0` unchanged |
| Standard-library XML parser on both authored hardware SVGs | Parsed successfully; this checks syntax, not CAD render or physical fit |

Logs: `artifacts/M6-checks/unit-tests.txt`, `unit-tests-with-host.txt`,
`scenario-suite.txt`, `export-tests.txt`.
Browser command/result/screenshots: `artifacts/M6-browser-smoke/`. They are local
ignored artifacts; the coordinator must retain selected logs in milestone evidence
before archiving this worktree. The final `check-final.cjs`, `result-final.json`
and `tank-*-final.png` repeat desktop/mobile/download/keyboard checks after the
controller-identity label, comparison-outcome caption and mobile-scroll hint.
`hazard-check.cjs/json` retain the separate failed-containment/termination check.

Still required: export actual final M5 thermal C runs, independently verify replay
cursor/quality/command/boundary display against those raw records, visually inspect
desktop/mobile/keyboard behavior, measure repeated released-dataset load time,
and derive final screenshots/figures from released data. The fixture is planned
NOT_FABRICATED; board NOT_EXECUTED; physical validation NOT_STARTED. OpenSCAD source
is supplied but no CAD-tool render or physical fit test was executed.

Coverage/license follow-up, 2026-10-06: the conservative thermal bound now retains
and displays `peak_bound_coverage` scope, actual retained start/end (including
fractional terminal roots), requested end and discarded-row count. UNAVAILABLE or
inconsistent coverage suppresses the numeric bound. The exporter now copies the
project MIT license unchanged as `LICENSE.txt` and hashes it in the replay manifest.

Actual checks: focused12 export/JS-helper tests passed0.513 s before the license
repair and0.615 s afterward; JS syntax checks passed. The full107-test suite
passed17.268 s without skips using the same actual MSVC host binary, and all seven
tank expectations passed; those broad checks preceded the narrow license-copy
repair. The later focused test checks both copied license bytes and manifest hash.
Project license SHA256:
`faf01a2585858a00fc23a8489041ca74c0f3fe45d8cbd81a4a50fb8f3c757cfb`.

Prior to the coordinator's instruction to reserve further browser QA for CUA,
an additional native Edge154.0.4258.53 smoke used three explicitly labeled
UI_FIXTURE NOT_VERIFICATION datasets. It displayed RETAINED_PREFIX through
1.23456789 s versus requested1200 s, FULL_RETAINED_HORIZON and UNAVAILABLE with
the numeric bound suppressed. No JavaScript errors or mobile document overflow
were observed. These are interface fixtures, not thermal campaign evidence.
No browser automation was performed after that instruction or for the final
license link. Logs are `artifacts/M6-checks/coverage-*.txt/json/cjs`; the synthetic
export is `artifacts/M6-coverage-ui-fixture/` and must not supply release figures.
