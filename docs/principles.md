# Azhou AI Hub principles

本页记录已确认的产品方向与取舍。它不替代 [Skill Standard](skill-standard.md)、[integration contract](integrations.md)、[support matrix](support-matrix.md) 或现有 license，也不把 Planned 工作变成已交付能力。[Roadmap](roadmap.md) 记录下一步；当前实现以 code、configuration 和原始 evidence 为准。

## Myself first, community-ready

先解决维护者真实使用中的 workflow 问题，再把有价值的能力做成别人可复用、可配置的 package。社区实践用于发现不同场景、改进能力与边界；不为了抽象上的完整性建设无人使用的平台。

## 三个互补 pillars

| Pillar | 主要价值 | 约束 |
|---|---|---|
| Human-facing Skills | 帮助人理解、判断并行动，补充 pstack、matt-style engineering workflows | 保持真实任务的 actionability，不重复接管已有 engineering workflow |
| Azhou UI personalization | 统一角色体验，可适度改善 readability 与 layout | 尊重 agent harness 的 native workflow、permissions、tools 与 model semantics；可配置、可逆，不做 replacement client |
| Orchestrator Kit | 在明确 quality requirements 下提高 token / model-budget efficiency | 不建设 generic scheduling platform，也不承诺超过 unlimited-budget best-model execution |

各项能力独立 opt-in。某个 Skill、UI 或 Kit 的安装与启用不自动启用其他能力；现有每个 task 一个 workflow owner 的 composition rule 保持有效。

## Azhou IP 与 firsthand endorsement

Azhou IP 是一个统一角色，以及维护者亲自使用后认为 useful / valuable 的个人背书。统一 identity 不要求共享 runtime 或 character engine。Automated tests 证明对应 checks，不能代替 owner endorsement；个人使用反馈、正式 visual approval 和 community validation 分别记录。任何一种认可都不自动覆盖所有 harnesses、versions 或整个 catalog，也不追认未验证能力。

保留 upstream authorship、attribution、provenance 和现有 notices；Azhou identity 不抹去来源。能力适配与 Azhou identity 都是修改 upstream 的合理原因，但应保留 core behavioral intent，使用 harness native mechanisms，并清楚记录有意改变、fallback 与 unsupported states。无需强制 universal runtime 或跨 harness parity。

## Capability-first support 与维护

按真实 capability 选择适合的 harness，不永久规定全项目 Codex-first，也不要求所有 harness 同时支持。每项 support claim 写明 capability、upstream revision、实际 validated harness/version、evidence 与 known limits；未验证、experimental、unsupported、deprecated 如实标注，不用 portable package 推导 runtime parity。

Upstream updates 先 review 再 merge，不自动覆盖本地适配。Bug report、planned release 或 known breaking change 触发相关 revalidation；没有 SLA 或 all-version promise。Kit comparisons 固定同一 task topology 和 quality criteria，计入 retries，区分 token counts、monetary cost 与 quota；没有对应 evidence 不宣称 savings。

## 让人理解，再作判断与行动

Explanation、structured output 与 visualization 都是工具；选择任务所需的最简单 presentation，不要求所有回答输出 HTML、固定 headings 或统一 artifact。保留影响判断的 evidence、limits、material uncertainty 和必要细节；显示更短不能缩减 underlying analysis、search 或 retained information。

Review Contract（Outcome、Evidence、Limits、Decision）只是轻量 candidate approach。目前只有一次 discussion example 与用户“更清楚”的反馈，尚无 quantitative proof；可在需要审阅和决策时试用，不强制每个 response 都套用，也不替代现有 Skill 的任务合同。

## Rights-controlled assets 的 distribution intent

已确认的产品意图是：在有权控制的 Azhou character/assets 范围内，随 official packages 正常使用；单独 extraction、modification 或 redistribution 需另行 permission。这是 intended distribution boundary，**不是新 license，也不是已生效的追溯限制**。它不撤回已有 grants，不覆盖 upstream / third-party assets，也不表示全部代码或素材都可发布。

Code licensing 继续逐 component 遵循实际 [LICENSE](../LICENSE)、[third-party notices](../THIRD_PARTY_NOTICES.md) 和 package notices。落地 asset policy 前须核对具体资产的 ownership、provenance、已有 grants 与发布内容；冲突或缺失项是该资产/发布的 legal implementation blocker，不能通过本页默默替换 license 或改写既有授权。现有根 MIT 与 brand-asset notices 未建立逐资产的新限制，本次不把 policy intent 宣称为已完成 legal implementation；未获授权的 animation code/private assets 保持现有 distribution hold。

## Lightweight community practice

采用 Try → Report → Improve → Verify：尝试一个真实任务，报告可复现问题或实际价值，提出小范围改进，再核对结果与边界。真实 examples、脱敏 failure cases、validation 和 documentation 都是有价值的贡献。不要求提交 private sessions、凭据或个人素材，不建设额外 contribution platform。
