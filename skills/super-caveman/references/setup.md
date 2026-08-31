# Setup

## Core requirements

- Agent Skills-compatible harness
- Python 3.10 or newer for `compression_guard.py`
- Python standard library only
- A filesystem that permits same-directory hard links for guarded apply/restore; the runtime probes this before moving the source and fails closed when unsupported

Check commands before changing a file:

```bash
python3 "$SKILL_DIR/scripts/compression_guard.py" --help
python3 "$SKILL_DIR/scripts/compression_guard.py" preflight /absolute/path/to/file --json
python3 "$SKILL_DIR/scripts/compression_guard.py" finalize --help
```

No global install, API key, Node.js package, hook, background service, or model-specific package identity is required for the neutral core.

## Installation boundary

Install the complete `skills/super-caveman/` directory under one configured skill root. Do not install the seven upstream Caveman source names beside it. Reload the harness if its skill catalog was already cached.

Canonical package name: `super-caveman`. `/caveman` and the six companion commands are compatibility triggers routed through this package, not separate packages.

Do not modify global harness settings or session-log locations as part of ordinary setup. Optional host adapters require a separate explicit review and authorization.

## Optional Codex lifecycle adapter

The bundled adapter is the current lifecycle integration. It is off by default and does not read transcripts, session logs, or network resources. It registers one five-second Codex `SessionStart` handler for `startup`, `resume`, `clear`, and `compact`. Every invocation supplies a bounded, full-mode capsule with a schema version and rules digest.

The one owned registration is intentionally not merged with unrelated `SessionStart` handlers. Sharing an event does not imply shared ownership: grouping other tools into this adapter would not reduce their invocations and would break scoped upgrade, uninstall, and rollback. Super Caveman owns one renderer, one Codex adapter, and at most one registration in each explicitly selected scope.

Codex merges matching hooks across user, project, and plugin layers. If this machine already injects the original Caveman or `i-have-adhd` hooks, adding Super Caveman without a switch would duplicate instructions. Reconcile the two direct legacy `SessionStart` handlers only after explicit review:

```bash
# Writes only ~/.codex/hooks.json; removes only the known legacy Caveman and ADHD commands.
python3 "$SKILL_DIR/scripts/codex_adapter.py" reconcile-legacy --scope user

# Required only when the old plugins are enabled on this machine; removes them from Codex's user plugin configuration.
codex plugin remove caveman@caveman
codex plugin remove i-have-adhd@i-have-adhd
```

Then choose one explicit adapter scope:

```bash
# Writes /absolute/path/to/project/.codex/hooks.json
python3 "$SKILL_DIR/scripts/codex_adapter.py" setup --scope project --project-dir /absolute/path/to/project

# Writes ~/.codex/hooks.json
python3 "$SKILL_DIR/scripts/codex_adapter.py" setup --scope user
```

Setup accepts only the standard hooks file for the selected scope, preserves unrelated entries, and is idempotent. It uses an atomic local write and rejects symbolic-link paths. It never runs during skill installation. Codex requires review and trust for new or changed non-managed hooks; inspect and trust the installed handler with `/hooks` before treating setup as active.

The adapter is a response-style convenience, not a security gate. Invalid hook input and internal rendering errors fail open; diagnostics go to stderr. Its one capsule preserves the core's `full` default and stop phrases. Commands such as `/super-caveman commit`, `/super-caveman review`, and `/super-caveman compress` remain canonical skill routes, not host hook state.

Remove only the adapter-owned entry with the matching explicit scope:

```bash
python3 "$SKILL_DIR/scripts/codex_adapter.py" uninstall --scope project --project-dir /absolute/path/to/project
python3 "$SKILL_DIR/scripts/codex_adapter.py" uninstall --scope user
```

## Optional Claude Code lifecycle adapter

The package also bundles an opt-in Claude Code adapter (`scripts/claude_adapter.py`). Like the Codex adapter it is off by default, never registered by ordinary skill installation, and reads no transcripts, session logs, or network resources. It registers two owned hooks in one explicitly selected Claude settings scope: a `SessionStart` handler for `startup`, `resume`, `clear`, and `compact`, and a `UserPromptSubmit` handler that resolves the five-layer state hierarchy (adapter installation, user default, project default, session state, one-shot state) on every prompt.

Resolve the current state at any time:

```bash
python3 "$SKILL_DIR/scripts/claude_adapter.py" status --project-dir /absolute/path/to/project
```

Choose one explicit adapter scope:

```bash
# Writes /absolute/path/to/project/.claude/settings.json
python3 "$SKILL_DIR/scripts/claude_adapter.py" setup --scope project --project-dir /absolute/path/to/project

# Writes ~/.claude/settings.json
python3 "$SKILL_DIR/scripts/claude_adapter.py" setup --scope user
```

Setup preserves unrelated settings entries, is idempotent, uses an atomic local write, and rejects symbolic-link paths. Claude Code requires review before new or changed hooks run; inspect and approve the two owned entries with `/hooks` before treating setup as active.

Persistent defaults are explicit and separate from session state:

```bash
# New sessions in this project start in full mode
python3 "$SKILL_DIR/scripts/claude_adapter.py" enable --scope project --mode full --project-dir /absolute/path/to/project

# Permanent opt-out at user scope (project explicit off still wins)
python3 "$SKILL_DIR/scripts/claude_adapter.py" disable --scope user
```

Effective mode precedence: session stop or session override, then the resumed session mode, then the project default (including explicit off), then the user default, then the neutral core with no automatic response shaping. Session mode switches (`/super-caveman <mode>` or `/caveman <mode>`) and the stop phrases (`stop super-caveman`, `stop caveman`, `stop adhd mode`, `normal mode`) affect only the current session. In Claude Code, a leading slash form is consumed by the host command layer before it reaches a prompt hook; the attempt-1 host receipt records this delivery finding, and until a host command file ships, submit the trigger forms where the host delivers them as prompt text (the stop phrases already work as plain phrases). `/super-caveman commit`, `review`, and `compress` are one-shot routes that restore the previous session mode; `status`, `help`, and `stats` never mutate state. Prompt reinforcement stays at most 1,024 characters and never re-emits the full startup capsule.

Remove only the adapter-owned entries with the matching explicit scope; add `--purge-state` to also remove adapter-owned defaults and session state:

```bash
python3 "$SKILL_DIR/scripts/claude_adapter.py" uninstall --scope project --project-dir /absolute/path/to/project [--purge-state]
python3 "$SKILL_DIR/scripts/claude_adapter.py" uninstall --scope user [--purge-state]
```

The adapter is a response-style convenience, not a security gate. Invalid hook input, oversized or corrupt state, symlinked paths, and internal errors fail open with diagnostics on stderr only. Rollback is the scoped `uninstall` above; it removes only the two owned hook entries and preserves unrelated Claude settings.

## Verification and rollback

Run the deterministic adapter checks from the repository root:

```bash
python3 -m unittest tests.test_super_caveman_codex_adapter tests.test_super_caveman_claude_adapter
python3 benchmarks/super-caveman/benchmark.py check
```

Deterministic adapter checks prove only the local configuration, the JSON protocol, and the normalized lifecycle contract. Deterministic evidence is not performance evidence, is not a host trust receipt, and is not promotion approval.

Rollback is the scoped `uninstall` of the selected adapter and scope; it removes only that adapter's owned hook entries and preserves unrelated host settings.
