# 鲜明配色、默认最大化与唯一入口：0.5.0 验收

> 历史范围：本文记录0.5.0的视觉与路径验收。0.5.1改为隐藏无.app载荷并移除dist副本，见 [0.5.1验收](upgrade-0.5.1-verification.md)；0.5.2增加应用图标。当前版本、唯一入口和操作步骤以 [项目 README](../README.md) 为准，本文不作为现行产物数量说明。

日期：2026-10-24。项目：`/Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation`。Git 起点 `c743c2b`；本轮没有 commit、push 或公开发布。本文记录用户要求删除旧入口及备份、对齐默认最大化、复用原项目能力增强动效之后的实际状态。

## 0.5.0验收结果

- 唯一日常安装入口：`/Users/guanxueliang/Applications/阿舟启动 Codex.app`。
- Bundle ID：`local.azhou.codex-startup`；可执行文件：`AzhouCodexStartup`；版本：`0.5.0 / build 2`；`LSUIElement=true`。
- 项目内唯一应用产物：`dist/阿舟启动 Codex.app`。它是安装来源；日常打开上面的 Applications 入口。
- 已核实的旧项目入口 `/Users/guanxueliang/Applications/Codex.app` 已移除。它是项目包装器，不是官方主程序。
- 已删除 `.local/recovery/` 中19个恢复文件，共28,299,908字节，并移除该恢复目录。删除清单和SHA256保留在 `.local/evidence/20261024-vivid/cleanup.json`；清单自身不包含可恢复副本。
- 当前官方目标仍为 `/Applications/ChatGPT.app`，身份 `com.openai.codex`，主可执行文件 `ChatGPT`。未修改或删除它，也未处理其正常 Helper。

## 最大化差异的原因与修复

上一版 `Native/App.swift` 按宽度不超过1000点、约1.52宽高比创建窗口；网页布局又根据容器等比缩放。这使原生安装版和大视口源码预览产生明显尺寸差异。此前还存在源码 / dist 已更新、旧名称安装副本未同步的历史问题，现已由统一安装命令和资源指纹检查处理。

现在原生播放器每次创建窗口时读取当前屏幕的 `visibleFrame`，用 `NSWindow.setFrame` 设置整个窗口，并允许用户调整大小。默认占满当前可用桌面区域，不创建独立全屏 Space。此修改作用于项目启动动画窗口，不改变官方主程序的窗口偏好。

本机实际最大化窗口为1512×889点，原点(0,60)，2× Retina；日志中的实际frame与visibleFrame相同。源码预览与安装版的viewport、人物/标题/英文/字幕bounds、画布尺寸和stageScale完全一致，见 `preview-installed-parity.json`。浏览器模式多出预览工具条，正式启动仅隐藏工具条，不另用一份构图。

角色源图1254×1254像素。布局使用源图尺寸、实际DPR和可用空间共同限制缩放；本机角色显示627×627点、画布1254×1254像素，报告中 `upsampled=false`。背景延展到整个窗口，人物不会因最大化被强行放大。

## 设计与原项目能力复用

按本机 `emil-design-eng`、`improve-animations`、`animation-performance`、`review-animations` 执行了源码审计、动效计划、原生粗演、幅度精修和代码复核。来源为 [emilkowalski/skills](https://github.com/emilkowalski/skills)。审计作者和代码复核作者没有独立观看远程播放，不能将其结论写成独立视觉验收。

| Before | After | Why |
| --- | --- | --- |
| 米绿、灰棕配色，工作台回应较弱。 | 暖橙角色、珊瑚粉标题、粉紫实验室、青色信号点；阅读面板保持浅色。 | 强化角色与启动节点，保证三项文案的清晰度。 |
| 原项目有粒子、刻度和光带，但直接复原会引入持续背景运动。 | 复用预先创建节点、确定性位置和transform/opacity：8个定向粒子、36枚入场后静止的刻度、一次光带和一次回应环。 | 将新增效果集中在“最后一击→电脑信号→Codex回应”。 |
| 局部网格动作偏轻，整张工作图没有独立关节图层。 | 保留网格，小幅增强前倾、左右敲键和发梢；桌面、电脑及凳子保持稳定。 | 增加动作可读性，同时控制单张插图变形的能力边界。 |
| 静态阶段仍可能重复提交同一画布状态。 | 缓存mesh状态，相同时跳过重画；固定装饰用预创建WAAPI并与预览时钟同步。 | 减少无意义提交，并保留暂停、定位和重播的确定性。 |

复用检查以Git HEAD原实现和实际文件为依据。沿用 Swift / AppKit / WKWebView、HTML / CSS / SVG / WebGL，没有换技术栈或引入第三方动画库。实验室现有SVG线条按40ms错开显现；没有搬回旧头像、旧轮廓数据、约1400块碎片或CRT收缩退出。源图没有更换或重绘。

粗演使用原网格幅度，观看最大化完整序列后再精修。最终头部角系数为0.035/0.018，左右手为0.0100/0.0080，发梢X系数0.008，最后左手敲键幅度1.15；没有直接采用计划中的试验上限。

### 实际时间轴

| 时间 | 主动作与阅读 |
| --- | --- |
| 0–0.6秒 | 阿舟与工作台入场，实验室线条依次显现。 |
| 0.6–2.65秒 | 前倾、五次交替敲键；标题1.38–1.93秒出现，英文1.98–2.36秒出现。 |
| 2.28–3.22秒 | 最后一击送出8个彩色信号点；光带2.42–3.08秒经过人物后方；Codex回应环2.87–3.22秒完成。 |
| 3.22–3.64秒 | 字幕出现。新增高显著辅助运动在3.50秒前收束。 |
| 3.64–7.05秒 | 三项文案稳定阅读；人物发梢在4.30秒前完成轻微收束，之后静止。 |
| 7.05–7.80秒 | 辅助线淡去，人物和三项文案保持完整。 |
| 原生交接 | 前端只发一次完成；原生核实目标、请求激活，约280ms淡出后退出启动器。 |

减少动态分支取消人物变形、位移、粒子、扫光和扩张，保留200ms透明度状态反馈；实现了系统偏好change监听。

## 实际验证

所有本轮证据位于 `.local/evidence/20261024-vivid/`。

| 检查 | 实际结果 | 证据 |
| --- | --- | --- |
| 粗演 | 最大化原生预览完整执行，保留录像并连续抽帧复核，之后精修幅度。 | `rough-maximized.mov`、`rough-maximized.jsonl`、`rough-filmstrip.jpg` |
| 最终安装版完整启动 | 从新Applications入口实际运行；一次播放、一次完成、一次激活、一次淡出、一次退出，0个failure。 | `final-installed.mov`、`final-installed.jsonl`、`acceptance.json` |
| 已运行Codex与再次打开入口 | 复用官方PID 97802；播放期间再次打开入口产生一次reopen-existing-player，没有新增播放或target-open-request。结束时官方主程序在前台，启动器PID已消失。 | `acceptance.json`、`target-probe.jsonl` |
| 默认最大化与对齐 | 实际frame=visibleFrame；源码预览与安装版的场景bounds和像素配置完全一致。 | `acceptance.json`、`preview-installed-parity.json` |
| 文案、清晰度与边界 | 女性Q版阿舟和三项固定文案正确；关键时刻可见主体完整，源码报告边界均在窗口内，无报告上采样。 | `preview-controls/frame-2.28.png`、`frame-2.90.png`、`frame-5.50.png` 及同名JSON |
| 预览控制 | 真实WKWebView加载源码预览：暂停120ms时钟不变、恢复时钟前进、三次重播无节点/动画累积，减少动态开关分支正确。128个机械断言、0失败。 | `preview-controls/summary.json`、`events.jsonl` |
| 正常重复构建/安装 | 重新执行 `bash tools/install-macos.sh` 成功，返回current；旧入口、ZIP及recovery目录没有重新出现。 | `repeat-build-install.log`、`final-file-checks.json` |
| 资源与私有范围 | 源码、dist、安装包中的HTML/CSS/JS及私有图逐文件SHA一致；原素材SHA未变；没有私有跟踪文件、没有暂存文件。 | `final-file-checks.json` |

最终播放记录的rAF间隔中位数17ms、p95为19ms、最大24ms，466个采样帧，没有超过50ms的间隔；JavaScript提交测量最大1ms。完整录像及连续抽帧未发现明显跳变，静止阶段的WebGL画面保持显示。这些数据只描述该次运行的rAF与JS提交，不能推导GPU/合成器耗时或宣称120fps；本轮未运行Instruments或完整WebKit性能录制。

**视觉判断与工程结果分开：**主执行者查看了最大化粗演和最终完整播放记录、连续帧，以及敲键2.28秒、回应2.90秒、稳定阅读5.50秒的精确预览截图。判断为角色焦点、敲键到信号的因果、三项文案阅读和退出收束均成立；未在这些画面发现非预期裁切或明显网格穿帮。截图只证明对应瞬间，连续动画依据完整录屏与日志。此判断不是独立人工审美评审。

桌面录屏右侧可能出现用户已有的企鹅装桌面宠物叠层；它不属于项目HTML/画布。精确WKWebView截图不包含该外部叠层。

## 删除、更新与恢复边界

安装器先验证新包的签名、内容和权限指纹，再处理经身份核实的旧项目入口。未知应用、官方 `com.openai.codex` 和符号链接不会被清理。成功更新后移除事务暂存旧包，不再生成持久ZIP备份；如发布失败会回滚，极端回滚失败会保留临时原包并明确报错。

用户明确要求删除的历史恢复包现已不存在，不能再使用历史文档中的恢复命令。当前版本可以从现有项目源码重新构建；Git仍保留原有已提交历史，但被删除备份中的未提交旧版本不再具有本项目提供的恢复副本。早期和最终录屏保留作为验收证据，不是可恢复的应用备份。

## 修改文件

| 文件 | 本轮作用 |
| --- | --- |
| `Native/App.swift` | 默认visibleFrame最大化、可调整大小、记录实际窗口与启动路径。 |
| `index.html`、`style.css`、`animation.js` | 鲜明配色、实验室刻度/线条、定向信号、局部动作精修、源像素适配、统一预览控制及减少动态。 |
| `tools/build-macos.sh` | 0.5.0/build2、私有构建保护、事务失败保留规则。 |
| `tools/install-macos.py` | 统一新安装名称、核实后移除旧入口、内容指纹与原子更新；不生成持久备份。 |
| `tools/verify-artifacts.py` | 唯一构建输出、旧项目产物身份检查与发布回滚；移除ZIP归档逻辑。 |
| `README.md`、`plans/`、`docs/` | 实际命令、动效计划、历史标记、本轮证据与未覆盖范围。 |

一次性预览验收程序保存在忽略的 `.build/VividValidation.swift`，不打包进应用，也不是产品新增功能。

## 尚未覆盖

- 未退出正在使用的官方主程序，因此没有再次实测“Codex完全未运行”的冷启动场景。
- 减少动态的前端切换分支已实测，系统设置的实际开关操作未覆盖；change监听做了静态复核。
- 源码交互预览在真实WKWebView中验证；未额外验证Safari / Chrome各版本、其他显示器、非Retina条件或其他macOS版本。
- 没有独立远程运行评审或独立人工审美评审；子任务的Approve仅限代码静态检查。
- 素材仍为单张RGBA工作场景，缺少独立关节/手势图层；本次小幅动作可用，不据此扩展成转身、走路或大幅手臂动作。

## 官方依据

- [Apple NSScreen.visibleFrame](https://developer.apple.com/documentation/appkit/nsscreen/visibleframe)：可用显示区域避开菜单栏、Dock等占用；创建窗口时重新读取。
- [Apple NSWindow.setFrame](https://developer.apple.com/documentation/appkit/nswindow/setframe(_:display:))：设置整个窗口frame，包含标题栏。
- [Apple NSWorkspace.openApplication](https://developer.apple.com/documentation/appkit/nsworkspace/openapplication(at:configuration:completionhandler:))：应用启动及完成回调；本项目另记录激活后的真实前台应用。
- [Apple LSUIElement](https://developer.apple.com/documentation/bundleresources/information-property-list/lsuielement)：项目启动器的agent应用身份配置。
- [WebKit Timelines Tab](https://webkit.org/web-inspector/timelines-tab/)：完整渲染性能诊断能力；本项目的rAF/JS日志不能替代它。
