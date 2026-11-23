# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Mattpocock-Skills-MIT.txt](../../../LICENSES/Mattpocock-Skills-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/mattpocock/skills` |
| Immutable commit | `d1478fcb140db0b93c0c8df17bcfd311844749d0` (tag `v1.3.2`, annotated tag object `85cbec972d7a79c278c793d272f7fc715850fad4`, released 2026-10-29) |
| Upstream path | `skills/productivity/grilling/SKILL.md` |
| Upstream source SHA-256 | `a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2` |
| Upstream LICENSE SHA-256 | `0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5` |
| License | MIT, copyright 2026 Matt Pocock |

The upstream entry is 2077 bytes: a two-key frontmatter (`name`, `description`) and the interview protocol. The last upstream commit touching the path is `7739eaed7f8f3915437a8def198a6d0d7206dbc7` (2026-10-29). The upstream directory also carries `agents/openai.yaml` (interface metadata only, no invocation policy), which is not imported; see [upstream-compatibility](upstream-compatibility.md). The upstream repository has no per-skill license file; the root `LICENSE` is the only license record and is vendored byte-for-byte as this package's `LICENSE`.

## Upstream file at the pin

| Upstream file @pin | SHA-256 |
|---|---|
| `skills/productivity/grilling/SKILL.md` | `a146842ed93ca43d833550fa9adf02e58cb63c83fea9d4b4522995b82242d4e2` |

`LICENSE` is vendored byte-for-byte and `tests/test_super_grilling.py` asserts it. `SKILL.md` is a delta file: it records the pin hash above as its upstream drift anchor, and the tests pin the retained upstream paragraphs and the file's full local bytes.

## Azhou-maintained adaptation

The upstream instruction body is retained verbatim except for one sentence; each delta is reproducible against the upstream anchors:

| # | Delta | Upstream anchor | Change |
|---|---|---|---|
| GL1 | Neutral frontmatter | upstream `name`, `description` | `name: super-grilling`; the description opens `Azhou skill.`, keeps both upstream trigger sentences verbatim, adds the renamed-from compatibility line, a Use-when clause, and the boundary with `super-brainstorming`; `invocation: both` follows the upstream documents, which describe typing `/grilling` and the model reaching for it on its own |
| GL2 | Sub-agent degradation sentence | the final sentence of the "Finding _facts_" paragraph | one appended sentence: on a harness without sub-agents, look the fact up yourself and say that it was not checked from an independent context window |
| GL3 | Azhou brand layer | none | the identity anchor and Brand protocol after the H1 title, and the round-based stage protocol in [brand-layer](brand-layer.md) |
| GL4 | UI metadata not imported | `agents/openai.yaml` | not vendored; recorded in [upstream-compatibility](upstream-compatibility.md) |

## Showcase scene

`assets/skills/super-grilling-effect.png` (added 2026-11-24) is the package's skill showcase scene under skill-standard §4. It landed through the governed azhou-scenes local candidate pipeline (2026-11-24, `backend: azhou-gen`, `execution_scope: local_candidate_only`, `article_16_9` mode, final profile tier): a `Qwen/Qwen-Image-2.1` edit through the `mflux-generate-qwen-2.1-edit` engine with the hash-locked canonical fox reference (SHA-256 `bb86cf0a9e80beee8647aeaae19506eb410d2fc19b4ba93c1ec0e2c4d1e0f8a2`) as the sole generation reference, anchor `06-ai-resume-filter` recorded observation-only (`used_as_image_gen_reference=false`, SHA-256 `393c63b843e44f14ff3defc64ff9e0f314007db0b2c6fb226e79fee6a54d8aad`) and mapped to a design-tree-plan scene with six recorded variation points, two seeds (2026112411 and 2026112413) at 1664x928 and 40 steps, each seed carrying an independent preflight/dispatch/engine/postflight receipt chain (`run-postflight.json` valid, asset status HOLD) bound to its CLI execution record. The two seeds do not share one prompt: after the first showed mirrored digits inside the tree boxes, the prompt for the second dropped the digits, with anchor, label and parameters unchanged. The shipped PNG is the metadata-sanitized copy of the selected seed-2026112413 candidate: a chunk whitelist keeps only IHDR, IDAT and IEND and strips the pipeline-embedded eXIf, iTXt and tEXt metadata, so the shipped file carries no prompt text and no runtime identity (candidate SHA-256 `62f2091411d753acb4567d4d209b9b66693890c9f92da9434b7958b91015fc80`, IHDR and IDAT stream byte-identical, shipped SHA-256 `1675128a0270a7c197beea639f0a218b50c8257ad4892850444b4ab399aa6461`), pinned by `tests/test_super_grilling.py` together with a chunk walk. The visual P0 selection was delegated to the session under the maintainer's standing go-ahead (2026-11-23); both candidates were viewed before the selection. Recorded deviations from the shot list's failure signals: the paw tips carry short toe lines, and one tree box is both scribbled out and circled. The selection record, the receipt chain and the deviation list live Git-external in the maintainer candidate library (`grill-showcase-20261124/`, `p0-approval-super-grilling-seed2026112413.json`), and the formal governed-workspace colour audit remains open. Repository-wide notice: [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Reproducible source check

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

Classification: `adapted`. The upstream interview protocol is kept verbatim and extended, not merely repackaged: one sentence adds a declared fallback for harnesses without sub-agents, and the Azhou brand layer adds the stage protocol and stable receipt. The upstream name keeps working as a trigger. Skill-standard §2.3.
