#requires -Version 5.1
<#
.SYNOPSIS
  T-0002 dev-environment bootstrap: pinned ARM GCC / CMake / Ninja / OpenOCD / PuTTY
  plus CMSIS + STM32G0 HAL. Everything goes to <repo>/.tools (git-ignored).

.DESCRIPTION
  From scratch on Windows 10/11 x64 (git, curl, tar are required; Windows ships curl/tar):
      powershell -ExecutionPolicy Bypass -File firmware/tools/bootstrap.ps1
  Idempotent: existing components are skipped; -Force re-downloads/reinstalls.

.NOTES
  Only official release packages are downloaded. No system PATH or registry changes.
  This script is ASCII-only so Windows PowerShell 5.1 can parse it without a BOM.
#>
[CmdletBinding()]
param(
  [string]$ToolsDir = '',
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if ([string]::IsNullOrWhiteSpace($ToolsDir)) {
  $ToolsDir = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path '.tools'
}
$root = [IO.Path]::GetFullPath($ToolsDir)
$downloads = Join-Path $root 'downloads'
New-Item -ItemType Directory -Force -Path $downloads | Out-Null

$packages = @(
  @{ Name = 'arm-gcc'; Archive = 'arm-gcc.zip'; Marker = 'bin\arm-none-eabi-gcc.exe'
     Url = 'https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v15.2.1-1.1/xpack-arm-none-eabi-gcc-15.2.1-1.1-win32-x64.zip' }
  @{ Name = 'cmake'; Archive = 'cmake.zip'; Marker = 'bin\cmake.exe'
     Url = 'https://github.com/xpack-dev-tools/cmake-xpack/releases/download/v3.31.9-1/xpack-cmake-3.31.9-1-win32-x64.zip' }
  @{ Name = 'ninja'; Archive = 'ninja.zip'; Marker = 'ninja.exe'; Flat = $true
     Url = 'https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip' }
  @{ Name = 'openocd'; Archive = 'openocd.zip'; Marker = 'bin\openocd.exe'
     Url = 'https://github.com/xpack-dev-tools/openocd-xpack/releases/download/v0.12.0-7/xpack-openocd-0.12.0-7-win32-x64.zip' }
  @{ Name = 'putty'; Archive = 'putty.exe'; Marker = 'putty.exe'; SingleFile = $true
     Url = 'https://the.earth.li/~sgtatham/putty/latest/w64/putty.exe' }
)

function Get-Package {
  param($Pkg)
  $archive = Join-Path $downloads $Pkg.Archive
  if ($Force -or -not (Test-Path $archive)) {
    Write-Host "[download] $($Pkg.Archive)"
    & curl.exe -L --fail --retry 3 --silent --show-error -o $archive $Pkg.Url
    if ($LASTEXITCODE -ne 0) { throw "download failed: $($Pkg.Url) (curl exit $LASTEXITCODE)" }
  } else {
    Write-Host "[download] $($Pkg.Archive) exists, skip"
  }
  return $archive
}

function Expand-Package {
  param($Pkg, [string]$Archive)
  $target = Join-Path $root $Pkg.Name
  if (-not $Force -and (Test-Path (Join-Path $target $Pkg.Marker))) {
    Write-Host "[install ] $($Pkg.Name) exists, skip"
    return
  }
  if ($Force -and (Test-Path $target)) { Remove-Item -Recurse -Force $target }

  if ($Pkg.SingleFile) {
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item $Archive (Join-Path $target $Pkg.Marker) -Force
    return
  }

  $stage = Join-Path $root ".stage-$($Pkg.Name)"
  if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
  New-Item -ItemType Directory -Force -Path $stage | Out-Null
  Write-Host "[install ] $($Pkg.Name) extracting"
  & tar.exe -xf $Archive -C $stage
  if ($LASTEXITCODE -ne 0) { throw "extract failed: $Archive" }

  if ($Pkg.Flat -or (Test-Path (Join-Path $stage $Pkg.Marker))) {
    Move-Item $stage $target
  } else {
    $inner = @(Get-ChildItem -LiteralPath $stage -Directory)
    if ($inner.Count -ne 1) { throw "unexpected archive layout: $($Pkg.Archive)" }
    Move-Item $inner[0].FullName $target
    Remove-Item -Recurse -Force $stage
  }
  if (-not (Test-Path (Join-Path $target $Pkg.Marker))) { throw "$($Pkg.Name) install check failed" }
}

foreach ($pkg in $packages) {
  $archive = Get-Package $pkg
  Expand-Package $pkg $archive
}

# CMSIS Core / G0 device headers+startup / HAL driver, pinned tags.
$cube = Join-Path $root 'stm32cube'
New-Item -ItemType Directory -Force -Path $cube | Out-Null
$repos = @(
  @{ Name = 'cmsis_core';           Tag = 'v5.9.0' },
  @{ Name = 'cmsis_device_g0';      Tag = 'v1.4.5' },
  @{ Name = 'stm32g0xx_hal_driver'; Tag = 'v1.4.7' }
)
foreach ($repo in $repos) {
  $dir = Join-Path $cube $repo.Name
  if ((Test-Path (Join-Path $dir '.git')) -and -not $Force) {
    Write-Host "[git     ] $($repo.Name) exists, skip"
    continue
  }
  if ($Force -and (Test-Path $dir)) { Remove-Item -Recurse -Force $dir }
  Write-Host "[git     ] $($repo.Name) @ $($repo.Tag)"
  & git clone --depth 1 --branch $repo.Tag "https://github.com/STMicroelectronics/$($repo.Name).git" $dir
  if ($LASTEXITCODE -ne 0) { throw "git clone failed: $($repo.Name)" }
}

Write-Host ''
Write-Host '=== version check ==='
& (Join-Path $root 'arm-gcc\bin\arm-none-eabi-gcc.exe') --version | Select-Object -First 1
& (Join-Path $root 'cmake\bin\cmake.exe') --version | Select-Object -First 1
& (Join-Path $root 'ninja\ninja.exe') --version | ForEach-Object { "ninja $_" }
$previousEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'   # openocd writes its version to stderr
$ocdOut = Join-Path $root '.ocd-version.out'
$ocdErr = Join-Path $root '.ocd-version.err'
Start-Process -FilePath (Join-Path $root 'openocd\bin\openocd.exe') -ArgumentList '--version' `
  -NoNewWindow -Wait -RedirectStandardOutput $ocdOut -RedirectStandardError $ocdErr | Out-Null
$ocdVersion = Get-Content $ocdErr -TotalCount 1
Remove-Item $ocdOut, $ocdErr -Force -ErrorAction SilentlyContinue
$ErrorActionPreference = $previousEap
$ocdVersion
"PuTTY " + (Get-Item (Join-Path $root 'putty\putty.exe')).VersionInfo.ProductVersion
foreach ($repo in $repos) {
  $dir = Join-Path $cube $repo.Name
  "{0} {1} ({2})" -f $repo.Name, $repo.Tag, (git -C $dir rev-parse --short HEAD)
}
Write-Host ''
Write-Host "done. tools root: $root"
