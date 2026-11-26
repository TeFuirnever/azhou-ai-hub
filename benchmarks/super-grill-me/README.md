# super-grill-me benchmark contract

Exploratory manual benchmark; **not** wired into `scripts/verify.py`. This file records a walkthrough contract a contributor can run by hand; executed runs are logged under [Recorded walkthrough](#recorded-walkthrough) and [Recorded multi-round session](#recorded-multi-round-session).

## Manual walkthrough contract

1. Give the skill a short written plan that contains at least one decision depending on another, then check:
   - The first round asks every question whose prerequisites are already settled, numbers each one, and gives a recommended answer for each.
   - A question whose answer depends on another question still open in the round is held for a later round.
   - Each question is worded so that "yes" accepts the recommended answer.
   - Facts are looked up rather than asked of the user. On a harness without sub-agents, the skill says the fact was not checked from an independent context window.
   - The session ends when the frontier is empty, and nothing is acted on until the user confirms a shared understanding.
2. Invoke it without naming anything. Expect one question asking what is to be grilled, a hold, and no interview rounds.

The conversation behavior is human-in-the-loop and is walked through, not automated, by this contract.

## Recorded walkthrough

Three runs are recorded (2026-11-24), one per configuration. Each gave a fresh agent context only this package in an isolated skill root, with no environment to read, no sub-agent and no command. The reader was not blind, and every session ended after the first answer.

- Explicit request, "grill me on this plan: we will add a nightly cron job that deletes user uploads older than 30 days". The reply carried the startup line, the design-tree event and the round event, then asked nine numbered questions with a recommended answer each. Every question was worded so that "yes" accepts its recommendation. The reply named the branches held for a later round, said that no environment fact had been checked because it had no sub-agent and could not read the codebase, and carried no receipt, because the turn waits for the reader.
- Model-reachable request, "I want to stress-test my thinking on this" with the same plan and five other skills installed beside this package. The subject opened this package's entry file and the brainstorming entry file to compare the two, then followed this package. The first round asked seven numbered questions, all worded so that "yes" accepts the recommendation. The reply named the held branches, said that the code had not been read, and carried no receipt.
- No subject named, the command alone. The reply carried the startup line with `scope=unresolved`, asked one question about what to grill, marked the hold with `reason=nothing-named`, asked no interview question, and ended with a receipt of `status: hold`, `rounds: 0` and `frontier: unopened`.

Each configuration has one sample on one model, so the runs show that each path can be met, not how often it is. No run reached an empty frontier, a later turn, a `complete` receipt or the success anchor. No run had a sub-agent or an environment to read, so the fact-finding path is untested. On earlier drafts of this package, one of three replies that received a plan did not word its questions that way. It asked open questions and told the reader that a "yes" answer accepts its recommendation.

## Recorded multi-round session

One session is recorded (2026-11-24 to 2026-11-25) on the shipped package bytes (`SKILL.md` SHA-256 `05e356f839278a294af9ec5dfd831c6fd3b42fba58b42fd0e49312b1859ffd4d`). A fresh host context received a synthetic project README that describes an upload service with a 30-day retention promise, and this package linked into that project's skill root. The host was Claude Code 2.1.330, headless. Every turn that produced a reply ran on the `opus` alias, which resolves to `xiaomi/mimo-v2.6-pro:max[1m]`. The reader was scripted: it accepted every recommendation, later named a gate owner, and confirmed once as a standalone message.

- Round 1 (429 s) emitted the startup line, the design-tree line, a facts line marked `source=self-check`, and the round line, then asked six numbered questions with a recommended answer each. Round 2 resumed the same session and asked six more (514 s). Twelve decisions settled in total.
- Two confirmation attempts were refused. The first carried a background-task notification in the same turn, and the model would not record a confirmation it could not attribute to the reader. The second was refused on the same pattern. A third, standalone confirmation was accepted (160 s).
- The run ended with a `complete_with_holds` receipt: `rounds: 2`, `open_questions: 1`, `confirmed_by: reader confirmation 2026-11-25 standalone message`, one hold for a cron mail delivery test with an owner and a next action, and a `verification` field that records the model's background completeness scan was stopped twice at turn boundaries, so frontier emptiness was never independently verified.
- Two host quirks are part of the record. One resume returned an empty turn while a background-task notification was pending. One turn hit the host's weekly quota on the default model route, and the session continued on the `opus` alias.
- Two other runs on these bytes (2026-11-24, 1298.9 s and 902.9 s, on the same model route, `xiaomi/mimo-v2.6-pro:max[1m]`), recorded Git-external, emitted a facts line marked `source=sub-agent`, which is the sub-agent path this session did not take.

Evidence fields of the recorded session:

- Inputs, with the SHA-256 of each text: the synthetic project README `37df9ab05e47b492e246400add94eee2594efcc5021cf3450393848120d80f1f`; the first message, the same text as message b of the host-check receipt, `bcd730c381ccf1ca7651f0b835cf1f9dc90ffa026500fac3d57a3178e4399ab1`; the reader's answer to round 1 and to round 2, the same text both times, `0d33e41abca88f8579a2b5c52f433c9dc77b9e6dd3230deabfadd97dead41dae`; the refused confirmation attempts, with one text sent to both turns 4 and 5, `4c7e926b08cea90ad0a4922d6d8218a2a32ee2edb03c4899ac16167267e4971d`, and another sent to turn 7, `9f22f14cbe909d4602571d7bb9127e9f6297a6c0b602dc41b5ac4679e8fcbdb2`; the final standalone confirmation, which carried the gate owner's name, `8ac3443370d3cbf6b14fef05e7d9ec8f3b90c40315888e0370b89418f73bfb50`.
- Tool permission: the host's `permissionMode` was `auto`, the maintainer's own configuration. No permission flag was passed.
- Bounds: each turn was bounded at 1800 s, with a 180 s quiet stop.
- Receipt: the SHA-256 of the terminal receipt block is `80ac049644c87b6251736599bfc652e042d2fbb339208c19633f7d27aab14e0f`.
- Named human check: none at record time. The independent machine judge named in the host-check receipt covered a different record.

The turn transcripts and the verbatim receipts stay Git-external in the maintainer's evidence store, under `.planning/grill-me-followup-20261124/host-runs/e2-session/`.

Limits: one session, one model route (`opus`, which resolves to `xiaomi/mimo-v2.6-pro:max[1m]`), one scripted reader who is not a human and who accepted every recommendation instead of judging each one. Turn 5 ran on the host's default route by driver error, hit the quota wall and produced no reply. The completeness scan never finished. The `complete` receipt, with an empty frontier and no holds, has not been observed.

Next action: run one session with a human reader to an empty frontier and a `complete` receipt, and record it here. The host check on Claude Code is recorded in [the receipt](../../evidence/super-grill-me-host-check-claude-2026-11-24.md).

## Next check

Repeat the plan-given Claude Code probe in a disposable project when the configured model route is available. Check for one design-tree anchor and one `round=1` before the reader replies, and confirm that tool results do not advance the round. Record the tested package digest and whether the host opened the brand reference.
