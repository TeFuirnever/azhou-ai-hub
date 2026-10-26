# Agent Orchestration Kit

A small, local kit for role responsibilities, focused handoffs, and evidence-based verification. **The only implemented integration is Codex.** ZCode, Claude Code and MiMo Code (`mimo`) are maintained Hub Skill targets, but this kit has no native role installer for them. The user's later MiMo Code clarification resolves the “MiniCode” name left unidentified in the 2026-10-25 guide.

This package is a personalized continuation of [donvito/codex-astra-luna-orchestrator](https://github.com/donvito/codex-astra-luna-orchestrator). Its [Apache 2.0 license](LICENSE) and upstream attribution are retained. The new name does not imply a published package or an upstream rename. See [UPSTREAM.md](UPSTREAM.md) for the imported source revision and update procedure.

## One-command user installation

From the Azhou AI Hub repository root:

```sh
./packages/agent-orchestration-kit/setup.sh
```

No business-project path or manual copying is needed. This installs **azhou-balanced** into the current user's Codex configuration and personal Skill directory:

| Responsibility | Model | Reasoning |
|---|---|---|
| Root | GPT-6.1 Sol | high |
| Independent reviewer | GPT-6.1 Sol | high |
| Explorer, worker, tester, researcher | GPT-6 Luna | max |
| Optional Astra specialist | GPT-6 Astra | medium |

Standard speed (`service_tier = "default"`); at most four concurrent child agents. The existing Astra escalation conditions remain in the Skill. Installation does not switch the model of an active conversation.

Requirements: Python 3.11 or newer, and a Codex runtime supporting standalone named agents and the native discovery methods used by this kit. No pip package or background service is installed. On macOS, the installer prefers the Codex/ChatGPT application whose bundle identifies the Codex app, and reports any different PATH runtime. The acceptance machine has ChatGPT App 26.1021.31345, bundled CLI `0.164.0-alpha.11.1`, and PATH CLI `0.160.1`; the bundled runtime is the validated target.

```sh
./packages/agent-orchestration-kit/setup.sh --dry-run
./packages/agent-orchestration-kit/setup.sh --codex-bin /absolute/path/to/codex
```

The scripts resolve profiles and helper files relative to their own package directory, so they can also be invoked by path from another working directory. The workflow guides below show `./setup.sh` commands from `packages/agent-orchestration-kit`.

`CODEX_HOME` is respected; otherwise the config directory is `~/.codex`. The personal Skill directory defaults to `~/.agents/skills`, independently of `CODEX_HOME`. Explicit `--codex-home` and `--skills-dir` are available for controlled targets. An alternate Skill location must be discoverable by the selected Codex runtime for native verification to pass. Paths are resolved at execution; profile templates contain no personal username.

## What installation owns

- Seven model/orchestration settings in `config.toml`: `model`, `model_reasoning_effort`, `service_tier`, and four documented `[agents]` settings. The legacy `agents.max_threads` alias is migrated to `max_concurrent_threads_per_session` if present.
- Six standalone files in `agents/`: `explorer`, `worker`, `tester`, `researcher`, `reviewer`, and `astra-specialist`.
- `astra-orchestrator/SKILL.md` in the selected personal Skill directory.
- One marked block in the user `AGENTS.md`.
- `agent-orchestration-kit/state.json`, a small ownership/recovery record containing only owned settings and file fingerprints.

The installer parses TOML with `tomllib`, replaces only owned scalar values, and reparses the result against the expected semantic diff. Unrelated text and comments remain in place. Normal tables, quoted scalar keys, and dotted scalar keys are supported. An owned value embedded in an inline table is rejected before target writes, with a request to expand that table; the installer never rewrites the entire personal configuration to work around it.

Unrelated MCP, Hooks, plugins, credentials, permissions, roles, and instruction text are preserved. User changes to previously installed owned keys/files/block cause a preflight stop. A different filename defining the same agent `name` is a conflict too: Codex uses the TOML `name` field as its identity. Symlinks and file/directory conflicts at managed targets are refused. Exact source content or exact recorded hashes from the old `azhou-balanced` installation can be adopted; unknown content is never silently overwritten.

## Failure and repeated execution

Preflight checks the source contract, target file types, role identities, existing ownership, TOML, runtime, and native config parsing before writing. Changed files are replaced atomically. A temporary, private transaction journal stores the original bytes and modes; a write or native-verification failure restores originals and removes files created by that attempt. Edits made by another process are never silently rolled back.

On success, the journal is removed. An identical second installation has zero changed files, preserves modification times, and creates no timestamped backups. If an abnormal process termination leaves the fixed transaction directory, the next install stops. Inspect it, then restore using the same target arguments:

```sh
./packages/agent-orchestration-kit/setup.sh --recover
```

Recovery refuses unexpected target paths or conflicting edits. A journal that needs manual attention is retained rather than discarded. There is no scheduled cleanup task.

The one-time migration keeps `~/.codex/agent-orchestration-kit/legacy-recovery.json`: deduplicated unique pre-install values, historical run identifiers, and a cleanup inventory. It contains personal recovery data and is deliberately **not in Git**. See [the migration and acceptance report](guides/migration-2026-10-25.md).

## Native loading and permissions

The installation result distinguishes three kinds of evidence:

1. **File validity:** source and merged TOML parse, unrelated configuration compares equal, and the transaction succeeds.
2. **Native discovery:** the selected App runtime rereads configuration and reports named agents and the installed Skill through its native app-server protocol. This is a local read-only check, not a model request.
3. **Actual execution:** the acceptance report records a bounded native run and its session/turn metadata. Agent claims about their model are not used as proof.

New root sessions use the installed defaults unless a project, profile, or explicit session override takes precedence. Existing sessions are not restarted. Begin a new session for reliable acceptance of changed defaults/roles; Skill discovery can refresh independently. The installer never rewrites project trust or permissions.

**Read-only instructions are behavioral.** Current Codex subagents inherit their parent's sandbox and approval policy. A custom role's `sandbox_mode` cannot establish a separate read-only sandbox, so the current `azhou-balanced` role files omit that ineffective field. The instructions still tell explorer/researcher/reviewer/Astra specialist to avoid edits. The legacy profiles retain their historical content; those fields also must not be interpreted as enforced per-role isolation.

Official contracts: [Subagents](https://developers.openai.com/codex/subagents), [Skills](https://developers.openai.com/codex/skills), [Configuration reference](https://developers.openai.com/codex/config-reference).

## Compatibility and names

| Name surface | Decision |
|---|---|
| Project brand / local directory | `agent-orchestration-kit` |
| Default command | `./setup.sh` installs current-user `azhou-balanced` |
| Legacy shell project installer | `./setup.sh --project` |
| Existing Windows project installer | `setup.ps1` retained; menu adds balanced profile |
| Skill invocation | `$astra-orchestrator` retained |
| Role names | Existing six names retained |
| Instruction markers | `ASTRA-LUNA-ORCHESTRATOR:BEGIN/END` retained |
| New ownership record | `agent-orchestration-kit/state.json` |
| Upstream URL / historical commits | Original names retained as provenance |

The standalone package lives at `packages/agent-orchestration-kit` in the Azhou AI Hub monorepo. Its installer, profiles, Skill, tests, and guides are self-contained; installation no longer depends on a sibling checkout.

## Existing project profiles

For explicit project-level installation:

```sh
./packages/agent-orchestration-kit/setup.sh --project
```

The interactive path/overwrite prompts remain. Existing numeric choices 1–6 keep their meaning; choice 7 and Enter select `azhou-balanced`. This legacy copy workflow is separate from the transactional user installer.

| Choice | Profile | Root | Execution | Reviewer | Children |
|---|---|---|---|---|---:|
| 7 (default) | `azhou-balanced` | Sol high | Luna max | Sol high | 4 |
| 1 | `pro` | Astra medium | Luna max | Astra low | 4 |
| 2 | `plus` | Luna max | Luna medium | Astra low | 4 |
| 3 | `pro-max-2-subagents` | Astra medium | Luna max | Astra low | 2 |
| 4 | `plus-max-2-subagents` | Luna max | Luna medium | Astra low | 2 |
| 5 | `GPT6-SolMax-LunaMax` | Sol max | Luna max | Sol max | 4 |
| 6 | `GPT6-SolMedium-LunaMax` | Sol medium | Luna max | Sol medium | 4 |

Windows users retain the existing PowerShell project entry (`pwsh -File .\packages\agent-orchestration-kit\setup.ps1`). The new user installer uses POSIX pipe polling and does not support Windows global installation in this round. This round validates macOS; Linux runtime behavior and the Windows project entry were not exercised.

## Scope and verification

Generic role duties, bounded task handoffs, non-overlapping ownership, and evidence reporting are reusable ideas. Codex TOML, paths, model identifiers, role invocation, permissions, and load precedence are Codex-specific. See [harness boundaries](guides/harness-boundaries.md) before proposing another integration. No adapter registry, common runtime, cross-harness dispatcher, or automatic budget manager is included.

From the Hub repository root, run the deterministic test suite without bytecode residue:

```sh
cd packages/agent-orchestration-kit
python3 -B -m unittest discover -s tests -v
```

`tests/test_install_codex.py` checks preservation and failure behavior independently of installer success messages. `tests/test_profiles.py` covers balanced and legacy profile selection. Native discovery and the one bounded on-device run are recorded in the acceptance report; routine unit tests do not spend model tokens.

The existing [workflow guides](guides/full-orchestration.md), [token-usage tooling](guides/token-usage.md), and historical profiles remain available as explicit alternatives. They do not change the default installation scheme.
