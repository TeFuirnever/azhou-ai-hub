# super-grill-me benchmark contract

Exploratory manual benchmark; **not** wired into `scripts/verify.py`. This file records a walkthrough contract a contributor can run by hand; executed runs are logged under [Recorded walkthrough](#recorded-walkthrough).

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
