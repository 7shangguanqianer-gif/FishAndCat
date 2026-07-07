# ab_sync.ps1 — AB 工程自动同步+测试一条命令
# 用法:powershell -File tools\ab_scripting\ab_sync.ps1          (同步+编译+保存+在线跑24用例)
#       powershell -File tools\ab_scripting\ab_sync.ps1 -SyncOnly (只同步编译,不在线测试)
# 前提:AB 未被人工打开(独占工程文件);全程无头,约 3-5 分钟。
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

Write-Output "=== [1/2] sync_st.py: .st -> AB 工程(34 对象)+ 编译 + 保存 ==="
$out1 = Run-ABScript "sync_st.py" "sync_result.txt" 300
$out1 | Select-String -Pattern "summary|MSG_ERR|Compile|SAVE|ABSENT|CREATED"
if (-not ($out1 -match "Compile complete -- 0 errors")) {
    Write-Output "!! 编译非 0 错误,停止(完整日志 sync_result.txt)"
    exit 1
}

if (-not $SyncOnly) {
    Write-Output "=== [2/2] run_test.py: 仿真在线跑 PRG_Test ==="
    $out2 = Run-ABScript "run_test.py" "runtest_result.txt" 300
    $out2 | Select-String -Pattern "LOGIN|STATE|iPassed|iFailed|xAllPass|LOGOUT"
    if ($out2 -match "iPassed = INT#40" -and $out2 -match "iFailed = INT#0") {
        Write-Output "=== ALL GREEN: iPassed=40 iFailed=0 ==="
    } else {
        Write-Output "!! 在线测试未达 40/0(完整日志 runtest_result.txt)"
        exit 2
    }
}
