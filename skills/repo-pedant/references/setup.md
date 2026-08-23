# Dependencies and setup

Read this before using the bundled history or evidence scripts, or when a command is unavailable.

## Runtime requirements

| Capability | Requirement | Used by |
|---|---|---|
| Python | 3.10 or newer; standard library only | inventory, lifecycle hook, evolution, history, and evidence scripts |
| Git | any maintained version | repository diff and final verification |
| ripgrep (`rg`) | optional but recommended | fast text and stale-path checks |

`repo-pedant` has no third-party Python package and no model- or harness-specific dependency. Do not run `pip install` for this skill.

For repository development, install the package under its canonical name with a soft link:

```bash
REPO_ROOT=/absolute/path/to/azhou-ai-hub
SKILLS_HOME=/absolute/path/to/harness/skills
ln -s "$REPO_ROOT/skills/repo-pedant" "$SKILLS_HOME/repo-pedant"
```

Remove an existing `neat-freak` installation only after explicit user confirmation. Do not create a compatibility alias unless the user asks for one.

## Discovery refresh

A task opened before installation may keep an older skill-picker catalog even when the soft link and `SKILL.md` are valid. Resolve it in this order:

1. verify the canonical link with `readlink <skills-home>/repo-pedant`;
2. invoke `$repo-pedant` literally in the current task;
3. if the runtime still does not load it, start a new task or reload the harness.

Do not add another `repo-pedant` copy or link under a second skill root merely to refresh discovery. Duplicate canonical names create ambiguous ownership and update paths.

## Preflight

```bash
python3 --version
git --version
rg --version
```

If Python, Git, or ripgrep is missing, install it with the operating system's package manager. Keep the install outside the skill directory; do not modify global agent or harness configuration.

## Verify the bundled scripts

Set `SKILL_DIR` to the installed `repo-pedant` directory:

```bash
SKILL_DIR=/absolute/path/to/repo-pedant
python3 "$SKILL_DIR/scripts/collect_agent_history.py" --help
python3 "$SKILL_DIR/scripts/validate_evidence_bundle.py" --help
python3 "$SKILL_DIR/scripts/inventory_knowledge.py" --help
python3 "$SKILL_DIR/scripts/closeout_hook.py" --help
python3 "$SKILL_DIR/scripts/manage_evolution.py" --help
python3 "$SKILL_DIR/scripts/validate_execution_protocol.py" --help
```

The collector reads local Codex, Claude, or zcode history only when explicitly requested. It does not need network access. Excerpt output is opt-in, local-only, and must remain outside Git.

## Local runtime state

Inventory, execution records, closeout markers, and evolution candidates default to `.repo-pedant/` inside the affected project. Treat that directory as local working state unless the project explicitly adopts a tracked receipt format. Add it to the project's ignore rules only when authorized; do not edit ignore files from an inferred trigger.

Inventory v2 requires one memory decision per project. Pass an enumerated memory candidate or explicit discovery evidence:

```bash
python3 "$SKILL_DIR/scripts/inventory_knowledge.py" snapshot \
  --project /absolute/project \
  --memory /absolute/project-memory/MEMORY.md \
  --output /absolute/project/.repo-pedant/inventory.json

python3 "$SKILL_DIR/scripts/inventory_knowledge.py" snapshot \
  --project /absolute/project \
  --memory-decision 'none_discovered::checked repository MEMORY.md and active harness project-memory path' \
  --output /absolute/project/.repo-pedant/inventory.json
```

Use `hold` instead of `none_discovered` when a candidate cannot be inspected or ownership is unresolved. Multi-project runs prefix memory paths and decisions with `PROJECT_ROOT::`.

The optional hook stores only gate counters under `XDG_CACHE_HOME/repo-pedant/hooks/` or the platform-equivalent user cache. It never stores document or transcript bodies.

Hook fragments live under `assets/hooks/`. Copy the relevant fragment into the host's supported configuration, replace `/absolute/path/to/repo-pedant`, then run the doctor command from [trigger-hooks.md](trigger-hooks.md). Skill installation alone does not install hooks.
