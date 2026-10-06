---
name: ask-azhou
description: One-line router for the Azhou AI Hub skill catalog: describe what you want to do and get a recommendation of the right canonical skill, its mode, and its boundary. MUST trigger for which-skill questions: which skill should I use, which skill handles this, is there a skill for X, 该用哪个 skill, 有没有能做这个的 skill, 帮我挑个 skill, or any routing question over this catalog; it recommends and never invokes another skill on the user's behalf.
invocation: user-invoked orchestrator
---

# Ask Azhou

**🦊 阿舟 · Ask Azhou**

> 🚪 说清你想做什么，我告诉你敲哪扇门。

Invocation class: user-invoked orchestrator, declared in frontmatter; the axis, its semantics and the composition rules are defined once in docs/skill-standard.md §2.2 (spec #126 ID-9) — invoked by name or by an explicit "which skill" request; it recommends and never invokes another skill on the user's behalf.

It is guidance, not a script. This is the hub's front door: fourteen canonical skills, organized by what you are trying to do. Answer with a recommendation (skill, mode, and the boundary that matters), not an invocation.

## Brand protocol

Emit this exact display event once:

```text
🦊 阿舟 · Ask Azhou 启动｜mode=route｜scope=<catalog>
```

Use `✅ 验证通过` only after the recommendation names a real canonical skill whose boundary fits the request. Use `❌ 验证失败` when no canonical skill fits and `🔒 阿舟暂停这一项` when the request is outside this hub's catalog entirely. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `｜` separators, fields, and values. Raw evidence stays out of receipts unless the user supplied it.

## Route by intent

The catalog below is generated from every canonical skill's frontmatter description — the same text a model router sees. Never edit the generated block by hand: change the owning skill's description, then run `python skills/ask-azhou/scripts/generate_routing_index.py` from the checkout root to regenerate; the repository gate fails on parity when the block drifts.

Match the request to a family first, then to the catalog's intent keywords: install, diagnose, or prove the hub itself (发行基建); produce or polish a visible artifact (内容生产力); keep knowledge and quality honest across sessions (工程纪律); long-running experiments; and this skill for routing questions.

<!-- generated-routing-index:begin -->
- `arch-doc` — End-to-end authoring and calibration of an architecture design document from upstream sources. MUST trigger for 写架构设计文档, 架构说明书, ARCH 文档, 软件实现架构说明书, 架构文档补时序图, PlantUML 时序图（架构文档内）, 交叉校准, 回源核对, 上游研读, 上游真源, 最佳实践评审, 架构评审对标, 架构文档模板, PRD 模板, 产品需求文档模板, 功能详细设计模板, 校准架构文档, 质量场景卡, or whenever a repository needs a software-implementation-architecture document drafted, calibrated against upstream design docs, or reviewed against industry best practices. Distilled from the MCC ARCH-2026-001 authoring pipeline.
- `ask-azhou` — One-line router for the Azhou AI Hub skill catalog: describe what you want to do and get a recommendation of the right canonical skill, its mode, and its boundary. MUST trigger for which-skill questions: which skill should I use, which skill handles this, is there a skill for X, 该用哪个 skill, 有没有能做这个的 skill, 帮我挑个 skill, or any routing question over this catalog; it recommends and never invokes another skill on the user's behalf.
- `autoresearch` — Wrap Karpathy's autoresearch environment so an agent can run, resume, and report automatic nanochat training experiments inside a user-owned pinned checkout. Requires an NVIDIA GPU and uv; vendors no upstream bytes. Use when the user asks to run or check autoresearch experiments; also for 跑 nanochat 训练实验.
- `azhou-doctor` — Diagnose Azhou AI Hub checkout, package, explicit install-target, or Treehouse lease health without mutation. Use for health checks, broken installs, environment diagnostics, or support verification; also for "is my checkout healthy", "what broke", 仓库体检, 哪里坏了, or a stuck-lease question.
- `azhou-info` — Report provable Azhou AI Hub checkout information or revision facts. Use for project info, installable repository inventory, support facts, version, commit, branch, or dirty-state questions; also for 这是什么版本, 现在装了哪些 skill, or "what revision is this checkout on".
- `azhou-setup` — Plan and explicitly apply Azhou AI Hub skill installation or receipt-owned repair, migration, and uninstall. Use for checkout-assisted setup and managed lifecycle operations with an exact target root; also for 帮我安装这个 skill, 卸载或迁移 skill, or "set this hub up".
- `azhou-verify` — Run and report the authoritative Azhou AI Hub repository verification gate. Use before completion, handoff, commit, pull request, release, or when full-codebase evidence is requested; also for 跑一遍完整门禁, 交付前验证, or "prove it passes before I claim done".
- `eli5` — Explain a topic like I'm 5 with one HTML artifact of big pictures and few words. MUST trigger for /eli5 <topic>, explain like I'm 5, ELI5, a dead-simple picture explainer, 给我讲明白, 用大白话讲, 讲给零基础的人, 通俗易懂地解释, or any request to make a hard topic click for a total beginner. Precision-critical asks (spec review, security analysis, migration plans, numerical or contractual claims) stay ordinary work and never degrade into eli5.
- `excalidraw-diagram` — Build or edit accurate, editable Excalidraw scenes; render the real scene, inspect the image, run deterministic layout/style checks, and deliver source plus requested exports. Use for workflows, architectures, sequences, data flows, concept maps, or existing .excalidraw files; also for 画个架构图, 画流程图, 画时序图, or "draw a diagram of this". Supports native JSON, offline Mermaid/SVG conversion, official component libraries, CJK-safe SVG/PNG export, and optional interactive preview.
- `session-insights` — Analyze local agent session stores into fact-bound usage insight reports — session counts, active days, hour/project distribution, tool ranking, friction signals. Use when the user asks how they actually use their coding agent, wants a weekly report, or asks to be roasted on real numbers; also for 我的 agent 使用报告, 这周用得怎么样, or "which tools do I actually use"; read-only, aggregates only, raw transcripts never leave the machine.
- `super-caveman` — Enhanced Caveman skill that combines the original terse-mode core, six companion routes, and the complete pinned i-have-adhd output-behavior contract in one installable package. Use for "super caveman", "caveman mode", "be brief", token efficiency, /super-caveman, /caveman, /cavecrew, /caveman-commit, /caveman-review, /caveman-compress, /caveman-help, /caveman-stats, commit-message requests, concise PR review, compact delegation, prose compression, or exact usage statistics.
- `super-lavish` — Renamed from lavish (the old name still triggers this skill). Turn complex or visual agent responses into rich, reviewable HTML artifacts that users can annotate and send feedback on through the Lavish Editor CLI, and relay a PRD, RFC, design spec, or technical plan with comments, selected-text annotations, feedback disposition, and next-owner state inside one portable HTML file. Use for visual artifacts, HTML explainers, interactive prototypes, review surfaces, product or technical plans, team spec review or transfer, comparisons, diagrams, tables, code views, reports, slides, or browser-based feedback loops; also for 把这个结果做成可审阅的 HTML.
- `super-llm-wiki` — Renamed from llm-wiki (the old name still triggers this skill). Build, query, lint, migrate, and maintain a private project Markdown wiki when verified architecture, decisions, debugging facts, or conventions must persist across sessions. Also for 记到 wiki, 把这个决定存下来, or "save this for future sessions". Do not use it for global memory, ephemeral scratch notes, secrets, or unreviewed transcripts.
- `super-repo-pedant` — Renamed from repo-pedant (the old name still triggers this skill). Reconcile repository knowledge at explicit task close. MUST trigger for sync up, tidy or clean up docs, update memory, /sync, /neat, /repo-pedant, 同步一下, 整理文档, 整理一下, 更新记忆, 梳理一下, 收尾, 这个阶段做完了, 新人能直接上手, stale docs, conflicting memories, clean handoff, or bare tidy/整理 in development context, 检查项目技术债务, 仓库健康检查, repo health check. An audit phrasing invites a repository-level review; a request scoped to a single file or task stays ordinary work. Inferred completion only reminds; ordinary implementation that merely mentions or edits this skill does not authorize closeout.
<!-- generated-routing-index:end -->

## Boundaries

- Recommendation only: name the skill and its mode; the user stays in control of what runs.
- Catalog edges: questions about mattpocock-skills workflows (tdd, grilling, specs) belong to the locally installed `ask-matt`, not this map — point there instead of duplicating it.
- No request fits everything: when no canonical skill owns the intent, say so plainly, name the nearest boundary, and record the miss (see Unrouted telemetry).

## Unrouted telemetry

A routing miss is evidence. When no canonical skill fits — the `❌ 验证失败` or `🔒 阿舟暂停这一项` outcome — record it once from the working checkout:

```bash
python skills/ask-azhou/scripts/record_unrouted.py --prompt "<the user's request as asked>"
```

Quote the request through `--stdin` when shell quoting or history is a concern. The store is `.azhou/ask-azhou/unrouted-telemetry.json` (git-ignored runtime state): per-request SHA-256 hashes with counts and day stamps only — the raw text is never written, so it cannot leak into receipts, reports, or Git. `--summary` prints the aggregate; accumulated misses are trigger-candidate evidence under the same paired positive/negative standard as the trigger-phrase inventory.

## Verification

The routing catalog is generated from the canonical skills manifest, so it cannot go stale silently: adding, renaming, or re-describing a skill requires regenerating this file, and the router-coverage plus generated-index parity checks in `scripts/check_repository.py` fail closed otherwise (removal is caught by discovery parity). End with a stable receipt carrying `schema`, `status`, `current truth`, `artifacts/changes`, `verification`, `holds`, `next action`, and `learning signal`; `artifacts` is empty for a routing answer. The router-pattern source pin and update path live in [provenance.md](references/provenance.md).
