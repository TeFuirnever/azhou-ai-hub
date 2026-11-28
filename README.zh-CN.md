# 🦊 Azhou AI Hub · 阿舟 AI 能力站

给 Agent 装上需要的技能，让它帮你画图、讲清复杂问题或审查代码。阿舟来源库收录 AI 官方文章和更新。

[English](README.md) · [找技能](https://tefuirnever.github.io/azhou-ai-hub/zh/skills/) · [安装 Ask Azhou](#安装-ask-azhou) · [打开来源库](https://tefuirnever.github.io/azhou-ai-hub/zh/library/)

## 安装 Ask Azhou

不确定该用哪个技能时，先装 Ask Azhou。它会根据任务推荐技能，你可以再安装需要的那一个。

### 让 Agent 安装

在当前项目打开 Agent 会话，粘贴这段安装提示词。Agent 会先检查能否找到 Ask Azhou，再决定是否要安装。

> 请按 https://github.com/TeFuirnever/azhou-ai-hub/blob/main/docs/installation.md#install-with-an-agent 在当前项目只安装 super-ask-azhou，并确认当前 Agent 宿主能找到它。

<details>
<summary>手动安装</summary>

[按 Agent 工具选择安装方式（英文）](docs/installation.md#choose-your-agent-host)。要用 Skills CLI 安装其他技能，见[包管理器安装指南（英文）](docs/installation.md#package-manager-install)。

### 在 Codex 里首次安装

登录 Codex，在项目目录用 Node.js 22.20 或更新版本运行下面的命令，按提示确认安装到当前项目。

~~~bash
npx skills add https://tefuirnever.github.io/azhou-ai-hub/downloads/super-ask-azhou.tgz --agent codex
~~~

[已在项目里装过 Ask Azhou？切换到官网直链（英文）](docs/installation.md#switch-ask-azhou-to-the-website-download)

</details>

<a name="在-codex-里试一次"></a>

### 试用 Ask Azhou

在同一项目打开新会话，让 Agent 用 `super-ask-azhou` 回答下面的问题。在 Codex 里可以直接粘贴整段示例。Ask Azhou 应推荐 `super-archify`。

> `$super-ask-azhou` 我有一段 Mermaid，想把它做成可以交互查看的架构图。该用哪个 Hub 技能？

[安装 Archify](https://tefuirnever.github.io/azhou-ai-hub/zh/skills/#super-archify) · [排查已安装的技能（英文）](docs/installation.md#check-that-your-host-finds-the-skill) · [更新或卸载（英文）](docs/installation.md#upgrade-or-uninstall)

## Skills

[按任务搜索技能](https://tefuirnever.github.io/azhou-ai-hub/zh/skills/)。已知道要做什么时，可以直接打开对应的[例子](#上手试试)。

<details>
<summary>全部 21 个可安装包</summary>

| 技能 | 能帮你做什么 |
|---|---|
| [Azhou Info](skills/super-azhou-info/SKILL.md) | 查看 Hub 本地仓库的版本、运行环境和支持情况。 |
| [Azhou Doctor](skills/super-azhou-doctor/SKILL.md) | 只读排查 Hub 仓库或本地安装的问题。 |
| [Azhou Setup](skills/super-azhou-setup/SKILL.md) | 用本地 Hub 仓库预览并安装、更新或卸载技能。 |
| [Azhou Verify](skills/super-azhou-verify/SKILL.md) | 运行完整的仓库检查。 |
| [Super Repo Pedant](skills/super-repo-pedant/SKILL.md) | 交接前检查文档、规则和实现是否一致。 |
| [Excalidraw Diagram](skills/super-excalidraw-diagram/SKILL.md) | 画一张可继续编辑的 Excalidraw 图，并导出 SVG 或 PNG。 |
| [Eli5](skills/super-eli5/SKILL.md) | 用一份可独立打开的 HTML 图解讲清复杂概念。 |
| [Ask Azhou](skills/super-ask-azhou/SKILL.md) | 描述你要做的事，找到适合的技能。 |
| [Arch Doc](skills/super-arch-doc/SKILL.md) | 从上游资料起草或审查架构文档。 |
| [Session Insights](skills/super-session-insights/SKILL.md) | 从已授权的本地 Agent 会话整理使用情况和工作规律。 |
| [ASD-STE100](skills/super-asd-ste100/SKILL.md) | 用 ASD-STE100 规则改写给 Agent 看的英文指令。 |
| [Archify](skills/super-archify/SKILL.md) | 把系统、方案或代码库变成可交互的 HTML 架构图。 |
| [Lavish](skills/super-lavish/SKILL.md) | 把 Agent 的输出做成可审阅的 HTML，再把批注发回 Agent。 |
| [Imagegen](skills/super-imagegen/SKILL.md) | 用本机已有的私有 azhou-imagegen 技能执行生图请求。 |
| [Rederive](skills/super-rederive/SKILL.md) | 通过重新推导设计，理解一个代码库。 |
| [i-have-adhd](skills/super-i-have-adhd/SKILL.md) | 把下一步放在最前面，每次给 ADHD 读者一小组行动。 |
| [Gh Axi](skills/super-gh-axi/SKILL.md) | 通过面向 Agent 的 CLI 操作 GitHub。 |
| [Diagram Design](skills/super-diagram-design/SKILL.md) | 设计 HTML 或 SVG 图表，也可导入 draw.io、Mermaid、Excalidraw 和 PlantUML。 |
| [Frontend Design](skills/super-frontend-design/SKILL.md) | 为新界面或改版选设计方向，评审配色、排版和布局。 |
| [Brainstorming](skills/super-brainstorming/SKILL.md) | 动手前澄清需求、比较方案并确认设计。 |
| [Grill Me](skills/super-grill-me/SKILL.md) | 逐个追问方案里的关键决定，发现没想清楚的地方。 |

</details>

### 上手试试

- [画一张登录时序图](docs/demos/super-excalidraw-diagram.md)，交付可编辑源文件和 PNG。
- [从上游资料起草架构文档](docs/demos/super-arch-doc.md)，确认结论有依据。
- [检查代码交接前的遗漏](docs/demos/super-repo-pedant.md)，找出还没解决的事项。

## Agent Rules Books

用工程书里的方法设计、重构和审查代码。[查看 14 套规则](docs/agent-rules-books.zh-CN.md) · [安装指定规则](docs/installation.md#install-agent-rules-books)

<details>
<summary>在 Codex 里手动安装一套规则</summary>

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill refactoring --agent codex
~~~

</details>

## 集成

- [阿舟 Agent 工作台](packages/azhou-agent-inspector/README.md)在 Codex 和 ZCode 显示对话耗时和速度。
- [pstack](packages/pstack-agent-harness/README.md)提供实现和审查工作流。当前状态见[支持矩阵](docs/support-matrix.md#optional-integrations)。
- [阿舟鼠标指针](assets/cursors/azhou-double-hug/README.md)是独立的 macOS Mousecape 主题。

<details>
<summary>集成支持详情</summary>

| 项目 | 包 | 当前支持范围 |
|---|---|---|
| `azhou-agent-inspector` | [阿舟 Agent 工作台](packages/azhou-agent-inspector/README.md) | Codex 会话侧面板、ZCode 输入框状态项与会话仪表盘。两个面板都显示整轮耗时和速率，可按需展开性能详情。宿主提供实际请求的用量和窗口上限时，详情会显示 Context 占用。工作台 0.12.13 遵循系统的「减少动态效果」偏好。通过各宿主自己的插件管理器安装。[各版本验收记录与待验项](docs/support-matrix.md#azhou-agent-workbench)。 |
| `pstack` | [pstack-agent-harness](packages/pstack-agent-harness/README.md) | `pstack-azhouzhou` 0.15.43 **候选版**：Codex／Claude 原生插件、自带捆绑 skills 的 zcode 插件，以及 MiMo 与 DeepSeek Harness 的共享 Skills 发现能力（维护者主机上的共享根 pstack 链接已于 2026-11-14 退役；以该方式向两者提供 pstack 移入单独任务处理，共享根中的其他 skill 不受影响）。带日期的证据与限制：[支持矩阵](docs/support-matrix.md#optional-integrations)。 |

</details>

<a name="退役面"></a>

## 项目入口

- [安装与维护（英文）](docs/installation.md) · [获取帮助或报告故障](https://tefuirnever.github.io/azhou-ai-hub/zh/support/#get-help) · [查看 Agent 支持哪些技能（英文）](docs/skill-platform-view.md)
- [文档目录（英文）](docs/README.md) · [技能规范](docs/skill-standard.md) · [参与贡献](CONTRIBUTING.md) · [更新记录](CHANGELOG.md)
- [技能验证依据（英文）](docs/skill-evidence.md) · [安全问题](SECURITY.md) · [已退役工具](docs/architecture.md#retired-surfaces)

<details>
<summary>开发者命令（Foundation CLI）</summary>

每个适配器都委派给该 checkout 的零依赖 Foundation CLI，因此下面的命令要在本仓库的 clone 中执行——这是 checkout 辅助路线，与上文的包管理器安装不同（[checkout 辅助安装](docs/installation.md#checkout-assisted-setup)）。[Codex 发现检查](docs/installation.md#check-codex-discovery) · [Foundation CLI 合同](docs/foundations.md)

| Agent Skill | CLI 权威命令 | 修改边界 |
|---|---|---|
| `super-azhou-info` | `info`、`version` | 只读报告项目、运行时、Git revision 和 dirty state。 |
| `super-azhou-doctor` | `doctor` | 只读诊断仓库、显式安装 target、可选 Treehouse lease 和宿主陈旧安装迁移。`--verify` 的验证子进程限时 10 分钟，有输出时会报告最后一行。 |
| `super-azhou-setup` | `setup`、`repair`、`migrate`、`uninstall` | 先 dry-run。安装时绑定已核对的计划；修复、迁移和卸载在执行时重新检查当前状态。 |
| `super-azhou-verify` | `verify` | 运行可公开复现的仓库完整性 gate：gate 输出中捕获到的 Foundation setup JSON 结果，若格式损坏、被截断，或状态不是 `pass`/`dry_run`，整个判定即为红（不通过）。 |

~~~bash
python scripts/azhou_hub.py info --json
python scripts/azhou_hub.py version --json
python scripts/azhou_hub.py doctor --json
python scripts/azhou_hub.py setup --skill super-repo-pedant --target /absolute/path/to/harness/skills --json
python scripts/azhou_hub.py verify
~~~

查看[完整确定性测试套件](docs/foundations.md#commands)和[验证依据](docs/skill-evidence.md)。

</details>

## 许可证

阿舟维护的代码：[MIT](LICENSE)。阿舟素材：[CC BY-NC-ND 4.0](assets/azhou/NOTICE.md)。名称、标识与角色：[TRADEMARKS.md](TRADEMARKS.md)。第三方组件保留自己的声明与许可证：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
