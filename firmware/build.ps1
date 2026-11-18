#requires -Version 5.1
<#
.SYNOPSIS
  Build the minimal firmware (T-0022; inherited from T-0002). Run bootstrap first.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File firmware/build.ps1
  powershell -ExecutionPolicy Bypass -File firmware/build.ps1 -Clean
#>
[CmdletBinding()]
param([switch]$Clean)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tools = Join-Path $repo '.tools'
$build = Join-Path $PSScriptRoot 'build'

foreach ($exe in @(
  (Join-Path $tools 'arm-gcc\bin\arm-none-eabi-gcc.exe'),
  (Join-Path $tools 'cmake\bin\cmake.exe'),
  (Join-Path $tools 'ninja\ninja.exe')
)) {
  if (-not (Test-Path $exe)) { throw "missing $exe; run firmware/tools/bootstrap.ps1 first" }
}

$env:PATH = "$tools\arm-gcc\bin;$tools\cmake\bin;$tools\ninja;$env:PATH"

Write-Output ("TOOLCHAIN: " + (& arm-none-eabi-gcc --version | Select-Object -First 1))
Write-Output ("CMAKE:     " + (& cmake --version | Select-Object -First 1))
Write-Output ("NINJA:     " + (& ninja --version))

if ($Clean -and (Test-Path $build)) { Remove-Item -Recurse -Force $build }

& cmake -S $PSScriptRoot -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release `
    "-DCMAKE_TOOLCHAIN_FILE=$PSScriptRoot\cmake\arm-none-eabi-gcc.cmake"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& cmake --build $build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Get-Item (Join-Path $build 'psu_minimal.elf'), (Join-Path $build 'psu_minimal.bin'), (Join-Path $build 'psu_minimal.hex') |
  Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
