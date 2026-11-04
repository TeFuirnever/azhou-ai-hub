# pstack-azhouzhou plugin-fabric plan

Four harnesses get a native plugin distribution named `pstack-azhouzhou`, across Claude Code, the ChatGPT desktop Codex engine, ZCode desktop, and DeepSeek Harness. The Hub repository stays the single source and the skills-root tree stays the payload base. Every install still named `pstack` retires. The PRs run AZ1 through AZ5 in that order.

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs `pstack/skills/poteto-mode/playbooks/autopilot-stack.md`. The operator lands every PR. Items AZ1 through AZ5 stop at merge-ready.

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

Environment deviations, named once. Claude Code ships no `control-ui` or `control-cli`, so every live lane drives its real surface through the session's own shell and saves a receipt under `evidence/`, the convention this repository already enforces. The unit check is the repository gate `python scripts/verify.py`. The program rides the local branch `pstack-upstream-rebase`; no PR targets `main` until the operator pushes, so every merge box below means a commit on that branch with the gate green.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [ ] Read these from the branch at program start. Re-read them at every tick.
  - [ ] `git show origin/main:pstack/skills/poteto-mode/playbooks/autopilot-stack.md` where it exists, else the plugin cache copy at `~/.claude/plugins/cache/pstack-claude/pstack/0.15.36/skills/poteto-mode/playbooks/autopilot-stack.md`.
  - [ ] `git show origin/main:pstack/skills/swarm/SKILL.md`, same fallback.
  - [ ] The Claude Code adapter at `~/.claude/plugins/cache/pstack-claude/pstack/0.15.36/docs/harness/claude-code.md`.
  - [ ] `packages/pstack-agent-harness/tools/build-harness.mjs` and `patches/series` on the branch.
- [ ] On the operator's go, arm the audit tick as `/loop 1h` with the tick prompt below. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook from the branch. Audit the operation against it and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in your decision trail. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] AZ1 is first. Every other PR branches after AZ1 lands.
  - [ ] AZ2, AZ3, and AZ4 are independent of each other. AZ5 runs after all of them.
- [ ] Hold the file boundaries. AZ1 touches `patches/` and the generated `harness/` trees. AZ2 touches `docs/integrations.md` and the default Codex home only through its installer. AZ3 and AZ4 each add one assembler section in `tools/build-harness.mjs` plus one docs page. AZ5 touches `docs/support-matrix.md`, `docs/skill-platform-view.md`, and `scripts/check_repository.py` together, the lockstep the gate enforces.
- [ ] Hold the review gate. No PR here changes a UI interaction, so none is review-gated. Each writes `**Review gate.** None.` and no boxes under it.

### PR mechanics, for every PR

- [ ] Resolve the forge once. Default to `gh`. Record any fallback. Never require `gt`.
- [ ] Open the PR ready, never draft, per **Opening a PR**. Until the operator pushes the branch, a PR is a commit on `pstack-upstream-rebase` with the full gate green. After the push, `gh pr create --base main`.
- [ ] Run the repository gate `python scripts/verify.py` once before every commit. Commit with hooks on.
- [ ] Run `/pstack:deslop` before each commit and `/pstack:no-comments` before review.
- [ ] Triage every Bugbot and security-reviewer comment per `../references/bugbot-triage.md`.
- [ ] Rebase onto current trunk before the code-ready report and babysit. Keep that merge base in fix rounds. Rebase again only at merge prep, on a `git merge-tree` conflict with trunk, on a CI failure that comes from a change on trunk, or when a known concurrent change to the same files lands.

### Verdict and merge, for every PR

- [ ] A full swarm runs once, at the code-ready head. A rebase, a merge-conflict resolution, or a minor fix gets a single verifier at the new head, and a wording-only change gets none. Run each full swarm per `pstack/skills/swarm/SKILL.md`. One gates lane. The live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. Two or more audit lanes, each with its own focus, that read the diff and the receipts and distrust the PR body. The root audits the receipts in the merge-ready report before the verdict.
- [ ] Judge every finding by the execution playbook's blocking rule. The verdict is clean when none blocks. A failure on trunk behavior in a lane marked `Regression lane against trunk.` is recorded against trunk and does not block the PR. A new head gets a fresh verdict, except for results that stay valid under the patch-id rule in `playbooks/shipping.md`.
- [ ] The operator lands every PR bottom-up on the pushed branch. The patch-id rule from `playbooks/shipping.md` holds for re-verdicts.

### Boot recipe, for every live lane

Each live lane runs on this maintainer machine at the PR head. There is no cloud VM leg in this program. Drive through the session's shell and the host's own app.

- [ ] `git -C /Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub checkout <head SHA>`.
- [ ] Rebuild the trees with `node tools/build-harness.mjs` when the PR touches them.
- [ ] Drive the real host app or CLI named by the lane. Save every receipt to `evidence/` and every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png`. Return the paths with the report.
- [ ] Read-only diagnostics are the lane's own receipt lines. Name them in the lane's report.

## Rename the distribution identity (AZ1)

**Depends on.** None.

**Files.**

- [x] Create `patches/0018-rename-distribution-identity.patch`.
- [x] Edit `patches/series`.
- [x] Edit `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`, the two marketplace manifests that carry the plugin entry name.
- [x] Edit `scripts/integration_pstack.py`, the installer id `PLUGIN` plus the manifest-name matches, and `packages/agent-orchestration-kit/scripts/install_codex.py`, whose copy counter now recognizes both the new name and legacy `pstack` copies.
- [x] Update the identity literals in `tests/native_codex_fixture.py`, `tests/test_integration_pstack.py`, `tests/test_integration_coexistence_install.py`, and `tests/test_integration_coexistence_transition.py`. Foreign-copy seeds keep the legacy name on purpose, as blocked-foreign scenarios.
- [x] Regenerate `harness/pstack/**` through the build.

**Build.**

- [x] One quilt patch changes `pstack/plugin.json` `name` from `pstack` to `pstack-azhouzhou`, keeps upstream authorship and version, and adds one keyword `azhouzhou`. DEP-3 header `Forwarded: not-needed`, a distribution identity change with no upstream to send.
- [x] `node tools/build-harness.mjs` regenerates every tree. The Claude manifests and the Codex `.codex-plugin/plugin.json` inherit the new name because the assembler reads identity from the tree `plugin.json`.
- [x] The rename surfaced four more identity surfaces the plan had folded into the trees, both marketplace manifests, the installer's plugin id and manifest-name matches, and the Kit's copy counter. All moved together and the gate stayed green.

**You see.**

- [ ] `claude plugin details pstack-azhouzhou@pstack-claude` reports 68 skills, 4 agents, 1 SessionStart hook, after the reinstall lane runs.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `python scripts/verify.py` green with the renamed identity in the trees. Run `python scripts/verify.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `opus` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Install the trunk-named `pstack@pstack-claude` and the head-named `pstack-azhouzhou@pstack-claude` in sequence and compare the plugin details output for skill, agent, and hook counts. Save `rename-parity.png`. Pass when both report 68, 4, and 1.
- [ ] Lane 2. Uninstall `pstack@pstack-claude`, install `pstack-azhouzhou@pstack-claude`, and list `/pstack-azhouzhou:poteto-mode` as invocable. Save `claude-rename-list.png`. Pass when the namespaced skill appears.
- [ ] Lane 3. Invoke `/pstack-azhouzhou:poteto-mode` in a fresh session and confirm the first-message restatement. Save `claude-rename-invoke.png`. Pass when the reply restates goal and smallest change.
- [ ] Lane 4. Confirm the SessionStart mandate still injects under the new name in a fresh session. Save `claude-rename-mandate.png`. Pass when the mandate block names `pstack-azhouzhou`.
- [ ] Lane 5. Confirm the skills-root tree at `~/.agents/skills` is untouched by the rename, 164 entries, 68 pstack. Save `skillsroot-stable.png`. Pass when the counts hold.
- [ ] Lane 6. Rebuild twice and byte-compare the trees. Save `rebuild-idempotent.png`. Pass when the second build changes nothing.
- [ ] Lane 7. Read the generated Codex `.codex-plugin/plugin.json` and confirm the name field and the identity parity with the Claude manifest. Save `codex-manifest-name.png`. Pass when both read `pstack-azhouzhou`.
- [ ] Lane 8. Run the Codex dedicated-home install loop from `docs/integrations.md` against a throwaway home and confirm registration under the new name. Save `codex-throwaway-install.png`. Pass when `doctor` reports the plugin by name.
- [ ] Lane 9. Grep the generated trees for a stray `"pstack"` identity string in manifest position. Save `no-stray-identity.png`. Pass when every manifest names `pstack-azhouzhou` and no skill file changed.
- [ ] Lane 10. Check the patch queue still applies on a pristine re-import by rebuilding from scratch after `rm -rf .build-harness`. Save `patch-queue-clean.png`. Pass when the build succeeds and reports 17 plus 1 patches.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Wall time of one full `node tools/build-harness.mjs` run, trunk and head, same machine, interleaved three times each.
- [ ] Probe. `/usr/bin/time node tools/build-harness.mjs` at trunk and at head, alternating.
- [ ] Baseline. Record the trunk median first.
- [ ] Rule. Head median within 1.5x of trunk. The rename adds one patch application, so any real regression is a parse or copy defect, not load.

**Review gate.** None. AZ1 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator lands AZ1 on the branch.

## Install the plugin into the default Codex home for the ChatGPT desktop (AZ2)

**Depends on.** AZ1.

**Files.**

- [ ] Edit `docs/integrations.md` with the default-home same-home path and its safety rails.

**Build.**

- [ ] One docs change records the supported path. Install `pstack-azhouzhou` from the reviewed local snapshot into the default `~/.codex` through the same-home coexistence rules the matrix already backs, registration plus the model sheet `session hook` line. No installer code changes.

**You see.**

- [ ] A ChatGPT desktop Codex session lists the plugin commands and, after the operator's `/hooks` approval, opens with the mandate injected.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `python scripts/verify.py` green. Run `python scripts/verify.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `opus` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Record the default home's plugins and hooks state before install. Save `default-home-baseline.png`. Pass when the snapshot is complete and restorable.
- [ ] Lane 2. Install into the default home through the documented path and run `doctor`. Save `default-home-doctor.png`. Pass when the plugin registers by the new name and no foreign file changed.
- [ ] Lane 3. List the plugin prompts in a default-home TUI session. Save `codex-prompts.png`. Pass when the poteto-mode prompt appears.
- [ ] Lane 4. After the operator approves `/hooks`, open a fresh ChatGPT desktop Codex session and capture the mandate injection. Save `desktop-mandate.png`. Pass when the session start shows the pstack-azhouzhou mandate.
- [ ] Lane 5. Run one real task in the desktop session through an installed prompt. Save `desktop-task.png`. Pass when the reply follows the poteto first-message rule.
- [ ] Lane 6. Confirm the skills-root user root still resolves and no skill duplicated between plugin and root names. Save `no-duplicate-skills.png`. Pass when the session lists one poteto-mode.
- [ ] Lane 7. Exercise the documented exit. Uninstall restores the baseline snapshot from lane 1. Save `uninstall-restore.png`. Pass when the diff against baseline is empty.
- [ ] Lane 8. Reinstall after uninstall and confirm convergence. Save `reinstall-converge.png`. Pass when the second install changes nothing relative to the first.
- [ ] Lane 9. Confirm the Agent Orchestration Kit files in the default home keep working beside the plugin, one Kit command still resolves. Save `kit-coexist.png`. Pass when the Kit surface answers.
- [ ] Lane 10. Confirm the dedicated home at `~/pstack-accept-tmp` is superseded, its registration disabled in favor of the default home. Save `dedicated-superseded.png`. Pass when only one active registration remains.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Default-home session start wall time before and after the plugin install, five fresh sessions each side.
- [ ] Probe. Time each session start to first prompt, interleaved.
- [ ] Baseline. Record the before median first.
- [ ] Rule. After median within 1.2x of before. The mandate injection is one script run, so a miss here is a hook defect.

**Review gate.** None. AZ2 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator lands AZ2 on the branch.

## Fabricate and install the ZCode plugin (AZ3)

**Depends on.** AZ1.

**Files.**

- [x] Edit `tools/build-harness.mjs` with one zcode plugin bundle emitter.
- [x] Create `docs/integrations.md` zcode plugin section.
- [x] Create `evidence/zcode-plugin-fabric-<date>.md` from the probe.

**Build.**

- [x] One probe first. Established that `zcode plugins marketplace add` accepts a local directory, that the marketplace entry must carry no `source` object so the installer resolves the sibling plugin directory, that the bundle must be flat, and that the `commands` manifest pointer is proven while `hooks` has no sample (receipt `evidence/zcode-plugin-fabric-2026-11-03.md`).
- [x] One emitter in the assembler packages the payload as a zcode plugin bundle named `pstack-azhouzhou`, commands only, with skills left on the shared root. The hooks field stays out as unproven and the omission is recorded.

**You see.**

- [ ] `zcode plugins list` shows `pstack-azhouzhou` enabled, and a ZCode desktop session invokes poteto-mode by name.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] The probe receipt and the emitter's deterministic output, byte-identical across two builds. Run `node tools/build-harness.mjs` twice and `diff -r`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `opus` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Record the current `zcode plugins list` output before install. Save `zcode-baseline.png`. Pass when the 11 official entries are captured unchanged.
- [ ] Lane 2. Add the private marketplace and install the bundle. Save `zcode-install.png`. Pass when `plugins list` shows `pstack-azhouzhou` enabled with the expected skill count.
- [ ] Lane 3. Open a ZCode desktop session and invoke poteto-mode explicitly. Save `zcode-invoke.png`. Pass when the reply follows the first-message rule.
- [ ] Lane 4. Confirm SessionStart firing in the GUI host when the probe proved a hooks field. Otherwise record the negative. Save `zcode-hooks.png`. Pass when the receipt states firing or the documented negative.
- [ ] Lane 5. Confirm the skills-root user root and the plugin do not double-list poteto-mode, one entry wins and the receipt names which. Save `zcode-no-dup.png`. Pass when one entry.
- [ ] Lane 6. Disable the plugin and confirm the skills-root fallback still serves the session. Save `zcode-disable.png`. Pass when poteto-mode still resolves.
- [ ] Lane 7. Update the plugin one version tick and confirm the upgrade path. Save `zcode-update.png`. Pass when the new version reports.
- [ ] Lane 8. Uninstall the plugin and confirm the baseline from lane 1 restores. Save `zcode-uninstall.png`. Pass when the list matches the baseline.
- [ ] Lane 9. Rebuild the bundle twice and byte-compare. Save `zcode-idempotent.png`. Pass when identical.
- [ ] Lane 10. Read the probe receipt back and confirm every claim it makes has a command line behind it. Save `zcode-probe-audit.png`. Pass when the audit finds no unsupported claim.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. ZCode desktop cold session start to first response, before and after plugin install, five sessions each side.
- [ ] Probe. Time the sessions, interleaved.
- [ ] Baseline. Record the before median first.
- [ ] Rule. After median within 1.2x of before, or the receipt records the plugin disabled pending a fix.

**Review gate.** None. AZ3 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator lands AZ3 on the branch.

## Fabricate and install the DeepSeek Harness plugin (AZ4)

**Depends on.** AZ1.

**Files.**

- [ ] Edit `tools/build-harness.mjs` with one dsh package emitter. Parked. The probe proved the surface carries cordis patches only.
- [ ] Create `docs/integrations.md` dsh plugin section. Parked with the emitter.
- [x] Create `evidence/dsh-plugin-fabric-<date>.md` from the probe.

**Build.**

- [x] One probe first. A minimal package in a throwaway profile registered nothing beyond node_modules, the bundle contract decodes to `dsh.bundle.patch` cordis patch layers with icon and locale metadata, and no field carries skills, commands, or hooks (receipt `evidence/dsh-plugin-fabric-2026-11-03.md`).
- [x] One emitter packaged for whatever surface the probe proved. The probe found none for this payload, so the emitter is parked and AZ4 closes as evidence-only on the plan's stated exit.

**You see.**

- [ ] Either a `dsh plugin add` install with the package registered in a profile, or a receipt that parks the plugin form with the measured reason.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] The probe receipt and, when the emitter runs, byte-identical double builds. Run the build twice and `diff -r`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `opus` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Record the throwaway profile's plugin state before add. Save `dsh-baseline.png`. Pass when the empty state is captured.
- [ ] Lane 2. `dsh plugin --profile <throwaway> add <bundle>` and list the profile. Save `dsh-add.png`. Pass when the package registers.
- [ ] Lane 3. Open a DSH session on the profile and confirm poteto-mode resolves. Save `dsh-invoke.png`. Pass when the reply follows the first-message rule.
- [ ] Lane 4. Record what the package registered beyond skills, commands or hooks, by diffing the profile directory. Save `dsh-surface.png`. Pass when the receipt names the surface exactly.
- [ ] Lane 5. Confirm the user root and the profile package do not double-list poteto-mode. Save `dsh-no-dup.png`. Pass when one entry or the precedence is named.
- [ ] Lane 6. Remove the package and confirm the baseline restores. Save `dsh-remove.png`. Pass when the profile diff is empty.
- [ ] Lane 7. Re-add and confirm convergence. Save `dsh-readd.png`. Pass when the second add changes nothing.
- [ ] Lane 8. Rebuild the bundle twice and byte-compare. Save `dsh-idempotent.png`. Pass when identical.
- [ ] Lane 9. Run the skills-root discovery receipt once more on the same profile and confirm it still passes beside the package. Save `dsh-skillsroot-hold.png`. Pass when 68 of 68.
- [ ] Lane 10. Read the probe receipt back and confirm every claim has a command line behind it, or that the park decision names its measured reason. Save `dsh-probe-audit.png`. Pass when the audit holds.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. DSH profile session start to first response, before and after the package add, five sessions each side, when the emitter runs.
- [ ] Probe. Time the sessions, interleaved.
- [ ] Baseline. Record the before median first.
- [ ] Rule. After median within 1.2x of before, or the package is removed and the park is recorded.

**Review gate.** None. AZ4 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator lands AZ4 on the branch.

## Retire the pstack-named installs and update the record (AZ5)

**Depends on.** AZ2, AZ3, AZ4.

**Files.**

- [x] Edit `docs/support-matrix.md`.
- [x] Edit `docs/skill-platform-view.md`.
- [x] Edit `scripts/check_repository.py` when a row vocabulary gains a token.
- [x] Create `evidence/pstack-azhouzhou-retirement-<date>.md`.

The matrix gains one dated plugin-form paragraph in Optional integrations naming all four program targets with their receipts, at `docs/support-matrix.md` beside the `0.9.103` note it supersedes. The view needs no edit: it derives only from capability and OS rows, carries no pstack coverage, and the paragraph sits outside its derivation, so the lockstep holds unchanged. The gate needs no edit: no row vocabulary token was added. The receipt is `evidence/pstack-azhouzhou-retirement-2026-11-04.md`.

**Build.**

- [x] One retirement sweep, evidence-first. The sweep removes the Claude `pstack@pstack-claude` registration, the dedicated home at `~/pstack-accept-tmp` after AZ2 supersedes it, and any zcode or dsh artifacts still carrying the old name. The skills-root links stay, they carry no plugin name. A finding from the sweep holds the whole item here, no machine carries an install named `pstack` that this Hub did not build, so "original pstack" has no separate uninstall target, and the receipt records that.

The sweep ran 2026-11-04. The Claude registration was already gone, replaced by `pstack-azhouzhou@pstack-claude` on 2026-11-02, so the removals covered the superseded `~/pstack-accept-tmp` accept home (48M, the last machine state registering `pstack@pstack-claude`), the pre-rename Hub caches `pstack-claude/pstack/0.15.36` and `0.9.103`, and the upstream cursor caches `cursor-plugins/pstack/0.15.25` and `0.15.29`. No install named `pstack` that this Hub did not build was registered anywhere: upstream pstack had no separate uninstall target, and the receipt records that. Zcode and dsh carried no old-name artifact.

**You see.**

- [ ] Every host reports only `pstack-azhouzhou`, and the matrix names the plugin form for all four targets with their receipts.

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] `python scripts/verify.py` green with the updated matrix, view, and gate constants in lockstep. Run `python scripts/verify.py`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `opus` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Capture the four hosts' install state before the sweep. Save `retire-baseline.png`. Pass when all four snapshots are complete.
- [ ] Lane 2. Run the sweep and list every removed artifact with its evidence line. Save `retire-sweep.png`. Pass when the receipt names each removal.
- [ ] Lane 3. `claude plugin details pstack-azhouzhou@pstack-claude` after the sweep. Save `retire-claude.png`. Pass when only the new name reports.
- [ ] Lane 4. Default Codex home after the sweep. Save `retire-codex.png`. Pass when only the new name reports.
- [ ] Lane 5. `zcode plugins list` after the sweep. Save `retire-zcode.png`. Pass when only the new name reports, or the parked state records.
- [ ] Lane 6. DSH profile after the sweep. Save `retire-dsh.png`. Pass when only the new name reports, or the parked state records.
- [ ] Lane 7. Skills-root invariance, 164 entries, 68 pstack, all resolvable. Save `retire-skillsroot.png`. Pass when the counts hold.
- [ ] Lane 8. Read the matrix and view against the gate, no drift error. Save `retire-gate.png`. Pass when the policy check passes.
- [ ] Lane 9. Search every home for a remaining `pstack` registration string in manifest position. Save `retire-nostray.png`. Pass when none reports.
- [ ] Lane 10. Re-run one end-to-end poteto-mode invocation on any one host and confirm the program still starts. Save `retire-smoke.png`. Pass when the reply follows the first-message rule.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. Combined install-state query time across the four hosts, before and after the sweep, three runs each side.
- [ ] Probe. Time the four queries, interleaved.
- [ ] Baseline. Record the before median first.
- [ ] Rule. After median within 1.2x of before. The sweep removes registrations, so any miss is a broken query, not load.

**Review gate.** None. AZ5 is not review-gated.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Bugbot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] The operator lands AZ5 on the branch.

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

Three open questions gate the plan and their probes live inside AZ3 and AZ4 as their first boxes. Whether a private zcode marketplace accepts a local directory. What the zcode plugin manifest declares for commands and hooks. What a pnpm package added to a dsh profile actually registers. Each question that stays unproven by its probe parks its emitter with a receipt, and the plan still closes.

One question was settled by session evidence before this plan. The name `pstack-azhouzhou` collides with no installed skill or plugin on this machine, checked against the 164-entry shared root and the three plugin registries on 2026-11-03.

## Appendix B. Alternatives rejected

Rename by forking the generator instead of a quilt patch. Rejected because the patch queue exists precisely to carry divergences from pristine upstream, and a fork would trade a patch for an untracked copy.

Keep the `pstack` name and distinguish by marketplace. Rejected by the operator. The name is the namespace users type, and two distributions called `pstack` is the confusion the operator asked to remove.

Unify all four hosts on skills-root only, no plugins. Rejected by the operator. The plugin form buys commands, hooks, and lifecycle on hosts whose registries support them.

Retire the skills-root tree once plugins exist. Rejected. MiMo Code and any future skills-root host still need it, and it is the payload base the emitters read.

## Appendix C. Risks

The default Codex home is the operator's production environment. AZ2 lands in it. The mitigation is the baseline snapshot in AZ2 lane 1 and the restore proof in lane 7, both before any merge.

The zcode and dsh plugin surfaces are unprobed. AZ3 and AZ4 each open with the probe, and each carries a parked exit so an unprovable surface stops the emitter without stopping the program.

The rename changes the namespace users type. Every invocation habit moves from `/pstack:` to `/pstack-azhouzhou:`. AZ1 lane 3 proves the new namespace and the retirement receipt in AZ5 records the old one gone.

The matrix, view, and gate move in lockstep. AZ5 holds them together because the repository policy fails any drift, as the 2026-11-02 DeepSeek Harness column change demonstrated with 34 errors before the lockstep landed.

## Appendix D. Links and reading list

`packages/pstack-agent-harness/tools/build-harness.mjs` and `patches/series` before any emitter work. `docs/integrations.md` for the same-home coexistence rules AZ2 rides. `evidence/pstack-orchestrator-native-acceptance-2026-10-26.md` for the throwaway-home install loop pattern. `docs/support-matrix.md` and `scripts/check_repository.py` together for the AZ5 lockstep. The Claude Code adapter for tool mapping in every lane.
