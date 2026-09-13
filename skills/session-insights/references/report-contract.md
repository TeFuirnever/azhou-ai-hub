# Report Contract · Session Insights

本文件是 `session-insights` 聚合与报告的口径合同：聚合器语义以这里为准，`benchmarks/session-insights/` 的 golden 聚合把它钉成回归基线。所有机器字段名纯 ASCII；所有时间戳为 UTC ISO 8601；hour 分桶一律按 UTC。

## 扫描与裁剪

- 默认 `--days 30`、`--max-sessions 200`（最近优先，按会话最大时间戳排序）。
- 窗口与上限锚定 **store 内最新观察到的会话时间戳**（`newest_session_at`），不是墙钟 now——静态 store 的聚合结果必然确定。
- 会话进入窗口的条件：会话最大时间戳 >= `newest_session_at - days`；通过窗口后再按新近度截到 `max_sessions`。
- 解析为流式逐行，从不整读文件。跳过：malformed 行（计入 `malformed_lines`）、`isSidechain: true` 行（subagent fan-out）、`isMeta: true` 行、`type` 非 `user`/`assistant` 的簿记记录。所有消息行都被跳过的会话计入 `skipped_subagent_sessions`。

## 逐会话解析结构

- `session_id`：首个带 `sessionId` 的记录值，缺省为文件名 stem。
- `start` / `end`：会话内消息时间戳的最小/最大（UTC ISO）。
- `turns`：真实用户消息数 = 有非空文本的 user 记录，排除中断标记。
- `user_messages`：有非空文本的 user 记录（含中断标记）；`assistant_messages`：assistant 记录数。
- `tool_calls`：assistant `message.content` 中 `type=tool_use` 项按 `name` 计数。
- `interruptions`：trim 后恰等于 `[Request interrupted by user]` 的用户文本消息数。
- `errors`：`isApiErrorMessage: true` 或顶层 `error` 字段为真值的 assistant 记录数。
- `first_prompt`：第一条非 meta、非 sidechain、非中断标记的用户文本，截断到 200 字符；中断标记不作为首条提示候选。

## 聚合指标（`session-insights.aggregate.v1`，per-harness 分节，绝不跨 harness 混合）

- `session_count`：窗口与上限裁剪后的会话数。
- `skipped_subagent_sessions` / `files_scanned` / `malformed_lines`：扫描侧计数（裁剪前）。
- `active_days`：入选会话全部消息时间戳覆盖的不同 UTC 日历日数。
- `hour_histogram_utc`：24 桶，按消息时间戳的 UTC 小时。
- `project_distribution`：按项目统计入选会话数。键是脱敏标签，不是 encoded 目录名——encoded 名可逆嵌入用户绝对路径（属用户数据，不进任何产物）：家目录部分坍缩为 `~`（如 `~/Desktop-oh-my-ai-azhou-ai-hub`），其余位置只保留最后两段（如 `.../dev-alpha`）；mangle 不匹配时只少显示、绝不泄漏。标签保持 ASCII。
- `tool_calls`：按调用次数降序、名称升序的工具排行。
- `interruption_rate`：`interruptions / turns`，`turns` 为 0 时取 0.0，保留 4 位小数。
- `error_count`：入选会话错误总数。
- `repeated_first_prompt_count`：trim 后完全相同的首条提示，每组只计首次之外的部分之和。
- `inputs`：`file_count` 与复合 SHA-256——排序后的（`sha256(相对路径)`、`mtime_ns`、`size`）元组；永不含文件内容，永不含明文绝对路径。

Codex 与 zcode 分节恒为 `{"status": "unsupported", "hold": "<harness> unsupported"}`：可检测，不解析，不产出任何猜测数字。store 目录不存在时 Claude Code 分节为 `{"status": "missing"}`。

## 增量缓存（`session-insights.metadata-cache.v1`）

- 只服务 `aggregate` 且仅在未开摘录时启用；`metadata`、`discover`、`--include-excerpts` 运行绕过。
- 位置：`<cwd>/.azhou/session-insights/metadata-cache.json`（gitignored 运行时命名空间；永不写入会话 store 内部）。
- 寻址：`stores[<sha256(harness + 解析后 store 根)>].files[<sha256(相对路径)>]`，条目以 `mtime_ns`+`size` 判活；不匹配即重解析该文件。扫描结束后条目集重写为当次所见文件，删除的会话自然失效。
- 内容边界：只存逐会话元数据与聚合级字段；`first_prompt` 文本与 `project` 标签不入缓存——首条提示以 `first_prompt_sha256` 留存，`repeated_first_prompt_count` 按摘要计数，与全量解析数值一致。project 标签每次扫描现算。
- 可丢弃性：文件缺失、损坏或 schema 不符按空缓存处理；写入为尽力而为的原子发布（临时文件 + `os.replace`），写失败静默。冷/热/删除缓存三种状态下聚合输出逐字节一致（由 benchmark 负控钉死）。

## 报告产物

- `report` 只读 aggregate JSON（文件或 stdin），schema 不符即 exit 1；绝不重算任何指标。
- `--tone report|roast`（默认 `report`）：两种语气从同一份 aggregate 渲染，机器小节逐字节一致；`roast` 只追加一个展示层小节，每条断言必须引用机器小节中出现的一个统计值——无派生数值、无虚构事件、路径与对话。收据机器字段跨语气一致，仅 artifact 摘要随正文变化。
- `--format markdown|html`（默认 `markdown`）：HTML 产物是自包含离线单文件——内联 CSS，无外部资源、无脚本、无链接引用，打印友好；所有事实条目与 Markdown 版逐一对应（由 benchmark 的逐行 parity 负控钉死）；隐私扫描与固定页脚同样覆盖 HTML 产物。
- 默认输出 `<cwd>/.azhou/session-insights/report-<date>.md`；`<date>` 取聚合内最新会话日期（无会话时 `empty`），保证静态 store 下产物名确定。`--out` 为用户自选交付物。
- 小节：概览、时段分布（UTC）、项目分布、工具调用排行、摩擦信号、可选摘录、Holds、Receipt。emoji 只出现在这些人读小节标题。
- **摘录默认关闭**。`aggregate --include-excerpts` 才把脱敏后的首条提示存进 aggregate；`report --include-excerpts` 渲染之。脱敏规则：家目录明文替换为 `~`；密钥样式（`sk-`、`ghp_`、`github_pat_`、`AKIA`、`AIza`、PEM 标记）替换为 `[redacted-secret]`。
- 固定页脚（逐字）：

```text
Review before sharing: this report aggregates local session metadata; when excerpts are enabled it may contain real prompt fragments — verify the redaction before sending it anywhere.
```

## 收据（`session-insights.report.v1`）

字段：`schema`、`status`、`inputs`、`artifacts`、`verification`、`holds`、`next_action`、`learning_signal`。`artifacts` 只含报告文件名（basename）与对 Receipt 小节之前正文的 SHA-256 和字节数。`learning_signal` 由聚合确定性推出：`repeated_first_prompt_count > 0` 时为 `repeated_first_prompts observed`；否则 `interruption_rate >= 0.2` 时为 `elevated interruption rate`；否则 `none`。

退出码：0 成功；1 gate/校验失败（aggregate schema 不符、`--project` 未命中、摘录开关不配等）；2 用法错误（argparse）。
