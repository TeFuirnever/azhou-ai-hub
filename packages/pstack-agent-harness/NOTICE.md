# NOTICE

This package distributes upstream MIT-licensed work together with modifications and additions by this Hub. The Hub's modifications and additions are (c) 2026 Michael Denyer and the Azhou AI Hub maintainers and are released under the [MIT license](LICENSE), except for ZCode-derived engineering references, which retain Apache-2.0 terms. All upstream copyright notices and license terms are preserved.

## Upstream sources

The three upstream components, their commits, copyright and license files are tabulated in [NOTICE-skills.md](NOTICE-skills.md). The component trees under `pstack/` and `components/` are byte-identical to their sources at the commit recorded in `hub-package.json`.

## Additional engineering sources

[ENGINEERING-SOURCES.md](ENGINEERING-SOURCES.md) attributes the eight adapted
references to pinned ZCode (Apache-2.0) and DeepSeek Harness (MIT) sources.
Retain `LICENSE-ZCode`, `NOTICE-ZCode.md` and `LICENSE-DeepSeek` in every skill
bundle containing these references. The generator copies them to all four trees.

## Modifications

Per the MIT license, modifications are permitted. The Hub does not edit upstream files in place. Every modification to upstream content is a patch under `patches/` with a header naming its defect, so what changed and why is one file per change. All upstream copyright notices in source files are preserved.

Hub-authored files covered by this notice include the `hub-skills/`, `hub-adapters/` and `hub-runtime/` trees, `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`, `hub-package.json`, `tools/build-harness.mjs`, `scripts/generate-pstack-harness-trees.mjs` (copied verbatim from upstream), this notice, [NOTICE-skills.md](NOTICE-skills.md), [README.md](README.md) and [UPSTREAM.md](UPSTREAM.md).

`LICENSE-cursor-team-kit` and `LICENSE-thermos` are copied verbatim from upstream cursor-team-kit and thermos rather than authored for this package.
