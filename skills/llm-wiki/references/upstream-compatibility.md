# oh-my-claudecode LLM Wiki compatibility

Baseline: oh-my-claudecode `4.14.6`, commit `deee3a446dadc9bfea31cdc8b19b00b16718082e`.

| Upstream capability | Azhou implementation | Status |
|---|---|---|
| `wiki_ingest` create-or-append | `ingest` with tag/source/link union and higher-confidence merge | preserved |
| `wiki_query` keyword, tag, category and limit | `query`; same weights, CJK characters/bigrams, no embeddings | preserved |
| `wiki_lint` health checks | `lint`; adds invalid-frontmatter reporting | preserved and hardened |
| `wiki_add` fail on duplicate | `add` | preserved |
| `wiki_list` | `list` | preserved |
| `wiki_read` | `read` | preserved |
| `wiki_delete` | `delete --yes` after explicit authorization | preserved with safety checkpoint |
| Markdown frontmatter schema v1 | same field names and category/confidence values | preserved |
| `.omc/wiki/` storage | supported in place with `--store .omc/wiki`; neutral default is `.llm-wiki/` | compatibility path |
| atomic writes and wiki-wide lock | standard-library atomic replacement and lock file | preserved |
| `index.md` and `log.md` | generated catalog and append-only operation log | preserved |
| query/lint logging | default on; `--no-log` adds a read-only path | preserved and extended |
| session-start bounded context | `hook session-start` or `context` | preserved through neutral adapter |
| pre-compact context | `hook pre-compact` | preserved through neutral adapter |
| session-end metadata capture | `hook session-end`; opt-in `autoCapture` | preserved, default changed for privacy |
| implicit `.claude/project-memory.json` feed | explicit `capture-environment --input` with source digest | host coupling replaced |
| automatic Claude hook installation | none | deliberately excluded; no proven cross-host equivalence |

The package does not expose the seven operations as MCP tools. Agent Skills provide the interaction surface; one neutral CLI supplies deterministic behavior across harnesses. A host may wrap the CLI, but the wrapper must not fork the storage semantics.
