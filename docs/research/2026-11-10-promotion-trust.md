# Promotion integrity and evaluation isolation — 2026-11-10

## Decision

Repair the source-binding and evaluator-isolation defects. Stop further behavior-optimization work after the diagnostic task pilot: it does not show a supported improvement in usable task artifacts. Do not add experience reuse, another Skill optimization layer, or higher-order RSI.

This report separates deterministic integrity regressions, a copied replay of the pinned historical evaluator, and drafts for real historical tasks. Passing one does not establish the others. Live adoption remains held for fresh exact-diff human approval. The historical host drift remains a qualified environment observation, not a demonstrated task-caused pstack change or an automatic blocker for independent source repair/review; the scope correction below supersedes that earlier disposition.

Study baseline: `dc980c4e48e3533cef777e312695ef4ad36f87c6`. The delivery base is `b2b0bf0888a25552d88b463e4f104ed1ca7e37fb`, which adds the independent Agent Skin animation fix #431 in three non-overlapping files. The frozen study baseline is not relabeled. [The machine-readable summary](../../evidence/promotion-trust-2026-11-10.json) contains aggregate results and exact evidence digests. Raw prompts, outputs, reviews, candidates, host inventories and failed attempts remain outside Git.

## Scope correction — 2026-11-10

The maintainer reaffirmed that pstack and its bundled skills are outside Hub Skill upgrade/evolution scope. This is a **post-hoc scope correction**, not a new preregistration or a repeated trial. The original candidate `c3c99a018c40bc8bcc67aea797e77ed555492a00`, its three-case cohort, ratings, raw outputs and incurred costs remain preserved. Exclude `hist-resume-guidance-422` (pstack maintenance) from this task's benefit analysis; retain it only as historical audit material. The two eligible cases are #421 and #429: A and B each have **1/2 usable tasks**, with no supported quality gain. Neither an improvement from 1/3 to 1/2 nor a new failure hypothesis follows from changing the denominator.

General host drift does not authorize pstack changes or broad revalidation. Unknown attribution remains unknown; any actual shared-dependency impact must be scoped and checked before the affected action. Judge-context uncertainty still limits the old pilot. This governance correction changes rules and derived report interpretation, not pstack, runtime code, frozen evaluators, original results or the prior candidate's history. Prior reviews and source digests remain bound to their original candidate; this new revision requires its own verification and exact-diff approval.

## P0 — actual content binding

A controlled baseline reproduction accepted a metadata-only gate record even when the associated patch was replaced or absent. This demonstrates an integrity defect; it does not assert a historical unauthorized promotion.

[The CLI](../../skills/super-repo-pedant/scripts/manage_evolution.py) now uses [the bundled binding helper](../../skills/super-repo-pedant/scripts/promotion_binding.py). The binding covers exact candidate and patch bytes, Git common-directory identity, full base and target commit IDs, and both trees. The target is one nonempty commit directly on the base. Forward and reverse patch application use a private index and object directory and must reconstruct both approved trees.

| Entry | Required state | Meaning |
| --- | --- | --- |
| `bind` | Clean base or target checkout | Produce a reviewable content binding; grants no permission |
| `gate` | Clean exact base; matching evaluation, approval and external binding anchor | Verify the specific pre-application proposal |
| `verify-applied` | Clean committed result with approved base parent and target tree | Verify the actual result, including an equivalent squash commit |

The gate never applies, commits or rolls back a live patch. The owner must serialize the transition, recheck immediately before application, and verify the result afterward. Hashes do not authenticate a human, lock a repository or create an atomic snapshot. Ignored state is excluded. Historical structure-only validation remains readable but is not the actual-source gate. See the [evolution contract](../../skills/super-repo-pedant/references/evolution-contract.md).

The 41 new [binding tests](../../tests/test_promotion_binding.py) cover wrong, missing and replaced patch bytes; equivalent trees with different diff bytes; altered candidate/approval bindings; stale bases including identical trees; changed targets; dirty/hidden index state; unexpected source files; and incorrect application results. Positive cases verify a valid proposal and application. A failed application check is followed by an explicit reverse, confirmation of base tree and bytes, and successful gate rerun.

Review also exposed observational side effects: index hooks, unsafe temporary-root probing and plain-Python import caches. Git observations now disable hooks, temporary storage is checked before creation, and the CLI disables bytecode writes before bundled imports. Original failures and fixes are preserved. Final full verification additionally caught a test subprocess lacking explicit UTF-8; a test-only repair and fresh full run are recorded.

## P1 — isolated historical evaluator

[The development adapter](../../benchmarks/super-repo-pedant/replay_isolated.py) accepts one pinned historical evaluator. It verifies registration, evaluator and frozen inputs; creates a disjoint output; copies runtime/evidence; reconstructs synthetic origins; and remaps copied ownership paths. Its derived registration is separate. This is not a byte-identical replay of the old location-dependent protocol or a general operating-system sandbox.

The final adapter replay completed **16/16 synthetic cases**. Complete original-evidence inventories, including directories, modes and symlinks, matched across **8,077 entries**. The digest remained `e878f23757021f7a077eb9b44260318d06df0cfeefae5fb74dd4b17ffd9a7483`. Copied protocol, inputs and runtime were unchanged. The 18 protected roots matched within this replay interval.

Nine [isolation tests](../../tests/test_replay_isolated.py) cover successful copies, pollution detection, failed-case accounting, timeout retention, invalid inputs, ancestor symlinks, overlapping/reused outputs, inventory detail and fabricated summaries. Failure artifacts remain available. Direct child timeout is tested; descendant-process containment is not established.

The wrapper makes no model calls. Arbitrary child-runtime usage is not metered and remains unknown. This recorded replay establishes bounded compatibility/isolation for the already-merged historical runtime; it does not establish candidate natural-task efficacy.

## P1 — traceable task-artifact pilot

The chain was repository source evidence → Super Repo Pedant guidance → proposed documentation corrections. An independent case author froze source excerpts, historical pre-change documents, packets, criteria and withheld solutions before actor runs. These are reconstructed historical tasks from one repository, not new live tasks or independent natural failures. One packet includes historical pstack documentation; actors proposed text only and made no pstack writes. That packet is excluded from in-scope benefit claims after the maintainer scope correction; the table retains its original result for audit.

| Task lineage | Historical source commit | A median / 16 | B median / 16 | Judge preferences | Usable A / B |
| --- | --- | ---: | ---: | --- | --- |
| Scope contract, #421 | `54e35bed231d15a57bf318348219b9f86339f3a8` | 15 | 14 | A, A, A | No / No |
| Resume guidance, #422 (excluded: pstack) | `523c83c670275f397b3f083c2226ca30f801fa38` | 14 | 14 | Tie, tie, tie | No / No |
| Project workflows, #429 | `79905b55c2ac78e265813c485955b9b568127ae9` | 16 | 16 | Tie, tie, tie | Yes / Yes |

A used baseline Skill bytes; B used candidate bytes. All 14 instruction Markdown files supplied to B matched the original candidate `c3c99a01`; the later governance contract changes were not evaluated by those actors. A later runtime-only startup-cache repair is disclosed: these actors did not execute Python runtime scripts, and the frozen B snapshot was not replaced.

Requested model: `gpt-6.1-sol`, high reasoning, byte-fingerprinted Codex CLI 0.167.0. Each cell received one fresh ephemeral attempt, a 240-second wall limit and read-only, tool-disabled permissions. Concurrency was two. No hard token or currency cap was configured. Six of six actors completed with zero tool events, no repairs or resampling, and unchanged packets/arm bytes.

Three fresh same-model judges used withheld criteria and reversed A/B order. Each reviewed all pairs; nine judge–task decisions are not nine independent task samples. Usability required all essential criteria, concrete surfaces and no material/critical corrections. All 18 arm/case criterion-ID checks matched.

- Both scope drafts omit parts of the non-atomic observation, excluded-input and concurrency-stop contract. A needs one material correction per judge; B needs one or two, with an additional public-mirror omission.
- Both resume drafts remove unimplemented checkpoint design instead of retaining it as proposed intent. Each needs one material correction; one judge also identified a minor issue in both.
- Both workflow drafts meet the frozen criteria without requested corrections.

Against the original packet allowlists, judges reported no out-of-scope edit proposals or fabricated completed checks. That historical judgment does not make the pstack packet eligible under the corrected task scope. That does not erase omissions or establish live execution safety. Correction units are reviewer estimates, not actual human edits/time. The original cohort yields **1/3 usable tasks** in each arm; the post-hoc in-scope subset yields **1/2** in each arm. The original three-case count is retained only as historical reporting, not this task’s efficacy denominator.

### Observed cost and control limits

The ledger below retains **all incurred runs**, including the excluded historical case; exclusion does not refund its cost. It is not a cost estimate for a fresh two-case experiment.

| Work | Input tokens | Output tokens | Sum of run wall times |
| --- | ---: | ---: | ---: |
| A, three actors | 139,038 | 10,937 | 306.969 s |
| B, three actors | 141,795 | 10,965 | 254.123 s |
| Three quality judges | 189,462 | 27,024 | 574.088 s |
| All nine study runs | 470,295 | 48,926 | 1,135.180 s |

Reasoning-token fields are itemized separately, not added again to output totals. Sum of run times is not end-to-end elapsed time. An availability probe used another 23,375 input/5 output tokens and is excluded from efficacy. B adds 2,757 input tokens, or 919 per actor attempt. This small single-attempt sample supports neither a reliable speedup nor economic savings.

Billed money, complete orchestration/development/review usage, and actual human correction time are unavailable. This is an observed-cost ledger with explicit gaps, not a complete financial cost estimate.

Actor context fingerprints matched. One user-configuration file changed during judging. Commands explicitly ignored user configuration and recorded role-file/binary digests remained stable, but complete effective model context was unavailable. Writer and effect are unknown. Original run records remain intact with a companion control qualification. No rerun was used to remove the unfavorable or uncontrolled observation.

## Historical engineering review and host-state observations

Three fresh engineering reviewers examined source with reversed order. Initial findings remain available. After the cache/input-ancestor fixes and test-only encoding addendum, all three prefer the candidate with no remaining blocking source finding in scope. They executed no repository code. These are engineering reviews, not human approval or task-quality votes.

The task-wide comparison of 4,746 regular-file entries found three changed shared records: one Codex configuration and two Claude plugin registries. Attribution is unknown; no restore/writeback was performed. All 3,234 protected Git paths and the shared validator matched. Endpoint inventories cannot certify transient writes or unrecorded metadata. The former blanket live-adoption hold is withdrawn as a scope-classification error, not marked technically resolved. It remains an unassigned environment observation, while uncertainty about judge controls continues to qualify the pilot. There is no established causal/dependency basis to block this independent governance/source repair or to trigger pstack upgrade, installation or revalidation. A later operation that actually changes a shared dependency must establish its own bounded impact evidence; the narrower replay-interval equality is not a global no-change claim.

## Validation and semantic impact

The original pre-governance runtime, test and contract bytes passed `python3 scripts/verify.py`: **716 Hub tests (one skipped), 59 model-router tests and 45 installer tests**, plus registered policy, benchmark-integrity and whitespace gates. This run preceded these two aggregate-only files. They receive separate policy/whitespace verification, and CI checks the exact committed head. Exact logs, commit/patch binding and recovery receipts stay outside Git to avoid self-reference. Those historical checks and reviews do not certify this later governance revision; it receives a fresh fixed-revision verification and approval packet without rewriting the original evidence.

| Surface / owner | Consumers and state | Boundary |
| --- | --- | --- |
| Evolution CLI / Super Repo Pedant | CLI callers, candidate/evaluation, Git source | Actual bytes at observation; distinct result verification |
| Bundled helper / Super Repo Pedant | Independently copied Skill package | Standard library; no import cache writes or live application |
| Schema/contract / Super Repo Pedant | Legacy records, external approval holder | Legacy structure stays readable; source gate needs fresh binding |
| Replay adapter / benchmark owner | Pinned evaluator, derived workspace | Preserves original evidence; no general child sandbox |
| Public instructions / maintainers | Skill users, diagnostic actor prompts | Explicit limits; no install pipeline or generated pstack change |

The experimental Foundation scope command records four Git layers with explicit base/head. Complete results must be rechecked before use; they are not semantic closure or a concurrency lock. There is no new host adapter or public support expansion.

## P2 disposition and adoption

**Do not start another behavior-optimization candidate.** The proposed-intent loss came from the now-excluded pstack lineage and is retained only as historical audit context, not as a basis for this task’s further evolution. Do not tune on these held-out outputs or add another optimization mechanism.

Integrity repairs have deterministic support of their own; do not attribute task-quality gains to them. Repository policy requires fresh exact-diff human approval before promotion. This report asserts no approval, live application or successful adoption. Later source changes require a new binding. Preserve the task branch and lease for review and recovery.
