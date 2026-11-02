# Offline isolation and fixture runtime

`Isolation(root)` accepts an explicitly supplied, owned 0700 evidence directory. `prepare_layout(run)` creates a fresh run inside that directory; `validate_layout` rechecks descriptor/path identity, ownership and permissions. `child_environment` supplies only the declared environment allowlist and private HOME, business and Electron data paths. Configuration fallback is refused without reading its contents.

`launch_plan` is metadata only. `hostLaunchAllowed` is always false. A checked static-source descriptor proves only the supplied bytes and identity; it grants no authority to launch an application or to treat historical installation information as current. Shared protocol handlers, external browser, login, security storage and actual Electron paths remain unverified. A private directory is not a same-UID sandbox or a separate macOS user.

The isolation implementation and 14 boundary tests were recovered from complete historical code strings, then adapted to an explicit evidence root and a caller-supplied static metadata fixture. The old source-guard path is not embedded in this portable candidate. The original unknown document write remains unknown. All results for this candidate must be newly produced.

The fixture runtime is a new implementation, not a recovered historical runtime. It never connects to a real host or reuses a live PID, port or profile.

## Fixture runtime contract

CLI: `node runtime/offline.mjs --request REQUEST.json --out NEW_DIRECTORY`.

The request has schema `offline-runtime-request.v1`, scope `fixture-only`, an absolute private evidence `root`, and `binding` / `producer` descriptors containing relative `path` and exact `sha256`. The request file and fresh output directory must be inside that evidence root. Existing output directories are refused. A resource tree may be copied with a separately verified byte manifest; copying a producer receipt preserves its bytes and does not produce new build evidence.

The runtime invokes only the candidate's fixed `rebind/check_binding.py` through `python3 -B`, records its actual argv, UTC, wait status and binary streams, and checks that its output binds the exact requested binding and producer digests. It then rechecks base payload, startup manifest and all mount/clean/foreign/stale wrapper bytes. Each wrapper configuration comes from the checker proof. The actual built wrappers run in one in-memory DOM fixture. Mount/readback, repeat ownership, stale/foreign refusals and owned cleanup are observed. A changed document generation or failed removal remains failed with cleanup unknown. Final byte rechecks precede success.

`result.json` is an A analysis (`offline-runtime-result.v1`), not a command completion. E phase records retain null exits. `checker-command.json` is C only after an observed terminal wait: a natural integer exit or a known Node signal mapped to the corresponding negative native return code and numeric signal. A spawn failure is E/not_started; an absent or unrecognized wait is E/exit_unknown, with null exit and signal. C and E retain UTC `observed_at`, actual `argv` and `command_id`; phase events link the checker identity. The original `validate_result` oracle checks this contract; the enclosing supervisor remains responsible for the runtime command's own C receipt. `hostValidation` remains `not_run` in every result. The outer supervisor must retain process ownership and actual wait semantics through signal, timeout and handoff.

The VM is a deterministic fixture, not a security sandbox. Only this reviewed candidate's bound generated wrappers belong in it. It does not establish real Electron paths, protocol/browser/Keychain isolation, a real main page, signature closure, R10 or H1. No real host CLI, network connection, daily profile or security-storage access is provided.


Fixed-checker fingerprint reads use an owned regular `O_NOFOLLOW` descriptor, compare descriptor/path identity and enforce the size bound. After the checker returns, fingerprint or argument-postcheck failures are captured as `evidence_errors` with unchanged flags false. The already observed terminal C (or truthful no-wait E) and raw streams are saved before VM admission is refused. A later metadata read cannot erase the real child wait or turn input drift into success. Public CLI regressions use private code copies whose synthetic fixed checker deletes itself or replaces itself with an external symlink; no configurable production checker path is introduced.
