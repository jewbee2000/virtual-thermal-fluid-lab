param([string]$BuildDir="artifacts/host-build", [string]$CMake="cmake")
$ErrorActionPreference="Stop"
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskBuild=if([IO.Path]::IsPathRooted($BuildDir)) { $BuildDir } else { Join-Path $taskRoot $BuildDir }
$taskCMake=(Get-Command $CMake -ErrorAction Stop).Source
$taskVswhere=Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio/Installer/vswhere.exe"
if(-not(Test-Path -LiteralPath $taskVswhere)) { throw "Visual Studio Installer/vswhere is required for native MSVC discovery" }
$taskInstallation=(& $taskVswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json | ConvertFrom-Json | Select-Object -First 1)
if(-not $taskInstallation) { throw "Install Visual Studio Build Tools with the C++ tools workload" }
$taskMajor=([version]$taskInstallation.installationVersion).Major
$taskGenerator=switch($taskMajor) { 17 { "Visual Studio 17 2022" }; 18 { "Visual Studio 18 2026" }; default { throw "Unsupported Visual Studio major $taskMajor; update the reviewed generator map" } }
Write-Output "Detected MSVC installation $($taskInstallation.installationPath); generator $taskGenerator"
& $taskCMake -S $taskRoot -B $taskBuild -G $taskGenerator -A x64 -DBUILD_TESTING=ON
if($LASTEXITCODE -ne 0) { throw "CMake configure failed ($LASTEXITCODE)" }
& $taskCMake --build $taskBuild --config Release
if($LASTEXITCODE -ne 0) { throw "CMake build failed ($LASTEXITCODE)" }
$taskCTest=Join-Path (Split-Path $taskCMake -Parent) "ctest.exe"
if(-not(Test-Path -LiteralPath $taskCTest)) { $taskCTest="ctest" }
& $taskCTest --test-dir $taskBuild -C Release --output-on-failure
if($LASTEXITCODE -ne 0) { throw "CTest failed ($LASTEXITCODE)" }
Write-Output (Join-Path $taskBuild "Release/fluid_controller_host.exe")
