# pstack host registration inventory and outstanding acceptance — 2026-11-11

**Scope:** read-only checks on the maintainer's connected Mac on 2026-11-11, plus existing committed historical receipts. No plugin installation, update, cache removal, model-sheet rewrite, Hook trust confirmation, task execution, rebasing, or host restart occurred in this audit.

**Environment limit:** the authorized Desktop Commander connection reached its monthly usage quota after the read-only inventory. New live tests are unavailable through that channel for this pass. This document preserves what was actually observed and assigns explicit **UNVERIFIED** status to everything else. Later CI or a plugin list cannot replace a missing host execution receipt.

## Inputs and exact identities

| Layer | Source / observation | Meaning |
| --- | --- | --- |
| Repository review head | `TeFuirnever/azhou-ai-hub@main` `e633c9b8261254e9f72ec51bbb0b98d276cf261a` at audit start | Clean baseline for this evidence pass |
| Hub upstream input | `cursor/plugins@c742dd61706fbacc1b95f1a20b7b988cf096ce6c`; pristine `pstack/plugin.json` `0.15.36` | Immutable source pin, not the installed plugin version |
| Hub distribution | `packages/pstack-agent-harness/hub-package.json` `0.15.37`; 23-patch quilt | Release candidate content; native host attestation still required |
| Mirror main | `backnotprop/pstack@main` `08547969e1dffaa6457ea65141cc62c1d9a2eef1` | Independent harness-neutral mirror overlay, not the Hub build source |
| Local git | `main...origin/main` with no changed files at the first read-only inspection | No checkout modification during that first inspection |

## Read-only observations

| Host / surface | Actual command or inspected path | Observed result | Claim limit |
| --- | --- | --- | --- |
| Codex (native plugin) | `codex plugin list` | `pstack-azhouzhou@pstack-claude`: `installed, enabled`, version `0.15.37`, source `packages/pstack-agent-harness/harness/pstack/codex` | **REGISTERED**, not a live Skill or Hook pass |
| Codex cached manifests | `~/.codex/plugins/cache/pstack-claude/pstack-azhouzhou/0.15.37/` | Matching plugin manifests observed in cache | Cache existence is not a complete source-lock or runtime attestation |
| Claude Code (native plugin) | `claude plugin list` | `pstack-azhouzhou@pstack-claude`, version `0.15.37`, source `packages/pstack-agent-harness/harness/pstack/claude-code` | **LISTED**, not a live invocation or lifecycle pass |
| Claude cache | `~/.claude/plugins/cache/pstack-claude/pstack-azhouzhou/0.15.36/` | Older-version cache directory observed | Does not establish that `0.15.36` is loaded or conflicting |
| Codex model sheet | `~/.codex/pstack-models.md` | `session hook: on` line present | **CONFIGURED**, not confirmed Hook trust or delivery |
| Claude model sheet | `~/.claude/pstack-models.md` | `session hook: on` line present | **CONFIGURED**, not confirmed Hook trust or delivery |
| ZCode | `zcode plugins list` attempted from the active PATH | Binary not found in this shell; some ZCode plugin data and a model sheet exist | **INCONCLUSIVE**; no claim of active plugin |
| MiMo Code | Repository historical support evidence | Discovery-only historical receipts | No new 2026-11-11 model invocation |
| DeepSeek Harness | Repository historical `2026-11-02` receipt | 68 pstack Skills discoverable through shared root | No new 2026-11-11 native invocation, hook or session-store proof |

The remote checks returned exit code 0 for `codex plugin list` and `claude plugin list` and reported the specific identities above. Long catalog outputs were filtered before being summarized here. They did **not** capture a frozen digest of the active loaded plugin bytes or a real task's event trace. Never infer a full-verification verdict from these short result lines.

## Host acceptance matrix

**Status vocabulary:** `OBSERVED` = a same-day direct read or command, `HISTORICAL` = a prior dated receipt bound to different known inputs, `UNVERIFIED` = no current version-bound proof, `UNAVAILABLE` = this pass could not execute the host command, and `NOT APPLICABLE` = host does not expose that surface.

| Gate | Codex 0.15.37 | Claude 0.15.37 | ZCode | MiMo | DeepSeek |
| --- | --- | --- | --- | --- | --- |
| Native registration | OBSERVED | OBSERVED | UNAVAILABLE | NOT APPLICABLE | NOT APPLICABLE |
| 68 Skills discoverable at current installed bytes | UNVERIFIED | UNVERIFIED | UNVERIFIED | HISTORICAL shared-root discovery | HISTORICAL 68 shared-root discovery |
| Real `how`/poteto-mode invocation | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| Current model/effort dispatch | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| SessionStart permission, injection, delivery | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| PR watcher + review gate end-to-end | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| Isolated install/remove/rollback with current exact bytes | HISTORICAL earlier candidate | HISTORICAL earlier candidate | UNVERIFIED | NOT APPLICABLE | NOT APPLICABLE |
| Current-version unattended restart/continuation | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED |

## Release and safety holds

| Hold | Affected action | Evidence | Owner | Clear only when |
| --- | --- | --- | --- | --- |
| H1 | Promote `0.15.37` as a fully host-validated release | Native plugin lists confirm registration only; source-lock/host execution missing | pstack distribution maintainer | Exact loaded-source digest, live Skill run, model dispatch and trustworthy host lifecycle receipts are captured |
| H2 | Install pstack into the default Codex home that previously hosted the retired Agent Orchestration Kit | `session hook: on` observed in default sheet at inventory time; the Kit coexistence contract that would have required `session hook: off` was removed by HUB-RET-001 (historical, no longer obtainable) | Codex integration owner | Follow the supported retirement path instead of the retired verdict: remove the retired Kit with its retained pre-deletion uninstaller before installing pstack (README "Retired surfaces"), and expect `scripts/integration_pstack.py` to refuse an unowned target whose `config.toml` still mentions the retired router. No silent model sheet rewrite |
| H3 | Declare Claude live parity | CLI lists `0.15.37`, but older cache directory exists and live invocation has not been exercised | Claude adapter owner | Inspect active native registry source and exact loaded content, run host invocation and Hook receipt |
| H4 | Declare ZCode native plugin active or GUI-supported | `zcode` CLI unavailable on inspected PATH | ZCode integration owner | Locate explicit supported host binary, run native list and GUI invocations with receipts |
| H5 | Claim Windows / Pi / OpenCode equivalence | Hub maintains only five target harnesses and mirror portability is not acceptance evidence | Maintainer | Explicitly expand support targets and independently validate; otherwise remain unsupported |

**H2 is a conditional integration hold, not a finding that the Kit is currently active in that specific `CODEX_HOME`.** Do not change configuration based on the `on` line alone. (2026-11-13 correction: H2's original exit criterion — obtaining the shared Kit coexistence verdict — references a mechanism HUB-RET-001 removed; the actionable path is now the supported uninstall-then-install sequence above.)

## Next executable verification runbook (not executed)

1. From an owned, isolated checkout, freeze `git HEAD`, complete index/working-tree state and distribution `runtime_paths` digests. Read `docs/integrations.md` and the native host's registry. Check that no other actor owns the target profile. Do not use the default `~/.codex` or `~/.claude` for experimental changes.
2. Read `codex plugin list`, `claude plugin list`, and supported native details for the installed plugin. Resolve the actual loaded manifest, cache/source path, plugin version and source bytes. Record digests before and after.
3. In a disposable, explicit home and fixture workspace, run a **read-only** `how` or investigation task using the actual installed pstack entry point. Capture command, session start, active Skill path, exit result, and transcript; do not infer any part from skill-discovery output.
4. Test a single explicit subagent role and effort dispatch against a safe fixture. Inspect actual child metadata and closeout. Then run an independent reviewer of a known frozen test change.
5. Probe SessionStart only in a safe, newly created session where required permissions are expressly approved. Verify event delivery and the configured `session hook` behavior. Do not change or auto-approve production trust settings.
6. Execute PR watcher fixtures using the test harness with CI/no-check, mergeability changes, pagination, review-thread and failure cases; no real merge. Run `node tools/build-harness.mjs`, the targeted generated tests, then `python3 scripts/verify.py` against frozen source.
7. Exercise install → doctor → remove → reinstall → remove **only in a disposable controlled home**, preserving all unrelated existing files and lease ownership, and capture recovery evidence.
8. Repeat host-specific gates separately on Claude, ZCode, MiMo and DeepSeek. Mark unsupported hooks as `NOT APPLICABLE` only after confirming the host capability contract.
9. Compare frozen identities and receipts and independently review failures. A change in installed bytes, worktree head, model-sheet bytes, host version or authorization invalidates a prior version-bound verdict.

## Relationship to historical evidence

- [Native isolated lifecycle, 2026-11-05](pstack-native-isolated-lifecycle-2026-11-05.md) proved a constrained `0.15.36` isolation/rollback sequence, not current `0.15.37` live invocation.
- [CodeQL and version triage, 2026-11-06](pstack-codeql-and-version-triage-2026-11-06.md) explicitly called `0.15.37` a new **candidate**, not installed **at that time**. The 2026-11-11 CLI state is newer and does not retroactively rewrite that historical fact.
- [PR 372 review remediation, 2026-11-06](pstack-pr372-codex-review-fixes-2026-11-06.md) describes package and host-safety tests on that candidate; it does not attest the current default desktop host.
- [Mirror GAP and 17-patch triage](../docs/research/2026-11-11-pstack-upstream-gap.md) record remaining upstream-only differences and release-safe patch management.

**Result of this pass:** updated, evidence-bounded release holds and installed-version inventory. **No newly passed end-to-end host acceptance**, no CI execution, no plugin promotion, and no claim that all five maintained harnesses are operationally equivalent.
