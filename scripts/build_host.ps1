param([string]$BuildDir="artifacts/host-build", [string]$CMake="cmake")
$ErrorActionPreference="Stop"
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskBuild=if([IO.Path]::IsPathRooted($BuildDir)) { $BuildDir } else { Join-Path $taskRoot $BuildDir }
$taskCMake=(Get-Command $CMake -ErrorAction Stop).Source
& $taskCMake -S $taskRoot -B $taskBuild -G "Visual Studio 17 2022" -A x64 -DBUILD_TESTING=ON
if($LASTEXITCODE -ne 0) { throw "CMake configure failed ($LASTEXITCODE)" }
& $taskCMake --build $taskBuild --config Release
if($LASTEXITCODE -ne 0) { throw "CMake build failed ($LASTEXITCODE)" }
$taskCTest=Join-Path (Split-Path $taskCMake -Parent) "ctest.exe"
if(-not(Test-Path -LiteralPath $taskCTest)) { $taskCTest="ctest" }
& $taskCTest --test-dir $taskBuild -C Release --output-on-failure
if($LASTEXITCODE -ne 0) { throw "CTest failed ($LASTEXITCODE)" }
Write-Output (Join-Path $taskBuild "Release/fluid_controller_host.exe")
