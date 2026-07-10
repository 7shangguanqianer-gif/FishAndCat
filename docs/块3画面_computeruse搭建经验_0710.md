# 块3 画面 computer use 搭建经验与进度(0710)

> 背景:块3 ST 侧已全绿(iPassed=45/0,commit deb2051)。画面(VisuMain)由 Claude 用
> computer use 在用户机上搭建。本文档记录**踩过的坑+验证过的正确方法+当前进度+下一步**,
> 供 compact 后接续或用户手搭参考。**核心结论:computer use 能搭但极耗,焦点/剪贴板/浮窗
> 遮罩多重障碍;若继续卡,转"用户手搭+Claude 截图导航"或"export XML 生成"更快。**

## 一、环境障碍与真相(踩坑记录,按发现顺序)

1. **AB 权限=full tier**(非预期的 click)——computer use 能拖能打字。请求:
   `request_access(["Automation Builder 2.9"], clipboardWrite=true)`(clipboardWrite 必须要,见坑6)。

2. **严禁 `open_application("Automation Builder 2.9")` 唤 AB**——它会**开出新的 AB 实例**
   (Start Page 空窗口),造成多实例混乱+反复弹许可框。要激活现有 AB 用点任务栏图标或直接
   操作可见窗口。多实例已出现过 2 次,每次都要手动关掉多余的。

3. **"黑块"真相=截图隐私遮罩**:computer use 截图会把**不在授权清单的窗口**涂成纯黑矩形
   (用户真实屏幕上是个**置顶浮窗**,内容正常)。规律:
   - AB **最大化**时→工具箱挪到屏幕右上,正好被那个固定位置的置顶浮窗盖住→工具箱变黑;
   - AB **窗口化**时→工具箱在别处→不被盖→正常。
   - **对策:别最大化 AB(保持窗口化);或请用户彻底关掉那个置顶浮窗(Clash/网易云/聊天悬浮之类)。**
   - 我曾把这个遮罩误判为"AB 渲染故障",带偏很久——**记住:规整的黑矩形=被遮罩的窗口,不是AB坏了。**

4. **工具箱不出元素的真相=面板太矮**:11 个分类标签(Basic/Common Controls/.../Favorite)
   挤满工具箱面板,**没有垂直空间显示元素缩略图**。解法:**菜单 Window → Reset Window Layout,
   或把工具箱面板拖高/拖宽,或关掉底部 Messages 面板腾高度**。搞定后 Basic 分类下出现 10 个
   缩略图:Rectangle/Rounded Rectangle/Ellipse/Line/Polygon/Polyline/Bézier Curve/Pie/Image/Frame。
   (用户"点 Basic 没反应"就是这个,不是点错。)

5. **仿真状态下画面只读**:AB 在 SIMULATION 在线时画面编辑器不可编辑。先 **Online → Logout**。

## 二、验证过的正确操作方法

6. **放元素**(关键,CODESYS 特有):**不是**直接拖工具箱→画布(快速拖不识别)。正确:
   - 单击工具箱元素缩略图 → 它变**蓝色选中**;
   - 在画布上**拖画一个矩形区域**(分步:`left_mouse_down` → 多个 `mouse_move` 慢移 → `left_mouse_up`);
   - 元素放置在拖画的区域。✅ 已成功放置 1 个 Rectangle。

7. **Properties 面板**:底部标签切 Properties/Visualization Toolbox。属性=分组可展开列表
   (Position/Colors/Appearance/Color variables/...)。**勾右上角 Advanced** 才显示高级属性
   (如 Color variables → Normal state → Fill color 变量绑定)。

8. **Fill color 变量绑定路径**:勾 Advanced → 展开 Color variables → 展开 **Normal state**
   → **Fill color** 行(⚠️展开 Normal state 后行会下移:Fill color 到 Frame color 下方,
   坐标要看当前截图实际位置,别用旧坐标)→ 双击 Value 进编辑框(右侧有 "..." Input Assistant 按钮)。

9. **打字焦点坑**:type 前 Claude 桌面端(Electron)会抢键盘焦点→报错
   `Claude's own window still has keyboard focus`。**解法:同一个 computer_batch 里
   double_click + type 连续执行**(中间不给 Claude 抢焦点的机会),别分两次调用。

10. **打字剪贴板坑**:变量名含 `$ [ ]` 特殊字符→type 走剪贴板粘贴→**必须有 clipboardWrite
    授权**,否则 type 报"Typed via clipboard"但实际没粘贴进去(单元格一直空,白忙)。
    **已在最后补授权 clipboardWrite**(request_access clipboardWrite=true)。

## 三、当前进度(compact 时点)

- ✅ 环境理顺:单 AB 实例、窗口化、已登出仿真、工具箱正常出元素、Advanced 已勾;
- ✅ 画布上放了 **1 个 Rectangle**(未绑变量,GenElemInst_2),工程有未保存改动(标题栏 `*`);
- ⏳ 正在给这个 Rectangle 的 **Fill color 绑变量**——刚补 clipboardWrite 授权,还没重试成功;
- ⚠️ **这个矩形若不在 AB 里保存,compact 后会丢**(在 AB 内存,没存进 .project)——但重放很快。

## 四、下一步操作序列(接续用)

1. 重绑 Fill color(clipboardWrite 已授权):同 batch `double_click(Fill color Value)` +
   `type "GVL_Visu.VisuSlotColor[$FIRSTDIM$, $SECONDDIM$]"` + `key Return` → zoom 确认填入;
   - ⚠️ 若 `$FIRSTDIM$` 占位符被 CODESYS 拒(存疑,未证实),先填 `[0, 0]` 验证机制,占位符
     交给 Multiply 对话框处理(Multiply 时指定"用第一维/第二维索引替换占位符")。
2. 设 Position:展开 Position,X=40 Y=40 Width=28 Height=20(28×20 无缝网格,几何常量见 GVL_Param);
3. **右键 Rectangle → Multiply Visualization Element** → 第一维(列)数量20/偏移28、第二维(层)
   数量20/偏移20 → **一次生成 400 格网格**(细则9 主体);
4. 再放其余样例元素(Common Controls: Text field/Button/Combo Box;Lamps: Lamp;Basic: Ellipse),
   按 [块3施工依据_0708.md] §1 + [AB可视化搭建操作卡_块3增补.md] 的绑定配方;
5. 保存 → 六步演示脚本 v2 验收。

## 四b、⚡0710 终局:ScriptVisualization API 路线实战胜出(Codex)

> 本节取代下方 §五 的猜想——**画面自动化的正解已实战验证,§五仅存档**。

- **AB 2.9 内嵌 CODESYS 支持官方 `ScriptVisualization` 脚本 API**(=CODESYS V3.5 SP21
  2025-03 新能力;0708 探针 `create_visualization=False` 探的是旧猜想名,漏了新命名空间)。
- Codex 用它完成批次 B/C 全部画面(VisuMain 477 元素+VisuStats 113 元素),编译 0 错、
  PRG_Test 45/0、ST 零改动审计过。生成器与探针档案已收编 **tools/visu_gen/**(含 README
  运行约束);交接报告=docs/evidence_0710/。
- GUI 自动点击(computer use)路线盖棺:AB GUI 受控崩溃 4 次,慢且不稳——本文档一至四节
  的坑此后只服务于"**人工** GUI 操作"场景(如批次 D 报警配置)。
- 剩余不可脚本化项:Alarm Configuration/Banner(无公开创建 API,Codex 与 0710 枪1 一致
  确认)→ 人工 GUI 一次性配置(增补卡 §3,约 10 分钟)。
- XML 管线(export_native→改→import_native)降级为**理论备份路线**:0710 枪2 实测风险=
  ScriptEngine import 路径与 IDE 菜单不等价(SP21P2 有 cast 报错真实案例)/GUID 会被校验/
  冲突处理需自写 NativeImportHandler(官方员工示例代码见枪2报告)——有 ScriptVisualization
  后不再需要走这条。

## 五、战略反思与备选路径(0710 上半日的猜想,已被 §四b 取代,存档)

- **computer use 搭 AB 画面能做但极耗**:焦点抢占、剪贴板授权、坐标随展开漂移、浮窗遮罩,
  每个元素+属性几十步,易错。不适合搭完整画面(尤其几十个元素)。
- **备选 A(推荐):用户手搭 + Claude 截图导航**——用户手动不受 Claude 焦点抢占困扰,
  Claude 看用户清晰截图(无遮罩)精确指令每一步。用户额度换稳定。
- **备选 B:export_native 导出裸元素 XML → Claude 在 XML 层生成 400 格+绑变量 → import_native**
  ——完全绕开 GUI,但要**先关 AB**(ScriptEngine 独占工程);裸元素结构可导出参考
  (tools/ab_scripting/dump_visu.py 已能导出,visu_main_native.xml 有空画面容器结构)。
- **备选 C:computer use 只放裸元素(它可靠),变量绑定+400格复制走 XML/Multiply**。
- **前置永远先做**:请用户彻底关掉那个置顶浮窗;保持 AB 窗口化不最大化。

## 六、关键坐标/事实备查

- 工具箱 Basic 元素缩略图(AB 窗口化、面板拖高后):Rectangle 在缩略图区左上第一个。
- 放元素:选中缩略图变蓝 → 画布 left_mouse_down/move/up 拖画。
- Fill color 编辑:勾 Advanced → Color variables → Normal state → Fill color → 双击 Value。
- 打字:double_click+type 必须同 batch;clipboardWrite 已授权。
- 别 open_application AB(开新实例);别最大化 AB(工具箱被浮窗遮罩)。
