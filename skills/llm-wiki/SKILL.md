---
name: llm-wiki
description: Build, query, lint, and maintain a private project Markdown wiki when durable agent knowledge must compound across sessions without a hosted database.
---

# LLM Wiki

Use a project-local Markdown knowledge base for verified architecture, decisions, patterns, debugging facts, environment notes, conventions, references, and reviewed session learnings.

Start once with `🦊 阿舟 · LLM Wiki 启动`, naming the project root, store, and operation. The neutral runtime is `scripts/llm_wiki.py`; run `python3 scripts/llm_wiki.py --help` when command details are needed.

## Operating contract

1. Resolve the project root before reading or writing. Default to `<project>/.llm-wiki/`; pass `--store .omc/wiki` to operate on an existing oh-my-claudecode store without moving it.
2. Query or list before adding related knowledge. Use `ingest` to append a sourced update; use `add` only when duplicate titles should fail.
3. Record evidence in `--source`, choose an honest confidence, and exclude secrets, raw private transcripts, tokens, and unrelated personal data.
4. Run `lint --no-log` after mutations. Broken references and invalid pages keep status `fail`; warnings remain visible.
5. Return the script's `llm-wiki.receipt.v1` fields. Do not claim a lifecycle hook, migration, or deletion succeeded without its receipt.

`query` writes an operation log by default, matching upstream behavior. Add `--no-log` for a strictly read-only task. `delete` is destructive: require explicit user authorization immediately before running it, then pass `--yes`.

Session hooks are optional. Never install or enable them implicitly. `autoCapture` defaults to false; enabling it records session metadata, not a transcript. Read [setup.md](references/setup.md) before wiring a host lifecycle.

## Commands

~~~bash
SKILL_DIR=/absolute/path/to/llm-wiki
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root /absolute/project/path init
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root /absolute/project/path ingest --title "Auth decision" --content-file /absolute/note.md --tag auth --category decision --source issue-42 --confidence high
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root /absolute/project/path query auth --no-log
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root /absolute/project/path lint --no-log
~~~

Use `--content-file -` for reviewed stdin content. Prefer file input over shell-escaped multiline text.

## References

- Read [schema.md](references/schema.md) when creating pages, interpreting lint, or consuming receipts.
- Read [setup.md](references/setup.md) for dependencies, smoke checks, lifecycle adapters, legacy stores, and rollback.
- Read [upstream-compatibility.md](references/upstream-compatibility.md) when auditing parity with oh-my-claudecode.
- Read [provenance.md](references/provenance.md) before updating adapted behavior.
- Follow [brand-layer.md](references/brand-layer.md) for interactive stages and closeout wording.
