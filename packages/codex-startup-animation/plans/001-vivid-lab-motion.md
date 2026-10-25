# 001 — 让阿舟的敲键点亮实验室

> 历史范围：本计划针对0.5.0之前的源码，执行结果为0.5.0。下文“当前”、行号、代码片段与命令均相对该次审计；`original/` 和 `emil/` 是审计临时快照路径。0.5.1已改为隐藏构建载荷，旧dist存在性预期不再适用。现行构建、安装和核查命令见 [项目 README](../README.md)。

- **Status**: DONE — 主执行者已完成粗演、精修、最终安装版运行及证据记录；未覆盖项明确列在文末。审计作者的独立结论仍限于静态代码。
- **Commit**: 原项目基线 `c743c2b`（主执行者核实）；审计作者最初收到的是无Git元数据的源码快照。当前改动未commit或push。
- **Severity**: MEDIUM
- **Category**: Purpose & frequency；Physicality & origin；Performance；Accessibility；Cohesion & tokens；Missed opportunities。
- **Estimated scope**: 3 个实现文件：`index.html`、`style.css`、`animation.js`。沿用 Swift/AppKit/WKWebView、现有 WebGL 局部网格、私有原图和 7.8 秒单次时间轴。
- **Audit scope**: 仅对提供的源码做静态分析；本计划作者未观看本轮真实播放，未打开素材，未测 GPU 或合成器性能。以下“当前”均为代码事实，视觉效果为待预演验证的设计目标。

## Problem

当前实现已有可用的场景结构、局部手部/头部动作、时间轴、预览控制和原生交接，主要缺少色彩辨识度，以及“阿舟敲键 → 实验室回应 → 标题点亮”的视觉因果。增强应围绕这个瞬间，不能把所有旧特效重新堆满画面。

### Before | After | Why

| 项目 | Before | After | Why / 审计依据 |
| --- | --- | --- | --- |
| 1. 色彩与最大化构图 | `style.css:1–5` 大量 `#ded9cf`、`#f1eadf`、`#263c34`、棕色信号；`animation.js:18` 无限跟随窗口等比放大整个场景；`index.html:51` 画布 backing 固定 1080²。 | 静态粉紫实验室底色，粉色、紫色、青色只集中在动作节点；扩大窗口后背景延展，主内容保持安全尺寸，人物按源图像素与实际 DPR 控制放大。 | 鲜明的角色氛围依赖构图和色彩关系。最大化不能被误解为放大低分辨率素材。AUDIT.md:97–104；性能检查参考 :71–80。 |
| 2. 实验室描线开场 | `index.html:23–38` 房间线条始终存在，当前只对人物和台灯做渐入；旧项目拥有轮廓预编译、分段描绘能力。 | 从电脑和台灯附近向外显现 6–8 条实验室短线；后退为低对比静态环境。角色从开场即是主角，不先展示另一个头像/雷达故事。 | 复用“线条构成场景”的能力解释实验室启动，同时省掉全屏碎片解体。AUDIT.md:7、48–58、106–115。 |
| 3. 更清楚的角色动作和回应 | `animation.js:31–43,68–74` 头/手/发梢已有局部动作；`animation.js:80–84` 信号路径开始时间接近敲键，但回应只有小圆点。 | 保持单张插图网格的能力边界，稍增强前倾与敲键；最后一击触发沿路径移动的 8 个短促光点、终点单次光圈，并让台灯/屏幕回应。 | 让效果说明角色动作造成了什么。重点是手部 → 电脑 → Codex 标识的顺序，不能靠整张图漂浮假装角色表演。AUDIT.md:7、22–26、48–58、99–104。 |
| 4. 单次色光扫过、充分阅读、安静交接 | 当前 `animation.js:77–85` 文案渐入后基本静态；旧项目 `original/animation.js:230–235` 有光带和持续粒子，:188–199 有 CRT 式收缩/闪白。 | 只在回应瞬间扫一次狭窄光带；字幕出现前所有高显著特效收束。三文案稳定读完；7.8 秒仅由当前 native 交接退出，不复活旧的压扁/亮闪。 | 复用能强化状态变化的光带；避免与 native 的 280ms 淡出叠加，且不把真实启动进度虚构成百分比。AUDIT.md:7、36–44、60–69、106–115。 |

### 当前关键代码（原样）

`animation.js:18`：

```js
function layout(){const b=root.getBoundingClientRect(),s=Math.min(b.width/1000,b.height/658);scene.style.transform=`translate(${(b.width-1000*s)/2}px,${(b.height-658*s)/2}px) scale(${s})`;}
```

`animation.js:31,35–38`：

```glsl
float angle=lean*.029+nod*.016;
p.y-=leftHand*.0085*soft(aUV,vec2(.558,.583),vec2(.076,.032));
p.y-=rightHand*.0070*soft(aUV,vec2(.624,.574),vec2(.033,.032));
p.x+=tail*.007*soft(aUV,vec2(.164,.496),vec2(.155,.245));
p.y-=tail*.003*soft(aUV,vec2(.164,.496),vec2(.155,.245));
```

`animation.js:68–74`：

```js
const started=performance.now(),t=ms/1000,arrival=ease(t/.55),lean=ease((t-.55)/.8)*(1-ease((t-2.55)/.7));
const leftTap=pulse(t,1.32,.15)+pulse(t,1.80,.15)+pulse(t,2.28,.19);
const rightTap=pulse(t,1.55,.15)+pulse(t,2.02,.16),taps=Math.max(leftTap,rightTap);
const nod=pulse(t,3.02,.40)-pulse(t,3.45,.36)*.35;
const blink=pulse(t,1.02,.09)+pulse(t,3.85,.105);
const tail=Math.sin((t-.55)*2.4)*ease((t-.55)/.65)*(1-ease((t-3.5)/.8));
renderer?.({lean:reduced?0:lean,nod:reduced?0:nod,leftHand:reduced?0:leftTap,rightHand:reduced?0:rightTap,blink:reduced?0:blink,tail:reduced?0:tail,warmth:ease((t-2.3)/.6)});
```

`animation.js:11,107` 只在初始化读取系统减少动态设置，并提供手动 `setReduced(value)`；本快照没有对应 MediaQueryList 的 `change` 监听。`animation.js:78` 的 `.copy-rule` 仍在减少动态模式下从 `scaleX(0)` 展开。

`Native/App.swift:225–232` 已有一次原生交接淡出：

```swift
terminating = true; watchdog?.invalidate(); snapshots.forEach { $0.cancel() }
log("handoff-fade-start", ["frontmost": appInfo(NSWorkspace.shared.frontmostApplication)])
NSAnimationContext.runAnimationGroup({ context in
    context.duration = 0.28; self.window.animator().alphaValue = 0
}, completionHandler: {
    self.log("handoff-fade-complete", ["frontmost": self.appInfo(NSWorkspace.shared.frontmostApplication), "target": self.appInfo(self.target)])
    self.window.orderOut(nil); NSApp.terminate(nil)
})
```

## Target

### 固定内容与能力边界

- 人物仅使用现有 `assets/private` 的女性 Q 版工作姿态图；不新增或生成图像，不改原素材库，不复用旧角色头像。
- 标题：`阿舟的 Agent 实验室`；英文：`AZHOU / AGENT LAB`；字幕：`和阿舟一起，把想法做出来。`。
- 保持局部纹理网格表现前倾、敲键、抬头、发梢跟随；单张图无法真实表现换手势、转身、走动或大幅关节遮挡，不能用变形冒充这些动作。
- 7.8 秒前端单次片长保留。native 已负责真实程序启动、重复打开和 280ms 窗口淡出，本计划不重写这些机制。

### 精确色彩、缓动与尺寸约束

在 `style.css` 根级集中声明：

```css
--lab-paper: #fff4fc;
--lab-lilac: #f0e5ff;
--lab-ink: #352143;
--lab-muted: #715780;
--lab-pink: #ef5da8;
--lab-violet: #8c5cf6;
--lab-cyan: #25bfd0;
--lab-warm: #ffc86a;
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
```

- 文字面板保持浅色，主标题用 `--lab-ink`；不要给所有字加辉光。
- 饱和色集中在左侧场景弧线、电脑信号、Codex 标识和一次回应；静态底色采用粉/紫渐变。大面积背景和人物不做逐帧 hue/filter 变化。
- 保留设计坐标 1000×658。当前人物 CSS 宽 540；若保持整个核心场景等比缩放，`s = min(frameW/1000, frameH/658, sourceW/(540*DPR))`。源图1254、DPR2时上限约1.161，即人物≤627pt。让 `.window` 的静态底色填满 visibleFrame，核心场景居中；不得出现黑色或异色 letterbox。
- 若真实最大化观察显示核心场景占比太小，可调整左右布局的间距，但人物的实际 CSS 宽仍必须满足 `sourceW / DPR`；不要通过超过上限放大图解决空间问题。
- 将 canvas backing 改为 `min(sourceW, ceil(actualCSSWidth * DPR))`，高度按同一比例。只在载入/尺寸变化时修改 backing 并更新 `gl.viewport`，不逐帧调整。当前固定1080²会让超过540pt@2x的画布提前发生画布上采样。
- 用当前实测 DPR 和实际 DOM bounds 验证；“627pt”仅为1254图在2x显示下的推导上限，并不是所有显示器的固定限制。

### 同一时间轴

| 时间 | 主动作 | 陪衬与文案 | 减少动态模式 |
| --- | --- | --- | --- |
| 0.00–0.55 | 人物保持工作姿态，最多12设计像素渐入位移；场景主体立刻可辨。 | 台灯/电脑附近先亮；6–8条实验室线在0.12–0.92秒依次显现，单线间隔40ms。 | 人物和场景用200ms opacity进入，取消位移和描线路径运动。 |
| 0.55–2.47 | 前倾；保留1.32、1.55、1.80、2.02、2.28秒敲键中心，最后一次更明确。 | 标题1.38–1.93出现，英文1.98–2.36出现。敲键灯光只响应相应手部脉冲。 | 姿态固定；电脑小光点用200ms opacity表明状态变化。 |
| 2.28–3.22 | 最后一击后回正并在3.02秒轻点头。 | 8个光点沿电脑→Codex路径传递，最后一个3.16秒消失；终点只亮一次回应环；2.66–3.08秒扫一次局部光带。 | 隐藏光点、环的扩张和光带，Codex标识用200ms opacity出现。 |
| 3.22–3.64 | 动作进入安定；3.85秒可有现有一次轻眨眼。 | 字幕渐入；所有高显著效果在3.50秒前消失，避免与字幕争抢。 | 字幕200ms opacity，保留清楚的状态结果。 |
| 3.64–7.05 | 4.30秒之后头、手、发梢静止。 | 三项文案完整稳定；只保留低对比、静态环境细节。 | 完全稳定。 |
| 7.05–7.80 | 不再制造新动作。 | 小辅助符号可在200ms内淡去；标题、人物、字幕继续保留到真实交接。 | 同样仅opacity变化。 |
| 完成后 | 前端发送一次complete。 | native核实目标后，以现有280ms整窗淡出交接；若仍等待目标，保留完整最后画面与现有等待提示。 | 同现有交接逻辑，不新增几何收缩。 |

### 复用清单与明确舍弃

| 原实现位置 | 可复用内容 | 本轮变体 | 不带回的内容 |
| --- | --- | --- | --- |
| `original/animation.js:22–27,232–235` | 一次性建立粒子节点、确定性位置、transform/opacity。 | 只建立8个粒子，绑定到2.28秒最后一击；每个活跃600ms，间隔40ms，总窗口至3.16秒。 | 14个粒子全程任意漂浮，不让粒子穿过脸部或文案。 |
| `original/style.css:1` 的 `.light-sweep`；`original/animation.js:230–231` | 预绘制渐变层，translateX加opacity。 | 狭窄信号区域内一次420ms光带，峰值opacity≤0.16；缩到电脑/标识区域，不扫全屏。 | 50%额外inset的大画布、强闪白、读字时重复扫光。 |
| `original/animation.js:39–46,148–179` | Path2D预编译和停止重复绘制的缓存思想。 | 对当前房间6–8条矢量短线做预定义显现；优先SVG/遮罩层的transform与opacity。 | 旧 `CONTOUR_PATHS` 数据、头像分块、约1400碎片、每帧重建完整角色轮廓。 |
| `original/index.html:45–48`；`original/style.css:9–15` | 单层细线光环和小中心点。 | 电脑信号到达时在Codex标识后回应一次：240ms opacity与scale(.94→1.06)，起点与标识中心重合。 | 雷达头像架构、持续旋转刻度、从scale(0)暴涨、无因果循环。 |
| `animation.js:20–64,68–74` | 当前局部网格与手/头分离的时间关系。 | 试演上限：头部角系数`.045/.022`，左右手Y系数`.0115/.0095`，发梢X系数`.009`；真实慢放后若出现橡皮变形，逐项退回原值。 | 整图呼吸缩放、桌子一起移动、伪造新手势。 |

上述姿态增强数值是待粗演检验的上限，不是“已证明素材安全”的结论。先看手指/键盘、眼眶、颈部、马尾根部和桌边的极限帧，再决定是否采用。

## Repo conventions to follow

- 沿用 `animation.js:65–94` 的一个绝对时间 `t`，不要引入独立计时器、随机数或新的动画库。停/播/拖动/重播必须可重复。
- 参考旧实现 `original/animation.js:39–46` 的“预先创建”、:148–151的“相同状态跳过重画”；不要把旧纹理分块重新加入当前项目。
- 保持 `window.launcherUI`、ready/complete消息结构、`report()` 的测量边界。`animation.js:99` 已明确 rAF/JS 统计不代表GPU或合成器性能，继续保留。
- 固定视觉装饰优先CSS/WAAPI的transform/opacity。为了预览seek，可以在现有play/stop/replay/seek入口同步少量预创建动画的currentTime；不要另建通用时间轴系统。
- WebGL只处理现有局部图像变形。缓存最后的uniform状态，4.30秒之后状态不变时不要反复提交同一画面；resize、seek、replay和减少动态变化时仍要重画。

## Steps

1. **`style.css`、`index.html`：**集中添加上述色彩/缓动令牌，替换房间、光线、文案、边框的米绿棕色。静态背景可延伸到窗口边界。先只改变色彩与安全布局，截图核实标题/角色/字幕比例。
2. **`animation.js`：**完成源图/DPR尺寸上限和按需backing resize；`report()`增加人物实际显示宽高、backing宽高及source-to-screen比。这样最大化下是否上采样可直接复核。
3. **`index.html`、`style.css`：**复用当前房间SVG中的线段，最多新增8条短线与1个回应环；添加一个局部光带容器和8个预创建光点。元素标记aria-hidden，不遮挡任何控制或主文案。
4. **`animation.js`：**按同一时间表接上最后一击、定向传递、回应环和单次光带；先不提高mesh幅度，完整粗演确认因果顺序成立后，再逐项试验上面的动作系数上限。
5. **`animation.js`、`style.css`：**统一入口/退出用`--ease-out`，屏幕内往返用`--ease-in-out`；继续允许叙事性的入场/动作超过300ms，不把7.8秒片段当普通UI切换。小状态反馈200–240ms。渐变、阴影均静态；禁止每帧动画blur、box-shadow、width、left或top。
6. **`animation.js`：**为`prefers-reduced-motion`加change监听并走同一`setReduced`路径；关闭位移、网格姿态、粒子、扩张和扫光，保留200ms透明度反馈。`.copy-rule`减少动态时直接保持scaleX(1)，只做opacity。
7. **`animation.js`：**装饰高显著动作3.50秒前结束，4.30秒后画布进入稳定状态。保留三项文案至原生交接；不添加全景缩放、场景压扁或前端黑幕。
8. **主执行者：**完成真实窗口粗演后调整幅度；用最终.app完整播放、录像与关键帧验收。记录审美判断和工程测量，分别标注。

## Boundaries

- 不新增依赖、素材生成、配置面板、通用粒子引擎、通用动画系统。
- 不改变标题、英文、字幕或女性Q版角色身份，不往公开仓库提交私有图与衍生产物。
- 不修改真实Codex、不重写应用身份、构建归档或启动机制。native窗口最大化由主执行者负责；本计划只处理前端如何适配。
- 不把启动时间百分比、线条完成度或粒子抵达伪称为真实Codex就绪进度。
- 不以旧版“酷炫程度”为唯一准则恢复旧效果；本计划只复用当前叙事需要的能力。
- 源码快照行号只用于定位。如果实现已并行变更，先对照实际代码，不盲目套补丁；不得覆盖其他执行者改动。

## Verification

### Mechanical

在原项目根目录执行以下已有命令；本计划作者尚未执行：

```sh
node --check animation.js
bash tools/build-macos.sh
python3 tools/verify-artifacts.py
```

期望：JS语法正确；native构建与签名校验通过；dist仍只有一个身份为`local.azhou.codex-startup`的项目入口。不得为了通过检查改掉私有资产保护。

### Feel check — 必须实际执行

- 用原生预览在当前显示器visibleFrame播放完整7.8秒。首先按正常速度看清“敲键→信号→标识亮→阿舟回正”，再用已有seek查看1.32、2.28、2.70、3.02、3.64、5.50、7.30秒。
- 局部mesh极限位置：手部没有离开键盘、不拉伸桌边；眼眶和头发边缘没有折线/拉扯；角色没有随光带一起缩放。
- 粒子只在电脑和Codex标识之间活动。3.64–7.05秒主标题、英文、字幕完整清晰，没有光点和光带穿过文字。
- 在2x屏幕读取report，人物实际宽≤627pt，backing不大于源图1254，也不低于实际显示像素需求；异常情况明确记录实际比例，不声称像素一比一。
- 拖动timeline、暂停、重播，单次光圈和光带应回到对应绝对时间，不残留上一遍节点、不重复触发native完成消息。
- 使用`launcherUI.setReduced(true)`检验所有新效果分支；还需在系统或WebKit实际切换减少动态，确认change监听生效。减少动态下仍看得出电脑与标识回应，但不存在位移/旋转/缩放扫光。
- 正常.app模式观看7.8秒结束到真实Codex显示，继续复用现有native280ms淡出；没有一层前端黑幕或第二次收缩。
- 对比日志的rAF间隔和JS提交时间；任何“没有卡顿”的结论必须结合录像/真实观看，必要时再用WebKit性能工具定位具体问题。不能只凭rAF统计写“GPU 60fps”。

### Done when

- 四项高价值改造在实际画面中清楚可辨，同时角色与三项文案保持主次稳定。
- 具有完整正常速度播放记录和上述关键时刻截图；审美检查与工程检查各有独立记录。
- 原生最大化、清晰度、暂停/seek/replay、减少动态和最终交接均有实际验证或明确的未验证标记。
- 构建成功不等于本计划完成；需要主执行者真实播放后将本计划状态改为DONE并填证据路径。


## Execution record — 2026-10-24

主执行者按本计划先完成原生最大化粗演，再精修并构建安装0.5.0/build2；最终真实运行和重复正常构建完成。0.5.0完成时的实装与本计划的试验建议有以下明确差别：

- 复用现有SVG房间线条的40ms错开显现，配合36枚有限入场后静止的刻度；没有新建完整Path2D轮廓系统。
- 光带实际为2.42–3.08秒、位于人物后方；8个粒子2.28–3.16秒，Codex回应环2.87–3.22秒。高显著辅助运动仍在3.50秒前完成。
- 网格最终角系数0.035/0.018，左右手0.0100/0.0080，发梢X系数0.008，末次左手敲键1.15。粗演保留原系数后再精修，没有直接使用试验上限。
- 原生及源码预览实测1512×889点、DPR2；人物627点，backing1254像素；两者bounds、viewport及像素配置一致。
- 最终正常安装版一次完整播放、重复打开一次、复用既有官方主程序、一次激活/淡出/退出；0失败。正常构建安装再次执行没有重建旧入口或ZIP。
- 真实WKWebView预览的暂停、继续、定位、三次重播、减少动态分支：128个机械断言0失败。系统减少动态设置的真实切换、冷启动、其他显示器/浏览器版本没有补测，不能标记通过。
- 子任务完成了代码级review-animations复核；没有独立远程视觉或运行评审。

完整证据在 `.local/evidence/20261024-vivid/`：
`rough-maximized.mov`、`final-installed.mov`、`acceptance.json`、`preview-installed-parity.json`、`preview-controls/summary.json`，以及2.28、2.90、5.50秒精确截图。详见 [本轮验收](../docs/azhou-vivid-maximized-verification.md)。
