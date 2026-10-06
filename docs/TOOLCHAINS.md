# Native toolchain provisioning record

Windows development stays native. Scientific lock remains unchanged. Portable
build tools are kept in ignored artifacts/tools, not redistributed in the source
release. Setup automation must verify these pins before using downloads.

| Tool | Pin/source | Verification/status |
| --- | --- | --- |
| PowerShell | 7.6.5 executed | PowerShell7 required for the native build scripts; Windows PowerShell5.1 is not the tested shell |
| uv | 0.12.19 official installer | Installer SHA256 f44cf87798d181653f4c160ee28df6353ccf0ac4efea16c9a32abff694c8f45b; installed and executed |
| Python | 3.12.2 already installed | Actual M0 interpreter; compatible Python3.12 required |
| Git | 2.55.0.windows.5 | Existing native tool |
| GitHub CLI | 2.102.0 | Existing C:\Program Files\GitHub CLI\gh.exe; browser login jewbee2000 verified; private repo creation/push executed |
| MSVC Build Tools | winget Microsoft.VisualStudio.2022.BuildTools 17.14.41 | VCTools/includeRecommended install exit0; vswhere finds2022 BuildTools; x64 cl19.44.35229; M3/M4 host and native tests built |
| CMake | 4.4.4 Windows x64 ZIP | SHA256 bace36e94b31c68ab6fa295f26dfa11219e0701cf7c94b0284a7d1cb13dac536; downloaded/verified/extracted; --version executed |
| Ninja | 1.13.2 Windows ZIP | SHA256 07fc8261b42b20e71d1720b39068c2e14ffcee6396b76fb7a795fb460b78dc65; downloaded/verified/extracted; --version executed |
| ARM GCC | 15.2.rel1 Windows x64 ZIP | SHA256 7936cac895611023ffb22a64b8e426098c7104cb689778c1894572ca840b9ece verified; gcc15.2.1; both M4 Pico modes cross-built |
| Pico SDK | 2.3.1 | Actual clone revision079c6f39023649b154152db30f1d781e884879bc; both M4 targets built |
| TinyUSB | SDK-pinned submodule | Only lib/tinyusb at86ad6e56c1700e85f1c5678607a762cfe3aa2f47; M4 USB targets built with hash-checked bounded receive wrapper |
| picotool | 2.3.1 source | Revision2041936441b48a3cc53ae3da9e805229fe8f4e18; native MSVC Release build exit0; version executed; USB loading/signing disabled |

Official portable sources:
[CMake](https://github.com/Kitware/CMake/releases/tag/v4.4.4),
[Ninja](https://github.com/ninja-build/ninja/releases/tag/v1.13.2),
[Arm package](https://developer.arm.com/-/media/Files/downloads/gnu/15.2.rel1/binrel/arm-gnu-toolchain-15.2.rel1-mingw-w64-x86_64-arm-none-eabi.zip),
[Arm instructions](https://learn.arm.com/install-guides/gcc/arm-gnu/),
[SDK](https://github.com/raspberrypi/pico-sdk/releases/tag/2.3.1).
The ARM pin is accessible and checksum-verified when provisioning completes; it
is not called latest. Tool versions do not prove target execution.

MSVC command actually launched:

```powershell
winget install --id Microsoft.VisualStudio.2022.BuildTools --exact --silent --accept-package-agreements --accept-source-agreements --override '--wait --quiet --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended'
```

Detect installed compiler using vswhere and developer environment rather than
assuming a Visual Studio path/generator. Keep host and MCU build trees separate.
Pico UART/ADC/GPIO/timer/watchdog need no SDK USB/network submodules. TinyUSB was
explicitly provisioned at the SDK's recorded commit for a possible USB serial
target. Network, Bluetooth and mbedTLS submodules remain uninitialized.
picotool was built with PICOTOOL_NO_LIBUSB=1 and default precompiled helper assets;
its UF2 conversion actually produced both M4 firmware images. No board flash or
execution has occurred. Original tool-source MSVC warnings remain in ignored
artifacts/tools/picotool-build.log; this provisioning success is not a firmware
test. Pin SDK/source license notices in ATTRIBUTION.md.

M4 CI provisioning pins Linux ARM15.2.rel1 archive SHA256
597893282ac8c6ab1a4073977f2362990184599643b4c5ee34870a8215783a16,
read from Arm's official .sha256asc; the actual CI download must still verify it.
CMake4.4.4 Linux archive SHA256 is
e5bb807f7728cb60cd8b27ebc97a2edb469b68655f21e844a600c3575b76f5bb,
checked against the official GitHub release asset digest. CI outcome remains in
tasks/evidence rather than inferred from these provisioning instructions.
