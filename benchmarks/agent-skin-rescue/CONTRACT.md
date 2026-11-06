# Offline reconstruction contract

## Ownership and evidence

Each worker owns disjoint files in a durable leased checkout. The integration owner merges reviewed local commits. Existing worktrees, original source materials, leases and branch references are preserved.

C records actual command completion and its argv, working directory, timestamps, true final wait outcome and input identity. E records events or errors while work is running; exit fields may be null or unknown, and an event is never a completion receipt. A records immutable artifacts. Each record binds the bytes and identity it actually observes; E links to a later C when available. A later archive references the immutable producer receipt; it never rewrites that producer. Binary stdout and stderr must survive invalid UTF-8 and short writes. Changed or unverified source, ownership or exit state cannot become success.

## Agreed test seams

- Records and archive: descriptor-bound byte capture, input drift, immutable receipts, later producer linkage, permission/link/source replacement rejection and short-write handling.
- Supervisor and installation registration: controlled child exit, timeout, first-signal latch, retained ownership through handoff, unknown identity without signals, and read-only synthetic bundle identity with streaming hashes.
- Isolation: fresh private HOME, business, Electron user/session, logs and temporary roots; environment allowlist, identity/permission revalidation and configuration fallback rejection. Host launch remains disabled.
- Resources and runtime: actual builder input/output binding and checker; pageAdapter remains the third parameter, diagnostic seam is explicit fourth parameter and disabled by default; one controlled VM context, exact resource proof, generation invalidation and bounded cleanup.
- Codex compatibility and browser harness: preserve default storage namespace, verifier predicates, all UI assertions and existing navigation budgets. Only owned headless fixture profiles may run; the Mac mock-keychain flag is confined to that fixture.

## Limits

Real ZCode/Codex host launch, daily profiles, credentials, system keychain, login and installed-product mutation are prohibited in this offline candidate. Synthetic observations do not establish real Electron or operating-system isolation. Signature closure, a newly confirmed serial host window, R10/H1 and subsequent dependent tickets remain unverified or not run.

Original uncertain writes remain uncertain. Reconstructed evidence records new timestamps and candidate identities; it cannot recreate missing historical observations.
