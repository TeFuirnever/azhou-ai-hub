---
name: super-prose-standard
description: Renamed from prose-standard (the old name still triggers this skill). Use when writing, reviewing, trimming, or auditing prose on current-state surfaces — Markdown docs, SKILL.md bodies, references, READMEs, comments, commit messages — when a cleanup pass must compress without losing facts, when prose reads like a leaked reasoning transcript (dead citations, change narration, PR vantage, review choreography, hedges), or when documentation claims an operation that must be verified by running it.
invocation: model-invoked discipline
---

# Super Prose Standard

**🦊 阿舟 · Super Prose Standard**

> ✂️ 每个事实都活着，才动手删字。

Invocation class: model-invoked discipline, declared in frontmatter; the axis, its semantics and the composition rules are defined once in docs/skill-standard.md §2.2 (spec #126 ID-9) — applicable during ordinary writing and review work without being named, and still directly invocable.

It is guidance, not a script. One package owns two branches of the same craft: the **writing branch** (enough prose to preserve the contract, then remove repetition and decoration) and the **audit branch** (hunting and fixing chain-of-thought leakage). Every branch is disclosed on demand — the entry carries only what both need.

## Brand protocol

Emit this exact display event once:

```text
🦊 阿舟 · Super Prose Standard 启动｜mode=<write|review|audit>｜scope=<surface>
```

Use `✅ 验证通过` only after the scope was read back and every deliberate keep or trim is accounted for. Use `❌ 验证失败` when a check fails or the scope cannot be resolved and `🔒 阿舟暂停这一项` when the requested scope is missing or the request needs precision-critical judgment this skill does not own. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `｜` separators, fields, and values. Raw evidence stays out of receipts unless the user supplied it.

## The complete-proposition rule (both branches)

Before editing a passage, enumerate its propositions. Preserve each relevant actor and action, condition, timing, and ordering, modality (must, may, never), negative guarantee and exception, ownership, side effect, failure mode, and consequence. Remove adjectives, repetition, and narration only when every factual clause survives and the result is clearer. A smaller word count alone is not an improvement. One explanation has one home; essential contract facts may repeat locally, and everything deeper links to its owner.

## Required coverage by location (writing branch)

This is not a one-way shortening pass — add or restore prose when code, types, and structure do not communicate a required contract:

- **Entry documents (SKILL.md, READMEs):** the consumer contract — configuration, semantics, failures, limitations, extension points — plus durable gaps and maintainer traps, not ordinary cleanup inventories.
- **Reference files:** rules, calibration examples, and caveats co-located under one heading; load on demand, never inline what only one branch needs.
- **Comments:** non-obvious contracts or rationale the code cannot express; delete control-flow narration and code restatement.
- **Tests:** only non-obvious test design — why a fixture or indirect observation is necessary; delete walkthroughs.
- **Prompts and visible strings:** wording is behavior; change only with owning behavior evidence.

When documentation claims an operation — a command, default, error, or platform difference — follow [the fact-check procedure](references/fact-check.md): run it, record what you observed, delete what you could not reproduce.

## Chain-of-thought leakage (audit branch)

Leakage is prose whose vantage is the authoring session rather than the repository: it cites artifacts only that session could see, narrates the change instead of the state, or argues with a reviewer who has left. The one test: could a reader at HEAD, with no access to any session transcript, PR thread, or uncommitted draft, resolve every reference and verify every claim? Audit with [the taxonomy](references/cot-leakage.md) (eight classes plus the keep-list of sanctioned near-misses) and [the recall batteries](scripts/recall_batteries.py) as probes — every hit still needs semantic judgment, and every zero-hit result needs a known positive before it proves anything.

## Scope and exclusions

Require an explicit scope; do not infer a repository-wide pass. Exclude runtime state (`.azhou/`, `.omc/`), VCS internals, and synthetic fixture corpora from the audit; fix the owning source before any generated or derivative surface. Fix the owning source before any generated or derivative surface.

## Verification

Read the edited scope back against the code or owning document; confirm every surviving citation resolves at HEAD and every fact-check claim has an observed run behind it. Run the narrow relevant checks and the repository gate when the scope lives in this repository. Report the inspected scope, changes, deliberate keeps, deferred cases, and checks actually run. End with a stable receipt carrying `schema`, `status`, `current truth`, `artifacts/changes`, `verification`, `holds`, `next action`, and `learning signal`. Adapted-material obligations, upstream pins, and the update path live in [provenance.md](references/provenance.md).
