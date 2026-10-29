# 阿舟 AI 实验室 / Azhou AI Lab

本目录是 Hub 的 canonical package `agent-skin`，显示名称为“阿舟 AI 实验室 / Azhou AI Lab”；当前唯一适配宿主为 Codex。此副本的固定构建版本为 0.9.0/build 19，包含同窗口 CDP 动画、壁纸及设置流程。中英界面跟随官方应用的语言与深浅色，不另设语言或主题偏好；入口和设置身份使用独立的私有 bot 头像，名字为“阿舟 / Azhou”。本地源码、构建与隔离验证不能代替实际安装交接或官方宿主的人工视觉验收。

Hub 运行评估根据已核验的 App 版本选择事件合同：0.7.1 保留旧评估；0.8.0 及更高版本按 `azhou-startup.event.v1` 单独报告热激活、启动就绪、跳过、中断和未证实状态。`smoke` 只评估独立播放器的完整播放，`wallpaper-status` 保持只读；恢复计划只清理 Agent Skin 控制器与壁纸，并保留已保存设置、Codex 进程和调试端口。这些 Hub 接口目前由合成事件测试验证，不是实际宿主验收。

原始来源仍为 [`panding999/codex-startup-animation`](https://github.com/panding999/codex-startup-animation)，本地来源为 [`TeFuirnever/codex-startup-animation`](https://github.com/TeFuirnever/codex-startup-animation.git)，基础提交 `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248`。来源工作树含未提交维护内容；上游没有提供开源许可，**不得对外发布或再分发**。详见 [上游来源](UPSTREAM.md)。

2026-10-26 的构建、启动 App 和 Pet 接管记录都指向当时的 `packages/codex-startup-animation/`。2026-10-27 建立 Agent Skin canonical package 时保留了该旧来源目录，因为现有安装标记和 Pet 回执仍绑定它；本次更名没有转移 App、Pet、`.build` 或 `.local` 所有权。历史验收仍只代表原记录中的输入与环境。私有角色图、壁纸图、图标源图和本地证据不随源码提交。

当前固定版本 **0.9.0 / build 19**，原生入口使用 Swift / AppKit / WKWebView，动画使用 HTML / CSS / 2D Canvas。12 秒动画按头像、散开、线稿、上色与背景展示的阶段播放；静态壁纸保留 Q 版实验室场景。bot 入口头像不会替换启动素材或 Pet，没有新增第三方运行依赖。

测试要求为整个包的生产代码 UT 行覆盖率至少 95%，按语言分别阻断，并保留独立的实机功能验收。执行入口、覆盖率口径及 Finder/Dock、冷/热启动、壁纸和安装升级用例见 [测试与功能验收](docs/testing.md)。

**唯一日常入口：`~/Applications/阿舟 AI 实验室.app`。** 构建生成隐藏的 `.build/azhou-payload` 安装载荷；安装验证成功后清理已核实的旧项目应用，项目 `dist` 不再保留第二份 `.app`。

物理文件名与显示名称均使用新产品名。安装器先验证新入口，再按原有身份、来源、签名和指纹规则退役已归属的旧名入口 `阿舟启动 Codex.app`；内部 Bundle ID、可执行文件名、日志路径和存储键保持稳定。安装器不会仅因显示名相同而接管其他应用。

改版范围、官方设置来源与本地验证边界见 [0.9.0 改版验证](docs/module-redesign-0.9.0.md)。

## 安装与启动

本机构建与安装需要 macOS 13+、Xcode Command Line Tools、Python 3，以及已安装、身份为 `com.openai.codex` 的官方应用。构建通过 `xcrun --sdk macosx swiftc` 明确选择 macOS SDK。播放器使用系统 AppKit / WebKit；壁纸辅助任务使用 Foundation 的 WebSocket 连接 CDP，不依赖旧扩展的 Node 运行链路。阿舟工作图、升级壁纸图和图标均为本地私有素材，不随公开源码分发。

```sh
cd packages/agent-skin

# 私有素材必须由使用者在本机从已授权来源单独提供。
: "${AZHOU_WORKING_IMAGE:?Set an authorized local path to the 1254x1254 RGBA working image}"
: "${AZHOU_ICON_SOURCE:?Set an authorized local path to the square PNG app icon}"
python3 tools/prepare-azhou-assets.py --source "$AZHOU_WORKING_IMAGE"
mkdir -p assets/private/app-icon
cp "$AZHOU_ICON_SOURCE" assets/private/app-icon/source.png

# bot 入口头像独立提供，不能用启动人物图替代；不会进入 Git。
: "${AZHOU_ENTRY_AVATAR:?Set an authorized local PNG path for the Azhou bot entry portrait}"
cp "$AZHOU_ENTRY_AVATAR" assets/private/entry-avatar.png

# 本地还需单独提供已授权的私有 Q 版全景壁纸图。
test -f assets/private/wallpaper-scene-q-v3.png

# 构建只创建隐藏载荷；安装命令会更新 ~/Applications 并可能打开 Codex。
bash tools/build-macos.sh

# 单独获准安装时才运行安装器。
bash tools/install-macos.sh

# 仅在明确获准启动实际入口时运行，这会启动 Codex。
open "$HOME/Applications/阿舟 AI 实验室.app"
```

只构建时运行 `bash tools/build-macos.sh`，输出 `.build/azhou-payload`。旧的 `bash tools/build-extension.sh` 兼容入口转发到同一构建。载荷不是日常启动入口；安装使用上面的统一命令。

也可以双击 `扩展启动Codex.command`：始终构建当前源码，完成安装、旧项目入口清理和唯一性检查后，再打开规范安装路径。不会因旧 `dist` 存在而跳过构建。

## 预览与窗口

```sh
# 当前源码的交互预览：重播、暂停、拖动时间轴。
open index.html

# 安装版的真实原生窗口，只预览，结束后退出。
"$HOME/Applications/阿舟 AI 实验室.app/Contents/MacOS/AzhouCodexStartup" --preview
```

原生动画默认最大化到当前屏幕 `visibleFrame`，保留菜单栏 / Dock 的区域，不创建独立全屏 Space；允许手动调整窗口。网页预览铺满当前浏览器视口。两者使用同一场景布局；浏览器额外显示预览控制，正式启动隐藏它们。

网页预览的 `window.launcherUI` 提供重播、暂停、定位和 `dispose()`。结束预览时调用 `dispose()` 会释放动画资源并解除当前预览的事件监听。

既有启动动画验收中，本机原生窗口为 1512×889 点、2× Retina。背景填满窗口，人物按原图像素限制放大；实际显示627×627点、画布1254×1254像素，没有上采样。不同显示条件使用实际DPR计算，不把627点硬编码为通用上限。

壁纸另有源码预览，使用模拟宿主页面；它不会连接实际 Codex。在项目根目录运行下面的本机服务器，再从另一个终端打开预览：

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

```sh
open "http://127.0.0.1:8765/wallpaper/preview.html?image=wallpaper-scene-q-v3.png"
```

需要复核模拟宿主时，可运行以下脚本。它另需支持内置 WebSocket 的 Node 和 Google Chrome，使用独立临时浏览器配置，将主测试视口设置为 1512×889，并把报告、截图保存在 `.local/evidence/`。这些测试工具不是应用运行依赖，模拟页面结果也不代表真实 Codex 已完成接入。

```sh
node tools/test-wallpaper.mjs --image wallpaper-scene-q-v3.png
```

## 应用图标

原项目使用用户提供的1254×1254方形PNG作为应用图标。图标源图与私有副本未迁入；需从已授权来源在本机补齐 `assets/private/app-icon/source.png`。

正常构建自动从私有副本生成10个标准尺寸，打包为 `AzhouAppIcon.icns` 并写入应用资源，后续升级持续保留。仅应用图标使用此图，动画仍使用女性Q版阿舟的工作姿态。

构建会拒绝缺失图标、非方形PNG或小于1024×1024的源图。

实际系统读取、Finder显示与升级验证见 [图标验收](docs/app-icon-0.5.2-verification.md)。

## 角色、配色与动作

默认标题使用“阿舟 AI 实验室 / Azhou AI Lab”。默认辅助文字和字幕随官方界面语言显示；已经保存的个人文字与上传图片保持原样，不自动翻译。

启动默认素材仍来自私有 `working.png` 和 `wallpaper-scene-q-v3.png`；构建时生成规范头像、背景和同图线稿。入口头像则单独读取 `assets/private/entry-avatar.png`，在入口与设置头部显示，不改变这些动画输入、应用图标或 Pet。

Codex 主界面壁纸使用 `assets/private/wallpaper-scene-q-v3.png`，原生尺寸为1672×941、RGB PNG。以正式 `04-working.png` 为 Q 版比例和画风主参考，女性v2身份图仅辅助核对角色特征，经 ImageGen 生成完整实验室场景。大头、小身体、短四肢的 Q 版造型必须保留；扩展背景不代表改用普通动漫身材。生成提示词、参考来源与摘要见私有记录 `assets/private/provenance/wallpaper-scene-q-v3.json`。

这是一份项目私有衍生图，不代表已进入正式 IP 素材库；原参考文件保持不变。场景使用 `cover` 等比铺满窗口，窄窗会裁掉部分环境，Retina或较大窗口可能放大原始像素，不宣称原生4K清晰度。

界面与动效遵循本机 Emil `emil-design-eng`、`animation-performance` 的审视方向：反馈明确、常用入口不做持续动画、先测量渲染成本，再减少不必要绘制。旧版 7.8 秒记录只代表历史播放器，不构成当前 Canvas 动画的验收。

| 时间 | 动作 |
| --- | --- |
| 0–1.15秒 | 准备提示。 |
| 1.15–4.18秒 | 头像与标题显现。 |
| 4.18–4.74秒 | 头像与文字散开。 |
| 4.74–5.08秒 | 线稿碎片保持散开状态。 |
| 5.08–7.18秒 | 线稿汇聚。 |
| 7.18–7.43秒 | 同一幅背景上色。 |
| 7.43–11秒 | 背景与字幕展示。 |
| 11–12秒 | 收束并结束。 |

动画按 rAF 时间戳推进，保持暂停、拖动与重播的时间轴语义；减少动态模式保留必要状态与透明度反馈。rAF 间隔与 JS 提交耗时分别报告，不等同于 GPU、合成器或屏幕呈现 FPS。

正常启动按 Esc 或点击“跳过”可直接交接。原生窗口不响应空格暂停，浏览器预览支持。动画不是主程序加载百分比。

## 身份与交接

| 项目 | 值 |
| --- | --- |
| 日常入口 | ~/Applications/阿舟 AI 实验室.app |
| Bundle ID | local.azhou.codex-startup |
| 主可执行文件 | AzhouCodexStartup |
| 版本 | 0.9.0 / build 19 |
| Dock策略 | LSUIElement=true / accessory |
| 主程序识别 | 规范化真实路径、com.openai.codex、有效主可执行文件；排除自身和嵌套Helper |

本机核实的官方应用路径为 `/Applications/ChatGPT.app`，Bundle ID 为 `com.openai.codex`；每次运行仍重新核对实际目标与进程。Codex 已运行时，入口核验并激活同一进程后退出，不打开播放器，也不向现有页面注入或重播动画。Codex 未运行时，入口先启动官方应用；主窗口就绪后，通过核验的回环 CDP 在该窗口安装 `startup/install.js` 并播放动画，使动画与工作页面处于同一窗口。启动接入总预算为 60 秒，其中签名预检最多 15 秒、页面接入最多 45 秒。启动器不退出官方应用，也不修改其安装包。

```sh
"$HOME/Applications/阿舟 AI 实验室.app/Contents/MacOS/AzhouCodexStartup" --probe
python3 tools/verify-artifacts.py
python3 tools/install-macos.py --check
```

应用进程启动回调不代表聊天页面或模型就绪。日志记录打开目标、控制器安装与就绪/跳过结果；运行中 Codex 的热激活单独记录为激活结果。

Hub 的 `run --mode launch` 使用已核验载荷版本评估启动器事件；热激活、控制器就绪和用户跳过各自有独立结果，壁纸失败不会改写启动器结果。独立 `smoke` 才评估动画播放是否完成。旧版本事件和当前版本事件使用各自解析规则，缺失字段、冲突 PID、重复启动边界或无效终态都会返回“行为未证实”。以上是适配器证据，不证明宿主已加载壁纸或用户看到目标画面。

## Codex 主界面壁纸

当前本地候选在启动背景失败时，通过外观入口提供原因和重试；设置保存后的应用失败仍在设置面板处理。设置和预览期间会隔离宿主键盘焦点，关闭后恢复交互。图片导入对可解析的有限文件头先检查尺寸；文件头不能解析时仍走原有解码和最终尺寸检查。预览采用当前主题底色；缩略图的裁切可能与实际窗口不同。上述行为的真实宿主与人工无障碍验收尚待完成；这不改变既有再分发限制。

Build 12 将冷启动时的页面外壳等待上限从 5 秒延长到 60 秒。动画仍在 12 秒自然结束；尚未完成的壁纸请求可在工作区稍后就绪时继续应用，不重播动画。跳过动画、开始新一轮或释放控制器会取消旧请求；等待到期会报告 `shell-timeout` 并清理临时观察器，仍可通过维护命令重试。

0.7.1 的静态 Codex 壁纸实现与显式 `--wallpaper-helper` 维护命令仍保留。该命令可单独应用、检查或恢复壁纸，不属于当前日常启动流程；状态核查只读取运行状态，恢复只移除 Agent Skin 拥有的控制器与壁纸并保留已保存设置。0.7.1 对聊天滚动区底部32px和主内容顶部40px渐隐层的修复、检查范围及实机反例记录见 [0.7.1渐隐层修复验收](docs/azhou-wallpaper-0.7.1-verification.md)。

0.7.0 将右下角透明人物壁纸扩展为完整的 Q 版实验室场景：图片等比铺满窗口，阅读区使用随宿主底色变化的遮罩，窄窗焦点向人物调整。实时状态同时核查 `cover`、固定视口背景、图片解码、外壳透明与 footer 装饰背景；输入框、菜单和代码块保留自身底色。状态中的 `rasterScale` 记录实际像素放大比例，视觉清晰度与裁切仍需查看实际画面。验收范围见 [0.7.0全景壁纸验收](docs/azhou-wallpaper-0.7.0-verification.md)。

0.6.1 修复聊天页底部装饰背景横向截断人物的问题：只清除输入框外侧的整行背景，保留输入框本体底色与交互；实时状态也会核查这层背景。真实界面与回归证据见 [0.6.1修复验收](docs/azhou-wallpaper-0.6.1-verification.md)。

0.6.0 通过 `Native/Wallpaper.swift` 和 `wallpaper/renderer.js`、`wallpaper/wallpaper.css` 恢复 Codex 窗口内部的静态阿舟背景。构建脚本把渲染代码、样式和私有新图打包成 `Contents/Resources/wallpaper/install.js`。辅助模式使用同一个 `AzhouCodexStartup` 可执行文件，不创建另一个 `.app`；它只改变目标页面本次运行中的背景与表面样式，不改官方安装包，也不改 macOS 桌面壁纸。

显式运行旧式静态壁纸 helper 时，仍适用以下维护条件；正常启动使用上文的冷/热启动流程：

- helper 只操作调用方明确给出的 PID 和应用路径；`--wallpaper-status` 会自行解析唯一的运行中 Codex，但不启动应用，也不注入页面。
- helper 对 Codex 进程身份、签名、回环监听和主页面逐项核验，再应用或恢复页面样式；恢复保留已保存的外观设置。
- 已运行的 Codex 若没有可核实的 CDP 页面连接，helper 返回 `needs-restart`。只有用户自行完整退出 Codex 并从入口冷启动后，才会获得新的启动连接。

显式 helper 最多运行 30 秒，结束后不留常驻服务。冷启动期间由启动入口进行的页面接入使用 60 秒总预算，不调用此 helper。**调试端口属于 Codex 进程；启动器或 helper 退出不会关闭它，端口会持续到 Codex 完整退出。** 页面样式属于当前页面会话；完整重载后需重新应用。

以下状态检查只读取当前实际运行状态，不启动程序、不注入、不登记、不写日志，也不会把历史成功记录当作本次成功：

```sh
"$HOME/Applications/阿舟 AI 实验室.app/Contents/MacOS/AzhouCodexStartup" --wallpaper-status
```

未应用或无法核实时会返回非零状态；这不表示 Codex 主程序启动失败。壁纸操作记录位于 `~/Library/Logs/AzhouCodexStartup/wallpaper.jsonl` 和 `latest.json`，记录状态与核实结果，不写入聊天内容、完整脚本或图片数据。

<a id="wallpaper-recovery"></a>
### 壁纸失败诊断与重试

排障先读取已安装应用 `Contents/Resources/azhou-build.json` 的版本、构建号和 `projectRoot`，再检查对应源码；当前工作目录可能属于旧检出。重试前运行上面的只读状态检查，保留失败现场。`pages` 中的 `failureCode` 和派生的 `failureStage` 区分页面等待超时、图片解码失败、样式未生效等有限类别，不输出任意异常文本、图片或聊天内容。

动画结束后，可显式让原控制器重试最近一次有效的图片与强度。PID 和应用路径须来自当前已核实的运行实例：

```sh
"$HOME/Applications/阿舟 AI 实验室.app/Contents/MacOS/AzhouCodexStartup" \
  --wallpaper-helper --action retry --target-pid "$CODEX_PID" \
  --target-bundle /Applications/ChatGPT.app
```

重试不重建控制器、不重播动画、不访问偏好存储；健康壁纸直接复查。控制器内的重试最多等待 10 秒，同一时刻只执行一次；结果的 `retries` 保留已过滤的重试前失败信息。新一轮设置或控制器移除会取消旧请求，迟到回调不能重新应用。禁用背景、忙碌状态、缺少有效请求或所有权冲突会拒绝重试。旧控制器没有该 API 时返回 `retry-unavailable`，不会强行替换；下次从更新后的入口冷启动才会加载新控制器。重试可恢复已知失败状态，但不证明某次历史失效的触发原因已查明。

当前启动构建通过 `extension/renderer.mjs` 在同窗口播放。结束或跳过后，点击阿舟外观入口打开设置（[配置覆盖与保存边界](docs/theme-appearance.md)）；取消不保存，保存后应用背景并关闭设置，启动动画可单独预览草稿。设置和壁纸仍待真实宿主验收，不再拦截与官方浏览器冲突的 ⌘⌥B。恢复外观会移除本页壁纸及设置入口，并保留已保存的用户设置。独立预览仍由 `Native/App.swift` 播放。

## 安装、升级与旧入口清理

构建与安装的职责固定如下：

1. 构建只生成隐藏、无 `.app` 后缀的安装载荷，并记录来源、版本和构建输入摘要。
2. 安装先核验载荷，原子更新 `~/Applications/阿舟 AI 实验室.app`，验证签名与完整内容指纹。
3. 对用户Applications和项目dist范围内已证实属于本项目的额外应用，重新核验后定点注销并删除；同版本同内容副本也属于重复入口。
4. 登记规范安装路径，再复扫实体应用与三个历史项目Bundle ID的全部系统登记路径；仍有冲突则返回失败，不宣称入口唯一。

来源不明、较高版本、符号链接以及官方 `com.openai.codex` 不会被当作旧项目包删除。已运行的项目播放器会阻止替换；官方主程序无需退出。安装失败保留原子回滚能力，成功后清除无 `.app` 后缀的事务暂存目录。

`python3 tools/install-macos.py --check` 和 `bash tools/install-macos.sh --check` 均为只读检查；前者也不会自动构建。普通安装和 `--open` 每次先构建当前源码。

从已安装的旧项目目录转到本包时，先在最终 Hub 包目录运行 `bash tools/build-macos.sh`，再执行 `python3 tools/install-macos.py --migrate-from /absolute/old/project/root`。它只接管旧安装记录、旧载荷和唯一原生入口同时吻合的包；完成后用本包的 `--check` 核对，再处理旧目录。普通安装不会自动接管旧项目。

历史旧命名入口和19个恢复文件已按用户要求删除。构建及安装不生成持久ZIP备份，早期验收录像继续保留。当前源码可重新构建；已删除的恢复包不能使用历史恢复命令找回。

完整规则、来源保护、登记工具边界和必要回归命令见 [安装升级约定](docs/installation-lifecycle.md)。

## 验收与私有素材

安装升级约定：[docs/installation-lifecycle.md](docs/installation-lifecycle.md)。
0.7.1 顶部/底部渐隐层修复与反例回归：[docs/azhou-wallpaper-0.7.1-verification.md](docs/azhou-wallpaper-0.7.1-verification.md)。
0.7.0 Q版全景壁纸历史验收：[docs/azhou-wallpaper-0.7.0-verification.md](docs/azhou-wallpaper-0.7.0-verification.md)。
0.6.0 壁纸接入与素材记录：[docs/azhou-wallpaper-0.6.0-verification.md](docs/azhou-wallpaper-0.6.0-verification.md)；以其中分别列出的模拟测试、真实运行和未覆盖项为准。
图标与安装包验收（0.5.2历史）：[0.5.2验收](docs/app-icon-0.5.2-verification.md)。
安装机制验收（0.5.1历史）：[docs/upgrade-0.5.1-verification.md](docs/upgrade-0.5.1-verification.md)。
视觉与动效记录：[docs/azhou-vivid-maximized-verification.md](docs/azhou-vivid-maximized-verification.md)。
动效计划：[plans/001-vivid-lab-motion.md](plans/001-vivid-lab-motion.md)。

原项目把视觉录屏、截图、运行日志、升级清单和图标记录保存在忽略的 `.local/evidence/` 目录。这些本地证据没有迁入本包；历史记录不能替代当前验证，也不是可恢复应用备份。

`assets/private/`、`dist/`、`.build/`、`.local/` 均被Git忽略，构建检查禁止它们被跟踪。原素材及其衍生应用、录屏、截图不得公开提交或发布。来源与发布边界见 [UPSTREAM.md](UPSTREAM.md)，迁移范围见 [MIGRATION-INVENTORY.md](MIGRATION-INVENTORY.md)。知识核对工作记录不随本包迁入。

历史 `extension/`、`Native/Extension.swift` 和旧默认素材没有迁入；当前正常构建不使用它们。


## 同主题原生 Codex pet

原项目新增了 **「阿舟 · Agent 实验室」** 原生 Codex pet（ID：`azhou-agent-lab`）。私有图集、冻结主题、审阅证据和安装状态不在此副本；已安装 Pet 的回执仍属于 `packages/codex-startup-animation/`。本副本中的 Pet 工具不能接管该安装。

```bash
python3 -B ../codex-startup-animation/tools/manage-codex-pet.py status
python3 -B ../codex-startup-animation/tools/manage-codex-pet.py sync
```

`sync` 会安装已生成、审阅且与当前主题匹配的候选包，可能修改用户级 `CODEX_HOME`。主题变更或没有候选时报告 `generation-required`：先用 `prepare` 冻结输入，再通过 ImageGen/hatch-pet 生成与审阅；脚本本身不调用生图 API。迁移与本轮验证未运行 `sync`，也未观察宿主选择后的实际播放。

pet 集成保留现有 Codex 会话、7.8 秒启动节奏、三项固定文案和唯一应用入口。操作、拒绝条件与恢复范围见 [原生 pet 说明](docs/codex-pet.md)；本次实际图集、测试结果、运行边界与并行工作树变化见 [2026-10-25 交付验证](docs/codex-pet-verification-2026-10-25.md)。
