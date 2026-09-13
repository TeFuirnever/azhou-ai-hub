# session-insights M3 Codex 适配器实测收据（真实 Codex rollout 存储，macOS）

> 日期：2026-09-13（Asia/Shanghai）· 环境：本机 macOS，Python 3（标准库）· 对象：本机真实 `~/.codex/sessions` rollout 存储（只读）· 载体：session-insights M3 Codex 适配器落地（issue #166，PR #211）
> 隐私口径：本收据只记录聚合计数与脱敏观察；不记录任何会话内容、提示词、明文路径或项目名（下文项目标签均为报告产物中的脱敏形态）。

## 执行与结果

| 步骤 | 命令（`skills/session-insights/scripts/session_insights.py`） | 结果 |
|---|---|---|
| 格式普查 | 只读脚本遍历 `~/.codex/sessions/**/rollout-*.jsonl` | 461 个 rollout；记录类型与 `session_meta.payload.thread_source`（user/subagent/guardian_review/缺失）分布定下适配器规则 |
| aggregate | `aggregate --harness codex --days 30` | schema `session-insights.aggregate.v1` 校验通过；`status=ok`；30 天窗口内 75 个会话、15 个活跃 UTC 日、219 轮对话、42 次中断（`turn_aborted{reason: interrupted}`）、`error_count=0`（Codex 无已核实错误标记，按合同恒 0）；`files_scanned=461`、`skipped_subagent_sessions=217`（subagent/guardian/缺失 thread_source 的 rollout 全部 fail-closed 排除） |
| 工具排行 | 同上 | 前五为协作类与 MCP 工具名，命名空间工具以 `namespace.name` 形态入榜（脱敏后可核） |
| 项目分布 | 同上 | 全部为脱敏标签（`~/…` 与 `.../…` 形态），无 encoded 目录名、无明文家目录、无用户名 |
| 隐私负控 | 对 aggregate 全文检查 | 明文家目录 0 命中；encoded 项目目录名 0 命中；`thread_source`/明文 `cwd` 不出现在产物 |

## 结论

Codex 适配器在真实存储上行为与合成 fixture golden 一致：只读、同管线、按 harness 分账、subagent 与注入文本排除、脱敏标签入产物。该实测支撑 `docs/support-matrix.md` 中 Codex 行的"read-only manual sanity run over the maintainer's real store (461 rollouts scanned, 217 subagent rollouts filtered) on macOS"表述。
