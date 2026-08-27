# LLM Wiki schema

## Storage

The default store is `<project>/.llm-wiki/`:

~~~text
.llm-wiki/
├── .gitignore     private-by-default boundary
├── config.json    optional lifecycle configuration
├── index.md       generated catalog
├── log.md         append-only operation chronicle
└── <slug>.md      Markdown knowledge pages
~~~

`index.md`, `log.md`, and `environment.md` are reserved. Page paths must stay directly inside the selected store. Writes use a store-wide lock and same-directory atomic replacement.

## Page frontmatter

Every page contains these fields:

| Field | Meaning |
|---|---|
| `title` | human-readable title; its deterministic slug identifies the page |
| `tags` | search terms |
| `created`, `updated` | ISO timestamps |
| `sources` | session IDs, issue IDs, evidence digests, or other provenance |
| `links` | filenames derived from `[[Wiki Link]]` references |
| `category` | `architecture`, `decision`, `pattern`, `debugging`, `environment`, `session-log`, `reference`, or `convention` |
| `confidence` | `high`, `medium`, or `low` |
| `schemaVersion` | currently `1` |

`ingest` never replaces existing content. It unions tags, sources, and links; keeps the higher confidence; and appends a timestamped update section. The original category remains stable.

## Query

Search stays local and deterministic. It uses exact tag filters, weighted title/tag/content matching, Latin tokens, CJK characters and CJK bigrams. It does not use embeddings or an external model.

## Lint

Lint reports orphan, stale, broken-reference, low-confidence, oversized, structural-contradiction, and invalid-page findings. Broken references and invalid pages produce command status `fail`; warnings and informational findings do not.

## Receipt

Every command emits one JSON object with schema `llm-wiki.receipt.v1`:

~~~text
schema, status, operation, store, result,
changes, verification, holds, nextAction
~~~

`pass`, `fail`, `hold`, and `skipped` remain distinct. A query with `--no-log` has no changes. A delete without `--yes` returns `hold` and exit code 3.
