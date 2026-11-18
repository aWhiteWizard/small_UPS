#requires -Version 5.1
<#
.SYNOPSIS
  Flash + verify + reset the minimal firmware through ST-Link/SWD + OpenOCD.
.DESCRIPTION
  Real target required. Prints the exact OpenOCD command, keeps a raw log under
  firmware/build/, and reports chip/program/verify/reset markers. -DryRun only
  prints the command and is safe without hardware.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File firmware/flash.ps1 -DryRun
  powershell -ExecutionPolicy Bypass -File firmware/flash.ps1
#>
[CmdletBinding()]
param(
  [string]$Elf = '',
  [string]$Interface = 'interface/stlink.cfg',
  [string]$Target = 'target/stm32g0x.cfg',
  [string]$Log = '',
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tools = Join-Path $repo '.tools'
$openocd = Join-Path $tools 'openocd\bin\openocd.exe'
$scripts = Join-Path $tools 'openocd\openocd\scripts'
$build = Join-Path $PSScriptRoot 'build'

if ([string]::IsNullOrWhiteSpace($Elf)) { $Elf = Join-Path $build 'psu_minimal.elf' }
if (-not (Test-Path $Elf)) { throw "firmware not found: $Elf (run firmware/build.ps1 first)" }
if (-not (Test-Path $openocd)) { throw "openocd not found: $openocd (run firmware/tools/bootstrap.ps1 first)" }
foreach ($cfg in @((Join-Path $scripts $Interface), (Join-Path $scripts $Target))) {
  if (-not (Test-Path $cfg)) { throw "openocd config not found: $cfg" }
}
if ([string]::IsNullOrWhiteSpace($Log)) {
  if (-not (Test-Path $build)) { New-Item -ItemType Directory -Force -Path $build | Out-Null }
  $Log = Join-Path $build ("flash-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")
}
$Log = [IO.Path]::GetFullPath($Log)

$tcl = "program {$Elf} verify reset exit"
$display = '"{0}" -s "{1}" -f {2} -f {3} -c "{4}"' -f $openocd, $scripts, $Interface, $Target, $tcl
Write-Output "FLASH-TARGET: $Target"
Write-Output "FLASH-ELF:    $Elf"
Write-Output "FLASH-CMD:    $display"
if ($DryRun) { Write-Output 'FLASH: DRYRUN (not executed)'; exit 0 }

# Keep native stderr from becoming a terminating NativeCommandError on PS 5.1.
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  $out = & $openocd -s $scripts -f $Interface -f $Target -c $tcl 2>&1
  $code = $LASTEXITCODE
} finally {
  $ErrorActionPreference = $previous
}

$lines = @($out | ForEach-Object { ([string]$_).TrimEnd() })
$text = ($lines -join "`r`n")
$enc = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($Log, $text + "`r`n", $enc)
$lines | ForEach-Object { Write-Output $_ }

$probe = @($lines | Where-Object {
  $_ -match 'STLINK|ST-Link|Target voltage|stm32g0x\.cfg'
}) -join ' | '
if (-not [string]::IsNullOrWhiteSpace($probe)) { Write-Output "FLASH-PROBE: $probe" }

$programmed = ($text -match '\*\* Programming Finished \*\*')
$verified = ($text -match '\*\* Verified OK \*\*')
$reset = ($text -match '\*\* Resetting Target \*\*|Resetting')
$noProbe = ($text -match 'Error: open failed|OpenOCD init failed|no device found|unable to find a matching')

if ($code -eq 0 -and $programmed -and $verified) {
  $resetText = if ($reset) { 'reset issued' } else { 'reset marker missing' }
  Write-Output "FLASH: PASS (programmed + verified + $resetText)"
  Write-Output "FLASH-LOG: $Log"
  exit 0
}

if ($noProbe) {
  Write-Output 'FLASH: FAIL (no ST-Link probe or target board detected)'
} else {
  Write-Output "FLASH: FAIL (openocd exit $code; program=$programmed verify=$verified)"
}
Write-Output "FLASH-LOG: $Log"
exit $(if ($code -ne 0) { $code } else { 1 })
