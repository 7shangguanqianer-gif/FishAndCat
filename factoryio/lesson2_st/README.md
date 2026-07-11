# 第二课教具 ST(Claude 预写,0711;7/14-15 开课用)

两段教具按课纲顺序使用(课纲=`F:\abb_wh_work\2_你要操作\FactoryIO仿真上手教程.md`,
教练任务书=`F:\abb_wh_work\docs\Codex三课教练任务书_0711.md`):

| 文件 | 场景 | 用时 | 验收物 |
|---|---|---|---|
| `belt_stop.st` | From A to B(传送带+光电) | ~30min | 30 秒录屏:箱到即停 |
| `crane_3boxes.st` | Automated Warehouse / Stacker Crane | ~1.5h | 30 秒录屏:3 箱进 5/18/31 格 |

规则(任务书原文):学生**亲手**粘贴+建变量+做映射,Codex 只指路排障;
FIO 的 tag 名以驱动窗口实际显示为准,变量语义已在文件头注释写死;
场景文件另存到 `F:\abb_wh_work\factoryio\`;验收物+卡点清单发回 Claude 讲评。

连不通先查三件套(教程原文):软 PLC 是否 RUN / Symbol Configuration 是否
下载 / Windows 防火墙;FIO 的 RUN 和 CODESYS 的 RUN 是两个开关。
