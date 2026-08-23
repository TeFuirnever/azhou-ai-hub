# Excalidraw scene quick reference

本页帮助排查手写 JSON，不替代 Excalidraw 官方类型。完整属性、默认值和枚举以本包从官方源码整理的 [element-types.md](element-types.md) 为准。

## Scene envelope

| Key | Contract |
|---|---|
| `type` | 固定为 `excalidraw` |
| `version` | 当前模板使用 `2` |
| `source` | 生成来源；本 skill 使用 `azhou-ai-hub/excalidraw-diagram` |
| `elements` | 元素数组；至少一个未删除元素 |
| `appState` | 画布与导出状态；可为空对象 |
| `files` | 图片等二进制资源的映射；无资源时为空对象 |

## Shared element contract

每个元素需要唯一 `id` 和合法 `type`。常见几何字段为 `x`、`y`、`width`、`height`、`angle`；视觉字段为 `strokeColor`、`backgroundColor`、`fillStyle`、`strokeWidth`、`strokeStyle`、`roughness` 与 `opacity`。

常用类型：

| Type | 适合表达 |
|---|---|
| `rectangle` | 组件、动作、职责区内节点 |
| `ellipse` | 外部角色、开始/结束、观察点 |
| `diamond` | 条件或需要选择的分支 |
| `arrow` | 有方向的语义关系 |
| `line` | 分隔、时间轴、树干等无方向结构 |
| `text` | 标题、标签、证据与注释 |
| `frame` | 可编辑分组或导出区域 |

## Text

关键字段：

- `text` 与 `originalText`：展示文本和原始文本；
- `fontSize`、`fontFamily`、`lineHeight`；
- `textAlign`、`verticalAlign`；
- `containerId`：容器文字指向 shape；自由文字为 `null`。

默认阿舟手绘风使用 `fontFamily: 1`。CJK 正式导出要经过随包字体和同 DOM 视觉检查。

## Connections

箭头的 `points` 是相对坐标数组；至少包含起点与终点。语义连接同时声明：

```json
{
  "startBinding": {"elementId": "source-node", "focus": 0, "gap": 2},
  "endBinding": {"elementId": "target-node", "focus": 0, "gap": 2},
  "startArrowhead": null,
  "endArrowhead": "arrow"
}
```

常见 arrowhead 包括 `arrow`、`triangle`、`dot`、`bar` 或 `null`。具体可用值随官方版本变化，升级时以 [element-types.md](element-types.md) 与 exporter 测试为准。

## Container symmetry

绑定文本时两边都要更新：

```json
{
  "shape": {"id": "node-a", "boundElements": [{"id": "label-a", "type": "text"}]},
  "text": {"id": "label-a", "containerId": "node-a"}
}
```

这是关系示例，不是可以直接写入 `elements` 的完整元素。

## Before delivery

1. JSON 能解析，顶层 envelope 完整。
2. id 唯一，删除元素不参与可见布局。
3. 数值字段有限且尺寸合理。
4. 容器/文字和箭头绑定一致。
5. hand-drawn、hygiene、overlap 检查完成。
6. official renderer 真实渲染并查看成图。
