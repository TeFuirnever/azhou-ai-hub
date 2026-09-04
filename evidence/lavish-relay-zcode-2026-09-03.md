# Lavish relay mode receipt — zcode — 2026-09-03

This receipt records a redacted real-host check that the zcode host loads the merged `lavish` package and drives its Spec Relay relay-mode CLI end to end from a linked install, including the optimistic stale-revision rejection. It contains no user identity, account data or raw transcript. This is the first receipt recorded against the merged single-package `lavish` (relay mode landed by the spec-relay merge); the earlier `spec-relay-review-loop-zcode-2026-09-02.md` receipt covers the pre-merge standalone package.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `cb8a26efe8cee76eea850a256599c6d2bd2b0bf4` (the linked user-scope package resolves to this content, including `scripts/relay_state.py` moved byte-identical from the merged `skills/spec-relay/`)
- Host: macOS (Apple Silicon), zcode GUI app session (interactive; user-scope Agent Skills root)
- Mode: interactive GUI session driving the relay CLI on a disposable fixture packet at a Git-external temp path, attempt-1

## Install step

Same Foundation CLI linked install as the eli5 receipt of this date (`--plan-id 8d64ab4ad4a26f348e9e1c767d771f8dcb32bd5cad0a15de6cb600149273d7fd`, apply exit `0`); the prior stale `lavish` copy (an August 18 pre-relay-merge snapshot without `references/` or `scripts/`) was moved Git-external to a backup directory before linking, disclosed here.

## Results

| Check | Result | Evidence |
|---|---|---|
| Merged package load with relay scripts | `PASS` | The linked install resolves `scripts/relay_state.py` inside the canonical `lavish` package. |
| `init` — portable relay state embedded | `PASS` | `initialized spec-relay.html-state.v1: <temp>/packet.html` on a one-requirement fixture with source spec, revision, review goal and status. |
| `add-feedback` — persist with expected revision | `PASS` | `persisted FB-001: <temp>/packet.html` with target `REQ-001`, selection, disposition, rationale and owner. |
| `validate` — exact visible-ledger check | `PASS` | `valid spec-relay.html-state.v1: packet=e7d0ca99-b01d-49e1-9360-325bb232918d revision=1 feedback=1 unresolved=0`. |
| Optimistic stale-revision rejection | `PASS` | A second `add-feedback` with `--expected-revision 0` against the now-current revision 1 was refused: `spec-relay: stale state revision: expected 0, current 1`, exit `1`, packet unchanged. |

## Claim boundary

This proves the zcode GUI host loads the merged `lavish` package and that the relay-mode CLI lifecycle (init, feedback persist, ledger validation, stale-copy rejection) completes from a linked install on this machine, attempt-1. It does not prove the browser-review/foreground-poll route (the autocompact guard disclosed in `spec-relay-review-loop-zcode-2026-09-02.md` still applies), the artifact-mode review loop beyond the 2026-09-02 receipt, or third-party sharing (which requires separate authorization). Raw fixtures stay Git-external; nothing private is committed.
