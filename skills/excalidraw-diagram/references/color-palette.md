# Azhou diagram palette

本文件是 `excalidraw-diagram` 的唯一颜色权威。换品牌时只改这里；不要把第二套色值写进 `SKILL.md`、模板或脚本。

## 阿舟核心色

角色资产的四个核心填充色来自阿舟视觉系统。图表只借用颜色，不复制角色形象：

| Token | Hex | 图表用途 |
|---|---|---|
| `fox-orange` | `#FA9439` | 主流程、当前焦点、关键节点 |
| `paper-cream` | `#FEF9EB` | 主卡片浅底、画布暖区 |
| `ink-brown` | `#6F3810` | 橙/奶油底上的标题与描边 |
| `peach` | `#FAA67C` | 次级强调、人工动作 |

核心色用于身份锚点，不承担所有状态。状态色必须能被文字和形状同时识别，不能只靠色相。

## 语义组合

| 语义 | Fill | Stroke | Text |
|---|---|---|---|
| Primary / active | `#FEF0DF` | `#C65A18` | `#6F3810` |
| Secondary / neutral | `#E8F1FF` | `#3E6FA8` | `#24364B` |
| External system | `#F1ECFF` | `#7357A6` | `#372B50` |
| Human review | `#FFF0EA` | `#C46A4A` | `#633322` |
| Decision | `#FFF6CC` | `#A66A00` | `#5B3A00` |
| Success | `#E3F7EA` | `#2F7D4A` | `#214F31` |
| Warning / hold | `#FFF0D6` | `#B86500` | `#673A00` |
| Failure | `#FFE7E7` | `#B43A3A` | `#6E2020` |
| Disabled / historical | `#EEF1F4` | `#78838F` | `#4A535C` |

历史或不可用节点除灰色外，再使用 `strokeStyle: "dashed"`。成功、警告和失败节点必须带可读标签或图形差异。

## 文字与证据块

| Role | Color |
|---|---|
| Page title | `#6F3810` |
| Section title | `#C65A18` |
| Body | `#344054` |
| Annotation | `#667085` |
| Inverse text | `#FFFFFF` |
| Code background | `#1F2937` |
| Code text | `#F8FAFC` |
| Data accent | `#86EFAC` |

## 线条与画布

- 默认画布：`#FFFFFF`。
- 主路径：`#C65A18`，`strokeWidth: 2` 或 `3`。
- 次路径：`#526579`，`strokeWidth: 2`。
- 分区边界：`#B8C2CC`，优先虚线或低对比实线。
- 时间轴/树干：`#6B7280`；节点圆点可用 `#FA9439`。

## 使用规则

1. 同一张图最多使用一个主色、三个语义状态色和中性色。
2. 浅底配深描边；正文对比不足时先改文字色，不加阴影补救。
3. 颜色不表达顺序；顺序用位置、编号和箭头。
4. 颜色不表达唯一状态；同时使用标签、形状或线型。
5. 技术证据块保持深底高对比，避免用阿舟橙作为大段代码背景。
