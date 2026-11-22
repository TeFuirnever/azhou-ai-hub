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

## Showcase deferral record

The skill-standard §4 showcase scene and the README hero/banner digit redraw are deferred to a dedicated maintainer visual pass, following the #478 deferral precedent set by the earlier document-skill adoption. The READMEs carry the catalog row and install command without a showcase section, and the hero/banner alt-text counts stay at their landed state until that pass lands. No governed azhou-scenes run, named human visual P0 approval or metadata-sanitized scene image exists for this package yet, and none may be substituted by an ungoverned generation tool. A future `feat(assets)` commit is expected to add `assets/skills/super-frontend-design-effect.png` and move the alt-text counts together.
