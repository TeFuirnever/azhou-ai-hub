# Research: Foundation Skill portability

Retrieved 2026-08-26 (Asia/Shanghai). This note records the design evidence for the Foundation Agent Skill layer.

## Direct answer

Agent Skills remove duplicated instructions and bundled workflow resources across compatible agents. They do not standardize discovery paths, explicit invocation syntax, plugin manifests, permissions, hooks, configuration ownership or tool availability. The correct architecture is therefore a neutral deterministic CLI plus standard `SKILL.md` UX packages and only thin, tested host installation surfaces.

## Local OMC evidence

Source lock: `/Users/guanxueliang/Desktop/Matrix/DynamicWorkflow/oh-my-claudecode` at commit `deee3a446dadc9bfea31cdc8b19b00b16718082e`, package version `4.14.6`.

| Capability | Agent Skill | Claude compatibility command | OMC CLI |
|---|---:|---:|---:|
| `info` | no matching package | no matching file | `omc info` |
| `version` | no matching package | no matching file | `omc version` and `--version` |
| `doctor` | `skills/omc-doctor/SKILL.md` | `commands/omc-doctor.md` | `omc doctor` |
| `setup` | `skills/setup/SKILL.md` and `skills/omc-setup/SKILL.md` | `commands/omc-setup.md` | `omc setup` |
| `verify` | `skills/verify/SKILL.md` | `commands/verify.md` | no matching subcommand in the bounded CLI entrypoint |

OMC's plugin manifest declares both Skills and commands, while `src/cli/index.ts` retains deterministic CLI operations. It is a hybrid reference, not evidence that Skill packaging erases host integration.

## Primary-source facts

- The [Agent Skills specification](https://agentskills.io/specification) defines `SKILL.md`, optional scripts/references/assets, compatibility metadata and progressive disclosure. It explicitly notes that tool-field support can vary by implementation.
- [OpenAI's Skill guidance](https://developers.openai.com/codex/skills/) documents Skills as reusable ChatGPT/Codex workflows, Codex repository discovery under `.agents/skills`, `$` invocation, and plugins for broader distribution.
- [Claude Code's Skill guidance](https://code.claude.com/docs/en/slash-commands) follows the open standard but uses `.claude/skills`, `/` invocation and Claude-specific extensions.
- [Claude Code's plugin guidance](https://code.claude.com/docs/en/plugins) treats Skills, agents, hooks and MCP servers as distinct plugin components rather than one portable runtime contract.

## Decision for Azhou AI Hub

1. `scripts/azhou_hub.py` remains the correctness and mutation authority.
2. Foundation Skills select a command, preserve approvals and interpret observed output; they never reimplement filesystem behavior.
3. The package is identical across harnesses. Only the configured discovery root and invocation syntax differ.
4. CLI tests prove the shared contract. Each claimed harness still needs discovery, invocation, permission and optional-integration smoke evidence.
5. Host-only hooks, MCP, configuration and identity metadata stay outside the canonical runtime package.

The Foundation Skills require a local checkout. This is intentional: the CLI manages checkout packages and repository verification, so a copied prompt must not pretend it contains that authority.
