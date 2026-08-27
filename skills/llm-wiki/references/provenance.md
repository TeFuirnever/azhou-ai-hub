# Provenance

## Adapted upstream

- Project: [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode)
- Immutable commit: [`deee3a446dadc9bfea31cdc8b19b00b16718082e`](https://github.com/Yeachan-Heo/oh-my-claudecode/commit/deee3a446dadc9bfea31cdc8b19b00b16718082e)
- Audited package version: `4.14.6`
- License: MIT; retained at [`LICENSES/oh-my-claudecode-MIT.txt`](../../../LICENSES/oh-my-claudecode-MIT.txt)
- Upstream implementation: `src/hooks/wiki/`, `src/tools/wiki-tools.ts`, and their tests

The Azhou implementation is a Python standard-library adaptation, not a byte-identical copy. It preserves the page schema, seven user operations, keyword/CJK search, append merge, lint classes, catalog, log, locking, and lifecycle concepts. It replaces oh-my-claudecode and Claude-specific paths with a neutral CLI and explicit lifecycle adapter.

The upstream comments credit the persistent self-maintained wiki concept to Andrej Karpathy. No Karpathy-authored code or text is redistributed here.

## Reproducible update path

1. Fetch the immutable upstream revision under review.
2. Run the upstream wiki-focused test suite before comparing behavior.
3. Diff `src/hooks/wiki/`, `src/tools/wiki-tools.ts`, and their tests against the baseline commit above.
4. Update the compatibility table before changing the neutral core.
5. Add a deterministic regression for each behavior change, then run repository verification.
6. Retain the MIT notice and record any compatibility loss or safety replacement explicitly.
