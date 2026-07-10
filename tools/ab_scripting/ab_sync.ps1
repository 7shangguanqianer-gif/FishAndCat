# ab_sync.ps1 -- AB project auto sync + online test, one command (ASCII-only, PS5.1-safe)
# Usage: powershell -File tools\ab_scripting\ab_sync.ps1          (sync + compile + save + online run 40 cases)
#        powershell -File tools\ab_scripting\ab_sync.ps1 -SyncOnly (sync + compile only)
# Prereq: AB not opened by a human (needs exclusive project lock); headless, ~3-5 min.
# Note: keep this file ASCII-only. Windows PowerShell 5.1 reads UTF-8-without-BOM as ANSI,
#       so non-ASCII comments/strings corrupt the parser (learned 2026-07-07).
param([switch]$SyncOnly)

$exe = "C:\Program Files\ABB\AB2.9\AutomationBuilder\Common\AutomationBuilder.exe"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Run-ABScript($scriptName, $resultName, $timeoutSec) {
    $script = Join-Path $here $scriptName
    $res = Join-Path $here $resultName
    if (Test-Path $res) { Remove-Item $res }
    $p = Start-Process -FilePath $exe -ArgumentList @('--profile="Automation Builder 2.9"','--noUI',"--runscript=`"$script`"") -PassThru -WindowStyle Hidden
    $done = $p.WaitForExit($timeoutSec * 1000)
    if (-not $done) {
        Write-Output "!! TIMEOUT($scriptName) - killing AB"
        Get-Process AutomationBuilder -ErrorAction SilentlyContinue | Stop-Process -Force
    }
    if (Test-Path $res) { Get-Content $res -Encoding UTF8 } else { Write-Output "!! no result file ($scriptName)" }
}

Write-Output "=== [1/2] sync_st.py: .st -> AB project (40 objects) + build + save ==="
$out1 = Run-ABScript "sync_st.py" "sync_result.txt" 300
$out1 | Select-String -Pattern "summary|MSG_ERR|Compile|SAVE|ABSENT|CREATED"
if (-not ($out1 -match "Compile complete -- 0 errors")) {
    Write-Output "!! compile not clean (0 errors), stop (full log: sync_result.txt)"
    exit 1
}

if (-not $SyncOnly) {
    Write-Output "=== [2/2] run_test.py: online run PRG_Test ==="
    $out2 = Run-ABScript "run_test.py" "runtest_result.txt" 300
    $out2 | Select-String -Pattern "LOGIN|STATE|iPassed|iFailed|xAllPass|LOGOUT"
    if ($out2 -match "iPassed = INT#45" -and $out2 -match "iFailed = INT#0") {
        Write-Output "=== ALL GREEN: iPassed=45 iFailed=0 ==="
    } else {
        Write-Output "!! online test not 45/0 (full log: runtest_result.txt)"
        exit 2
    }
}
