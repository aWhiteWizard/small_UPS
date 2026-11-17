#requires -Version 5.1
<#
.SYNOPSIS
  Flash the T-0002 minimal firmware through ST-Link + OpenOCD (real target required).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File firmware/flash.ps1
  powershell -ExecutionPolicy Bypass -File firmware/flash.ps1 -Elf firmware/build/psu_minimal.elf
#>
[CmdletBinding()]
param(
  [string]$Elf = '',
  [string]$Interface = 'interface/stlink.cfg',
  [string]$Target = 'target/stm32g0x.cfg'
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tools = Join-Path $repo '.tools'
$openocd = Join-Path $tools 'openocd\bin\openocd.exe'
$scripts = Join-Path $tools 'openocd\openocd\scripts'

if ([string]::IsNullOrWhiteSpace($Elf)) { $Elf = Join-Path $PSScriptRoot 'build\psu_minimal.elf' }

if (-not (Test-Path $Elf)) { throw "firmware not found: $Elf (run firmware/build.ps1 first)" }
if (-not (Test-Path $openocd)) { throw "openocd not found: $openocd (run firmware/tools/bootstrap.ps1 first)" }

& $openocd -s $scripts -f $Interface -f $Target `
    -c "program `"$Elf`" verify reset exit"
exit $LASTEXITCODE
