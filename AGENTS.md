# Azhou AI Hub agent rules

## Codebase discovery

This project uses `codebase-memory-mcp`. Prefer graph evidence over grep/glob for structural code discovery:

1. `search_graph` for symbols;
2. `trace_path` for callers/callees;
3. `get_code_snippet` for exact implementations;
4. `check_index_coverage` for every relied-on path;
5. `query_graph` for complex relationships;
6. `get_architecture` for high-level structure.

Use source search/read for literals, configs, non-code files, graph gaps, and every missed coverage range. At session start or after compaction, confirm project/generation and choose Scout, Verify, or Auditor evidence depth. A clean coverage result means no recorded gap, not proof of completeness.

## Repository shape

- [`docs/skill-standard.md`](docs/skill-standard.md) is the project authority for every skill's package, setup, brand lifecycle, evidence, evaluation, evolution, and closeout.
- Keep every skill independently installable under `skills/<canonical-name>/`; keep development-only evaluation material under repository-level `benchmarks/`.
- `README.md` is the English public entry and `README.zh-CN.md` its Chinese reader mirror. Material product, install, evidence, compatibility, security, or license changes update both in one commit.
- Public support claims must match `docs/support-matrix.md`. Portable runtime does not imply identical hooks, memory APIs, or tool access across harnesses.
- Do not add `agents/openai.yaml` or other model-specific package identity. Harness adapters must call a neutral core or stay in documented examples.
- Interactive skills use one restrained Azhou anchor per material stage and a stable receipt. Emoji stays out of schema keys, enums, digests, paths, commands, tests, and raw evidence.
- Historical runs may create isolated regression candidates. Observers and hooks never mutate live skills; promotion requires deterministic gates, paired majority, no safety regression, and exact-diff human approval.
- Adapted or vendored material requires an immutable source, license, retained notice, local boundary and reproducible update path. Public code without a license is not reusable source.

## Git and GitHub

- Use `type(scope): imperative summary`. One commit answers one reason; code, its test and necessary contract update may stay together.
- Do not rewrite public default-branch history or let bots create statistics-only commits.
- GitHub Actions use least privilege, full commit-SHA action pins, bounded timeouts and no untrusted `pull_request_target` checkout.
- Keep versioned docs in the repository rather than a competing Wiki. Security reports use private advisories, never public issues.

## Treehouse worktrees

- Treehouse `v2.3.0` or newer is the default for temporary, concurrent, experimental and coding-agent implementation work in maintainer checkouts. Acquire a durable lease with `treehouse get --lease --json --lease-holder <task-id>`.
- Record the returned path, lease ID and holder in task evidence. Use one task, one lease and one `codex/<task>` branch; verify the leased path belongs to this repository before writing.
- Direct `git worktree add` is reserved for an explicitly approved, long-lived manual worktree. If Treehouse is unavailable, do not install or upgrade it implicitly; report the blocker or obtain approval for the fallback.
- Never return a dirty, unmerged, unverified or in-use worktree. Never prune or destroy dirty, unlanded, in-use or leased work. Keep the lease until work is landed or preserved by a separately verified recovery point.
- Automated return requires both `--if-lease-id` and `--if-lease-holder`. Do not use path-only automation or `treehouse return --force`.
- Destructive Treehouse operations stay dry-run-first. `--include-unlanded`, `--include-in-use` and `--include-leased` require explicit user authorization for the exact path.
- Treehouse provides workspace and lifecycle isolation, not a security sandbox, identity proof or approval boundary. Follow [`docs/worktree-policy.md`](docs/worktree-policy.md) for acquisition, migration, recovery and closeout.

## Repo-pedant invariants

- Treat code and machine-readable configuration as current behavior. Keep unimplemented spec intent in reminders.
- Preserve every `neat-freak` capability unless `skills/repo-pedant/references/neat-freak-compatibility.md` records a tested safety conflict or implementation disadvantage.
- Never let lifecycle hooks or history observers mutate the live skill. Evolution candidates require deterministic checks, paired majority, no safety regression, and exact-diff human approval.
- Keep raw agent history, excerpts, local inventory, hook state, and evolution candidates out of Git.

## Verification

Run before handoff:

```bash
python3 scripts/verify.py
```

This runs repository policy, all unit tests, both benchmark-integrity suites, and working/staged Git whitespace checks. For Excalidraw runtime changes, also execute the render/export/visual gates in `skills/excalidraw-diagram/references/setup.md`.

Use `uv run --with pyyaml python <skill-creator>/scripts/quick_validate.py skills/<skill>` only for development validation; PyYAML is not a runtime dependency of these skills.
