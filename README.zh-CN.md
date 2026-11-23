<div align="center">

# 🦊 Azhou AI Hub · 阿舟 AI 能力站

**不止能演示，更要经得起真实任务。**

足够小，可以改；足够严，可以验；足够中立，可以跨 Agent harness 使用。

[English](README.md) · [安装](docs/installation.md) · [支持矩阵](docs/support-matrix.md) · [文档索引](docs/README.md) · [参与贡献](CONTRIBUTING.md) · [站点](https://tefuirnever.github.io/azhou-ai-hub/)

[![CI](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/TeFuirnever/azhou-ai-hub?display_name=tag&sort=semver)](https://github.com/TeFuirnever/azhou-ai-hub/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-2f7d4a.svg)](LICENSE)

<img src="assets/github/readme-hero.png" alt="Azhou AI Hub 主视觉：阿舟狐狸把卡片送进亮着绿灯的闸机，旁边是主张文字——17 个可安装 skill 包、一个确定性仓库门禁、只有人类批准的演化。" width="100%" />

https://github.com/user-attachments/assets/35c1a361-d494-437f-ad6c-0049f6828fd3

</div>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/github/readme-banner-install.zh-CN-dark.jpg">
  <img src="assets/github/readme-banner-install.zh-CN.jpg" alt="安装：一条命令，装一个 skill" width="100%">
</picture>

### 在 Codex 里首次安装

先登录 Codex，并确认电脑已安装带 `npx` 的 Node.js；所有命令都在你想要安装 Ask Azhou 的项目目录下执行。示例命令均为 POSIX shell：Windows 请在 Git Bash 中运行（[Windows 说明](docs/installation.md#windows-notes)）；仓库 gate 与随附脚本覆盖哪些平台，见[操作系统支持表](docs/support-matrix.md#operating-system-support-deterministic-gate)。

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-ask-azhou --agent codex
~~~

在同一项目打开一个新的 Codex 会话，试着问下面的问题。

> `$super-ask-azhou` 我有一段 Mermaid，想把它做成可以交互查看的架构图。该用哪个 Hub Skill？

应看到它推荐 `super-archify`。如果找不到 Ask Azhou，先看[首次安装排查](docs/installation.md#first-install-in-codex)；已经装过时，可以[检查更新、更新或卸载](docs/installation.md#upgrade-or-uninstall)。

四个 Foundation Skill 用同样的方式安装：

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-info --agent codex
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-doctor --agent codex
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-setup --agent codex
npx skills add TeFuirnever/azhou-ai-hub --skill super-azhou-verify --agent codex
~~~

其余的包用同样的方式安装：

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-repo-pedant
npx skills add TeFuirnever/azhou-ai-hub --skill super-excalidraw-diagram
npx skills add TeFuirnever/azhou-ai-hub --skill super-eli5
npx skills add TeFuirnever/azhou-ai-hub --skill super-arch-doc
npx skills add TeFuirnever/azhou-ai-hub --skill super-session-insights
npx skills add TeFuirnever/azhou-ai-hub --skill super-asd-ste100
npx skills add TeFuirnever/azhou-ai-hub --skill super-archify
npx skills add TeFuirnever/azhou-ai-hub --skill super-lavish
npx skills add TeFuirnever/azhou-ai-hub --skill super-imagegen
npx skills add TeFuirnever/azhou-ai-hub --skill super-i-have-adhd
npx skills add TeFuirnever/azhou-ai-hub --skill super-rederive
npx skills add TeFuirnever/azhou-ai-hub --skill super-gh-axi
npx skills add TeFuirnever/azhou-ai-hub --skill super-frontend-design
npx skills add TeFuirnever/azhou-ai-hub --skill super-diagram-design
~~~

每个 skill 只选一种安装方式（[单一路径规则](docs/installation.md#one-path-rule)）。包管理器安装解析的是可变默认分支，不留 Hub 回执。四个 `super-azhou-*` 包只是薄封装：npx 命令装的是 Skill，但调用时执行的是本仓库 checkout 里的 Foundation CLI（`scripts/azhou_hub.py`），所以磁盘上仍需要这份 checkout（clone 一次即可）。

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
| [Archify](skills/super-archify/SKILL.md) | 把系统、计划或代码库变成交互图示地图 HTML。 | 上游 v3.2.0 同步（git tag + SHA-256）；收尾/校验 gate。 |
| [Lavish](skills/super-lavish/SKILL.md) | 把回答变成可审阅的 HTML；浏览器标注反馈回到 agent。 | 锁定的上游发布（SHA-256 + npm 钉定）；完整性测试。 |
| [Imagegen](skills/super-imagegen/SKILL.md) | 经本机已安装的私有 `azhou-imagegen` skill 执行准备好的生图请求；缺该 skill 或其 doctor gate 时 fail-closed。 | 仅契约层包；基线哈希钉定；fail-closed。 |
| [Rederive](skills/super-rederive/SKILL.md) | 通过重新推导设计来练习理解代码。 | 上游钉定（SHA-256）；仅探索性观察。 |
| [i-have-adhd](skills/super-i-have-adhd/SKILL.md) | 为 ADHD 读者塑形输出：下一步动作先行、步骤有界。 | 冻结上游（SHA-256）；正文逐字保留；完整性测试。 |
| [Gh Axi](skills/super-gh-axi/SKILL.md) | 经 agent 人体工学的封装 CLI 运行 GitHub 操作。 | 锁定的上游发布（SHA-256 + npm 钉定）；完整性测试。 |
| [Diagram Design](skills/super-diagram-design/SKILL.md) | 51 种视觉类型下创建品牌化、编辑级的 HTML/SVG 图表，支持 .drawio/Mermaid/.excalidraw/PlantUML 导入。 | 上游 vendored（commit 钉定 + 逐文件 SHA-256）；包内 `self_check.py` 门禁。 |
| [Frontend Design](skills/super-frontend-design/SKILL.md) | 为新 UI 或界面改版产出独特、非模板化的视觉设计方向：色板、字体排印、布局，以及避开 AI 默认观感的评审流程。 | 在 anthropics/skills 的钉定 commit 上 faithful 引入：上游指导正文逐字保留，Apache-2.0 许可逐字节 vendored，配 SHA-256 完整性测试。尚无行为 benchmark。 |

[逐 skill 平台汇总](docs/skill-platform-view.md) · [评测合同](docs/eval-case-contract.md)

### 上手试试

下表“必须返回什么”中的两个固定说法：hold＝明确挂起、留待后续处理的事项；稳定收据＝一次运行留下的可核对结果记录。

| Skill | 复制给 Agent | 必须返回什么 |
|---|---|---|
| Super Repo Pedant | <code>这个阶段做完了，跑一次 super-repo-pedant reconcile。</code> | 已对齐的知识面、具名检查、明确 hold 和稳定收据。[运行 demo](docs/demos/super-repo-pedant.md)。 |
| Excalidraw Diagram | <code>用 super-excalidraw-diagram 画登录时序图，交付可编辑源图和 PNG。</code> | 可编辑 <code>.excalidraw</code>、真实渲染/导出、确定性 gate、视觉复核状态和稳定收据。[运行 demo](docs/demos/super-excalidraw-diagram.md)。 |
| Arch Doc | <code>用 super-arch-doc 从这个仓库的上游设计文档产出架构说明书。</code> | 带出处的研究笔记、图注全记账的模板骨架、仅 PlantUML 的图纪律、确定性收尾门禁和稳定收据。[运行 demo](docs/demos/super-arch-doc.md)。 |

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

两个完整项目位于 `packages/`。这些项目不是 Skill；安装 Hub 的 Skill 不会启用任何集成。下文中的**候选版**（candidate）指已维护、但尚未接受为正式发布的源码版本；其证据以[支持矩阵](docs/support-matrix.md#optional-integrations)中带日期的收据为准，不构成发布声明。

| 入口 | 完整项目包 | 当前边界 |
|---|---|---|
| `pstack` | [pstack-agent-harness](packages/pstack-agent-harness/README.md) | `pstack-azhouzhou` 0.15.43 **候选版**：Codex／Claude 原生插件、自带捆绑 skills 的 zcode 插件，以及 MiMo 与 DeepSeek Harness 的共享 Skills 发现能力（维护者主机上的共享根 pstack 链接已于 2026-11-14 退役；以该方式向两者提供 pstack 移入单独任务处理，共享根中的其他 skill 不受影响）。带日期的证据与限制：[支持矩阵](docs/support-matrix.md#optional-integrations)。 |
| `agent-skin` | [阿舟 AI 实验室 for Codex](packages/agent-skin/README.md) | Codex 桌面冷启动时播放 12 秒阿舟启动动画并应用阿舟壁纸（视觉验收仍待人工确认；以[支持矩阵](docs/support-matrix.md#optional-integrations)为准）；组装好的 DeepSeek Harness 插件包把同样的外观带到 DSH。当前源码候选为 `0.9.0/build 43`。更新按[本地安装 SOP](packages/agent-skin/docs/local-install-sop.md) 执行。 |

[阿舟外观](packages/agent-skin/docs/theme-appearance.md#appearance-file-boundary)可选用本机图片和阿舟 JSON 预设，不导入其他项目的主题，也不迁移其他项目的数据。

[阿舟鼠标指针 3.3.1](assets/cursors/azhou-double-hug/README.md) 提供独立 Mousecape 候选包，桌面视觉验收仍待确认。

同样在本仓库的 clone 中执行：

~~~bash
python scripts/azhou_hub.py integrations list --json
python scripts/azhou_hub.py integrations pstack --help
python scripts/azhou_hub.py integrations agent-skin --help
~~~

pstack 保留其上游 MIT 声明。Agent Skin 代码自 #441 独立重写后由 Hub 根 MIT 许可证覆盖。`packages/agent-skin/assets/azhou/` 的阿舟素材采用 CC BY-NC-ND 4.0，阿舟名称、标识与角色见 [TRADEMARKS.md](TRADEMARKS.md)。

[接入手册](docs/integrations.md) · [来源记录](docs/integration-provenance.md) · [支持矩阵](docs/support-matrix.md#optional-integrations)

### 退役面

退役面、各自最后支持的版本，以及已装用户的处置方式：

- **agent-skin 的 ZCode 宿主层**——最后支持 `0.9.0/build 41`。已安装的 ZCode 皮肤作为冻结安装继续可用；恢复其原始启动器，或连同回执移除阿舟入口。
- **Agent Orchestration Kit（model router）**——从未公开发布。这一条只写给仍残留内部测试安装的机器：从 Git 历史或旧 release 取回其自带的卸载器执行卸载，然后再安装 pstack。
- **旧 `codex-startup-animation` 包**——末版 `0.7.1/build 8`，2026-11-12 移除。当前启动器源码由 Agent Skin 维护；Git 历史保留旧字节。
- **阿舟 Codex Pet**——2026-11-18 退役。见[退役记录](packages/agent-skin/evidence/azhou-pet-retirement-2026-11-18.md)。

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

在 Codex 中，`$refactoring` 把重构指南落到一次改动上，`$release-it` 评审故障恢复；14 套[书籍规则](THIRD_PARTY_NOTICES.md#agent-rules-books)随仓库放在 `.agents/skills/` 下——属于项目本地内容，不在 `skills/` 的 19 个可安装包之列——按需读取。

仓库级 gate 只需要 Python 3.11+：

~~~bash
python scripts/verify.py
~~~

## 项目入口

[文档](docs/README.md) · [产品原则](docs/principles.md) · [路线图](docs/roadmap.md) · [变更记录](CHANGELOG.md) · [发布流程](docs/releasing.md) · [安全政策](SECURITY.md) · [支持方式](SUPPORT.md) · [参与贡献](CONTRIBUTING.md)

## 许可证

阿舟维护的代码：[MIT](LICENSE)。阿舟素材：[CC BY-NC-ND 4.0](packages/agent-skin/assets/azhou/NOTICE.md)。名称、标识与角色：[TRADEMARKS.md](TRADEMARKS.md)。第三方组件保留自己的声明与许可证：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
