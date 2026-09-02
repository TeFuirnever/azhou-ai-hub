# Canonical SKILL.md package load receipt — zcode — 2026-09-02

This receipt records a redacted real-host check that the zcode host discovers and loads all ten canonical Agent Skills packages from a project-scope linked install. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `9841d3fac51623d9a9b81fd546464c1c8f7153b1` (merged `main`; disposable Git checkout at a temporary path, removed after capture)
- Host: macOS 26.6.2, arm64
- Host: zcode headless CLI `0.16.5` (run via the ZCode.app `3.10.1` bundle, `ZCODE_APP_VERSION` recorded by the host), Node.js 24.15.0
- Python: 3.14.7
- Mode: disposable checkout, project-scope Agent Skills root (`.agents/skills`), linked install via the neutral Foundation CLI, headless non-interactive model runs (`zcode --cwd <checkout> --prompt …`, GLM-5.1 via the BigModel Coding Plan), attempt-1 per run

## Install step

~~~bash
python3 scripts/azhou_hub.py setup --skill azhou-info --skill azhou-doctor --skill azhou-setup --skill azhou-verify --skill excalidraw-diagram --skill lavish --skill llm-wiki --skill repo-pedant --skill spec-relay --skill super-caveman \
  --target <checkout>/.agents/skills --mode link --apply --plan-id <dry-run planId> --json
~~~

- Dry-run `planId`: `4b74ec667085c405c9d06a9ade6af3995015e4201f25f50750a083d75640a9e2`; apply exit `0`; all ten skills linked. The `planId` is emitted deterministically for the recorded commit and target; no re-apply was needed.

## Results

| Check | Result | Evidence |
|---|---|---|
| Project-scope linked install of all ten canonical packages | `PASS` | Foundation CLI apply receipt: exit `0`, ten linked entries under the checkout's project skills root. |
| Host discovery | `PASS` | `zcode skills list --cwd <checkout>` (exit 0) listed all ten skills with scope `project/agents`, each resolved to its `SKILL.md` under the checkout's `.agents/skills` root. |
| Real load run per package | `PASS` 10/10 | One headless run per package forcing a load of the named package: each run read the package's `SKILL.md` and returned exactly that package's frontmatter `name:` line (10/10 exact matches, exit 0). |
| Real load run (first package, second route) | `PASS` | The `azhou-info` load run re-confirmed discovery+load in a first run before the loop; the ten-run loop covers each package exactly once. |

One invocation that failed at argument parsing before any model run (mis-ordered CLI flags, host printed usage and exited) was recorded and re-invoked with corrected flags; the model run itself was attempt-1. One loop run (super-caveman) was killed by an operator shell timeout before any output and re-invoked once; the recorded run is the first completed model run for that package. Both disclosed invocations produced no model output and are not model attempts.

## Reproduction

1. Clone the repository at the recorded commit into a disposable checkout; append `/.agents/` to `.gitignore` (working-tree-only, disclosed).
2. Dry-run then apply `azhou_hub.py setup` for all ten skills into `<checkout>/.agents/skills`.
3. Run `zcode skills list --cwd <checkout>`; check all ten names appear with scope `project/agents` resolving under the checkout root.
4. For each package, run one headless `--prompt` run forcing a load of that package and check the returned frontmatter name line matches.

## Claim boundary

This proves zcode 0.16.5 discovers and loads the ten canonical packages from a project-scope linked install on this machine, one attempt per package. It does not prove GUI-surface behavior, cross-host parity, or skill-route behavior beyond package load. Raw run artifacts stay Git-external; nothing private is committed.