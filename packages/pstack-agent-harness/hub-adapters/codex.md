# pstack in Codex

pstack skills use Cursor names. In Codex, read this file once per session, then map each Cursor name in a skill with the tables below. `<pstack>` means the folder that holds `skills/` and `docs/`. If a Cursor field has no row, drop it and say so. Never pass a field or value the tool schema rejects.

## Tools

| Cursor | Codex |
| --- | --- |
| `Task` | `spawn_agent`. It needs `multi_agent` in `~/.codex/config.toml`. Without it the fan-out skills run one sequential pass, and a required independent review stays blocked. |
| `AskQuestion` | Ask in plain text and let the user answer. Codex has no structured-choice tool. |
| Open a todolist | `update_plan`. |
| Run another pstack skill (`/name` or "the **name** skill") | Skills load natively. Read `<pstack>/skills/<name>/SKILL.md` and follow it. Tell the user to invoke the native Codex Skill by its available name (for example `$poteto-mode`), not by a Claude Code-specific namespaced slash command. |
| `Grep`, `Glob` | `shell` with `rg`, `find`, `ls`. |
| Read a file | `shell` (`cat`, `head`, `tail`). |
| Edit or delete a file | `apply_patch`. |
| Fetch a URL | `shell` with `curl`. |
| Search the web | `web_search`. |
| Wait for a subagent | `wait_agent`. Free a finished slot with `close_agent` when the session exposes it. A thread-limit error is capacity, not a bad model slug, so do not fall back to another model. |

## Subagent fields

| Cursor | Codex |
| --- | --- |
| `subagent_type: generalPurpose` | Ad-hoc `spawn_agent`. Codex has no subagent types. |
| `poteto-agent`, `comment-sicko` | Ad-hoc `spawn_agent` whose brief tells the worker to read `poteto-mode/SKILL.md`, or `poteto-mode/references/agents/comment-sicko.md`, in full first. |
| `thermo-nuclear-review-subagent`, `thermo-nuclear-code-quality-review-subagent` | Two `spawn_agent` calls, each brief naming the skill its worker reads in full first and the diff and file contents it reviews. |
| `readonly: true` | No sandbox field. The brief also says "do not edit files", and you check `git status` afterward. |
| `readonly: false` | Same dispatch. It keeps the session's MCP servers. |
| `environment: "cloud"` | No cloud agents. Run on this machine, and give the worker its own worktree or branch when it writes. |
| `environment: "local"` | Omit. |
| `cloud_base_branch: <b>` | Tell the worker to check out `<b>` first. |
| `run_in_background: true` | Omit. `spawn_agent` already runs beside your turn. |
| `resume` | Spawn a new agent and paste the earlier result into its brief. |
| `file_attachments` | List the paths in the brief. |
| A named custom role, such as `explorer`, `worker`, `reviewer` | Never attach one to a pstack child. A selected custom-role file overrides the model and effort fields you set. |

## Models

| Cursor | Codex |
| --- | --- |
| `claude-<family>-<version>-<effort>[-fast]`, such as `claude-opus-5-5-xhigh` | Your configured Codex slug, such as `gpt-6-sol`, and `reasoning_effort: "xhigh"`. Codex has no Claude slugs. Drop `-fast`. |
| A `grok-*`, `gpt-*`, or other non-Claude slug | Use it when the session exposes it. Otherwise omit `model` so the agent runs on the session model, and say so. |
| `auto` or `inherit-parent` | Omit `model`. |
| The `pstack-models.mdc` rule, `~/.cursor/rules/pstack-models.mdc` | The sheet at the path setup-pstack names below. Codex never reads `.mdc`, and its role lines are not loaded into every session, so read the sheet when a skill needs a role. If the sheet or the role's line is missing, use the skill's default slug. |
| A role value `<model> <effort>`, such as `opus high` | `model: "<slug>"` and `reasoning_effort: "high"`. A value of `session` passes no `reasoning_effort`. |

## setup-pstack

Codex loads no rules directory into every session, so `setup-pstack` writes its sheet at the path its Other runtimes table names. Follow its steps with these changes.

- Detect. The detected models are the slugs the session exposes, not `Agent` tool schema values. Write each as `<slug> <effort>`, such as `gpt-6-sol xhigh`. The effort is the last token, so the budget step works as written.
- Defaults. Map each default slug with the rows above: `claude-opus-5-5-xhigh` is `gpt-6-sol xhigh`, and `grok-4.7-xhigh-fast` is `inherit-parent`.
- Write. Overwrite the whole sheet. Never put the role lines in `AGENTS.md` or `CLAUDE.md`. A `session hook: off` line stops the `SessionStart` routing hook.

## Paths

| Cursor | Codex |
| --- | --- |
| `.cursor/skills/`, `~/.cursor/skills/` | `.agents/skills/` in the project, `~/.agents/skills` for the shared root. |
| `~/.cursor/plugins/`, `.cursor-plugin/plugin.json` | `~/.codex/`. There is no plugin manifest, so the skills install as plain Skill folders. |
| `.cursor/rules/*.mdc`, always-applied rules | `AGENTS.md` at the project root, plus `~/.codex/AGENTS.md` for global rules. Codex never reads `.mdc`. The model rule is the exception. See Models. |
| `https://github.com/cursor/plugins/blob/main/pstack/<path>` | `<pstack>/<path>` when that file exists. The plugin ships the skills, `docs/guide/`, and `README.md`. Read the local copy and never fetch it. Give the user the URL when they need a link. |
| Transcripts in `~/.cursor/projects/<slug>/agent-transcripts/` | `$CODEX_HOME/sessions/` and `$CODEX_HOME/archived_sessions/`, default `~/.codex`. Read only this workspace's folders. |

## Cursor-only features

Codex has no Cursor Automations, Bugbot, Cursor cloud agents, or built-in PR tool. When a step needs one, put one line in your reply, `Skipped in Codex: <step>. <reason>.`, then go on to the next step. Do not stop, ask, or retry. When a later step needs what the skipped step made, such as a URL or a key, leave a placeholder and name it in the line.

| Cursor | Codex |
| --- | --- |
| Cursor Automations: routines, `update_state` routine calls, `api2.cursor.sh/automations` webhooks, routine wakes, and `SendToUser` secret requests | Skip with the line. |
| Bugbot | Bugbot comments on a GitHub PR are ordinary review threads, so triage them with the forge command that the step gives. Skip a step that starts, waits for, or configures Bugbot when the PR has no Bugbot check or comment. |
| Cursor cloud agents | No equivalent. Run on this machine and give the worker its own worktree when it writes. Skip a step that needs the cloud agent itself, such as its dashboard status or its own machine. |
| A built-in PR tool | Use the forge command that the step gives, such as `gh pr create`. That is not a skip, so write no line. |
| The `control-ui` and `control-cli` driver skills | Codex ships neither. Run the app yourself through `shell` and observe the real output, or hand the user a concrete manual check. Do not claim done without observing the artifact. |
