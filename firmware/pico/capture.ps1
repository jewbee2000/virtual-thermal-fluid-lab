param(
    [Parameter(Mandatory=$true)][string]$Port,
    [Parameter(Mandatory=$true)][string]$Stimulus,
    [string]$Out="artifacts/board-capture",[int]$Seconds=25
)
$ErrorActionPreference="Stop"
if($Seconds -lt 1 -or $Seconds -gt 300) { throw "Capture duration must be 1..300 seconds" }
$packet=Get-Content -LiteralPath $Stimulus -Raw | ConvertFrom-Json
if($packet.version -ne 1 -or $packet.mode -notin @("link","peripheral")) { throw "Unsupported stimulus" }
$records=@($packet.records)
$previous=-1L
foreach($record in $records) {
    if($record.offset_ms -lt $previous -or $record.offset_ms -lt 0 -or $record.offset_ms -ge $Seconds*1000) { throw "Stimulus offsets must be ordered and within capture" }
    $bytes=[Text.Encoding]::ASCII.GetBytes($record.ascii)
    if($bytes.Length -gt 256 -or -not $record.ascii.EndsWith("`n") -or $record.ascii.Contains("`r")) { throw "Invalid stimulus framing" }
    $previous=$record.offset_ms
}
if(Test-Path -LiteralPath (Join-Path $Out "device-to-host.bin")) { throw "Use a fresh output directory to preserve existing capture evidence" }
New-Item -ItemType Directory -Path $Out -Force | Out-Null
$serial=[IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.DtrEnable=$true
$serial.RtsEnable=$true
$serial.ReadTimeout=100
$serial.WriteTimeout=1000
$raw=[IO.File]::Create((Join-Path $Out "device-to-host.bin"))
$events=[Collections.Generic.List[object]]::new()
$clock=[Diagnostics.Stopwatch]::new()
$index=0
$buffer=[byte[]]::new(256)
$failure=$null
try {
    $serial.Open()
    $clock.Start()
    while($clock.Elapsed.TotalSeconds -lt $Seconds) {
        while($index -lt $records.Count -and $clock.ElapsedMilliseconds -ge $records[$index].offset_ms) {
            $bytes=[Text.Encoding]::ASCII.GetBytes($records[$index].ascii)
            $serial.Write($bytes,0,$bytes.Length)
            $events.Add(@{host_wall_us=[long]($clock.Elapsed.TotalMilliseconds*1000);direction="host-to-device";ascii=$records[$index].ascii})
            $index++
        }
        $count=[Math]::Min($serial.BytesToRead,256)
        if($count -gt 0) {
            $received=$serial.Read($buffer,0,$count)
            $raw.Write($buffer,0,$received)
            $events.Add(@{host_wall_us=[long]($clock.Elapsed.TotalMilliseconds*1000);direction="device-to-host";hex=[Convert]::ToHexString($buffer,0,$received)})
        }
        Start-Sleep -Milliseconds 5
    }
} catch {
    $failure=$_.Exception.Message
} finally {
    $clock.Stop()
    $serial.Close()
    $serial.Dispose()
    $raw.Dispose()
    $events | ForEach-Object { $_ | ConvertTo-Json -Compress } | Set-Content -LiteralPath (Join-Path $Out "events.jsonl") -Encoding utf8
    @{version=1;port=$Port;mode=$packet.mode;epoch=$packet.epoch;duration_wall_us=[long]($clock.Elapsed.TotalMilliseconds*1000);
      stimulus_sha256=(Get-FileHash -LiteralPath $Stimulus -Algorithm SHA256).Hash.ToLowerInvariant();
      raw_sha256=(Get-FileHash -LiteralPath (Join-Path $Out "device-to-host.bin") -Algorithm SHA256).Hash.ToLowerInvariant();
      sent_records=$index;failure=$failure;assessment="UNASSESSED";physical_validation="NOT_STARTED"} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Out "capture.json") -Encoding utf8
}
if($failure) { throw "Capture failed; partial bytes/events retained: $failure" }
Write-Output (Join-Path $Out "capture.json")
