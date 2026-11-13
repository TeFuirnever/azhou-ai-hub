---
name: dsh-responsive-ui
description: "设计、实现或审查窄屏布局、文本截断/标题换行、纯图标操作、混合输入设备的 hover/tooltip、移动键盘与宽度变化时焦点。"
metadata:
  internal: true
---

# dsh-responsive-ui

本 Skill 仅用于当前项目。用户授权、项目 AGENTS.md 和实际宿主能力优先。

1. 以本产品实际支持的最小 viewport 和断点为准，检查页面/弹窗整体，不套用 DSH 固定 390 CSS px 下限。断点两侧、长文本/本地化、受限高度下，主操作可达，无非预期重叠、裁剪或整页横向滚动。
2. 先重新分配空间或换行，再考虑截断、图标化或移入 More。主操作和关键状态不能消失；不靠全局 overflow hidden、缩小所有字号或点击热区掩盖冲突。
3. 截断内容必须能在可到达的菜单/详情中完整查看。错误与关键信息不能只留 ellipsis；没有其他完整展示位置就直接展示。tab、selector、按钮等优先单行，页标题优先完整并让动作换行，卡标题自然换行或提供全文入口。
4. 图标化要求含义清楚/熟悉、可访问名称和适用的说明，不能只因宽度不足把陌生导航换成无法识别的符号。触摸用户不能依赖 hover 才能发现动作。
5. 布局用宽度，输入呈现用 `(pointer: coarse)`、`(hover: hover)` 等真实能力，不按 user-agent 或“窄屏=触摸=无键盘”推断。混合设备的 JS hover 忽略 touch 事件；hover 样式只控制 hover，不抹掉 selected、expanded、pressed、enabled 和 focus-visible。
6. 手机轻触不能留下仅 hover 才应有的背景/按钮；无 hover 时动作持续可见或有明确入口，键盘也能到达。不能 blur 焦点来清 hover。
7. 辅助动作名称/快捷键 tooltip 在触摸操作中不应拦截原动作；有实质说明的信息 tooltip 提供 tap-to-show、关闭和键盘方式。不能以关闭所有 tooltip 解决移动问题。
8. 宽度切换后仍可交互的控件保留 focus 与草稿，不只为布局 remount。控件确实被隐藏/删除时把焦点送到合理剩余入口，避免无意弹出移动键盘；非用户意图不自动聚焦文本框。
9. 粗指针上的网页输入按需要保持至少 16px，避免 iOS Safari focus zoom；细指针保留现有紧凑尺寸。该做法须在目标页面/设备验证，不宣称 CSS query 能检测物理键盘。

验证实际动作、全文读取、主操作、焦点顺序与窄宽切换，在相关主题/平台中观察。fixture、桌面模拟和真实触摸设备证据分别报告，缺设备不记为已验收。

来源、适配边界和许可证见 [provenance.md](provenance.md)。
