# Upstream provenance and updates

This directory preserves the independently installable Agent Orchestration Kit package inside the Azhou AI Hub repository. The imported source and package license are:

- Source repository: <https://github.com/donvito/codex-astra-luna-orchestrator.git>
- Upstream base in the source checkout: `f5efba0f957a1e3f0671e629ccc2c655725a7e7b` (`origin/main`, tagged `v0.2.2`)
- Local source commits on that base: `44bfe5922cf2f96aecc0fa2a9bab970c343d6f7e` and `4d1a2081f96cdab8a9ea0fe3d357312471546dcc`
- Imported source checkout HEAD: `4d1a2081f96cdab8a9ea0fe3d357312471546dcc` (`codex/agent-orchestration-kit-20261025`, clean at import, no upstream tracking branch configured)
- Azhou AI Hub HEAD immediately before import: `9a0ab6f10f4930515030b1bf9cf30db305df5bad` (`codex/hub-monorepo-20261026`)
- License and notice: [`LICENSE`](LICENSE), Apache License 2.0

The source checkout commit is the immutable imported snapshot. The two source commits above were local to the inspected checkout; do not assume the imported HEAD is directly fetchable from the public repository. The package files preserve that snapshot without nested Git metadata. No release version is assigned here. Local package adaptations are limited to monorepo installation guidance, this provenance record, and neutral Hub package metadata; profile models, role defaults, and native installer behavior remain from the imported source.

## Reproduce a future upstream update

1. Clone the source repository into a temporary directory and check out the exact full upstream commit being considered:

   ```sh
   aok_update_dir=$(mktemp -d)
   aok_source_dir="$aok_update_dir/source"
   aok_export_dir="$aok_update_dir/export"
   aok_reviewed_commit='SET_THIS_TO_THE_REVIEWED_FULL_UPSTREAM_COMMIT'
   git clone https://github.com/donvito/codex-astra-luna-orchestrator.git "$aok_source_dir"
   git -C "$aok_source_dir" checkout --detach "$aok_reviewed_commit"
   test "$(git -C "$aok_source_dir" rev-parse HEAD)" = "$aok_reviewed_commit"
   ```

2. Review the upstream commit range and changed files, then export that commit without its `.git` directory:

   ```sh
   mkdir -p "$aok_export_dir"
   git -C "$aok_source_dir" archive --format=tar "$aok_reviewed_commit" \
     | tar -xf - -C "$aok_export_dir"
   ```

   Do not import Git metadata, caches, virtual environments, or local installation/recovery state. Keep `LICENSE` and upstream notices with the package.

3. Compare the export with this package, carry forward only reviewed upstream changes, and reapply the monorepo guidance adaptations. Preserve the current model identities and role defaults unless an explicitly reviewed change updates them.

4. Run the package unit tests from the Hub repository root:

   ```sh
   cd packages/agent-orchestration-kit
   python3 -B -m unittest discover -s tests -v
   ```

   Use only isolated temporary Codex and Skill directories for installer checks. Never point an update check at a real user installation.

5. Record the exact reviewed upstream commit and resulting local source checkout HEAD, along with the Hub base HEAD used for the update. Inspect the resulting package diff and verify that no nested `.git` data was added.
