# pstack upstream re-pin to 0.15.43 (2026-11-18)

**Scope:** authorized upstream-maintenance task under the
[pstack source and generation chain](../docs/integration-provenance.md#pstack-source-and-generation-chain)
contract. Treehouse worktree lease `a1aed31f0b5854ef260e11b61184964c`
(holder `pstack-upstream-01543-20261118`), branch
`codex/pstack-upstream-0.15.43` off `origin/main` at
`e6e745a6b5beeed0e8d4c153b44b486c022f9358`, the actual parent of the first
task commit (the opening narrative named
`8097fc7ac5c9d49ed4db435514e18126907c5f27`, never this branch's parent; base
corrected post-review on 2026-11-18). This is a **Hub source
candidate**, not a release: no host installation, reinstall, model dispatch,
hook trust or workflow run is claimed, and the four-host rolling upgrade is a
separate task.

## Upstream evidence (re-verified this date, not reused from 2026-11-17)

- `gh api repos/cursor/plugins/commits/main` → HEAD
  `93b916d4a1e806507e22f4716b352fa91f2b227e` ("Merge pull request #1230 from
  cursor/add-rillet-plugin", committer date 2026-11-17T22:49:29Z). Same HEAD
  as the 2026-11-17 read-only check: upstream had not moved again when this
  task ran.
- `gh api "repos/cursor/plugins/contents/pstack/plugin.json?ref=main"` →
  `"version": "0.15.43"` (name `pstack`, MIT, Lauren Tan).
- `gh api "repos/cursor/plugins/compare/c742dd61706fbacc1b95f1a20b7b988cf096ce6c...93b916d4a1e806507e22f4716b352fa91f2b227e"`
  → `ahead_by: 96`, `files: 300` (GitHub caps the compare file list at 300;
  the component subset it returned was 106, all under `pstack/`, with zero
  entries under `cursor-team-kit/` or `thermos/`).
- Ground truth for the refresh was the per-commit tarball
  (`repos/cursor/plugins/tarball/<sha>`, downloaded into fresh empty `/tmp`
  directories, artifacts not committed): a `diff -rq` comparison of the two
  pins' `pstack/` trees shows **80 modified, 24 deleted, 2 added = 106
  file-level changes**, all under `pstack/`, agreeing with the compare API's
  component subset. (An initial checksum-`rsync` tally of 111 overcounted: it
  booked 29 deletions where the authoritative diff shows 24 — the five extra
  were `references`/`sources` directory entries, not files — and this
  machine's openrsync `-c` comparison proved unreliable for this purpose, so
  the tarball `diff -rq` and `git diff --name-status` (2A/24D/80M) are the
  recorded authority; count corrected post-review on 2026-11-18.)
- Before refresh, `diff -rq` confirmed the package's `pstack/`,
  `components/cursor-team-kit/skills/`, `components/thermos/skills/` and
  `components/thermos/agents/` were byte-pristine mirrors of the old pin
  `c742dd61706fbacc1b95f1a20b7b988cf096ce6c` (team-kit carries only the six
  named skills by design). After the refresh, the independent review's
  tarball `diff -r` confirmed the refreshed `pstack/` tree byte-identical to
  the new pin (an interim checksum-rsync pass had also reported zero
  differences, but per the corrected count above the tarball diff is the
  recorded authority).

## Pin change

- `pstack/` re-imported at `93b916d4a1e806507e22f4716b352fa91f2b227e`.
  Notable upstream deltas: plugin version 0.15.36→0.15.43; #1236's new
  default models and Opus xhigh routing cap (new Claude adapter defaults
  `claude-opus-5-5-xhigh-fast`/`-high-fast`, `claude-fable-5-2-high`,
  `gemini-4-carbon-high` as `inherit-parent`; `grok-*`/`gpt-*` dropped from
  the adapter's non-Claude slug row in favor of `gemini-*`); the
  `orchestrate` playbook, `check-plan.mjs`, and the `why`/`how`/`architect`/
  `reflect` reference files removed upstream; `poteto-mode` playbooks 23→22
  with a new `worker.md`.
- `components/cursor-team-kit/` and `components/thermos/`: zero upstream
  commits between the pins; left untouched.
- `UPSTREAM.md` source table pin rows updated to the new commit;
  `hub-package.json` `version` → `0.15.43`, `commit` → new pin.

## Patch queue disposition (24 → 23 patches: 22 at re-pin plus the post-review 0024)

- `0001`–`0017`, `0019`, `0023`: applied unchanged; their declared files
  (watch-pr scripts, log.sh, generator, worktree-audit.sh) were untouched by
  upstream between the pins.
- `0018-rename-distribution-identity`: rebased — only its context line moved
  (`"version": "0.15.36"` → `"0.15.43"`); upstream still ships the name
  `pstack`, so the rename stays.
- `0020-hub-claude-namespace-guides`: rebased — upstream reworded the
  claude-code.md todolist row and inserted a `model:` subagent row; the Hub's
  identity replacements themselves were unchanged. Extended post-review on
  2026-11-18: the 01-setup.md write path now names the config-root sheet
  (`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/pstack-models.md`) the SessionStart
  hook reads, not the rules directory.
- `0022-hub-claude-sheet-hook-path`: rebased onto upstream's new Models table
  (the `grok-*`/`gpt-*` non-Claude row became `gemini-*`), and extended to
  restore `gpt-*` in that row. Reason: the Hub distribution still names
  `gpt-*` slugs (hub-skills `pi-tools.md`/copilot references), and upstream's
  unmodified generator requires the adapter to carry a row for every slug
  family the assembled skills mention — without it the build fails with
  `Claude Code adapter has no row for gpt-, used by poteto-mode, setup-pstack`.
- `0022-hub-claude-sheet-hook-path` (extended post-review on 2026-11-18):
  restores the `orchestrate` README table row and the twenty-three playbook
  counts in the README and `docs/guide/02-poteto-mode.md` that upstream's
  playbook deletion trimmed. The Hub `hub-skills` overlay keeps a
  portable-host `orchestrate` playbook, so the generated trees ship
  twenty-three playbooks and the generated docs must count them.
- `0024-hub-orchestrate-routing-restore` (added post-review on 2026-11-19,
  addressing the resolved codex P2 thread on this PR): upstream's condensed
  routing paragraph dropped `Orchestrate` together with the playbook and cut
  its title from the condensed playbook list, so the retained playbook had no
  normal entry route — project-scale requests all routed to `figure-it-out` —
  and the list counted twenty-two titles against the twenty-three shipped
  playbooks. The patch restores the standing project-scale-program routing
  sentence and the `Orchestrate` enumeration entry in the pristine poteto-mode
  `SKILL.md`, and the Orchestrate guide sentences the same deletion dropped in
  `docs/guide/07-overnight.md`, `docs/guide/02-poteto-mode.md` and
  `skills/poteto-help/SKILL.md`, before the generator mirrors them into all
  five trees.
- `0021-hub-distribution-version-0.15.37` and
  `0024-hub-distribution-version-0.15.38`: **removed from the queue** (patch
  files deleted, `series` lines dropped). A patch is a loan; these stamped
  Hub-only payload releases past the pinned upstream `0.15.36` so the plugin
  would not reuse an installed cache key. The new pristine tree itself
  carries `0.15.43`, which already differs from every installed Hub cache key
  (`0.15.36`/`0.15.37`/`0.15.38`), so re-stamping would only push the version
  backwards. They cannot rebase non-vacuously and are recorded here.
- Version convention: the Hub line follows upstream (the fork-era
  distribution shipped upstream's `0.15.36` verbatim; Hub stamps only ever
  bumped past the pin for Hub-only payload changes). With the pin at
  `0.15.43` ≥ the last Hub stamp, the Hub distribution takes `0.15.43`
  directly — same convention as `fcf2606b` keeping `commit` at the pin while
  `version` tracks the distribution line.

## #1236 model-routing adaptation (hub-adapters / hub-runtime)

- `hub-runtime/` hooks carry no model slugs (grep over all hook files:
  zero hits); no change needed.
- `hub-adapters/codex.md` `Defaults.` line enumerated the retired upstream
  default pair (`claude-opus-5-5-xhigh`, `grok-4.7-xhigh-fast`); realigned to
  upstream's new four-slug default set. The `claude-fable-5-2-high` →
  `gpt-6-astra high` Codex example follows the Hub's own cross-host table
  (`hub-skills/poteto-mode/references/pi-tools.md`: fable →
  `openai-codex/gpt-6-astra`); flagged for review confirmation in the task
  result since that mapping is Hub-chosen, not upstream-decreed.
- `hub-adapters/zcode.md` and `skills-root.md` Defaults lines are generic
  ("a default with no host model is `inherit-parent`") and needed no change.
  Their `grok-*, gpt-*` example prefix rows stay: upstream's own new
  `setup-pstack/SKILL.md` still routes legacy `grok-*` slugs, and the
  copilot overlay still names the grok vendor, so the prefix remains a live
  example of "other non-Claude slug", not a stale default.

## Known divergence and follow-up (adapted material)

- The Hub portable-host rewrite `hub-skills/poteto-mode/playbooks/autopilot-full.md`
  (#372) shadows the pristine playbook at assembly, so upstream 0.15.43's
  step-2 behavior fix — "Where that playbook says to report a rebase, the
  owner rebases its own branch and publishes it with
  `git push --force-with-lease`." — reaches no generated tree. Absorbing
  upstream text into the Hub rewrite is out of scope for this re-pin, so
  the divergence is deliberate and recorded here as the adapted material's
  reproducible update path. Follow-up (separate maintenance task):
  reconcile the Hub rewrite with the upstream delta — adopt the
  `force-with-lease` republish step or record its explicit rejection —
  then regenerate the mirrors from that decision.

## Build summary

`node tools/build-harness.mjs` (run in the package directory): all 23 series
patches applied; upstream's unmodified `generate-pstack-harness-trees.mjs`
ran clean and emitted the four committed trees (`claude-code/`, `codex/`,
`zcode/`, `skills-root/`, each 68 skills), plus the ZCode plugin surface
(41 commands, 68 bundled skills) and 41 Codex prompts. All generated
`plugin.json` manifests carry `0.15.43` with name `pstack-azhouzhou`.
`scripts/verify.py` was **not** run (unified gate, out of this task's red
line); the repository gate runs in the pipeline on the pushed branch.

## Docs aligned

- `docs/integration-provenance.md`: Current package inputs row, pstack
  chain paragraph pin, and "The Hub candidate is now `0.15.43`".
- `docs/support-matrix.md`: candidate line re-pinned to `0.15.43` with the
  previous candidate recorded; install-state paragraph now states no
  `0.15.43` host installation is claimed (ZCode at `0.15.38` per the
  bundled-skills receipt; Claude Code at `0.15.38` per the 2026-11-18
  update receipt; `0.15.37` kept only as Codex's 2026-11-11 inventory
  observation; parenthetical corrected post-review on 2026-11-18).
- `packages/pstack-agent-harness/UPSTREAM.md`: pin rows and quilt-count
  paragraph (23 patches; stamp patches' exit recorded).
- `CHANGELOG.md`: Unreleased entry added.
