# Azhou AI Hub agent rules

## Repository shape

- Follow [product principles](docs/principles.md) and the [roadmap](docs/roadmap.md) for direction; they do not override current runtime contracts, support evidence or legal grants.
- Avoid unnecessary secondary labels and descriptions. Let the layout do the explaining.

- [`docs/skill-standard.md`](docs/skill-standard.md) is the project authority for every skill's package, setup, brand lifecycle, evidence, evaluation, evolution, and closeout.
- [`docs/integrations.md`](docs/integrations.md) governs the two optional projects under `packages/` (pstack-agent-harness and agent-skin). Maintain their canonical package sources, preserve original-import provenance, and fingerprint current `runtime_paths` inputs for each plan. Keep native installation ownership and installation/discovery/invocation evidence distinct. They do not become canonical Skills or bypass the orchestrator composition rule.
- For Agent Skin local installation, source recovery, or installed-version checks, read [the three-host local install SOP](packages/agent-skin/docs/local-install-sop.md) first.
- Keep every canonical skill independently installable under `skills/<canonical-name>/`; project-local engineering workflows remain in `.agents/skills/`. Keep development-only evaluation material under repository-level `benchmarks/`.
- `README.md` is the English public entry and `README.zh-CN.md` its Chinese reader mirror. Material product, install, evidence, compatibility, security, or license changes update both in one commit.
- Public support claims must match `docs/support-matrix.md`. Portable runtime does not imply identical hooks, memory APIs, or tool access across harnesses.
- Do not add `agents/openai.yaml` or other model-specific package identity. Harness adapters must call a neutral core or stay in documented examples. This restriction applies to public repository files; untracked, Git-ignored local tool installations under `.agents/skills/` may retain their upstream metadata.
- Interactive skills use one restrained Azhou anchor per material stage and a stable receipt. Emoji stays out of schema keys, enums, digests, paths, commands, tests, and raw evidence.
- Adapted or vendored material requires an immutable source, license, retained notice, local boundary and reproducible update path. Public code without a license is not reusable source.
- Long-range plans and ticket drafts live under `.planning/`, which is git-ignored and therefore absent from Treehouse worktrees; read them from the maintainer checkout by absolute path whenever a task references them.

## Change scope

- Separate authorized change targets, mechanism references, protected objects and evaluation subjects before work; none grants authority over another. Follow [scope and attribution](docs/skill-standard.md#11-scope-and-attribution) and the [stable-source update rules](docs/skill-standard.md#12-stable-source-updates).
- **pstack is excluded from Hub Skill upgrades and autonomous evolution**, including its bundled skills. Do not enhance, upgrade, regenerate, install or reconfigure it in a Skill task, or use pstack maintenance tasks as in-scope benefit evidence. Upstream maintenance requires a separate explicit task under the existing [source and generation contract](docs/integration-provenance.md#pstack-source-and-generation-chain); preserve its pristine sources, recorded patch queue and adapters rather than asserting assembled byte parity or deleting them.
- Protect actual shared-dependency effects without expanding scope. Unattributed host/configuration drift is an observation, not automatically a task-caused defect or a global blocker. A hold must name the affected action, dependency/evidence, owner and release condition; pause the affected action when safety cannot be established and continue independent work. Never repair excluded objects or write back shared host configuration without authorization.

For change planning or review with an explicit base and head, use the experimental [Foundation scope command](docs/foundations.md#experimental-change-scope) to separate committed, staged, unstaged and non-ignored untracked paths. Recheck the complete result before relying on it and stop if concurrent changes cannot be excluded. Trace owners and consumers in the [semantic impact record](docs/foundations.md#record-semantic-impact); path lists are not semantic closure or proof of an atomic snapshot.

## Git and GitHub

- Use `type(scope): imperative summary`. One commit answers one reason; code, its test and necessary contract update may stay together. Preserve frozen/reviewed candidates; governance or report corrections use a new commit. Changed content requires a fresh exact-diff binding, not reuse of an earlier approval.
- Merging to `main` is squash-only and stays blocked until the ruleset's required checks pass and every review thread (including CodeQL and bot comments) is resolved.
- Do not rewrite public default-branch history or let bots create statistics-only commits.
- GitHub Actions use least privilege, full commit-SHA action pins, bounded timeouts and no untrusted `pull_request_target` checkout.
- Keep versioned docs in the repository rather than a competing Wiki. Security reports use private advisories, never public issues.

## Treehouse worktrees

- Treehouse `v2.3.0` or newer is the default for temporary, concurrent, experimental and coding-agent implementation work in maintainer checkouts. Acquire a durable lease with `treehouse get --lease --json --lease-holder <task-id>`.
- Record the returned path, lease ID and holder in task evidence. Use one task, one lease and one `codex/<task>` branch; verify the leased path belongs to this repository before writing. One active writer owns a worktree; a lease is not a writer lock. Resume only after identifying or handing off that owner; reviewers use read-only snapshots.
- Direct `git worktree add` is reserved for an explicitly approved, long-lived manual worktree. If Treehouse is unavailable, do not install or upgrade it implicitly; report the blocker or obtain approval for the fallback.
- Never return a dirty, unmerged, unverified or in-use worktree. Never prune or destroy dirty, unlanded, in-use or leased work. Keep the lease until work is landed or preserved by a separately verified recovery point.
- Before returning a lease, `cd` the host shell out of the worktree and have persistent agent shells do the same; a shell left inside the deleted directory fails `getcwd` afterward.
- Automated return requires both `--if-lease-id` and `--if-lease-holder`. Do not use path-only automation or `treehouse return --force`.
- Destructive Treehouse operations stay dry-run-first. `--include-unlanded`, `--include-in-use` and `--include-leased` require explicit user authorization for the exact path.
- Treehouse provides workspace and lifecycle isolation, not a security sandbox, identity proof or approval boundary. Follow [`docs/worktree-policy.md`](docs/worktree-policy.md) for acquisition, migration, recovery and closeout.

## Super Repo Pedant invariants

- Treat code and machine-readable configuration as current behavior. Keep unimplemented spec intent in reminders.
- Preserve every `neat-freak` capability unless `skills/super-repo-pedant/references/neat-freak-compatibility.md` records a tested safety conflict or implementation disadvantage.
- Never let lifecycle hooks or history observers mutate the live skill. Evolution candidates require deterministic checks, paired majority, no safety regression, and exact-diff human approval bound to actual patch/source/result bytes; see [the evolution contract](skills/super-repo-pedant/references/evolution-contract.md). Declare integrity repair, task-quality gain and recursive improvement separately; a receipt or vote alone is not effect evidence.
- Keep raw agent history, excerpts, local inventory, hook state, and evolution candidates out of Git.

## Verification

Freeze writes during version-bound verification: capture HEAD, index, complete changed-file bytes, runtime and evaluator/input identities before and after. A concurrent edit, commit or rebase invalidates that version-bound verdict even if the command exits zero; preserve it and rerun on a stable isolated revision. Do not rerun an evaluator in its frozen evidence directory. See [worktree verification](docs/worktree-policy.md#single-writer-and-verification-freeze) and [evaluation rules](docs/skill-standard.md#41-evaluation-integrity).

Run before handoff:

```bash
python3 scripts/verify.py
```

This runs repository policy, the retired-surface reverse scan, Hub unit tests, package manifest/lifecycle suites, every registered benchmark-integrity suite, and working/staged Git whitespace checks. For Excalidraw runtime changes, also execute the render/export/visual gates in `skills/super-excalidraw-diagram/references/setup.md`. For Codex Pet runtime changes, also run `python3 -B packages/agent-skin/tools/test-codex-pet.py` and `python3 -B packages/agent-skin/tools/test-import-codex-pet.py`; these Pillow-dependent suites run in the macOS CI leg, separately from the standard-library repository gate.

Use `uv run --with pyyaml python <skill-creator>/scripts/quick_validate.py skills/<skill>` only for development validation; PyYAML is not a runtime dependency of these skills.
