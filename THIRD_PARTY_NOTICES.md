# Third-party notices

Azhou AI Hub code is licensed under the root [MIT License](LICENSE). Some runtime packages preserve or build on separately copyrighted open-source material. Their upstream notices remain effective.

## Azhou brand assets

`assets/github/social-preview.png` is an Azhou-maintained brand asset generated in-house on 2026-08-23 with Codex image generation and resized to 1280×640 for GitHub previews. This version intentionally contains no third-party logos or copied assets. When replacing it, repeat visual and rights review, keep the file below GitHub's 1 MB limit, and verify the separate GitHub Social Preview setting; the README reference is not that platform receipt.

## Repo Pedant baseline

`benchmarks/repo-pedant/upstream/neat-freak/` is an exact regression snapshot of the `neat-freak` skill from [KKKKhazix/Khazix-Skills](https://github.com/KKKKhazix/Khazix-Skills) at commit [`bab178311a65f93ffd073e4fdebc9911eae35791`](https://github.com/KKKKhazix/Khazix-Skills/commit/bab178311a65f93ffd073e4fdebc9911eae35791). Its entry file is named `SKILL.snapshot.md` so package discovery cannot install the legacy baseline.

- Copyright: 数字生命卡兹克
- License: [MIT](LICENSES/Khazix-Skills-MIT.txt)
- Distribution purpose: provenance and parity regression only; it is not the installable current skill.

`skills/repo-pedant/` is the Azhou-maintained derivative. Its compatibility contract records every preserved or deliberately replaced behavior.

## Super Caveman

`skills/super-caveman/` enhances the original Caveman Agent Skill with six companion skills from [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) at immutable commit [`11ddc0c9813c8f75365cd5be2f753df08712f154`](https://github.com/JuliusBrussee/caveman/commit/11ddc0c9813c8f75365cd5be2f753df08712f154).

The requested local import set is not described as byte-identical wholesale: `cavecrew`, `caveman-commit`, and `caveman-review` match the pinned commit, while `caveman`, `caveman-compress`, `caveman-help`, and `caveman-stats` are separately hashed local derivative snapshots. Both trusted hash sets and lineage labels are retained in `benchmarks/super-caveman/capability-map.json`; retained non-installable patches reconstruct the four derivative snapshots from the pinned commit.

- Copyright: Julius Brussee, 2026
- License: [MIT](LICENSES/Caveman-MIT.txt)
- Imported boundary: response modes, delegation router, commit and review formats, help, safe prose compression, and exact-statistics semantics
- Local changes: original Caveman remains the core while six companion entries become routes in one canonical package; Claude-only presets, model subprocesses, automatic hooks and unverified savings claims are replaced by neutral capability routing and deterministic local gates

The complete pinned output-behavior contract and its original fourteen response fixtures are adopted from [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) at immutable commit [`b42a45a068e080294924bfba19a7a2e8944c48ff`](https://github.com/ayghri/i-have-adhd/commit/b42a45a068e080294924bfba19a7a2e8944c48ff). Five local closure fixtures cover previously implicit behavior without importing plugin installation, hooks, global configuration or persistence files.

- Copyright: Ayoub Ghriss, 2026
- License: [MIT](LICENSES/i-have-adhd-MIT.txt)
- Imported boundary: ten response-shaping rules, explicit exceptions, and fourteen evaluation cases
- Local changes: response rules run before Caveman compression; upstream hooks, global configuration, adapters and diagnostic claims are omitted

Upstream README files, installers, status-line integration and separate alias packages are not redistributed. Source hashes, adaptation mapping and integrity fixtures live under `benchmarks/super-caveman/`.

## LLM Wiki

`skills/llm-wiki/` is a Python standard-library adaptation of the LLM Wiki implementation in [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) at commit [`deee3a446dadc9bfea31cdc8b19b00b16718082e`](https://github.com/Yeachan-Heo/oh-my-claudecode/commit/deee3a446dadc9bfea31cdc8b19b00b16718082e), audited as package version `4.14.6`.

- Copyright: Yeachan Heo
- License: [MIT](LICENSES/llm-wiki-source-MIT.txt)
- Adaptation boundary: Markdown page schema, seven wiki operations, keyword/CJK search, append merge, lint, catalog, operation log, locking and lifecycle concepts. Current product integration uses a neutral CLI, stdio MCP server, lifecycle adapter, and a single private store.

The upstream comments credit the persistent self-maintained wiki concept to Andrej Karpathy. This repository does not redistribute Karpathy-authored code or text.

## Spec Relay / Lavish Editor

`skills/spec-relay/` is an enhanced derivative of the generated `lavish` Agent Skill from [kunchenguid/lavish-axi](https://github.com/kunchenguid/lavish-axi) at immutable commit [`232972beba9e0e4e75682c98f2aeb2cf01532122`](https://github.com/kunchenguid/lavish-axi/commit/232972beba9e0e4e75682c98f2aeb2cf01532122). The unmodified upstream baseline is hash-locked for reproducibility; the local Skill intentionally diverges and uses a distinct canonical name.

- Copyright: Kun Chen, 2026
- License: [MIT](LICENSES/Lavish-AXI-MIT.txt)
- Imported boundary: generated skill instructions only; no Lavish application code, browser bundle or hosted service is vendored
- Local changes: `spec-relay` identity, neutral frontmatter, locked CLI baseline, portable Spec HTML, embedded comment/annotation state, stable review IDs, feedback disposition, next-owner receipts, setup/provenance/compatibility records and explicit authorization checkpoints

`lavish-axi` remains an external npm runtime dependency. `ht-ml.app` sharing is a third-party publication action, not a bundled or repository-operated service.

## Excalidraw Diagram

The package uses these licensed upstreams. Package versions and local digests are current runtime evidence. The three commit rows marked “selected baseline” were chosen on 2026-08-26 as the latest public commits at or before the 2026-08-23 package build; they are immutable future comparison points, not proof of the exact historical import commit.

| Upstream | Immutable lock | Use | License |
|---|---|---|---|
| [Agents365-ai/excalidraw-skill](https://github.com/Agents365-ai/excalidraw-skill/commit/00606e9fcb072e9644cbfbb3d49a9dafe8b98c25) | selected baseline `00606e9fcb072e9644cbfbb3d49a9dafe8b98c25` | library helper and independently adapted layout/routing techniques | [MIT](LICENSES/Agents365-MIT.txt) |
| [excalidraw/excalidraw](https://github.com/excalidraw/excalidraw/commit/a2ec2889babf7d2295469c6d90ebe77fae57df84) | `@excalidraw/excalidraw@0.18.1`; tag commit `a2ec2889babf7d2295469c6d90ebe77fae57df84` | official export engine, type facts, fonts and renderer assets | [MIT](LICENSES/Excalidraw-MIT.txt), plus font licenses below |
| [excalidraw/excalidraw-libraries](https://github.com/excalidraw/excalidraw-libraries/commit/92e1979e8157da0ad9c2bd912c01ea9381d1733f) | selected baseline `92e1979e8157da0ad9c2bd912c01ea9381d1733f` | offline component-library snapshot; exact historical import commit remains unproved | [MIT](LICENSES/Excalidraw-MIT.txt) |
| [excalidraw/mermaid-to-excalidraw](https://github.com/excalidraw/mermaid-to-excalidraw/commit/167be14d2f6f5915af4d157bfc66e341ceb58c35) | `@excalidraw/mermaid-to-excalidraw@2.2.2`; npm `gitHead` `167be14d2f6f5915af4d157bfc66e341ceb58c35` | Mermaid conversion in the consolidated engine | [MIT](LICENSES/Excalidraw-MIT.txt) |
| [excalidraw/svg-to-excalidraw](https://github.com/excalidraw/svg-to-excalidraw/commit/b862bb78c8d677729996417640c4061af8060ee5) | `svg-to-excalidraw@0.0.2`; npm `gitHead` `b862bb78c8d677729996417640c4061af8060ee5` | SVG conversion in the consolidated engine | [MIT](LICENSES/Excalidraw-MIT.txt) |
| [github/awesome-copilot](https://github.com/github/awesome-copilot/commit/83561bd7d8a46fcda0581aedabdf8eac7cb196b6) | selected baseline `83561bd7d8a46fcda0581aedabdf8eac7cb196b6` | diagram-type prior art and schema references | [MIT](LICENSES/GitHub-Awesome-Copilot-MIT.txt) |

Font redistribution notices ship beside the fonts:

- [Virgil SIL Open Font License 1.1](skills/excalidraw-diagram/references/Virgil-LICENSE.md)
- [Excalifont SIL Open Font License 1.1](skills/excalidraw-diagram/references/Excalifont-LICENSE.md)

The vendored `excalidraw-all.esm.js` retains its generated bundled-license block, including notices for React, pako, fonteditor-core, harfbuzzjs, pica, DOMPurify, Mermaid and other bundled dependencies. Do not strip that block when rebuilding the file.

Refresh these sources only in an isolated checkout or package workspace at an approved immutable commit/version. Rebuild the engine and font set together. Before replacing libraries, compare the selected baseline to the checked-in snapshot; if it differs, record the verified source commit instead of assuming equivalence. Retain author paths, regenerate `skills/excalidraw-diagram/references/icon-catalog.md`, update both provenance surfaces and license copies, then run `python3 scripts/verify.py`. Never refresh from a moving default branch directly into the runtime package.

## Public prior art excluded from distribution

[coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill) was reviewed as public prior art. At audited commit [`8646fcc9f74f38539c6cdb4c969723336a96ddcd`](https://github.com/coleam00/excalidraw-diagram-skill/commit/8646fcc9f74f38539c6cdb4c969723336a96ddcd), the repository declared no license. Azhou AI Hub therefore does not redistribute its files. The Excalidraw entry instructions, palette, fragments, schema guide, renderer and HTML host were independently re-expressed before public release.

## Contributor rule

New vendored or adapted material requires a source URL, immutable version or commit, license identifier, retained notice and a reproducible update path. Public visibility without a license is not permission to copy, modify or redistribute.
