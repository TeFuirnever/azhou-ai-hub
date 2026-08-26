# Provenance and bundled assets

This file records runtime lineage. Repository-wide notices and license copies live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Maintained Azhou layer

The following are Azhou-maintained implementations: `SKILL.md`, the brand lifecycle, palette, scene fragments, setup/evolution contracts, templates, deterministic checks, the Python renderer/HTML host, persistence helpers and benchmark protocol.

`coleam00/excalidraw-diagram-skill` was inspected as public prior art but declared no license at audited commit `8646fcc9f74f38539c6cdb4c969723336a96ddcd`. Its files are not distributed here. A pre-publication audit replaced previously mirrored expression in the entry instructions, palette, fragments, schema guide and renderer.

## Licensed sources

| Component | Upstream | Version / boundary |
|---|---|---|
| library merge helper and layout prior art | `Agents365-ai/excalidraw-skill` | selected comparison baseline `00606e9fcb072e9644cbfbb3d49a9dafe8b98c25`; exact historical import commit was not recorded; local helper adds offline-catalog behavior |
| diagram types and schema prior art | `github/awesome-copilot`, `skills/excalidraw-diagram-generator` | selected comparison baseline `83561bd7d8a46fcda0581aedabdf8eac7cb196b6`; exact historical import commit was not recorded; local references are maintained independently |
| official engine | `@excalidraw/excalidraw` | `0.18.1`, tag commit `a2ec2889babf7d2295469c6d90ebe77fae57df84`; `references/vendor/excalidraw-all.esm.js` and mirrored fonts |
| Mermaid converter | `@excalidraw/mermaid-to-excalidraw` | `2.2.2`, npm `gitHead` `167be14d2f6f5915af4d157bfc66e341ceb58c35`; bundled into the consolidated engine |
| SVG converter | `svg-to-excalidraw` | `0.0.2`, npm `gitHead` `b862bb78c8d677729996417640c4061af8060ee5`; bundled into the consolidated engine |
| component libraries | `excalidraw/excalidraw-libraries` | selected comparison baseline `92e1979e8157da0ad9c2bd912c01ea9381d1733f`; exact historical import commit was not recorded; 231 gzipped libraries and 4,134 catalogued items |

The consolidated engine retains its generated bundled-license comment. Its upstream public Firebase client identifier is neutralized in this offline package because collaboration services are outside the runtime boundary. The checked-in bundle SHA-256 is `f0a616466292610789f05a2da3f529b44d57cb1a44b3ca91081bb8d074fc542c`; recompute it from the repository root with `shasum -a 256 skills/excalidraw-diagram/references/vendor/excalidraw-all.esm.js`. Rebuilds must repeat that neutralization, preserve the license block, and update this table, lockfiles and verification evidence together.

## Fonts and libraries

The mirrored Excalidraw production font tree enables offline rendering. Virgil and Excalifont use SIL OFL 1.1; keep `Virgil-LICENSE.md` and `Excalifont-LICENSE.md` beside the assets.

The gzipped component-library snapshot lives in `references/libraries/`. It is resolved locally by `scripts/excalidraw_lib.py`; network lookup is fallback-only for a library absent from the snapshot. Its sorted per-file SHA-256 manifest digest is `bb265f168a10338f095143d7d56387e9fc44d3d4ad994521b1be989a87ab124a`. Recompute it from the repository root with `find skills/excalidraw-diagram/references/libraries -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256`. Before refresh, compare the selected baseline to the checked-in snapshot; if it differs, record the verified source commit instead of assuming equivalence. Retain author paths, regenerate `icon-catalog.md`, recompute the manifest digest and verify catalog counts before promotion.

## Reproducible refresh boundary

1. Create an isolated checkout/package workspace at the exact package lock or selected comparison baseline above; never copy from a moving default branch.
2. Follow [setup.md](setup.md) to rebuild the consolidated engine and mirror the matching font tree. Preserve the generated bundled-license comment and repeat the Firebase-client neutralization.
3. Compare the selected library baseline to the current snapshot. Only after exact source identity is proved, mirror with the gzip command in `icon-catalog.md`, retain author paths, regenerate the catalog, and verify the item counts.
4. Update this file, `THIRD_PARTY_NOTICES.md`, relevant license copies, bundle/library digests and lockfiles in the same change, then run `python3 scripts/verify.py` from the repository root.

## Excluded upstream surfaces

Store, room, playground, analytics, hosted library services and archived desktop/embed clients are not runtime dependencies. Stub or empty upstream docs are also excluded. The skill creates local files and does not need Excalidraw cloud infrastructure.
