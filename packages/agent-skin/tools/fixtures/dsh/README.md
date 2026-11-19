# DSH source-bound paint-plane fixtures

These are test-only, unmodified upstream source snapshots from DeepSeek's MIT-licensed deepseek-harness. Each version retains its LICENSE and manifest with immutable commit, original paths and full-file SHA-256. They are not shipped runtime code.

The adapter test consumes the manifest shape, checks the retained source digests and structural source anchors, then verifies paint-plane admission and revocation through the adapter API. The DOM is synthetic, not a browser-rendered upstream application. Neither source evidence nor a passing fixture establishes release support or live upgrade acceptance.

The installed application reports 0.2.2-rc.1 but has no package-to-source attestation. The previously observed checkout fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159 is a merge commit, not the rc.1 release tag. It must not be used as that release's identity.

## Reproduce an update

Resolve the exact `dsh-v<version>` tag using `git ls-remote https://github.com/deepseek-ai/deepseek-harness.git refs/tags/dsh-v<version>` and peel annotated tags if needed. Retrieve each manifest path from `https://raw.githubusercontent.com/deepseek-ai/deepseek-harness/<commit>/<path>`, preserve bytes and license, recalculate SHA-256, review the source anchors and update the explicit shape. Add the version to the adapter tests and run them plus `python3 scripts/verify.py`. Never infer a new release's shape by relabeling an older fixture. Real package identity and live browser acceptance remain separate gates.
