# Commit and review formats

## Commit message

Return a paste-ready message. Do not stage, commit, or amend.

Subject:

```text
<type>(<scope>): <imperative summary>
```

- Use `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`, `style`, or `revert`.
- Keep the subject at 50 characters when practical and never above 72.
- Use imperative mood and no trailing period.
- Match repository capitalization conventions.
- Add a body only for non-obvious rationale, migration notes, breaking changes, security fixes, or reverts.
- Wrap body lines at 72 characters. Put issue references last.
- Include `BREAKING CHANGE:` when required.
- Do not add AI attribution unless repository rules require a trailer.

Always include explanatory body text for security fixes, data migrations, breaking changes, and reverts.

## Review finding

Use one actionable line per finding:

```text
<file>:L<line>: <severity>: <problem>. <fix>.
```

Severity:

- `bug`: broken behavior or likely incident;
- `risk`: fragile behavior, race, missing guard, or swallowed failure;
- `nit`: optional style, naming, or micro-optimization;
- `question`: genuine uncertainty, not disguised advice.

Sort findings by file and line. Keep exact line numbers and symbols. Explain why when the fix is not obvious. If no actionable finding exists, return `No issues.`

Use a normal paragraph for security findings, architectural disagreements, and onboarding explanations. A review does not edit code, approve, or request changes.
