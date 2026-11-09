# Make fixtures survive concurrent execution

Read this for tests involving asynchronous work, processes, clocks, global state, files, sockets or flaky CI. Inspect the active worker and job configuration; separate processes may still share host resources.

- Allocate resources atomically: private temporary directories, exclusive file creation, unique database namespaces and loopback port zero. Do not discover a free port and claim it later. Stable recorded identifiers stay separate from ephemeral live addresses.
- Register restoration as soon as acquisition succeeds. Prefer instance-local dependencies to changing environment, cwd, locale, clocks, mocks or global fetch. If mutation is necessary, restore the exact original value including absence, in the narrowest finally block.
- Synchronize on observable readiness, an owned promise, handshake or barrier. A timeout bounds the wait; a sleep does not prove readiness. A race regression must demonstrate the relevant overlap.
- Await cleanup to quiescence: stop callbacks and new requests, then await child exit, server close or worker termination. Test that late results cannot affect the next case. Keep dependencies available until their consumers finish cleanup.
- Respect the runner's setup, test and teardown budgets. Keep the outer deadline comfortably above a timeout being tested. Before asserting child exit, distinguish exit code, signal, cancellation and timeout.
- Read back operating-system-owned values instead of assuming exact timestamp round trips or case-sensitive environment keys. Use explicit reasoned platform skips for genuinely unsupported permission or signal semantics; never weaken all platforms to hide one mismatch.

For a new guard, introduce a rejected input through the real entry and observe failure. For a shared-host isolation fix, run independent processes concurrently as well as the focused test. Stress repetition supplements a deterministic case. Reject blind timeout increases, retries, blanket serialization, swallowed failures and normalization that hides the behavior under test. A measured contention budget or documented transient external retry remains a separate, explicit case.

Report exact selected tests, observed assertions and skipped checks. A filter selecting zero tests cannot establish success. Run the repository's required full gate as well as focused evidence when its policy requires it.

## Source and local changes

Adapted by Azhou AI Hub; read `ENGINEERING-SOURCES.md` at the installed distribution root for immutable sources, licenses, local substitutions and update steps. These are workflow instructions, not an automatic safety or approval gate.
