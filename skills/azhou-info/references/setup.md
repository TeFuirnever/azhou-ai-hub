# Azhou Info setup and compatibility

## Requirements

- An Azhou AI Hub checkout containing `scripts/azhou_hub.py` and `docs/skill-standard.md`.
- Python 3.11 or newer.
- Git is optional; without it, revision fields may be unavailable and must remain unclaimed.

This Skill is harness-neutral and does not bundle or install the repository-level Foundation CLI. Install the same Skill directory into any Agent Skills-compatible root, then invoke it while working in the checkout or provide the checkout path explicitly. It does not require `agents/openai.yaml`, Claude commands, hooks, MCP, or harness configuration changes.

## Smoke check

~~~bash
python3 scripts/azhou_hub.py info --json
python3 scripts/azhou_hub.py version --json
~~~

Both commands are read-only. A non-zero exit is a failure to report, not permission to repair or update the checkout.
