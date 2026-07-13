# 合成鼠标右键拖拽（相对位移版，兼容 Unity Raw Input 的 mouse-look）
# 用法: rdrag.ps1 -dx 300 -dy 0   （右键按住后相对移动 dx,dy 屏幕像素，分小步产生 delta 事件）
param(
    [int]$dx = 0, [int]$dy = 0,
    [int]$steps = 30
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class MouseOps {
    [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, UIntPtr dwExtraInfo);
    public const uint MOVE      = 0x0001;
    public const uint RIGHTDOWN = 0x0008;
    public const uint RIGHTUP   = 0x0010;
}
"@
[MouseOps]::mouse_event([MouseOps]::RIGHTDOWN, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 150
$sx = [Math]::Truncate($dx / $steps)
$sy = [Math]::Truncate($dy / $steps)
for ($i = 0; $i -lt $steps; $i++) {
    [MouseOps]::mouse_event([MouseOps]::MOVE, $sx, $sy, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 15
}
Start-Sleep -Milliseconds 150
[MouseOps]::mouse_event([MouseOps]::RIGHTUP, 0, 0, 0, [UIntPtr]::Zero)
Write-Output "rdrag relative done dx=$dx dy=$dy"
