# super-grilling benchmark contract

Exploratory manual benchmark; **not** wired into `scripts/verify.py`. This file records a walkthrough contract a contributor can run by hand, and one recorded walkthrough.

## Manual walkthrough contract

Give the skill a short written plan that contains at least one decision depending on another, then check:

1. The first round asks every question whose prerequisites are already settled, numbers each one, and gives a recommended answer for each.
2. A question whose answer depends on another question still open in the round is held for a later round.
3. Each question is worded so that "yes" accepts the recommended answer.
4. Facts are looked up rather than asked of the user. On a harness without sub-agents, the skill says the fact was not checked from an independent context window.
5. The session ends when the frontier is empty, and nothing is acted on until the user confirms a shared understanding.

The conversation behavior is human-in-the-loop and is walked through, not automated, by this contract.

## Recorded walkthrough

Two runs are recorded (2026-11-24). Each gave a fresh agent context this package (once alone, once beside `super-grill-me`) and a short plan to grill. In both, the first round asked eight numbered questions, each with a recommended answer and worded so that "yes" accepts it. Both listed the facts to look up and the branches held for later rounds, and both ended by stating that nothing is acted on before the user confirms a shared understanding. Neither run had an environment to read and neither reply used a sub-agent, and both replies said that no fact had been checked from an independent context window.

Limits: one sample per configuration, one model, and a reader who knew what to expect. Both sessions ended after the first round, so later rounds and the completion rule were not exercised, and no run yet shows a sub-agent looking up a fact.
