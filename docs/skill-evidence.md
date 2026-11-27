# Skill verification

Use the [support matrix](support-matrix.md) for host-specific discovery, invocation and integrations. The entries below describe what each package verifies.

| Skill | Verification basis |
|---|---|
| [Azhou Info](../skills/super-azhou-info/SKILL.md) | Stable `info`/`version` JSON contracts; read-only checks. |
| [Azhou Doctor](../skills/super-azhou-doctor/SKILL.md) | Read-only doctor contract; Treehouse lease smoke contract (subprocess-boundary unit tests); fail-closed. |
| [Azhou Setup](../skills/super-azhou-setup/SKILL.md) | Dry-run-first setup; mutation lock, identity guards and rollback regressions. |
| [Azhou Verify](../skills/super-azhou-verify/SKILL.md) | Repository policy, retired-surface reverse scan, unit, package manifest/lifecycle, benchmark-integrity, wiring-integrity and whitespace gates. |
| [Super Repo Pedant](../skills/super-repo-pedant/SKILL.md) | All 28 capabilities of the upstream `neat-freak` baseline ([Khazix-Skills](../THIRD_PARTY_NOTICES.md#super-repo-pedant-baseline)) accounted; 4 registered behavior cases. |
| [Excalidraw Diagram](../skills/super-excalidraw-diagram/SKILL.md) | 5 frozen benchmark cases; deterministic style/scene/overlap gates. |
| [Eli5](../skills/super-eli5/SKILL.md) | Upstream behavior sentence pinned (SHA-256); no behavior benchmark. |
| [Ask Azhou](../skills/super-ask-azhou/SKILL.md) | Routing-map parity gate with a negative control. |
| [Arch Doc](../skills/super-arch-doc/SKILL.md) | Deterministic scaffold, closing-gate checker and golden case. |
| [Session Insights](../skills/super-session-insights/SKILL.md) | Synthetic-store wiring suite; reflection contract checks. |
| [ASD-STE100](../skills/super-asd-ste100/SKILL.md) | Pinned upstream (SHA-256); deterministic `ste-lint.py` gate. |
| [Archify](../skills/super-archify/SKILL.md) | Upstream v3.3.0 sync (git tag + SHA-256; Apache-2.0 with retained MIT grants; proactive explainer default); SVG style validation and finalize/validate gates. |
| [Lavish](../skills/super-lavish/SKILL.md) | Locked upstream release (SHA-256 + npm pins); integrity tests. |
| [Imagegen](../skills/super-imagegen/SKILL.md) | Contract-only package; baseline hashes pinned; fails closed. |
| [Rederive](../skills/super-rederive/SKILL.md) | Pinned upstream (SHA-256); exploratory observation only. |
| [i-have-adhd](../skills/super-i-have-adhd/SKILL.md) | Frozen upstream (SHA-256); verbatim body; integrity tests. |
| [Gh Axi](../skills/super-gh-axi/SKILL.md) | Locked upstream release (SHA-256 + npm pins); integrity tests. |
| [Diagram Design](../skills/super-diagram-design/SKILL.md) | Vendored upstream (commit pin + per-file SHA-256); packaged `self_check.py` gate. |
| [Frontend Design](../skills/super-frontend-design/SKILL.md) | Faithfully adopted from anthropics/skills at the pinned commit with the upstream guidance body preserved verbatim, the Apache-2.0 license vendored byte-identical, and SHA-256 integrity tests. No behavior benchmark yet. |
| [Brainstorming](../skills/super-brainstorming/SKILL.md) | Adapted from obra/superpowers at the pinned tag with six recorded deltas, per-file upstream SHA-256 anchors, and integrity tests. No behavior benchmark yet. |
| [Grill Me](../skills/super-grill-me/SKILL.md) | Adapted from mattpocock/skills at the pinned tag; upstream trigger sentences kept verbatim; instruction body verbatim outside one sentence; SHA-256 integrity tests. No behavior benchmark yet. [Claude Code host check](../evidence/super-grill-me-host-check-claude-2026-11-24.md). |

See the [evaluation contract](eval-case-contract.md), [per-skill platform view](skill-platform-view.md), and [third-party notices](../THIRD_PARTY_NOTICES.md).
