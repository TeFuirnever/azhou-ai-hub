# Provenance and compatibility

Classification: `faithful`

Upstream: [anthropics/skills](https://github.com/anthropics/skills), path `skills/frontend-design`, immutable commit [`41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f`](https://github.com/anthropics/skills/commit/41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f), Apache-2.0. The pinned commit is the latest commit that touched the path (2026-09-03, "Update frontend-design skill to avoid generic design defaults (#1713)"); at adoption the branch HEAD carried the same blobs as the pin, so the pin is both the path tip and a content match. The classification follows Skill-standard §2.3: the upstream capability body is preserved verbatim in the package `SKILL.md`, and every local addition (neutral frontmatter, the Azhou identity anchor, the brand protocol, boundaries, the receipt, and these provenance records) is wrapper-layer work that never counts as adapted.

The upstream directory carries no copyright header, no NOTICE file, and no repository-level license; the per-directory `LICENSE.txt` (the bare Apache-2.0 text, ending at "END OF TERMS AND CONDITIONS" with no appendix and no copyright placeholder line) is the only upstream notice. The attribution anchor is therefore the source URL plus the pinned commit, recorded above and in THIRD_PARTY_NOTICES.md. The complete license is vendored byte-identical as [LICENSE.txt](../LICENSE.txt) and retained as [LICENSES/Anthropic-Skills-Apache-2.0.txt](../../../LICENSES/Anthropic-Skills-Apache-2.0.txt).

| File | Upstream SHA-256 | Local status |
|---|---|---|
| `SKILL.md` | `d91970639e9f5c37682ac7ab60094d35f1c7c1f38d731bd56396563aee10c1d3` | body preserved verbatim below the wrapper; frontmatter normalized to the hub three-key contract (the upstream host-specific `license:` key is dropped; the license file itself is retained) |
| `LICENSE.txt` | `0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594` | vendored byte-identical as the package `LICENSE.txt` and as the `LICENSES/` copy |

## Import-review scope record

The 2026-11-18 anthropics/skills import review ([docs/research/2026-11-18-anthropics-skills-import-review.md](../../../docs/research/2026-11-18-anthropics-skills-import-review.md)) explicitly excluded `frontend-design` from the sourcing scope of its adoption units, so this package is an independent adoption outside that review's scope. The review's R2 document-format batch was subsequently retired rather than kept in distribution, and the review's R1 attribution ruling was made for the document-format adoption units: the attribution wording used in THIRD_PARTY_NOTICES.md for this package borrows that ruling's condition-2 template because no prior ruling exists for this package, and its effect rests on the maintainer approval of the adoption PR that introduced this package.

## Reproducible source check

```bash
git clone https://github.com/anthropics/skills /tmp/anthropics-skills-provenance-check
git -C /tmp/anthropics-skills-provenance-check checkout 41bbe19d1a1a7eaab5e7bb9050a417e5c6cffc8f
shasum -a 256 /tmp/anthropics-skills-provenance-check/skills/frontend-design/SKILL.md /tmp/anthropics-skills-provenance-check/skills/frontend-design/LICENSE.txt
```

The two digests must match the table above. A changed digest means the source moved: follow skill-standard §1.2, review the upstream diff, and re-pin the commit, the provenance digests and the package test pins together in one commit. Any byte change to the vendored license requires both the provenance digest and the package test pin to be recomputed in that same commit.

## Showcase record

The showcase scene landed through the governed azhou-scenes local candidate pipeline (2026-11-22, `backend: azhou-gen`, `execution_scope: local_candidate_only`, `article_16_9` mode, final profile tier): Qwen-Image-2.1 edit via the mflux engine adapter with the hash-locked canonical fox reference (SHA-256 `bb86cf0a9e80beee8647aeaae19506eb410d2fc19b4ba93c1ec0e2c4d1e0f8a2`) as the sole generation reference via the declared frozen snapshot, anchor `03-production-alert` recorded observation-only (`used_as_image_gen_reference=false`) and mapped to a layout-assembly-rail scene with no reuse of the earlier showcase compositions, two seeds (31/33) at 1664x960, 40 steps, each seed carrying an independent preflight/dispatch/engine/postflight receipt chain bound to its CLI execution record. The approved candidate is `super-frontend-design-s33.png` (run `azhou-20261122T101649Z-super-frontend-design-showcase-s33`, local run `794e040b2de546d491a53f164b36313f`, SHA-256 `e276ea480a95d43461ee274cbdcb4c3380bd4f50f56530a3beef0eb1c4ecf2f0`). The maintainer chose the local azhou-gen backend for the visual pass and delegated the named visual P0 selection to the session ("up to you, go", 2026-11-22); the selection record with both candidates' comparison lives Git-external in the maintainer candidate library as `p0-approval-s33.json` alongside the full receipt chain.

The shipped `assets/skills/super-frontend-design-effect.png` is the metadata-sanitized copy of that candidate (chunk whitelist IHDR/IDAT/IEND; iTXt/tEXt/eXIf stripped; the IDAT stream byte-identical), SHA-256 `9e4e41a6712bd7f7582e12c928ddcd6f11da24cb9ff4772b50be93f901430dd9`, pinned by `tests/test_super_frontend_design.py`. With this image every non-Foundation canonical skill carries an `assets/skills/<name>-effect.png` except `super-diagram-design`, whose showcase scene is [deferred at its adoption](../../super-diagram-design/references/provenance.md#showcase-deferral).

Two surfaces remain at their landed state and stay owned by the maintainer: the README hero/banner digit redraw (pixels and alt texts say seventeen; the redraw pipeline is Git-external on the maintainer side and was not located on this machine), and the repo-wide README showcase sections (removed for every skill by the #548 storefront rewrite, so no per-skill section is reintroduced for this package alone). The tree-bound count claims say 22 and are test-pinned; the pixel-bound hero/banner/alt/site surfaces move to 22 together in the maintainer redraw.
