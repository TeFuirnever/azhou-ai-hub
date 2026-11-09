# Preserve state when an operation fails

Read this when changing error handling, retries, background work, installation, cancellation or cleanup. Internal type trust does not prove that side effects have completed or that state remains valid.

For each operation identify its input boundary, state owner, admission point, commit point, reporting owner and cleanup owner. Use the package's existing typed failure conventions with stable discriminants and preserved causes. Handle failures by machine identity, not message text. Unexpected defects must remain failures.

Record effects separately as absent, partial, committed or unknown. Catching an exception only contains propagation; it does not undo a write. Only the state owner can establish that dependent work is safe to continue. Logging is not recovery. Stop dependent work when invariants or outcome are unknown, while continuing independent authorized work.

Retry only when repetition is safe, bounded for a finite operation, cancelable and owned. A persistent supervisor needs a lifetime and visible degradation. Do not describe a partial restore as rollback; distinguish installed bytes, selected configuration and successful activation.

Register ownership and cleanup immediately when acquiring a resource. Stop admission and detach producers before releasing dependencies that outstanding consumers still need. Await the owned completion signal for children, listeners, workers and servers. Abort, kill or close requests are not settlement. A direct child's exit does not prove that descendants stopped. Where settlement cannot be observed, report it as unknown and preserve the recovery resources.

Exercise cancellation at awaits, stale callbacks after disposal, alternate callers of a denied operation, failure after a partial write and failure while reporting another failure. Use deterministic barriers for races. Observe the resulting state and the user-visible report, not only the caught exception.

Final reports state the operation, state guarantee, uncertainty, residual effects and safe next action. Use existing localization and an independent fallback for reporting failures. Persistent invalid state stays visibly invalid; never report success merely because an exception was contained. Do not expose private paths, credentials or raw internal data in public reports.

## Source and local changes

Adapted by Azhou AI Hub; read `ENGINEERING-SOURCES.md` at the installed distribution root for immutable sources, licenses, local substitutions and update steps. These are workflow instructions, not an automatic safety or approval gate.
