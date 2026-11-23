# super-grill-me benchmark contract

Exploratory manual benchmark; **not** wired into `scripts/verify.py`. This file records a walkthrough contract a contributor can run by hand, and one recorded walkthrough.

## Manual walkthrough contract

1. Load `skills/super-grill-me/SKILL.md` in a harness where `super-grilling` is not installed and name a plan to be grilled. Expect a stop that names `super-grilling` as the missing requirement, with no interview questions.
2. Load it with `super-grilling` installed beside it and name a plan. Expect the startup broadcast and a handoff to the `super-grilling` rounds, with no second interview protocol run from here.
3. Invoke it without naming anything. Expect one question asking what is to be grilled, and nothing else.

The conversation behavior is human-in-the-loop and is walked through, not automated, by this contract.

## Recorded walkthrough

One walkthrough is recorded (2026-11-24). A fresh agent context received only this package in an isolated skill root and the request "grill me on this plan: we will add a nightly cron job that deletes user uploads older than 30 days". It read `SKILL.md` and two reference files, emitted the startup broadcast and the hold marker, named `super-grilling` as the missing requirement, and asked no interview questions. A second context received this package together with `super-grilling` and the same request. It emitted this package's startup broadcast, then the `super-grilling` startup broadcast and a first round of eight numbered questions with recommended answers.

Limits: one sample per configuration, one model, and a reader who knew what to expect. The result supports the handoff contract and says nothing about other harnesses or models. The third contract step, invoking the skill without naming anything, was not exercised.
