# Releasing

The hub uses repository-level Semantic Versioning. A tag such as <code>v0.2.0</code> identifies one installable snapshot of every skill; release notes list which skills changed.

## Version policy

- Patch: behavior-preserving fix, documentation correction or deterministic tooling repair.
- Minor: new skill, new user-visible capability or backward-compatible package contract.
- Major: incompatible trigger, install, receipt, schema or runtime-package change.

Benchmark reruns and evidence refreshes do not create a release unless they change the installable contract.

## Release checklist

1. Update [CHANGELOG.md](../CHANGELOG.md), both READMEs and affected support/provenance documents.
2. Run <code>python3 scripts/verify.py</code> from a clean checkout.
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

Signed tags remain a target until a maintainer signing key is configured and verified in a real release rehearsal. The repository must not claim a tag is signed before GitHub shows verifiable evidence.
