# 生产操作：Agent Skin 首期 Codex 适配

产品名为Agent Skin，目标包名为`agent-skin`，首期仅适配Codex。当前包目录和Hub组件仍分别为`codex-startup-animation`与`startup-animation`；下方命令是更名前的实际入口，不表示更名已经完成。前置单N落地时同步这些入口；Codex安装身份、旧snapshot来源与生产门保持。

本文规定如何把[目标设计](detailed-design.md)推进到**本机日常使用**。目标实现尚未开始；操作和晋级门均为Planned。对外分发是额外门，不能由本机Production推导。用户已有授权持续有效，执行前核对其范围；仅在缺失真实操作授权时才请求补充，不重复索取已授予许可。

## 1. 晋级门与完成判据

| 门 | 输入 / Owner | 退出判据 | 不满足时 |
|---|---|---|---|
| G0：设计可执行 | v0.2文档、回源及独立评审 / 文档Owner | FR01–FR12有设计和T映射；无未修P1/P2契约矛盾；图真实渲染无错误；agent工作单和生产命令明确 | 修文档或记录外部限制，不能以分数代替缺项 |
| G1：隔离实现 | A–D代码及行为测试 / 实现Owner | T01–T20适用fake/browser/native项通过；新增测试已接入对应CI；全仓verify通过 | 保持Planned/Implemented，修复失败切片 |
| G2：固定构建与隔离安装 | E构建、授权私有输入、既有installer / 构建Owner | T21–T26/T28–T29隔离部分通过；真实输入摘要、产物签名与inspect一致；smoke完成；test-install/uninstall保持其他登记 | 不碰日常入口，不删除未知包来消除冲突 |
| G3：真实宿主 | 固定构建+具体官方版本 / 验收Owner | 冷启动同窗口、热启动不重播、设置事务、CSP/图像呈现、恢复、只读status、端口寿命、错误降级都有当前环境证据 | 标记该版本不支持，保留官方入口 |
| G4：视觉与资源 | 授权默认图、3尺寸×2DPR、深浅色 / 维护者+验收Owner | 阶段动作和阿舟身份明确，文字可读、输入可用；RC6帧/资源门满足，系统内存与呈现观测如实记录 | 不切换日常实现；实际视觉反馈修素材或布局 |
| G5：本地日常切换 | G1–G4证据、获准安装、前向修复方案 / 维护者 | 从最终Hub包路径构建并安装；唯一入口核验通过；受控完成一次冷启动和一次热激活，再完成下一次日常启动，无阻断项 | dispose/官方入口退回；程序用更高修复版恢复行为 |
| G6：对外分发 | 程序及素材许可、脱敏文档、支持声明 / 维护者 | 对复用代码与资产有明确许可，分发内容与支持版本一致，发布单独获准 | 本地使用状态保持，分发继续hold |

“本地Production”仅在G5结束并记录真实Owner决定后成立；需写出精确App版本、macOS、构建和素材范围。G6尚未通过时不能发布App/源码包/私有资产。任何门的PASS被相关新bytes、配置或官方版本变化失效，只重做受影响门，不重新泛跑全部历史测试。

本机首轮候选环境（2026-10-26只读）：官方`/Applications/ChatGPT.app`，`com.openai.codex`，`26.1021.31345/build21828`，签名描述Team`2DC432GLL2`。此记录既不是深签名验证也不是运行PASS；G3运行前重新读取并验证。macOS13是代码部署目标，不推导所有13+版本、所有架构已支持；只公布实际测过的组合。

## 2. 进入G2：构建和隔离操作

下面是**现有入口形状**；先完成实现指南E的消费方升级再用于新payload。所有路径变量必须由本轮真实plan输出填入，不猜默认目录。当前仅文档任务不执行这些命令。

```sh
# 从Hub根目录，读取命令面和source状态
python scripts/azhou_hub.py integrations startup-animation --help
python scripts/azhou_hub.py integrations startup-animation check-source

# workspace是源目录外的绝对临时工作区，private-assets是已有授权素材目录
python scripts/azhou_hub.py integrations startup-animation build \
  --workspace "$STARTUP_WORKSPACE" --private-assets "$STARTUP_PRIVATE_ASSETS"
```

计划确认当前输入、scope仅为隔离构建后，使用该计划的完整plan_id重复同一命令并加`--apply --plan-id "$STARTUP_BUILD_PLAN_ID"`。读取输出的bundle字段填为`STARTUP_PAYLOAD`；不要把产品路径硬编码成源树的旧dist。

```sh
python scripts/azhou_hub.py integrations startup-animation inspect --bundle "$STARTUP_PAYLOAD"
python scripts/azhou_hub.py integrations startup-animation run --mode smoke --bundle "$STARTUP_PAYLOAD"
```

run默认只出plan。获准隔离运行后，同一命令带该次plan_id和--apply执行，按RC7 smoke判据检查完成。它不能证明真实CDP接入。test-install/test-uninstall亦先plan，再携当前plan_id apply；读取--help填真实payload/workspace字段，receipt记录target与registry差异。它们会写隔离App和系统登记，不能把“测试”当成全机无副作用。

命令路径稳定不等于旧plan永远有效；源、素材、版本或目标变化后重新生成计划，不能复用旧id。执行失败时保留输出及owned receipt，按当前工具报错处理，不手工删共享状态。

## 3. 进入G3：真实宿主验收

先完成所有可在隔离环境完成的检查，再执行以下会影响当前官方会话的步骤。若当前用户只批准文档或隔离测试，交付已经构建的载荷、精确计划、影响及恢复步骤，等待真实操作授权；不要提前开关用户App。

1. 记录官方Bundle版本和完整签名/路径、主PID、是否已运行及既有端口；只读取元数据和最少进程信息，不采集聊天。完成条件：目标身份可信，运行中的工作会话是否需要用户保存明确。
2. **热启动先验**：官方已运行时打开目标入口，分别检查已有/无可验证CDP两种fixture；实机至少覆盖当前状态。完成条件：同一PID被激活，进程数不增加、不重启、不重播，事件=target-activated而不是startup-ready。
3. **冷启动**：由用户保存工作并正常完全退出官方应用后，从目标入口启动；不使用kill。完成条件：窗口内出现动画；targetId唯一且可信；installed、ready/skip与辅助退出分开记录；官方正常加载。
4. 用独立验收reader有界检查本页status和overlay DOM，记录natural complete或skipped；reader完成即退出。完成条件：parent覆盖层消失，点击真实输入框可正常输入；日志中辅助ready退出不被误作完整播放。
5. 执行T08–T12/T26真实部分：播放中和结束后快捷键、保存并预览、取消、默认、错误输入、恢复；真实账号环境不人为填满磁盘或破坏其IDB来做故障注入，故障反例由隔离测试完成。完成条件：实际变更与RC一致，用户原设置可恢复。
6. 真实读取wallpaper-status，确认图片解码、CSS哨兵、窄表面与装饰核查；菜单、输入框、代码块、长聊天滚动和侧栏可用。完成条件：CSP没有阻断动画样式/data图片/Blob壁纸；不兼容时按分项失败，不改官方CSP。
7. 执行restore，确认owned控制器/样式/URL/监听被移除，已保存设置保留；再只读查看调试端口。完成条件：页面恢复官方外观，明确记录端口仍属于官方进程。用户正常完全退出后从官方图标重开，确认本次调试状态终止且没有美化自动加载。

多个可信主页面时，本产品拒绝猜测；测试报告记录ambiguous-main-page，用户手动整理窗口后可发起新的明确冷启动，不在原重试循环中切目标。

## 4. G4视觉、性能与交互

使用固定的授权默认图和已知测试图，记录窗口点数、DPR、像素放大与crop。至少覆盖窄/常规/宽3种尺寸，DPR=1/2，深浅色；测不到的组合不列为支持。按T03时间点采样，在4.18–7.43s检查头像散开、左到右聚合和色图配准；12s检查覆盖层消失。无需复刻S角色、品牌文字或像素分布。

资源验收使用同一授权素材和静止测试窗口，10轮播放/设置重播，每轮complete后观察5s：owned动画rAF=0、iframe=0，身份位图/Path2D等引用释放，最多保留一份已解码壁纸与URL，dispose后owned URL/样式/监听为0。系统CPU/RSS/峰值内存单独采样，注明宿主自身活动和测量方法；不能把宿主总RSS波动归因给本功能，也不能只凭JS计时声称GPU无丢帧。

帧工作警告/降级线使用RC6；若目标60Hz无法稳定达到，评审默认素材/粒子成本，或明确降低已支持效果与预算后重验，不静默把未达标写成PASS。无法取得系统测量时G4保持未满足，而不是编一个峰值数。

## 5. G5最终路径安装与日常切换

从最终Hub package路径构建日常载荷，核对来源projectRoot。隔离snapshot生成的载荷不能未经明确归属迁移就冒充最终日常包；原安装器的migrate-from只用于已验证的真实旧源交接，不能用来掩盖错误构建路径。

安装前记录目前installed版本、唯一入口检查和登记清单；有运行中的项目播放器时保持安装器拒绝替换。原子安装失败保留并核验原App；成功升级不保留旧可运行App，不承诺直接降级。安装不得强退官方应用。获准后沿用包现有安装器，再运行其只读check和Hub native-check，确认唯一规范入口、版本、指纹与归属。

切换验收不是再写一份PASS：使用该唯一实际安装App完成一次冷启动和一次热激活，保存/取消各一次并验证dispose；下一次日常启动再确认同一行为。若中间相关bytes变化，之前验收不能代表这个安装。维护者据这些证据确认本地日常使用范围，并把结果记入receipt。

## 6. 失败处置与支持期

| 触发 | 立即动作 | 恢复判据 |
|---|---|---|
| 覆盖层超过25s、无法输入、CSP阻断 | 可信同页dispose；无法连接则用户正常退出，官方入口重开 | 不再有owned遮罩，官方正常可用；保持失败分类 |
| 壁纸不兼容或图片失真 | 恢复外观；保存值保留 | 原生输入和surface恢复，不靠全局透明化补救 |
| 安装失败 | 保留安装器事务与当前包，不做路径通配删除 | read-only check识别有效原入口或精确待恢复状态 |
| 新版产品回归 | 立即用官方入口脱离；按详细设计§12做更高版本前向修复 | 修复包正常通过来源/版本门及受影响用例，不直接downgrade |
| 官方应用更新 | 暂停对新版本的兼容承诺，复查G3及相关G4 | 新精确版本有当前证据后更新支持矩阵 |

无后台watcher或自动重注入。支持排查顺序：实际官方版本/身份→当前控制器status与targetId→wallpaper分项→本轮事件/资源摘要；不要求用户上传聊天、完整payload或私有图。诊断日志沿用既有本地位置，维护者在本轮结论确认后清理不再需要的私有证据，不能为省空间删除仍用于恢复的owned receipt。

## 7. 最小生产回执

回执留在被忽略的本地evidence，公开只交脱敏摘要。字段：代码与工作树、固定构建input/产物摘要、原生签名和版本、真实宿主版本/macOS/架构、素材来源、G0–G6每门结果及证据、安装projectRoot/规范入口、冷/热/设置/恢复结果、性能观测、维护者决定、保留限制和下一次重验条件。

每门状态用`passed/failed/not_run/blocked/not_applicable`，not_applicable必须附理由且不能用于必需的G1–G5。只有G5及其所有前置passed才在限定范围写Production；分发许可未取得时G6=blocked并明确“本地使用，不对外分发”。不用一个全局passed掩盖真实宿主、视觉、安装或权利缺口。
