# Agent Skin 测试与功能验收

用户要求覆盖整个 `packages/agent-skin/` 的生产代码，UT 行覆盖率至少 95%。这是一项失败即阻断的验收条件；配置了门禁、测试数量增加或功能截图通过，都不表示已经达到覆盖率。

## UT 范围与判定

`tools/test-unit-coverage.py` 自动发现 JavaScript、Python、Swift、Bash 和 `.command` 生产源码。生产构建与安装工具、Pet 工具、原生适配器和新加入的源码都在统计范围内。测试程序、生成产物、私有素材和文档不进入生产代码分母。`wallpaper/preview.html` 是带自检按钮的合成宿主夹具，其独立交互脚本 `wallpaper/preview-controller.js` 也纳入 JavaScript 分母，由 `tools/preview-controller.unit.test.mjs` 在 Node 合成页面中执行计量；生产预览仍使用 `index.html` 加载已计入的独立 JS。CSS、HTML 标记和 JSON 配置没有可执行行覆盖率，分别通过浏览器、构建和功能用例验收。

每种语言及整个包都须达到 **95% 行覆盖率**。判定使用原始计数，不以四舍五入后的百分比放行；分支和函数统计可用于诊断，但不代替行覆盖率。缺失报告、漏算生产文件、工具失败或 UT 失败均阻断。Node LCOV、Coverage.py、LLVM 和 Bash 覆盖率保留各自原始结果；不把浏览器 E2E、实机启动或人工审阅混入 UT。

Swift 生成的固定 CDP JavaScript 也单独计量：Codex 的 10 段为 `generated/Native-Wallpaper.<expression>.js`，由当前源码编译出的 UT 程序导出，再由 Node VM 执行并测量。只执行 Swift 的字符串赋值不能算这些脚本的 UT。生成器、表达式和独立 JS 模块均不得漏算；缺少任何一段的执行报告会阻断。

启动载荷中的工厂接线和只读属性安装使用规范模块 `extension/bootstrap.mjs`，由生成器原样嵌入，并独立执行 UT。素材数据与模块调用包装不重复统计；生成器内部不得隐藏未经测量的手写函数。

被复制到临时夹具的 Python 源码，只有在执行前确认与规范源码字节相同后才合并覆盖率。发生源码修改的夹具不能冒充规范源码。Bash 通过实际源码和外部工具边界运行；测试不能改写生产命令路径后把副本算作规范源码。

在包目录运行：

```sh
python3 -m pip install coverage==7.16.2 Pillow==12.3.0
python3 -B tools/test-setup-unit-tools.py
python3 -B tools/test-coverage-policy.py
python3 -B tools/test-functional-verdict.py
python3 -B tools/test-unit-coverage.py
```

需要 macOS 的 AppKit、WebKit、Xcode 命令行工具及 Node 24；Pet UT 还需 `Pillow==12.3.0`。工具准备脚本将固定版本 GNU Bash 5.2.37 和 Bashcov 1.7.0 放入忽略的 `.build/`，不会替换系统 Bash/Ruby 或安装 Homebrew 包。覆盖率工具仅用于开发测试，不是用户应用依赖。`--language javascript|python|swift|shell` 用于单组开发复验，只证明该组，不能用它宣称整个包通过。最新报告在 `.build/unit-coverage/report.json`，每次运行的报告和证据保存在 `.build/unit-coverage/runs/` 下；报告为失败时不得写“UT 95% 已完成”。

## 功能用例

每项都规定触发、期望和验收入口。模拟或单元测试通过不自动关闭实机验收。

| ID | 触发与操作 | 期望 | 自动看护 / 实机验收 |
|---|---|---|---|
| FT-LOCALE | 官方页面英文、浏览器语言中文；切换官方页面语言 | 页面语言优先；文案、bot、设置和动画同步，不新增语言偏好 | `localization.test.mjs`、`startup.test.mjs`、生成载荷浏览器测试；实机观察官方界面 |
| FT-FINDER | 按当前 macOS 语言查看已安装应用；检查中英资源 | 英文显示 `Azhou AI Lab for Codex`，中文显示主题指定名称；真实安装文件名不充当本地化结论 | `test-startup-build.py` 的 Bundle 回退名与本地化资源；`test-installed-acceptance.py` 的 Finder API；真实 Finder 窗口检查 |
| FT-DOCK | 将旧版固定到 Dock，升级后再查看标签和启动目标 | 标签符合 macOS 语言，只启动唯一新入口；旧固定项或缓存不能算新版本已通过 | 安装归属 UT；Dock 实际标签与目标需现场验收。没有入口时保留 pending，不能以空列表通过 |
| FT-ICON-IDENTITY | 使用已批准的源图 SHA-256 构建，分别在预检前和预检后换入同尺寸的图 | 正确摘要生成经校验的暂存图，替换图被拒绝，原载荷保留 | preflight UT 与真实构建命令的隔离用例。实际 Dock 图案、标签和点击按 FT-DOCK 现场核对 |
| FT-COLD-PROTOCOL | 模拟宿主打开、身份校验、工作区就绪、取消和迟到事件 | 只有绑定的当前运行可完成；切换应用或 Space 立即中断；观察器和窗口只清理一次，迟到事件不复活播放器 | `StartupNativeTests.swift` 的生产 driver/transport UT；不证明真实窗口可见 |
| FT-COLD-WINDOW-ORDER | 在真实 macOS 桌面创建自有遮罩，随后创建普通宿主夹具窗口，再显露播放器并释放 | 普通层级负对照被后来的窗口盖住；生产遮罩在显露前后均排在宿主前；同一 WKWebView 从隐藏变为显示，封面移除；前台 PID 不变；释放后自有窗口消失 | `test-startup-payload-browser.py --native-window-ordering`，在 macOS CI 必跑；合成窗口不证明完整冷启动的屏幕连续性 |
| FT-COLD | 用户完整退出官方宿主，再从阿舟入口启动 | 恰好一次动画；有效保存的外观快照生效；工作区就绪后交接；禁用壁纸或明确降级可进入；没有第二个宿主 | `test-installed-acceptance.py --cold-start` 加同一安装候选的全屏幕连续录制与视觉审阅；技术完成仍为 pending |
| FT-COLD-SHELL | 首个绑定页尚无支持的外壳；随后同页挂载外壳，或连接失效后出现可证明的唯一后继页 | 外壳未就绪时零安装；每页自行返回严格就绪字段。后继页沿用完整退休证明并等待自己的外壳；取消、未知字段、身份漂移和预算不足均不发送载荷 | `StartupNativeTests.swift` 的生产 connector/transport 夹具与编译后 inspect 表达式的 Node VM 用例；实机连续播放仍按 FT-COLD 验收 |
| FT-COLD-REPLACE | Codex 接入期间在 inspect、安装回复、loading 或已 ready 的 playing 轮询阶段销毁初始主页面，并在同一进程和端口创建唯一新主页面 | 只有完整目标清单证实旧 target 已消失、进程启动身份及独占回环端口未变时才接续；每个 target 最多安装一次，新页必须自行提供安装回执与状态；旧页存活、歧义、普通协议错误、取消和已完成 run 不触发重播 | `StartupNativeTests.swift` 的生产 transport/connector/event capture 夹具、playing 重叠后换页并完成的回归、拒绝与取消矩阵；真实冷启仍按 FT-COLD 单独验收 |
| FT-LIFECYCLE | Codex、DSH 正常完成；就绪前后页面移除浮层；设置浮层或 DSH 嵌入面板被移除 | 正常完成保持成功；Codex 原生遮罩与 DSH document gate 只清理自有资源；嵌入面板只清理和通知一次 | Native/Node 两宿主行为回归；DSH 无有效 gate 时的壁纸重新应用及全屏幕冷启仍单独实机验收 |
| FT-PLAYBACK-TIMEOUT | 动画已 ready 但播放未结束，25 秒 watchdog 到期；宿主导航已存在或随后挂载；点击恢复的外观入口 | 保留 overlay-timeout、completed=false 和空 completion；释放旧浮层，布局可用时显示同一入口；点击只创建新的 settings run，不重播。未 ready、素材失败或已释放的控制器仍拒绝；旧 frame、run 消息和 watchdog 不得影响新设置会话 | `startup.test.mjs` 的超时与迟到消息回归；`test-startup-browser.mjs` 的实际动画准备、watchdog 边界、入口顺序/几何、真实点击、取消及焦点/inert 清理。合成定时器不证明锁屏视觉或自然播放完成 |
| FT-HOT | 官方宿主保持运行，再打开阿舟入口 | 激活同一 PID；不重播、不覆盖控制器、不退出宿主 | 原生事件 UT；实机对照前后 PID、事件和页面 |
| FT-LATE-SHELL | 页面外壳晚于 12 秒动画出现 | 动画准时结束，壁纸继续等待并生效，不重播动画 | `startup.test.mjs`、`test-startup-browser.mjs` 的生成载荷延迟场景 |
| FT-SHELL-TIMEOUT | 60 秒内始终没有支持的页面外壳 | 返回 `shell-timeout`；临时观察器清理；不伪造成功 | 生成载荷完整超时测试 |
| FT-CANCEL | 等待或解码时跳过、重新开始、禁用或释放 | 旧请求失效；迟到回调不能重装背景或复活控制器 | 控制器与渲染器 UT、浏览器取消/乱序测试 |
| FT-RETRY | 壁纸失败后重试；并发重试；健康状态重复调用 | 最多一个尝试、10 秒上限；保留已过滤的先前原因；不重播动画；健康状态只复查 | 控制器及编译后的 helper 表达式测试 |
| FT-SURFACES | 深浅色、窄窗、CSP 拒绝图片或样式、未知遮罩 | 真实图片解码；保留输入框、菜单和代码块；失败可见；未知层不被擅自清除 | 渲染器 UT、CSP/布局浏览器测试；实机检查裁切、人物及文字可读性 |
| FT-SETTINGS | 保存/取消/恢复草稿、并发冲突、配额或超时、强度为零；查看运行版本；窄窗、短窗用 Tab 遍历设置；内嵌呈现（#382）的保存保持打开、Escape 归还焦点、无焦点陷阱 | 保存成功才应用；取消保留旧值；失败可恢复；零强度关闭背景；标题下版本与运行载荷一致；键盘焦点环可见且不被底部操作栏遮挡；独立覆盖层保持模态与焦点隔离，`settings.section` 内嵌为非模态且仅随宿主卸载移除 | `image-settings.test.mjs`、存储浏览器测试、保存与草稿预览及生成载荷版本显示场景、`test-startup-browser.mjs` 的受限视口设置键盘矩阵；内嵌行为由 `image-settings.test.mjs`/`animation.unit.test.mjs` 内嵌用例与 DSH embed 生命周期浏览器检查（frameSpec `presentation` 断言）覆盖，真面板 section 实体键盘矩阵随 DSH 实机 e2e 验收 |
| FT-SIDEBAR | 动画期间跳过，Home 导航可见或不可用；加载层覆盖页面控件；更新下载按钮、输入区或头像出现；侧栏滚动、窄窗或导航重建 | 宿主尚无可见且可命中的页面控件时，Appearance 保持隐藏。仅有几何可见但被加载层遮挡的控件不算就绪；覆盖层移除后重试。唯一可见的 Your dot 出现时（包括数字和无障碍未读提示出现、改变及清除），入口在 Home 导航正常流中紧随其后、位于 Pinned 前，并保留 6 像素上间距；Home 不可用但宿主控件可交互时，使用避开控件、输入区和 composer 的备用位置。无空位时暂时隐藏，空位恢复后重新显示 | `startup.test.mjs`、`test-startup-browser.mjs` 的直接按钮与列表包装结构、未读提示出现/清除、早期跳过、遮挡恢复、重复候选、导航重建、碰撞、入口点击和窄栏场景；合成场景不证明官方 DOM 或同一运行版本的真实宿主位置，须现场验收 |
| FT-INSTALL | 旧名称升级、跨来源接管、失败中断后重试、未知同名应用 | 先验证新入口；保留归属与签名边界；唯一实体和登记；未知对象不被删除 | `test-install-macos.py`、构建 UT、实际 `install-macos.py --check` |
| FT-ASSETS | 缺图、非法路径、符号链接、错误尺寸、旧构建输入 | 构建拒绝并保留原有效入口；私有素材不进入 Git | preflight、构建器、校验器、资源处理及 shell UT |
| FT-ACCEPT-ARM | 挂机离线验收：逐文件核对全部钉点面（含探针 EXPECTED 等工具自带基线）、运行目录 0700、TCC 消毒（`env -i` 逐触面可读、监督链零 `~/Desktop` 依赖）、LaunchAgent 存活心跳 | 任一旧指纹字面量零命中；裸环境可读全部触面；心跳按周期跳动且存活超 2 分钟 | `acceptance-harness.test.mjs` |
| FT-ACCEPT-RUN | 用户退出日常宿主后监督链自动执行：隔离实例 → 只读探针确认主页面 → CDP 页面截图（URL 带 `?locale=` 查询串）→ 生产 UI 十步 | 探针 exit 0 且唯一主页面；截图为有效 PNG；UI 十步全绿 exit 0 | `acceptance-harness.test.mjs` 的 E2E 切片（`/json` 带查询串端到端解析）；全链按 runbook 实机执行 |
| FT-ACCEPT-CLOSEOUT | 验收失败路径：预检拒绝、UI 中途失败、宿主丢失 | 每次失败都落盘 STATUS/HOST-CLOSEOUT/PIPELINE-DONE 并自动重开宿主；退避在收尾之后；截图在盖章前必须经操作者事后审阅 | `acceptance-harness.test.mjs` 的幂等目录与错误码契约；closeout 语义按 runbook 复苏清单人工核对 |

Finder/Dock 使用 **macOS 语言**；注入的动画和外观使用 **官方宿主页面语言**。这两条合同分别验收，不能用应用内按钮为英文推断 Finder/Dock 已通过。

## 冷启动防回归门禁

从包目录执行生成载荷、原生窗口与浏览器功能回归：

```sh
python3 -B tools/test-startup-payload-browser.py --native-window-ordering --out .local/startup-functional-001
```

每次使用新的输出目录；工具拒绝已存在的目录及符号链接，保留失败运行供复核。默认 `test-startup-native.py` 只运行协议、握手和表达式检查；真实窗口探针必须显式启用，不进入 UT 覆盖率。

原生功能报告必须包含四组唯一的窗口观测与两组释放观测，并绑定编译输入和二进制摘要。窗口标识、前台 PID 和 WindowServer 排序必须实际可读；缺少桌面或观测、空输出、仅有成功摘要、重复/矛盾记录、非零退出和源码漂移均不能通过。生成载荷浏览器报告也须包含实际通过的必需用例，不能仅凭子进程退出码放行。CI 保留隔离夹具的报告和原始输出，不上传本机录屏。

| 反复出现的漏测 | 固定看护 |
|---|---|
| 绘制已提交，但窗口被宿主盖住 | 真实窗口前后顺序、普通层级负对照 |
| 显露函数被改成空操作，窗口排序仍正确 | 同一 WKWebView 的隐藏状态与封面移除 |
| 切换应用后遮罩仍留着，或迟到事件复活播放器 | 原生中断/取消 UT、观察器释放与真实窗口消失 |
| 成功日志混有失败、数量字段使用布尔值、借用其他入口回执 | 安装验收谓词及完整 `check()` 的拒绝用例 |
| 子进程什么也没测却返回 0，或复用旧报告 | 严格观测集合、必需浏览器用例、新证据目录、输入摘要前后比对 |
| 技术检查通过就宣称肉眼体验正常 | `test-functional-verdict.py` 保证完整技术成功仍为 `pending-visual-review`，整体不通过 |

仓库 UT `tests/test_agent_skin_native_window_guard.py` 看护功能运行器和证据边界；包级 `test-functional-verdict.py` 看护安装验收。DSH 的 document gate、取消、迟到存储结果与正常清理继续由 `startup.test.mjs` 和生成载荷浏览器用例覆盖；真实 DSH 桌面首帧仍按同版安装证据单独验收。

## 实机执行与保留项

```sh
# 只读检查当前安装、Finder API、Dock 条目和壁纸；不启动或退出官方宿主。
python3 -B tools/test-installed-acceptance.py --out .local/functional-acceptance-001

# 先由用户保存工作并完整退出官方宿主，再执行。
# 脚本发现宿主仍在运行就保留 pending，不自动退出或重启它。
python3 -B tools/test-installed-acceptance.py --cold-start --out .local/cold-acceptance-001
```

实机报告明确标记 `unitCoverageInput: false`。每次更换输出目录，已有目录或符号链接会在执行任何检查前被拒绝。Dock 没有固定入口、冷启动未执行或尚缺视觉审阅都不能输出全通过。报告包含当前检查结果和日志路径；历史截图或旧 build 记录不能替代当前安装的结果。

共用生命周期改动走 FT-LIFECYCLE 两宿主检查。实机回执按宿主、运行模式和候选载荷分别记录。DSH Web 隔离配置能验证插件启动和设置交互，桌面模式另行验收。

Codex 的真实冷启动路径由原生 driver 持有一次运行的 nonce、绝对 deadline、cover/playback 终态和当前 workspace 观测。入口先作 bundle 签名预检，再提交并显示自有 cover，之后启动或接入 Codex。准备阶段沿该 deadline 只读检查进程和端口，校验绑定的页面身份与支持外壳；设置由页面控制器固定导出为一份带摘要、有限大小的快照，再传给原生本地播放器。播放器沿用 12 秒动画；workspace 身份、外观入口、壁纸 disposition 与动画终态独立观察。只有自然完成且当前 workspace 已验证时才揭开宿主；用户跳过或关闭会立即释放自有窗口，异常和 deadline 会退出而不终止 Codex。热启动保持只激活。

原生 `coverDrawCommitted` 只表示 AppKit 提交绘制事务，不证明屏幕已经显示它，也不能替代全屏幕录制判断对话页是否先露出。新的 `startup-native-result` 绑定 run nonce、target PID、当前 page target、workspace run 和壁纸状态。完成、跳过、中断、失败分别输出；只有完成且入口路径匹配可作为原生冷启动协议完成。合成窗口功能报告与安装事件报告均保持 `visualContinuity: not-measured`，直到安装了同一候选的实机录屏被人工复核。

Codex 的主页面接续仅在本次尚未结束的接入操作内生效，始终使用原总 deadline 和同一进程操作锁，不增加常驻观察器。请求中断本身不证明页面已销毁；已核实 ready 的 `playing` 轮询中，若所选 target ID 和 socket 仍匹配且与候选主页面重叠，也只进入同一退休证明。首次选页、安装前、`settings` 和终态歧义仍拒绝；先经过暂态清单等待时，仍按同页证明规则中断，不借重叠恢复。Foundation WebSocket 握手的 `NSURLErrorDomain/-1011` 且实际 HTTP 状态为 404 或 500 时，仅允许进入替换证明，不以状态码认定页面已退休；401、其它状态和缺失响应仍拒绝；旧 target 从完整清单消失也可能滞后于连接失败，等待期间只做有界只读清单复核（进程与端口验证不变），旧 ID 尚在时不连接、安装或释放任何候选页，预算耗尽仍未消失则按 attach-timeout 拒绝。同一 target 的导航、控制器缺失或 run ID 漂移仍按中断处理。已观测到完成、跳过、失败或释放后不重新安装。安装发送总计不因换页清零，回复丢失仍保留未知安装状态；安装、就绪和跳过事件中的 `pageTargetID` 区分同一 PID 下重新从 run ID 1 开始的页面。确认就绪或已完成状态时，重新核对唯一当前 target；失败、超时和已释放状态直接结束，不进入换页接续。`playing` 就绪会通知原生窗口激活，但不结束接入；继续使用同一时限、进程锁和替换证明，直到自然完成、用户跳过或进入设置。进入设置即交还用户，不等待用户编辑，也不要求壁纸启用。播放始终未完成时按原预算超时，不延长 deadline；返回之后再发生的页面替换不属于本机制。动画控制器就绪和官方外壳可交互分别判断，不以固定等待或壁纸是否启用充当页面稳定证明。需要对单次真实冷启分类失败时，仅为该次启动设置环境变量 `AZHOU_STARTUP_DIAGNOSTICS=1`：启动器经既有日志通道追加有界且无内容的诊断记录（操作阶段、单调时间、页面 ID、原始传输错误 domain/code、存在时的 HTTP 状态、失败发生阶段与 pageConnectionLost 分类、复核清单的旧 ID 在场与合格主页面数）。该设施默认关闭，不改变公开失败类别，也不记录表达式、载荷或完整清单。

同一 opt-in 开关也区分 `target-opened` 之前的身份拒绝。整个打开回调与本次 system.validate 的诊断先暂存在本地，在成功/拒绝已经裁定后一次写入 `bounded-open` 记录的 `checks` 数组（当前有限路径至多 11 项）；动态属性读取、fresh process 查询与命令核验之间不做日志 I/O，post-open-facts 也只在自身裁定结束后写一次。`callback-identity` 记录系统打开回调的实际短路 guard；`system-validation` 保留原始固定 `WallpaperFailure.state` / `StartupFailure.reason` 与 NSError domain/code；其下 `target-input`、`process-facts-initial`、`launch-time`、`process-facts`、`ps-identity`、`signature` 标识本次实际裁定的快照或命令检查；`post-open-facts` 区分回调通过后字段再消失的情况。字段仅含固定标签、单调时间、已实际读取的 PID、字段存在与匹配布尔值，未执行的短路条件省略；PID 尚未读取时标记 `pidObserved=false`，不为补齐日志再次查询。关闭时不额外读取动态属性或诊断时钟；开启时不增加身份查询、命令、启动次数、延时或重试，也不改变 guard 与公开失败类别。诊断 environment 是本次 validate 的值副本，不向后续 connector 核验泄漏 sink。原始命令、路径、URL、异常描述、userInfo 与用户内容均不记录。原生回归经 bounded-open 的 existential 接口执行 production target system，比较开关两侧的结果、getter/系统调用次序与次数，并覆盖迟后字段缺失、各底层检查及超时映射。诊断结果只用于定位，不能宣称修复了真实启动失败。

就绪复查只对 `NSURLErrorDomain` 的 `timedOut`、`networkConnectionLost`、`cannotConnectToHost` 做原预算内的只读重试，间隔至多 150 毫秒，每轮仍复核进程启动身份和端口归属。HTTP 错误、重定向、响应大小或结构不合规不因复查而放行；已完成或跳过的 run 不进入等待。首次状态读取通过当前 CDP 会话持有控制器对象引用，不新增页面 global，断开或换页即清除，捕获与请求返回还须匹配原连接 generation，迟到回复不能把旧 objectId 写入新连接。等待后必须重新确认同一主页面、同一控制器和 run 的最新状态，不能使用等待前的 ready 快照；同页新控制器即使从 run ID 1 开始也按中断处理，不能释放新对象。异常清理也使用已持有的对象引用，在一次 CDP 调用内核对当前 global 与原对象相同后才释放；没有绑定证据时不重新捕获或清理当前对象。等待期间页面变化保守返回 partial，不借暂态清单故障授权重装；没有等待的既有页面换代路径仍按完整旧 ID 缺席证明处理。`StartupNativeTests.swift` 覆盖单次与永久故障、身份/端口/页面/run 变化、取消和终态；两个新增固定表达式由 Node VM 执行同对象与替换对象负例并计入覆盖率。

启动接入的 discovery、replacement proof 与当前页 recheck 每轮仍新读进程/启动时间、ps 用户和执行路径、listener，并检查取消和同一绝对 deadline；这些只读轮询不重复完整 codesign。`validateProcess` 是真正的 `StartupTargetSystem` requirement，保留旧 adapter 的完整验证默认实现，production existential 才能派发到仅验证进程的方法。完整签名/ownership 保留在 operation lock 后首次发现之前、每个选定页面连接之前、每个页面最终同页 proof 之后立即发送载荷之前；异常 cleanup 的完整验证也保留。没有跨轮缓存成功签名，也没有改变换页证明、controller identity 或终态重播规则。独立 wallpaper apply/retry/restore 的三处旧 extension 调用改为显式完整 validate，保留它们原来实际执行的签名边界。生产 environment 注入回归统计真实 codesign 命令，证明单页成功固定 3 次、替换后的每代连接与安装各自验证、轮询次数不增加扫描，并覆盖边界拒绝、身份/端口/取消/预算变化和独立操作完整验证。控制器 capture 测试通过明确的 suspension 通知同步，不再使用一秒 wall-clock 忙等。

宿主布局回归以脱敏的实际结构为依据：核对目标控件、影响可见性和尺寸的祖先样式、滚动容器与重建行为，不复制聊天内容。合成夹具需断言目标顺序和实际几何；选择器命中或备用入口可见不能代替目标位置通过。早期跳过回归会延迟挂载合成 app shell，并验证可交互控件到达后备用入口恢复；它不证明官方加载画面的 DOM 时序。交付分别记录测试载荷版本、安装版本和页面实际运行版本；实机结果仅在同版页面检查后判定，无法核实时保持待验收。

`CI / Agent Skin full production UT coverage` 运行完整 UT 门禁，并进入聚合 Required 判定；macOS Startup and Pet 作业必跑生成载荷浏览器及真实窗口功能回归。仓库通用 `python3 scripts/verify.py` 仍执行其原有完整检查，不能替代本页的包级覆盖率命令。提交/推送状态与远端 CI 结果另行报告，不因本地通过而推断远端已通过。


## P08 isolated source-library developer checks

`tools/theme-library.py` is an explicit-root developer CLI, not an installed host capability. Its original-ZIP import/list/read contract and failure boundaries are documented in [the source-library design](theme-source-library.md). Run `python3 -B tools/test-production-theme-package-preflight.py`, `python3 -B tools/test-production-theme-library.py` and `node --test tools/dream-theme-validator.test.mjs` in the existing Node/Pillow development environment. The dependency-equipped macOS repository gate and CI register these suites. `test-unit-coverage.py` discovers the production suites; no whole-package 95% result is inferred from their standalone success. Contract fixtures are synthetic and do not establish external-theme compatibility, visual acceptance, CSS mapping or permission to apply a theme.

The source-stage literal-paint adapter and lossless capsule boundary run through `python3 -B tools/test-production-dream-style.py`, registered in repository verification and macOS CI. It checks fixed AST derivation, pristine validator corpus parity, total source-order mapping, unsupported-field rejection, exact file bytes/hashes, duplicate-key/UTF-8 bounds, static-image checks and cancelled decoding. Settings and live application are not yet covered by this source-stage suite.


## P08 imported source UI and tagged transport candidate

The current candidate has a real settings file-input path and an independent `dreamThemes` record. `node tools/test-image-settings-browser.mjs --out NEW_DIRECTORY` runs isolated Chrome plus real IndexedDB and a self-authored original ZIP through the actual library CLI/capsule/UI import flow. `AZHOU_TEST_PYTHON` may select the existing Pillow-equipped interpreter; no dependency installation occurs. Output directories must be fresh. It proves directory persistence/reopen, same-source idempotency, text-only names, retained startup drafts, unchanged active records/paint, and disabled application when no trusted host callback is available. The extra Dream-section screenshot records actual controls/focus. It does not exercise a real Codex host.

`python3 -B tools/test-startup-native.py` extends the existing production bridge: original ZIP→library/capsule→canonical settings snapshot→compiled Swift receiver and transfer expressions→animation receiver. It covers bundled and original PNG/JPEG/WebP, and a legal large ancillary PNG above the old artwork URL limit. It uses existing Node/Pillow development dependencies. Native checks are injected host facts/transport only, with no real open/kill. Unknown active schemas, source loss/tampering, actual image hashes, MIME/length/numeric-plan bounds, and old legacy byte limits remain failure gates. The finite wire does not prove full Dream CSS compatibility, an installed host, rollback or a whole-package 95% coverage result.

### First-profile explicit Dream application

The generated startup browser check `generated Dream source UI applies literal main paint and restores the saved Azhou appearance` exercises the visible CLI-capsule/file-input/directory/Apply/fresh-startup/Restore loop. It asserts actual main computed colors, main `background-image:none`, original body artwork, alpha-composition screenshot pixels, retained unsaved startup drafts, and rollback after activated-candidate quota, independent-IDB-connection conflict and cancellation. Quota is an injected DOMException at the real write boundary, not exhausted user storage. Renderer unit tests additionally cover retained incumbent resources, bundled-mask rollback, foreign/new owners, workspace replacement and idempotent finalize/rollback. Settings tests cover four-record CAS, pending-read/put cancellation/disposal/timeouts, exact-commit compensation and monotonic restoration. Synthetic/generated checks do not establish installed Codex/IME acceptance, external theme media permission, full Dream engine parity or whole-package 95% unit coverage.
