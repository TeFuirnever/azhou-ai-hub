# Dependencies and setup

Read this before first use, or whenever the installed private skill, the doctor gate, the runtime lock, or the handoff path fails.

## Runtime requirements

| Requirement | Source | Purpose |
|---|---|---|
| Private `azhou-imagegen` skill install | The machine's already-installed skill root (for example `~/.agents/skills/azhou-imagegen/`); resolved through the harness skill roots, never downloaded here | The generation CLI, its doctor gate, the runtime lock, and the export command |
| Python 3 | The runtime that executes the installed skill's standard-library CLI | Run `azhou_gen.py`, the doctor gate, and the export helper |
| Local inference stack and model weights | Installed and licensed inside the private environment only | The actual raster generation; never vendored, fetched, or reinstalled by this package |
| macOS | The host the private pipeline is currently hardened on | Resource observation; the doctor gate reports the real machine state |

This package contains the contract layer only. The generation code, prompt templates, style masters, character references, model weights, runtime locks, and receipt stores of the private install are **not vendored** and are never copied into this package or any checkout. A missing install is a named hold, not a prompt for a substitute.

**Fail closed:** when the installed private skill cannot be resolved, its Python entry point is broken, or the doctor gate reports a blocking item, stop with `🔒 阿舟暂停这一项` and name the gap. Do not fall back to another generator, a different model, an online image service, or a partial copy of the private install. Do not install or download models to "fix" the gate; fixing the private environment is the owner's authorized action.

## Locate and inspect before executing

Resolve the install through the harness skill roots in order, then verify the CLI responds:

```bash
python3 <installed>/scripts/azhou_gen.py --help
python3 <installed>/scripts/azhou_gen.py --doctor --json
```

Treat `--help` as the parameter authority — flags, defaults, and profiles are read from the installed copy, not from memory or from this document. `--doctor --json` must be run with the request's actual profile, model, and output parameters; a doctor pass on different parameters proves nothing for this request. The doctor reports model components, applicable LoRAs, the runtime lock, the output directory, and observed machine resources. It never downloads anything, and it never installs anything.

On a machine without a captured runtime lock, the first run may capture one with the installed runtime tool (`azhou_runtime.py --create` pointing at a new lock file). Capture records the runtime identity; it does not install, download, or overwrite an existing lock, and a captured lock is handed to `--runtime-lock` or the private environment's default location — never committed anywhere.

## Execution lock and concurrency

The installed CLI holds a non-blocking machine-local file lock while a generation task runs. When another local inference task owns the lock, the new task is refused: report the hold and wait for the owner task to finish instead of bypassing, killing, or queuing silently. A timeout budget is a resource bound, not a duration promise; a started process is not a delivered image.

## Outputs, exports, and cleanliness

- Write outputs only to explicit new paths chosen for the request; never overwrite an existing image, lock, receipt, or master.
- Review copies are exported with the installed export command to a new path and verified by pixel-level read-back; the internal original is never modified.
- Prompt files, receipts, dispatch records, and exported copies can carry private content: keep them under the authorized root or an ignored local path, out of Git, unless the user explicitly selects a sanitized copy.

## Maintenance boundary

The private install is upgraded inside its authorized environment by its owner; this package pins no version and must not reach into, patch, or reconfigure it. When the private CLI's command surface changes in a way this contract depends on, update this package's workflow and [provenance](provenance.md) baseline hashes together in one reviewed change, and re-run the skill validator before the change lands. Do not silently drift the contract ahead of or behind the installed reality.
