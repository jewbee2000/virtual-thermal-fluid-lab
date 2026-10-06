# Reproduce the software release on native Windows

Use PowerShell7 (tested7.6.5), Python3.12, uv0.12.19, Git, CMake4.4.4 and Visual Studio C++ Build
Tools. Tested tool versions, official sources and archive hashes are in
[TOOLCHAINS.md](TOOLCHAINS.md). No WSL, API key or MCU board is required for SIL.
Keep output directories new: an ordinary run must not overwrite release evidence.

From a clean checkout of the release tag:

```powershell
git clone --branch v0.1.0 https://github.com/jewbee2000/virtual-thermal-fluid-lab.git
cd virtual-thermal-fluid-lab
uv sync --locked
./scripts/build_host.ps1 -CMake (Get-Command cmake).Source
uv run python -m unittest discover -s tests -v
uv run python scripts/run_suite.py --out artifacts/reproduce/tank
uv run python scripts/verify_thermal.py --out artifacts/reproduce/thermal
uv run python scripts/run_campaign.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/reproduce/campaign --repeat
uv run python scripts/refine_campaign.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/reproduce/refinement
uv run --no-project --python 3.12 --with jsonschema==4.25.1 python scripts/audit_exports.py --run artifacts/reproduce/campaign --run artifacts/reproduce/refinement
```

Each command must exit0 before continuing. The campaign includes all17 thermal
cases, seven real-C tank cases and the seeded nominal repeat. The refinement has
36 executions. A deliberately uncontained hazard passes its expectation while
reporting containmentFAILED and completionFAIL. Inspect those statuses separately.
The independent auditor's isolated dependency does not change the simulation lock.

Export the complete19-scenario replay (all thermal cases and two tank contrasts):

```powershell
$taskReplayArgs = @('scripts/build_replay.py', '--run', 'artifacts/reproduce/campaign/nominal_heat_step')
foreach ($taskScenario in (Get-ChildItem scenarios/thermal/*.json | Where-Object BaseName -ne 'nominal_heat_step' | Sort-Object Name)) {
    $taskReplayArgs += @('--run', "artifacts/reproduce/campaign/$($taskScenario.BaseName)")
}
$taskReplayArgs += @('--run', 'artifacts/reproduce/campaign/tank/nominal', '--run', 'artifacts/reproduce/campaign/tank/pump_stuck_on', '--out', 'artifacts/reproduce/replay')
uv run python @taskReplayArgs
```

Open `artifacts/reproduce/replay/index.html` in a browser. The static bundle
contains charts, full source rows, raw downloads and licenses; it fetches no CDN
or simulation service. Its local HTTP hosted-variant preview was checked;
actual public deployment is recorded separately when performed.
Direct file-URL browser execution was not available to this desktop automation;
record that distinction instead of inventing an offline browser check.
For a website variant use a new output directory and add `--compress-raw`; all
summary/transport downloads are lossless gzip with original and packaged hashes.

Measure software performance only after other local tests/builds finish:

```powershell
uv run python scripts/benchmark_campaign.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/reproduce/performance
uv run python scripts/benchmark_campaign.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/reproduce/suite-performance --suite
```

The selected240s nominal demo has frozen60s/512MiB budgets for the recorded
observed process family. PID coverage and method limitations accompany the
measurement. The whole differing-horizon suite is separately recorded without
silently applying the240s budget. Neither measurement establishes hard real time.

Native device checks and target build are separate from running SIL:

```powershell
cmake -S firmware/pico/tests -B artifacts/device-tests
cmake --build artifacts/device-tests --config Release
ctest --test-dir artifacts/device-tests -C Release --output-on-failure
# Replace these quoted example paths with your provisioned pinned tools.
./scripts/build_pico.ps1 -SdkPath 'C:/tools/pico-sdk-2.3.1' -ToolchainPath 'C:/tools/arm-15.2.rel1' -Picotool 'C:/tools/picotool/picotool.exe' -CMake (Get-Command cmake).Source -Ninja (Get-Command ninja).Source
```

Use the pinned SDK/TinyUSB/Arm/picotool inputs in TOOLCHAINS.md; build picotool
with `PICOTOOL_NO_LIBUSB=1` for UF2 conversion. Both target modes use the same C
core as SIL. See [Pico README](../firmware/pico/README.md) and the
[hardware packet](hardware/PACKET.md) for explicitly unexecuted physical steps.
Board execution is NOT_EXECUTED, fabrication NOT_FABRICATED and physical
validation NOT_STARTED. Do not use cross-build sizes as runtime measurements.

[DEMO.md](DEMO.md) gives the five-minute walkthrough.
[REQUIREMENTS.md](REQUIREMENTS.md) and [tasks.json](tasks.json) define and record
the gates. Release reports preserve actual revisions, source/binary/lock hashes,
solver settings and failures; provenance is never reassigned after execution.
