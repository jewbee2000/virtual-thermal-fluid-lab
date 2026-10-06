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

**Credibility:** equations and numerical implementation can be verified; physical validation is NOT_STARTED. Parameters and acceptance thresholds are educational design choices. This is software-in-the-loop (SIL), not hardware-in-the-loop (HIL), a subsea geothermal model, or a certified safety system.

| File | Purpose |
| --- | --- |
| `docs/RESEARCH_AND_PLAN.md` | Research, decisions, staged implementation, references |
| `docs/START_HERE.md` | Linux/Windows setup and first session |
| `docs/MODEL.md` | Equations, units, assumptions, validity envelope |
| `docs/VERIFICATION.md` | Checks, physical experiments, uncertainty and acceptance |
| `docs/ORCHESTRATION.md` | Agent ownership, execution, reviews and recovery |
| `AGENTS.md` | Repository-wide instructions |
| `.codex/agents/` | Four optional custom agent definitions |
| `prompts/` | Kickoff and role prompts |
| `scenarios/` | Seven runnable configurations |
| `docs/tasks.json` | Initial implementation backlog |
| `docs/CLAIMS.csv` | Evidence and claims ledger |
| `examples/` | Actual checked baseline output and verification evidence |

Sources were reviewed on October 5, 2026 Pacific time (October 6 UTC). Official tooling can change: record local versions and verify configuration support. Python libraries are pinned in `pyproject.toml` and `uv.lock`; these are tested project choices, not a claim that they are the newest releases.
