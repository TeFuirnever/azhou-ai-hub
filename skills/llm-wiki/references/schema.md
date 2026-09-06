# LLM Wiki schema

## Storage

The default store is `<project>/.azhou/llm-wiki/`:

~~~text
.azhou/llm-wiki/
├── .gitignore     private-by-default boundary
├── config.json    optional lifecycle configuration
├── project-context.json  optional reviewed lifecycle input
├── .archive-lock.json  archived-page content hashes and archival metadata
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
| `lifecycle` | optional, decision pages only: `proposed`, `implemented`, `archived`, or `rejected`; any other value, or the field on another category, makes the page invalid |
| `schemaVersion` | currently `1` |

`ingest` never replaces existing content. It unions tags, sources, and links; keeps the higher confidence; and appends a timestamped update section. The original category and lifecycle remain stable.

## Query

Search stays local and deterministic. It uses exact tag filters, weighted title/tag/content matching, Latin tokens, CJK characters and CJK bigrams. It does not use embeddings or an external model.

## Archive

`archive --title <t>` freezes a decision page whose lifecycle is `implemented`: the lifecycle becomes `archived`, the page's exact bytes are hashed into `.archive-lock.json` together with the archival timestamp, and the page is byte-frozen from then on. `archived` is reachable only through this command — creation refuses `--lifecycle archived`. Each lock entry records `{sha256, archivedAt, title}` per page; archival metadata lives in the lock, never in the page. `ingest` and `delete` both refuse archived pages, and lint recomputes every lock hash: a changed byte, a missing archived page, an `archived` page without a lock entry, or a corrupt/invalid lock file each fail lint. A hand-edited page stuck in `archived` without a lock is remediated by restoring `lifecycle: implemented` and running `archive`.

## Lint

Lint reports orphan, stale, broken-reference, low-confidence, oversized, structural-contradiction, missing-alternatives, archive-tamper, unfrozen-archived, and invalid-page findings. A `decision` page in the `implemented` or `rejected` lifecycle without an `## Alternatives considered` section is a missing-alternatives error: recorded alternatives prevent re-litigating a settled decision. Broken references, invalid pages, missing-alternatives, archive-tamper, and unfrozen-archived findings produce command status `fail`; warnings and informational findings do not.

## Receipt

Every command emits one JSON object with schema `llm-wiki.receipt.v2`:

~~~text
schema, status, operation, store, currentTruth, result,
changes, verification, holds, nextAction, learningSignal
~~~

`currentTruth` states the bounded post-operation fact without copying page content or private input. `learningSignal` is one of `none`, `scope`, `source`, `privacy`, `retrieval`, `write`, `lint`, `migration`, `lifecycle`, `deletion`, or `config`.

`pass`, `fail`, `hold`, and `skipped` remain distinct. A query with `--no-log` has no changes. A CLI delete without `--yes` returns `hold` and exit code 3; MCP deletion rejects calls unless `confirm` is exactly `true`.
