<div align="center">

# 🦊 Azhou AI Hub · 阿舟 AI 能力站

**不止能演示，更要经得起真实任务。**

足够小，可以改；足够严，可以验；足够中立，可以跨 Agent Core 运行。

[English](README.md) · [安装](docs/installation.md) · [支持矩阵](docs/support-matrix.md) · [参与贡献](CONTRIBUTING.md)

[![CI](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/ci.yml)
[![CodeQL](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/codeql.yml/badge.svg)](https://github.com/TeFuirnever/azhou-ai-hub/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-2f7d4a.svg)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/TeFuirnever/azhou-ai-hub?display_name=tag&sort=semver)](https://github.com/TeFuirnever/azhou-ai-hub/releases)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/TeFuirnever/azhou-ai-hub/badge)](https://securityscorecards.dev/viewer/?uri=github.com/TeFuirnever/azhou-ai-hub)

<img src="assets/github/social-preview.png" alt="Azhou AI Hub——以证据驱动的 Agent Skills" width="100%" />

</div>

很多 skill 仓库停在提示词。Azhou AI Hub 把每个 skill 当成产品：触发准确、运行包可移植、依赖可复现、检查可执行、评测不造假、来源可追踪、演化受人类控制。

这里不做接管一切的通用框架，不为每个模型复制一份 skill，也不把 benchmark 答案藏进运行包。

## 30 秒安装

安装一个 skill：

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill repo-pedant
~~~

或者：

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill excalidraw-diagram
~~~

如需通过 Agent Skill 诊断 checkout：

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill azhou-doctor
~~~

或者：

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill super-caveman
~~~

只选一种安装方式。同一 canonical name 下，不要叠加托管安装、手工复制和开发软链接。手工安装与贡献者软链接见[安装指南](docs/installation.md)。

## 诊断或配置当前 checkout

四个可移植阿舟 Agent Skills 提供 checkout 工作流入口，但不复制执行逻辑：`azhou-info`、`azhou-doctor`、`azhou-setup` 和 `azhou-verify`。它们先定位显式的 Azhou AI Hub checkout，再委派给零依赖基础 CLI。CLI 继续作为仓库级 `info`、`version`、只读 `doctor`、先 dry-run 的 `setup`、canonical `verify` 以及 receipt-owned `repair`、同 target `migrate` 和 `uninstall` 的唯一权威：

~~~bash
python3 scripts/azhou_hub.py doctor --json
python3 scripts/azhou_hub.py setup --skill repo-pedant --target /absolute/path/to/harness/skills --json
python3 scripts/azhou_hub.py setup --managed --receipt /absolute/path/to/receipt.json --skill repo-pedant --target /absolute/path/to/harness/skills --json
~~~

只有出现 `--apply` 才会修改文件；重复执行可收敛；遇到不同安装会拒绝覆盖。Managed 生命周期命令要求再次提供同一 target，并独立校验 canonical source 与安装身份；不会强制覆盖 drift、跨 harness root 迁移、安装 hook、重写宿主配置、访问 registry 或自更新。完整边界见[基础 CLI 合同](docs/foundations.md)。

## Skills

| Skill | 解决的真实任务 | 当前证据 |
|---|---|---|
| [Azhou Info](skills/azhou-info/SKILL.md) | 报告 checkout、运行时、支持范围和可证明的 Git revision，不虚构发布状态。 | 委派给稳定的 `info` / `version` JSON 合同；只读包检查与仓库策略检查。 |
| [Azhou Doctor](skills/azhou-doctor/SKILL.md) | 只读诊断仓库、显式安装 target 和可选 Treehouse lease。 | 只读 doctor 合同、真实 Treehouse 2.3.0 smoke 和 fail-closed target 检查。 |
| [Azhou Setup](skills/azhou-setup/SKILL.md) | 先规划再显式执行 checkout-assisted 安装或 receipt-owned 生命周期操作。 | dry-run-first setup、mutation lock、身份防护、rollback 与 receipt 回归。 |
| [Azhou Verify](skills/azhou-verify/SKILL.md) | 执行并报告唯一权威的全仓验证 gate。 | 委派给已注册的仓库策略、单元测试、benchmark integrity 和空白检查。 |
| [Repo Pedant](skills/repo-pedant/SKILL.md) | 明确任务结束时，用当前代码校正文档、项目规则、交接状态和已绑定项目 memory。 | 28/28 项 <code>neat-freak</code> 能力有机器映射；3 个注册行为 case；固定执行协议与 memory inventory 证明。 |
| [Excalidraw Diagram](skills/excalidraw-diagram/SKILL.md) | 生成或编辑可继续修改的图，渲染真实产物、查看成图，并按需交付 CJK-safe SVG/PNG。 | 5 个冻结 benchmark case；风格、场景、重叠和 same-DOM 确定性 gate。仓库 reference 只证明接线，不冒充模型效果。 |
| [Super Caveman](skills/super-caveman/SKILL.md) | 在原版 Caveman 上完整采用锁定版 `i-have-adhd` 输出行为，并吸纳 commit、review、委派、帮助、文件压缩和统计路线。 | 原版 Caveman 加六个伴生 Skill，收口为一个 canonical 包；8 条路线、保留的 14-case 历史证据、当前 19/19 case 与 44/44 criterion 行为运行、三名独立配对评审 3/3 选择 candidate 且高风险回归为 0，以及可恢复压缩门禁。证据仅适用于记录的 Codex Desktop 宿主/模型。 |

七个包都可独立安装。Azhou Skills 需要显式本地 checkout，因为它们编排仓库级 CLI，不在 prompt 中复制执行逻辑。运行时材料在 <code>skills/</code>；prompt、assertion、fixture 和 judge record 在仓库级 <code>benchmarks/</code>。

## 60 秒试用三个任务型 Skill

| Skill | 复制给 Agent | 必须返回什么 |
|---|---|---|
| Repo Pedant | <code>这个阶段做完了，跑一次 repo-pedant reconcile。</code> | 已对齐的知识面、具名检查、明确 hold 和稳定收据。[运行 demo](docs/demos/repo-pedant.md)。 |
| Excalidraw Diagram | <code>用 excalidraw-diagram 画登录时序图，交付可编辑源图和 PNG。</code> | 可编辑 <code>.excalidraw</code>、真实渲染/导出、确定性 gate、视觉复核状态和稳定收据。[运行 demo](docs/demos/excalidraw-diagram.md)。 |
| Super Caveman | <code>使用 /super-caveman full，再为这份 diff 写 commit message。</code> | 行动优先精简模式和可直接粘贴的 Conventional Commit；不暂存、不提交。 |

Demo 严格区分产品行为与 benchmark 主张：合成 fixture 只证明合同和 verifier 接线，只有冻结的 attempt-1 运行才算模型证据。

## 为什么可信

- **现役行为优先。** 代码、机器配置和真实运行证据定义 current truth；未实现 spec 保留为 reminder。
- **主张必须有 gate。** 仓库执行当前确定性测试套件、3-case Repo Pedant 套件、8-route 加 19-response-case Super Caveman 完整性套件、5-case Excalidraw benchmark 完整性检查、JSON/链接/来源/凭据策略和空白检查。
- **不伪装跨平台完全等价。** Codex、Claude Code、zcode 共用运行包，但 hook 与历史适配能力在[支持矩阵](docs/support-matrix.md)中分开写。
- **历史不能静默改 live skill。** promotion 必须先有回归，再通过确定性检查、paired 多数、无安全回归和 exact-diff 人类批准。
- **来源边界公开。** 上游快照、vendored 资产和未授权 prior art 的排除记录见[第三方声明](THIRD_PARTY_NOTICES.md)。

## Repo Pedant

> 🧹 代码是唯一现役答案，其他都要对齐。

任务确实结束时显式调用：

~~~text
这个阶段做完了，跑一次 repo-pedant reconcile。
~~~

只推测 milestone 时，skill 只提醒一次，不静默写仓库。明确 reconcile/handoff 默认覆盖三层项目知识：用户文档、<code>AGENTS.md</code>/<code>CLAUDE.md</code>、已证明属于当前项目的 memory。全局指令、归属不明 memory、整文件删除、发布和部署继续保留 checkpoint。

[兼容合同](skills/repo-pedant/references/neat-freak-compatibility.md) · [执行协议](skills/repo-pedant/references/execution-protocol.md)

![Repo Pedant 效果图](assets/skills/repo-pedant-effect.png)

> 🦊 效果图由 Azhou Scenes skill 生成。机器颜色门禁已通过；身份、手部和文字仍保留人工复核 checkpoint。

## Excalidraw Diagram

> ✏️ 先让结构讲清关系，再让文字补充证据。

JSON 可解析不等于完成。这个 skill 要求交付可编辑源图，用官方引擎渲染，实际查看图片，从源场景修复，再重跑 gate。离线字体、官方引擎、转换器和 231 个 MIT 许可的组件库随运行包提供。

![Excalidraw Diagram 效果图](assets/skills/excalidraw-diagram-effect.png)

> ✏️ 效果图由 Azhou Scenes skill 生成。机器颜色门禁已通过；身份、手部和文字仍保留人工复核 checkpoint。

[运行包](skills/excalidraw-diagram/SKILL.md) · [依赖安装](skills/excalidraw-diagram/references/setup.md) · [来源说明](skills/excalidraw-diagram/references/provenance.md)

## Super Caveman

> 🪨 少说话，技术信号不丢。

Super Caveman 保留原版 Caveman 的持续精简模式作为核心，把六个伴生 Skill 吸纳为紧凑委派、commit message、review、受保护文本压缩、帮助和证据约束统计路线，并完整采用锁定版 `i-have-adhd` 的输出行为合同。全部能力只通过一个 canonical `super-caveman` 包交付。安全与显式输出合同优先，完整 ADHD-friendly 行为合同其次，Caveman 压缩最后。插件安装、hook、全局配置、诊断主张和未经验证的跨会话持久化不进入这个中立包。文件压缩不会启动第二个模型，也不会静默外传内容；标准库门禁会检查源文件、验证受保护结构、写入仓库外备份、使用检查点式不覆盖安装，并拒绝覆盖更新后的文件。受保护 apply/restore 要求文件系统支持同目录 hard link；不支持时会在移动源文件前阻断。关键操作每个已验证阶段只使用一个克制的阿舟锚点；普通精简回复不添加生命周期 emoji。宿主没有可审计计数器时，精确统计明确返回不可用。

[运行包](skills/super-caveman/SKILL.md) · [依赖安装](skills/super-caveman/references/setup.md) · [来源说明](skills/super-caveman/references/provenance.md) · [压缩安全流程](skills/super-caveman/references/compression.md)

## 一套架构

~~~text
docs/skill-standard.md ── 约束 ──> skills/<name>/       可安装运行包
          │                              │
          ├── 约束 ──────────────────> tests/              确定性证明
          └── 约束 ──────────────────> benchmarks/<name>/  隔离行为证据

历史信号 ──> 隔离 candidate ──> paired review ──> 人类 promotion
                    永远不直接写 live skill
~~~

[Azhou Skill Standard](docs/skill-standard.md) 是项目唯一准则。[架构说明](docs/architecture.md)解释边界，[治理规则](GOVERNANCE.md)解释决策方式。

## 开发

仓库级验证只需要 Python 3.11+：

~~~bash
python3 scripts/verify.py
~~~

同一条命令检查仓库策略、全部单元测试、三套 benchmark 完整性和 Git 空白。Excalidraw 真渲染需要额外锁定的 Python/Node 依赖，按自己的 setup 文档安装。

## 项目入口

- [路线图](docs/roadmap.md)
- [变更记录](CHANGELOG.md)
- [安全政策](SECURITY.md)
- [支持方式](SUPPORT.md)
- [基础 CLI](docs/foundations.md)
- [Treehouse worktree 规范](docs/worktree-policy.md)
- [本次开源化对标研究](docs/research/2026-08-23-open-source-benchmark.md)

贡献应从真实失败或真实任务开始，以可复现证据结束。先读 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

阿舟自研代码使用 [MIT](LICENSE)。第三方组件保留自己的版权与许可证：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
