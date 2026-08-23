# Scene fragments

这些片段用于手写小型场景。复杂图优先调用 `scripts/excalidraw_lib.py` 或从 `templates/` 开始，避免复制大量易漂移字段。

默认交付风格：`roughness: 1`、文字 `fontFamily: 1`。颜色从 [color-palette.md](color-palette.md) 取值。字段合法值以 [element-types.md](element-types.md) 为准。

## 最小顶层

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

## 带文字的节点

shape 与 text 的引用必须对称。位置、宽高和 `seed` 是示例值，创建新元素时换成稳定唯一值。

```json
[
  {
    "id": "node-ingest",
    "type": "rectangle",
    "x": 120,
    "y": 160,
    "width": 220,
    "height": 96,
    "strokeColor": "#C65A18",
    "backgroundColor": "#FEF0DF",
    "fillStyle": "solid",
    "strokeWidth": 2,
    "strokeStyle": "solid",
    "roughness": 1,
    "opacity": 100,
    "angle": 0,
    "seed": 41001,
    "version": 1,
    "isDeleted": false,
    "groupIds": [],
    "boundElements": [{"id": "label-ingest", "type": "text"}],
    "roundness": {"type": 3},
    "link": null,
    "locked": false
  },
  {
    "id": "label-ingest",
    "type": "text",
    "x": 150,
    "y": 194,
    "width": 160,
    "height": 28,
    "text": "Validate input",
    "originalText": "Validate input",
    "fontSize": 20,
    "fontFamily": 1,
    "textAlign": "center",
    "verticalAlign": "middle",
    "lineHeight": 1.25,
    "strokeColor": "#6F3810",
    "backgroundColor": "transparent",
    "fillStyle": "solid",
    "strokeWidth": 1,
    "strokeStyle": "solid",
    "roughness": 1,
    "opacity": 100,
    "angle": 0,
    "seed": 41002,
    "version": 1,
    "isDeleted": false,
    "groupIds": [],
    "boundElements": null,
    "containerId": "node-ingest",
    "link": null,
    "locked": false
  }
]
```

## 节点到节点的箭头

`points` 相对箭头自身的 `x`/`y`。需要绕行时加入中间点，不要把 `width`/`height` 当成绝对终点。

```json
{
  "id": "flow-ingest-store",
  "type": "arrow",
  "x": 340,
  "y": 208,
  "width": 140,
  "height": 0,
  "points": [[0, 0], [140, 0]],
  "strokeColor": "#C65A18",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 2,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "angle": 0,
  "seed": 41003,
  "version": 1,
  "isDeleted": false,
  "groupIds": [],
  "boundElements": null,
  "startBinding": {"elementId": "node-ingest", "focus": 0, "gap": 2},
  "endBinding": {"elementId": "node-store", "focus": 0, "gap": 2},
  "startArrowhead": null,
  "endArrowhead": "arrow",
  "link": null,
  "locked": false
}
```

## 自由标题

```json
{
  "id": "title-main",
  "type": "text",
  "x": 80,
  "y": 60,
  "width": 520,
  "height": 44,
  "text": "Evidence becomes a release gate",
  "originalText": "Evidence becomes a release gate",
  "fontSize": 32,
  "fontFamily": 1,
  "textAlign": "left",
  "verticalAlign": "top",
  "lineHeight": 1.25,
  "strokeColor": "#6F3810",
  "backgroundColor": "transparent",
  "fillStyle": "solid",
  "strokeWidth": 1,
  "strokeStyle": "solid",
  "roughness": 1,
  "opacity": 100,
  "angle": 0,
  "seed": 41004,
  "version": 1,
  "isDeleted": false,
  "groupIds": [],
  "boundElements": null,
  "containerId": null,
  "link": null,
  "locked": false
}
```

## 片段验收

- 所有 id 在整个 scene 唯一。
- 非删除元素的 `width`、`height` 与坐标是有限数字。
- shape/text 绑定双向一致。
- 语义箭头两端都有 binding。
- `check-scene-hygiene.py`、style gate、overlap audit 与真实渲染全部完成。
