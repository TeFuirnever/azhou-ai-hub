# Dependencies and setup

Read this before using the bundled history or evidence scripts, or when a command is unavailable.

## Runtime requirements

| Capability | Requirement | Used by |
|---|---|---|
| Python | 3.10 or newer; standard library only | inventory, lifecycle hook, evolution, history, and evidence scripts |
| Git | any maintained version | repository diff and final verification |
| ripgrep (`rg`) | optional but recommended | fast text and stale-path checks |

`super-repo-pedant` has no third-party Python package and no model- or harness-specific dependency. Do not run `pip install` for this skill.

For repository development, install the package under its canonical name with a soft link:

```bash
REPO_ROOT=/absolute/path/to/azhou-ai-hub
SKILLS_HOME=/absolute/path/to/harness/skills
ln -s "$REPO_ROOT/skills/super-repo-pedant" "$SKILLS_HOME/super-repo-pedant"
```

Remove an existing `neat-freak` installation only after explicit user confirmation. Do not create a compatibility alias unless the user asks for one.

## Discovery refresh

A task opened before installation may keep an older skill-picker catalog even when the soft link and `SKILL.md` are valid. Resolve it in this order:

1. verify the canonical link with `readlink <skills-home>/super-repo-pedant`;
2. invoke `$super-repo-pedant` (or the compatibility name `$repo-pedant`) literally in the current task;
3. if the runtime still does not load it, start a new task or reload the harness.

Do not add another `super-repo-pedant` copy or link under a second skill root merely to refresh discovery. Duplicate canonical names create ambiguous ownership and update paths.

## Preflight

```bash
python --version
git --version
rg --version
```

If Python, Git, or ripgrep is missing, install it with the operating system's package manager. Keep the install outside the skill directory; do not modify global agent or harness configuration.

## Verify the bundled scripts

Set `SKILL_DIR` to the installed `super-repo-pedant` directory:

```bash
SKILL_DIR=/absolute/path/to/super-repo-pedant
python "$SKILL_DIR/scripts/collect_agent_history.py" --help
python "$SKILL_DIR/scripts/validate_evidence_bundle.py" --help
python "$SKILL_DIR/scripts/inventory_knowledge.py" --help
python "$SKILL_DIR/scripts/closeout_hook.py" --help
python "$SKILL_DIR/scripts/manage_evolution.py" --help
python "$SKILL_DIR/scripts/validate_execution_protocol.py" --help
```

The collector reads local Codex, Claude, or zcode history only when explicitly requested. It does not need network access. Excerpt output is opt-in, local-only, and must remain outside Git.

## Local runtime state

Inventory, execution records, closeout markers, hook counters, and evolution candidates default to `.azhou/super-repo-pedant/` inside the affected project. Treat that directory as local working state unless the project explicitly adopts a tracked receipt format. Add it to the project's ignore rules only when authorized; do not edit ignore files from an inferred trigger.

Inventory v2 requires one memory decision per project. Pass an enumerated memory candidate or explicit discovery evidence:

```bash
python "$SKILL_DIR/scripts/inventory_knowledge.py" snapshot \
  --project /absolute/project \
  --memory /absolute/project-memory/MEMORY.md

python "$SKILL_DIR/scripts/inventory_knowledge.py" snapshot \
  --project /absolute/project \
  --memory-decision 'none_discovered::checked repository MEMORY.md and active harness project-memory path'

# Full form with global-instruction candidate and an explicit output path:
python "$SKILL_DIR/scripts/inventory_knowledge.py" snapshot \
  --project /absolute/project \
  --memory /absolute/project-memory/MEMORY.md \
  --global-instruction /absolute/global-instructions.md \
  --output /absolute/project/.azhou/super-repo-pedant/inventory.json
```

A single-project snapshot defaults to `.azhou/super-repo-pedant/inventory.json`; multi-project runs require an explicit `--output`. Validate execution state without a path to read `.azhou/super-repo-pedant/execution.json` from the current project.

To import a prior state root, review and bind one explicit migration plan. Two compatibility sources are recognized: the legacy `.repo-pedant/` directory (default `--source`) and the pre-rename `.azhou/repo-pedant/` namespace:

```bash
python "$SKILL_DIR/scripts/migrate_state.py" --project /absolute/project
python "$SKILL_DIR/scripts/migrate_state.py" \
  --project /absolute/project --apply --plan-id '<reviewed-planId>'
python "$SKILL_DIR/scripts/migrate_state.py" \
  --project /absolute/project --source .azhou/repo-pedant
```

The source is preserved. Normal commands and hooks do not read it after migration.

Use `hold` instead of `none_discovered` when a candidate cannot be inspected or ownership is unresolved. Multi-project runs prefix memory paths and decisions with `PROJECT_ROOT::`.

The optional hook stores only gate counters under `.azhou/super-repo-pedant/hooks/`. It never stores document or transcript bodies.

Hook fragments are rendered, never copied by hand: run the renderer, review the absolute paths, then merge the printed JSON into the host's supported configuration and run the doctor command from [trigger-hooks.md](trigger-hooks.md). Skill installation alone does not install hooks.

```bash
python "$SKILL_DIR/scripts/closeout_hook.py" render-hooks --format claude
python "$SKILL_DIR/scripts/closeout_hook.py" render-hooks --format codex
```

Host shell premise: rendered commands are POSIX shell syntax executed by the host shell — on Windows this requires Git Bash (a PowerShell fallback is outside the supported claim). Pass `--python` to bind a different host interpreter. The event core is fail-open and always exits 0 in advisory mode.
