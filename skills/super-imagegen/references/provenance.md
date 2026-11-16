# Provenance and local boundary

This package is a **contract-only canonical layer** over a proprietary local capability. There is no upstream skill to import, and nothing from the private runtime is redistributed through this repository.

## Private source, not an upstream

| Field | Recorded value |
|---|---|
| Classification basis | no upstream skill lineage; Azhou-authored capability, package wraps an unmodified external runtime |
| Runtime capability | the machine's already-installed private `azhou-imagegen` skill (Azhou proprietary) |
| Runtime role | runtime dependency only — not an upstream, not vendored, not redistributed |
| Baseline snapshot (2026-11-16, maintainer host) | installed `SKILL.md` SHA-256 `0dcca3866f5ec6910040d639f92fc2b01785f6c3baeb9f6ec9f43e16d8b1a92d` |
| Baseline snapshot (2026-11-16, maintainer host) | installed `azhou_gen.py` CLI entry SHA-256 `681ea164c306d8ee3a0500e279485c5a256eb6c26ef3d565a9e294b405dad5d0` |
| Baseline snapshot (2026-11-16, maintainer host) | installed `LICENSE` SHA-256 `b2e167d36a6ccbdb21c49dd0bdad6449f24bbb6988a15629b3df11915a311b03` |
| Private license | Proprietary; see the installed `LICENSE` and `NOTICE.md` in the authorized environment |

The baseline hashes register the private-install snapshot this contract was written against, so a later drift between the contract and the installed reality is detectable; they are an observation pin, not a redistribution, and the private files themselves never enter this repository. The runtime dependency is located and verified at run time per [setup](setup.md); the exact model components, weights, LoRAs, masters and reference assets of the private environment are out of scope here by design.

## What this package carries — and what it never carries

The package carries only: the neutral frontmatter contract, the orchestration workflow (routing, doctor gate, runtime lock, execution tracking, receipt handoff), the fail-closed setup reference, the Azhou interaction layer, and this provenance record. It never carries: generation code, prompt bodies or templates, master paths or master content, character or reference assets, receipt store contents, model weights, or any private configuration. The private runtime's own third-party model licenses are handled inside the authorized environment per its `NOTICE.md`; this package adds no rights to them.

The private capability is **Azhou proprietary**: source, prompts, masters, receipts and character assets stay in the authorized environment; the public package and public outputs do not grant any right to the private implementation or to Azhou character assets. The private runtime's current use decision (recorded 2026-10-03) limits its local entry to non-commercial research and evaluation; commercial or public use requires a separate rights check. This boundary statement documents the limit — it does not grant, widen, or transfer it.

## Reproducible baseline check

Run inside the authorized environment to confirm the registered baseline still describes the installed reality (re-register fresh hashes here when they intentionally change):

```bash
shasum -a 256 ~/.agents/skills/azhou-imagegen/SKILL.md \
  ~/.agents/skills/azhou-imagegen/scripts/azhou_gen.py \
  ~/.agents/skills/azhou-imagegen/LICENSE
```

Expected values on the registered snapshot are the three SHA-256 hashes in the table above. A mismatch means the private install moved: re-read its `--help` and doctor surface, reconcile this contract in one reviewed change, and update the pins — never stretch the old contract text over a changed runtime.

## Fidelity classification

Classification: `original` — no upstream skill lineage; Azhou-authored capability and package bytes. The package wraps an unmodified external runtime (the installed private skill) without changing its behavior, which skill-standard §2.3 counts as `original`, and zero private bytes are vendored. Skill-standard §2.3.
