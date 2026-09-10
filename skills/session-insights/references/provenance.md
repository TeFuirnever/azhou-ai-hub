# Provenance · Session Insights

本包**零 vendored 字节**：未复制任何上游代码、模板或文案，因此不需要 `THIRD_PARTY_NOTICES.md` 条目。下列来源仅作机制参考（prior art），以不可变 pin 记录；机制背景见仓库研究笔记 [agent-insights-industry-survey](../../../docs/research/2026-09-07-agent-insights-industry-survey.md) 与 [zcode-session-store-format](../../../docs/research/2026-09-10-zcode-session-store-format.md)。

| 来源 | 角色 | Pin | 许可证 |
|---|---|---|---|
| [awesome-skills/insights](https://github.com/awesome-skills/insights) | 可移植社区实现：跨 harness 发现 → 元数据 → 聚合 → 渲染管线与 200 会话上限的参考 | URL pin，2026-09-07 访问；未记录 commit，因为未复制任何字节 | MIT（未复制字节，无 notice 义务） |
| [Claude Code `/insights` 机制解析（Vincent Qiao 博客）](https://blog.vincentqiao.com/en/posts/claude-code-insights/) | 官方 `/insights` 的元数据先行、增量缓存与分节生成机制转述 | URL pin，2026-09-07 访问 | 博客文章，非代码来源 |
| [atani/codex-insights](https://github.com/atani/codex-insights) | Codex 会话分析器的指标面参考 | URL pin，2026-09-07 访问；未记录 commit，因为未复制任何字节 | 未复制字节，许可证不影响本包 |

更新路径：若未来需要逐行对照上游实现，先在研究笔记中记录不可变 commit 与许可证，再评估是否仍维持零 vendor；复制任何字节都必须同步进入 `THIRD_PARTY_NOTICES.md` 与本表。
