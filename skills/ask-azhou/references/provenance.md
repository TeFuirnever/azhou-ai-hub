# Provenance

## Source of the adapted pattern

- Upstream: https://github.com/mattpocock/skills (MIT License)
- Immutable pin: commit `3cca18b368ae95cdbdebbff572ccafa662551015` (2026-09-05 HEAD)
- Source path: `skills/engineering/ask-matt/SKILL.md` — the hand-written prose flow-map router (no manifest, no scan, model judgment over branch questions) and the user-invoked orchestrator discipline.

## Adaptation boundary

- The pattern is borrowed, not the file: no upstream text is copied. This package's map is written for this hub's catalog and organized by intent across the three families (hub infrastructure, content production, engineering discipline) plus a standalone long-running-experiments branch.
- The upstream's hand-maintained currency weakness is deliberately closed here, structurally: the routing catalog block in `SKILL.md` is generated from every canonical `skills/*/SKILL.md` frontmatter description by this package's `scripts/generate_routing_index.py`, and the repository gate (`scripts/check_repository.py`) fails on both router coverage and generated-index parity when a skill is added, removed, renamed, or re-described without regenerating.
- The upstream `disable-model-invocation` frontmatter key is not used: this repository's package contract pins frontmatter to exactly `name` and `description`; the invocation class is declared in the entry body, and the formal axis belongs to the skill-standard proposal (spec #126 ID-9).
- No model-specific package identity is shipped. The description originally shipped trigger-list-free, per the upstream user-invoked discipline; on 2026-10-06 (u4, after cross-harness execution evidence showed zero router invocations across 137 catalog enumerations and routing questions answered by bare models) that stance was reversed for the router itself: which-skill trigger phrases now live in the description, while the package identity stays harness-neutral.
- MIT notice: the upstream repository is MIT-licensed; only the pattern (flow-map form, recommendation-only contract, composability rule) is retained, which the upstream license permits with attribution recorded here.

## Reproducible update path

1. Diff the pinned upstream router against the current pin: `git -C <mattpocock-skills-checkout> show 3cca18b368ae95cdbdebbff572ccafa662551015:skills/engineering/ask-matt/SKILL.md`.
2. Map structural changes (new routing conventions, composability rule updates) onto this package; keep the catalog map generated from this repository's own skill set.
3. Update the pin above only after the mapped change lands, in the same commit.

## Fidelity classification

Classification: `original` — no upstream skill lineage: the ask-matt pattern (pinned commit `3cca18b368ae95cdbdebbff572ccafa662551015`, MIT) is borrowed with zero upstream bytes copied, and the router map is written for this hub's own catalog. Skill-standard §2.3.
