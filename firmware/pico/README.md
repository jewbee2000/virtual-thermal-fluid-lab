# Pico firmware and hardware capture packet

Two RP2040/Pico USB CDC images compile the exact `firmware/core/fl_core.c` and `fl_protocol.c` used by host SIL. `fluid_controller_pico_link.uf2` accepts synthetic observations for tank or thermal profiles. `fluid_controller_pico_peripheral.uf2` uses ADC/GPIO for the tank profile only and rejects external observation replacement. Both boot DISARMED. GPIO drives only the onboard indicator; there are no pump, valve, or heater outputs.

## Build and native checks

Run from repository root after `uv sync --locked`. Supply your pinned tool locations; tools are not fetched by this build.

```powershell
./scripts/build_pico.ps1 -SdkPath <pico-sdk-2.3.1> -ToolchainPath <arm-15.2.rel1> -Picotool <picotool.exe> -CMake <cmake.exe> -Ninja <ninja.exe>
cmake -S firmware/pico/tests -B artifacts/device-test-build
cmake --build artifacts/device-test-build --config Release
ctest --test-dir artifacts/device-test-build -C Release --output-on-failure
```

The build records ELF/map/bin/UF2 hashes, linked section sizes, source hashes, compiler/SDK/TinyUSB versions and explicit `NOT_EXECUTED` board status in `artifacts/pico-build/build-evidence.json`. Static RAM and linked flash sizes do not establish runtime stack peaks or board timing. Project C files build with warnings as errors. Vendor SDK sources use SDK defaults; the bounded USB wrapper also builds with project warning flags.

The timer ISR increments a saturating due counter. Main-loop work executes once at actual 64-bit device time, counts skipped due ticks, and integrates PI with actual elapsed time; the first step uses configured dt. Host SIL retains its exact integer virtual-time schedule. Device tick support is 1,000..1,000,000 us, default 100,000 us. The watchdog is 1,500 ms and is fed only after completed scheduled control/acquisition or unconfigured housekeeping. No board reset or latency result has been measured.

Each main-loop pass bounds RX at 256 bytes and TinyUSB queue receives at eight. `usb_task.c` routes the pinned vendor receive site through a budget; CMake rejects changes to the reviewed vendor source hash/site. This addresses a queue that can otherwise be replenished forever by USB IRQs. The independent native stub continuously replenishes the queue and verifies that each pass returns. TX stages whole frames in eight fixed slots, prioritizing B/Q/R/N ahead of X; a full queue drops whole frames and records the count. These structural bounds do not establish a measured worst-case execution time.

ADC conversion waits at most 100 us or 10,000 polls, rejects conversion ERR and invalid raw values, and records invalid quality without refreshing last-good age. `X` retains synthetic source clock/time while controller freshness uses local receipt time. `U` is a separately sequenced operation/heat intent with a local receipt lease; expiry at equality inhibits ARM/RESET and trips RUNNING with reason 7 after higher-priority guards. `S` never advances MCU time. Disconnect/new epoch clears operations and requires configuration and a new ARM. Held ARM/RESET boot levels initialize edge history.

## Indicator-only peripheral fixture

| Pico signal | Assignment | Pedigree/meaning |
| --- | --- | --- |
| GP26 / ADC0 | potentiometer wiper | Assumed 0..3.3 V maps to 0..1 m illustrative tank level; no measured calibration |
| GP14 | separate trip, active HIGH, pull-up | Ground jumper clears trip; disconnected input trips |
| GP15 | ARM, active LOW, pull-up | Momentary button to ground; edge triggered |
| GP16 | RESET, active LOW, pull-up | Momentary button to ground; RESET has priority |
| GP25 | onboard LED | off DISARMED, on RUNNING, 2 Hz blink TRIPPED |

Use Pico 3V3 OUT and GND for the potentiometer ends; keep ADC input within the board's documented voltage limits. Review the [Pico pinout](https://www.raspberrypi.com/documentation/microcontrollers/pico-series.html) before wiring. This fixture exercises educational I/O and controller state; it does not measure a thermal/fluid plant.

## Human capture steps (not yet executed)

1. Photograph the board identity, wiring and indicator-only fixture. Hold BOOTSEL while connecting USB, then copy the chosen UF2 to RPI-RP2. Record its SHA256 and the Windows COM port. Board flashing/wiring requires a human.
2. Use PowerShell 7 for the capture script. Generate a stimulus for a fresh boot with epoch 1; for a reconnect without reboot choose a half-range-newer nonzero epoch.

```powershell
uv run python firmware/pico/make_stimulus.py --mode link --epoch 1 --out artifacts/hardware-stimulus.json
./firmware/pico/capture.ps1 -Port COM4 -Stimulus artifacts/hardware-stimulus.json -Out artifacts/board-link-capture -Seconds 25
```

The link stimulus sends tank H/C, level 0.49 m/trip clear, one ARM then refreshed HOLD intents, and continues observations after intents stop. Inspect raw Q/R/X/N: expect initial DISARMED, explicit ARM, local-age diagnostics and eventual intent-expiry trip. Actual device times and trip latency must be computed from the captured records; generated stimulus files alone prove nothing about a board. Capture preserves raw bytes, host wall receipt events and hashes, with `UNASSESSED` status.

3. For the peripheral image generate `--mode peripheral`; the packet sends only H/C. Set the potentiometer near half scale and clear GP14 by grounding it. Verify held ARM during boot does not arm; release and press ARM. Hold each button state for at least two configured ticks so the sampled edge can be acquired. Remove the GP14 jumper, restore it, press RESET, then separately press ARM. Record physical actions with host timestamps and retain video/photos alongside the raw capture. LED state is an indicator, not physical containment.
4. Repeat cable/DTR disconnect and reconnect with a newer epoch: verify DISARMED and new ARM required. Preserve malformed/incomplete serial stimulus probes, queue/load timing and watchdog fault-injection evidence separately when actually performed. Watchdog reset testing requires a reviewed debug/fault fixture and remains unexecuted; do not infer it from a healthy running image.

The COM path has not been executed on a board. Capture scripts/stimuli can be parsed and generated without hardware; actual USB enumeration, ADC/GPIO acquisition, overrun behavior, watchdog reset and trip latency remain `NOT_EXECUTED`. Physical validation remains `NOT_STARTED`. Vendor SDK/TinyUSB notices are retained in `THIRD_PARTY_LICENSES.txt`; release packaging must also audit the linked toolchain/runtime notices.
