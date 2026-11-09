# Engineering guidance by task

Read only the row that applies to the current change. These are the maintained
source references that also ship in the optional pstack bundle; reading them
here requires no plugin installation and starts no other orchestrator.

| Trigger | Read before acting |
| --- | --- |
| Performance workload or speed claim | [user-paths](../../packages/pstack-agent-harness/hub-skills/benchmark-checklist/references/user-paths.md) |
| Public interface, shared state, generation or installation impact | [semantic-impact](../../packages/pstack-agent-harness/hub-skills/blast-radius/references/semantic-impact.md) |
| Verification journey, replay, coverage promotion or UI acceptance | [case-admission](../../packages/pstack-agent-harness/hub-skills/create-verification-skill/references/case-admission.md) |
| Design/code review or simplification | [independent-contracts](../../packages/pstack-agent-harness/hub-skills/interrogate/references/independent-contracts.md) |
| Errors, retries, cancellation or cleanup | [failure-ownership](../../packages/pstack-agent-harness/hub-skills/principle-boundary-discipline/references/failure-ownership.md) |
| Tool schema, skill discovery or context budget | [model-interface](../../packages/pstack-agent-harness/hub-skills/principle-guard-the-context-window/references/model-interface.md) |
| Resource-owning, asynchronous or platform-sensitive test | [reliable-fixtures](../../packages/pstack-agent-harness/hub-skills/principle-test-behavior-not-implementation/references/reliable-fixtures.md) |
| Documentation, translation, upgrade guidance or decision consolidation | [current-contracts](../../packages/pstack-agent-harness/hub-skills/technical-writing/references/current-contracts.md) |

Repository rules take precedence: run `python scripts/verify.py` before handoff,
keep required host/visual evidence separate, and squash-merge only after required
checks and every review thread are resolved. Follow the existing Treehouse and
native installation owners. Source-project commands, data stores, approval
conventions and deployment tools are not transferred by these references.

Use the [pinned Skill comparison](../research/2026-11-09-zcode-dsh-skills.md)
for individual adoption decisions and limits. Workflow instructions are not
mechanical enforcement or evidence that a model followed them.
