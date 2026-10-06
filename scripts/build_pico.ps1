param(
    [string]$BuildDir="artifacts/pico-build",
    [Parameter(Mandatory=$true)][string]$SdkPath,
    [Parameter(Mandatory=$true)][string]$ToolchainPath,
    [Parameter(Mandatory=$true)][string]$Picotool,
    [string]$CMake="cmake", [string]$Ninja="ninja"
)
$ErrorActionPreference="Stop"
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskBuild=if([IO.Path]::IsPathRooted($BuildDir)) { $BuildDir } else { Join-Path $taskRoot $BuildDir }
$taskSdk=(Resolve-Path -LiteralPath $SdkPath).Path
$taskArm=(Resolve-Path -LiteralPath $ToolchainPath).Path
$taskCMake=(Get-Command $CMake -ErrorAction Stop).Source
$taskNinja=(Get-Command $Ninja -ErrorAction Stop).Source
$taskPicotool=(Get-Command $Picotool -ErrorAction Stop).Source
$taskGcc=Join-Path $taskArm "bin/arm-none-eabi-gcc.exe"
$taskSize=Join-Path $taskArm "bin/arm-none-eabi-size.exe"
$taskNm=Join-Path $taskArm "bin/arm-none-eabi-nm.exe"
$taskPython=Join-Path $taskRoot ".venv/Scripts/python.exe"
if(-not(Test-Path -LiteralPath $taskPython)) { throw "Run uv sync --locked before the SDK build" }
$taskSdkRevision=(& git -C $taskSdk rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0 -or $taskSdkRevision -ne "079c6f39023649b154152db30f1d781e884879bc") { throw "Expected pinned Pico SDK2.3.1 revision" }
$taskTinyUsbRevision=(& git -C (Join-Path $taskSdk "lib/tinyusb") rev-parse HEAD).Trim()
if($LASTEXITCODE -ne 0 -or $taskTinyUsbRevision -ne "86ad6e56c1700e85f1c5678607a762cfe3aa2f47") { throw "Expected pinned TinyUSB submodule revision" }
$taskCompilerVersion=(& $taskGcc --version | Out-String).Trim()
if($LASTEXITCODE -ne 0 -or $taskCompilerVersion -notmatch "15\.2\.Rel1") { throw "Expected Arm GNU Toolchain15.2.Rel1" }
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
& $taskCMake -S (Join-Path $taskRoot "firmware/pico") -B $taskBuild -G Ninja "-DCMAKE_MAKE_PROGRAM=$taskNinja" "-DPICO_SDK_PATH=$taskSdk" "-DPICO_TOOLCHAIN_PATH=$taskArm" "-DPython3_EXECUTABLE=$taskPython" -DPICO_BOARD=pico -DPICO_NO_PICOTOOL=ON -DCMAKE_BUILD_TYPE=Release 2>&1 | Tee-Object -FilePath (Join-Path $taskBuild "configure.log")
if($LASTEXITCODE -ne 0) { throw "Pico CMake configuration failed ($LASTEXITCODE)" }
& $taskCMake --build $taskBuild --parallel 4 2>&1 | Tee-Object -FilePath (Join-Path $taskBuild "build.log")
if($LASTEXITCODE -ne 0) { throw "Pico cross-build failed ($LASTEXITCODE)" }
$taskOutputs=@()
foreach($taskTarget in @("fluid_controller_pico_link","fluid_controller_pico_peripheral")) {
    $taskElf=Join-Path $taskBuild "$taskTarget.elf"
    $taskUf2=Join-Path $taskBuild "$taskTarget.uf2"
    & $taskPicotool uf2 convert $taskElf $taskUf2 --family rp2040 2>&1 | Tee-Object -FilePath (Join-Path $taskBuild "$taskTarget.uf2.log")
    if($LASTEXITCODE -ne 0) { throw "UF2 conversion failed ($LASTEXITCODE)" }
    $taskSizeText=(& $taskSize --format=berkeley $taskElf | Out-String).Trim()
    if($LASTEXITCODE -ne 0) { throw "ELF size inspection failed" }
    $taskSizeText | Set-Content -LiteralPath (Join-Path $taskBuild "$taskTarget.size.txt") -Encoding utf8
    $taskRow=($taskSizeText -split "`r?`n")[-1].Trim() -split "\s+"
    $taskText=[long]$taskRow[0]; $taskData=[long]$taskRow[1]; $taskBss=[long]$taskRow[2]
    $taskSectionsText=(& $taskSize --format=sysv $taskElf | Out-String).Trim()
    if($LASTEXITCODE -ne 0) { throw "ELF section inspection failed" }
    $taskSectionsText | Set-Content -LiteralPath (Join-Path $taskBuild "$taskTarget.sections.txt") -Encoding utf8
    $taskSections=@()
    $taskMainRam=0L
    $taskScratch=0L
    foreach($taskSectionLine in ($taskSectionsText -split "`r?`n")) {
        if($taskSectionLine -match '^\s*(\.[a-zA-Z0-9_]+)\s+(\d+)\s+(\d+)\s*$') {
            $taskSectionName=$Matches[1]; $taskSectionBytes=[long]$Matches[2]; $taskSectionAddress=[long]$Matches[3]
            if($taskSectionAddress -ge 0x10000000 -and $taskSectionAddress -lt 0x20042000) {
                $taskSections+=@{name=$taskSectionName;size_bytes=$taskSectionBytes;vma=$taskSectionAddress}
            }
            if($taskSectionAddress -ge 0x20000000 -and $taskSectionAddress -lt 0x20040000) { $taskMainRam+=$taskSectionBytes }
            if($taskSectionAddress -ge 0x20040000 -and $taskSectionAddress -lt 0x20042000) { $taskScratch+=$taskSectionBytes }
        }
    }
    & $taskNm --defined-only $taskElf 2>&1 | Set-Content -LiteralPath (Join-Path $taskBuild "$taskTarget.symbols.txt") -Encoding utf8
    if($LASTEXITCODE -ne 0) { throw "ELF symbol inspection failed" }
    $taskFiles=@{}
    foreach($taskSuffix in @("elf","elf.map","bin","uf2")) {
        $taskFile=Join-Path $taskBuild "$taskTarget.$taskSuffix"
        if(-not(Test-Path -LiteralPath $taskFile)) { throw "Missing expected artifact $taskFile" }
        $taskFiles["$taskTarget.$taskSuffix"]=(Get-FileHash -LiteralPath $taskFile -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $taskOutputs+=@{target=$taskTarget;mode=$(if($taskTarget -match "peripheral") { 2 } else { 1 });
        text_bytes=$taskText;data_bytes=$taskData;bss_bytes=$taskBss;
        linked_text_plus_data_bytes=$taskText+$taskData;berkeley_data_plus_bss_bytes=$taskData+$taskBss;
        main_ram_allocated_sections_bytes=$taskMainRam;scratch_ram_allocated_sections_bytes=$taskScratch;allocated_sections=$taskSections;
        flash_image_bin_bytes=(Get-Item -LiteralPath (Join-Path $taskBuild "$taskTarget.bin")).Length;
        memory_meaning="RAM VMA sections include read-only RAM code/data and reserved heap/stack; Berkeley text/data classification differs. Stack/runtime peak and board measurements not established";
        artifact_sha256=$taskFiles}
}
$taskSources=@{}
foreach($taskFolder in @("firmware/core","firmware/pico")) {
    Get-ChildItem -LiteralPath (Join-Path $taskRoot $taskFolder) -File -Recurse | ForEach-Object {
        $taskRelative=[IO.Path]::GetRelativePath($taskRoot,$_.FullName).Replace('\','/')
        $taskSources[$taskRelative]=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$taskReport=@{version=1;board="pico/RP2040";sdk_version="2.3.1";sdk_revision=$taskSdkRevision;tinyusb_revision=$taskTinyUsbRevision;
    compiler=$taskCompilerVersion;cmake=((& $taskCMake --version | Out-String).Trim());ninja=((& $taskNinja --version | Out-String).Trim());
    picotool=((& $taskPicotool version | Out-String).Trim());source_revision=((& git -C $taskRoot rev-parse HEAD).Trim());
    sdk_generation_python=((& $taskPython --version | Out-String).Trim());
    tinyusb_usbd_sha256=(Get-FileHash -LiteralPath (Join-Path $taskSdk "lib/tinyusb/src/device/usbd.c") -Algorithm SHA256).Hash.ToLowerInvariant();
    bounded_usb_wrapper_sha256=(Get-FileHash -LiteralPath (Join-Path $taskRoot "firmware/pico/usb_task.c") -Algorithm SHA256).Hash.ToLowerInvariant();
    usb_queue_receives_per_pass=8;usb_task_timeout_ms=0;rx_bytes_per_pass=256;tx_frame_slots=8;
    source_dirty=([bool](& git -C $taskRoot status --porcelain));source_sha256=$taskSources;
    supported_device_tick_us=@{minimum=1000;maximum=1000000;default=100000};watchdog_ms=1500;
    adc_timeout_us=100;adc_poll_cap=10000;adc_conversion_error_quality="invalid";
    outputs=$taskOutputs;board_execution="NOT_EXECUTED";physical_validation="NOT_STARTED"}
$taskReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskBuild "build-evidence.json") -Encoding utf8
Write-Output (Join-Path $taskBuild "build-evidence.json")
