# Releasing

The hub uses repository-level Semantic Versioning. A tag such as <code>v0.2.0</code> identifies one installable snapshot of every skill; release notes list which skills changed.

## Version policy

- Patch: behavior-preserving fix, documentation correction or deterministic tooling repair.
- Minor: new skill, new user-visible capability or backward-compatible package contract.
- Major: incompatible trigger, install, receipt, schema or runtime-package change.

Benchmark reruns and evidence refreshes do not create a release unless they change the installable contract.

## Release checklist

Before external distribution, check package-local rights in the [provenance ledger](integration-provenance.md). Agent Skin and its retained startup source currently have no redistribution grant; the Hub license and a passing verifier do not authorize publishing either source or binaries, including inside a repository archive. Private artwork, candidate state and machine-specific evidence stay outside distribution.

1. Update [CHANGELOG.md](../CHANGELOG.md), both READMEs and affected support/provenance documents.
2. Run <code>python scripts/verify.py</code> from a clean checkout to reproduce the public integrity gate.
3. Confirm required checks pass on a pull request and all review conversations are resolved.
4. Use the manual “Draft release” workflow with the intended SemVer tag.
5. Review generated notes, installation commands, breaking changes, skill digests and known limitations before publishing the draft.

Do not rewrite a published tag or default-branch history. A faulty release gets a new patch release and an explicit changelog correction.

## Release notes

GitHub categories come from [.github/release.yml](../.github/release.yml). Every release should state:

- user-visible outcomes;
- affected skills;
- upgrade or migration action;
- verification summary;
- security/privacy changes;
- known holds;
- full changelog comparison.

The signing mechanism is decided and rehearsed: keyless sigstore (Fulcio OIDC bound to the repository's own workflow identity, Rekor bundles), exercised end to end on 2026-10-17 via the "Signed release rehearsal" workflow — see [the rehearsal evidence](../evidence/signed-release-rehearsal-2026-10-17.md). Release artifacts are signed through this path once downloadable artifacts ship. The repository must not claim a tag or release is signed before GitHub shows verifiable signature evidence for that specific artifact; Git tags themselves remain unsigned until a tag-signing step is added and separately rehearsed.
