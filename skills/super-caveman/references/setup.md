# Setup

## Core requirements

- Agent Skills-compatible harness
- Python 3.10 or newer for `compression_guard.py`
- Python standard library only
- A filesystem that permits same-directory hard links for guarded apply/restore; the runtime probes this before moving the source and fails closed when unsupported

Check commands before changing a file:

```bash
python3 "$SKILL_DIR/scripts/compression_guard.py" --help
python3 "$SKILL_DIR/scripts/compression_guard.py" preflight /absolute/path/to/file --json
python3 "$SKILL_DIR/scripts/compression_guard.py" finalize --help
```

No global install, API key, Node.js package, hook, background service, or model-specific package identity is required.

## Installation boundary

Install the complete `skills/super-caveman/` directory under one configured skill root. Do not install the seven upstream Caveman source names beside it. Reload the harness if its skill catalog was already cached.

Canonical package name: `super-caveman`. `/caveman` and the six companion commands are compatibility triggers routed through this package, not separate packages.

Do not modify global harness settings or session-log locations as part of setup. Optional host adapters require a separate explicit review and authorization.
