# pstack in ZCode

pstack skills use Cursor names. In ZCode, read this file once per session, then map each Cursor name in a skill with the tables below. `<pstack>` means the folder that holds `skills/` and `docs/`. If a Cursor field has no row, drop it and say so. Never pass a field or value the tool schema rejects. This project records no ZCode tool-name contract, so these rows name the capability and the session supplies the tool. Use only the tools and model choices the current session exposes; a skills-only install adds no native agents, hooks, or tool mappings.

## Tools

| Cursor | ZCode |
| --- | --- |
| `Task` | Dispatch a child through the session's own dispatch, when it has one. ZCode types those children `subagent_child`. With no dispatch, run the step yourself and say so. |
| `AskQuestion` | Ask in plain text and let the user answer. No structured-choice tool is recorded. |
| Open a todolist | No todolist tool is recorded. Keep the list in your reply and update it at each phase. |
| Run another pstack skill (`/name` or "the **name** skill") | Invoke the project skill explicitly. ZCode discovers skills at `.agents/skills/`, so read `<pstack>/skills/<name>/SKILL.md` and follow it. Tell the user to invoke the Skill by its discovered ZCode name; use `zcode skills list` to verify it, rather than assuming a Claude Code namespaced slash command. The separate commands-only plugin exposes commands such as `/architect`. |
| `Grep`, `Glob` | The session's shell tool with `rg`, `find`, `ls`. |
| Read a file | The session's file-read tool. |
| Edit or delete a file | The session's file-edit tool. |
| List the models this session can use | `ListModels`. A full id reads `account:<plan>/<model>`. |
| Run the CLI headless | `zcode --cwd <dir> --prompt …`. `zcode skills list --cwd <dir>` lists what ZCode discovered. |

## Subagent fields

| Cursor | ZCode |
| --- | --- |
| `subagent_type: generalPurpose` | No named subagent types are recorded. Dispatch ad-hoc and put the role in the brief. |
| `poteto-agent`, `comment-sicko` | The same dispatch, with a brief that tells the worker to read `poteto-mode/SKILL.md`, or `poteto-mode/references/agents/comment-sicko.md`, in full first. |
| `thermo-nuclear-review-subagent`, `thermo-nuclear-code-quality-review-subagent` | The same dispatch, one per worker, each brief naming the skill its worker reads in full first and the diff and file contents it reviews. |
| `readonly: true` | No sandbox field is recorded. The brief also says "do not edit files", and you check `git status` afterward. |
| `readonly: false` | Same dispatch. |
| `environment: "cloud"` | No cloud agents. Run on this machine, and give the worker its own worktree or branch when it writes. |
| `environment: "local"` | Omit. |
| `cloud_base_branch: <b>` | Tell the worker to check out `<b>` first. |
| `run_in_background: true` | Omit. A child runs beside your turn, and ZCode types it `subagent_child`. |
| `resume` | Start a new child and paste the earlier result into its brief. |
| `file_attachments` | List the paths in the brief. |
| A named custom role | Never attach one to a pstack child. |

## Models

| Cursor | ZCode |
| --- | --- |
| `claude-<family>-<version>-<effort>[-fast]`, such as `claude-opus-5-5-xhigh` | No Claude slugs. Take the model from `ListModels` and pass its full id, such as `account:<plan>/<model>`. Pass a reasoning level only when the session's model field accepts one. Drop `-fast`. |
| A `grok-*`, `gpt-*`, or other non-ZCode slug | Omit `model` so the run uses the session model, and say so. |
| `auto` or `inherit-parent` | Omit `model`. |
| The `pstack-models.mdc` rule, `~/.cursor/rules/pstack-models.mdc` | The sheet under `~/.zcode/` at the path setup-pstack names below. ZCode never reads `.mdc`, and its role lines are not loaded into every session, so read the sheet when a skill needs a role. If the sheet or the role's line is missing, use the skill's default slug mapped through the rows above. |
| A role value `<model> <effort>`, such as `opus high` | The sheet's full model id and its reasoning level. A value of `session` passes no level. |

## setup-pstack

ZCode loads no rules directory into every session, so `setup-pstack` writes its sheet under `~/.zcode/`, at the path its Other runtimes table names. Follow its steps with these changes.

- Detect. Ask `ListModels` for the models the current session can use and write each full id, such as `account:<plan>/<model>`, as `<id> <effort>`. The effort is the last token, so the budget step works as written.
- Defaults. Map each default slug with the rows above. A default with no ZCode model is `inherit-parent`.
- Write. Overwrite the whole sheet. Never put the role lines in `AGENTS.md`. A `session hook: off` line stops routing. ZCode registers hooks in `<scope-root>/.zcode/cli/config.json`. A probe at zcode 0.16.5 on macOS saw `SessionStart` fire in the GUI host and fire zero markers across a completed headless `--prompt` run, so do not rely on it outside the GUI host.

## Paths

| Cursor | ZCode |
| --- | --- |
| `.cursor/skills/`, `~/.cursor/skills/` | `.agents/skills/` in the project, `~/.agents/skills` for the shared root. |
| `~/.cursor/plugins/`, `.cursor-plugin/plugin.json` | `~/.zcode/`. There is no plugin manifest, and hooks register in `~/.zcode/cli/config.json`. |
| `.cursor/rules/*.mdc`, always-applied rules | `AGENTS.md` at the project root. ZCode never reads `.mdc`, and this project records no global instructions path for it. The model rule is the exception. See Models. |
| `https://github.com/cursor/plugins/blob/main/pstack/<path>` | `<pstack>/<path>` when that file exists. The plugin ships the skills, `docs/guide/`, and `README.md`. Read the local copy and never fetch it. Give the user the URL when they need a link. |
| Transcripts in `~/.cursor/projects/<slug>/agent-transcripts/` | `~/.zcode/cli/db/db.sqlite`, as `session`, `message`, and `part` rows. Drop the bare-uuid `session.id` rows, which are Claude Code imports, and filter `task_type` before you count. `~/.zcode/cli/rollout/` and `~/.zcode/v2/sessions/` are not sources. Read only this workspace's rows. |

## Cursor-only features

ZCode has no Cursor Automations, Bugbot, Cursor cloud agents, or built-in PR tool. When a step needs one, put one line in your reply, `Skipped in ZCode: <step>. <reason>.`, then go on to the next step. Do not stop, ask, or retry. When a later step needs what the skipped step made, such as a URL or a key, leave a placeholder and name it in the line.

| Cursor | ZCode |
| --- | --- |
| Cursor Automations: routines, `update_state` routine calls, `api2.cursor.sh/automations` webhooks, routine wakes, and `SendToUser` secret requests | Skip with the line. |
| Bugbot | Bugbot comments on a GitHub PR are ordinary review threads, so triage them with the forge command that the step gives. Skip a step that starts, waits for, or configures Bugbot when the PR has no Bugbot check or comment. |
| Cursor cloud agents | No equivalent. Run on this machine. Skip a step that needs the cloud agent itself, such as its dashboard status or its own machine. |
| A built-in PR tool | Use the forge command that the step gives, such as `gh pr create`. That is not a skip, so write no line. |
| The `control-ui` and `control-cli` driver skills | ZCode ships neither. Run the app yourself through the session's shell and observe the real output, or hand the user a concrete manual check. Do not claim done without observing the artifact. |
