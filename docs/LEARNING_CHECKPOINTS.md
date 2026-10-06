# Milestone learning checkpoints

These checkpoints explain the engineering decisions behind the executed software.
They do not establish Walter's independent mastery or claim unperformed hardware.
Commands run from the repository root; choose a new output directory each time.

| Milestone | Runnable result | Explain and inspect |
| --- | --- | --- |
| M0 Baseline | `uv run python scripts/run_suite.py --out artifacts/learn-M0` | Conservation changes stored inventory. A stop request cannot prevent overflow when applied inflow remains on. Distinguish expectationPASS from containmentFAILED. |
| M1 Contracts | `uv run fluidlab scenarios/nominal.json --out artifacts/learn-M1 --plot` | The manifest identifies actual solver/source/seed. Sensor source time, receipt time and last-good age answer different questions. Missing evidence must never create a vacuous pass. |
| M2 Physics | `uv run python scripts/verify_thermal.py --out artifacts/learn-M2` | Add the three energy balances: internal terms cancel. Convert9L/min to1.5e-4m3/s. Derive20/27.974/44.641C equilibrium and explain why240s cold start is still transient. |
| M3 Shared C | `./scripts/build_host.ps1` then `uv run python scripts/verify_host.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/learn-M3` | A pure C controller sees observed channels, never plant truth. Work through PI saturation/anti-windup, latching, epoch/order rules and a stale-age equality case. |
| M4 Pico | Native device CTest and the pinned build in `firmware/pico/README.md` | Virtual time is exact; device PI uses actual elapsed time. Bound queue/ADC work, retain source and local acquisition clocks, reject external U in peripheral mode. Linked RAM sizes do not measure runtime stack or timing. |
| M5 Campaign | Full campaign/refinement in `REPRODUCE.md` | Frozen values can stay fresh. Separate-switch rescue relies on declared channel/actuator assumptions. Compare solver error at fixed tick separately from changing control timing. Shared-prefix refinement avoids misleading equal boundary peaks. |
| M6 Replay | Released replay or export with `scripts/build_replay.py` | Align all plots on absolute time; inspect truth/observations, requested/leased/applied/actual, invalid gaps and before/after event rows. A466.299590s terminal prefix is not1200s of evidence. Check a raw download hash. |
| M7 Release | Tagged source, evidence ZIP, replay and website case study | Follow a figure to its original CSV/manifest and immutable source revision. Explain software verification versus hardware execution, physical holdout validation and safety certification. Identify the next measurement that could falsify an assumption. |

The [five-minute walkthrough](DEMO.md) connects the key results. The hardware
packet is a future experiment design: NOT_FABRICATED, board NOT_EXECUTED,
physical validation NOT_STARTED. A portfolio interview should use these labels
and acknowledge Codex's implementation/review assistance.
