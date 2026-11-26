<div align="center">

# 🦊 Azhou AI Hub · 阿舟 AI 能力站

**不止能演示，更要经得起真实任务。**

足够小，可以改；足够严，可以验；足够中立，可以跨 Agent harness 使用。

[English](README.md) · [安装](docs/installation.md) · [支持矩阵](docs/support-matrix.md) · [文档索引](docs/README.md) · [参与贡献](CONTRIBUTING.md) · [站点](https://tefuirnever.github.io/azhou-ai-hub/)

[![CI](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/TeFuirnever/azhou-ai-hub?display_name=tag&sort=semver)](https://github.com/TeFuirnever/azhou-ai-hub/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-2f7d4a.svg)](LICENSE)

</div>

## 能力

| 能力 | 可以做什么 |
|---|---|
| [Hub Skills](#skills) | 有 21 个可安装包，支持架构绘图、方案探索和仓库检查等任务。 |
| [阿舟 Agent 工作台](packages/azhou-agent-inspector/README.md) | 在 Codex 和 ZCode 查看整轮耗时、速率及可用的性能详情。 |
| [pstack](packages/pstack-agent-harness/README.md) | 用工程工作流完成实现、评审和 PR 跟进。 |
| [Agent Rules Books](#agent-rules-books) | 用 14 套书籍工程规则指导设计、代码改动和评审。 |
| [阿舟来源库](https://tefuirnever.github.io/azhou-ai-hub/zh/library/) | 搜索 AI 官方选文、订阅 RSS，或打开 [Agent 阅读索引](https://tefuirnever.github.io/azhou-ai-hub/llms.txt)。 |

维护者可用[来源库工具](packages/source-library/README.md)试抓 RSS、网页或 JSON 信源，批量导入候选，并将选文留存在私有目录。

## 在 Codex 里首次安装

想一次装齐 Hub Skills、pstack 和 Agent Rules Books，或按需选择其中几套，可以使用 [Codex 统一安装命令](docs/installation.md#install-hub-components-in-codex)。

先登录 Codex，并确认电脑已安装 Node.js 22.20 或更新版本。在项目目录运行下面的命令，看到提示后确认安装到当前项目。Windows 用户请在 Git Bash 中运行[示例命令](docs/installation.md#windows-notes)。

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-ask-azhou --agent codex
~~~

在同一项目打开一个新的 Codex 会话。先输入 `$super-ask-azhou`，确认 Codex 找得到它，再试试下面的问题。

> `$super-ask-azhou` 我有一段 Mermaid，想把它做成可以交互查看的架构图。该用哪个 Hub Skill？

正常情况下，它会推荐 `super-archify`。如果 Codex 找不到 Ask Azhou，可以[检查安装](docs/installation.md#if-codex-cannot-find-ask-azhou)。已经装过时，可以[检查更新、更新或卸载](docs/installation.md#upgrade-or-uninstall)。

想安装 Ask Azhou 推荐的技能时，按[单个技能安装指南](docs/installation.md#package-manager-install)操作。每个技能只选[一种安装方式](docs/installation.md#one-path-rule)。四个 `super-azhou-*` 技能还需要一份本地仓库 checkout。

上面的走查以 Codex 为目标。其余受维护的 harness——Claude Code、MiMo Code（`mimo`）、DeepSeek Harness（`dsh`）、zcode——各自的已验证安装路线与证据见[支持矩阵](docs/support-matrix.md)；也可以用仓库 checkout 走 [checkout 辅助安装](docs/installation.md#checkout-assisted-setup)或[手动复制](docs/installation.md#manual-copy)。

[更新或卸载](docs/installation.md#upgrade-or-uninstall) · [校验安装内容](docs/installation.md#verify-what-you-installed) · [安装指南](docs/installation.md) · [离线恢复](docs/installation.md#offline-recovery)

## Skills

每个改编包都在 `skills/<name>/references/provenance.md` 记录自己的上游出处；SHA-256 源码钉定与 npm 完整性钉定只出现在该文件实际记录之处——并不是全目录的统一保证。

| Skill | 解决的真实任务 | 验证依据 |
|---|---|---|
| [Azhou Info](skills/super-azhou-info/SKILL.md) | 汇报 checkout、运行时、支持范围与可证明的 Git revision 事实。 | 稳定的 `info`/`version` JSON 合同；只读检查。 |
| [Azhou Doctor](skills/super-azhou-doctor/SKILL.md) | 只读诊断仓库、安装 target、lease 与宿主迁移健康。 | 只读 doctor 合同；Treehouse lease smoke 合同（subprocess 边界单测）；fail-closed。 |
| [Azhou Setup](skills/super-azhou-setup/SKILL.md) | 引导按范围安装、更新与卸载，含 checkout 受管的生命周期。 | 先 dry-run 的安装；变更锁、身份防护与回滚回归。 |
| [Azhou Verify](skills/super-azhou-verify/SKILL.md) | 运行公开的全仓完整性 gate。 | 仓库策略、退役面反向扫描、单元测试、包清单/生命周期、benchmark 完整性、接线完整性与空白检查。 |
| [Super Repo Pedant](skills/super-repo-pedant/SKILL.md) | 任务收尾时对齐文档、规则与交接状态。 | 上游 `neat-freak` 基线（[Khazix-Skills](THIRD_PARTY_NOTICES.md#super-repo-pedant-baseline)）28/28 项能力有账可查；4 个已注册行为 case。 |
| [Excalidraw Diagram](skills/super-excalidraw-diagram/SKILL.md) | 创建或编辑可继续修改的场景；渲染、检查并交付 CJK 安全的 SVG/PNG。 | 5 个冻结 benchmark case；确定性的风格/场景/重叠 gate。 |
| [Eli5](skills/super-eli5/SKILL.md) | 把主题讲成一份自包含的 HTML——大图、少字。 | 上游行为句钉定（SHA-256）；尚无行为 benchmark。 |
| [Ask Azhou](skills/super-ask-azhou/SKILL.md) | 路由：说清意图，得到 skill、模式与边界。 | 带负控的路由图一致性校验 gate。 |
| [Arch Doc](skills/super-arch-doc/SKILL.md) | 从上游资料起草、校准并评审架构文档。 | 确定性脚手架、收尾门检查器与黄金用例。 |
| [Session Insights](skills/super-session-insights/SKILL.md) | 从本机会话存储产出事实绑定的使用报告；对已授权材料做反思。 | 合成存储接线套件；反思合同检查。 |
| [ASD-STE100](skills/super-asd-ste100/SKILL.md) | 按源自 ASD-STE100 的结构规则改写面向 agent 的英文。 | 上游钉定（SHA-256）；确定性的 `ste-lint.py` gate。 |
| [Archify](skills/super-archify/SKILL.md) | 把系统、计划或代码库变成交互图示地图 HTML、代码分析覆盖层与故事走查。 | 上游 v3.3.0 同步（git tag + SHA-256；Apache-2.0、历史 MIT 授权保留；explainer 默认主动）；SVG 样式校验与收尾验证。 |
| [Lavish](skills/super-lavish/SKILL.md) | 把回答变成可审阅的 HTML；浏览器标注反馈回到 agent。 | 锁定的上游发布（SHA-256 + npm 钉定）；完整性测试。 |
| [Imagegen](skills/super-imagegen/SKILL.md) | 经本机已安装的私有 `azhou-imagegen` skill 执行准备好的生图请求；缺该 skill 或其 doctor gate 时 fail-closed。 | 仅契约层包；基线哈希钉定；fail-closed。 |
| [Rederive](skills/super-rederive/SKILL.md) | 通过重新推导设计来练习理解代码。 | 上游钉定（SHA-256）；仅探索性观察。 |
| [i-have-adhd](skills/super-i-have-adhd/SKILL.md) | 为 ADHD 读者塑形输出：下一步动作先行、步骤有界。 | 冻结上游（SHA-256）；正文逐字保留；完整性测试。 |
| [Gh Axi](skills/super-gh-axi/SKILL.md) | 经 agent 人体工学的封装 CLI 运行 GitHub 操作。 | 锁定的上游发布（SHA-256 + npm 钉定）；完整性测试。 |
| [Diagram Design](skills/super-diagram-design/SKILL.md) | 51 种视觉类型下创建品牌化、编辑级的 HTML/SVG 图表，支持 .drawio/Mermaid/.excalidraw/PlantUML 导入。 | 上游 vendored（commit 钉定 + 逐文件 SHA-256）；包内 `self_check.py` 门禁。 |
| [Frontend Design](skills/super-frontend-design/SKILL.md) | 为新 UI 或界面改版产出独特、非模板化的视觉设计方向：色板、字体排印、布局，以及避开 AI 默认观感的评审流程。 | 在 anthropics/skills 的钉定 commit 上 faithful 引入：上游指导正文逐字保留，Apache-2.0 许可逐字节 vendored，配 SHA-256 完整性测试。尚无行为 benchmark。 |
| [Brainstorming](skills/super-brainstorming/SKILL.md) | 在动手前探清读者真正想要什么与为什么：枚举方案、写设计文档、守审批门。 | 上游 adapted（tag 钉定 + 逐文件 SHA-256 锚）；六处记录在案 delta；完整性测试。尚无行为 benchmark。 |
| [Grill Me](skills/super-grill-me/SKILL.md) | 按轮拷问用户的方案、决定或想法：前提已定的问题逐个附上推荐答案，事实去查，决策留给用户。 | 上游 adapted（tag 钉定；上游触发句逐字保留；正文除一句外逐字保留）；SHA-256 完整性测试。尚无行为 benchmark。 [Claude Code 宿主实测](evidence/super-grill-me-host-check-claude-2026-11-24.md). |

[逐 skill 平台汇总](docs/skill-platform-view.md) · [评测合同](docs/eval-case-contract.md)

### 上手试试

https://github.com/user-attachments/assets/35c1a361-d494-437f-ad6c-0049f6828fd3

下表“必须返回什么”中的两个固定说法：hold＝明确挂起、留待后续处理的事项；稳定收据＝一次运行留下的可核对结果记录。

| Skill | 复制给 Agent | 必须返回什么 |
|---|---|---|
| Super Repo Pedant | <code>这个阶段做完了，跑一次 super-repo-pedant reconcile。</code> | 已对齐的知识面、具名检查、明确 hold 和稳定收据。[运行 demo](docs/demos/super-repo-pedant.md)。 |
| Excalidraw Diagram | <code>用 super-excalidraw-diagram 画登录时序图，交付可编辑源图和 PNG。</code> | 可编辑 <code>.excalidraw</code>、真实渲染/导出、确定性 gate、视觉复核状态和稳定收据。[运行 demo](docs/demos/super-excalidraw-diagram.md)。 |
| Arch Doc | <code>用 super-arch-doc 从这个仓库的上游设计文档产出架构说明书。</code> | 带出处的研究笔记、图注全记账的模板骨架、仅 PlantUML 的图纪律、确定性收尾门禁和稳定收据。[运行 demo](docs/demos/super-arch-doc.md)。 |

## Agent Rules Books

从下面 14 套书籍工程规则中，选一套来处理眼前的工程问题。

- `a-philosophy-of-software-design` 用来简化模块边界和 API。
- `clean-architecture` 用来让业务规则独立于框架、数据库和界面。
- `clean-code` 用来改进命名、函数和代码可读性。
- `code-complete` 用来检查控制流、防御性代码和测试。
- `designing-data-intensive-applications` 用来分析数据一致性、复制和可靠性。
- `domain-driven-design` 用来为复杂业务建模、划分限界上下文。
- `domain-driven-design-distilled` 用来梳理子域和上下文之间的关系。
- `implementing-domain-driven-design` 用来实现聚合、领域事件和仓储。
- `patterns-of-enterprise-application-architecture` 用来选择服务层、事务脚本和数据映射器等模式。
- `refactoring` 用来改进现有代码结构，同时保留可观察的行为。
- `refactoring-guru` 用来识别代码坏味道、选择重构手法。
- `release-it` 用来评审超时、重试、熔断和故障恢复。
- `the-pragmatic-programmer` 用来缩短反馈周期、判断哪些工作值得自动化。
- `working-effectively-with-legacy-code` 用来通过接缝和刻画测试安全修改难以测试的代码。

### 在 Azhou AI Hub 开发时使用

Hub 维护的版本在 `.agents/skills/`。开发 Hub 时，直接使用当前 checkout 自带的规则。在这个 checkout 打开的 Codex 会话里，可以输入 `$refactoring 检查这次改动，建议一项能保持行为的最小重构。` Ask Azhou 核实当前工作区已启用对应规则后，也可以推荐它。

### 在其他项目安装

准备好 Node.js 和 npm 后，在自己的项目目录运行下面的命令，为 Codex 安装 Hub 维护的版本。把 `refactoring` 换成上面任意一个规则名即可。如果安装器询问安装范围，请选当前项目。

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill refactoring --agent codex
~~~

在同一项目里打开新会话，确认能找到该技能后再调用。安装器默认从 Hub 的默认分支取规则。要与某个 Hub checkout 的版本完全一致，在仓库名后加 `@<commit>`。[安装和更新说明](https://github.com/TeFuirnever/azhou-ai-hub/blob/main/docs/installation.md#install-agent-rules-books)

## 为什么可信

- **现役行为优先。** 代码、机器配置和真实运行证据定义 current truth；未实现的 spec 保留为 reminder。
- **主张必须有 gate。** 仓库权威 gate 运行完整确定性测试套件——仓库策略、退役面反向扫描、Hub 单元测试、包清单/生命周期套件、全部已注册 benchmark 完整性与接线完整性套件——外加空白检查。
- **宿主差异保持可见。** 当前维护的目标是 Codex、Claude Code、MiMo Code（命令 `mimo`）、DeepSeek Harness（命令 `dsh`）和 zcode；其他 harness 暂不支持。见[支持矩阵](docs/support-matrix.md)与[逐 skill 平台汇总](docs/skill-platform-view.md)。
- **历史不能静默改写 live skill。** promotion 必须通过规定的回归用例与确定性检查，再经成对评审以多数胜出（奇数次、至少三次的同裁判成对比较须按多数支持候选），无安全回归，并取得绑定到 exact diff 的人类批准。
- **来源可追溯。** 上游快照、vendored 资产与被排除的无许可 prior art 记录在[第三方声明](THIRD_PARTY_NOTICES.md)。

![Azhou AI Hub：公开的验证命令与一次本地验证结果。](assets/github/readme-proof.png)

[评测合同](docs/eval-case-contract.md)定义了一个包可以主张的最低行为证据。

## Foundation CLI

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

## 集成

可选集成位于 `packages/`。这些项目不是 Skill；安装 Hub 的 Skill 不会启用任何集成。下文中的**候选版**（candidate）指已维护、但尚未接受为正式发布的源码版本；其证据以[支持矩阵](docs/support-matrix.md#optional-integrations)中带日期的收据为准，不构成发布声明。

| 入口 | 完整项目包 | 当前边界 |
|---|---|---|
| `azhou-agent-inspector` | [阿舟 Agent 工作台](packages/azhou-agent-inspector/README.md) | Codex 会话侧面板、ZCode 输入框状态项与会话仪表盘。两个面板都显示整轮耗时和速率，可按需展开性能详情。宿主提供实际请求的用量和窗口上限时，详情会显示 Context 占用。工作台 0.12.13 遵循系统的「减少动态效果」偏好。通过各宿主自己的插件管理器安装。[各版本验收记录与待验项](docs/support-matrix.md#azhou-agent-workbench)。 |
| `pstack` | [pstack-agent-harness](packages/pstack-agent-harness/README.md) | `pstack-azhouzhou` 0.15.43 **候选版**：Codex／Claude 原生插件、自带捆绑 skills 的 zcode 插件，以及 MiMo 与 DeepSeek Harness 的共享 Skills 发现能力（维护者主机上的共享根 pstack 链接已于 2026-11-14 退役；以该方式向两者提供 pstack 移入单独任务处理，共享根中的其他 skill 不受影响）。带日期的证据与限制：[支持矩阵](docs/support-matrix.md#optional-integrations)。 |


[阿舟鼠标指针 3.6.1](assets/cursors/azhou-double-hug/README.md) 是一套适用于 macOS 的独立 Mousecape 皮肤。主题指南提供下载、安装和恢复系统指针的入口。

同样在本仓库的 clone 中执行：

~~~bash
python scripts/azhou_hub.py integrations list --json
python scripts/azhou_hub.py integrations pstack --help
~~~


[接入手册](docs/integrations.md) · [来源记录](docs/integration-provenance.md) · [支持矩阵](docs/support-matrix.md#optional-integrations)

### 退役面

退役面、各自最后支持的版本，以及已装用户的处置方式：

- **Agent Skin** 已退役，覆盖 Codex、DSH 与此前退役的 ZCode。见[已安装用户退出说明](docs/decisions/agent-skin-retirement.md)。
- **Agent Orchestration Kit（model router）**——从未公开发布。这一条只写给仍残留内部测试安装的机器：从 Git 历史或旧 release 取回其自带的卸载器执行卸载，然后再安装 pstack。
- **旧 `codex-startup-animation` 包**——末版 `0.7.1/build 8`，2026-11-12 移除。Git 历史保留旧字节。
- **阿舟 Codex Pet**——2026-11-18 退役。见[退役记录](https://github.com/TeFuirnever/azhou-ai-hub/blob/1eeb03c6005ac08b2c852d6f61823181bcee4fe4/packages/agent-skin/evidence/azhou-pet-retirement-2026-11-18.md)。

[HUB-RET-001](docs/decisions/hub-retirement-physical-deletion.md) 记录了这次切割；[来源记录](docs/integration-provenance.md)各历史行定位每个删除前的修订，所有旧 release 与 tag 全量保留。

## 一套架构

~~~text
docs/skill-standard.md ── 约束 ──> skills/<name>/       可安装运行包
          │                              │
          ├── 分配 ──────────────────> .azhou/<name>/      私有运行状态
          ├── 约束 ──────────────────> tests/              确定性证明
          └── 约束 ──────────────────> benchmarks/<name>/  隔离行为证据

历史信号 ──> 隔离 candidate ──> paired review ──> 人类 promotion
                    永远不直接写 live skill
~~~

[Azhou Skill Standard](docs/skill-standard.md) 是项目唯一准则；[架构说明](docs/architecture.md)解释边界，[治理规则](GOVERNANCE.md)解释决策方式。

## 开发

开发 Hub 时，可以用 Hub Skill 完成仓库文档对齐等具体任务，也可以用已安装的 pstack 工作流推进实现或评审。每项任务由一套工作流主导，遇到具体工程判断时按需调用 [Agent Rules Books](#agent-rules-books)。[书籍规则来源与许可](THIRD_PARTY_NOTICES.md#agent-rules-books)

仓库级 gate 只需要 Python 3.11+：

~~~bash
python scripts/verify.py
~~~

## 项目入口

[文档](docs/README.md) · [产品原则](docs/principles.md) · [路线图](docs/roadmap.md) · [变更记录](CHANGELOG.md) · [发布流程](docs/releasing.md) · [安全政策](SECURITY.md) · [支持方式](SUPPORT.md) · [参与贡献](CONTRIBUTING.md)

## 许可证

阿舟维护的代码：[MIT](LICENSE)。阿舟素材：[CC BY-NC-ND 4.0](assets/azhou/NOTICE.md)。名称、标识与角色：[TRADEMARKS.md](TRADEMARKS.md)。第三方组件保留自己的声明与许可证：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
