# LLM Wiki production design

## Canonical store

All normal entrypoints resolve one project-local store: `<project>/.azhou/llm-wiki/`. CLI, MCP, lifecycle events, project context, generated index, operation log, and configuration share the same `WikiStore` core. Alternate paths exist only as explicit migration sources.

~~~text
CLI ───────────────┐
MCP stdio ─────────┼──> WikiStore ──> .azhou/llm-wiki/
lifecycle adapter ─┘        │
                            ├── atomic page writes
                            ├── store-wide lock
                            ├── generated index
                            └── append-only operation log
~~~

The MCP and lifecycle layers translate protocols only. They do not fork storage, search, lint, or mutation semantics.

## Trust boundaries

- `workingDirectory`, migration source, page names, and content are untrusted inputs.
- Store paths must remain relative to the project root; symlinked store paths and page/log/config links are rejected.
- Writes use same-directory temporary files and atomic replacement. The store directory is restricted to the current user.
- `wiki_delete` and CLI `delete` require an explicit destructive checkpoint.
- Lifecycle capture defaults off, stores metadata only, and never reads transcripts.
- Configuration renderers return JSON only; installation remains a human-controlled action.
- Brand anchors stay in the interactive presentation layer; CLI, MCP, hooks, schemas, paths, and raw evidence remain emoji-free.

## Failure modes

| Failure | Required behavior |
|---|---|
| malformed page or config | return a named failure; never guess |
| active store lock | bounded wait, then observable failure |
| symlink or escaping path | reject before reading or writing |
| interrupted migration | target remains absent; source remains unchanged |
| existing target conflict | reject before any migration write |
| missing store during lifecycle event | continue without creating data |
| invalid hook input | fail open for the host; emit no private content |

## Migration and rollback

Migration uses expand, verify, then contract:

1. `migrate --from-store <recognized-path>` inventories and validates without writing, then emits a stable `planId`.
2. `--apply --plan-id <reviewed-planId>` rejects changed plans before copying approved text files into a private staging directory.
3. Session capture is reset to false, the index is rebuilt, and the staged directory is atomically renamed to `.azhou/llm-wiki/`.
4. Repeating the same migration returns `already-current`; divergent targets fail.
5. The source is never deleted. It is the rollback copy until separately authorized contraction.

## Production gates

Release requires all of these:

1. Product-surface negative scan contains no historical path, brand, or host-specific term outside mandatory legal provenance.
2. Fixed Azhou stage anchors map honestly to receipt v2; machine outputs contain no brand emoji.
3. CLI, seven MCP tools, and three lifecycle events pass real-process integration tests against `.azhou/llm-wiki/`.
4. Migration proves dry-run, atomic apply, idempotent retry, conflict rejection, privacy reset, and source preservation.
5. Repository policy, unit tests, benchmark-integrity suites, whitespace checks, and knowledge-graph coverage pass with no unreviewed code gaps.
