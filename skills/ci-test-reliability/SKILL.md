---
name: ci-test-reliability
description: Use when writing or changing tests that own resources (ports, temp paths, subprocesses, clocks, process-global state), when tests run under concurrent CI workers or a platform matrix, when reviewing test isolation, or when diagnosing a flaky CI failure; covers topology-aware allocation, quiescent teardown, timeout budgeting, regression negative controls, and the flake-masking blacklist.
invocation: model-invoked discipline
---

# CI Test Reliability

**🦊 阿舟 · CI Test Reliability**

> 🧪 测试自己可靠，才配当证据。

Invocation class: model-invoked discipline, declared in frontmatter; the axis, its semantics and the composition rules are defined once in docs/skill-standard.md §2.2 (spec #126 ID-9) — applicable during ordinary test-writing and review work without being named, and still directly invocable.

It is guidance, not a script. Build tests that stay correct under the repository's real CI topology — concurrent workers, a platform matrix, shared hosts — not only when run alone on a quiet workstation. This skill owns isolation and reliability judgment for test design and flake diagnosis; it never selects or replaces the repository verification gate itself.

## Brand protocol

Emit this exact display event once:

```text
🦊 阿舟 · CI Test Reliability 启动｜mode=<design|review|diagnose>｜scope=<test-or-suite>
```

Use `✅ 验证通过` only after the selected regression actually runs green and its negative control runs red. Use `❌ 验证失败` for a red regression or a failed negative control and `🔒 阿舟暂停这一项` when a required fact (the CI topology, the owning lane, the awaited readiness signal) cannot be established. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `｜` separators, fields, and values. Raw evidence such as failing runs, queue logs, and worker traces stays out of receipts unless the user supplied it.

## Model the execution topology

Assume these layers can overlap unless the active configuration proves otherwise:

1. Cases inside one test module.
2. Separate modules or runner processes.
3. Independent jobs in one CI run.
4. Different CI jobs whose runners share one host.

Process isolation does not isolate host ports, predictable filesystem paths, external services, sockets, databases, or inherited child processes. For every acquired resource, name its owner, its atomic allocation mechanism, its observable readiness signal, its registered cleanup, and its quiescent completion signal. Never serialize an entire suite because one fixture lacks isolation; narrow the exclusive scope or fix the allocation — a sequential module cannot protect a host resource from another module, process, job, or runner.

## Allocate resources atomically

Use the resource owner's allocator instead of checking availability and claiming later.

- Bind network listeners to port 0 and read the assigned port only after the listener reports it is listening; never scan for a free port and bind it later.
- Create per-test temporary roots with `tempfile.mkdtemp`; never acquire predictable shared paths.
- Give shared databases, sockets, sessions, and output locations unique per-test namespaces.
- Use exclusive creation where a path must not already exist.

Literal paths and URLs used only as parser inputs or expected values are not acquired resources; do not rewrite them merely because they look fixed.

## Contain process-global state

Treat `os.environ`, the working directory, `time` mocks, locale and timezone settings, module-level mocks, registries, and global patching as exclusive mutable resources. Prefer an injected dependency or an instance-local adapter. When mutation is required, capture whether the original value was absent or present, restore that exact state, register the restoration immediately, and keep `try/finally` around the smallest mutation scope.

## Respect platform-owned semantics

A value the operating system owns does not always round-trip the way a test wrote it.

- Writing a value back is safe only when the assertion tolerates the write-back failing; when the assertion depends on the restoration, take the expected value from a fresh read, not from the remembered one.
- Windows matches environment variable names case-insensitively, so seeding `http_proxy` and `HTTP_PROXY` as separate keys holds one entry there.
- Windows releases file handles asynchronously, so a rename or removal that completes at once on POSIX may need a bounded retry sized to observed contention.
- Windows has no POSIX permission or signal semantics; a case that depends on them takes an explicit platform skip naming the reason.

Prefer an observation that holds on every platform; when a case genuinely cannot, exclude it on that platform explicitly.

## Budget timeouts against the lane

A per-test timeout overrides the runner's lane budget instead of yielding to it, so a value below the lane's granted budget lowers what CI already gave — and a tighter value carries the reason it is tighter. Setup and teardown pay the same contention, so raise hook budgets with test budgets. Where time itself is the subject, inject or fake the clock and always restore real timers; keep the outer wait far larger than the deadline under test, or load decides which deadline reports first.

## Synchronize on state, never on sleeps

A fixed sleep is not evidence that setup completed or cleanup settled. Wait for an explicit readiness event, handshake, barrier, `threading.Event`, `asyncio.Future`, or externally observable condition. Use a timeout only to bound a wait, never as the condition that makes the assertion correct. Use barriers or deferred events to place a race at a deterministic point and prove the relevant operations overlap; do not assert scheduler-dependent ordering unless that ordering is the product behavior under test. Repeated execution alone is not a race test.

## Dispose to quiescence

Register cleanup immediately after acquisition so assertion failures also release the resource. Cleanup stops new callbacks or requests, detaches listeners, restores global state, terminates owned work, and awaits the owned completion signal — child exit, server close, worker termination. Calling `kill()` or `close()` without awaiting the owned completion signal is incomplete teardown; when late completion is possible, prove that disposal prevents it from mutating another test.

## Prove the regression, reject flake-masking

Observe the intended regression fail before the fix when practical; for a new guard, temporarily introduce the rejected case and observe the intended failure. Where a fixture spawns with its own deadline, assert that no signal or timeout ended the child before asserting its exit status, so a killed child reports as a timeout instead of a status mismatch. For ports, sockets, shared paths, or subprocesses, run independent test processes concurrently when cross-process isolation is part of the fix. Verify external state, events, files, logs, exits, or disposal instead of trusting the component's self-report. Stress runs supplement a deterministic regression; they never replace one.

None of these are root-cause fixes for a deterministic local test: increasing a timeout without identifying the awaited state, adding retries, making all modules serial, swallowing an error, weakening an assertion, normalizing unstable behavior, or adding a sleep before cleanup or assertion. Restoring a budget is not masking: raising a suite to the lane budget it already had, or sizing a bounded retry to measured contention, names the awaited work and returns what the lane granted. Retries remain valid only for documented transient external-provider tests at the real-API boundary.

## Diagnose an existing flake

For a probabilistic CI failure, follow [the diagnosis workflow](references/ci-flake-diagnosis.md): freeze the evidence, classify the failure, climb the reproduction ladder until the contention reproduces, fix at the owning resource, and close out with the negative control. A diagnosis-only request stays read-only; report the cause and evidence unless the user also asks for a fix.

## Verification

For new or changed tests, run the owning focused test module plus its negative control, then the repository gate (`scripts/verify.py`). Report exact commands and observed results; never describe retries, skipped tests, or pending CI as passing. End with a stable receipt carrying `schema`, `status`, `current truth`, `artifacts/changes`, `verification`, `holds`, `next action`, and `learning signal`; `artifacts` may be empty for a guidance-only run. Adapted-material obligations, the upstream pin, and the update path live in [provenance.md](references/provenance.md).
