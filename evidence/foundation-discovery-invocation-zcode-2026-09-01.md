# Foundation discovery/invocation receipt — zcode — 2026-09-01

This receipt records a redacted real-host check of zcode skill discovery for the four Foundation Agent Skills packages. It contains no temporary path, user identity, account data or raw transcript. Host-side invocation was not evidenced on this machine; the deterministic blocker is recorded below.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `14e0bebed2619cfcbf6fd79df3537b742deed70b` (disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Python: 3.14.7
- Node.js: 24.15.0
- Host: zcode headless CLI `0.16.5` (run via the ZCode.app 3.10.2 bundle)
- Mode: disposable checkout, project-scope Agent Skills root (`.agents/skills`), linked install via the neutral Foundation CLI, deterministic host CLI probe, attempt-1

## Install step

~~~bash
python3 scripts/azhou_hub.py setup --skill azhou-info --skill azhou-doctor --skill azhou-setup --skill azhou-verify \
  --target <checkout>/.agents/skills --mode link --apply --plan-id <dry-run planId> --json
~~~

- Dry-run `planId`: `7896c024d36b90f0b71cee479ab4d320c9f80cd5c9a2b7151a1eb70a59eaec28`; apply exit `0`; all four skills linked.

## Results

| Check | Result | Evidence |
|---|---|---|
| Project-scope linked install of the four packages | `PASS` | Foundation CLI apply receipt: exit 0, four linked entries under the checkout's project skills root. |
| Host discovery | `PASS` | `zcode skills list` (exit 0) listed all four skills with scope `project/agents`, each resolved to its `SKILL.md` under the checkout's `.agents/skills` root. |
| Host invocation | `NOT EVIDENCED` | See blocker below. |

### Invocation blocker (recorded, not worked around)

Headless invocation (`zcode -p`) on this machine fails deterministically before any model call:

~~~text
Error: Model config is missing. Create <user-level>/.zcode/cli/config.json with an explicit model provider before running ZCode.
~~~

The zcode CLI reads this configuration only from the user-level home; no environment variable or project-scope override redirects it. The machine's Z.AI login exists only in the separate desktop-app configuration, so a model provider entry would be a new user-level configuration decision, outside this receipt's authority.

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout.
2. Dry-run then apply `azhou_hub.py setup` for the four skills into `<checkout>/.agents/skills`.
3. Run `zcode skills list --cwd <checkout>` and check the four names appear with scope `project/agents`.
4. `zcode -p` headless invocation requires a model provider decision recorded in the user-level zcode CLI config, which is outside this receipt's authority.

## Claim boundary

This proves zcode 0.16.5 discovers project-scoped linked installs of the four Foundation packages on this machine. It does not prove model-driven invocation, GUI-surface behavior, or parity with any other host. Raw run artifacts stay Git-external; nothing private is committed.