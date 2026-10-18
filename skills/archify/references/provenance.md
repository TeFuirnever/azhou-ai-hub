# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [archify-MIT.txt](../../../LICENSES/archify-MIT.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/tt-a1i/archify` |
| Immutable tag / commit | `v3.1.0` / `1c2b42d660e4a7571813fb43839c79e3e9ca7720` |
| Upstream `SKILL.md` SHA-256 | recorded in `tests/test_archify.py` beside every vendored file hash |
| License | MIT, retained at [archify-MIT.txt](../../../LICENSES/archify-MIT.txt); upstream `THIRD_PARTY_NOTICES.md` ships inside the package (JetBrains Mono OFL and other bundled notices) |

The upstream capability baseline at the locked tag is the complete presentation-diagram discipline: typed JSON schemas for ten diagram modes, the deterministic `validate`/`deliver`/`finalize` CLI with real-browser checks, the viewer runtime, the authoring/delivery contracts, and the update-awareness rule. The package is vendored from the upstream `archify/` subtree with two exclusions recorded in the compatibility map — the fifteen pre-rendered example HTML files and `package-lock.json` (dev-only); `node bin/archify.mjs doctor` passes all 25 checks on the trimmed package, and every vendored file's SHA-256 is pinned in the complete digest manifest `tests/archify-vendor-manifest.json`.

## Azhou-maintained adaptation

- keeps the upstream `SKILL.md` capability body verbatim, including the fast authoring path, type router, Mermaid mapping, delivery and repair limits, update awareness, setup/fallback and the output contract;
- normalizes frontmatter to the hub contract (`name`, `description`, `invocation`), moving the upstream `license` and `metadata` fields into this record (upstream v3.1.0 by tt-a1i);
- carves the coexistence boundary into the description: editable `.excalidraw` source scenes belong to excalidraw-diagram; this skill delivers the read-only interactive map (mirrored in excalidraw-diagram's own description);
- adds the Azhou brand protocol, the hold boundary, and the stable receipt (`archify.receipt.v1`) whose verification line restates the upstream finalize receipt verdicts;
- adds `references/setup.md` (Node.js 18+ runtime, fail-closed `doctor`/`guide`/`validate` verification), this provenance record and the upstream compatibility map.

Classification: `faithful` — the complete upstream capability (schemas, CLI gates, renderers, viewer runtime, contracts) is retained unmodified, and every local addition (frontmatter normalization, boundary carve, brand protocol, receipt, setup record, provenance and compatibility records) is packaging or interaction layer, which skill-standard §2.3 excludes from `adapted`. Precedent: verbatim retention of the entire upstream capability with packaging-only additions decides `faithful`. Skill-standard §2.3.

## Reproducible source check

```bash
git clone https://github.com/tt-a1i/archify /tmp/archify-upstream
git -C /tmp/archify-upstream checkout v3.1.0
shasum -a 256 /tmp/archify-upstream/archify/SKILL.md /tmp/archify-upstream/archify/bin/archify.mjs
```
