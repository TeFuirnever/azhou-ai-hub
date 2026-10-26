# 阿舟启动 Codex

本包 fork 自 [`panding999/codex-startup-animation`](https://github.com/panding999/codex-startup-animation)，基于 `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248` 的本地维护工作树，包含当时的未提交修改和新增维护文件。上游没有提供开源许可；用户正在联系维护者确认。此处仅授权本地迁移，**不得对外发布或再分发**。详见 [上游来源](UPSTREAM.md)。

本次迁移没有运行安装器、启动或重启 Codex，也没有执行壁纸接入。历史验收文档只记录原项目当时的结果，不代表本包或当前机器刚刚通过验收。私有角色图、壁纸图、图标源图和本地证据未随源码迁入。

女性 Q 版阿舟在实验室陪伴 Codex 启动。当前版本 **0.7.1 / build 8**，沿用 Swift / AppKit / WKWebView 和 HTML / CSS / SVG / WebGL。Codex 主界面使用保留 Q 版造型的全景实验室静态壁纸，独立启动动画保持原有节奏，没有新增第三方运行依赖。

**唯一日常入口：`~/Applications/阿舟启动 Codex.app`。** 构建生成隐藏的 `.build/azhou-payload` 安装载荷；安装验证成功后清理已核实的旧项目应用，项目 `dist` 不再保留第二份 `.app`。

## 安装与启动

本机构建与安装需要 macOS 13+、Xcode Command Line Tools、Python 3，以及已安装、身份为 `com.openai.codex` 的官方应用。构建通过 `xcrun --sdk macosx swiftc` 明确选择 macOS SDK。播放器使用系统 AppKit / WebKit；壁纸辅助任务使用 Foundation 的 WebSocket 连接 CDP，不依赖旧扩展的 Node 运行链路。阿舟工作图、升级壁纸图和图标均为本地私有素材，不随公开源码分发。

```sh
cd packages/codex-startup-animation

# 私有素材必须由使用者在本机从已授权来源单独提供。
: "${AZHOU_WORKING_IMAGE:?Set an authorized local path to the 1254x1254 RGBA working image}"
: "${AZHOU_ICON_SOURCE:?Set an authorized local path to the square PNG app icon}"
python3 tools/prepare-azhou-assets.py --source "$AZHOU_WORKING_IMAGE"
mkdir -p assets/private/app-icon
cp "$AZHOU_ICON_SOURCE" assets/private/app-icon/source.png

# 本地还需单独提供已授权的私有 Q 版全景壁纸图。
test -f assets/private/wallpaper-scene-q-v3.png

# 构建只创建隐藏载荷；安装命令会更新 ~/Applications 并可能打开 Codex。
bash tools/build-macos.sh

# 单独获准安装时才运行安装器。
bash tools/install-macos.sh

# 仅在明确获准启动实际入口时运行，这会启动 Codex。
open "$HOME/Applications/阿舟启动 Codex.app"
```

只构建时运行 `bash tools/build-macos.sh`，输出 `.build/azhou-payload`。旧的 `bash tools/build-extension.sh` 兼容入口转发到同一构建。载荷不是日常启动入口；安装使用上面的统一命令。

也可以双击 `扩展启动Codex.command`：始终构建当前源码，完成安装、旧项目入口清理和唯一性检查后，再打开规范安装路径。不会因旧 `dist` 存在而跳过构建。

## 预览与窗口

```sh
# 当前源码的交互预览：重播、暂停、拖动时间轴。
open index.html

# 安装版的真实原生窗口，只预览，结束后退出。
"$HOME/Applications/阿舟启动 Codex.app/Contents/MacOS/AzhouCodexStartup" --preview
```

原生动画默认最大化到当前屏幕 `visibleFrame`，保留菜单栏 / Dock 的区域，不创建独立全屏 Space；允许手动调整窗口。网页预览铺满当前浏览器视口。两者使用同一场景布局；浏览器额外显示预览控制，正式启动隐藏它们。

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

固定文案：

- 阿舟的 Agent 实验室
- AZHOU / AGENT LAB
- 和阿舟一起，把想法做出来。

启动动画继续采用素材库中现有的女性Q版工作姿态 `azhou-chibi-pet/v1.0.0/images/04-working.png`，1254×1254 RGBA，对应私有文件 `working.png` 和 `scene.js`。准备脚本逐字节复制并生成本地加载文件；不改原素材库。原图没有独立角色图层，已校准的局部网格表现小幅敲键、前倾、点头、眨眼与发梢跟随，不能据此推断具备走动或转身资产。

Codex 主界面壁纸使用 `assets/private/wallpaper-scene-q-v3.png`，原生尺寸为1672×941、RGB PNG。以正式 `04-working.png` 为 Q 版比例和画风主参考，女性v2身份图仅辅助核对角色特征，经 ImageGen 生成完整实验室场景。大头、小身体、短四肢的 Q 版造型必须保留；扩展背景不代表改用普通动漫身材。生成提示词、参考来源与摘要见私有记录 `assets/private/provenance/wallpaper-scene-q-v3.json`。

这是一份项目私有衍生图，不代表已进入正式 IP 素材库；原参考文件保持不变。0.6.x 的 `working-v2.png` 留存，启动动画继续使用已校准的 `working.png` 与网格。场景使用 `cover` 等比铺满窗口，窄窗会裁掉部分环境，Retina或较大窗口可能放大原始像素，不宣称原生4K清晰度。

动效重做使用本机 Emil 技能 `emil-design-eng`、`improve-animations`、`animation-performance`、`review-animations`，按“审计、计划、粗演、精修、复核”执行。旧项目的粒子预分配、SVG刻度与渐变光带得到复用；配色更新为暖橙、粉紫、珊瑚粉与青色点缀。

| 时间 | 动作 |
| --- | --- |
| 0–0.6秒 | 人物与工作台显现，实验室线条依次亮起。 |
| 0.6–2.65秒 | 前倾和五次交替敲键，标题与英文依次进入。 |
| 2.28–3.22秒 | 最后一击送出8个彩色光点，一次光带扫过人物后方，Codex标识回应。 |
| 3.22–3.64秒 | 字幕出现，显著辅助效果收束。 |
| 3.64–7.05秒 | 完整构图保持阅读；人物轻微收束后静止。 |
| 7.05–7.8秒 | 辅助线淡去，主体与文案保留到交接。 |

固定装饰由预创建的 Web Animations API 动画驱动，暂停、拖动、重播与原有时钟同步。原有 rAF 继续处理局部角色网格；静态阶段跳过相同画布状态的重绘。减少动态模式保留透明度反馈，关闭位移、粒子、扫光与角色变形，并监听系统设置变化。

正常启动按 Esc 或点击“跳过”可直接交接。原生窗口不响应空格暂停，浏览器预览支持。动画不是主程序加载百分比。

## 身份与交接

| 项目 | 值 |
| --- | --- |
| 日常入口 | ~/Applications/阿舟启动 Codex.app |
| Bundle ID | local.azhou.codex-startup |
| 主可执行文件 | AzhouCodexStartup |
| 版本 | 0.7.1 / build 8 |
| Dock策略 | LSUIElement=true / accessory |
| 主程序识别 | 规范化真实路径、com.openai.codex、有效主可执行文件；排除自身和嵌套Helper |

本机核实的官方应用路径为 `/Applications/ChatGPT.app`，Bundle ID 为 `com.openai.codex`；每次运行仍重新核对实际目标与进程。播放时准备或复用目标，动画结束后请求激活，成功后以约280ms原生淡出交接并退出。壁纸接入独立进行，不延长7.8秒动画，也不以壁纸成功作为激活 Codex 的前提。播放器不隐藏或退出官方应用，不修改其安装包。

```sh
"$HOME/Applications/阿舟启动 Codex.app/Contents/MacOS/AzhouCodexStartup" --probe
python3 tools/verify-artifacts.py
python3 tools/install-macos.py --check
```

启动回调只代表应用进程启动结果，不代表聊天页面或模型就绪。日志分开记录复用 / 打开、激活请求、真实前台应用及启动器退出。

## Codex 主界面壁纸

0.7.1 修复聊天滚动区独立的底部32px渐隐层与主内容顶部40px渐隐层。定点清除已识别装饰着色，保留输入框、菜单、代码块及输入框内部mask。状态核查同时检查已知装饰的背景、伪元素、阴影和backdrop效果；发现未覆盖装饰时返回失败及固定诊断分类，不把未知容器一律透明化。原生状态命令逐项验证renderer报告，输出逐页检查与 `verificationIssues`，旧版不完整报告和混合版本不会被当成本轮验证通过。实机及反例回归见 [0.7.1渐隐层修复验收](docs/azhou-wallpaper-0.7.1-verification.md)。

0.7.0 将右下角透明人物壁纸扩展为完整的 Q 版实验室场景：图片等比铺满窗口，阅读区使用随宿主底色变化的遮罩，窄窗焦点向人物调整。实时状态同时核查 `cover`、固定视口背景、图片解码、外壳透明与 footer 装饰背景；输入框、菜单和代码块保留自身底色。状态中的 `rasterScale` 记录实际像素放大比例，视觉清晰度与裁切仍需查看实际画面。验收范围见 [0.7.0全景壁纸验收](docs/azhou-wallpaper-0.7.0-verification.md)。

0.6.1 修复聊天页底部装饰背景横向截断人物的问题：只清除输入框外侧的整行背景，保留输入框本体底色与交互；实时状态也会核查这层背景。真实界面与回归证据见 [0.6.1修复验收](docs/azhou-wallpaper-0.6.1-verification.md)。

0.6.0 通过 `Native/Wallpaper.swift` 和 `wallpaper/renderer.js`、`wallpaper/wallpaper.css` 恢复 Codex 窗口内部的静态阿舟背景。构建脚本把渲染代码、样式和私有新图打包成 `Contents/Resources/wallpaper/install.js`。辅助模式使用同一个 `AzhouCodexStartup` 可执行文件，不创建另一个 `.app`；它只改变目标页面本次运行中的背景与表面样式，不改官方安装包，也不改 macOS 桌面壁纸。

启动条件如下：

- **Codex 尚未运行：** 播放器申请一个 `127.0.0.1` 临时端口，释放临时占用后，将明确的正整数端口传给正常启动请求。启动请求仍禁止创建额外实例。辅助任务随后从返回的真实主 PID 核验路径、用户、签名和实际回环监听；临时端口被其他进程占用或连接失败时，只报告壁纸未应用，不重启补救。
- **Codex 已运行且有可验证的 CDP 端口：** 复用该进程，尝试应用壁纸并独立复查图片解码、匹配表面与实际背景。
- **Codex 已运行但没有可验证端口：** 返回 `needs-restart`，动画显示壁纸尚未应用，仍正常交接。首次遇到此情况，请先保存当前工作，再自行完整退出 Codex，然后从“阿舟启动 Codex”入口重新打开。启动器不会替你退出或重启现有会话。

辅助任务最多运行30秒。它不阻塞动画交接，正常交接后可能继续有限收尾；成功、失败或超时都会结束，没有常驻壁纸服务。**调试端口属于 Codex 进程，辅助任务退出不会关闭它；端口会持续到该 Codex 进程完整退出。** 壁纸本身属于当前页面会话，完整页面重载或程序退出后需重新接入。

以下状态检查只读取当前实际运行状态，不启动程序、不注入、不登记、不写日志，也不会把历史成功记录当作本次成功：

```sh
"$HOME/Applications/阿舟启动 Codex.app/Contents/MacOS/AzhouCodexStartup" --wallpaper-status
```

未应用或无法核实时会返回非零状态；这不表示 Codex 主程序启动失败。壁纸操作记录位于 `~/Library/Logs/AzhouCodexStartup/wallpaper.jsonl` 和 `latest.json`，记录状态与核实结果，不写入聊天内容、完整脚本或图片数据。

独立动画仍由 `Native/App.swift` 和原前端播放。旧 `Native/Extension.swift`、`extension/` 动画覆盖层和 ⌘⌥B 图片设置链路不属于当前构建，详见[迁移清单](MIGRATION-INVENTORY.md)。

## 安装、升级与旧入口清理

构建与安装的职责固定如下：

1. 构建只生成隐藏、无 `.app` 后缀的安装载荷，并记录来源、版本和构建输入摘要。
2. 安装先核验载荷，原子更新 `~/Applications/阿舟启动 Codex.app`，验证签名与完整内容指纹。
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

原项目新增了 **「阿舟 · Agent 实验室」** 原生 Codex pet（ID：`azhou-agent-lab`），保持正式女性 Q 版阿舟与现有启动器、全景壁纸的暖橙、奶白、棕色主题。此处只迁入 `pet/theme.json` 与维护工具；私有图集、冻结主题、审阅证据和安装状态均未迁入，不能据此认定本机已安装或已选择该 pet。

```bash
python3 -B tools/manage-codex-pet.py status
python3 -B tools/manage-codex-pet.py sync
```

`sync` 会安装已生成、审阅且与当前主题匹配的候选包，可能修改用户级 `CODEX_HOME`。主题变更或没有候选时报告 `generation-required`：先用 `prepare` 冻结输入，再通过 ImageGen/hatch-pet 生成与审阅；脚本本身不调用生图 API。迁移与本轮验证未运行 `sync`，也未观察宿主选择后的实际播放。

pet 集成保留现有 Codex 会话、7.8 秒启动节奏、三项固定文案和唯一应用入口。操作、拒绝条件与恢复范围见 [原生 pet 说明](docs/codex-pet.md)；本次实际图集、测试结果、运行边界与并行工作树变化见 [2026-10-25 交付验证](docs/codex-pet-verification-2026-10-25.md)。
