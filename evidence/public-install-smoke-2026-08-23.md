# Public install smoke receipt — 2026-08-23

This receipt records a redacted clean-install check against the public GitHub repository. It contains no temporary directory, user identity, account data or runtime history.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Public default-branch commit: `0a3fa879ce36062f66a61941e433ef446807c99c`
- Host: macOS 26.6.2
- Node.js: 24.15.0
- npm: 11.12.1
- `skills` CLI: 1.5.23
- Install mode: isolated temporary Git repository, Codex target, copied package, non-interactive

## Results

| Check | Result | Evidence |
|---|---|---|
| Public discovery | `PASS` | `skills add ... --list` found exactly `excalidraw-diagram` and `repo-pedant`. |
| Repo Pedant install | `PASS` | 28 files copied; `SKILL.md`, `scripts/closeout_hook.py` and `references/neat-freak-compatibility.md` present. |
| Excalidraw Diagram install | `PASS` | 505 files copied; `SKILL.md`, offline Excalidraw runtime, Excalifont, component libraries and locked Node dependency file present. |
| Development links | `PASS` | Both existing contributor symlinks were byte-for-byte unchanged after the isolated installs. |

## Reproduction

Run each install from a different empty Git repository:

```bash
npx --yes skills add TeFuirnever/azhou-ai-hub --list
npx --yes skills add TeFuirnever/azhou-ai-hub --skill repo-pedant --agent codex --copy -y
npx --yes skills add TeFuirnever/azhou-ai-hub --skill excalidraw-diagram --agent codex --copy -y
```

## Claim boundary

This proves that the public default branch exposes only the two canonical skills and that each selected runtime package can be copied with its critical files intact. It does not prove a tagged release, every harness-specific install path, task quality, Excalidraw visual quality, Social Preview upload or publication success.
