# Agent Skin 测试与功能验收

用户要求覆盖整个 `packages/agent-skin/` 的生产代码，UT 行覆盖率至少 95%。这是一项失败即阻断的验收条件；配置了门禁、测试数量增加或功能截图通过，都不表示已经达到覆盖率。

## UT 范围与判定

`tools/test-unit-coverage.py` 自动发现 JavaScript、Python、Swift、Bash 和 `.command` 生产源码。生产构建与安装工具、Pet 工具、原生适配器和新加入的源码都在统计范围内。测试程序、生成产物、私有素材、文档和测试夹具不进入生产代码分母。`wallpaper/preview.html` 是带自检按钮的合成宿主测试夹具；生产预览使用 `index.html` 加载已计入的独立 JS。CSS、HTML 标记和 JSON 配置没有可执行行覆盖率，分别通过浏览器、构建和功能用例验收。

每种语言及整个包都须达到 **95% 行覆盖率**。判定使用原始计数，不以四舍五入后的百分比放行；分支和函数统计可用于诊断，但不代替行覆盖率。缺失报告、漏算生产文件、工具失败或 UT 失败均阻断。Node LCOV、Coverage.py、LLVM 和 Bash 覆盖率保留各自原始结果；不把浏览器 E2E、实机启动或人工审阅混入 UT。

Swift 生成的固定 CDP JavaScript 也单独计量：Codex 的 10 段为 `generated/Native-Wallpaper.<expression>.js`，ZCode 的状态与释放两段为 `generated/Native-ZCodeRuntime.<expression>.js`。前者由当前源码编译出的 UT 程序导出；后者从完整规范源码编译的测试程序发给自有合成 CDP 服务的 `Runtime.evaluate` 请求捕获原字节，绑定源码与输出 SHA，再由 Node VM 执行并测量。只执行 Swift 的字符串赋值不能算这些脚本的 UT。生成器、表达式和独立 JS 模块均不得漏算；缺少任何一段的执行报告会阻断。

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

每项都规定触发、期望和验收入口。模拟或单元测试通过不自动关闭实机验收。ZCode 盖章证据还必须由同轮宿主 `observations` 严格导出两项能力声明，`tools/acceptance-declarations.test.mjs` 和 `tools/test-ship-zcode.py` 只验证验证器在合成记录上的可观察行为；只有真实监督链及截图、设置持久化证据均可追溯时才能宣称宿主通过。

| ID | 触发与操作 | 期望 | 自动看护 / 实机验收 |
|---|---|---|---|
| FT-LOCALE | 官方页面英文、浏览器语言中文；切换官方页面语言 | 页面语言优先；文案、bot、设置和动画同步，不新增语言偏好 | `localization.test.mjs`、`startup.test.mjs`、生成载荷浏览器测试；实机观察官方界面 |
| FT-FINDER | 按当前 macOS 语言查看已安装应用；检查中英资源 | 英文显示 `Azhou AI Lab for Codex`，中文显示主题指定名称；真实安装文件名不充当本地化结论 | `test-startup-build.py` 的 Bundle 回退名与本地化资源；`test-installed-acceptance.py` 的 Finder API；真实 Finder 窗口检查 |
| FT-DOCK | 将旧版固定到 Dock，升级后再查看标签和启动目标 | 标签符合 macOS 语言，只启动唯一新入口；旧固定项或缓存不能算新版本已通过 | 安装归属 UT；Dock 实际标签与目标需现场验收。没有入口时保留 pending，不能以空列表通过 |
| FT-ICON-IDENTITY | 使用该宿主已批准的源图 SHA-256 构建，分别在预检前和预检后换入同尺寸的图，并用 Codex 摘要启动 ZCode 构建 | 正确摘要生成经校验的暂存图，替换图或宿主串图被拒绝，原载荷保留 | preflight UT 与真实构建命令的隔离用例。实际 Dock 图案、标签和点击按 FT-DOCK 现场核对 |
| FT-COLD | 用户完整退出官方宿主，再从阿舟入口启动 | 恰好一次冷启动、控制器就绪、动画结束和壁纸生效；没有第二个宿主 | 原生协议 UT、生成载荷测试；`test-installed-acceptance.py --cold-start` 加视觉审阅 |
| FT-COLD-REPLACE | Codex 接入期间在 inspect、安装回复或 loading 轮询阶段销毁初始主页面，并在同一进程和端口创建唯一新主页面 | 只有完整目标清单证实旧 target 已消失、进程启动身份及独占回环端口未变时才接续；每个 target 最多安装一次，新页必须自行提供安装回执与状态；旧页存活、歧义、普通协议错误、取消和已完成 run 不触发重播 | `StartupNativeTests.swift` 的生产 transport/connector/event capture 三阶段夹具、拒绝与取消矩阵；真实冷启仍按 FT-COLD 单独验收 |
| FT-LIFECYCLE | Codex、ZCode、DSH 正常完成；就绪前后页面移除浮层；设置浮层或 DSH 嵌入面板被移除；ZCode 收到终态失败 | 正常完成保持成功；浮层丢失撤销就绪并释放宿主；嵌入面板只清理和通知一次；原生等待不越过终态继续接受就绪 | macOS Required 路径中的三宿主浏览器回归与 ZCode 原生协议夹具 |
| FT-PLAYBACK-TIMEOUT | 动画已 ready 但播放未结束，25 秒 watchdog 到期；宿主导航已存在或随后挂载；点击恢复的外观入口 | 保留 overlay-timeout、completed=false 和空 completion；释放旧浮层，布局可用时显示同一入口；点击只创建新的 settings run，不重播。未 ready、素材失败或已释放的控制器仍拒绝；旧 frame、run 消息和 watchdog 不得影响新设置会话 | `startup.test.mjs` 的超时与迟到消息回归；`test-startup-browser.mjs` 的实际动画准备、watchdog 边界、入口顺序/几何、真实点击、取消及焦点/inert 清理。合成定时器不证明锁屏视觉或自然播放完成 |
| FT-HOT | 官方宿主保持运行，再打开阿舟入口 | 激活同一 PID；不重播、不覆盖控制器、不退出宿主 | 原生事件 UT；实机对照前后 PID、事件和页面 |
| FT-LATE-SHELL | 页面外壳晚于 12 秒动画出现 | 动画准时结束，壁纸继续等待并生效，不重播动画 | `startup.test.mjs`、`test-startup-browser.mjs` 的生成载荷延迟场景 |
| FT-SHELL-TIMEOUT | 60 秒内始终没有支持的页面外壳 | 返回 `shell-timeout`；临时观察器清理；不伪造成功 | 生成载荷完整超时测试 |
| FT-CANCEL | 等待或解码时跳过、重新开始、禁用或释放 | 旧请求失效；迟到回调不能重装背景或复活控制器 | 控制器与渲染器 UT、浏览器取消/乱序测试 |
| FT-RETRY | 壁纸失败后重试；并发重试；健康状态重复调用 | 最多一个尝试、10 秒上限；保留已过滤的先前原因；不重播动画；健康状态只复查 | 控制器及编译后的 helper 表达式测试 |
| FT-SURFACES | 深浅色、窄窗、CSP 拒绝图片或样式、未知遮罩 | 真实图片解码；保留输入框、菜单和代码块；失败可见；未知层不被擅自清除 | 渲染器 UT、CSP/布局浏览器测试；实机检查裁切、人物及文字可读性 |
| FT-SETTINGS | 保存/取消/恢复草稿、并发冲突、配额或超时、强度为零；查看运行版本；窄窗、短窗用 Tab 遍历设置 | 保存成功才应用；取消保留旧值；失败可恢复；零强度关闭背景；标题下版本与运行载荷一致；键盘焦点环可见且不被底部操作栏遮挡 | `image-settings.test.mjs`、存储浏览器测试、保存与草稿预览及生成载荷版本显示场景、`test-startup-browser.mjs` 的受限视口设置键盘矩阵 |
| FT-SIDEBAR | 动画期间跳过，Home 导航可见或不可用；加载层覆盖页面控件；更新下载按钮、输入区或头像出现；侧栏滚动、窄窗或导航重建 | 宿主尚无可见且可命中的页面控件时，Appearance 保持隐藏。仅有几何可见但被加载层遮挡的控件不算就绪；覆盖层移除后重试。唯一可见的 Your dot 出现时（包括数字和无障碍未读提示出现、改变及清除），入口在 Home 导航正常流中紧随其后、位于 Pinned 前，并保留 6 像素上间距；Home 不可用但宿主控件可交互时，使用避开控件、输入区和 composer 的备用位置。无空位时暂时隐藏，空位恢复后重新显示 | `startup.test.mjs`、`test-startup-browser.mjs` 的直接按钮与列表包装结构、未读提示出现/清除、早期跳过、遮挡恢复、重复候选、导航重建、碰撞、入口点击和窄栏场景；合成场景不证明官方 DOM 或同一运行版本的真实宿主位置，须现场验收 |
| FT-INSTALL | 旧名称升级、跨来源接管、失败中断后重试、未知同名应用 | 先验证新入口；保留归属与签名边界；唯一实体和登记；未知对象不被删除 | `test-install-macos.py`、构建 UT、实际 `install-macos.py --check` |
| FT-ASSETS | 缺图、非法路径、符号链接、错误尺寸、旧构建输入 | 构建拒绝并保留原有效入口；私有素材不进入 Git | preflight、构建器、校验器、资源处理及 shell UT |
| FT-ACCEPT-ARM | 宿主指纹漂移后重钉并挂机离线验收：逐文件核对全部钉点面（含探针 EXPECTED 等工具自带基线）、运行目录 0700、TCC 消毒（`env -i` 逐触面可读、监督链零 `~/Desktop` 依赖）、LaunchAgent 存活心跳 | 任一旧指纹字面量零命中；裸环境可读全部触面；心跳按周期跳动且存活超 2 分钟 | `acceptance-harness.test.mjs`；挂机清单按 [offline-acceptance-runbook.md](offline-acceptance-runbook.md) 逐项执行 |
| FT-ACCEPT-RUN | 用户退出日常宿主后监督链自动执行：隔离实例 → 只读探针确认主页面 → CDP 页面截图（URL 带 `?locale=` 查询串）→ 生产 UI 十步 | 探针 exit 0 且唯一主页面；截图为有效 PNG；UI 十步全绿 exit 0 | `acceptance-harness.test.mjs` 的 E2E 切片（`/json` 带查询串端到端解析）；全链按 runbook 实机执行 |
| FT-ACCEPT-CLOSEOUT | 验收失败路径：预检拒绝、UI 中途失败、宿主丢失 | 每次失败都落盘 STATUS/HOST-CLOSEOUT/PIPELINE-DONE 并自动重开宿主；退避在收尾之后；截图在盖章前必须经操作者事后审阅 | `acceptance-harness.test.mjs` 的幂等目录与错误码契约；closeout 语义按 runbook 复苏清单人工核对 |

Finder/Dock 使用 **macOS 语言**；注入的动画和外观使用 **官方宿主页面语言**。这两条合同分别验收，不能用应用内按钮为英文推断 Finder/Dock 已通过。

## 实机执行与保留项

```sh
# 只读检查当前安装、Finder API、Dock 条目和壁纸；不启动或退出官方宿主。
python3 -B tools/test-installed-acceptance.py --out .local/functional-acceptance

# 先由用户保存工作并完整退出官方宿主，再执行。
# 脚本发现宿主仍在运行就保留 pending，不自动退出或重启它。
python3 -B tools/test-installed-acceptance.py --cold-start --out .local/cold-acceptance
```

实机报告明确标记 `unitCoverageInput: false`。Dock 没有固定入口、冷启动未执行或尚缺视觉审阅都不能输出全通过。报告包含当前检查结果和日志路径；历史截图或旧 build 记录不能替代当前安装的结果。

共用生命周期改动走 FT-LIFECYCLE 三宿主检查。实机回执按宿主、运行模式和候选载荷分别记录。DSH Web 隔离配置能验证插件启动和设置交互，桌面模式另行验收。ZCode 回执目录与 Electron 用户配置是两个不同的隔离边界。

Codex 的主页面接续仅在本次尚未结束的接入操作内生效，始终使用原总 deadline 和同一进程操作锁，不增加常驻观察器。请求中断本身不证明页面已销毁；Foundation WebSocket 握手的 `NSURLErrorDomain/-1011` 且实际 HTTP 状态为 404 或 500 时，仅允许进入替换证明，不以状态码认定页面已退休；401、其它状态和缺失响应仍拒绝；旧 target 从完整清单消失也可能滞后于连接失败，等待期间只做有界只读清单复核（进程与端口验证不变），旧 ID 尚在时不连接、安装或释放任何候选页，预算耗尽仍未消失则按 attach-timeout 拒绝。同一 target 的导航、控制器缺失或 run ID 漂移仍按中断处理。已观测到完成、跳过、失败或释放后不重新安装。安装发送总计不因换页清零，回复丢失仍保留未知安装状态；安装、就绪和跳过事件中的 `pageTargetID` 区分同一 PID 下重新从 run ID 1 开始的页面。最终就绪之前重新核对唯一当前 target；返回之后再发生的页面替换不属于本机制。动画控制器就绪和官方外壳可交互分别判断，不以固定等待或壁纸是否启用充当页面稳定证明。需要对单次真实冷启分类失败时，仅为该次启动设置环境变量 `AZHOU_STARTUP_DIAGNOSTICS=1`：启动器经既有日志通道追加有界且无内容的诊断记录（操作阶段、单调时间、页面 ID、原始传输错误 domain/code、存在时的 HTTP 状态、失败发生阶段与 pageConnectionLost 分类、复核清单的旧 ID 在场与合格主页面数）。该设施默认关闭，不改变公开失败类别，也不记录表达式、载荷或完整清单。

同一 opt-in 开关也区分 `target-opened` 之前的身份拒绝。整个打开回调与本次 system.validate 的诊断先暂存在本地，在成功/拒绝已经裁定后一次写入 `bounded-open` 记录的 `checks` 数组（当前有限路径至多 11 项）；动态属性读取、fresh process 查询与命令核验之间不做日志 I/O，post-open-facts 也只在自身裁定结束后写一次。`callback-identity` 记录系统打开回调的实际短路 guard；`system-validation` 保留原始固定 `WallpaperFailure.state` / `StartupFailure.reason` 与 NSError domain/code；其下 `target-input`、`process-facts-initial`、`launch-time`、`process-facts`、`ps-identity`、`signature` 标识本次实际裁定的快照或命令检查；`post-open-facts` 区分回调通过后字段再消失的情况。字段仅含固定标签、单调时间、已实际读取的 PID、字段存在与匹配布尔值，未执行的短路条件省略；PID 尚未读取时标记 `pidObserved=false`，不为补齐日志再次查询。关闭时不额外读取动态属性或诊断时钟；开启时不增加身份查询、命令、启动次数、延时或重试，也不改变 guard 与公开失败类别。诊断 environment 是本次 validate 的值副本，不向后续 connector 核验泄漏 sink。原始命令、路径、URL、异常描述、userInfo 与用户内容均不记录。原生回归经 bounded-open 的 existential 接口执行 production target system，比较开关两侧的结果、getter/系统调用次序与次数，并覆盖迟后字段缺失、各底层检查及超时映射。诊断结果只用于定位，不能宣称修复了真实启动失败。

就绪复查只对 `NSURLErrorDomain` 的 `timedOut`、`networkConnectionLost`、`cannotConnectToHost` 做原预算内的只读重试，间隔至多 150 毫秒，每轮仍复核进程启动身份和端口归属。HTTP 错误、重定向、响应大小或结构不合规不因复查而放行；已完成或跳过的 run 不进入等待。首次状态读取通过当前 CDP 会话持有控制器对象引用，不新增页面 global，断开或换页即清除，捕获与请求返回还须匹配原连接 generation，迟到回复不能把旧 objectId 写入新连接。等待后必须重新确认同一主页面、同一控制器和 run 的最新状态，不能使用等待前的 ready 快照；同页新控制器即使从 run ID 1 开始也按中断处理，不能释放新对象。异常清理也使用已持有的对象引用，在一次 CDP 调用内核对当前 global 与原对象相同后才释放；没有绑定证据时不重新捕获或清理当前对象。等待期间页面变化保守返回 partial，不借暂态清单故障授权重装；没有等待的既有页面换代路径仍按完整旧 ID 缺席证明处理。`StartupNativeTests.swift` 覆盖单次与永久故障、身份/端口/页面/run 变化、取消和终态；两个新增固定表达式由 Node VM 执行同对象与替换对象负例并计入覆盖率。

启动接入的 discovery、replacement proof 与当前页 recheck 每轮仍新读进程/启动时间、ps 用户和执行路径、listener，并检查取消和同一绝对 deadline；这些只读轮询不重复完整 codesign。`validateProcess` 是真正的 `StartupTargetSystem` requirement，保留旧 adapter 的完整验证默认实现，production existential 才能派发到仅验证进程的方法。完整签名/ownership 保留在 operation lock 后首次发现之前、每个选定页面连接之前、每个页面最终同页 proof 之后立即发送载荷之前；异常 cleanup 的完整验证也保留。没有跨轮缓存成功签名，也没有改变换页证明、controller identity 或终态重播规则。独立 wallpaper apply/retry/restore 的三处旧 extension 调用改为显式完整 validate，保留它们原来实际执行的签名边界。生产 environment 注入回归统计真实 codesign 命令，证明单页成功固定 3 次、替换后的每代连接与安装各自验证、轮询次数不增加扫描，并覆盖边界拒绝、身份/端口/取消/预算变化和独立操作完整验证。控制器 capture 测试通过明确的 suspension 通知同步，不再使用一秒 wall-clock 忙等。

宿主布局回归以脱敏的实际结构为依据：核对目标控件、影响可见性和尺寸的祖先样式、滚动容器与重建行为，不复制聊天内容。合成夹具需断言目标顺序和实际几何；选择器命中或备用入口可见不能代替目标位置通过。早期跳过回归会延迟挂载合成 app shell，并验证可交互控件到达后备用入口恢复；它不证明官方加载画面的 DOM 时序。交付分别记录测试载荷版本、安装版本和页面实际运行版本；实机结果仅在同版页面检查后判定，无法核实时保持待验收。

`CI / Agent Skin full production UT coverage` 运行完整 UT 门禁，并进入聚合 Required 判定；现有 macOS 作业继续运行生成载荷浏览器功能回归。仓库通用 `python3 scripts/verify.py` 仍执行其完整仓库检查，不能替代本页的包级覆盖率命令。提交/推送状态与远端 CI 结果另行报告，不因本地通过而推断远端已通过。
