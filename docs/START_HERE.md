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

Read REQUIREMENTS.md and tasks.json. M0-M7 are complete: thermal physics, the shared C core, Pico cross-builds, fault campaign, replay and public release have executed evidence. Use README.md and REPRODUCE.md for the current firmware/replay commands. Hardware execution and holdout validation remain separate. Walter selected MIT, confirmed starter authorship and access to Pico/Arduino; Pico is the selected target. No API key is needed.
