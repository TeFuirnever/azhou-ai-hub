# Foundation CLI

`scripts/azhou_hub.py` is the repository-level, harness-neutral control surface for local information, diagnostics, explicit skill setup and verification. It uses only Python 3.11+ standard library modules.

## Commands

~~~bash
python3 scripts/azhou_hub.py info --json
python3 scripts/azhou_hub.py version --json
python3 scripts/azhou_hub.py doctor --json
python3 scripts/azhou_hub.py verify
~~~

- `info` reports the checked-out repository, Git revision when available, Python runtime, canonical skill list, support-matrix path and verification command.
- `version` reports only the provable Git revision and dirty state. It does not invent installed or released version metadata.
- `doctor` is read-only. It checks repository shape, Python, Git metadata, canonical packages, an optional install target and, with `--verify`, the complete deterministic gate.
- `verify` delegates to `python3 scripts/verify.py` and preserves its exit code.

Use `--help` on the root command or any subcommand for current options.

## Setup: inspect first, apply explicitly

`setup` requires an explicit harness skill root. Its default is a dry-run; `--apply` is the mutation checkpoint.

~~~bash
SKILLS_HOME=/absolute/path/to/harness/skills

python3 scripts/azhou_hub.py setup \
  --skill repo-pedant \
  --target "$SKILLS_HOME" \
  --mode link \
  --json

python3 scripts/azhou_hub.py setup \
  --skill repo-pedant \
  --target "$SKILLS_HOME" \
  --mode link \
  --apply \
  --json

python3 scripts/azhou_hub.py doctor \
  --skill repo-pedant \
  --target "$SKILLS_HOME" \
  --json
~~~

Use `link` for checked-out contributor work and `copy` for an isolated package snapshot. Omit `--skill` to plan all canonical packages. Repeating the same setup converges to `current`. If a destination contains a different symlink, file or directory, setup returns `conflict` and does not overwrite it.

The JSON setup receipt names the source, destination, mode, applied state and per-skill outcome. It is emitted to stdout; callers decide whether and where to persist it.

## Exit codes and status

| Result | Exit code |
|---|---:|
| Healthy doctor, including warnings | `0` |
| Setup dry-run or successful apply | `0` |
| Failed doctor or setup conflict/error | `1` |
| Invalid command or option | `2` |
| `verify` failure | underlying verifier exit code |

Doctor checks use `pass`, `warn`, `fail` and `skip`. Warnings produce `degraded` health but do not masquerade as a failed deterministic gate.

## Ownership boundary

The foundation CLI does not contact registries, self-update, remove installations, rewrite harness configuration, install hooks or clean caches. Managed installations still use their package manager for update and removal. Skill-specific lifecycle adapters remain explicit and keep their own setup/uninstall contracts.

The design source and portability decisions are recorded in [the oh-my-claudecode foundation research](research/oh-my-claudecode-foundation-capabilities.md).
