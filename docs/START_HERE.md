# Start on native Windows

Use the existing Codex desktop app and PowerShell in this checkout. WSL and Codex CLI are not prerequisites. Archived setup is in archive/START_HERE-starter.md.

uv 0.12.19 is installed at C:\Users\Walt\.local\bin\uv.exe. A new PowerShell session should discover it; for an existing shell:

```powershell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
uv --version
uv sync --locked
uv run python -m unittest discover -s tests -v
uv run python scripts/run_suite.py
uv run fluidlab scenarios/nominal.json --out artifacts/nominal --plot
uv run fluidlab scenarios/pump_stuck_on.json --out artifacts/pump_stuck_on --plot
```

M0 ran with Python3.12.2, Windows11, NumPy2.3.5, SciPy1.17.0 and Matplotlib3.10.8. New baseline logs are in evidence/M0; examples/ are inherited historical evidence. Dependencies and lock remain unchanged.

At .5m level and .65 opening, hand calculation gives 7.572105L/min drain and .31550438 ideal inflow command. This is metered inflow, not a centrifugal operating point. After stop its assumed lag means flow decays; a stuck-on pump ignores the request and overflows.

Read REQUIREMENTS.md and tasks.json. Thermal physics, shared C core, Pico target cross-build, fault campaign, replay and publication are required M2-M7. Hardware execution and holdout validation are separate. Walter selected MIT, confirmed starter authorship and access to Pico/Arduino; Pico is selected per the revised plan. Firmware/replay commands are added when implemented and executed. No API key is needed.
