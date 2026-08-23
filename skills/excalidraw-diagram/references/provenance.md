# Provenance and bundled assets

This file records runtime lineage. Repository-wide notices and license copies live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md).

## Maintained Azhou layer

The following are Azhou-maintained implementations: \`SKILL.md\`, the brand lifecycle, palette, scene fragments, setup/evolution contracts, templates, deterministic checks, the Python renderer/HTML host, persistence helpers and benchmark protocol.

\`coleam00/excalidraw-diagram-skill\` was inspected as public prior art but declared no license at audited commit \`8646fcc9f74f38539c6cdb4c969723336a96ddcd\`. Its files are not distributed here. A pre-publication audit replaced previously mirrored expression in the entry instructions, palette, fragments, schema guide and renderer.

## Licensed sources

| Component | Upstream | Version / boundary |
|---|---|---|
| library merge helper and layout prior art | \`Agents365-ai/excalidraw-skill\` | MIT; local helper has additional offline-catalog behavior |
| diagram types and schema prior art | \`github/awesome-copilot\`, \`skills/excalidraw-diagram-generator\` | MIT; local references are maintained independently |
| official engine | \`@excalidraw/excalidraw\` | \`0.18.1\`; \`references/vendor/excalidraw-all.esm.js\` |
| Mermaid converter | \`excalidraw/mermaid-to-excalidraw\` | \`2.2.2\`; bundled into the official engine build |
| SVG converter | \`excalidraw/svg-to-excalidraw\` | \`0.0.2\`; bundled into the official engine build |
| component libraries | \`excalidraw/excalidraw-libraries\` | 231 gzipped libraries, 4,134 catalogued items |

The consolidated engine retains its generated bundled-license comment. Its upstream public Firebase client identifier is neutralized in this offline package because collaboration services are outside the runtime boundary. Rebuilds must repeat that neutralization, preserve the license block, and update this table, lockfiles and verification evidence together.

## Fonts and libraries

The mirrored Excalidraw production font tree enables offline rendering. Virgil and Excalifont use SIL OFL 1.1; keep \`Virgil-LICENSE.md\` and \`Excalifont-LICENSE.md\` beside the assets.

The gzipped component-library snapshot lives in \`references/libraries/\`. It is resolved locally by \`scripts/excalidraw_lib.py\`; network lookup is fallback-only for a library absent from the snapshot. Refresh only from the MIT-licensed \`excalidraw/excalidraw-libraries\` repository, retain author paths, regenerate \`icon-catalog.md\`, and verify catalog counts before promotion.

## Excluded upstream surfaces

Store, room, playground, analytics, hosted library services and archived desktop/embed clients are not runtime dependencies. Stub or empty upstream docs are also excluded. The skill creates local files and does not need Excalidraw cloud infrastructure.
