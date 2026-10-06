# M4 Pico target checks

Both USB link and peripheral images cross-built natively on Windows with Pico
SDK2.3.1, pinned TinyUSB, ARM15.2.Rel1, CMake4.4.4, Ninja1.13.2 and picotool2.3.1.
The same fl_core.c/fl_protocol.c production files are compiled in the host and
Pico targets. Link accepts declared synthetic channels; peripheral is tank-only
ADC/GPIO with LED indication. No pump/heater/valve physical output exists.

The clean isolated writer committed874674fa37e27b55e441c935dc883b3272cd66e1;
root integrated it at09f5858. Original writer-build-evidence.json is retained
unchanged. The coordinator's first raw-source comparison found CRLF/LF differences
in three HAL test/stub files (source-byte-differences.json); production firmware
bytes matched. Their LF-normalized contents were identical. The coordinator then
actually rebuilt both Pico targets from integrated LF files and verified all25
firmware-file hashes and eight output hashes against final build-evidence.json.
That final manifest accurately says source_dirty=true because unrelated M5 Python
implementation was in progress. It does not imply a clean root checkout.

```powershell
./scripts/build_pico.ps1 -BuildDir artifacts/M4-integrated-pico -SdkPath ./artifacts/tools/pico-sdk-2.3.1 -ToolchainPath ./artifacts/tools/arm-15.2.rel1 -Picotool ./artifacts/tools/picotool-build/picotool.exe -CMake ./artifacts/tools/cmake/cmake-4.4.4-windows-x86_64/bin/cmake.exe -Ninja ./artifacts/tools/ninja/ninja.exe
```

Actual linked FLASH is41,692 bytes for link and41,828 for peripheral. Each allocates
22,716 bytes main RAM and2,048 bytes scratch stack. Section/address reports explain
the Berkeley classification difference; these are linked allocations including
reserved heap/stack, not measured runtime stack or worst-case execution time.
ELF/map/bin/UF2 hashes and tool/source identities are in both build manifests.
Actual binaries/maps remain in artifacts/M4-integrated-pico and CI artifacts.

The original failures are preserved: CRC integer promotion under strict GCC and
-Wpedantic applied to SDK IRQ Thumb pointer conversions. Explicit unsigned CRC
arithmetic preserves goldens; warnings-as-errors now apply to project sources,
while vendor SDK sources use supported defaults. HAL review also reproduced ADC
ERR acceptance and a replenishable USB task queue. The repair rejects ADC ERR
and bounds pinned vendor receive processing to eight queue receives per pass,
with checked source hash and retained wrapper hash. SDK checkout remains unchanged.

Actual independent native tests passed197 device-policy checks,27 HAL checks and
1,000 continuously replenished USB queue passes. The clean isolated Python suite
passed98 tests in19.301s; both seven-case Python and C tank suites passed expected
outcomes, including FAILED containment/full for the stuck pump. The integrated
root MSVC host CTest and all three standalone device CTests also passed.
Logs are retained here.504 generated stimulus frames were decoded and capture.ps1
was parsed without opening a COM port. Those checks prove no board execution.

Device policy uses actual D elapsed time/local receipt ages and separate U intent
lease while host V scheduling remains exact. Source clocks stay explicit in X;
N records counters and freshness. Explicit ARM/reset, epoch changes and held-button
startup policy are documented in firmware/pico/README.md and MCU_CONTRACT.md.

Board execution is NOT_EXECUTED; physical validation NOT_STARTED. Timer/ADC/GPIO/
USB/watchdog source paths and native stubs do not establish measured hardware
latency, overruns or watchdog resets. H1 capture instructions are runnable when a
human supplies the board. M4 CI and final runtime-license packaging audit remain
pending until their actual records are added.

The first PR CI run37439468227 passed Windows/Linux full verification, native
device tests and ASan/UBSan, then rejected TinyUSB usbd.c at Linux configure.
The pinned immutable Git blob uses LF, SHA256
f15a6da11eca127b792bd04d3270e6ea3901b0a29c24f462d5687d63da1df6cb;
Windows checkout uses CRLF, SHA256
d198d57e626db62c2ac42fe9c26c815403984d92cedecd5414a9b38d3836a95d.
An actual byte comparison proved CRLF-to-LF yields the exact pinned Git blob.
The narrow repair enumerates only those two known representations and still
rejects every other hash. Source revision, receive-site count, queue budget and
warning checks are unchanged. The original CI failure and actual successful
native configure are retained; repaired Linux cross-build must run before M4
is marked complete. This revises a platform-byte pin, not a behavior threshold.
