# ab_sync.ps1 -- AB project auto sync + online test, one command (ASCII-only, PS5.1-safe)
# Usage: powershell -File tools\ab_scripting\ab_sync.ps1          (sync + compile + save + online run 77 cases)
#        powershell -File tools\ab_scripting\ab_sync.ps1 -SyncOnly (sync + compile only)
# Prereq: AB not opened by a human (needs exclusive project lock); headless, ~3-5 min.
# Note: keep this file ASCII-only. Windows PowerShell 5.1 reads UTF-8-without-BOM as ANSI,
#       so non-ASCII comments/strings corrupt the parser (learned 2026-07-07).
param([switch]$SyncOnly)

$exe = "C:\Program Files\ABB\AB2.9\AutomationBuilder\Common\AutomationBuilder.exe"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# 0712 guard: refuse to run while AB GUI is open (double instance = project corruption).
# Mechanism-level gate replaces "ask the human first" (DR-5 action-guard pattern).
if (Get-Process -Name "AutomationBuilder" -ErrorAction SilentlyContinue) {
    Write-Output "!! Automation Builder is RUNNING - close it first, then rerun (exit 3)"
    exit 3
}

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

Write-Output "=== [1/2] sync_st.py: .st -> AB project (48 objects) + build + save ==="
$out1 = Run-ABScript "sync_st.py" "sync_result.txt" 300
$out1 | Select-String -Pattern "summary|MSG_ERR|Compile|SAVE|ABSENT|CREATED|NOT_IN_MAP"
if (-not ($out1 -match "Compile complete -- 0 errors")) {
    Write-Output "!! compile not clean (0 errors), stop (full log: sync_result.txt)"
    exit 1
}

if (-not $SyncOnly) {
    Write-Output "=== [2/2] run_test.py: online run PRG_Test ==="
    $out2 = Run-ABScript "run_test.py" "runtest_result.txt" 300
    # 0712 R-audit: archive each round's logs as non-overwritable copies. A three-round
    # narrative needs three replayable artifacts, so do not keep only the last round.
    # (0729: this comment was Chinese, violating the ASCII-only rule at the top of this file.
    #  It happened to parse anyway because the mojibake stayed inside a comment - luck, not design.)
    $logDir = Join-Path $here "logs"
    New-Item -ItemType Directory -Force $logDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    if (Test-Path (Join-Path $here "sync_result.txt")) {
        Copy-Item (Join-Path $here "sync_result.txt") (Join-Path $logDir "sync_result_$stamp.txt")
    }
    if (Test-Path (Join-Path $here "runtest_result.txt")) {
        Copy-Item (Join-Path $here "runtest_result.txt") (Join-Path $logDir "runtest_result_$stamp.txt")
    }
    $out2 | Select-String -Pattern "LOGIN|STATE|iPassed|iFailed|xAllPass|LOGOUT"

    # 0729 gate rewrite. Two reasons (see plc\README_PLC.md section 2b):
    #  (1) the expected count now follows N_CASES in the source instead of a hardcoded 77,
    #      so extending PRG_Test no longer silently leaves a stale gate behind;
    #  (2) "not 77/0" used to be reported the same way whether a case really failed or the
    #      simulated PLC was still running an older application. Those need different fixes,
    #      so they now print different messages.
    $stFile = Join-Path (Split-Path -Parent (Split-Path -Parent $here)) "plc\06_PRG_Test.st"
    $nExpect = 77
    if (Test-Path $stFile) {
        $mN = Select-String -Path $stFile -Pattern 'N_CASES\s*:\s*INT\s*:=\s*(\d+)' | Select-Object -First 1
        if ($mN) { $nExpect = [int]$mN.Matches[0].Groups[1].Value }
    }
    $txt = ($out2 | Out-String)
    $mP = [regex]::Match($txt, 'iPassed = INT#(\d+)')
    $mF = [regex]::Match($txt, 'iFailed = INT#(\d+)')
    if (-not ($mP.Success -and $mF.Success)) {
        Write-Output "!! could not read iPassed/iFailed (full log: runtest_result.txt)"
        exit 2
    }
    $nPass = [int]$mP.Groups[1].Value
    $nFail = [int]$mF.Groups[1].Value
    if ($nPass -eq $nExpect -and $nFail -eq 0) {
        Write-Output "=== ALL GREEN: iPassed=$nPass iFailed=0 (N_CASES=$nExpect) ==="
    } elseif (($nPass + $nFail) -ne $nExpect) {
        Write-Output "!! STALE APPLICATION - this is NOT a test failure."
        Write-Output "   iPassed+iFailed = $($nPass + $nFail), but source N_CASES = $nExpect."
        Write-Output "   The summary loop 'FOR i := 1 TO N_CASES' bumps exactly one counter per case,"
        Write-Output "   so the two must always add up to N_CASES. A smaller sum means the simulated"
        Write-Output "   PLC is still running an OLDER application."
        Write-Output "   Most likely cause: run_test.py logs in with OnlineChangeOption.Try (online"
        Write-Output "   change), and N_CASES is VAR CONSTANT, which online change cannot alter."
        Write-Output "   Try forcing a full download (OnlineChangeOption.Never), then rerun."
        Write-Output "   Read plc\README_PLC.md section 2b first - it also explains why the loose"
        Write-Output "   runtest_result.txt in this folder must never be cited as evidence."
        exit 2
    } else {
        Write-Output "!! REAL TEST FAILURE: iPassed=$nPass iFailed=$nFail (N_CASES=$nExpect)"
        Write-Output "   Sum matches N_CASES, so the running application IS current."
        $out2 | Select-String -Pattern "sLastFail"
        exit 2
    }
}
