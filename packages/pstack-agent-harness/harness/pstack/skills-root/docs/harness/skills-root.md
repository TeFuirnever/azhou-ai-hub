# pstack in skills-root hosts

pstack skills use Cursor names. This tree installs into an explicit skills root that several hosts read as-is: Codex, zcode, MiMo Code, and DeepSeek Harness today, plus candidates under receipt. Read this file once per session, then map each Cursor name with the tables below. `<pstack>` means the folder that holds `skills/` and `docs/`. If a Cursor field has no row, drop it and say so. Never pass a field or value the tool schema rejects. No single host owns this contract, so each row names the capability and the session supplies the tool. For a host-specific tool-name mapping, read `codex.md` or `zcode.md` beside this file. A skills-only install adds no native agents, hooks, or tool mappings.

## Tools

| Cursor | skills-root host |
| --- | --- |
| `Task` | Dispatch a child through the session's own dispatch, when it has one. Codex calls it `spawn_agent`; zcode types the child `subagent_child`; DeepSeek Harness exposes `subagent`, `subagent_fork`, `spawn_teammate` and `workflow`. With no dispatch, run the step yourself and say so. |
| `AskQuestion` | Ask in plain text and let the user answer. No structured-choice tool is shared. |
| Open a todolist | Use the host's plan tool when it has one. Otherwise keep the list in your reply and update it at each phase. |
| Run another pstack skill (`/name` or "the **name** skill") | Invoke the project skill explicitly. Hosts discover skills at `.agents/skills/`, so read `<pstack>/skills/<name>/SKILL.md` and follow it. When you tell the user to type it, use the host's skill invocation. |
| `Grep`, `Glob` | The session's shell tool with `rg`, `find`, `ls`. |
| Read a file | The session's file-read tool. |
| Edit or delete a file | The session's file-edit tool. |
| Fetch a URL | The session's shell tool with `curl`, or its native fetch tool. |
| List the models this session can use | The host's model-list surface when it has one. |

## Subagent fields

| Cursor | skills-root host |
| --- | --- |
| `subagent_type: generalPurpose` | No shared named subagent types. Dispatch ad-hoc and put the role in the brief. |
| `poteto-agent`, `comment-sicko` | The same dispatch, with a brief that tells the worker to read `poteto-mode/SKILL.md`, or the plugin-root `agents/comment-sicko.md`, in full first. |
| `thermo-nuclear-review-subagent`, `thermo-nuclear-code-quality-review-subagent` | The same dispatch, one per worker, each brief naming the skill its worker reads in full first and the diff and file contents it reviews. |
| `readonly: true` | No shared sandbox field. The brief also says "do not edit files", and you check `git status` afterward. |
| `readonly: false` | Same dispatch. |
| `environment: "cloud"` | No cloud agents. Run on this machine, and give the worker its own worktree or branch when it writes. |
| `environment: "local"` | Omit. |
| `cloud_base_branch: <b>` | Tell the worker to check out `<b>` first. |
| `run_in_background: true` | Omit. A child runs beside your turn. |
| `resume` | Start a new child and paste the earlier result into its brief. |
| `file_attachments` | List the paths in the brief. |
| A named custom role | Never attach one to a pstack child. A selected custom-role file overrides the model and effort fields you set. |

## Models

| Cursor | skills-root host |
| --- | --- |
| `claude-<family>-<version>-<effort>[-fast]`, such as `claude-opus-5-5-xhigh` | No shared Claude slugs. Use the host's own model naming, and say so when you substitute. Drop `-fast`. |
| A `grok-*`, `gpt-*`, or other non-Claude slug | Use it when the session exposes it. Otherwise omit `model` so the agent runs on the session model, and say so. |
| `auto` or `inherit-parent` | Omit `model`. |
| The `pstack-models.mdc` rule, `~/.cursor/rules/pstack-models.mdc` | Each host's model sheet at the path its setup section names. No host loads `.mdc` here, so read the sheet when a skill needs a role. If the sheet or the role's line is missing, use the skill's default slug. |
| A role value `<model> <effort>`, such as `opus high` | The host sheet's model id and its reasoning level. A value of `session` passes no level. |

## setup-pstack

No host here loads a rules directory into every session, so `setup-pstack` writes its sheet per host, at the path that host's section names. Follow its steps with these changes.

- Detect. Ask the host's model-list surface for the models the current session can use, and write each as `<id> <effort>`. The effort is the last token, so the budget step works as written.
- Defaults. Map each default slug with the rows above. A default the host cannot name is `inherit-parent`.
- Write. Overwrite the whole sheet for that host. Never put the role lines in `AGENTS.md`. A `session hook: off` line stops routing on the hosts that register one.

## Paths

| Cursor | skills-root host |
| --- | --- |
| `.cursor/skills/`, `~/.cursor/skills/` | `.agents/skills/` in the project, `~/.agents/skills` for the shared user root. One install at either root serves every host that reads it. |
| `~/.cursor/plugins/`, `.cursor-plugin/plugin.json` | No shared plugin manifest. Codex installs through its own `.codex-plugin/` from the codex tree; other hosts take the Skill folders as-is. |
| `.cursor/rules/*.mdc`, always-applied rules | `AGENTS.md` at the project root, plus the host's global instructions path when it has one. No host here reads `.mdc`. The model rule is the exception. See Models. |
| Transcripts in `~/.cursor/projects/<slug>/agent-transcripts/` | Each host's own session store. Codex keeps `$CODEX_HOME/sessions/`, zcode keeps `~/.zcode/cli/db/db.sqlite`, DeepSeek Harness keeps `~/.dsh/sessions/` with no parser claimed. Read only this workspace's records. |
| `https://github.com/cursor/plugins/blob/main/pstack/<path>` | `<pstack>/<path>` when that file exists. The plugin ships the skills, `docs/guide/`, and `README.md`. Read the local copy and never fetch it. Give the user the URL when they need a link. |

## Cursor-only features

No skills-root host has Cursor Automations, Bugbot, Cursor cloud agents, or a built-in PR tool. When a step needs one, put one line in your reply, `Skipped on this host: <step>. <reason>.`, then go on to the next step. Do not stop, ask, or retry. When a later step needs what the skipped step made, such as a URL or a key, leave a placeholder and name it in the line.

| Cursor | skills-root host |
| --- | --- |
| Cursor Automations: routines, `update_state` routine calls, `api2.cursor.sh/automations` webhooks, routine wakes, and `SendToUser` secret requests | Skip with the line. |
| Bugbot | Bugbot comments on a GitHub PR are ordinary review threads, so triage them with the forge command that the step gives. Skip a step that starts, waits for, or configures Bugbot when the PR has no Bugbot check or comment. |
| Cursor cloud agents | No equivalent. Run on this machine and give the worker its own worktree when it writes. Skip a step that needs the cloud agent itself. |
| A built-in PR tool | Use the forge command that the step gives, such as `gh pr create`. That is not a skip, so write no line. |
| The `control-ui` and `control-cli` driver skills | No host here ships one. Run the app yourself through the session's shell and observe the real output, or hand the user a concrete manual check. Do not claim done without observing the artifact. |
