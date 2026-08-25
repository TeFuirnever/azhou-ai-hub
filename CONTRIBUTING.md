# Contributing

Contributions start with a real task or observed failure and end with reproducible evidence. The [Azhou Skill Standard](docs/skill-standard.md) governs every skill package.

中文贡献者可以直接用中文提交 issue 和 PR；机器字段、canonical skill name 和 commit title 保持英文。

## Start

1. Search [issues](https://github.com/TeFuirnever/azhou-ai-hub/issues) and [discussions](https://github.com/TeFuirnever/azhou-ai-hub/discussions).
2. Fork the repository and branch from <code>main</code>.
3. Keep one pull request focused on one falsifiable behavior or repository outcome.
4. Run the full local gate before opening the PR:

~~~bash
python3 scripts/verify.py
~~~

The repository gate requires Python 3.11+. Excalidraw render/export work also follows its [locked dependency setup](skills/excalidraw-diagram/references/setup.md).

Maintainer and coding-agent workflows that need parallel local checkouts follow the [Treehouse worktree policy](docs/worktree-policy.md). Ordinary contributors can continue to use a normal fork and focused task branch.

## Choose the change type

### Add a skill

- Place one independently installable package at <code>skills/&lt;canonical-name&gt;/</code>.
- Include progressive references, reproducible setup for external dependencies and provenance for adapted/vendored material.
- Keep prompts, expected outputs, fixtures and judge records in <code>benchmarks/&lt;canonical-name&gt;/</code>.
- Add deterministic package tests plus at least one bounded real-task evaluation contract.
- Add the skill to both READMEs and the support matrix without claiming unverified harness parity.

### Fix a skill

- Point to a reproducible failure or safety risk.
- Add or identify a regression before changing the instruction or script.
- Change the smallest mechanism that explains the failure.
- Run the affected real-task comparison with frozen prompt, runtime tree, time limit and permissions.
- Never let history collectors, hooks or background judges modify the live package.

### Add benchmark evidence

- Use attempt 1 and an immutable case/runtime digest.
- Separate operational, semantic, deterministic and human/visual gates.
- Identify human reviewers; <code>skipped</code> is never <code>passed</code>.
- Commit only synthetic/redacted fixtures, aggregate receipts and mechanism-level conclusions.
- Keep raw conversations, private paths, identities, tokens and unpublished assets outside Git.

### Change the project standard

- Explain the cross-skill failure the rule prevents.
- Update [docs/skill-standard.md](docs/skill-standard.md) once; do not copy a competing authority into every skill.
- Update all materially conflicting packages, tests and docs in the same PR.
- Treat permission, deletion, privacy and publication boundaries as safety changes.

## Commit contract

Use Conventional Commit style:

~~~text
feat(repo-pedant): add memory inventory proof
fix(excalidraw): preserve editable arrow bindings
docs(readme): clarify one-path installation
test(repo-pedant): cover closeout trigger boundary
ci: pin actions and require benchmark gates
~~~

One commit answers one “why.” Implementation, its tests and necessary contract update may share a commit; unrelated skills may not. Commit bodies explain motivation, risk and evidence instead of repeating the diff.

Do not rewrite public default-branch history. Automation must not create high-frequency statistics commits.

## Pull request evidence

Complete the PR template:

- real task/failure and expected outcome;
- affected skill, schema or project contract;
- security/privacy/permission impact;
- commands and results;
- benchmark case and paired votes when behavior changed;
- documentation/provenance updates;
- limitations and rollback.

Three independent paired judges with reversed A/B order are required for skill promotion. Automated scores are triage, not promotion authority. The exact diff still needs human approval.

## License and sources

By contributing, you agree your contribution is available under the repository [MIT License](LICENSE) and that you have the right to submit it.

Adapted or vendored material must include:

- source URL;
- immutable version or commit;
- license identifier and retained notice;
- local files affected;
- reproducible update and verification path.

Publicly visible code with no license cannot be copied into this repository. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Review

Maintainers may close a proposal that cannot provide a bounded task, reproducible evidence, safe source rights or a maintainable runtime boundary. Disagreement is resolved using current code, tests, execution evidence and the project standard—not authority by assertion.
