#requires -Version 5.1
<#
.SYNOPSIS
  Minimal serial console: list COM ports, read output with timestamps, send one
  line, or self-test the formatter without hardware.
.DESCRIPTION
  Uses built-in System.IO.Ports (Windows PowerShell 5.1); no pip/pyserial.
  Defaults: 115200 8N1. Logs under firmware/build/serial-<time>.log (git ignored).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File firmware/tools/serial.ps1 -List
  powershell -ExecutionPolicy Bypass -File firmware/tools/serial.ps1 -Port COM3 -Seconds 10
  powershell -ExecutionPolicy Bypass -File firmware/tools/serial.ps1 -Port COM3 -Send "ping"
  powershell -ExecutionPolicy Bypass -File firmware/tools/serial.ps1 -SelfTest
#>
[CmdletBinding()]
param(
  [switch]$List,
  [switch]$SelfTest,
  [string]$Port = '',
  [int]$Baud = 115200,
  [int]$Seconds = 5,
  [string]$Send = '',
  [string]$Log = ''
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$build = Join-Path $repo 'firmware\build'
if ([string]::IsNullOrWhiteSpace($Log)) {
  if (-not (Test-Path $build)) { New-Item -ItemType Directory -Force -Path $build | Out-Null }
  $Log = Join-Path $build ("serial-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")
}
$Log = [IO.Path]::GetFullPath($Log)
$enc = New-Object System.Text.UTF8Encoding($false)

function Format-Line {
  param([string]$Text, [datetime]$At)
  return '[' + $At.ToString('HH:mm:ss.fff') + '] ' + $Text.TrimEnd("`r")
}

if ($List) {
  $names = @([System.IO.Ports.SerialPort]::GetPortNames())
  $names | ForEach-Object { Write-Output $_ }
  Write-Output ("SERIAL-LIST: " + $names.Count + " port(s)")
  exit 0
}

if ($SelfTest) {
  $at = [datetime]'2026-11-18T12:00:00'
  $out = @('PSU minimal boot', 'flash=1544 B') | ForEach-Object { Format-Line $_ $at }
  $out | ForEach-Object { Write-Output $_ }
  if ($out.Count -eq 2 -and $out[0] -match '^\[12:00:00\.000\] PSU minimal boot$') {
    Write-Output 'SERIAL-SELFTEST: PASS (formatter/timestamp, 2 lines)'
    exit 0
  }
  Write-Output 'SERIAL-SELFTEST: FAIL'
  exit 1
}

if ([string]::IsNullOrWhiteSpace($Port)) {
  Write-Output 'SERIAL: no -Port given. Use -List, -SelfTest, or -Port COMx.'
  exit 2
}
$available = @([System.IO.Ports.SerialPort]::GetPortNames())
if ($available -notcontains $Port) {
  $availableText = if ($available.Count) { $available -join ',' } else { 'none' }
  Write-Output ("SERIAL: port {0} not present (available: {1})" -f $Port, $availableText)
  exit 2
}
if ($Seconds -lt 1) { throw "-Seconds must be >= 1" }

$sp = New-Object System.IO.Ports.SerialPort $Port, $Baud, 'None', 8, 'One'
$sp.ReadTimeout = 500
$sp.WriteTimeout = 1000
$log = New-Object System.Text.StringBuilder
try {
  $sp.Open()
  $line = "SERIAL-OPEN: $Port $Baud 8N1"
  Write-Output $line
  [void]$log.AppendLine($line)
  if (-not [string]::IsNullOrEmpty($Send)) {
    $sp.WriteLine($Send)
    $line = Format-Line ("TX " + $Send) (Get-Date)
    Write-Output $line
    [void]$log.AppendLine($line)
  }
  $deadline = (Get-Date).AddSeconds($Seconds)
  $bytes = 0
  $lines = 0
  while ((Get-Date) -lt $deadline) {
    $chunk = ''
    try { $chunk = $sp.ReadExisting() } catch { $chunk = '' }
    if ([string]::IsNullOrEmpty($chunk)) {
      Start-Sleep -Milliseconds 50
      continue
    }
    $bytes += $chunk.Length
    foreach ($part in ($chunk -split "`r?`n")) {
      if ($part -ne '') {
        $line = Format-Line $part (Get-Date)
        Write-Output $line
        [void]$log.AppendLine($line)
        $lines++
      }
    }
  }
  $line = "SERIAL: $bytes byte(s), $lines line(s) in ${Seconds}s"
  Write-Output $line
  [void]$log.AppendLine($line)
  [IO.File]::WriteAllText($Log, $log.ToString(), $enc)
  Write-Output "SERIAL-LOG: $Log"
  exit 0
} catch {
  Write-Output ("SERIAL: FAIL ({0})" -f $_.Exception.Message)
  exit 1
} finally {
  if ($null -ne $sp -and $sp.IsOpen) { $sp.Close() }
  $sp.Dispose()
}
