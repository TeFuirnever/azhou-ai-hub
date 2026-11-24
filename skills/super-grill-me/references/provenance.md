# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Mattpocock-Skills-MIT.txt](../../../LICENSES/Mattpocock-Skills-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/mattpocock/skills` |
| Immutable commit | `d1478fcb140db0b93c0c8df17bcfd311844749d0` (tag `v1.3.2`, annotated tag object `85cbec972d7a79c278c793d272f7fc715850fad4`, released 2026-10-29) |
| Upstream paths | `skills/productivity/grill-me/SKILL.md` and `skills/productivity/grilling/SKILL.md` |
| Upstream grill-me SHA-256 | `caaf8b8de1684f96e26b28f3c29189db5c89cce4b73e1c93d86164f66ef88637` |
| Upstream grilling SHA-256 | `a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2` |
| Upstream LICENSE SHA-256 | `0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5` |
| License | MIT, copyright 2026 Matt Pocock |

Upstream ships two entries. `grill-me` is 157 bytes, a three-key frontmatter (`name`, `description`, `disable-model-invocation: true`) and one body line, `Call the Skill tool with "grilling".`. `grilling` is 2077 bytes, a two-key frontmatter and the interview protocol. The last upstream commits touching the paths are `fcf0071560d32913c9d4f820e0d7ca467c881619` for grill-me (2026-08-15) and `7739eaed7f8f3915437a8def198a6d0d7206dbc7` for grilling (2026-10-29). The upstream documents state the pairing directly (`docs/productivity/grilling.md` at the pin): "`grill-me` is a one-line skill whose whole body is "run a `/grilling` session", so it needs this skill installed too."

This package carries both entries as one package. skill-standard §2 does not allow a package to depend on a sibling skill directory, so the upstream forwarder and the protocol it forwards to are merged instead of landing as two packages, one depending on the other. The interview protocol therefore has one copy in this repository.

Both upstream directories also carry an `agents/openai.yaml`, which is not imported. See [upstream-compatibility](upstream-compatibility.md). The upstream repository has no per-skill license file. The root `LICENSE` is the only license record and is vendored byte-for-byte as this package's `LICENSE`.

## Azhou-maintained adaptation

The upstream grilling instruction body is retained verbatim except for one sentence. Each delta is reproducible against the upstream anchors:

| # | Delta | Upstream anchor | Change |
|---|---|---|---|
| M1 | Neutral frontmatter for both entries | upstream `name`, `description` of both entries; `disable-model-invocation` on grill-me | `name: super-grill-me`; the description opens `Azhou skill.`, keeps both upstream trigger sentences verbatim, adds a renamed-from line for both names, a Use-when clause, and the boundary with `super-brainstorming`; `invocation: both` follows the upstream documents, which describe a reader who types `/grill-me` or `/grilling` and a model that reaches for grilling on its own |
| M2 | Entry and protocol in one package | the one body line of grill-me | the upstream forwarder is not reproduced; this package carries the interview itself, so nothing depends on a sibling directory |
| M3 | Sub-agent degradation sentence | the final sentence of the "Finding _facts_" paragraph | one appended sentence: on a harness without sub-agents, look the fact up yourself and say that it was not checked from an independent context window |
| M4 | Azhou brand layer | none | the identity anchor and Brand protocol after the H1 title, one hub-authored paragraph for the nothing-named hold, and the round-based stage protocol in [brand-layer](brand-layer.md) |
| M5 | UI metadata not imported | both `agents/openai.yaml` files | not vendored; recorded in [upstream-compatibility](upstream-compatibility.md) |

## Showcase scene

`assets/skills/super-grill-me-effect.png` (added 2026-11-24) is the package's skill showcase scene under skill-standard §4. It landed through the governed azhou-scenes local candidate pipeline (2026-11-24, `backend: azhou-gen`, `execution_scope: local_candidate_only`, `article_16_9` mode, final profile tier): a `Qwen/Qwen-Image-2.1` edit through the `mflux-generate-qwen-2.1-edit` engine with the hash-locked canonical fox reference (SHA-256 `bb86cf0a9e80beee8647aeaae19506eb410d2fc19b4ba93c1ec0e2c4d1e0f8a2`) as the sole generation reference, anchor `06-ai-resume-filter` recorded observation-only (`used_as_image_gen_reference=false`, SHA-256 `393c63b843e44f14ff3defc64ff9e0f314007db0b2c6fb226e79fee6a54d8aad`) and mapped to a design-tree-plan scene with six recorded variation points, two seeds (2026112411 and 2026112413) at 1664x928 and 40 steps, each seed carrying an independent preflight/dispatch/engine/postflight receipt chain (`run-postflight.json` valid, asset status HOLD) bound to its CLI execution record. The two seeds do not share one prompt. The first showed mirrored digits inside the tree boxes, so the prompt for the second dropped the digits, with anchor, label and parameters unchanged.

The shipped PNG is the metadata-sanitized copy of the selected seed-2026112413 candidate. A chunk whitelist keeps only IHDR, IDAT and IEND and strips the pipeline-embedded eXIf, iTXt and tEXt metadata, so the shipped file carries no prompt text and no runtime identity. The IHDR and the IDAT stream are byte-identical to the candidate (candidate SHA-256 `62f2091411d753acb4567d4d209b9b66693890c9f92da9434b7958b91015fc80`, shipped SHA-256 `1675128a0270a7c197beea639f0a218b50c8257ad4892850444b4ab399aa6461`), and `tests/test_super_grill_me.py` pins the shipped digest together with a chunk walk.

The visual P0 selection was delegated to the session under the maintainer's standing go-ahead (2026-11-23). Both candidates were viewed before the selection. The scene was generated for the planned `super-grilling` package, and the session assigned it to this merged package on 2026-11-24. The bell scene generated for the planned forwarder package is not shipped. Recorded deviations from the shot list's failure signals: the paw tips carry short toe lines, and one tree box is both scribbled out and circled. The selection record, the receipt chain and the deviation list live Git-external in the maintainer candidate library (`grill-showcase-20261124/`, `p0-approval-super-grill-me-seed2026112413.json`), and the formal governed-workspace colour audit remains open. Repository-wide notice: [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/mattpocock/skills/d1478fcb140db0b93c0c8df17bcfd311844749d0/skills/productivity/grill-me/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `caaf8b8de1684f96e26b28f3c29189db5c89cce4b73e1c93d86164f66ef88637`.

```bash
curl -fsSL https://raw.githubusercontent.com/mattpocock/skills/d1478fcb140db0b93c0c8df17bcfd311844749d0/skills/productivity/grilling/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2`.

License copy check against the retained file:

```bash
curl -fsSL https://raw.githubusercontent.com/mattpocock/skills/d1478fcb140db0b93c0c8df17bcfd311844749d0/LICENSE \
  | shasum -a 256
```

Expected SHA-256: `0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5`, byte-identical to [LICENSES/Mattpocock-Skills-MIT.txt](../../../LICENSES/Mattpocock-Skills-MIT.txt).

## Fidelity classification

Classification: `adapted`. The package keeps the upstream interview protocol verbatim and extends it. The upstream forwarder entry and the protocol are merged into one package, one sentence adds a declared fallback for harnesses without sub-agents, and the Azhou brand layer adds the stage protocol and stable receipt. Both upstream names keep working as triggers. Skill-standard §2.3.
