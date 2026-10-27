# 2026-10-25 migration and acceptance

This report concerns the bounded Codex integration on the inspected Mac. The date uses Asia/Shanghai. Machine-specific full configuration, credentials, and raw histories are excluded from Git. The sanitized acceptance record is [tests/evidence/macos-2026-10-25.json](../tests/evidence/macos-2026-10-25.json).

## Verified starting point

- Starting commit: `44bfe5922cf2f96aecc0fa2a9bab970c343d6f7e`.
- Starting branch: `codex/sol-balanced-global-20261024-234914`; the working tree was clean.
- Work branch: `codex/agent-orchestration-kit-20261025`; no reset, clean, upstream push, or host source edit.
- Upstream: `https://github.com/donvito/codex-astra-luna-orchestrator.git`, retained unchanged.
- App: `/Applications/ChatGPT.app`, bundle `com.openai.codex`, version 26.1021.31345 / build 21828.
- App CLI: `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`, `0.164.0-alpha.11.1`.
- PATH CLI: `0.160.1`, a separate npm installation.
- Python: Homebrew Python 3.14.7; `tomllib` available, `tomlkit` absent. The installer requires only Python 3.11+ standard-library modules.
- No CI workflow existed; `.github/FUNDING.yml` was the only existing GitHub configuration file. No unrelated CI platform was added.

## Four pre-change questions, answered with repository evidence

**Necessary missing work.** `setup.sh` and `setup.ps1` only supported interactive project copying; `README.md` required manual global merging. `tests/test_profiles.py` covered six profiles but omitted `azhou-balanced`. A supported user installer therefore needed explicit ownership, preservation, conflict detection, rollback, and balanced-default tests. The profile's global instructions embedded a personal absolute path. Role `name` values, not filenames alone, needed conflict checks. The installed roles claimed sandbox modes that the current host does not apply per role.

**Primary materials.** The actual scripts established copy/overwrite behavior. The balanced config, six role TOMLs, Skill, and instruction block established the intended contract. Installed bytes matched the old profile at the starting commit. Backup `installation.json` files identified source commits, profiles, changed paths, and prior validation locations. Original configuration snapshots preserved user values that Git could not reconstruct. The native App CLI, generated protocol schema, native `config/read`, `skills/list`, rendered tool schema, and actual session records supplied host evidence.

**Methods.** Read Git status/history/worktrees and applicable instructions first. Parse TOML, perform targeted scalar edits, preserve unrelated raw text, and independently compare before/after bytes and parsed semantics. Use temporary targets for first install, conflicts, repeated execution, and injected failure. Use the App runtime rather than silently taking PATH. Retain known legacy fingerprints for migration; never infer ownership merely from age or a filename.

**Ways to falsify success.** Unexpected config changes, role-name collisions, altered managed content, writes during a failed preflight, incomplete rollback, duplicate instructions, or nonzero second-install changes fail acceptance. Native discovery must show the intended roles/models/efforts and enabled user Skill. Actual model execution must be supported by raw session/turn records, not an agent's self-description. The official [Codex subagent contract](https://developers.openai.com/codex/subagents) falsifies the claim that role-local `sandbox_mode` enforces a separate sandbox.

## Repository and interface migration

At the 2026-10-25 acceptance point, the physical checkout was:

```text
/Users/guanxueliang/Desktop/Matrix/社区工程/agent-orchestration-kit
```

At that inspection, the old sibling `codex-astra-luna-orchestrator` was a relative symlink to the renamed directory; both resolved to the same inode and a single Git working tree. `lsof` found no process using the original repository as its working directory. App prompt history still mentioned the old source path, so the compatibility link preserved resolution then without rewriting history or restarting sessions.

For current installation, run `./setup.sh` from the [Hub package](../README.md). The default is user-level `azhou-balanced`; `./setup.sh --project` preserves the old interactive shell workflow. Existing profile numbers 1–6 retain their meanings, with balanced added as choice 7/default. `setup.ps1` remains the legacy Windows project installer with the same menu addition. `$astra-orchestrator`, the six role names, and existing instruction markers remain compatible. Project branding changed; upstream attribution, license, and historical identifiers did not.

The 2026-10-26 [Hub local handoff](../../../evidence/optional-integrations-local-handoff-2026-10-26.md) verified that the user installation already matched the Hub package and that a fresh `--dry-run` changed nothing after the former checkout was removed. The path above and its sibling symlink are historical, not current install sources.

## Cleanup inventory and recovery responsibility

The authorized historical set was removed: 22 files, totaling **180,800 bytes**. All source file hashes matched the inspected inventory immediately before deletion:

| Historical path under `~/.codex` | Classification | Files | Bytes | Decision / reason |
|---|---|---:|---:|---|
| `config.toml.backup-astra-luna-trial-20261024-222720` | Pre-trial configuration | 1 | 24,383 | Replace with verified minimal recovery values. Its semantic difference from the first global pre-install snapshot is exactly the trial trust entry. |
| `backups/astra-luna-global-20261024-223729` | Config/instruction snapshots | 2 | 28,306 | Preserve unique configuration deltas; original instruction prefix remains verbatim in the current file. |
| Same directory | Installation metadata | 1 | 1,053 | Preserve provenance and file inventory in the fixed migration record. |
| Same directory | Verification files | 6 | 6,646 | Preserve run identifiers and hashes; native history is retained. Remove duplicate prompts/logs/summaries. |
| `backups/astra-sol-balanced-20261024-234914` | Config/instruction/Skill/reviewer snapshots | 4 | 42,257 | Preserve unique config values and old managed block. Old Skill and reviewer match retained `profiles/pro` source exactly. |
| Same directory | Installation metadata | 1 | 1,417 | Preserve source commit/profile and cleanup inventory. |
| Same directory | Verification files | 7 | 76,738 | Preserve historical identifiers/hashes and the new sanitized acceptance evidence. Remove redundant discovery dump and transcripts. |

The initial metadata identified two old temporary validation directories; both were already absent. Its exact old trial-trash location was also absent. No Trash sweep, session cleanup, or unrelated backup deletion was performed.

`~/.codex/agent-orchestration-kit/legacy-recovery.json` is retained at **37,635 bytes**, with mode 0600. The installed ownership `state.json` is **4,417 bytes**. All three configuration snapshots reconstructed successfully from the recovery record and the checked current baseline immediately before cleanup. It stores deduplicated old values/deltas, list splices where appropriate, historical run identifiers, source fingerprints, and the exact cleanup inventory. Reconstruction was verified against the original snapshots before deletion. This record is needed because some old global settings differ from the present configuration and are not in source Git. It is not a complete historical user-home backup and must not be blindly replayed over newer unrelated settings. Restore only deliberately selected values after comparing the current state.

The old project Skill and reviewer snapshots are reproducible from upstream commit `f5efba0f957a1e3f0671e629ccc2c655725a7e7b`, at `profiles/pro/agents/skills/astra-orchestrator/SKILL.md` and `profiles/pro/codex/agents/reviewer.toml`. Their exact hashes are in the private recovery record. Original full configuration and authentication data are not committed.

The new installer removes its transaction journal after success. Its durable `state.json` contains only owned keys, fingerprints, prior owned values, and the old managed instruction block when needed. It does not produce a new permanent timestamped backup on each run. There is no background cleanup service.

### Exact historical file inventory

All paths below are relative to `~/.codex`; these are historical audit entries, not active file links.

| Removed file | Bytes | Purpose / replacement |
|---|---:|---|
| `config.toml.backup-astra-luna-trial-20261024-222720` | 24,383 | Configuration snapshot; unique prior values preserved and reconstruction verified |
| `backups/astra-luna-global-20261024-223729/AGENTS.md.before` | 3,757 | Original prefix remains; old owned block retained where needed |
| `backups/astra-luna-global-20261024-223729/config.toml.before` | 24,549 | Configuration snapshot; unique prior values preserved and reconstruction verified |
| `backups/astra-luna-global-20261024-223729/installation.json` | 1,053 | Installation provenance; minimal fields retained in recovery record |
| `backups/astra-luna-global-20261024-223729/verification/events.jsonl` | 2,107 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-luna-global-20261024-223729/verification/final-response.txt` | 155 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-luna-global-20261024-223729/verification/prompt.txt` | 925 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-luna-global-20261024-223729/verification/run.json` | 299 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-luna-global-20261024-223729/verification/stderr.log` | 482 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-luna-global-20261024-223729/verification/verified-results.json` | 2,678 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-sol-balanced-20261024-234914/AGENTS.md.before` | 4,600 | Original prefix remains; old owned block retained where needed |
| `backups/astra-sol-balanced-20261024-234914/SKILL.md.before` | 12,205 | Exact duplicate of retained upstream source |
| `backups/astra-sol-balanced-20261024-234914/config.toml.before` | 24,577 | Configuration snapshot; unique prior values preserved and reconstruction verified |
| `backups/astra-sol-balanced-20261024-234914/installation.json` | 1,417 | Installation provenance; minimal fields retained in recovery record |
| `backups/astra-sol-balanced-20261024-234914/reviewer.toml.before` | 875 | Exact duplicate of retained upstream source |
| `backups/astra-sol-balanced-20261024-234914/verification/discovery.json` | 33,308 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-sol-balanced-20261024-234914/verification/events.jsonl` | 37,392 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-sol-balanced-20261024-234914/verification/final-response.txt` | 477 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-sol-balanced-20261024-234914/verification/prompt.txt` | 865 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-sol-balanced-20261024-234914/verification/run.json` | 299 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-sol-balanced-20261024-234914/verification/stderr.log` | 363 | Old acceptance material; identifiers/hashes retained, normal native history preserved |
| `backups/astra-sol-balanced-20261024-234914/verification/verified-results.json` | 4,034 | Old acceptance material; identifiers/hashes retained, normal native history preserved |

## Implementation and preservation

`setup.sh` dispatches the default command to `scripts/install_codex.py`. It checks Python before importing the standard-library installer and disables repository bytecode writes. `scripts/codex_native.py` owns only Codex runtime selection and native read-only validation/discovery.

The installed root and reviewer remain Sol/high; explorer/worker/tester/researcher remain Luna/max; Astra specialist remains medium under the existing escalation rules. Standard speed and four concurrent child agents remain unchanged. The current global `config.toml` already matched this contract, so the real installation preserved it byte-for-byte.

The installer validates the source contract and all target paths before mutation. It detects role identities across TOML files, managed content edits, file/directory and symbolic-link conflicts, malformed TOML, and missing runtime/dependencies. It parses TOML and edits only owned scalars, preserving unrelated text/comments; unsupported aggregate representations of owned settings stop before writes. A final semantic comparison rejects unintended changes.

During mutation, files are atomically replaced with original modes retained. A private temporary transaction journal records original bytes and newly created paths. Failures restore touched files and remove new files/directories. A concurrent change prevents destructive automatic rollback and leaves the journal for explicit recovery. `./setup.sh --recover` validates its target allowlist before restoring an interrupted transaction.

## Acceptance evidence

The deterministic suite passed **42 test methods** on this Mac. The independent installer suite contains 25 tests and uses direct byte/mode/mtime/tree snapshots and TOML comparisons. Two regressions found during review—missing recheck for a no-change plan and source-file symlink following—were fixed and retained as tests.

| Acceptance case | Evidence |
|---|---|
| First install / existing personal settings | Isolated targets; unrelated settings, comments, instructions, and roles preserved. |
| Repeat install | Both isolated and actual-user installs: zero changes; bytes, modes, and mtimes unchanged. |
| User modifications / name collisions / file types | Preflight refusal; no target write. Tests include another filename with the same actual agent `name`. |
| Illegal configuration / missing dependency | Malformed source/target TOML and missing Python/runtime stop before installation. |
| Mid-write failure | Fault after the eighth real atomic replacement; existing bytes/modes restored, new files/directories removed. |
| Native verification failure | Full transaction rollback. |
| Retained interrupted transaction | Recovery restores exact originals; unexpected external target is refused. |
| Renamed location | Tests and the actual user install executed from the new physical path. |
| Real configuration preservation | Byte-identical `config.toml`, unchanged instruction text outside the owned block, unchanged unrelated roles. |
| Skill metadata | Skill Creator quick validator passed; native Skill discovery reports enabled/user scope. |

The real user installation changed 9 files (six roles, the Skill, the owned global instruction block, and the ownership record). The following real installation changed 0. The temporary transaction directory was absent afterward.

Native discovery uses `config/read`, `skills/list`, and `debug prompt-input`. The latter exposes named role model/effort bindings in the host-generated `agent_type` tool schema; prose in user/assistant messages is explicitly rejected as evidence by tests. All six roles were discovered with their expected settings; the Skill was discovered at its intended user path and enabled; the managed instruction block appeared in the native prompt. These checks request no model inference.

`app-server --print-startup-config` was inspected but is not used as proof of full configuration validity: in this build it reports requirements and did not reject an invalid reasoning-effort string. The implementation therefore uses TOML/source-contract checks, native staged rereading and role-schema discovery, and the separate actual-run evidence.

### Actual execution

The bounded native run completed with exit code 0 in **70.13 seconds**. Raw thread/turn metadata remains in Codex's normal session store; no raw conversation dump is committed. It used a temporary three-line probe, one worker, and one reviewer. Both child tool outputs independently returned the correct line count and nonce with exit code 0. The probe and global config were unchanged. Spawn records contain named roles and `fork_turns = "none"`, with no model/reasoning overrides; no Astra or nested delegation occurred.

| Actual role | Native thread ID | Raw model / effort |
|---|---|---|
| Root | `01a17005-a381-7343-a360-22ab9e75c6c7` | `gpt-6.1-sol` / `high` |
| Worker | `01a17005-e2e6-7430-9377-a0e753050b5c` | `gpt-6-luna` / `max` |
| Reviewer | `01a17005-f562-73f1-82b8-4250c9144beb` | `gpt-6.1-sol` / `high` |

All three have native `task_complete` events and matching `turn_context` model/effort fields. The temporary validation directory (8,385 bytes of probe/run/events/stderr files) was removed after extracting the sanitized evidence. Native session history was retained.

The host logged that its global personal Skill scan reached the traversal limit. The specific orchestrator Skill was discovered, enabled, and actually read by the root, so the requested integration passed; completeness of unrelated Skill discovery was not assessed. A second host log entry said memories Phase 2 had no changes. Neither entry prevented task completion. No unrelated Skill or memory configuration was changed.

## Permission and support limits

Custom agent files cannot replace the parent's sandbox/approval settings in this Codex version. The balanced files now omit the ineffective `sandbox_mode` entries. Behavior instructions remain read-only where intended. An earlier actual worker record (`01a16e9b-464b-77d2-a10d-8936f121c076`) has `read-only` in its raw `turn_context` even though the then-installed worker file said `workspace-write`; its parent used read-only. This is direct host evidence of inheritance, consistent with the official contract.

Only this Mac and App runtime are accepted. Linux was not exercised. PowerShell project compatibility was retained, but PowerShell was not available for execution on this Mac. The new native stdio reader uses POSIX pipe polling, so Windows global installation is not supported by this round. A future Windows implementation needs a suitable pipe reader before claiming support.

Discovery is not an actual call to every role. Astra was intentionally not invoked; four-way concurrency and general task quality were not stress-tested. MiniCode remains unidentified, while ZCode and Claude Code remain documented future targets, as detailed in [harness boundaries](harness-boundaries.md). Existing active sessions were not restarted or interrupted.
