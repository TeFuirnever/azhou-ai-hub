# 源项目行为研读

本文只记录现状；目标契约见[详细设计](detailed-design.md)。核对日期：2026-10-26。`S` 表示用户指定源目录，`H` 表示 Hub。行号用于本次定位，符号用于后续重查。

## 1. 证据身份与读取范围

| 标记 | 根目录 | 检查时提交 | 工作树 | 用途 |
|---|---|---|---|---|
| S | 源项目独立检出目录（由实施者本地解析） | `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248` | 干净 | 提炼源功能与算法 |
| H | 本仓库根目录 | `f6f309ccedf4f9d0f1febcd7958aee36729824b0` | 写本文前干净 | 确认目标现役契约 |

S 的出处使用 `S:相对路径:行号`，由上表根目录定位；缺少 S 时，本文的行为摘要仍可供实现，逐字校准需恢复上述提交。H 的链接使用仓库相对路径。任一相关文件变化后，重新核对对应条目，不能把本文当实时清单。

S 研读覆盖：README、唯一 `docs/references.md`、`extension/README.md`，两份 Swift 入口，全部四个生产扩展 MJS、壁纸 CSS、动画及设置 JS、HTML/CSS、两份构建脚本、两份素材处理 Swift、素材准备 shell、模拟宿主脚本与三项 Node 测试。图片、图标和轮廓数组只核对角色、尺寸与引用关系，不复制到设计文档。

图索引采用 Verify 深度：项目 `codex-startup-animation-design-source`，generation `2026-10-26T14:28:22Z`；H 项目 `Users-guanxueliang-Desktop-oh-my-ai-azhou-ai-hub`，generation `2026-10-26T11:05:17Z`。S 的 `tools/`、`docs/` 被索引排除，`extension/wallpaper.css:25` 为 partial，均以源码读取补足。图覆盖无记录缺口只表示未发现记录缺口，不保证完整。

## 2. 源项目事实

| ID | 事实与关键原文 | 第一手出处 |
|---|---|---|
| S01 | 正式入口先查 `com.openai.codex`；已有实例时 `existing.activate` 后退出，不重播、不强杀。 | `S:Native/Extension.swift:10` `applicationDidFinishLaunching` |
| S02 | 冷启动执行 `codesign --verify --deep --strict`；Node 辅助再次校验 Bundle ID 与 `TeamIdentifier=2DC432GLL2`。Swift 在执行内置 Node 前只做完整性校验，Team ID 校验发生在 Node 内，不能说 Swift 已验证签名主体。 | `S:Native/Extension.swift:25`、`S:extension/run.mjs:29` |
| S03 | 正式入口复用应用内 `Contents/Resources/cua_node/bin/node`，随后 `open -n -a … --remote-debugging-address=127.0.0.1`。 | `S:Native/Extension.swift:32`、`S:extension/run.mjs:38` |
| S04 | `verifyListener` 校验所有监听地址均为指定 `127.0.0.1:port`、监听 UID 为当前用户、可执行路径位于目标 bundle。临时端口先占用后释放，存在竞争窗口；后续验证是必要控制。 | `S:extension/run.mjs:16` |
| S05 | `pageTarget` 仅接收 `type=page`、`app://-/index.html`，拒绝 `initialRoute` 中 `avatar/quick.chat/detached/mini/popover/notification`。`localSocket` 限定 `ws://127.0.0.1:<port>/devtools/page/`，拒绝凭据。 | `S:extension/cdp.mjs:1` |
| S06 | `connect` 以递增请求 ID 匹配响应；错误响应 reject、关闭时 reject 所有 pending；连接超时 5 s，默认请求超时 10 s。 | `S:extension/cdp.mjs:12` |
| S07 | `buildInjection` 把 HTML、CSS、设置、轮廓、动画与两张图合成表达式；移除 script/link/meta CSP 和默认图片引用，将 `requestAnimationFrame` 等绑定到 iframe。它不修改父页面 CSP，但通过 CDP 执行脚本。 | `S:extension/payload.mjs:4` |
| S08 | `installRenderer` 只在顶层页面运行；已存在 `__aemeathExtension` 时返回 `alreadyActive`。正式动画是 `about:blank` 临时 iframe，不是 AppKit 窗口。 | `S:extension/renderer.mjs:2` |
| S09 | 消息限定当前 `frame.contentWindow` 和 `type=aemeath-boot`。支持 `background/ready/complete/assetError/settings-open/settings-close/restore`。完整动作语义见[运行契约 §1](runtime-contracts.md#1-源消息与目标消息)。 | `S:extension/renderer.mjs:64` |
| S10 | iframe watchdog 为 25 s；打开设置时取消。结束仅移除覆盖层，保留静态样式、图片与快捷键；`dispose` 撤销 Blob URL、恢复此前属性和两个 CSS 变量、移除监听。 | `S:extension/renderer.mjs:10` |
| S11 | 壁纸默认 `42`、范围 `0..75`；使用 Blob URL 避开大 data URL 的 CSS token 限制；0 清除图片。`dispose` 不关闭宿主 CDP 端口。 | `S:extension/renderer.mjs:24`、`S:README.md` |
| S12 | 总时间 `12000` ms；脉冲→身份→散开→左到右描线→彩色背景→收拢。显示百分比来自时间插值，不是官方应用或模型加载进度。 | `S:animation.js:4`、`progress`、`render` |
| S13 | `warmIdentityTexture` 在计时前渲染 4179 ms 布局并准备位图；4.74 s 后释放；描线完成后复用 Path2D，不逐帧分配粒子。 | `S:animation.js:263`、`prepareIdentityTexture`、`trace` |
| S14 | 减少动态效果在初始化读取，关闭部分运动/闪光；代码没有监听系统偏好运行中变化。不能把 H 的动态监听能力归给 S。 | `S:animation.js:5` |
| S15 | 设置分 `savedImages/pendingImages`；关闭放弃草稿并结束本次动画；保存先应用，IndexedDB 写成功后更新 saved 并重播；失败尝试恢复 saved。恢复默认只是草稿变化，仍需保存。 | `S:animation.js:308` |
| S16 | IndexedDB：`aemeath-startup-images` v1 / store `settings` / key `images`；transaction complete 才 resolve。源独立预览与正式注入运行在不同存储上下文，不共享设置。 | `S:image-settings.js:42`、S README |
| S17 | 接受 PNG/JPEG/WebP，文件大于 `30*1024*1024` bytes 拒绝；头像中心 cover 裁成 512²，背景裁成 1536×1024。背景和线稿从同一裁切图导出。 | `S:image-settings.js:57` |
| S18 | 在线轮廓使用 768×512 灰度、Sobel、四向非极大抑制，阈值 32，8 邻接遍历，路径至少 8 点，每两点抽样，保留最长 1200 条，放大回 1536×1024。 | `S:image-settings.js:4` `vectorize` |
| S19 | 离线默认轮廓使用 Vision `VNDetectContoursRequest`，`contrastAdjustment=1.4`、`maximumImageDimension=1200`；与在线算法不同，只承诺同图坐标一致，不承诺轮廓逐点一致。 | `S:tools/trace-contours.swift` |
| S20 | 三段文字字段上限分别 `16/48/60`，`slice` 和 HTML maxlength 按 UTF-16 计数；空串隐藏。 | `S:animation.js:310`、`S:index.html` |
| S21 | 独立 `Native/App.swift` 支持 `--settings/--launch/--smoke-test/--snapshot`。旧 launch 路径会 hide/unhide 目标；这是 S 预览入口的行为，不能迁入 H 的不隐藏主程序契约。 | `S:Native/App.swift:110` |
| S22 | 45 s 是重试循环 deadline，不是严格端到端上限：循环内验证子进程/请求可继续耗时。辅助进程在确认 ready 后退出，并未等待完整播放。 | `S:extension/run.mjs:39` |
| S23 | 构建产出两份 App；正式 `local.aemeath.extension` 和预览 `local.aemeath.startup`。没有许可证；程序、人物素材和标志权利须分别处理。 | `S:tools/build-extension.sh`、`S:tools/build-macos.sh`、`S:docs/references.md` |

## 3. Hub 当前事实与差异

| ID | 当前行为 | 证据 | 对目标设计的影响 |
|---|---|---|---|
| H01 | 唯一入口 `~/Applications/阿舟启动 Codex.app`，`local.azhou.codex-startup`，单可执行文件 `AzhouCodexStartup`。 | [包 README](../../../packages/codex-startup-animation/README.md)、[构建脚本](../../../packages/codex-startup-animation/tools/build-macos.sh) | 复用身份与安装所有权，不新增第二 App。 |
| H02 | 独立 AppKit/WKWebView 播放 7.8 s 阿舟实验室动画；最大化到 visibleFrame；不 hide、不退出官方应用；动画完成和目标应用可用共同触发交接。 | [App.swift](../../../packages/codex-startup-animation/Native/App.swift) `startTarget/finishIfReady/handoff`、[animation.js](../../../packages/codex-startup-animation/animation.js) | 保留可信启动、实例激活与失败保留官方窗口，替换原生动画窗口交接；当前7.8s不冒充源12s。 |
| H03 | 壁纸仍为 CDP 注入，使用 Foundation WebSocket；`Native/Wallpaper.swift` 与 `wallpaper/renderer.js` 分开运行，最多约 30 s；与动画交接解耦。 | [Wallpaper.swift](../../../packages/codex-startup-animation/Native/Wallpaper.swift)、[renderer.js](../../../packages/codex-startup-animation/wallpaper/renderer.js) | “原生路线”只描述动画；可选壁纸依然有页面适配与端口风险。 |
| H04 | 已运行却无可验证调试端口时报告 `needs-restart`，继续交接；只读 `--wallpaper-status` 不注入、不启动、不写日志。 | [包 README](../../../packages/codex-startup-animation/README.md)、Wallpaper `status` 分支 | 设置 UI 也必须保留此失败语义。 |
| H05 | 壁纸按已识别表面和装饰定点处理，保留输入框、菜单、代码块；状态检查图片解码、表面、装饰和报告版本。 | [wallpaper/renderer.js](../../../packages/codex-startup-animation/wallpaper/renderer.js)、[0.7.1 记录](../../../packages/codex-startup-animation/docs/azhou-wallpaper-0.7.1-verification.md) | 复用比 S 的较宽 CSS 覆盖更成熟的核查。记录为历史，不代表本次宿主验收。 |
| H06 | 当前前端未纳入 S 的 `image-settings.js`、临时 iframe、⌘⌥B 设置链路；默认图是私有阿舟素材。 | [迁移清单](../../../packages/codex-startup-animation/MIGRATION-INVENTORY.md)、[manifest](../../../packages/codex-startup-animation/hub-package.json) | 自定义设置、动态图轮廓和恢复外观 UI 都属新增设计。 |
| H07 | 包安装器核对来源、内容、安装记录和 LaunchServices 登记，原子替换唯一入口；Hub adapter 只拥有隔离测试安装；生产 install/uninstall adapter 保持阻断。 | [安装生命周期](../../../packages/codex-startup-animation/docs/installation-lifecycle.md)、[integration_startup_animation.py](../../../scripts/integration_startup_animation.py) | 新设置存放用户数据目录，不能被安装/升级当作包内容覆盖。 |
| H08 | `hub-package.json.commit` 是历史导入基点；实际导入含当时维护工作树。当前 H 包不等于用户此次指定的干净 S。 | [UPSTREAM.md](../../../packages/codex-startup-animation/UPSTREAM.md)、[集成约定](../../integrations.md) | 两份证据分别标识，禁止用同一个 commit 推导代码相同。 |
| H09 | Hub 还含 Pet 管理与导入链路；用户指定 S 不含这套能力。 | [pet/theme.json](../../../packages/codex-startup-animation/pet/theme.json)、[Pet 说明](../../../packages/codex-startup-animation/docs/codex-pet.md) | Pet 保持独立所有权，不扩入此次重实现。 |
| H10 | 当前壁纸renderer没有MutationObserver；status按调用核查DOM；dispose无条件恢复快照，且旧实例只按owner/dispose识别，未精确校验version。 | [renderer.js](../../../packages/codex-startup-animation/wallpaper/renderer.js) `installRenderer/status/dispose` | 目标条件恢复与精确旧版识别是新增行为，不能当现有能力复用。 |
| H11 | 原生transport为Wallpaper专用：2MiB入站上限，evaluate的CDP timeout=5000、socket取消6s，错误只识别壁纸分类。 | [Wallpaper.swift](../../../packages/codex-startup-animation/Native/Wallpaper.swift) `WallpaperTransport:268–325` | RC7需要重组状态和错误消费，不能只换payload文件名。 |
| H12 | adapter inspect逐字核对5份旧web资源；launch要求player/complete/fade日志，而新CDP辅助只等ready。 | [integration_startup_animation.py](../../../scripts/integration_startup_animation.py) `inspect_bundle:161`、`assess_execution:455` | 新旧版本分支、资源清单和完成范围必须一起改。 |
| H13 | 构建器与verify-artifacts均绑定0.7.1/build8、固定INPUT_FILES和wallpaper/install.js资源清单。 | [build-macos.sh](../../../packages/codex-startup-animation/tools/build-macos.sh)、[verify-artifacts.py](../../../packages/codex-startup-animation/tools/verify-artifacts.py) `INPUT_FILES/verify_wallpaper` | 不能仅更新hub-package.json；所有核验消费者都需覆盖新资源。 |

v0.2只读环境记录：本机`/Applications/ChatGPT.app`的Info.plist显示`com.openai.codex`、版本`26.1021.31345`、build`21828`、最低macOS13.0；codesign描述显示`TeamIdentifier=2DC432GLL2`。这只是当前候选支持目标的元数据，不是深度签名验证、CDP能力或真实运行验收。

v0.2补充S顺序差异：S `animation.js:306`先发送ready再调用play预热；目标改为预热后ready。S设置保存先applyImages后写库（370–375），目标改为commit-first。S保存后的watchdog只清理iframe（`renderer.mjs:73`），目标统一写入timeout状态。S生产消息经绑定source的闭包而非真正postMessage（`renderer.mjs:56`）；S `payload.mjs:12`设module=undefined。上述差异是目标改进与明确化，不作为S已有能力。

## 4. 源能力迁移决策

| 源能力 | 目标处理 | 原因 | 目标契约 |
|---|---|---|---|
| 动画内嵌官方窗口 | 采用源项目 CDP 同窗口临时 iframe | 用户最新明确选择；替代此前原生窗口建议 | 详细设计 §6 |
| 头像、背景、文字与线稿 | 独立重新实现同类能力 | 这是源项目可定制性的核心；现有固定角色网格不能套用任意头像 | 运行契约 §2–§4 |
| 12 s 动画 | 作为目标时间轴；当前 7.8 s 是待替代的现役基线 | 以源项目动作结构重实现，阿舟素材与实际画面仍需视觉验收 | 运行契约 §3、详细设计 §15 |
| 背景显现程度、0 关闭、恢复外观 | 合并进一个 CDP 页面会话控制器 | 保留 H 表面核查，动画与壁纸共享资源及清理所有权 | 运行契约 §5 |
| 独立预览 | 复用 H 同一 App 的 preview 模式 | 保留唯一安装身份 | 详细设计 §7 |
| 官方窗口 ⌘⌥B | 保留父页面设置入口，按当前 iframe 身份校验消息 | 不添加系统级键盘监听或常驻原生程序 | 运行契约 §1 |
| IndexedDB 作为唯一存储 | 保留本机事务存储；H 使用自己的数据库名 | 短命辅助进程退出后，设置与重播仍在页面内运行；预览隔离 | 运行契约 §4 |
| Node 扩展与 `open -n` | 迁移其 CDP 行为，不要求迁移执行器 | H 已有 Foundation CDP 核验与单实例启动；原生 transport 承担同一协议 | 详细设计 §4 |
| 上游图像、品牌文字、图标、源代码 | 仅用作行为研究 | 尚无再分发授权；行为蒸馏不自动构成法律意义的独立创作证明 | 详细设计 §11 |

## 5. 已知证据边界

本次执行 S 的 Node suite：3/3 通过，覆盖目标筛选、回环 URL、协议响应/错误/超时。没有执行 S 或 H 的真实启动、壁纸应用、安装、窗口交接、视觉或无障碍验收；这些能力在本文均只能标为 Implemented 或目标态。

尚无可复核峰值内存、GPU 呈现时序和跨 Codex 版本兼容数据；源 README 的约 12 s 和 H 的历史截图不是这些指标的替代证据。
