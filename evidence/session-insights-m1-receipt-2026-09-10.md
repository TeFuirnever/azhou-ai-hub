# session-insights M1 实测收据（真实 Claude Code 存储，macOS）

> 日期：2026-09-10（Asia/Shanghai）· 环境：本机 macOS，Python 3（标准库）· 对象：本机真实 `~/.claude/projects` 会话存储（只读）· 载体：session-insights M1 落地（issue #163）
> 隐私口径：本收据只记录聚合计数、schema 校验与脱敏扫描结果；不记录任何会话内容、提示词、明文路径或项目名。

## 执行与结果

| 步骤 | 命令（`skills/session-insights/scripts/session_insights.py`） | 结果 |
|---|---|---|
| detect | `detect` | claude-code `available`（239 个会话文件）；codex / zcode `unsupported` + store_present=true + hold 入账 |
| aggregate | `aggregate` | schema `session-insights.aggregate.v1` 校验通过；200 会话（触发 200 上限，最近优先）、13 个活跃 UTC 日、错误计数 10；窗口锚定 store 内最新会话时间戳 |
| report | `report --aggregate … --out …` | Markdown 产物落盘；收据 `session-insights.report.v1` 含 file_count=239 与复合 SHA-256；holds 原样列出 codex/zcode unsupported |
| 隐私负控 | 对 report 与 aggregate 全文 grep | 绝对家目录 0 命中；`sk-`/`ghp_`/`AKIA`/`AIza` 密钥样式 0 命中；用户名 0 命中 |

## 过程中发现并修复的边界缺口（留档）

首版实现把 Claude Code 的 encoded 项目目录名原样写进 `project_distribution`。该编码可逆嵌入用户绝对路径（含用户名），违反硬边界三「用户路径不进产物」，且形状绕过对 `$HOME` 明文的朴素扫描。修复：聚合器在写入任何产物前把 encoded 名脱敏为标签——家目录部分坍缩为 `~/`，其余位置只保留最后两段（`.../<tail>`）；规则钉入 `references/report-contract.md`，benchmark 隐私负控新增「产物不含 encoded 项目目录名」断言（aggregate 与两种摘录模式的 report 三个面）。修复后真实 store 复跑：项目分布只出现 `~/…` 与 `.../…` 标签，用户名扫描 0 命中。

## 接线完整性

`benchmarks/session-insights/`（合成 fixture 在 check 时生成于临时目录，密钥样式串运行时拼接、不入库）覆盖：golden 聚合逐项钉住指标口径、窗口/上限裁剪、收据复合摘要稳定性与内容敏感性、隐私负控、codex/zcode fail-closed 负控；已注册进 `scripts/verify.py` 与 CI benchmark job。行为 benchmark 暂无（与 eli5、ci-test-reliability 同级声明）。

## 结论

M1 验收的 CLI、适配器、聚合唯一事实源、收据、隐私负控、fail-closed 与目录原子落地均已实证。剩余边界：Codex/zcode 适配器在格式验证前维持 fail closed；roast tone 属 M2，本版不出 roast 报告。
