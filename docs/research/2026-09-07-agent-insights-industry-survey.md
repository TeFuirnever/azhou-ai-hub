# Research: Agent 使用洞察（insights / roast）业界对照

> 日期：2026-09-07（Asia/Shanghai）
> 性质：研究笔记，表达目标与外部对照，不表达本仓库已实现能力。
> 用途：为"会话使用洞察"类 skill 的规划提供业界机制对照（spec：`docs/specs/2026-09-07-session-insights-skill.md`）。

## 1. 研究对象

| 对象 | 形态 | 一句话定位 |
|---|---|---|
| ChatGPT "Computer History" 插件（Tibo @thsottiaux 传播） | ChatGPT 桌面连接器 | 全天被动记录电脑使用事件，用户主动要求 "roast my computer behavior"，得到一条幽默但有数据的复盘 |
| Claude Code 官方 `/insights` | Claude Code 内置命令 | 扫描本地会话历史，生成 30 天量级的 HTML 用量洞察报告 |
| awesome-skills/insights（MIT） | 可移植社区 skill | 同一个 `/insights` 跨 Claude Code、Codex、Gemini CLI、OpenCode，产出离线单文件 HTML 报告 |
| atani/codex-insights | 第三方 CLI | Codex CLI 会话分析器，生成带 AI 建议的 HTML 用量报告 |

来源链接见 §5。tweet 属二手观察，未复现其连接器实现。

## 2. 机制对照

| 维度 | Computer History | Claude Code /insights | awesome-skills/insights |
|---|---|---|---|
| 数据源 | 桌面连接器记录的应用/输入事件 | `~/.claude/projects/**.jsonl` | 四家 harness 的本地会话存储 |
| 扫描策略 | 全天持续记录 | 先轻量元数据扫描，上限 200 个会话，超限取最近 | 五段管线：discover → metadata → transcript/facet → aggregate → render |
| 缓存 | 无（持续记录） | `~/.claude/usage-data/`，按会话增量复解析 | 按 mtime 缓存元数据 |
| 叙事生成 | 模型直接点评 | Claude Opus 做 facet 抽取 + 分节并行生成（每节 8192 token 上限） | 本地脚本抽取 + 当前对话中的 LLM 综合，JSON 作为交换格式 |
| 产物 | 聊天回复 | `~/.claude/data/report.html` | 离线单文件 HTML（内联 CSS、无 JS、无 CDN） |
| 隐私边界 | 本机记录、分享靠用户自行判断 | 声明"只读本地"，但 facet 与分节生成经 API 调用模型 | 全程本地；报告内嵌真实提示词/路径，README 明确提醒分享前人工审查 |
| 特色指标 | 事件占比（如 "48% 是 Slack"）、事件总数与时间跨度 | 交互风格、有效工作流、摩擦分析、CLAUDE.md 建议、multi_clauding（时间戳重叠判定并行会话） | 项目聚类、工具/语言/目标条形图、可复制建议；明确拒绝跨 harness 的 token 对比 |

本地实测（2026-09-07，本机，只看存储结构不看内容）：

- Claude Code：`~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl`，31 个项目目录；首行记录顶层键含 `type`、`sessionId`。
- Codex：`~/.codex/sessions/YYYY/MM/DD/rollout-<时间戳>-<uuid>.jsonl`。
- zcode：存在 `~/.zcode/v2/sessions` 目录；内部格式未验证，适配前需先做格式确认（fail closed）。

## 3. 可提炼的业界最佳实践

1. **元数据先行 + 增量缓存**：两次运行之间的差异只有新增/修改的会话文件；按 mtime/大小缓存元数据，把全量解析降到一次。官方实现 200 会话上限 + 最近优先，控制成本。
2. **公共会话契约 + 薄适配器**：每家 harness 只需实现 `list_sessions` / `parse_session` 两个函数，返回统一 `ParsedSession`；单个适配器 150–250 行即可覆盖三种存储形态（流式 JSONL、单 JSON、SQLite）。
3. **机器聚合与叙事分离**：数字由确定性脚本算出，LLM 只做综合叙述；这是"洞察可信"的地基。
4. **喂给模型的内容必须有界**：转写只取头尾（约前 30% + 后 70%）、过滤 subagent 会话与注入文本、还原真实用户输入；避免把整段历史塞进上下文。
5. **叙事必须绑定事实**：roast 的传播力来自"具体数字 + 幽默人设"（8,592 个事件、48% 是 Slack），而非编造；每条点评能落到一个机器派生统计上才成立。
6. **跨 harness 指标不做假等价**：各家 token 口径不同，跨家比较是谎言；报告内只做同源比较。
7. **离线单文件产物**：HTML 内联样式、不引用外部资源，既可分享也不外泄访问记录。
8. **分享前人工审查是硬前提**：报告天然内嵌真实路径、提示词片段；产物层面要做默认脱敏，分享警告不能省。
9. **fail closed**：未知会话格式、未知存储位置时报告"不支持"，而不是猜。

## 4. 对本仓的落点

- 机制 1–4、9 对应 skill-standard §2（标准库脚本、确定性）与 §4（聚合统计入仓、原始对话不出 Git）；azhou 版应比上游更进一步：默认产物只含聚合与脱敏摘录，摘录需显式开启。
- 机制 5 对应 §3 品牌层：roast/report 只是展示层的两种 tone，机器数字同源。
- 机制 6、7、8 进入报告合同与收据。
- 本机实测确认了 Claude Code 与 Codex 两家适配器的路径形态；zcode 适配器需先完成格式验证任务。

## 5. 来源

- Tibo (@thsottiaux) 关于 Computer History 的推文（用户提供截图，2026-09-07 在线热帖）
- Claude Code /insights 机制解析：[Vincent Qiao 的博客](https://blog.vincentqiao.com/en/posts/claude-code-insights/)
- 可移植实现：[awesome-skills/insights](https://github.com/awesome-skills/insights)（MIT）
- Codex 会话分析器：[atani/codex-insights](https://github.com/atani/codex-insights)
- Claude Code 会话 JSONL 格式解析：[Inside Claude Code: The Session File Format](https://databunny.medium.com/inside-claude-code-the-session-file-format-and-how-to-inspect-it-b9998e66d56b)
- 生态索引（其余同类）：[MCP Market: Session History Insight](https://mcpmarket.com/tools/skills/session-history-insight)、[skills.rest: cc-history](https://skills.rest/skill/cc-history)、[getclaudeskills.com: Session Report](https://www.getclaudeskills.com/skills/session-report-anthropics)

## 6. 局限

- 未获取 Claude Code 官方 `/insights` 的实现源码，机制描述来自第三方博客转述。
- awesome-skills/insights 的管线细节来自其 README 与检索摘要，未逐行读源码。
- Computer History 插件为闭源产品，机制是二手观察。
- zcode 会话存储内部格式在本机存在但未验证，规划中列为前置验证任务而非既成事实。
