---
name: llm-wiki
description: Build, query, lint, migrate, and maintain a private project Markdown wiki when verified architecture, decisions, debugging facts, or conventions must persist across sessions. Do not use it for global memory, ephemeral scratch notes, secrets, or unreviewed transcripts.
---

# LLM Wiki

**🦊 阿舟 · LLM Wiki**

> 📚 知识要留得住，也要经得起查证。

Use a project-local Markdown knowledge base for verified architecture, decisions, patterns, debugging facts, environment notes, conventions, references, and reviewed session learnings.

## Brand and progress

For an interactive run, read [brand-layer.md](references/brand-layer.md), then start exactly once:

```text
🦊 阿舟 · LLM Wiki 启动｜operation=<operation>｜scope=<project-root>
```

Use one fixed anchor per completed material stage. Keep machine JSON, paths, commands, schema values, page content, and raw evidence emoji-free. Never emit `✅ 验证通过` after a `fail`, `hold`, or `skipped` machine receipt. A host without Unicode may remove emoji without changing prefixes, separators, fields, or values.

Every runtime entry uses the canonical `<project>/.llm-wiki/` store. The CLI is `scripts/llm_wiki.py`; the optional stdio MCP server is `scripts/llm_wiki_mcp.py`.

## Operating contract

1. Resolve the project root before reading or writing. Normal operations never select an alternate store.
2. Query or list before adding related knowledge. Use `ingest` to append a sourced update; use `add` only when duplicate titles should fail.
3. Record evidence in `--source`, choose an honest confidence, and exclude secrets, raw private transcripts, tokens, and unrelated personal data.
4. Run `lint --no-log` after mutations. Broken references and invalid pages keep status `fail`; warnings remain visible.
5. Return the script's `llm-wiki.receipt.v2` fields, including `currentTruth` and `learningSignal`. Do not claim a lifecycle event, migration, or deletion succeeded without its receipt.

`query` writes an operation log by default. Add `--no-log` for a strictly read-only task. `delete` is destructive: require direct user authorization immediately before running it, then pass `--yes`.

Lifecycle wiring is optional and explicit. `autoCapture` defaults to false, records only session metadata when enabled, and never reads transcripts. Rendered configuration is review-only and never mutates host files.

## Commands

~~~bash
SKILL_DIR=/absolute/path/to/llm-wiki
PROJECT_ROOT=/absolute/path/to/project

python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" init
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" ingest --title "Auth decision" --content-file /absolute/note.md --tag auth --category decision --source issue-42 --confidence high
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" query auth --no-log
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" lint --no-log
~~~

Use `--content-file -` for reviewed stdin content. Prefer file input over shell-escaped multiline text.

Configured MCP clients receive exactly seven tools: `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_add`, `wiki_list`, `wiki_read`, and `wiki_delete`. Apply the same evidence, privacy, lint, and deletion checkpoints as the CLI; `wiki_delete` requires `confirm: true` after direct authorization.

## Migration checkpoint

Normal operations never read another store. To preserve data from any prior project-relative directory, run `migrate --from-store <path>` first for a dry-run receipt, review conflicts and file counts, then rerun with `--apply`. Migration creates the canonical store atomically, resets session capture to false, and never deletes the source.

## References

- Read [design.md](references/design.md) for architecture, trust boundaries, failure modes, migration, rollback, and production gates.
- Read [schema.md](references/schema.md) when creating pages, interpreting lint, or consuming receipts.
- Read [setup.md](references/setup.md) for MCP, lifecycle, smoke checks, migration, and rollback.
- Read [provenance.md](references/provenance.md) before updating adapted behavior or notices.
- Follow [brand-layer.md](references/brand-layer.md) for interactive stages and closeout wording.
