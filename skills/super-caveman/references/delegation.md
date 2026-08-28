# Compact delegation

Use delegation to protect the main context, not to add ceremony. Prefer the host's configured equivalent role; never claim a preset exists before checking the available tool surface.

## Router

| Task | Route |
|---|---|
| Find a definition, caller, or use site | Investigator |
| Surgical edit in one or two known files | Builder |
| Review a diff for concrete defects | Reviewer |
| New feature, three or more files, or cross-cutting refactor | Main thread or architecture-capable worker |
| Deep review with rationale and alternatives | Full reviewer, not compressed reviewer |
| One-line answer already known | Main thread |

If the repository provides structural graph tools, query them before delegation. Pass project, generation, evidence tier, bounded scope, graph results, coverage state, direct-source fallback already performed, exact paths, and unresolved questions. If the child lacks graph tools, require direct reads of every relevant missed-coverage range.

## Contracts

Investigator:

```text
<Header>:
- path:line — `symbol` — short note
totals: <counts>.
```

Builder:

```text
<path:line-range> — <change in ten words or fewer>.
verified: <re-read OK | mismatch @ path:line>.
```

Reviewer:

```text
path:line: <severity>: <problem>. <fix>.
totals: <counts by severity>.
```

Accept terminal tokens `too-big.`, `needs-confirm.`, `ambiguous.`, and `regressed.` when they accurately stop unsafe work.

## Chaining

Use investigator, then builder, then reviewer only when each handoff adds evidence. Skip investigation when the exact site is already known. Do not send a five-file refactor to a one-or-two-file builder. Do not ask a compressed reviewer for broad architecture advice.

Security warnings and irreversible-action confirmations use full sentences.
