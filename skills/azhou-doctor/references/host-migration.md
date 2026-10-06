# Azhou Doctor host install migration

Canonical renames move a package under its new `skills/<canonical-name>/` directory, but host-side wiring is not renamed with them: session hooks, host config entries and installed directories keep referencing the old name until an operator migrates them. The 2026-10-06 cross-harness research (`docs/research/2026-10-06-cross-harness-execution-evidence.md`, section 3.2) records the real failure: after a five-rename sequence, Claude Code `SessionStart`/`SessionEnd` hooks still referenced the pre-rename skill path, raised startup hook errors, and were only repaired by hand. This page is the standing host-side step for any future canonical rename.

## Read-only probe

`doctor --host-root` extends the diagnostic with a migration scan. It compares every observed skill name against the canonical package list and reports one `host_migration` check. It never mutates the host:

~~~bash
python scripts/azhou_hub.py doctor --host-root <host-root> --json
~~~

The probe scans:

- entries under `<host-root>/skills/` whose directory name is not canonical - reported as residual installs, with the entry kind (symlink plus resolved target, directory copy, or file);
- every depth-1 `*.json` and `*.toml` config file directly under `<host-root>/` for `skills/<name>/` references whose `<name>` is not canonical - each hit is reported as a stale hook path with the file and matched string.

Status semantics follow the doctor contract: a stale hook path fails the check (the recorded failure mode is a startup hook error), residual installs alone degrade it to a warning, a clean host passes, and a host root that exposes neither a skills directory nor a config file warns that nothing was scanned. The probe is harness-neutral: it does not infer which harness owns the host root, so the path must be supplied explicitly.

Doctor stays read-only. Removing residual installs and rewriting hook paths are operator actions and are never performed by the skill.

## Migration steps (operator actions)

1. Run the probe against the explicit host root and keep its findings list as the migration inventory.
2. For each stale hook path, edit the named host config and replace `skills/<old-name>/` with `skills/<new-name>/`, preserving unrelated hooks and entries. Restart the harness and confirm the startup hook error is gone.
3. For each residual install, confirm it is residue - its canonical replacement is installed and current - then remove the old-named entry. If the canonical skill is missing from the host, install it from the checkout (for example with `azhou-setup`, or `npx skills add TeFuirnever/azhou-ai-hub --skill <canonical-name>`).
4. Re-run the probe. The migration is closed only when the `host_migration` check reports pass with no findings.

## Known rename map

Canonical renames recorded in `CHANGELOG.md` (#178-#183):

| Renamed away | Canonical now |
| --- | --- |
| ci-test-reliability | super-ci-test-reliability |
| prose-standard | super-prose-standard |
| repo-pedant | super-repo-pedant |
| lavish | super-lavish |
| llm-wiki | super-llm-wiki |

A future canonical rename lands its host-side migration guidance in the same commit as the rename; this page is the runbook step those commits update.
