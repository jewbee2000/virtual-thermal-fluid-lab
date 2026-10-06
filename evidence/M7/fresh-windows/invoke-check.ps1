param([Parameter(Mandatory=$true)][string]$Name,
      [Parameter(Mandatory=$true)][string]$Program,
      [string[]]$Arguments=@())
$ErrorActionPreference="Stop"
$checkRoot=(Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$checkRevision=(& git -C $checkRoot rev-parse HEAD).Trim()
$checkBefore=@(& git -C $checkRoot status --porcelain=v1 --untracked-files=all)
$checkLockBefore=(Get-FileHash -LiteralPath (Join-Path $checkRoot "uv.lock") -Algorithm SHA256).Hash.ToLowerInvariant()
if($checkRevision -ne "cc5a6feae95dc5888bf3041bc9dc3306dba667ba" -or $checkBefore.Count -ne 0) { throw "Frozen clean checkout required" }
$checkStdout=Join-Path $PSScriptRoot "$Name.stdout.txt"
$checkStderr=Join-Path $PSScriptRoot "$Name.stderr.txt"
if(Test-Path -LiteralPath (Join-Path $PSScriptRoot "$Name.json")) { throw "Do not overwrite an executed check" }
$checkStart=[DateTime]::UtcNow.ToString("o")
$checkTimer=[Diagnostics.Stopwatch]::StartNew()
$checkExit=127
$checkError=$null
$checkProcess=[Diagnostics.Process]::new()
$checkProcess.StartInfo.FileName=$Program
$checkProcess.StartInfo.WorkingDirectory=$checkRoot
$checkProcess.StartInfo.UseShellExecute=$false
$checkProcess.StartInfo.CreateNoWindow=$true
$checkProcess.StartInfo.RedirectStandardOutput=$true
$checkProcess.StartInfo.RedirectStandardError=$true
foreach($checkArgument in $Arguments) { $checkProcess.StartInfo.ArgumentList.Add($checkArgument) }
$checkOut=[IO.FileStream]::new($checkStdout,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::ReadWrite,1,[IO.FileOptions]::Asynchronous)
$checkErr=[IO.FileStream]::new($checkStderr,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::ReadWrite,1,[IO.FileOptions]::Asynchronous)
try {
    if(-not $checkProcess.Start()) { throw "Process did not start" }
    $checkOutTask=$checkProcess.StandardOutput.BaseStream.CopyToAsync($checkOut)
    $checkErrTask=$checkProcess.StandardError.BaseStream.CopyToAsync($checkErr)
    $checkProcess.WaitForExit()
    [Threading.Tasks.Task]::WaitAll(@($checkOutTask,$checkErrTask))
    $checkExit=$checkProcess.ExitCode
} catch {
    $checkError=$_.Exception.Message
} finally {
    $checkOut.Dispose(); $checkErr.Dispose(); $checkProcess.Dispose()
    $checkTimer.Stop()
}
$checkAfter=@(& git -C $checkRoot status --porcelain=v1 --untracked-files=all)
$checkLockAfter=(Get-FileHash -LiteralPath (Join-Path $checkRoot "uv.lock") -Algorithm SHA256).Hash.ToLowerInvariant()
$checkRecord=[ordered]@{name=$Name;program=$Program;arguments=$Arguments;working_directory=$checkRoot;
    started_utc=$checkStart;ended_utc=[DateTime]::UtcNow.ToString("o");wall_elapsed_s=$checkTimer.Elapsed.TotalSeconds;
    exit_code=$checkExit;invocation_error=$checkError;git_revision=$checkRevision;git_dirty_before=$checkBefore.Count -ne 0;
    git_dirty_after=$checkAfter.Count -ne 0;git_status_after=$checkAfter;lock_sha256_before=$checkLockBefore;
    lock_sha256_after=$checkLockAfter;stdout=$checkStdout;stderr=$checkStderr}
$checkRecord | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $PSScriptRoot "$Name.json") -Encoding utf8
Write-Output "$Name exit=$checkExit wall=$($checkTimer.Elapsed.TotalSeconds)s"
if($checkLockAfter -ne $checkLockBefore -or $checkAfter.Count -ne 0) { throw "Frozen checkout or lock changed" }
exit $checkExit
