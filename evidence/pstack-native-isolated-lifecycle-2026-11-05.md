# pstack native Codex isolated install/reinstall/rollback — 2026-11-05

## Candidate

Source branch: codex/pstack-namespace-sweep-20261105.
Source commit: 3e3135e92cdaa55d44acde84f3b385b3e925127d.
Frozen source lock SHA-256: 9c788a50173b7f25bab5e95896b933e567c2e61e5803de3f097491d8c433409e.
Plugin identity: pstack-azhouzhou@pstack-claude, manifest version 0.15.36.

The test uses ChatGPT Desktop's bundled native Codex executable but a
fresh and separate CODEX_HOME and workspace beneath the namespace-sweep
Treehouse lease. This is NOT the user's default ~/.codex and does not
modify the installed plugin cache, model sheet or desktop account.

## Actual native lifecycle

| Step | Exit and observed result |
| --- | --- |
| Initial source-locked install plan | exit 0, reviewed private snapshot and two native add commands |
| Apply install | exit 0, installation-verified |
| Doctor | exit 0, installation-verified; native registration and files true |
| Plan and apply remove | exit 0, removed |
| Native plugin list after remove | exit 0, no pstack plugin or marketplace |
| Reinstall plan from removed state | exit 0; same source lock |
| Apply reinstall | exit 0, installation-verified |
| Second doctor | exit 0, installation-verified; source manifest matches native cache |
| Final plan and apply remove | exit 0, removed |
| Final native plugin list | exit 0, no pstack registration; cache directory absent |

The doctor call following removal returned blocked, stating that there
was no completed installation receipt for this target. This is
consistent with the removed state; the native list corroborates the
actual absence. It is not falsely recorded as a passing post-remove
doctor.

Original command JSON, plans, adapter receipts and native registry
results are preserved under the test-owned path:

/Users/guanxueliang/.treehouse/pstack-namespace-sweep-20261105/native-acceptance-20261105/evidence/

The native lifecycle is idempotent across one remove-reinstall-remove
round trip. No running user session, external account or plugin trust
prompt was touched. These steps do not prove live Skill invocation,
model routing, subagent closeout or the SessionStart trust decision;
the adapter reports those as host-only evidence.

## Integration tests

The same commit passed repository verification (8 gates),
the Watch PR strict TypeScript and 93-unit suite, the 6 distribution
contract tests and independent regeneration of 2,487 files from
20 quilt patches with no hash differences.

The initial full verification had failed repository policy on a broken
Muse link caused by an over-broad namespace replacement. The bad
attempt and the independent Codex P2 finding are retained as evidence.
After the correction, repository policy accepted 4,522 public files.
The post-commit full verification completed with no failed gates.

## Remaining holds

1. The **default** native plugin install still points to its previous
   source and has not been updated with the corrected namespace adapter.
   A versioned, reviewed update is required; 0.15.36 bytes changed
   within the isolated candidate without changing the manifest version.
2. Complete real two-agent independent review and Hook trust evidence.
   Synthetic policy tests are not a native GUI event.
3. The new branch is not in main or published. Respect the original
   pstack and Agent Skin Treehouse leases and the primary checkout's
   uncommitted edits.
