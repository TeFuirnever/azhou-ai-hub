# LLM Wiki setup

## Runtime

- Python 3.11+
- Python standard library only
- Local filesystem access to the selected project root

No Node package, hosted database, MCP server, model API, or global configuration is required.

## Smoke check

~~~bash
SKILL_DIR=/absolute/path/to/llm-wiki
PROJECT_ROOT=/absolute/path/to/project

python3 "$SKILL_DIR/scripts/llm_wiki.py" --help
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" init
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" list
~~~

`init` creates a private-by-default `.llm-wiki/` store. Inspect the path before execution; the command writes `.gitignore` and `index.md` inside it.

## Legacy oh-my-claudecode store

Operate in place without copying or deleting data:

~~~bash
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" --store .omc/wiki list
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" --store .omc/wiki lint --no-log
~~~

This is the compatibility window and rollback path. Removing the skill does not remove either `.llm-wiki/` or `.omc/wiki/`. Do not contract or delete the legacy store as part of installation.

## Lifecycle adapter

The neutral adapter reads a JSON object from stdin. It supports `session-start`, `pre-compact`, and `session-end` events:

~~~bash
printf '%s\n' '{"cwd":"/absolute/path/to/project"}' | \
  python3 "$SKILL_DIR/scripts/llm_wiki.py" hook session-start
~~~

Do not install host hooks automatically. First verify the host's event names, stdin schema, stdout contract, timeout, recursion behavior, and failure policy. A host adapter must call this neutral core or remain a documented local example.

Session-end capture is off by default. Enabling it is a separate retention choice:

~~~bash
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" config --auto-capture true
~~~

The adapter stores only session metadata. It never reads a transcript. Disable with the same command and `false`.

## Environment snapshot

`capture-environment` accepts a reviewed JSON file and stores its SHA-256 digest in page sources. Inspect and redact the file before ingestion; the command does not infer that private host memory belongs to the project.
