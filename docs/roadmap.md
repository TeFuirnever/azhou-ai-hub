# Roadmap

本页遵循 [Azhou AI Hub principles](principles.md)。项目描述 outcomes，不承诺 release dates。Planned 不等于实现、安装、发布或运行 pilot 的授权；接受进入执行的工作再明确 owner 与 evidence target。

## Next milestone

- **Principles 与现有工作对齐**：确立 Myself first, community-ready 与两个互补 pillars；复用既有工作和验收路径，不重复实现，不开展 full repository audit。
- **Planned — `super-i-have-adhd`**：来源为 [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd)。已形成 [bounded pilot design](specs/super-i-have-adhd-pilot.md)：先对照 upstream instructions、当前 Hub Skills 与 retired Super Caveman 的历史边界，再在一个真实 workflow 比较原始、当前与最小增强。当前只授权 design；没有 Skill implementation、pilot execution、installation 或 publication。它不被预设为 Super Caveman 的 replacement。
- **Existing integrations 继续既有 acceptance tracks**：pstack 沿 [integration contract](integrations.md) 与 [support matrix](support-matrix.md)；Agent Skin 沿既有 tickets 与其实现分支验收，不新建并行实现。Focused Skill pilot 不以所有 integrations 完成为前置条件。

## Current-work reconciliation

Agent Skin 已在本仓库的 [canonical package](../packages/agent-skin/README.md) 实现，当前支持与验收边界以 [support matrix](support-matrix.md) 和该包文档为准。安装状态与实际宿主验收须分别核查；本地构建或 tracker 状态不能替代它们。

2026-10-27 的 tracker handoff 曾报告 #352–358 completed、[#359](https://github.com/TeFuirnever/azhou-ai-hub/issues/359) ready-for-human/open、[#360](https://github.com/TeFuirnever/azhou-ai-hub/issues/360) open，并检查了当时的 `codex/agent-skin-integration` 分支；这些都是历史快照。历史 [local handoff](../evidence/optional-integrations-local-handoff-2026-10-26.md) 只证明当时的输入，不覆盖后续候选或当前安装归属。

## Maintenance decisions

- 按 capability 记录 verified versions、upstream revision 和 known limits；先 review upstream changes，再决定 merge。Bug reports、planned releases 和 known breaking changes 触发相关 revalidation，无 SLA 或全版本支持承诺。
- Azhou asset policy A 已确认为 product intent；逐资产 grants、provenance 与 license consistency 尚须落地核对。保留现有法律授权，冲突或 missing provenance 阻断受影响发布，不把原则批准当成 distribution permission。
- 用 Try → Report → Improve → Verify 接纳真实 examples、脱敏 failure cases、validation 与 docs；可继续为一个可复现问题建立一个 `good first issue`。

## Later

- General Hub production install/uninstall 继续沿对应 package 的 destination/state/uninstall contract 推进；不把一次性 handoff 当成通用 lifecycle。
- Shared character/export logic 只在真实 consumers 需要时考虑；统一 Azhou identity 不要求先建通用 engine。
- 新 Skills 保持独立安装与现有标准；仅在 downloadable releases 需要时生成 SBOM/provenance artifacts。
- Repository Markdown 不足时再考虑 documentation site，repository 继续作为 authority。

通过 [skill request form](https://github.com/TeFuirnever/azhou-ai-hub/issues/new?template=skill-request.yml) 或 [Discussions](https://github.com/TeFuirnever/azhou-ai-hub/discussions) 提出后续建议。
