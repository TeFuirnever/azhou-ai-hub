---
name: ask-azhou
description: One-line router for the Azhou AI Hub skill catalog: describe what you want to do and get a recommendation of the right canonical skill, its mode, and its boundary.
invocation: user-invoked orchestrator
---

# Ask Azhou

**🦊 阿舟 · Ask Azhou**

> 🚪 说清你想做什么，我告诉你敲哪扇门。

Invocation class: user-invoked orchestrator, declared in frontmatter; the axis, its semantics and the composition rules are defined once in docs/skill-standard.md §2.2 (spec #126 ID-9) — invoked by name or by an explicit "which skill" request; it recommends and never invokes another skill on the user's behalf.

It is guidance, not a script. This is the hub's front door: sixteen canonical skills, organized by what you are trying to do. Answer with a recommendation (skill, mode, and the boundary that matters), not an invocation.

## Brand protocol

Emit this exact display event once:

```text
🦊 阿舟 · Ask Azhou 启动｜mode=route｜scope=<catalog>
```

Use `✅ 验证通过` only after the recommendation names a real canonical skill whose boundary fits the request. Use `❌ 验证失败` when no canonical skill fits and `🔒 阿舟暂停这一项` when the request is outside this hub's catalog entirely. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `｜` separators, fields, and values. Raw evidence stays out of receipts unless the user supplied it.

## Route by intent

Ask which family the request belongs to, then the branch question.

### Install, diagnose, or prove the hub itself (发行基建)

- "Set this hub up / repair a broken install / migrate or uninstall a skill" → `azhou-setup` — plan first, apply the exact reviewed plan.
- "Is my checkout healthy / what broke / is a lease stuck?" → `azhou-doctor` — read-only diagnosis, no mutation.
- "What version / commit / branch / installable inventory is this?" → `azhou-info` — only provable repository facts.
- "Prove this repository state passes its gate before I claim done" → `azhou-verify` — the full authoritative gate, exit code and all.

### Produce or polish a visible artifact (内容生产力)

- "Explain this to someone who knows nothing, with pictures" → `eli5` — one self-contained HTML, big pictures, few words; refuses precision-critical asks.
- "Draw an accurate, editable diagram (architecture, flow, sequence)" → `excalidraw-diagram` — real render, deterministic style and layout gates.
- "Turn this complex result into a rich, reviewable HTML artifact" → `super-lavish` — artifact, relay, review, export, or share mode.
- "Make my agent's replies terse / action-first / commit-message-ready" → `super-caveman` — output-behavior modes, explicit enable/disable.
- "Write an architecture design document from upstream sources" → `arch-doc` — end-to-end authoring with calibration and review gates.

### Keep knowledge and quality honest across sessions (工程纪律)

- "Persist this verified decision / debug fact / convention for future sessions" → `super-llm-wiki` — private local store; decisions carry a lifecycle and archived pages are tamper-evident.
- "Reconcile docs, rules, and memory at task close" → `super-repo-pedant` — the closeout protocol with inventory proof.
- "How am I actually using my agent / give me a usage report from my local session history" → `session-insights` — fact-bound aggregate reports from local session stores (Claude Code and Codex adapters; zcode fails closed — no plaintext transcript store); it analyzes local stores only, never monitors, never sends anything out.
- "Which skill for this?" → this skill, `ask-azhou`.

### Long-running experiments

- "Run, resume, or report nanochat training experiments in my pinned checkout" → `autoresearch` — user-owned environment, explicit boundaries.

## Boundaries

- Recommendation only: name the skill and its mode; the user stays in control of what runs.
- Catalog edges: questions about mattpocock-skills workflows (tdd, grilling, specs) belong to the locally installed `ask-matt`, not this map — point there instead of duplicating it.
- No request fits everything: when no canonical skill owns the intent, say so plainly and name the nearest boundary.

## Verification

The routing map must name every canonical skill; the repository gate enforces that parity (add or rename a skill without updating this map and the gate goes red (removal is caught by discovery parity)). End with a stable receipt carrying `schema`, `status`, `current truth`, `artifacts/changes`, `verification`, `holds`, `next action`, and `learning signal`; `artifacts` is empty for a routing answer. The router-pattern source pin and update path live in [provenance.md](references/provenance.md).
