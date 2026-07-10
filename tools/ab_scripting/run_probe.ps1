# run_probe.ps1 -- generic one-shot AB ScriptEngine probe runner (ASCII-only, PS5.1-safe)
# Usage: powershell -File tools\ab_scripting\run_probe.ps1 -Script dump_visu.py -Result dump_visu_result.txt
# Same invocation pattern as ab_sync.ps1 (quoting learned 2026-07-08: bash->powershell -Command loses
# the inner quotes of --profile, so always go through a .ps1 file with ArgumentList array).
param(
    [Parameter(Mandatory=$true)][string]$Script,
    [Parameter(Mandatory=$true)][string]$Result,
    [int]$TimeoutSec = 240
)
$exe = "C:\Program Files\ABB\AB2.9\AutomationBuilder\Common\AutomationBuilder.exe"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$s = Join-Path $here $Script
$r = Join-Path $here $Result
if (Test-Path $r) { Remove-Item $r }
$p = Start-Process -FilePath $exe -ArgumentList @('--profile="Automation Builder 2.9"','--noUI',"--runscript=`"$s`"") -PassThru -WindowStyle Hidden
$done = $p.WaitForExit($TimeoutSec * 1000)
if (-not $done) {
    Write-Output "!! TIMEOUT($Script) - killing AB"
    Get-Process AutomationBuilder -ErrorAction SilentlyContinue | Stop-Process -Force
}
if (Test-Path $r) { Get-Content $r -Encoding UTF8 } else { Write-Output "!! no result file ($Script)" }
