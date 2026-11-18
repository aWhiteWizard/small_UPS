#requires -Version 5.1
<#
.SYNOPSIS
  T-0022 pinned toolchain check: verify every version installed by bootstrap.ps1.
.DESCRIPTION
  Read-only. No download, no PATH/registry change, no target hardware required.
  Exit 0 when all pinned versions match; exit 1 with a table of mismatches otherwise.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File firmware/tools/check-env.ps1
#>
[CmdletBinding()]
param([string]$ToolsDir = '')

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if ([string]::IsNullOrWhiteSpace($ToolsDir)) { $ToolsDir = Join-Path $repo '.tools' }
if (-not (Test-Path $ToolsDir)) {
  throw "missing tools root: $ToolsDir (run firmware/tools/bootstrap.ps1 first)"
}
$tools = (Resolve-Path $ToolsDir).Path

function Get-FirstLine {
  param([string]$Exe, [string[]]$ArgList)
  if (-not (Test-Path $Exe)) { return '' }
  $previous = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try { $text = & $Exe @ArgList 2>&1 | Out-String } finally { $ErrorActionPreference = $previous }
  $line = @($text -split "`r?`n" | Where-Object { $_.Trim() })[0]
  if ($null -eq $line) { return '' }
  return ([string]$line).Trim()
}

function Get-StderrFirstLine {
  param([string]$Exe, [string]$Arg)
  if (-not (Test-Path $Exe)) { return '' }
  $stdout = [IO.Path]::GetTempFileName()
  $stderr = [IO.Path]::GetTempFileName()
  try {
    Start-Process -FilePath $Exe -ArgumentList $Arg -NoNewWindow -Wait `
      -RedirectStandardOutput $stdout -RedirectStandardError $stderr | Out-Null
    $line = Get-Content -LiteralPath $stderr -TotalCount 1 -ErrorAction SilentlyContinue
    if ($null -eq $line) { return '' }
    return ([string]$line).Trim()
  } finally {
    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
  }
}

function Get-GitTag {
  param([string]$Dir)
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return '' }
  if (-not (Test-Path (Join-Path $Dir '.git'))) { return '' }
  $previous = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try { $tag = & git -C $Dir describe --tags --always 2>$null } finally { $ErrorActionPreference = $previous }
  if ($LASTEXITCODE -ne 0 -or $null -eq $tag) { return '' }
  return ([string]$tag).Trim()
}

$script:rows = @()
function Add-Row {
  param([string]$Name, [string]$Expect, [string]$Found)
  $ok = $false
  if (-not [string]::IsNullOrWhiteSpace($Found)) { $ok = $Found -like "*$Expect*" }
  $script:rows += [pscustomobject]@{ Item = $Name; Expect = $Expect; Found = $Found; OK = $ok }
}

Add-Row 'arm-none-eabi-gcc' '15.2.1' (Get-FirstLine (Join-Path $tools 'arm-gcc\bin\arm-none-eabi-gcc.exe') @('--version'))
Add-Row 'cmake' '3.31.9' (Get-FirstLine (Join-Path $tools 'cmake\bin\cmake.exe') @('--version'))
Add-Row 'ninja' '1.13.2' (Get-FirstLine (Join-Path $tools 'ninja\ninja.exe') @('--version'))
Add-Row 'openocd' '0.12.0' (Get-StderrFirstLine (Join-Path $tools 'openocd\bin\openocd.exe') '--version')

$puttyExe = Join-Path $tools 'putty\putty.exe'
$puttyVer = ''
if (Test-Path $puttyExe) { $puttyVer = (Get-Item -LiteralPath $puttyExe).VersionInfo.ProductVersion }
Add-Row 'PuTTY' '0.85' ("PuTTY " + $puttyVer)

Add-Row 'cmsis_core' 'v5.9.0' (Get-GitTag (Join-Path $tools 'stm32cube\cmsis_core'))
Add-Row 'cmsis_device_g0' 'v1.4.5' (Get-GitTag (Join-Path $tools 'stm32cube\cmsis_device_g0'))
Add-Row 'stm32g0xx_hal_driver' 'v1.4.7' (Get-GitTag (Join-Path $tools 'stm32cube\stm32g0xx_hal_driver'))

$script:rows | Format-Table -AutoSize
$bad = @($script:rows | Where-Object { -not $_.OK })
if ($bad.Count -gt 0) {
  Write-Output ("CHECK-ENV: FAIL (" + $bad.Count + " item(s))")
  exit 1
}
Write-Output 'CHECK-ENV: PASS'
