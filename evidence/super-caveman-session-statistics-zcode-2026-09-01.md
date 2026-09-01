# Super Caveman exact session statistics receipt — zcode — 2026-09-01

This receipt records a redacted real-host check of what the zcode host exposes
as session counters for a current conversation. No temporary path, user
identity, account data or raw transcript appears in this file.

## Tested source

- Repository: TeFuirnever/azhou-ai-hub
- Local default-branch commit: 85447284c8953e7f1797b46146ad80e247b1d518 (merged main)
- Host: macOS 26.6.2 arm64, zcode headless CLI 0.16.5 (ZCode.app 3.10.2 bundle), Node.js 24.15.0
- Runs: two headless runs (fresh session, then -c resume), attempt-1 each

## Counters exposed (fresh run, attempt-1)

| Counter | Value |
|---|---|
| usage.source | provider |
| usage.modelRequestCount | 1 |
| usage.inputTokens | 41842 |
| usage.outputTokens | 65 |
| usage.totalTokens | 41907 |
| usage.cacheReadTokens | 32128 |
| usage.cacheWriteTokens | 0 |
| usage.reasoningTokens | 0 |
| usage.webFetchRequests | 0 |
| usage.webSearchRequests | 0 |
| projection.turnCount | 1 |
| projection.totalTokenCount | 41907 |
| projection.contextUsed | 41907 of a 200000 context window |

usage.totalTokens covers input plus output; cache-read tokens are listed
separately and are not double-counted in the total.

## Resume run observation

The -c resume returned the same session id and a fresh single-request usage
record (inputTokens 40859, modelRequestCount 1, turnCount 1), consistent with
the counters describing the current invocation rather than proven cumulative
accumulation. No accumulation claim is made.

## Findings

1. zcode --json exposes provider-attributed exact per-invocation counters:
   request count, input/output/total tokens, cache read/write tokens, reasoning
   tokens, web fetch/search request counts, plus a session projection with
   turnCount, totalTokenCount, contextUsed and contextWindow. These cover the
   measured fields the exact-statistics source priority demands.
2. The model id is not part of the counters payload; it appears only in the
   host's separate model I/O rollout, so no model claim is made from the
   counters themselves.
3. No cost or savings figures are exposed or derived. The host exposes no
   pricing table, and the statistics reference requires omitting cost and
   savings when pricing or attribution is missing.
4. No bundled log scanner exists in the package. The counters were exercised at
   the host CLI surface, never by scanning the host's private logs.
5. Multi-turn cumulative accumulation was not demonstrated. The resume-run
   shape is recorded above and no claim is made about it.

## Reproduction

1. Run zcode -p "Reply with exactly: OK-STATS" --json in any directory.
2. Read the usage and projection objects in the JSON output.
3. Optionally run a second prompt with -c and record the fresh-usage shape.

## Claim boundary

This receipt records exactly what zcode 0.16.5 exposes as host counters:
provider-attributed per-invocation usage plus a session projection, audited
counters for a current conversation at the host CLI surface. It does not prove
cumulative multi-turn accumulation, cost or savings derivation, GUI-surface
behavior, or parity with any other host. Full counter payloads stay
Git-external; nothing private is committed. Any support-matrix wording for
this row is staged separately with the promotion batch and is not claimed by
this receipt alone.
