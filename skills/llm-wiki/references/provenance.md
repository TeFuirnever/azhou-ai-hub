# Provenance

## Adapted source

- Project: [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)
- Immutable commit: [`deee3a446dadc9bfea31cdc8b19b00b16718082e`](https://github.com/Yeachan-Heo/oh-my-claudecode/commit/deee3a446dadc9bfea31cdc8b19b00b16718082e)
- Audited package version: `4.14.6`
- License: MIT; retained at [`LICENSES/llm-wiki-source-MIT.txt`](../../../LICENSES/llm-wiki-source-MIT.txt)
- Upstream implementation: `src/hooks/wiki/`, `src/tools/wiki-tools.ts`, their tests, lifecycle wrappers, hook/tool registries, standalone MCP transport, keyword detector, and wiki command/skill entry

The Azhou implementation is a Python standard-library adaptation, not a byte-identical copy. `llm_wiki.py` owns storage and migration semantics; `llm_wiki_mcp.py` exposes seven tools over stdio; `llm_wiki_adapter.py` renders explicit protocol configuration and translates lifecycle/trigger contracts; `assets/host/commands/wiki.md` provides the explicit command entry. Current product behavior uses one `.llm-wiki/` store and a reviewed `project-context.json` input.

The upstream comments credit the persistent self-maintained wiki concept to Andrej Karpathy. No Karpathy-authored code or text is redistributed here.

## Reproducible update path

1. Fetch the immutable upstream revision under review.
2. Run the upstream wiki-focused test suite before comparing behavior.
3. Diff the full audit surface named above, including indirect registrations and tests, against the baseline commit.
4. Update `design.md` and production regressions before changing the neutral core.
5. Add a deterministic regression for each behavior change, then run repository verification.
6. Retain the MIT notice and record any compatibility loss or safety replacement explicitly.
