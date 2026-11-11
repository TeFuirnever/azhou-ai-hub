# Third-party notices

Azhou AI Hub code is licensed under the root [MIT License](LICENSE). Some runtime packages preserve or build on separately copyrighted open-source material. Their upstream notices remain effective.

## Optional external integrations

The three entries under `integrations/` contain source-lock metadata, not redistributed source trees. Their adapters operate on explicitly supplied external local checkouts and freeze necessary runtime inputs only in ignored local state. See [integration provenance](docs/integration-provenance.md) for the full chain, selected file boundaries and fixed-version update procedure.

| External source | Selected version | License and distribution boundary |
|---|---|---|
| [TeFuirnever/pstack-agent-harness](https://github.com/TeFuirnever/pstack-agent-harness), selected commit also published by [michael-denyer/pstack-claude](https://github.com/michael-denyer/pstack-claude/commit/356c6e0f978df729eb16f227d795f34d221c5aad) | `356c6e0f978df729eb16f227d795f34d221c5aad`, `0.9.102` | MIT; original pstack, Cursor Team Kit and thermos attribution is retained through the selected licenses/notices. The existing tracked plugin icon is an external input, not new Hub artwork. |
| Agent Orchestration Kit, recorded origin [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator) | Local continuation `4d1a2081f96cdab8a9ea0fe3d357312471546dcc` | Apache-2.0; the exact local continuation and its license are required. Publication of that commit at the recorded origin has not been established. |
| [TeFuirnever/codex-startup-animation](https://github.com/TeFuirnever/codex-startup-animation) | Original base `c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248` plus 22 selected worktree hashes; maintained runtime `0.7.1` build `8` | No program license grant was found. Source copies are retained at `packages/agent-skin/` and `packages/codex-startup-animation/`; the root MIT license does not apply to either copy. No public redistribution authorization has been established. Local operation does not establish that permission. |

Animation character art, scene data, wallpaper and icon source are separate private runtime inputs, supplied explicitly. Generated bundles and visual evidence containing those inputs remain private; no material is generated or promoted into public brand assets by this integration. A successful hash check is not a rights grant or formal visual approval.

## Change scope

`scripts/azhou_hub.py` adapts the four-layer change-scope method and Git failure controls from [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) at commit [`fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`](https://github.com/deepseek-ai/deepseek-harness/tree/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159), specifically `scripts/change-scope.ts` and its tests. The Hub implementation uses Python, a separate worktree-head identity and its own CLI; it does not bundle the DSH runtime.

- Copyright: DeepSeek, 2026
- License: [MIT](LICENSES/DeepSeek-Harness-MIT.txt)
- Update path: compare the pinned source and tests at an immutable revision, review changed behavior and notices, adapt only compatible changes, and run the Hub scope and repository gates.

## Project-local engineering workflows

The tracked workflows under `.agents/skills/` adapt [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness/tree/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159) (MIT) and [ZCode](https://github.com/zai-org/ZCode/tree/a9fe401eede6e6e5e01be9048679c206fe6f02d9) (Apache-2.0). Each workflow retains its upstream license, applicable notice, source pin and adaptation boundary. The GIF encoder and its regression tests are derived from the DeepSeek Harness source at that pin. To update, compare the pinned source and its license to the proposed revision, review the local adaptation and run the relevant checks.

## Azhou brand assets

`assets/github/social-preview.png` is an Azhou-maintained brand asset generated in-house on 2026-08-23 with Codex image generation and resized to 1280×640 for GitHub previews. This version intentionally contains no third-party logos or copied assets. When replacing it, repeat visual and rights review, keep the file below GitHub's 1 MB limit, and verify the separate GitHub Social Preview setting; the README reference is not that platform receipt.

## Super Repo Pedant baseline

`benchmarks/super-repo-pedant/upstream/neat-freak/` is an exact regression snapshot of the `neat-freak` skill from [KKKKhazix/Khazix-Skills](https://github.com/KKKKhazix/Khazix-Skills) at commit [`cfa3436d4d31db9b1340af3082a914adf92f023f`](https://github.com/KKKKhazix/Khazix-Skills/commit/cfa3436d4d31db9b1340af3082a914adf92f023f) (official repository release v1.2.0, skill version 3.1.1; synchronized 2026-11-10 from the previous v3.0.0 reference at `322346ded8129436b3f64707789a73e732ae24d9`; original absorption commit [`bab178311a65f93ffd073e4fdebc9911eae35791`](https://github.com/KKKKhazix/Khazix-Skills/commit/bab178311a65f93ffd073e4fdebc9911eae35791)). Its entry file is named `SKILL.snapshot.md` so package discovery cannot install the baseline.

- Copyright: 数字生命卡兹克
- License: [MIT](LICENSES/Khazix-Skills-MIT.txt)
- Distribution purpose: provenance and parity regression only; it is not the installable current skill.

`skills/super-repo-pedant/` is the Azhou-maintained derivative. Its compatibility contract records every preserved or deliberately replaced behavior.

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

- [Virgil SIL Open Font License 1.1](skills/super-excalidraw-diagram/references/Virgil-LICENSE.md)
- [Excalifont SIL Open Font License 1.1](skills/super-excalidraw-diagram/references/Excalifont-LICENSE.md)

The vendored `excalidraw-all.esm.js` retains its generated bundled-license block, including notices for React, pako, fonteditor-core, harfbuzzjs, pica, DOMPurify, Mermaid and other bundled dependencies. Do not strip that block when rebuilding the file.

Refresh these sources only in an isolated checkout or package workspace at an approved immutable commit/version. Rebuild the engine and font set together. Before replacing libraries, compare the selected baseline to the checked-in snapshot; if it differs, record the verified source commit instead of assuming equivalence. Retain author paths, regenerate `skills/super-excalidraw-diagram/references/icon-catalog.md`, update both provenance surfaces and license copies, then run `python3 scripts/verify.py`. Never refresh from a moving default branch directly into the runtime package.

## Eli5

`skills/super-eli5/` adapts the upstream `eli5` skill from [anthropics/claude-plugins-community](https://github.com/anthropics/claude-plugins-community) at immutable commit [`794af9e63d07fad17087dcab61f21f44cb48effd`](https://github.com/anthropics/claude-plugins-community/commit/794af9e63d07fad17087dcab61f21f44cb48effd). The upstream baseline is a single 321-byte `SKILL.md`; its behavior sentence is retained verbatim in the local package.

- License: [Apache-2.0](LICENSES/Claude-Plugins-Community-Apache-2.0.txt), the repository-level license file of the upstream project
- Imported boundary: the upstream eli5 behavior sentence and trigger intent; no other upstream files exist
- Local changes: harness-neutral description and topic argument, topic boundary, self-contained artifact contract, Azhou brand protocol, stable receipt, provenance and compatibility records

## ASD-STE100

`skills/super-asd-ste100/` imports the upstream `asd-ste100` skill from [TeFuirnever/asd-ste100-skill](https://github.com/TeFuirnever/asd-ste100-skill) at immutable commit [`32511c6992ecb5f1971e46a2943f2e6adceedafe`](https://github.com/TeFuirnever/asd-ste100-skill/commit/32511c6992ecb5f1971e46a2943f2e6adceedafe). The rewrite discipline, the writing-rules summary, the deterministic linter and the worked examples are vendored from the pinned commit; the ASD-STE100 standard's own dictionary is not redistributed and stays excluded by the upstream boundary, which carries over unchanged.

- Copyright: Dustin Yuchen Teng, 2026
- License: [MIT](LICENSES/asd-ste100-skill-MIT.txt)
- Imported boundary: the controlled-English rewrite capability with its Strict and STE-flavored modes, the structural-rule linter `ste-lint.py`, the writing-rules summary and the worked examples
- Local changes: frontmatter normalization to the hub contract, Azhou brand protocol, explicit hold boundary, stable receipt, provenance and compatibility records, plus two reviewed `ste-lint.py` patches (hard-wrapped sentence merging, verb-inflection matching) recorded with both SHA-256 values in the package's provenance

## Archify

`skills/super-archify/` imports the upstream `archify` skill package from [tt-a1i/archify](https://github.com/tt-a1i/archify) at immutable tag [`v3.2.0`](https://github.com/tt-a1i/archify/releases/tag/v3.2.0) (commit [`208acba8d412335185b2056fedf54b3405df43fb`](https://github.com/tt-a1i/archify/commit/208acba8d412335185b2056fedf54b3405df43fb)). The vendored subtree keeps the package's own `THIRD_PARTY_NOTICES.md`, which retains the bundled-asset notices including the JetBrains Mono SIL Open Font License; the pre-rendered example HTML files and the dev-only `package-lock.json` remain the documented exclusions, recorded in the package's compatibility map.

- Copyright: tt-a1i (Archify), 2026
- License: [MIT](LICENSES/archify-MIT.txt); bundled font notice inside the package under `assets/JetBrainsMono-OFL.txt`
- Imported boundary: the ten-mode typed-JSON diagram capability and the explainer capability, with their artifact-specific `validate`/`deliver`/`finalize` gates, renderers, viewer templates, contracts, examples and locale translations
- Bundled explainer dependency: Pele `1.3.0` by kepano (MIT); its retained package license also contains the Lucide rotate-ccw ISC attribution. Preserve both bundled license texts and the package notices.
- Local changes: frontmatter normalization to the hub contract, the carved coexistence boundary against `super-excalidraw-diagram` (recorded in both skills' descriptions), Azhou brand protocol, stable receipt restating the upstream receipt verdicts, `references/setup.md`, provenance and compatibility records

## Public prior art excluded from distribution

[coleam00/excalidraw-diagram-skill](https://github.com/coleam00/excalidraw-diagram-skill) was reviewed as public prior art. At audited commit [`8646fcc9f74f38539c6cdb4c969723336a96ddcd`](https://github.com/coleam00/excalidraw-diagram-skill/commit/8646fcc9f74f38539c6cdb4c969723336a96ddcd), the repository declared no license. Azhou AI Hub therefore does not redistribute its files. The Excalidraw entry instructions, palette, fragments, schema guide, renderer and HTML host were independently re-expressed before public release.

## Contributor rule

New vendored or adapted material requires a source URL, immutable version or commit, license identifier, retained notice and a reproducible update path. Public visibility without a license is not permission to copy, modify or redistribute.
