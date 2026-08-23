# Third-party notices

Azhou AI Hub code is licensed under the root [MIT License](LICENSE). Some runtime packages preserve or build on separately copyrighted open-source material. Their upstream notices remain effective.

## Repo Pedant baseline

\`benchmarks/repo-pedant/upstream/neat-freak/\` is an exact regression snapshot of the \`neat-freak\` skill from [KKKKhazix/Khazix-Skills](https://github.com/KKKKhazix/Khazix-Skills) at commit [\`bab178311a65f93ffd073e4fdebc9911eae35791\`](https://github.com/KKKKhazix/Khazix-Skills/commit/bab178311a65f93ffd073e4fdebc9911eae35791). Its entry file is named \`SKILL.snapshot.md\` so package discovery cannot install the legacy baseline.

- Copyright: 数字生命卡兹克
- License: [MIT](LICENSES/Khazix-Skills-MIT.txt)
- Distribution purpose: provenance and parity regression only; it is not the installable current skill.

\`skills/repo-pedant/\` is the Azhou-maintained derivative. Its compatibility contract records every preserved or deliberately replaced behavior.

## Excalidraw Diagram

The package uses these licensed upstreams:

| Upstream | Use | License |
|---|---|---|
| [Agents365-ai/excalidraw-skill](https://github.com/Agents365-ai/excalidraw-skill) | library helper and independently adapted layout/routing techniques | [MIT](LICENSES/Agents365-MIT.txt) |
| [excalidraw/excalidraw](https://github.com/excalidraw/excalidraw) | official export engine, type facts, fonts and renderer assets | [MIT](LICENSES/Excalidraw-MIT.txt), plus font licenses below |
| [excalidraw/excalidraw-libraries](https://github.com/excalidraw/excalidraw-libraries) | offline component-library snapshot | [MIT](LICENSES/Excalidraw-MIT.txt) |
| [excalidraw/mermaid-to-excalidraw](https://github.com/excalidraw/mermaid-to-excalidraw) | Mermaid conversion | [MIT](LICENSES/Excalidraw-MIT.txt) |
| [excalidraw/svg-to-excalidraw](https://github.com/excalidraw/svg-to-excalidraw) | SVG conversion | [MIT](LICENSES/Excalidraw-MIT.txt) |
| [github/awesome-copilot](https://github.com/github/awesome-copilot) | diagram-type prior art and schema references | MIT; see upstream |

Font redistribution notices ship beside the fonts:

- [Virgil SIL Open Font License 1.1](skills/excalidraw-diagram/references/Virgil-LICENSE.md)
- [Excalifont SIL Open Font License 1.1](skills/excalidraw-diagram/references/Excalifont-LICENSE.md)

The vendored \`excalidraw-all.esm.js\` retains its generated bundled-license block, including notices for React, pako, fonteditor-core, harfbuzzjs, pica, DOMPurify, Mermaid and other bundled dependencies. Do not strip that block when rebuilding the file.

## Public prior art excluded from distribution

[coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill) was reviewed as public prior art. At audited commit [\`8646fcc9f74f38539c6cdb4c969723336a96ddcd\`](https://github.com/coleam00/excalidraw-diagram-skill/commit/8646fcc9f74f38539c6cdb4c969723336a96ddcd), the repository declared no license. Azhou AI Hub therefore does not redistribute its files. The Excalidraw entry instructions, palette, fragments, schema guide, renderer and HTML host were independently re-expressed before public release.

## Contributor rule

New vendored or adapted material requires a source URL, immutable version or commit, license identifier, retained notice and a reproducible update path. Public visibility without a license is not permission to copy, modify or redistribute.
