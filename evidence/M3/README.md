# M3 shared C core on native Windows

The coordinator built the integrated M2+M3 head with CMake4.4.4 and MSVC19.44
using scripts/build_host.ps1. The build used C11 and /W4 /WX. CTest's single
portable_core_codec executable passed303846 independent assertions. The combined
Python unit suite passed95 tests in19.509 s, with actual host integration tests
enabled. The seven Python tank expectations remained passing.

```powershell
./scripts/build_host.ps1 -CMake ./artifacts/tools/cmake/cmake-4.4.4-windows-x86_64/bin/cmake.exe
uv run python -m unittest discover -s tests -v
uv run python scripts/run_suite.py --out artifacts/M3-integrated-baseline
uv run python scripts/verify_host.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/M3-final-identity
```

All seven actual C tank expectations passed. Stuck pump trips at117.9 s then
reaches full: expectation PASS, containment FAILED. Dropout trips at60.3 s even
though the separate switch continues refreshing. Bias trips at123.1 s. Final
nominal wall duration3.706 s includes a separately executed Python comparison;
this is not the isolated M5 performance benchmark. The pre-optimization suite
retains the39.030 s nominal result from Windows sleep polling.

Curated summaries/manifests and actual console/build/CTest logs are tracked here.
The manifests identify the executed C binary/core source hashes and startup
provenance, including dirty=true at revision57bf3c1. Complete raw telemetry and
byte-exact stdin/stdout/stderr/events are in local artifacts/M3-final-identity;
their listed hashes remain in each manifest. CI also retains full exports.
The generic legacy firmware_execution field refers to board execution and stays
NOT_EXECUTED; controller_execution HOST_SIL and controller_implementation
portable_c11_host identify the actual host execution. M5 expands canonical source
coverage to all firmware/build inputs before its campaign.

The first coordinator benchmark invocation used the wrong --executable flag;
argparse rejected it with exit2 (initial-cli-error.txt). The corrected --exe
invocation passed. A later metadata correction captured startup provenance and
replaced the inherited Python-controller label with the executed C identity;
the retained final suite was rerun after that correction. No threshold changed.

Read-only test review accepted CRC literals, independent PI recurrences,
freshness/order/epoch semantics, lease equality and bounded transport failure
probes. Child stdin/output deadlines terminate and reap failures without a Python
fallback. Caller-supplied arbitrary Python hook execution is outside that child
I/O deadline guarantee. Thermal closed-loop containment, MCU execution and
physical validation are not established by these host checks.
