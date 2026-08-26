# Azhou Verify setup and compatibility

## Requirements

- An Azhou AI Hub checkout containing `scripts/azhou_hub.py`, `scripts/verify.py`, and `docs/skill-standard.md`.
- Python 3.11 or newer.
- Git for working/staged whitespace gates.
- Skill-specific benchmark dependencies only when the registered benchmark requires them.

This Skill is harness-neutral and does not bundle or replace the repository verifier. Install the same Skill directory into any Agent Skills-compatible root, then invoke it while working in the checkout or provide the checkout path explicitly.

## Full gate

~~~bash
python3 scripts/azhou_hub.py verify
~~~

The command delegates to `python3 scripts/verify.py` and preserves its exit code. Passing this gate proves the repository's registered deterministic checks at that revision; it does not prove every external harness, platform, or human-review condition.
