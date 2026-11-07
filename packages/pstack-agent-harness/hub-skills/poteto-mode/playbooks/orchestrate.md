### Orchestrate

> **Hub portable-host contract:** The Cursor-specific Task, cloud-agent,
> Project tracker/store and /loop examples below are *capabilities*, not
> guaranteed tools in Claude Code, Codex, ZCode or a skills-only host. Resolve
> them using the installed host adapter before proceeding. Missing execution
> or review capability is a blocking gate, never a license to invent agents,
> virtual machines, asynchronous progress or verification. The user still
> owns irreversible approval and any protected merge or push.

**You run the program, never the code. Decide which agent does each piece of work, then check what each one produces.** For a standing project handed to one coordinator chat: multi-day, many stacked PRs, dozens to hundreds of subagents, few human turns. One task driven to a predicate is Autonomous run. One ambitious run that needs a bespoke workflow is figure-it-out. Work that one agent could finish inside the session's budget is not a program.

Run it with your own tools. Spawn workers with `Task`. Keep the program's state in the Project tracker (`notes.md`) and the Project store. Watch each PR with PR and CI event subscriptions when your harness has them. Call no scripts, run no polling loops, and never relay messages or status between agents.

#### Topology

- **One owner per PR.** The owner is the only writer of its branch and carries the PR from build to merge. Only the owner pushes, rebases, or retargets it. Closing or retargeting a base PR orphans every PR above it, so the owner does that only on your call. You never author or edit code. Conflicted merges, chain rebases, and fixes go to owners.
- **A fresh worker for each independent task.** Its kickoff carries everything it needs, including each upstream report it depends on, pasted in full. Workers can't see their siblings. Run workers on a new cloud VM (`environment: "cloud"`) unless the work needs this machine: a `control-ui` or `control-cli` runtime check (from `cursor-team-kit`), local transcripts, a simulator, or auth that exists only here. Pick each subagent's reasoning level and fast or standard speed for the job, per the Subagents section.
- **A sub-coordinator only when one area has many parallel workers.** It owns that area's workers and kickoffs and sends you one rollup, never raw worker reports. Stop at three levels: you, sub-coordinators, and workers. Keep about ten workers in flight per coordinator, and start the next one as each finishes instead of waiting on a whole batch.
- **Fork when new work needs a worker's built state,** such as its checkout, uncommitted changes, or a running process. Message a worker only for a follow-up on the same work. Never message one to check on it, because a message restarts an idle agent.
- **Each PR gets a verifier that isn't its author,** on a different model family. The owner merges only on that verifier's pass at the current head.
- **Start with one unit.** Take it through kickoff, owner, verifier, and merge before you fan out, so a flaw in the kickoff costs one agent instead of fifty. On near-identical cheap units, the first unit is that test.

#### Supervision

- **Each kickoff names the evidence that proves the work is done,** such as a command and its expected output, a control-skill check, or an artifact. It also names the goal, the paths the worker may and may not write, and the actions it must not take. If you can't name the evidence, the unit isn't scoped yet.
- **Read the diff or the artifact, not only the worker's summary.** Green CI is an input to a verdict, not a verdict. Behavioral work needs more than a type check. A verdict covers one head SHA, so a new push needs a new verdict. Read a sample of each sub-coordinator's kickoffs while its workers run, and fix its instructions when one fails.
- **Send back work that drifts from scope or grows past what was asked.** Keep only the fixes that block the program, and park the rest as follow-ups.
- **Check a PR's live state before you report on it,** with `gh pr view` and `gh pr checks` or your forge's equivalents, not the worker's last report. Account for every worker you spawned as done, replaced, or absorbed into another worker's scope.
- **Stop or replace a worker that stalls or loops.** Judge it by its pushes and PR activity, not its status text. Retry by cause: a smaller scope after a context or memory limit, the same kickoff after a dropped connection, and a different model after a tool error. After two retries, drop the unit and replan around it. When a stopped worker returns late, check its result against the PR's current state, and hand any unique findings to a fresh worker.
- **Ask the user only for a real decision or a blocker,** such as an irreversible action, a product or preference call that no experiment settles, or a dead end that survived a replan. Rebase mechanics, retries, CI flakes, review triage, and "should I keep going" never reach the user.

**Reply:** what landed against the goal, each PR's live state and verdict with its link, what was dropped and why, and the decisions waiting on the user.


#### Hub portable coordination and durable recovery

**Capability gates before delegation.** If the host has no real Task or
subagent dispatcher, run only a scoped sequential task that does not require
parallelism; mark any independent review or multi-agent completion BLOCKED.
If it has no cloud worker environment, a separately owned local worktree or
branch is an acceptable writer boundary, with one lease/owner per branch
and no shared uncommitted source. Never report a local worker as a cloud VM.
A missing Project tracker/store is not a reason to keep the only copy of
critical program state in the chat context.

**Persist the state, not the whole conversation.** Choose a private,
owner-controlled project trail that survives the coordinator's session and
is recoverable by another authorized coordinator. Name its location in the
kickoff and human report. Record, using the host's available files, issue
tracker or Project state (the exact filenames are not mandatory):

- The approved goal, working scope, forbidden paths, decision gates and
  immutable standing orders for every worker.
- For every unit: its single writer, branch/worktree or PR, dependency,
  current head SHA, live state, last verified artifact and next action.
- For every release verdict: the exact PR or change and head SHA, the
  independent reviewer, its evidence paths and status. A new head invalidates
  an old head's pass until reconfirmed.
- Human gates and pending irreversible operations with their actual grant;
  absence of an answer does not authorize a destructive action.
- For every launched worker: identifier, provenance, observed side effects,
  bounded stuck threshold and final state (done, failed, replaced or
  abandoned). Never infer completion from a worker's prose alone.

**Restart and liveness.** On resumption, treat old agent process identities
as unavailable until independently observed. Re-read the standing orders,
enumerate live branches and PRs from Git/forge, validate each head SHA and
verdict against the saved trail, and rebuild the frontier from those facts.
Reattach by branch or PR identity, not a possibly dead agent ID. Stop any
unit whose owner is ambiguous. Observe liveness through actual commits,
test results and PR state, not chat status. Retry a stuck worker at most
twice with cause-specific changes, then record the failure and replan.

**No invented scheduler.** Prefer native event subscriptions where the host
supports them. Without subscriptions, perform explicit finite checkpoints
during active authorized turns. Do not claim automatic monitoring, background
wakes, a future report or a persistent loop unless a real host scheduler
was actually configured. Do not implement a polling loop as a substitute.

**Release gate.** Green CI alone is insufficient: an independent author-free
reviewer must verify the current landed head on the real artifact. If the
host cannot provide the required independent reviewer, stop at merge-ready
and hand over the unresolved gate. The coordinator does not write code to
work around ownership or verification failure.
