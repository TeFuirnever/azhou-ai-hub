# Offline Agent Skin rescue candidate

This development-only candidate reconstructs recoverable offline components after local workspace loss. It does not change the installed product or add ZCode support.

Source recovery and current verification are separate. Exact historical source or patches may be reused after digest verification; historical passing counts never substitute for a current run on the reconstructed candidate. Raw history, private assets, process receipts and local ownership records belong outside this tracked directory.

The offline source is the exact historical build 31 tree, reconstructed without the unpublished historical commit object: every run extracts the `packages/agent-skin` archive of the public immutable commit `b689702097be8bd3e2a4b6f2a10afb348cf5cb37` (subtree `93de39312c4a7aadaa2800ff2d60d52de3e4aac7`), applies the tracked restoration patch `rebind/restoration.patch.b64` (decoded SHA-256 `5b5382b8b4dcfd4dfe1894ff4140fec1ac6c5dbc7146d320de92e429e5a045fb`), and verifies the restored subtree by Git tree id against the historical build-31 identity `3060b7e3587b37a0486c54423f76bb3d792c7b6d` before use; patch or source drift is refused. Runs therefore reconstruct build 31, not the current package, and do not establish current-build compatibility or production readiness. The legacy `packages/codex-startup-animation/wallpaper` subtree (`92cfa938ad3f342c9d3111e4a6114cd3f37c7a8b`) is identical at the public anchor and the historical baseline; each run re-verifies the anchor subtree and the restored file digests. The upstream redistribution status remains as recorded in `packages/agent-skin/UPSTREAM.md`.

See [CONTRACT.md](CONTRACT.md) for the agreed offline seams. Source changes are committed before creating a verified external checkpoint with `tools/checkpoint.py`.

## Run the offline composition

Use Python 3.10 or newer and Node. Choose a new evidence directory beneath this
working tree's `.scratch`. The builder checks the fixed registered material
digests; `RESCUE_MATERIALS` must point to the authorized local private-material
directory. Materials and generated resources stay outside Git.

```sh
RESCUE_MODULES="$PWD/benchmarks/agent-skin-rescue"
RESCUE_EVIDENCE="$PWD/.scratch/new-rescue-run"
python3 -B "$RESCUE_MODULES/rebind/build_candidate.py" \
  --root "$RESCUE_EVIDENCE" --source "$PWD/packages/agent-skin" \
  --materials "$RESCUE_MATERIALS" --tools "$RESCUE_MODULES"
python3 -B "$RESCUE_MODULES/integration.py" \
  --root "$RESCUE_EVIDENCE" --binding build/binding.json \
  --producer producer/0/command.json --out "$RESCUE_EVIDENCE/integration"
```

The resource root contains relative binding paths. Supervisor source registration
is anchored to this checkout; its output directory is a private descendant of the
resource root. The composition creates only a synthetic bundle registration and
private layout, verifies resource producers, exercises a controlled handoff and
one VM context, then archives stable raw streams without changing their producers.
A successful composition remains an offline fixture result.

Run component regressions separately from the expensive browser suite:

```sh
python3 -B "$RESCUE_MODULES/tools/run_components.py" \
  --out "$RESCUE_EVIDENCE/component-tests" --resource-root "$RESCUE_EVIDENCE"
python3 -B "$RESCUE_MODULES/tools/verify_source.py" \
  --out "$RESCUE_EVIDENCE/repository-gates"
```

See [browser instructions](browser/README.md) for the private headless workflow.
Preserve failed producers and use new output paths for subsequent attempts. A
verified checkpoint contains committed safe source; raw evidence and private
materials need their own explicitly scoped private backup and manifest.

The component entrypoint supplies the isolation output and lifecycle harness
arguments explicitly. It includes the host-guard and listener-gate tests, which
require macOS and Seatbelt. It prepares files and runs controlled Node models;
it does not start Chrome or repeat the formal 256-test browser prerequisite.
The repository-wide `scripts/verify.py` does not run these candidate-specific
component or browser suites; run them separately as described here.

The source-verification entrypoint runs every existing repository gate and keeps
all tracked source, including this candidate, in the public file inventory. Only
untracked root `.scratch/` and the retained `benchmarks/agent-skin-rescue/.scratch/`
runtime data stay out of that inventory — durably via the committed `.gitignore`,
re-asserted process-locally during verification: those preserved negative fixtures
deliberately contain invalid JSON and links. A process-local
Git discovery ceiling keeps synthetic independent projects from inheriting the
enclosing repository remote. HOME remains private at its original long path;
no assertion, repository configuration, global configuration, or test is removed.
The unadjusted first verification failure remains preserved separately.
