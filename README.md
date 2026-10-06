# Virtual Thermal Fluid Lab

A fluid and thermal engineering portfolio project for Walter Teitelbaum. The atmospheric tank baseline runs; required next milestones add a thermal circulation model, one C controller core on desktop and Pico, and an inspectable static fault replay. The software release and case study follow actual evidence gates.

**Start here:** use native Windows/PowerShell in the existing desktop app. Read `docs/START_HERE.md`, the rationalized `docs/REQUIREMENTS.md`, and `docs/tasks.json`. `docs/Codex_Implementation_Plan.md` supersedes the starter roadmap. Historical prompts/tasks are preserved under `docs/archive/`.

```powershell
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run fluidlab scenarios/nominal.json --out artifacts/nominal --plot
uv run python scripts/run_suite.py
```

The starter includes a sampled PI controller, latched shutdown supervisor, gravity drain, actuator lag, seven fault scenarios, analytic benchmarks, solver comparison, controller-tick refinement, and CSV/JSON reports. No API key is needed for the simulation.

M0 actually reproduced all 20 tests and seven scenario expectations on native Windows on 2026-10-06; see `evidence/M0`. Later milestones are tracked as unfinished until their checks run. A hazard expectation passing still means containment failed for the stuck-on pump. License: MIT; Walter confirmed starter authorship. MCU target: Pico/RP2040; board execution NOT_EXECUTED.

M1 source checks passed55 tests and seven scenarios; see `evidence/M1` and current CI
status in `docs/tasks.json`. Inputs are strict, executed solver settings and portable
source hashes are retained, terminal snapshots expose sensor age, and incomplete
evidence cannot pass. The tank remains the Python benchmark until M3 adds C control.

M2 now implements the assumed thermal loop and stable pump/system intersection.
Run `uv run python scripts/verify_thermal.py --out artifacts/thermal-checkpoint`
for analytic heating/cooling, an independent matrix solution, persistent boundary
checks and solver refinement. Native Windows checks passed78 tests, the seven
tank scenarios and ten thermal benchmarks; retained evidence is in `evidence/M2`.
At imposed9 L/min and5 kW the assumed equilibrium is20 C cooled liquid,
27.974 C hot liquid and44.641 C wall. The1200 s benchmark approaches it within
0.000109133 K; a240 s cold start remains transient. C integration follows M3.

M3's native C host now runs the preserved tank campaign with the same portable
controller core intended for Pico. Build with `./scripts/build_host.ps1` when
CMake is on PATH (or supply its `-CMake` path), then run:

```powershell
uv run python scripts/verify_host.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/c-checkpoint
```

Native combined checks passed95 unit tests, CTest and both seven-case tank suites.
The C dropout trips at60.3 s; the stuck pump still overflows after shutdown.
See `evidence/M3`. MCU clock/HAL additions and thermal C integration follow M4/M5.

**Credibility:** equations and numerical implementation can be verified; physical validation is NOT_STARTED. Parameters and acceptance thresholds are educational design choices. This is software-in-the-loop (SIL), not hardware-in-the-loop (HIL), a subsea geothermal model, or a certified safety system.

| File | Purpose |
| --- | --- |
| `docs/Codex_Implementation_Plan.md` | Required thermal, firmware, replay and release roadmap |
| `docs/REQUIREMENTS.md` | Rationalized requirements and frozen acceptance criteria |
| `docs/RESEARCH_AND_PLAN.md` | Historical starter research and source register |
| `docs/START_HERE.md` | Native Windows setup and first session |
| `docs/MODEL.md` | Equations, units, assumptions, validity envelope |
| `docs/VERIFICATION.md` | Checks, physical experiments, uncertainty and acceptance |
| `docs/ORCHESTRATION.md` | Agent ownership, execution, reviews and recovery |
| `AGENTS.md` | Repository-wide instructions |
| `.codex/agents/` | Four optional custom agent definitions |
| `prompts/` | Kickoff and role prompts |
| `scenarios/` | Seven runnable configurations |
| `docs/tasks.json` | Current M0–M7 task/evidence record |
| `docs/CLAIMS.csv` | Evidence and claims ledger |
| `examples/` | Inherited starter outputs; historical evidence |
| `evidence/` | Actual checks performed during revised implementation |

Sources were reviewed on October 5, 2026 Pacific time (October 6 UTC). Official tooling can change: record local versions and verify configuration support. Python libraries are pinned in `pyproject.toml` and `uv.lock`; these are tested project choices, not a claim that they are the newest releases.
