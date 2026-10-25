# 阿舟启动 Codex：实际验收记录

> 历史路径已按[迁移清单](../MIGRATION-INVENTORY.md)脱敏；变量仅定位原项目环境，原始证据仍留在本地，不证明本包当前已安装或生效。

> 历史记录：本文描述0.5.0之前的设计或验收，文中的版本、命令和数量均属于当时状态。旧 `~/Applications/Codex.app` 及恢复备份已按用户要求删除，历史恢复命令不再适用。现行入口、构建安装步骤和验收索引以 [项目 README](../README.md) 为准。

> 0.4.0后续记录：用户指出已有 Applications 安装入口后的原位更新，见 [当时的安装补齐记录](azhou-installation-verification.md)。该记录同样属于历史，不代表现行安装状态。

日期：2026-10-24。工作目录：`$ORIGINAL_PROJECT_ROOT`。Git 起点：`c743c2b`；保留了开始时已有的 README 和两个 command 文件的未提交修改。本轮没有 commit、push 或公开发布。

## 结论和证据边界

已完成当前项目源码中的视觉、动效、原生交接和构建收敛。最终产物为 `dist/阿舟启动 Codex.app`。实际运行包括粗演、最终原生预览、正式应用启动，以及播放中再次打开同一入口。正式验收复用了正在运行的真实主程序，没有退出它或启动第二份主程序。

视觉复核方式为真实窗口完整执行、全程屏幕录制、连续抽帧和关键帧查看；记录保留了开场前及交接后画面。不能把截图或抽帧当作实时逐帧观看的替代，也不能把本记录写成独立人工审美评审通过。独立子任务完成的是部分代码静态复核；没有独立远程素材或运行复核结果。

## 环境和产物身份

| 项目 | 实际值 |
| --- | --- |
| 机器 / 系统 | Apple M5，macOS 27.0.1 |
| 显示 | 1512×982 点，3024×1964 像素，2× Retina，屏幕报告 120 Hz |
| 原生窗口 | 宽 1000 点，高 657.895 点；网页 viewport 1000×658，DPR 2 |
| 录制区域 | x=256、y=91、1000×658 点；保存为 2000×1316 像素视频 |
| 项目应用 | `dist/阿舟启动 Codex.app` |
| Bundle ID / executable | `local.azhou.codex-startup` / `AzhouCodexStartup` |
| 版本 / Dock | 0.4.0，build 1；LSUIElement=true，accessory |
| 实际主程序 | `/Applications/ChatGPT.app` |
| 主程序 ID / executable | `com.openai.codex` / `ChatGPT` |
| 主程序签名元数据 | TeamIdentifier `2DC432GLL2`；Developer ID Application: OpenAI OpCo, LLC |
| 本轮主程序 PID | 45354，正式交接前后保持不变 |

目标解析按真实路径、Bundle ID 和可执行文件校验；本轮读取了实际主程序签名元数据，但没有为启动器增加密码学签名认证机制。不要将显示名称当作应用身份。

## 画面与素材核查

指定头像为 256×256 RGBA 半身像；指定实验室图为 1536×1024 RGB，背景已包含成人比例人物。它们不足以支持独立完整 Q 版桌前敲键动作。最终使用原素材库已经存在的女性 Q 版工作姿态：

`$PRIVATE_IP_ROOT/assets/characters/azhou-chibi-pet/v1.0.0/images/04-working.png`

该图为 1254×1254 RGBA，alpha 范围 0–255，alpha>8 的可见包围盒为 [61,37,1209,1212]，四边无 alpha>8 的像素。原图和私有复制的 SHA-256 均为：

`34dc9a8e9c06c226ec0cc80878548f118ff4a23b4a87d160674e66db4a905e58`

它是一张人物、桌面、电脑合成图，没有独立图层或连续姿态帧。以 540×540 点显示，2× 所需像素为 1080×1080；本轮局部小动作不需要额外资产。大幅转身、走动、抬起整条手臂仍需独立分层或连续帧，本轮未制作。指定头像和原背景仍保留在素材库，没有覆盖。

新版在同一构图中完成前倾、五次错开的左右手敲键、轻点头、眨眼以及头发 / 尾部的小幅延迟响应；桌面和电脑保持稳定。标题、英文、字幕依次出现，字幕完全出现后保留约 4.16 秒，之后才交接。精修后检查了完整人物边缘、动作极限采样和文字区域，未在复核帧中发现非预期裁切、遮挡或露底。最后一次修正隐藏了启动画面正文区域的鼠标文字光标，避免光标盖住字幕。

审美判断：相比旧版的小头像、碎片 / 描线转场和后半程人物比例变化，新版具有更连续的桌前动作、更明确的左侧人物 / 右侧文字构图，色调也更接近温暖实验室。以上是设计判断，不是用户满意度或第三方审美评分。

## 实际运行结果

证据根目录：`.local/evidence/20261024/`。

| 检查 | 实际结果与对应证据 |
| --- | --- |
| 旧版复现 | 以旧原生 host 和已安装旧版 web 资源完整执行约 12 秒，见 before-full-window.mov、before-full.log。观察 host 增加置顶；最初被遮挡的失败观察不算通过。 |
| 粗演与精修 | rough-playback.mov / rough.log；refined-preview.mov / refined-preview.log。先确认构图、动作和阶段，再修改局部权重及节奏。 |
| 最终应用原生预览 | final-preview.mov / final-preview.jsonl；单次播放完成并退出，不启动主程序。 |
| 正式最终启动 | final-verified-launch.mov / final-verified-launch.jsonl；使用最终构建 app 通过 open 启动。 |
| 重开入口 | 同一正式播放中再次 open；只记录一次 reopen-existing-player，没有重置时间轴或重复打开目标。 |
| 交接 | 只记录一次 target-reused、一次 target-activation-request；activation accepted=true；淡出开始和结束时 frontmost 均为真实主程序。 |
| 收尾 | player-terminated completed=true、failed=false；after-verified-launch.json 未发现启动器残留。 |
| 内容 | 运行报告中的标题、英文、字幕与要求逐字一致；角色、标题、英文、字幕的区域全部 inside=true。 |
| JS / 帧间隔 | 最终一轮 465 个 rAF 样本；间隔中位数 17 ms、p95 17 ms、最大 24 ms、超过 50 ms 为 0；JS errors 为空。 |
| 正常重复构建 | 多次执行 build-macos.sh，并执行旧 build-extension.sh 兼容入口；最终仍为同一个产物。rebuild-final.log 与 final-file-checks.json 保存最后一次结果。 |
| 产物身份 / 数量 | verify-artifacts.py 返回 distAppCount=1；整个项目遍历并排除 app 包内结构后也只有最终这一个 .app。 |
| 产物与源文件 | index.html、style.css、animation.js、working.png、scene.js 与最终包内对应文件 SHA-256 一致。 |
| 恢复验证 | 实际解压最新恢复 ZIP 到临时目录，确认 Bundle ID、主可执行文件和 codesign --verify --strict 成功，随后移除临时解压副本。见 recovery-restore-check.json。 |
| 私有素材 / Git | assets/private、dist、.local 没有被 Git 跟踪；暂存区为空；git diff --check 通过。 |

最终日志时间（相对本次 launcher 进程）：0.638 s 开始动画并复用主程序；1.049 s 收到重开；8.420 s 动画自然完成；8.433 s 激活请求成功；8.728 s 淡出完成；8.753 s 启动器退出。动画本身仍是 7.8 s，原生淡出设为 0.28 s；不将进程初始化时间计为动画时长。

这些帧间隔数据仅覆盖 rAF 和 JS 提交，不包含完整 GPU、合成线程或显示扫描过程，也不证明 120 FPS。粗演时同步抓取 WebKit 快照曾干扰帧间隔；最终验收禁用该快照机制，截图从完整录屏提取。未执行 Instruments 或完整 WebKit Timelines 性能剖析。

## 重复现象的已确认范围

开始检查时项目 dist 目录为空，没有现场复现出两个同时存在的项目 app。确认的历史输出逻辑是：

| 对象 | 身份和用途 | 本轮处理 |
| --- | --- | --- |
| 旧 dist/Aemeath Startup.app | local.aemeath.startup / AemeathStartup；旧预览构建 | 统一构建逻辑不再生成；识别旧产物时校验后归档处理。 |
| 旧 dist/Codex.app | local.aemeath.extension / CodexStartup；旧注入启动器 | 同上；不再用 Codex 作为项目产物显示名称。 |
| ~/Applications/Codex.app | 实际存在，local.aemeath.extension / CodexStartup，0.3.5；包含上一轮阿舟替换 | 项目外，没有修改或删除；项目 command 不再优先启动它。 |
| /Applications/ChatGPT.app | com.openai.codex / ChatGPT；真实主程序 | 正常复用与激活，没有修改、退出或清理。 |
| LaunchServices 的旧 Aemeath 路径 | 指向 ~/.Trash/Aemeath Startup.app；磁盘对象已不存在 | 只读记录，没有系统级清理。 |

Dock 只读检查中相关固定项指向真正 ChatGPT，未复现两个当前 Codex 固定图标。历史同名包装器、两个构建入口以及 command 优先选择外部旧副本是已确认的混淆来源；不能宣称本轮清除了系统所有重名入口。

新构建先检查已知旧身份并归档，在新产物成功发布后才退役旧项目入口；更新现有新产物时先归档，再原子交换目录。未知身份和符号链接会阻止清理。实际修复过 ditto ZIP 中文名称没有 UTF-8 标志导致的校验失败；失败时原正式 app 保持完整，修正后多次正常构建成功。

## 记录索引与恢复

- 旧版全程：`before-full-window.mov`。
- 粗演：`rough-playback.mov`；精修：`refined-preview.mov`。
- 最终原生预览：`final-preview.mov`。
- **最终正式全程（含重开和交接）：`final-verified-launch.mov`**。
- 全程缩略帧：`final-verified-filmstrip.jpg`，按行从左至右，2 fps，不能替代原视频。
- 关键帧：`keyframes/01-enter.png`、`02-typing-title.png`、`03-full-composition.png`、`04-settle.png`、`05-handoff.png`。提取自最终视频的 1.8、3.0、5.5、8.5、9.3 秒，视频时间与动画内部时间不同。
- 汇总：`acceptance.json`、`final-file-checks.json`、`source-assets.json`、`bundle-inventory-before.json`、`launchservices-records.json`。
- 起点恢复包：`.local/recovery/20261024/source-before.zip`、`before.patch`、`installed-web-before.zip`、`RESTORE.txt`。
- 重建前产物：`.local/recovery/*.zip` 及对应 JSON 清单。观察用临时 app 也已压缩归档，不再作为并列入口。

恢复时先解压到新的临时目录并核对内容，再选择性恢复；不要直接 git reset / clean。不要把包含私有阿舟素材的恢复包、应用、录屏或截图提交到公开仓库。

## 未覆盖事项

- **主程序完全未运行时的冷启动**：本机主程序承载当前工作，没有为测试而退出它。冷启动分支仅完成代码检查，不能记作实机通过。
- 预览尚未 ready 时重开、激活被拒绝、主程序缺失、渲染器崩溃等异常分支修复完成代码检查，未进行逐项故障注入实测。
- 不同机器、非 Retina、其他窗口尺寸与其他 macOS 版本未实测。
- 没有独立人工实时审美评审，没有完成独立远程素材 / GUI 复核；主体核查均来自本轮主流程。

## 文件改动与依据

- `index.html`、`style.css`、`animation.js`：新构图、分镜、固定文案、局部角色动作和预览控制。
- `Native/App.swift`：真实主程序解析、单实例、准备 / 激活 / 淡出、日志及明确错误处理。
- `tools/build-macos.sh`、`tools/build-extension.sh`、`tools/verify-artifacts.py`：唯一产物、身份核验、归档与原子更新。
- `tools/prepare-azhou-assets.py`、`.gitignore`：本地私有素材准备和防止意外纳入 Git。
- 两个 `.command`、`README.md`、本记录与设计记录：修正入口、说明使用步骤与事实边界。

官方依据：

1. [Apple：Core Foundation Keys](https://developer.apple.com/library/archive/documentation/General/Reference/InfoPlistKeyReference/Articles/CoreFoundationKeys.html) — 显示名称、Bundle ID、主可执行文件分别核查。
2. [Apple：NSWorkspace.openApplication](https://developer.apple.com/documentation/appkit/nsworkspace/openapplication(at:configuration:completionhandler:)) — 按 URL 打开目标，完成回调不能证明应用内部页面已经就绪。
3. [Apple：createsNewApplicationInstance](https://developer.apple.com/documentation/appkit/nsworkspace/openconfiguration/createsnewapplicationinstance) — 复用实例，避免强制新建。
4. [Apple：LSUIElement](https://developer.apple.com/documentation/bundleresources/information-property-list/lsuielement) — 包装器采用 agent 应用身份，不增加同名 Dock 入口。
5. [WebKit：Timelines Tab](https://webkit.org/web-inspector/timelines-tab/) — 完整性能分析需要区分脚本、布局、绘制等阶段，不能用 rAF 采样代替。
