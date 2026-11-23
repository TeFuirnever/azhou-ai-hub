# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Mattpocock-Skills-MIT.txt](../../../LICENSES/Mattpocock-Skills-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/mattpocock/skills` |
| Immutable commit | `d1478fcb140db0b93c0c8df17bcfd311844749d0` (tag `v1.3.2`, annotated tag object `85cbec972d7a79c278c793d272f7fc715850fad4`, released 2026-10-29) |
| Upstream path | `skills/productivity/grill-me/SKILL.md` |
| Upstream source SHA-256 | `caaf8b8de1684f96e26b28f3c29189db5c89cce4b73e1c93d86164f66ef88637` |
| Upstream LICENSE SHA-256 | `0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5` |
| License | MIT, copyright 2026 Matt Pocock |

The upstream entry is 157 bytes: a three-key frontmatter (`name`, `description`, `disable-model-invocation: true`) and one body line, `Call the Skill tool with "grilling".` The last upstream commit touching the path is `fcf0071560d32913c9d4f820e0d7ca467c881619` (2026-08-15). The upstream directory also carries `agents/openai.yaml`, which is not imported; see [upstream-compatibility](upstream-compatibility.md). The upstream repository has no per-skill license file; the root `LICENSE` is the only license record and is vendored byte-for-byte as this package's `LICENSE`.

The upstream documents state the dependency directly (`docs/productivity/grilling.md` at the pin): "`grill-me` is a one-line skill whose whole body is "run a `/grilling` session", so it needs this skill installed too." This is why `super-grill-me` and `super-grilling` land in one change.

## Azhou-maintained adaptation

| # | Delta | Upstream anchor | Change |
|---|---|---|---|
| G1 | Neutral frontmatter | upstream `name`, `description`, `disable-model-invocation` | `name: super-grill-me`; the description opens `Azhou skill.`, keeps the upstream trigger sentence verbatim, adds the renamed-from compatibility line, a Use-when clause, and the boundaries with `super-grilling` and `super-brainstorming`; `invocation: user-invoked orchestrator` carries the upstream explicit-only policy |
| G2 | Harness-neutral handoff | the single body line | `Call the Skill tool with "grilling".` becomes a three-step handoff to the sibling `super-grilling` package that stops when that package is missing or nothing was named |
| G3 | Dependency record | none | [setup](setup.md) records the fail-closed boundary on `super-grilling` |
| G4 | UI metadata not imported | `agents/openai.yaml` | not vendored; recorded in [upstream-compatibility](upstream-compatibility.md) |

## Showcase scene

`assets/skills/super-grill-me-effect.png` (added 2026-11-24) is the package's skill showcase scene under skill-standard §4. It landed through the governed azhou-scenes local candidate pipeline (2026-11-24, `backend: azhou-gen`, `execution_scope: local_candidate_only`, `article_16_9` mode, final profile tier): a `Qwen/Qwen-Image-2.1` edit through the `mflux-generate-qwen-2.1-edit` engine with the hash-locked canonical fox reference (SHA-256 `bb86cf0a9e80beee8647aeaae19506eb410d2fc19b4ba93c1ec0e2c4d1e0f8a2`) as the sole generation reference, anchor `01-meeting-pull-in` recorded observation-only (`used_as_image_gen_reference=false`, SHA-256 `bea74b7be1dcdd0a8d6a4128e7730d86e9a5b5b900d60e054287670cf5212a43`) and mapped to a service-bell-and-plan scene with six recorded variation points, two seeds (2026112401 and 2026112402) at 1664x928 and 40 steps, each seed carrying an independent preflight/dispatch/engine/postflight receipt chain (`run-postflight.json` valid, asset status HOLD) bound to its CLI execution record. The shipped PNG is the metadata-sanitized copy of the selected seed-2026112402 candidate: a chunk whitelist keeps only IHDR, IDAT and IEND and strips the pipeline-embedded eXIf, iTXt and tEXt metadata, so the shipped file carries no prompt text and no runtime identity (candidate SHA-256 `ed5100845690ca88064d23c6519561ff8491dd1ca2a18bf86c507b3d6c161c83`, IHDR and IDAT stream byte-identical, shipped SHA-256 `1230068b932666f597f92f32bb54288150597f201ec353592c63f09d245526d5`), pinned by `tests/test_super_grill_me.py` together with a chunk walk. The visual P0 selection was delegated to the session under the maintainer's standing go-ahead (2026-11-23); both candidates were viewed before the selection. Recorded deviations from the shot list's failure signals: the paw tips carry short toe lines, and the bell has a realistic metal finish. The selection record, the receipt chain and the deviation list live Git-external in the maintainer candidate library (`grill-showcase-20261124/`, `p0-approval-super-grill-me-seed2026112402.json`), and the formal governed-workspace colour audit remains open. Repository-wide notice: [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/mattpocock/skills/d1478fcb140db0b93c0c8df17bcfd311844749d0/skills/productivity/grill-me/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `caaf8b8de1684f96e26b28f3c29189db5c89cce4b73e1c93d86164f66ef88637`.

License copy check against the retained file:

```bash
curl -fsSL https://raw.githubusercontent.com/mattpocock/skills/d1478fcb140db0b93c0c8df17bcfd311844749d0/LICENSE \
  | shasum -a 256
```

Expected SHA-256: `0e7ac423bf2c6e223b7c5b156f8cf72da49d748e56a1641402c31f22ad07dbb5`, byte-identical to [LICENSES/Mattpocock-Skills-MIT.txt](../../../LICENSES/Mattpocock-Skills-MIT.txt).

## Fidelity classification

Classification: `adapted`. The upstream entry is rewritten into a harness-neutral handoff with an explicit dependency boundary, so the local layer changes instruction text and not only packaging. The upstream trigger sentence stays verbatim and the upstream name keeps working as a trigger. Skill-standard §2.3.
