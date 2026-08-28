# Super Caveman source reconstruction

This directory is benchmark evidence, not an installable skill package.

The immutable Caveman source is commit `11ddc0c9813c8f75365cd5be2f753df08712f154` from <https://github.com/JuliusBrussee/caveman>. Three requested local entry snapshots match that commit. Four are derivatives reconstructed by the patches in `local-source-deltas/`.

## Reconstruct the four local snapshots

1. Check out the immutable Caveman commit.
2. From its repository root, apply each zero-context `local-source-deltas/*.patch` file with `git apply --unidiff-zero`.
3. Hash the resulting `skills/<name>/SKILL.md` files with SHA-256.
4. Compare each result with `local_snapshot_sha256` in `../capability-map.json`.
5. Compare each patch with its `delta_sha256` before relying on the result.

The patches deliberately retain source-relative paths and do not use the reserved `SKILL.md` package entry name.
