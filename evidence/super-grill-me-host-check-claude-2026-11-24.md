# Super Grill Me host check receipt: Claude Code, 2026-11-24

This receipt records a redacted real-host check that Claude Code discovers and invokes the `super-grill-me` package. It contains no temporary path, user identity, account data or raw transcript. The verbatim records stay Git-external in the maintainer's evidence store.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Commit: `8463555cbea982932ecc3bfe59145f5624f42d0b`, the head of PR #578. Its tree is identical to the tree of squash commit `1eeb03c6005ac08b2c852d6f61823181bcee4fe4` on main. Base for comparison: `30d81370565ad4b0e4307520290f4137f32bf815`.
- Package: `skills/super-grill-me/`. `SKILL.md` SHA-256 `05e356f839278a294af9ec5dfd831c6fd3b42fba58b42fd0e49312b1859ffd4d`. The installer's `source_digest` of the package tree is `fe5f3fc53101a2263d63a789eed5a71d6ee5fe270c7927bdf15284b2dd9e3d81`.
- Host: macOS 27.2.1 (26B131), arm64.
- Host CLI: Claude Code `2.1.330` (`claude --version`), headless `claude -p`, one run per message.
- Model route, as the host's own log line names it: `xiaomi/mimo-v2.6-pro`. Log lines of two runs also name `xiaomi/mimo-v2.6-flash`.
- Tool permission: the stream capture's init event reports `permissionMode: auto`. That is the test machine's own configuration. No permission flag was passed.
- Mode: two disposable exports made with `git archive`, project-scope Agent Skills root (`.claude/skills`), linked install through the neutral Hub CLI.
- Named human check: none at receipt time. An independent machine judge, a fresh Claude Sonnet 4.5 session that read the records only, returned `PASS`. The verdict is on PR #578.

## Inputs

| Message | SHA-256 of the text |
|---|---|
| a. List the skills available to you in this project by name only. | `1360fa2563282f91a8501ad34de6f70ab66a413a2b0ebf2172cb2a0c754c282d` |
| b. /super-grill-me grill me on this plan: we will add a nightly cron job that deletes user uploads older than 30 days. | `bcd730c381ccf1ca7651f0b835cf1f9dc90ffa026500fac3d57a3178e4399ab1` |
| c. /super-grill-me | `c0744a97b9109a9867d0df7fb552878f7b74fc5509b288dc747b3e703decaa17` |
| d. Before we build anything, I want to stress-test my thinking on this: we will add a nightly cron job that deletes user uploads older than 30 days. | `6266dcda0a6c605f7cfb2514999c73d35a2b6f438c93cc7fcd792c756f9783cc` |

## Install step

~~~bash
python3 scripts/azhou_hub.py setup --skill super-grill-me --target <export>/.claude/skills --mode link --json
python3 scripts/azhou_hub.py setup --skill super-grill-me --target <export>/.claude/skills --mode link --apply --plan-id <dry-run planId> --json
~~~

- Base export: the installer rejects the unknown skill with exit 2 and creates nothing under the target root.
- Head export: the dry run returns a planId. Apply exits 0 and leaves one link.

## Results

| Check | Result | Evidence |
|---|---|---|
| Project-scope linked install of the package | `PASS` | Installer receipts. Base: exit 2, nothing created. Head: dry run, then apply with exit 0 and one link. |
| Host discovery | `PASS` | A headless run asked to list the project's skills by name listed `super-grill-me` among 49 names (exit 0 in 29.7 s). |
| Explicit request with a plan | `PASS`, attempt 2 | The reply carried the startup line with `mode=start` and five numbered questions, each with a recommended answer (exit 0 in 161.3 s). Attempt 1 ended by a 900 s bound with empty output (exit 142 in 900.0 s). |
| Nothing named | `PASS` | The reply carried the startup line with `scope=unresolved`, the hold anchor with `reason=nothing-named`, and a receipt with `status: hold`, `rounds: 0` and `frontier: unopened` (exit 0 in 20.6 s). |
| Model-reachable request, no skill named | `PASS`, attempt 2 | The reply carried the startup line with `mode=start` and four numbered questions, each with a recommended answer (exit 0 in 343.6 s). Attempt 1 ended by a 900 s bound with empty output (exit 142 in 900.0 s). |
| Base runs no interview | `PASS` | The explicit request on the base export, captured in stream mode, produced two short status lines and no interview question (exit 142 in 600.0 s, ended by the bound). |
| Repository facts | `PASS` | `skills/` holds 20 directories on the base and 21 on the head. The package's 8 tests pass on the head. The README install block names the skill on the head and not on the base. |

## Reply digests

| Message | Record | SHA-256 of the captured reply |
|---|---|---|
| a | `03-head-discovery.txt`, record 03-1, attempt 1 | `d6ecfe682cb9cff275522c92524c0dab085981fe65a5290a46d404d09e748465` |
| b | `04-head-explicit.txt`, record 04-2, attempt 2 | `5352e1d37236aba2061ecf156e564a0be0b7035f3e14303db6169eb970c55702` |
| c | `05-head-nothing-named.txt`, record 05-1, attempt 1 | `0a0afd1f4f0a1f7ff6637e142de317d5c6637a764da5c1a3d1199dd8af7f6a3a` |
| d | `06-head-model-reachable.txt`, record 06-2, attempt 2 | `fea13170c8008cbe62ebee5ded1f65c008ddf5efba05d8ce1b83beedc24010d0` |

## Deviations recorded

1. One character of the hold anchor's fixed text was damaged in the nothing-named reply. The second character of the anchor's name was emitted as U+FFFD. The host's own session record holds the same byte sequence, so the damage came from the model output. The `（reason=nothing-named）` group and every receipt field were intact.
2. The two plan-given replies carried the startup line and no design-tree or round stage line. In the first attempts, the host model's tool calls show that it did not open `references/brand-layer.md`, where those two lines are defined. The walkthroughs recorded in `benchmarks/super-grill-me/README.md` ran on another model that did read that file, and they emitted both lines.
3. The questions were open questions with a separate recommended answer each. They were not worded so that "yes" accepts the recommendation. The explicit-request reply told the reader that a recommendation can be accepted by naming it.
4. In plain output mode the host printed nothing until the process exited, and the process stayed alive while background work ran that the model had started on its own. That is why two first attempts ended by the time bound with empty output. The first-round reply of each had been written about a minute after the start, as the host's own session log shows.
5. The absence of the stage lines depends on whether the model opens the reference file, not on the host alone. A later run on the same host and route, started in a small scratch project with the shipped bytes, opened `references/brand-layer.md` and emitted the startup line, the design-tree line, a facts line and the round line before six questions worded so that "yes" accepts each recommendation (429.4 s, one run). The reply's SHA-256 is `0ed6ef7837fab8d42aea51ae28bdc6293482a5084666530f6b0b1b89c26c1df1`.
## Reproduction

1. Export the commit into a disposable directory with `git archive <commit> | tar -x -C <directory>`.
2. Dry-run, then apply, `azhou_hub.py setup` for `super-grill-me` into `<directory>/.claude/skills`.
3. Run one headless `claude -p` run per message from inside the export. Bound each run generously. The plan-given runs took up to 344 s on this route. The stream form `--output-format stream-json --verbose` shows a reply while background work is still running.

## Claim boundary

This proves that Claude Code 2.1.330 discovers a project-scoped linked install of `super-grill-me` and runs the interview, the model-reachable request and the nothing-named hold in headless runs on one machine, on the model route named above. It does not prove a personal-root install, an interactive session, another host, another model, or a project that holds the facts of the plan under interview. The runs in this receipt end at the first answer. A separate session on the same package bytes went past that point and returned `complete_with_holds`. [Multi-round session record](../benchmarks/super-grill-me/README.md)
