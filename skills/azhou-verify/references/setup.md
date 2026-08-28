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

The default command needs no private inputs, but its Super Caveman integrity check still recomputes the approved exact diff against the current staged or committed tree. A changed approved path therefore blocks the public gate until a fresh checked-in promotion receipt matches it. Maintainers may explicitly run `python3 scripts/azhou_hub.py verify --promotion-evidence` only after setting `SUPER_CAVEMAN_APPROVAL_RECORD` and `SUPER_CAVEMAN_REVIEW_RECORD` to absolute Git-external files. That additional mode authenticates the paired raw evidence against the same diff and fails closed when either record is unavailable, stale, inside the repository, or malformed.
