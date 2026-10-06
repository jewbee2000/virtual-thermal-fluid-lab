# Repository instructions

Virtual Thermal Fluid Lab: educational fluid/thermal SIL, shared portable C host/MCU control, and static evidence replay. Read README, docs/REQUIREMENTS.md, docs/Codex_Implementation_Plan.md, docs/MODEL.md, docs/VERIFICATION.md and the assigned milestone in docs/tasks.json before editing. The current request and revised plan supersede the archived T01–T08 roadmap and prompts.

- Use SI quantities with unit-bearing names; all commands normalized [0,1]. Never silently substitute Cv, Kv, mass flow or volume flow.
- Keep plant truth separate from observed I/O. Controllers/supervisor must not access Plant or fault labels.
- Preserve virtual-time schedule and zero-order-held inputs. Keep random sampling out of ODE functions.
- Stop at domain boundaries. Never clamp away inventory errors or relabel an uncontained hazard as a safe outcome.
- State parameter pedigree: measured, literature, manufacturer or assumed. Baseline parameters are assumed.
- Verification, physical validation and safety certification are distinct. Physical validation is NOT_STARTED until holdout evidence exists.
- Changing equations, assumptions or acceptance thresholds requires an explicit rationale and evidence update. Do not loosen a criterion solely to pass a failing test.
- Use independent analytic oracles; do not derive expected test results by calling the function under test.
- Keep one code writer per shared checkout; readers may review concurrently. Use separate worktrees for independent writers. Follow the revised prompts/00-kickoff.md.
- Coordinator alone edits docs/tasks.json and shared contracts; return concise handoffs with files, checks, sources and remaining uncertainty.
- Run `uv run python -m unittest discover -s tests -v` and the scenario suite for behavioral changes. Record actual commands and outcomes. Do not claim a check you did not execute.
- Preserve pinned dependencies and lockfile. Develop natively in Windows/PowerShell using the existing desktop app; WSL and Codex CLI are not prerequisites. Baseline development needs no hardware. The user authorized private GitHub development and public release/website publication after the revised release gates. Keep the website in its separate verified deployment checkout.
- New work should be reviewable in bounded commits. Do not add unrelated services, cloud infrastructure or CFD before a test question justifies them.
- Start M0/M1 then proceed through required M2–M7 with runnable learning checkpoints. Ask only for missing facts, browser sign-in or physical actions. Cross-builds do not establish board execution or physical validation.
- Use one C core for host SIL and Pico; never silently fall back to Python in the flagship campaign. Keep simulation, host wall and device monotonic clocks distinct.

Stable baseline commands in PowerShell:

```powershell
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run fluidlab scenarios/nominal.json --out artifacts/nominal --plot
uv run python scripts/run_suite.py
```

Add firmware and replay commands only when implemented and executed. Historical .codex role files are optional for desktop operation.
