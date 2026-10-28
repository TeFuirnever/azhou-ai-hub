# Planned: super-i-have-adhd bounded pilot

本页是 [roadmap](../roadmap.md) 的 planning deliverable，遵循 [principles](../principles.md) 与 [Skill Standard](../skill-standard.md)。本次只完成 source comparison、scope 与 acceptance design；未新增 runtime package、安装、付费 experiment 或执行 pilot。以下 criteria 是 proposed local decision gates，不是已测结果或通用 benchmark。

## Source comparison 与最小增量

上游为 [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd)，本轮只读检查其 [current instructions](https://github.com/ayghri/i-have-adhd/blob/main/skills/i-have-adhd/SKILL.md) 和 [MIT notice](https://github.com/ayghri/i-have-adhd/blob/main/LICENSE)。读取的是 moving main，不将其冒充 immutable pin；执行比较前必须冻结完整 upstream commit、instruction/license bytes 与 hashes，保留 attribution。未复制 upstream runtime 到 Hub。

Upstream 已有 action-first、bounded steps、state continuity、停止模式、显式例外和保留重要 uncertainty；其 list rule 限制 presentation，不限制 analysis 或遗漏完整性所需内容。Harness 冲突时服从 native constraints。因此“更短”“固定四段”“不丢信息”本身不足以证明新增价值。

| 已有能力 / evidence | 与 pilot 的重叠 | 本次不重复的范围 |
|---|---|---|
| [Eli5](../../skills/super-eli5/SKILL.md) | 理解复杂主题 | 已有 zero-background HTML/picture contract；不把 precision-critical decision handoff 降为 Eli5 |
| [Lavish](../../skills/super-lavish/SKILL.md) | structured artifact / Spec Relay review | 不重建 HTML editor、annotation、relay state 或 publication workflow |
| [Arch Doc](../../skills/super-arch-doc/SKILL.md) | source calibration、evidence 与设计判断 | 不重建 architecture authoring workflow |
| [ASD-STE100](../../skills/super-asd-ste100/SKILL.md) | 清楚表达、保留精确信息 | 主要面向 agent-facing English rewrite，不等于 human decision continuity |
| Retired Super Caveman | 历史上合并 i-have-adhd 与 compression/routes | 以 retirement commit `f7788b2` 的 parent 中 SKILL、modes、provenance 为只读历史；当前目录已无此 package，见 [changelog](../../CHANGELOG.md)。不恢复 compression、companion routes、hooks 或 promotion machinery，不假设新 Skill 取代它 |

最小 enhancement hypothesis：在原 actionability 上，按任务需要把 decision 所需的 source pointers 与尚未验证的 limits 放在相应结论附近，并在 follow-up 区分状态变化和仍待决定项。仅在已有 evidence 时给链接，不创造证据。Review Contract（Outcome、Evidence、Limits、Decision）是可选组织方法，不固定 headings、不默认 HTML，不要求所有 turn 都使用，更不因阅读负荷缩减 analysis。若 upstream/current 已做到同样清楚，就选择不增强。

## 一个真实 workflow 与 reference harness

Workflow：维护者阅读 Hub 的 integration handoff，判断“现在能否接受能力、是否需要进入下一验收步骤”。使用现有 [coexistence live-session receipt](../../evidence/pstack-orchestrator-live-sessions-2026-10-27.md) 与 [support matrix](../support-matrix.md) 冻结一个脱敏 packet，保留 task ownership、explicit/named-role dispatch、hook trust unknown、单 client evidence 与没有 quality/cost claim 等事实。比较期间不执行安装、真实宿主操作或 Agent Skin 验收，也不抢占既有 integration workflow。

Reference harness 选 Codex：现有 receipt 已记录其 discovery、dispatch 与 task boundaries，适合作为第一个 bounded reference，而非永久 Codex-first 原则。历史 client 为 CLI `0.164.0-alpha.11.1`；执行 pilot 前重新记录实际 client build、model、effort、permissions 与 native Skill discovery，历史 receipt 不证明今天可用。不能使用时记 blocked，另选 harness 需明确记录新 evidence，不静默替换。

## Baseline / candidate comparison（未执行）

同一个 packet、同一 prompts、model/effort、tool permissions、task topology 与可用预算，分别在独立 context 中比较；不得同时激活相互竞争的 response modes。每一组经历相同三轮：初始 handoff；追问“哪些已证实、哪些仍未知”；加入“不改真实环境”的约束后询问下一步。只提供阅读 packet 的权限。

| Arm | 固定输入 / 用途 |
|---|---|
| A — Upstream | 冻结的原始 instructions，保留 actionability；native harness 约束优先，不复制全局 plugin/hook installation |
| B — Current | 当前 Hub checkout 的普通 response behavior 与现有项目规则，固定 HEAD 和实际 loaded instructions；无新增 Skill |
| C — Minimal candidate | 与 A 相同，仅加入上一节 evidence/limits 邻近结论与 follow-up decision continuity 的 presentation delta；品牌包装独立记录，不当作功能收益 |

保留 attempt-1 与 retries 的原因和完整次数，不只挑选最好输出。未来运行须另获授权；原始 prompts、outputs、paths 与个人反馈留在忽略的 local evidence，公开只保留脱敏 packet、摘要和可追溯 receipt。不得以此 pilot 请求 private sessions 或诊断用户 ADHD。

## Observable acceptance 与 decision

| 检查 | 预先定义的判据 |
|---|---|
| Material fidelity | 三轮中 packet 的全部 decision-critical facts、限制和重要 uncertainty 都保留且无相互矛盾；未知 hook trust 不写为 approved，isolated evidence 不扩展到所有版本，无捏造 source / test / cost claim |
| Actionability | 首轮能定位一个具体、符合授权的 next action；follow-up 正确接续状态；未完成事项仍可追踪，不引入 install/publish、第二 orchestrator 或额外用户动作 |
| Decision readability | Owner 对去除 Arm labels 的三份结果分别指出 outcome、supporting evidence、limits、待决定事项；记录需要回找或追问的位置，而非仅打“短”分 |
| Added value | Owner 明确认为 C 对该 workflow 比 A、B 更易理解或行动，并指出具体原因；若持平或更差，保留 upstream/current 或收窄 delta，不为产生 package 强行晋级 |
| No regression | C 不因五项分组、固定篇幅或 presentation 省略关键事实；token/cost/quota 若有 host counters 则分别记录，否则 unknown；无 savings 或总体模型质量推论 |

Material fidelity 与 no regression 必须全过；owner 认可独立于 automated checks。一次偏好只能支持该 workflow 的 provisional decision，不构成 quantitative proof、医学效果、跨 harness 支持或正式 owner endorsement。之后是否实现、扩大样本、安装或发布分别决定。

本轮没有必须先问用户才能完成 design 的问题。Harness 与 workflow 是基于现有 evidence 的 reference choices；未来实际运行所用 client/model/budget、冻结的 upstream revision 和输入 packet 仍需按执行时上下文确认，不编造已获 runtime/spending authorization。
