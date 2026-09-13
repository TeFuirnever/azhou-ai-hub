---
name: session-insights
description: Analyze local agent session stores into fact-bound usage insight reports — session counts, active days, hour/project distribution, tool ranking, friction signals. Use when the user asks how they actually use their coding agent, wants a weekly report, or asks to be roasted on real numbers; read-only, aggregates only, raw transcripts never leave the machine.
invocation: user-invoked orchestrator
---

# Session Insights

**🦊 阿舟 · Session Insights**

> 📊 先有数字，再有故事。

Invocation class: user-invoked orchestrator, declared in frontmatter; the axis, its semantics and the composition rules are defined once in docs/skill-standard.md §2.2 (spec #126 ID-9) — invoked by name or by an explicit "我的 agent 使用报告" request; it never chains into another orchestrator and nothing chains into it.

它读取本机 harness 会话存储，由标准库脚本确定性聚合，产出事实绑定的使用洞察报告。品牌层协议见 [brand-layer](references/brand-layer.md)，报告口径见 [report-contract](references/report-contract.md)，prior art 与零 vendor 声明见 [provenance](references/provenance.md)。

## 四条硬边界

1. **只读观察者**：脚本只读宿主会话目录，永不写入、永不外联；读取私有会话日志的授权就是本次显式调用本身。
2. **机器先于叙事**：aggregate JSON 是唯一事实源；报告中的每个数字来自它，LLM 只做综合叙述与 tone，不重算任何指标。
3. **原始记录不出机器**：聚合与脱敏摘录进产物；原始转写与用户路径不进 Git、不进上下文全文。产物默认落在 `.azhou/session-insights/`（仓库 `.gitignore` 已覆盖）。
4. **同源比较**：跨 harness 的 token 口径不同，报告只做同源比较，不做假等价。

## 触发与用法

显式调用："用 session-insights 给我出一份 agent 使用报告（或周报）"。CLI 单入口五个子命令（脚本在已安装包目录下）：

```bash
python <skill-dir>/scripts/session_insights.py detect
python <skill-dir>/scripts/session_insights.py discover --harness claude-code
python <skill-dir>/scripts/session_insights.py metadata --harness claude-code
python <skill-dir>/scripts/session_insights.py aggregate --out .azhou/session-insights/aggregates.json
python <skill-dir>/scripts/session_insights.py report --aggregate .azhou/session-insights/aggregates.json
```

- `detect`：报告各家 harness 存储是否在场；Codex 与 zcode 可检测但一律 `unsupported`。
- `discover`：列出会话清单（id、项目、起止），不含指标。
- `metadata`：流式逐行解析，输出逐会话元数据 JSON；跳过 malformed 行、`isSidechain`/`isMeta` 行与非消息簿记类型；全为 sidechain/meta 的会话计为 skipped-subagent。
- `aggregate`：产出 `session-insights.aggregate.v1`，唯一事实源；默认 `--days 30`、`--max-sessions 200`（最近优先），`--project <path>` 缩到单项目。窗口与上限锚定 store 内最新会话时间戳，不是墙钟——静态 store 结果必然确定。
- `report`：只从 aggregate JSON 渲染 Markdown，绝不重算数字；`--tone roast` 切换 roast 语气，机器小节逐字节不变。

唯一新增的 seam 是每个子命令的 `--store-root <path>`，用于把宿主存储重定向到测试 fixture；没有其他隐藏开关。

## 增量缓存

`aggregate`（未开摘录时）把逐文件解析元数据缓存到 `<当前项目>/.azhou/session-insights/metadata-cache.json`：条目按（harness、store 根摘要、文件相对路径摘要）寻址，以 mtime+大小判活；只存元数据与聚合级字段——首条提示文本永不入缓存，只留其 SHA-256（重复首条提示检测据此进行，数值与全量解析一致）。改动、新增、删除的会话文件下一轮自动重扫；缓存完全可丢弃，删除后重建且聚合输出逐字节不变。损坏的缓存按空缓存处理并就地重建。`metadata`、`discover` 与 `--include-excerpts` 运行绕过缓存（它们需要真实文本）。缓存永不写入会话 store 内部——只读观察者边界不变。

## 输出与产物

- 默认产物 `<当前项目>/.azhou/session-insights/report-<日期>.md`（自动建目录）；`--out` 指向用户自选的交付物位置。
- 摘录默认关闭；`--include-excerpts` 时摘录先脱敏（家目录替换为 `~`、`sk-`/`ghp_`/`github_pat_`/`AKIA`/`AIza`/PEM 等密钥样式打码），报告页脚固定提醒分享前人工审查。
- Codex 与 zcode 适配器 fail closed：任何 aggregate/report 尝试只记录 `unsupported` hold，绝不产出猜测数字。

## roast 红线

roast 是展示层 tone（`report --tone roast`，已发布）：`report` 与 `roast` 从同一份 aggregate JSON 渲染，机器小节逐字节一致，roast 只是追加的展示层小节。红线：每条 roast 断言必须引用机器小节中出现的一个统计值；禁止派生数值、虚构事件、路径与对话。收据合同与机器字段跨语气一致（仅 artifact 摘要随正文变化）。

## Brand protocol

每次运行开始时原样播报一次：

```text
🦊 阿舟 · Session Insights 启动｜mode=<report>｜scope=<harness-or-project>
```

`✅ 验证通过` 只在报告产物落盘并读回核对之后使用；`❌ 验证失败` 用于聚合 schema 校验失败或产物写读失败；`🔒 阿舟暂停这一项` 用于请求越界（如要求监控、外传或 roast 尚未发布的功能）。Emoji 只出现在展示层；JSON key、schema 值、digest、路径、命令、测试名与原始证据保持无 Emoji。原始证据（原始转写、未脱敏摘录、用户路径明文）永远不进入报告、收据或 Git。host 不支持 Unicode 时可去掉前导 emoji，固定文本、`｜` 分隔符、字段与值不得改变。

## Verification

运行收据为 `session-insights.report.v1`：schema、status、inputs（文件计数 + 排序后（相对路径摘要、mtime、大小）的复合 SHA-256，不含内容与明文绝对路径）、artifact 摘要、verification、holds、next action、learning signal。机器字段纯 ASCII，emoji 只在人读小节标题。报告口径的完整定义以 [report-contract](references/report-contract.md) 为准；接线完整性套件在仓库级 `benchmarks/session-insights/`，尚无行为 benchmark。
