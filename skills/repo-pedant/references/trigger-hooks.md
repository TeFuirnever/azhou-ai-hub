# Trigger and lifecycle hook contract

This contract adapts proven lifecycle patterns from `planning-with-files` without copying its planning subsystem. Repo-pedant owns repository closeout; it does not own task planning, transcript replay, or host continuation loops.

## Three trigger layers

| Layer | Signal | Allowed behavior |
|---|---|---|
| Skill discovery | Explicit cleanup, sync, milestone, stale-doc, memory-conflict, handoff, or evolve request | Execute the selected repo-pedant mode. |
| Project rule | Optional always-loaded instruction tells the agent to invoke repo-pedant at explicit task close | Invoke only after the user or task controller explicitly closes the task. |
| Lifecycle hook | Host Stop/agent-end/closeout event observes an unfinished or absent closeout receipt | Emit one bounded reminder by default; an opt-in supported gate may request continuation. |

An inferred milestone is detection, not write authorization. Hooks never edit repository files, install themselves, publish, or start evolution.

User-facing hook messages use the fixed `🟡 阿舟提醒` and `🧠 阿舟记忆检查` prefixes from [brand-layer.md](brand-layer.md). The message remains a constant: brand text never permits state, transcript, or file content to leak into control output.

## Reused planning-with-files mechanisms

| Mechanism | Repo-pedant adaptation |
|---|---|
| Thin host adapter plus neutral core | Host input/output conversion stays outside closeout-state evaluation. |
| Explicit activation and one-shot opt-out | Hook behavior is inactive until installed; `REPO_PEDANT_DISABLED=1` silences one invocation. |
| Session/workspace isolation | A hook evaluates only state canonically contained under the current repository, keyed to the current session when the host provides an ID. |
| Advisory default | Unsupported, ambiguous, unconfigured, or failed hook paths exit successfully and stay non-mutating. |
| Bounded continuation | Opt-in gate requires a current unfinished closeout marker, recursion guard, progress since the last block, and a small cap. |
| Fixed control output | Hook control messages use constants plus validated state labels; no transcript, spec body, plan body, or arbitrary file text enters a continuation reason. |
| Pre-compaction flush | Only remind when a repo-pedant closeout run is already active and has unrecorded progress. |
| Doctor | Verify host feature flag, hook location, duplicate installs, executable runtime, workspace containment, and event output. |

## Deliberately not imported

- `task_plan.md`, `findings.md`, `progress.md`, active-plan resolution, planning slash commands, or plan-body injection;
- raw session catchup or command replay;
- unconditional Cursor-style follow-up for every incomplete task;
- claims of hard blocking on a host whose checked adapter only emits a message;
- planning attestation, nonces, or ledgers that duplicate repo-pedant receipts and evidence bundles;
- a model-specific `agents/openai.yaml` runtime dependency.

## Host truth table

| Host surface | Evidence from planning-with-files v3.8.1 | Repo-pedant target |
|---|---|---|
| Claude Code skill/plugin hooks | Prompt, pre-tool, post-tool, PreCompact, and Stop; gated Stop can emit `decision:block` | Advisory default; optional gate only after integration tests prove the host contract. |
| Codex `.codex/hooks.json` | SessionStart, prompt, Bash pre/post, PreCompact, Stop; checked Stop adapter is advisory | Advisory closeout reminder and doctor; never advertise hard block. |
| Cursor hooks | Prompt, tool, stop with follow-up loop limit 3; checked adapter lacks isolation/safety guards | Do not copy until explicit activation, containment, and stall guards exist. |
| Pi extension | Explicit `/plan-execute`, session-plan counter, notify mode, agent-end follow-up cap, PreCompact | Preferred model for an optional bounded follow-up adapter. |
| OpenCode skill/scripts | Skill and recovery scripts exist; no checked hard-stop adapter | Skill description/project rule first; hook capability reported as unavailable until implemented. |
| Other runtimes including zcode | No proven hook contract in the audited source | Keep runtime-neutral skill behavior; use history collector and manual invocation. |

## Optional planning composition

When planning-with-files is active, its all-phases-complete state may be treated as a closeout reminder signal. Repo-pedant must still establish its own explicit mode, repository scope, current code truth, authorization boundary, and receipt. Planning state never becomes repository authority.

## Neutral core

The shipped core is `scripts/closeout_hook.py`. It reads only a canonically contained `.azhou/repo-pedant/closeout-state.json` matching `assets/closeout-state.schema.json`. A symlink, external path, invalid schema, workspace mismatch, absent state, completed state, or session mismatch exits successfully without control output.

Create the marker only after an explicit closeout begins:

```json
{
  "schema_version": "repo-pedant.closeout-state.v1",
  "repo_root": "/absolute/project/root",
  "session_id": "host-session-id-or-empty",
  "status": "active",
  "progress": 1,
  "unrecorded_progress": false,
  "receipt_digest": null
}
```

Advance `progress` only after a completed closeout step. Set `unrecorded_progress` before compaction when work is not yet reflected in the inventory/receipt. Set `complete` and the SHA-256 receipt digest after validation; use `held` only when the final receipt names every unresolved hold.

Core smoke checks:

```bash
python3 <skill-dir>/scripts/closeout_hook.py event \
  --event stop --workspace /absolute/project/root \
  --format plain --mode advisory

python3 <skill-dir>/scripts/closeout_hook.py event \
  --event precompact --workspace /absolute/project/root \
  --format plain --mode advisory
```

`REPO_PEDANT_DISABLED=1` suppresses one invocation. Input is capped at 64KB by default and never echoed.

## Host installation

- Codex: merge `assets/hooks/codex-hooks.fragment.json` into the supported workspace/global hook configuration. Keep `--mode advisory`; the audited adapter is non-blocking.
- Claude Code: merge `assets/hooks/claude-hooks.fragment.json`. Advisory is default. To opt into tested Stop blocking, change only the Stop command to `--mode gate`; private counters cap blocks at three and require progress between blocks.
- Pi: call the same core from an explicitly activated `agent_end`/`pre_compact` extension; keep per-session activation in the extension and advisory output unless its continuation contract is tested.
- OpenCode, Cursor, zcode, and other harnesses: wire Stop/agent-end only after verifying event input/output and workspace identity. Until then use the project rule or skill trigger; do not claim a hook is active.

Optional always-loaded reminder text lives at `assets/hooks/project-rule.md`.

## Doctor

Run after installation and after host upgrades:

```bash
python3 <skill-dir>/scripts/closeout_hook.py doctor \
  --workspace /absolute/project/root \
  --config /absolute/workspace-hook-config.json \
  --require-env HOST_HOOKS_ENABLED=1
```

Pass every actual global and workspace hook config with repeated `--config`. The doctor reports unreadable configs, a malformed/foreign state marker, missing required feature flags, and duplicate configs containing `closeout_hook.py`. A warning for absent state is normal when no closeout is active.

## Required regressions

1. Explicit trigger vocabulary invokes; inferred milestones only remind.
2. No state or host support exits silently with success.
3. External symlink/state path is rejected.
4. One-shot disable suppresses every lifecycle event.
5. Advisory output contains no file or transcript text.
6. Optional gate blocks only with every guard and stops on recursion, stall, or cap.
7. Doctor detects missing feature flags and duplicate global/workspace installs.
