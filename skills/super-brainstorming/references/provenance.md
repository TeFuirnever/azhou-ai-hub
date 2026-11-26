# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Obra-Superpowers-MIT.txt](../../../LICENSES/Obra-Superpowers-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/obra/superpowers` |
| Immutable commit | `22f0b463e7a5e579904dd6211a520321035526f7` (tag `v7.0.2`, annotated tag object `c62ffea8267a70de07583e153544d355b6748a56`, released 2026-11-03) |
| Upstream path | `skills/brainstorming/` |
| Upstream LICENSE SHA-256 | `a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400` |
| License | MIT, copyright 2025 Jesse Vincent |

The upstream release carries no per-skill license file; the repository-root `LICENSE` is the only license record in the upstream tree, and it is vendored byte-for-byte as this package's `LICENSE`. The upstream repository at the locked commit is a plugin ecosystem (installer, sibling skills such as `writing-plans`, plugin manifests); none of that ecosystem is vendored here — see [upstream-compatibility](upstream-compatibility.md) for the checkout-vs-installed split.

## Upstream files at the pin

| Upstream file @pin | SHA-256 |
|---|---|
| `skills/brainstorming/SKILL.md` | `2c9ca71f94886f9ca9f4aef055f7cafb3e1a9bdf3aeebf8f4cb547c69405d207` |
| `skills/brainstorming/builder-check-prompt.md` | `36d51a4723d6f0a3ce5811a0ea3b3a8424f07533947e1355f5d8cb8cce40c55e` |
| `skills/brainstorming/visual-companion.md` | `6ffcb038b53254bd31debaa15e12dcd4ff24bd63d690e0b644ac6396701cf2e2` |
| `skills/brainstorming/scripts/server.cjs` | `763abf96510e0b892a1141397b31aa82ef900cf87ed34dde94bc8782baf4a7ca` |
| `skills/brainstorming/scripts/start-server.sh` | `314dd68dc00e8dd94c7491aca8a5f004c7fddffc161e2b07482f29f48d13659a` |
| `skills/brainstorming/scripts/stop-server.sh` | `0b5ccbbd57f62d3ed88993f7940b5ee0e5c0fc9b21c550c623da4f6292e47daf` |
| `skills/brainstorming/scripts/frame-template.html` | `6a8a4e58bd6a44b904e2e3c57de774481d909204597e1498de53f1b2fecc4c4e` |
| `skills/brainstorming/scripts/helper.js` | `43c6d69954a46ec34a2a262bcc62a9a7e83e839c739f199cb72646d397c686e3` |

`builder-check-prompt.md`, `scripts/start-server.sh`, `scripts/stop-server.sh`, and `scripts/helper.js` are vendored byte-for-byte; their local SHA-256 equals the pin value above and `tests/test_super_brainstorming.py` asserts it. The four delta files (`SKILL.md`, `visual-companion.md`, `scripts/server.cjs`, `scripts/frame-template.html`) record the pin hash above as their upstream drift anchor, and the tests pin local anchor-span digests and the four delta files' full local bytes locally.

## Azhou-maintained adaptation

The upstream instruction body is retained verbatim except for the recorded deltas and the Azhou brand layer; each delta is reproducible against the upstream anchors:

| # | Delta | Upstream anchor | Change |
|---|---|---|---|
| D1 | Neutral frontmatter | upstream frontmatter keys `name`/`description` | `name: super-brainstorming`; description opens `Azhou skill.`, keeps every upstream trigger sentence verbatim, adds the renamed-from compatibility line, a Use-when clause, and the capability carve; `invocation: model-invoked discipline` |
| D2 | Planning handoff neutralized | step 4 of the ordered list; the final paragraph inside `<HARD-GATE>` | "invoke `superpowers:writing-plans` and no other skill" is replaced at both sites with wording adapted per site. The ordered-list step reads "Hand the approved design doc to the planning workflow your human partner chooses; this skill does not chain into a sibling skill."; the `<HARD-GATE>` paragraph reads "hand the approved design document to the planning workflow your human partner chooses, and invoke no implementation skill yourself." |
| D3 | Design-doc location neutralized | `**Where it goes:**` paragraph | `docs/superpowers/specs/…` becomes `docs/specs/…` or the project's own conventions |
| D4 | Branding and telemetry default off | `SUPERPOWERS_BRAND_IMAGE_URL` block and `brandMarkup()` in `scripts/server.cjs`; `<title>` in `scripts/frame-template.html` | the upstream opt-out switches (`SUPERPOWERS_DISABLE_TELEMETRY`, `DISABLE_TELEMETRY`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`) become opt-in (`SUPERPOWERS_ENABLE_TELEMETRY`, `ENABLE_TELEMETRY`); with telemetry off the companion renders no brand markup, fetches no remote logo, and links no upstream repository; the frame title is neutral (`Visual Brainstorming`) |
| D5 | Harness note | `visual-companion.md`, before `**Launching the server by platform:**` | one inserted paragraph declaring the platform recipes examples and the generic start/share/stop loop normative |
| D6 | Builder-check provenance note | the subagent fallback sentence ("Without a subagent tool, read the document as that builder yourself.") | one appended clause requiring the mechanism that performed the check to be named |

| D7 | Companion choice feedback | Choice styles and frame body in `scripts/frame-template.html` | Add a mobile viewport, keep selected cards the same size, follow reduced motion, and expose framed choices to keyboard and assistive technology. Selection still calls the original helper. |

### Accepted upstream-behavior notes

Six review findings reported against the packaged scripts (2026-11-24) sit in bytes identical to the pin — three in files vendored byte-for-byte, the other three in `scripts/server.cjs` regions outside the D4 hunks — and were accepted as upstream-behavior notes rather than patched, so the upstream bytes and their pins stay intact and upstream keeps ownership of the fixes: a launcher loop when a value-taking option has no value, deletion of project-backed sessions under `/tmp` when a running server is stopped, explicit-choice events left out of the feedback file, percent-encoded asset names returning 404, an entry URL that cannot authenticate when `BRAINSTORM_TOKEN` contains `+` or `%`, and a server crash when a running session's `content/` directory is removed. The itemized record and the hub-layer guidance are in [upstream-compatibility](upstream-compatibility.md#accepted-upstream-behavior-notes-at-the-pin) and [setup](setup.md#known-upstream-behavior-at-the-pin).

## Adoption evidence

Adoption follows the execution plan in `.planning/skills-intro-brainstorming-grill-me-20261123/plan.md` (Git-external): the upstream pin was re-verified against the live release list on 2026-11-23 (v7.0.2 still the latest stable release), the byte baseline was re-verified twice (all eight upstream blob SHAs recomputed locally and matched the upstream `contents` API at the pin), and the delta diff of the packaged `SKILL.md` against the upstream file was mechanically confirmed to contain exactly the recorded deltas and the Azhou layer before commit.

## Showcase scene

`assets/skills/super-brainstorming-effect.png` (added 2026-11-23) is the package's skill showcase scene under skill-standard §4. It landed through the governed azhou-scenes local candidate pipeline (2026-11-23, `backend: azhou-gen`, `execution_scope: local_candidate_only`, `article_16_9` mode, final profile tier): Qwen-Image-2.1 edit via the mflux engine adapter with the hash-locked canonical fox reference (SHA-256 `bb86cf0a9e80beee8647aeaae19506eb410d2fc19b4ba93c1ec0e2c4d1e0f8a2`) as the sole generation reference, anchor `04-code-review-rework` recorded observation-only (`used_as_image_gen_reference=false`, SHA-256 `d2c81283d347a6ee9cc7828fd016dc2dc549d21e0be523bd73d9756018816d30`) and mapped to a blueprint-and-approval-gate scene with five recorded variation points, two seeds (20261123/20261124) at 1664x928, 40 steps, each seed carrying an independent preflight/dispatch/engine/postflight receipt chain (`run-postflight.json` valid, asset status HOLD) bound to its CLI execution record. The shipped PNG is the metadata-sanitized copy of the approved seed-20261124 candidate (chunk whitelist keeps only IHDR, IDAT and IEND and strips the pipeline-embedded tEXt metadata, so the shipped file carries no prompt text, no local paths and no runtime identity; candidate SHA-256 `16a3f9d05967b7cf8e606077745846a8f9610e47e3526744358a9059712f1f992`, pixel stream byte-identical, shipped SHA-256 `7a6885b4bdb3f12b4a7b56ab885f6e366a9a4428fb630121927dee14c36da412`), pinned by `tests/test_super_brainstorming.py` together with a chunk walk. The named visual P0 selection was delegated to the session under the maintainer's standing go-ahead (2026-11-23) and compared both candidates; the selection record and the full receipt chain live Git-external in the maintainer candidate library (`super-brainstorming-showcase-20261123/`, `p0-approval-seed20261124.json`), and the formal governed-workspace colour audit remains open. Repository-wide notice: [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/obra/superpowers/22f0b463e7a5e579904dd6211a520321035526f7/skills/brainstorming/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `2c9ca71f94886f9ca9f4aef055f7cafb3e1a9bdf3aeebf8f4cb547c69405d207`.

License copy check against the retained file:

```bash
curl -fsSL https://raw.githubusercontent.com/obra/superpowers/22f0b463e7a5e579904dd6211a520321035526f7/LICENSE \
  | shasum -a 256
```

Expected SHA-256: `a37e0e9697144819e1d965176ac4ae5bc3fa02d11e7812036bbcadf6dafe2400`, byte-identical to [LICENSES/Obra-Superpowers-MIT.txt](../../../LICENSES/Obra-Superpowers-MIT.txt).

## Fidelity classification

Classification: `adapted` — the upstream capability is extended, not merely repackaged: the six recorded deltas change instruction text (planning handoff, design-doc location, builder-check provenance) and default behavior (branding/telemetry opt-in), and the Azhou brand layer is added alongside them, while the upstream instruction body itself is retained verbatim outside the recorded deltas and the Azhou brand layer; the upstream name keeps working as a trigger. Skill-standard §2.3.
