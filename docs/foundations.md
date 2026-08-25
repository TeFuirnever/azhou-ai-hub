# Foundation CLI

`scripts/azhou_hub.py` is the repository-level, harness-neutral control surface for local information, diagnostics, explicit skill setup, opt-in checkout lifecycle operations and verification. It uses only Python 3.11+ standard library modules.

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

When a task is running inside a Treehouse pool, the doctor can also verify the explicit pool without changing its lease:

~~~bash
python3 scripts/azhou_hub.py doctor \
  --treehouse-root /absolute/path/to/treehouse-pool \
  --json
~~~

This check requires Treehouse 2.3.0 or newer, runs `treehouse status --json` from the current checkout, and treats `--treehouse-root` as the expected pool path boundary. It fails when the checkout is outside that boundary or is not an actively leased member with a lease id and holder. The path is not forwarded as Treehouse's own `--root` override because that flag selects a pool configuration rather than verifying the current checkout's pool. Doctor never calls `get`, `return`, `prune` or `destroy`.

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

The normal JSON setup result names the source, destination, mode, applied state and per-skill outcome. It is emitted to stdout and does not establish durable ownership.

## Managed checkout lifecycle: explicit opt-in

Use managed mode only when this CLI should later repair, switch or remove the exact artifact it installed. Managed mode accepts one skill, requires an explicit receipt path, and still defaults to a dry-run:

~~~bash
RECEIPT="$SKILLS_HOME/.azhou-ai-hub/receipts/repo-pedant.json"

python3 scripts/azhou_hub.py setup \
  --managed \
  --receipt "$RECEIPT" \
  --skill repo-pedant \
  --target "$SKILLS_HOME" \
  --mode link \
  --json

python3 scripts/azhou_hub.py setup \
  --managed \
  --receipt "$RECEIPT" \
  --skill repo-pedant \
  --target "$SKILLS_HOME" \
  --mode link \
  --apply \
  --json
~~~

The receipt records the canonical source, source digest, explicit target, recomputed destination, installed identity and repository revision. Its integrity digest detects accidental corruption; it is not a signature and does not authenticate an untrusted file. Every later mutation also requires `--target` and independently revalidates the current canonical skill, source digest, destination boundary and installed artifact.

~~~bash
# Restore only a missing, receipt-owned artifact.
python3 scripts/azhou_hub.py repair \
  --receipt "$RECEIPT" --target "$SKILLS_HOME" --json
python3 scripts/azhou_hub.py repair \
  --receipt "$RECEIPT" --target "$SKILLS_HOME" --apply --json

# Switch the same skill at the same target between link and copy.
python3 scripts/azhou_hub.py migrate \
  --receipt "$RECEIPT" --target "$SKILLS_HOME" --mode copy --json
python3 scripts/azhou_hub.py migrate \
  --receipt "$RECEIPT" --target "$SKILLS_HOME" --mode copy --apply --json

# Remove only the exact artifact still matching the receipt.
python3 scripts/azhou_hub.py uninstall \
  --receipt "$RECEIPT" --target "$SKILLS_HOME" --json
python3 scripts/azhou_hub.py uninstall \
  --receipt "$RECEIPT" --target "$SKILLS_HOME" --apply --json
~~~

`repair` never updates changed source or overwrites drift. `migrate` does not move between harness roots or rename a skill. `uninstall` does not scan by name, accept `--force`, or remove drifted/unowned content. A missing managed artifact is an idempotent no-op.

## Exit codes and status

| Result | Exit code |
|---|---:|
| Healthy doctor, including warnings | `0` |
| Setup or lifecycle dry-run; successful apply; already current/absent | `0` |
| Failed doctor; conflict, invalid receipt, rollback failure or other mutation error | `1` |
| Invalid command or option | `2` |
| `verify` failure | underlying verifier exit code |

Doctor checks use `pass`, `warn`, `fail` and `skip`. Warnings produce `degraded` health but do not masquerade as a failed deterministic gate.

## Ownership boundary

The foundation CLI does not contact registries, self-update, rewrite harness configuration, install hooks, clean caches or infer a harness home. Its lifecycle commands own only artifacts created by explicit managed checkout setup and proven by a valid receipt plus current filesystem identity. Package-manager installations still use their package manager for update and removal. Skill-specific lifecycle adapters remain explicit and keep their own setup/uninstall contracts.

The design source and portability decisions are recorded in [the oh-my-claudecode foundation research](research/oh-my-claudecode-foundation-capabilities.md).
