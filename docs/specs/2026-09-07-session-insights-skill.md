# Spec: `session-insights` 技能规划（Agent 会话使用洞察报告）

> Spec 日期：2026-09-07（Asia/Shanghai）
> 来源证据：[docs/research/2026-09-07-agent-insights-industry-survey.md](../research/2026-09-07-agent-insights-industry-survey.md)（业界机制对照：Claude Code `/insights`、awesome-skills/insights、Computer History roast 插件）、2026-09-07 本机会话存储结构实测（研究笔记 §2，只验证路径与字段形态，未读取内容）。
> 状态：ready-for-agent。本 spec 只定义工作，不执行修改。
> 发布：2026-09-07 已按 to-spec 流程发布为 [issue #161](https://github.com/TeFuirnever/azhou-ai-hub/issues/161)（英文，spec-of-record，标签 `ready-for-agent`）；本文件保留中文扩展细节与落地约束，实现以 issue 为准，两处冲突时先对齐再动工。

## Problem Statement

用户与编码 agent 的会话在本地积累了几百份转写，但没有人能回答"我到底在怎么用 agent"：宿主计数器（`/status`、statusline）只给当次 token，官方 `/insights` 只覆盖 Claude Code 一家，社区实现要么隐私口径含糊（报告内嵌真实提示词，仅靠一句"分享前自行审查"），要么没有包纪律（一次性脚本、无收据、无回归）。本仓目录有 15 个 canonical skill，没有一个承担这个任务。同时这个品类的传播力已被验证： Computer History 插件的 "roast my computer behavior" 模式证明，绑定真实数字的幽默复盘是用户主动想要的东西。

## Solution

新增第 16 个 canonical skill `session-insights`：用户显式调用，读取本机 harness 会话历史（Claude Code、Codex、zcode），由标准库脚本确定性聚合，产出事实绑定的使用洞察报告；`roast` 只是展示层 tone，不改变数字。四条硬边界：

1. **只读观察者**：脚本只读宿主会话目录，永不写入、永不外联；读私有会话日志的授权就是本次显式调用本身，写入 `SKILL.md` 共享规则。
2. **机器先于叙事**：`aggregates.json` 是唯一事实源；报告中的每个数字来自它，LLM 只做综合叙述与 tone。
3. **原始记录不出机器**：聚合与脱敏摘录进产物，原始转写与用户路径不进 Git、不进上下文全文；产物默认落在 `.gitignore` 已覆盖的 `.azhou/session-insights/`。
4. **同源比较**：跨 harness 的 token 口径不同，报告只做同源比较，不做假等价。

按三个里程碑推进：M1（核心管线 + Claude Code 适配器 + 目录化落地）→ M2（roast tone + 单文件 HTML）→ M3（Codex/zcode 适配器 + 缓存）。不 vendor 任何上游字节，只借鉴机制；三个上游实现以不可变 pin 记入 `references/provenance.md` 作为 prior art 参考。

## User Stories

1. 作为 skill 用户，我想说"用 session-insights 给我的 agent 使用出一份周报（或 roast 我一下）"，就得到一份基于本机真实会话的报告，而不需要手动导出任何东西。
2. 作为用户，我想在报告里看到会话数、活跃天、时段分布、项目分布、工具调用排行，以便知道自己的真实使用形态。
3. 作为用户，我想看到摩擦信号（错误重试环、中断率、重复同命令），以便改进我和 agent 的协作方式。
4. 作为用户，我想每条 roast/点评都能对应报告里的一个机器统计，以便幽默不等于编造。
5. 作为用户，我想默认产物不含原始对话全文，以便报告放在磁盘上不构成新的隐私面。
6. 作为用户，我想显式开启 `--include-excerpts` 时摘录自动脱敏（家目录替换、密钥样式过滤），且报告脚注提醒分享前人工审查。
7. 作为跨 harness 用户，我想一份 skill 同时覆盖 Claude Code、Codex 与 zcode 的会话存储，以便不必为每家装一个工具。
8. 作为 zcode 用户，当 zcode 会话格式无法确认时，我想适配器诚实报告"不支持"而不是给出错误洞察。
9. 作为连续使用者，我想第二次运行很快（增量缓存），以便周报成为习惯而不是负担。
10. 作为用户，我想报告产物默认写进 `.azhou/session-insights/`（不进 Git），也可以 `--out` 指到我自己选的位置。
11. 作为维护者，我想聚合器在合成 fixture 上有 golden 基线与完整性套件，以便聚合口径的回归被门禁拦截。
12. 作为维护者，我想收据记录输入文件的计数与复合摘要（不含内容），以便报告可复验而不泄露原始会话。
13. 作为审计者，我想公开仓库里只有合成 case、聚合口径与脱敏收据，以便独立复核时接触不到任何真实会话。
14. 作为目录读者，我想 ask-azhou 与 README（中英）把这个 skill 的边界讲清楚，以便知道它"分析什么、不监控什么"。

## Implementation Decisions

- **命名与定位**：canonical name `session-insights`（与 `repo-pedant`、`ci-test-reliability` 同风格，描述任务而非比喻）；品牌锚点 `🦊 阿舟 · Session Insights`，口号候选「先有数字，再有故事。」；frontmatter `invocation: user-invoked orchestrator`（花用户认知负载的显式命令，不追求普通工作中被自主到达）。skill 间组合为零：不链入任何 orchestrator，也不被链入。
- **包结构**：`skills/session-insights/` 下 `SKILL.md`（入口、触发、只读边界）、`references/brand-layer.md`（collect → aggregate → report 三阶段事件协议与收据）、`references/provenance.md`（三个上游 prior art 的不可变 pin 与"零字节 vendor"声明）、`references/report-contract.md`（报告分节、指标口径、脱敏规则）、`scripts/session_insights.py`（单入口 CLI：`detect / discover / metadata / aggregate / report` 子命令）。纯 Python 3.11+ 标准库，无外部依赖，不需要 `references/setup.md`。
- **适配器契约**：每家 harness 实现同一对函数 `list_sessions() -> [SessionRef]` 与 `parse_metadata(ref) -> ParsedSession`，统一结构含：会话 id、起止时间、轮次/消息计数、按名工具调用计数、中断/错误计数、首条用户提示（≤200 字符，供摘录位）。Claude Code 读 `~/.claude/projects/<encoded-cwd>/*.jsonl`；Codex 读 `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` 并过滤 subagent rollout；zcode 适配器以 `~/.zcode/v2/sessions` 的格式验证任务为前置，未验证前 fail closed。全库遵循跨平台纪律（`pathlib`、显式 `encoding="utf-8"`、无 POSIX-only 命令），与 2026-09-07 Windows/macOS spec 的护栏一致。
- **扫描策略**：默认 `--days 30`、`--max-sessions 200`（最近优先，对齐业界上限）；跳过 subagent 会话与注入文本；`--project <path>` 可缩到单项目。解析为流式逐行，不整读大文件。
- **缓存**：`.azhou/session-insights/cache/metadata.json`，键为会话文件 mtime+大小摘要，值只含元数据与聚合所需字段，永不存转写正文；缓存可整目录删除重建（ disposable，不算用户交付物）。M3 落地。
- **报告产物**：v1 主产物为 Markdown 报告（人读 + agent 可复核），M2 增加离线单文件 HTML（内联样式、无外部资源、无 JS）。默认输出 `<当前项目>/.azhou/session-insights/report-<日期>.md`；`--out` 显式路径视为用户自选交付物。摘录默认关闭；开启时家目录路径替换为 `~`、密钥样式（`sk-`、`ghp_` 等）打码，报告脚注固定提醒"分享前人工审查"。
- **tone 双模**：`report`（中性）与 `roast`（幽默）共享同一份 `aggregates.json`，只影响措辞层；SKILL.md 明确 roast 的红线——每条断言必须引用报告内出现的统计，禁止虚构事件、路径与对话。v1 不做"fun ending"位（需要更宽的摘录授权），列为后续评估。
- **收据**：`session-insights.report.v1`，字段含 schema、status、inputs（文件计数 + 排序后的（路径摘要、mtime、大小）复合 SHA-256，不含内容与明文路径）、artifacts 摘要、verification、holds（如 zcode 适配器 unsupported）、next action、learning signal。机器字段纯 ASCII，emoji 只在展示层。
- **目录落地（一次原子提交族）**：新增 skill 必须同步进入 `scripts/check_repository.py` 的 discovery 与品牌合同、`skills/ask-azhou/references/` 路由图（gate 强制全目录覆盖）、README.md 与 README.zh-CN.md 的安装清单与 Skills 表、`docs/support-matrix.md`（只声明已验证的 harness 维度，zcode 未验证前不进表）。`CHANGELOG.md` 在 super-caveman 晋级记录的 exact-diff 覆盖清单内，落库批次必须与维护者批准的 promotion 流程同行或换取新收据，不允许单独先改。
- **不 vendor 字节**：awesome-skills/insights（MIT）、Claude Code `/insights`、Computer History 均只作机制参考；MIT 来源的 pin 与许可证记入 provenance，未复制任何上游代码，故不进 `THIRD_PARTY_NOTICES.md`。

## Testing Decisions

- **好测试的标准**：只测外部行为——CLI 退出码、JSON 结构、golden 聚合值、产物文本终态；沿用仓库既有写法。
- **fixture 与完整性套件**：`benchmarks/session-insights/` 内含合成 Claude Code/Codex 会话 fixture（手写 JSONL，含中断、错误重试、subagent 会话等干扰项）、golden `aggregates.json`、suite 脚本，注册进 `scripts/verify.py` 的 benchmark-integrity 门禁。
- **确定性覆盖点**：时间窗与会话上限裁剪；mtime 缓存命中/失效；跨 harness 聚合不混合（各自独立口径）；收据复合摘要对同输入稳定、对内容变化敏感。
- **隐私负控**：产物扫描断言不含绝对家目录路径与 fixture 中埋入的密钥样式串；摘录默认关闭时报告中无任何转写原文。
- **fail-closed 负控**：zcode 适配器在格式未知时返回 `unsupported` 并进 holds，不产出猜测性报告。
- **品牌合同**：check_repository 品牌套件覆盖启动行、阶段事件与收据格式；ask-azhou 路由 parity 负控防"加了 skill 忘了路由"。
- **行为评测**：v1 只做接线完整性（与 eli5、ci-test-reliability 同级声明"No behavior benchmark yet"）；roast 事实绑定的语义判断留给后续 paired-judge case，不伪装成机器可证。

## Out of Scope

- Computer History 式的桌面/应用事件记录、屏幕截图或键盘采集——本 skill 只读既有 agent 会话存储。
- 官方 `/insights` 式的经 API 的 facet 抽取与云端分析——一切聚合在本地脚本完成。
- 跨 harness 的 token 成本等价换算。
- 定时自动报告、hook 触发、后台 observer——只有显式调用；历史观察者不得改写 live skill 的标准条款继续适用。
- 跨会话学习/演化（`references/history-evolution.md`）——等 roast judge case 积累后再议。
- `--days` 之外的复杂查询语言、多人/多账户会话隔离。

## Further Notes

- 落库顺序建议：M1 完成时一次性原子落地（包 + 门禁 + 路由 + 双语 README + support-matrix），避免出现"目录里有 skill 但 gate 不知道"的中间态。
- CHANGELOG 与既有 promotion 覆盖路径的耦合见 Implementation Decisions；这是本 spec 与 windows/macOS spec 共享的落库约束。
- 命名留有一处备选：若实现期发现 `session-insights` 与宿主生态已有强占用（如用户已装的同名社区 skill 冲突），备选名 `agent-insights`，切换只发生在 M1 落地前。
- zcode 会话格式验证是独立的前置侦察任务（只读结构、不取内容），可先于 M3 执行。
- 本 spec 自身不执行任何修改；实施时按 skill-standard §6 收尾并跑 `python3 scripts/verify.py`。
