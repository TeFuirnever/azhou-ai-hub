# LLM Wiki setup

## Runtime

- Python 3.11+
- Python standard library only
- Local filesystem access to the selected project root

No Node package, hosted database, model API, or global configuration is required. CLI, MCP, migration, and lifecycle adapters ship together.

## Smoke check

~~~bash
SKILL_DIR=/absolute/path/to/llm-wiki
PROJECT_ROOT=/absolute/path/to/project

python3 "$SKILL_DIR/scripts/llm_wiki.py" --help
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" init
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" list
~~~

`init` creates `<project>/.azhou/llm-wiki/`, secures the directory to the current user, and writes its private-by-default `.gitignore` and generated `index.md`.

## MCP server

`scripts/llm_wiki_mcp.py` exposes seven tools over newline-delimited JSON-RPC stdio. Every call accepts an optional `workingDirectory`; every operation resolves `<workingDirectory>/.azhou/llm-wiki/`.

~~~bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | \
  python3 "$SKILL_DIR/scripts/llm_wiki_mcp.py"
~~~

Render a configuration fragment, review absolute paths, then merge only the emitted `llm-wiki` entry into the active MCP client configuration:

~~~bash
python3 "$SKILL_DIR/scripts/llm_wiki_adapter.py" render-mcp \
  --skill-dir "$SKILL_DIR" --python "$(command -v python3)"
~~~

The renderer prints JSON only. It never edits configuration files.

`wiki_delete` requires `confirm: true`. Set it only after the user directly authorizes that specific page deletion.

## Lifecycle adapter

The neutral event core supports `session-start`, `pre-compact`, and `session-end`. Direct smoke check:

~~~bash
printf '%s\n' '{"cwd":"/absolute/path/to/project"}' | \
  python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" hook session-start
~~~

Render command hooks for a compatible event host:

~~~bash
python3 "$SKILL_DIR/scripts/llm_wiki_adapter.py" render-hooks \
  --skill-dir "$SKILL_DIR" --python "$(command -v python3)"
~~~

Append each emitted group to the matching event array. Preserve unrelated hooks. `SessionStart` repairs a missing index and refreshes reserved `environment.md` from optional `.azhou/llm-wiki/project-context.json`. `PreCompact` emits a bounded reminder. `SessionEnd` does nothing until `autoCapture` is explicitly enabled:

~~~bash
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" config --auto-capture true
~~~

Disable with the same command and `false`. Capture stores a one-way session reference only; no raw session identifier or transcript is retained.

## Command asset

The explicit command template lives at `assets/host/commands/wiki.md`. Copy it only into a recognized command location after reviewing namespace rules. Test trigger classification without installation:

~~~bash
python3 "$SKILL_DIR/scripts/llm_wiki_adapter.py" trigger "wiki query"
~~~

## Migration and rollback

Dry-run a recognized prior store:

~~~bash
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" \
  migrate --from-store .llm-wiki
~~~

After reviewing `files`, `target`, `sourcePreserved`, and `autoCaptureReset`, apply:

~~~bash
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" \
  migrate --from-store .llm-wiki --apply --plan-id '<reviewed-planId>'
~~~

Migration refuses symlinks, active locks, unknown entries, invalid pages, invalid configuration, and target conflicts. It restores the private ignore rule, disables session capture, stages the full copy, rebuilds the index, then atomically publishes `.azhou/llm-wiki/`. The source remains untouched. Rollback means stop using the canonical store and return to the preserved source; deleting either directory is a separate destructive action.

## Environment snapshot

`capture-environment` accepts reviewed JSON and stores its SHA-256 digest in page sources. Inspect and redact the file first. For automatic local refresh, write the smaller reviewed context to `.azhou/llm-wiki/project-context.json`.
