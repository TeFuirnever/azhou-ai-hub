---
name: excalidraw-diagram
description: Build or edit accurate, editable Excalidraw scenes; render the real scene, inspect the image, run deterministic layout/style checks, and deliver source plus requested exports. Use for workflows, architectures, sequences, data flows, concept maps, or existing .excalidraw files. Supports native JSON, offline Mermaid/SVG conversion, official component libraries, CJK-safe SVG/PNG export, and optional interactive preview.
---

# Excalidraw Diagram

**🦊 阿舟 · Excalidraw Diagram**

> ✏️ 先让结构讲清关系，再让文字补充证据。

交付物必须包含可继续编辑的 `.excalidraw` 源文件。PNG、SVG、HTML 或截图都是衍生物，不能替代源文件。

## 启动协议

交互执行前读取 [brand-layer.md](references/brand-layer.md)，首条进度使用：

```text
🦊 阿舟 · Excalidraw Diagram 启动｜mode=<create|edit|render|export>｜deliverable=<format>｜scope=<diagram>
```

按需使用 `🧭 需求锁定`、`🔎 事实确认`、`✏️ 场景生成`、`🧪 审核第 n 轮`、`📦 交付完成` 和最终验证锚点。锚点只陈述真实进度。缺少权限或依赖时，用 `🔒 阿舟暂停这一项` 标记单项阻塞，继续不受影响的工作。

Emoji 只属于展示层。文件名、JSON 字段、状态枚举、命令、digest、测试名和证据数据保持纯文本。

## 不可跳过的交付合同

1. **先锁定任务。** 明确读者、核心结论、输入事实、画布用途、源文件路径和衍生格式。
2. **技术图先核实。** API、协议、事件名、数据格式和代码示例必须来自当前一手资料；不确定内容标成假设。
3. **结构先于装饰。** 先画分区、节点、主路径和反馈，再放标签、颜色和细节。
4. **源图必须可编辑。** 元素使用稳定且唯一的 id；容器文字双向绑定；连线落在真实节点上。
5. **真实渲染后才能判断。** JSON 可解析不代表图可用。必须渲染、查看成图、修复，再重跑检查。
6. **机器检查与人工判断分开。** 脚本证明结构和确定性；视觉可读性由具名 reviewer 或当前 agent 的实际图像检查证明。
7. **不得伪造通过。** renderer、浏览器或视觉能力缺失时，状态是 `hold`/`failed`，不能写 `passed`。

## 第一次运行

依赖、dry-run、安装和验证命令都在 [setup.md](references/setup.md)。先设置真实安装路径，不猜测 harness 目录：

```bash
SKILL_DIR=/absolute/path/to/excalidraw-diagram
```

需要改配色时，只修改 [color-palette.md](references/color-palette.md)。依赖或上游素材变化时，同时核对 [provenance.md](references/provenance.md) 与第三方许可证。

## 1. 需求与事实

把用户需求压缩成一条 visual thesis：读者看完图后，应能说出哪一个关系、顺序、边界或因果。

创建前确认：

- `mode`：create、edit、render 或 export；
- `audience`：谁使用，在哪个尺寸查看；
- `thesis`：图要证明什么，不只是列出什么；
- `facts`：必须出现的真实名称、流向、状态和证据；
- `deliverables`：至少 `.excalidraw`，以及用户需要的 PNG/SVG/HTML；
- `constraints`：品牌、语言、隐私、来源、现有模板和禁止改动项。

技术主题先检索官方规范或当前代码。把可核实事实放进图：真实事件、字段、调用、载荷、入口和失败分支。不要用“Service A”“处理数据”替代已经可得的具体信息。

## 2. 选表达法

先读 [diagram-types.md](references/diagram-types.md)，再按关系选择结构：

| 主要问题 | 优先结构 |
|---|---|
| 谁按什么顺序交互 | sequence / timeline |
| 责任与边界如何分层 | layered architecture / zones |
| 输入如何变成输出 | data flow / pipeline |
| 条件如何改变路径 | decision flow / state machine |
| 哪些角色承担哪些步骤 | swimlane |
| 一个概念如何展开或汇聚 | tree / fan-out / convergence |

复杂技术图同时保留三个缩放层：一眼能读出的主路径、清楚的责任分区、少量可验证细节。细节只为主结论服务；不要把文档整页搬上画布。

可复用起点：

- `templates/zoned-architecture.excalidraw`
- `templates/swimlane.excalidraw`
- `templates/sequence-frame.excalidraw`
- [element-templates.md](references/element-templates.md)
- [icon-catalog.md](references/icon-catalog.md) 与 `references/libraries/`

## 3. 构图

用 [design-system.md](references/design-system.md) 的网格、间距、路由和文本规则。推荐顺序：

1. 画布分区与阅读方向；
2. 主节点和主路径；
3. 条件、回路、异常与跨区连接；
4. 节点标签与证据块；
5. 色彩、层级和辅助注释。

构图硬规则：

- 每个视觉区域只有一个主要职责；
- 相同角色保持相同形状和配色；
- 主路径比辅助路径更显眼；
- 箭头从节点边缘出发并落到目标边缘；
- 优先使用水平/垂直分段，避免穿过节点和文字；
- 交叉不可避免时减少交叉次数，并让交点远离标签；
- 长文本拆成证据块或移到配套说明；
- 画布留出外边距，避免内容贴边或出现巨大空洞。

## 4. 生成可编辑场景

默认使用 hand-drawn preset：元素 `roughness: 1`，文字 `fontFamily: 1`。需要其他风格时必须由用户要求或既有资产合同决定。

场景顶层至少包含：

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "azhou-ai-hub/excalidraw-diagram",
  "elements": [],
  "appState": {"viewBackgroundColor": "#ffffff"},
  "files": {}
}
```

属性语义以 [element-types.md](references/element-types.md) 为准；快速索引见 [json-schema.md](references/json-schema.md)。

### 绑定完整性

容器与文字必须成对：

- shape 的 `boundElements` 引用 text id；
- text 的 `containerId` 指回 shape id；
- 同一 text 不绑定多个容器；
- 删除或换 id 时同步更新两端。

需要表达节点间关系的箭头必须声明 `startBinding` 和 `endBinding`。只有分隔线、时间轴或说明引线可以不绑定。

### 低代码入口

已存在 Mermaid、SVG 或官方组件库时，不必手写全部 JSON。读取 [advanced-workflows.md](references/advanced-workflows.md) 后选择：

- `scripts/mermaid-to-excalidraw.py`
- `scripts/svg-to-excalidraw.py`
- `scripts/excalidraw_lib.py`
- `references/libraries/`

转换结果仍要经过同一套风格、语义、渲染和视觉检查。转换成功不等于交付通过。

## 5. 渲染与修复循环

先运行结构检查，再渲染真实场景：

```bash
python3 "$SKILL_DIR/scripts/check-scene-hygiene.py" /absolute/diagram.excalidraw
python3 "$SKILL_DIR/scripts/audit-overlaps.py" /absolute/diagram.excalidraw

cd "$SKILL_DIR/references"
uv run python render_excalidraw.py /absolute/diagram.excalidraw --output /absolute/diagram.png
```

查看 PNG 本身，不只读 JSON。每轮至少检查：

- 主结论是否在 5 秒内可见；
- 必要节点、文本和流向是否齐全；
- 标签是否截断、溢出、重叠或出现 tofu；
- 箭头方向、端点和路由是否准确；
- 间距、对齐、密度和留白是否平衡；
- 证据块在交付尺寸下是否可读；
- 用户指定的语言、品牌和隐私边界是否满足。

发现问题后修改 `.excalidraw` 源文件，重跑受影响脚本，并重新查看渲染图。不要直接修 PNG 掩盖源场景问题。

## 6. 正式导出

需要 SVG/PNG 正式衍生物时使用官方引擎路径：

```bash
cd "$SKILL_DIR/references"
uv run python "$SKILL_DIR/scripts/export-official-svg.py" \
  /absolute/diagram.excalidraw \
  /absolute/diagram.svg \
  --png /absolute/diagram.official.png

uv run python "$SKILL_DIR/scripts/check-handdrawn-style.py" \
  /absolute/diagram.excalidraw

uv run python "$SKILL_DIR/scripts/visual-check.py" \
  --scene /absolute/diagram.excalidraw \
  --artifact /absolute/diagram.svg
```

导出接口、字体与 same-DOM gate 见 [export-api.md](references/export-api.md)。`scripts/render-svg.mjs` 是快速预览路径；正式 SVG 仍以上面的官方引擎导出为准。

## 7. 交付

先确认所有文件存在且可读，再发送 `📦 交付完成`。最终收据使用 [brand-layer.md](references/brand-layer.md) 定义的 `excalidraw-diagram.receipt.v1`，至少写清：

- `status` 与 `mode`；
- 源 `.excalidraw` 路径；
- PNG/SVG/HTML 衍生物路径；
- 已运行的 deterministic checks；
- 实际查看的渲染图与 reviewer；
- `holds`、限制和一个 next action；
- 可用于后续改进的 learning signal。

只在全部声明检查真实完成后输出 `✅ 验证通过`。失败使用 `❌ 验证失败` 并写出具体 gate 和影响。

## 历史与受控演化

跨 Codex、Claude、zcode 或其他 harness 的运行证据按 [history-evolution.md](references/history-evolution.md) 脱敏聚合。私密 prompt、原始对话、用户路径和未公开资产不进 Git。

历史观察不能直接改 live skill。候选变更必须遵守 [evolution-contract.md](references/evolution-contract.md)：先有回归，再做隔离 candidate；确定性检查、具名视觉复核、paired 多数、无安全回归和 exact-diff 人类批准缺一不可。

## 快速故障表

| 现象 | 处理 |
|---|---|
| Playwright 未安装 | 按 [setup.md](references/setup.md) 在 skill 自带环境安装 |
| Chromium 缺失 | 先按 [setup.md](references/setup.md) 运行 `check-playwright-runtime.py`；仅在退出 `2` 时安装一次 |
| JSON 能开但 PNG 异常 | 用 official exporter 复核，并检查元素属性/字体 |
| 连线漂移 | 修复双向 binding 与端点坐标，不补装饰线 |
| CJK 乱码/tofu | 使用随包字体与 official export；不得用截图遮盖 |
| overlap 脚本误报 | 查看成图和具体坐标；记录具名人工判定，不伪造脚本通过 |
| 无视觉查看能力 | 交付源文件与机器结果，视觉 gate 保持 hold |
