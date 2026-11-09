# Engineering reference provenance

These eight references are adaptations maintained by Azhou AI Hub. They add
conditional instructions to existing pstack skills; they are not new plugins,
canonical Hub skills, automatic validators, or permission grants.

## Immutable sources

- ZCode: https://github.com/zai-org/ZCode/tree/a9fe401eede6e6e5e01be9048679c206fe6f02d9
  — Apache-2.0; retain `LICENSE-ZCode` and the unmodified `NOTICE-ZCode.md`.
- DeepSeek Harness: https://github.com/deepseek-ai/deepseek-harness/tree/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159
  — MIT, Copyright (c) 2026 DeepSeek; retain `LICENSE-DeepSeek`.
- Existing pstack and component sources retain their MIT notices. The bundle
  contains both MIT and Apache-2.0 material; the root MIT license does not
  replace the ZCode grant. No trademark or third-party product asset grant is
  inferred. `NOTICE-ZCode.md` describes its original product, not this bundle.

## Adaptation map

Paths below are relative to the distributed `skills/` directory. Source names
refer to `.agents/skills/<name>/SKILL.md` at the pinned source except for DSH
`agent-experience`, whose actual owner is
`packages/preset/agent-preset/skills/agent-experience/SKILL.md`.

| Reference | Source skills | Local changes |
| --- | --- | --- |
| `blast-radius/references/semantic-impact.md` | ZCode feature-boundary-planner, architecture-governance, dep-refs | Generalize state owners, consumers and acceptance cases; use current repository checks and available search, not ZCode's TS parser, layer names, graph or session model. |
| `principle-boundary-discipline/references/failure-ownership.md` | DSH dsh-error-handling, cordis-styling-nitpicking | Keep failure guarantees and quiescent cleanup without Cordis services or source-specific severity rules. |
| `principle-test-behavior-not-implementation/references/reliable-fixtures.md` | DSH dsh-ci-test-reliability | Generalize runner topology, resource allocation and platform evidence; retain the destination's required checks. |
| `create-verification-skill/references/case-admission.md` | ZCode e2e-case-lifecycle; DSH dsh-client-ui-ux, dsh-responsive-ui, record-browser-gif | Keep independent expectations, per-assertion coverage, transactional promotion and real UI evidence; no WDIO, Docker admission flags, fixed viewport, automatic GIF publication or second case store. |
| `interrogate/references/independent-contracts.md` | DSH dsh-code-review, dsh-find-simplifications, dsh-pre-push-checks | Keep consumer necessity and independent requirements; preserve Hub full verification, squash-only policy and review-thread gates. |
| `principle-guard-the-context-window/references/model-interface.md` | DSH agent-experience | Add deferred discovery, omissions and total-work measurement; do not infer unavailable host APIs or private context. |
| `benchmark-checklist/references/user-paths.md` | DSH dsh-speed-up-perf | Retain realistic workload dimensions, memory and end-to-end endpoints; use existing benchmark owners and calibrated local limits. |
| `technical-writing/references/current-contracts.md` | DSH dsh-prose-standard, dsh-doc, dsh-trim-cot-leakage, dsh-create-upgrade-guide, dsh-translate-docs, dsh-archive-agent-notes | Preserve propositions, current authority, bilingual meaning and migration steps; no imported note store, deletion authority or mandatory delegated translation. |

## Reproduce and update

In the Hub source checkout, the complete pinned inventory and individual
adopt/reuse/exclude decisions live in
`docs/research/2026-11-09-zcode-dsh-skills.json` and its Markdown companion.
Enumerate each original checkout with
`git ls-tree -r --name-only <pin>` and select paths ending in `/SKILL.md`.
Read bytes with `git show <pin>:<path>`; compare their SHA-256 values with the
inventory. The DSH development alias is a Git symlink, so inspect its tracked
target too. Do not treat locally installed or untracked skills as source.

When updating, freeze the new commit, re-enumerate the whole inventory,
review changed source entries and their applicable license/notice files, then
edit `hub-skills/` and the conditional-entry patch in `patches/series`.
Keep `pstack/` and `components/` pristine. Run
`node tools/build-harness.mjs` from this package and commit the generated
four trees with the source changes. Run the Hub root verifier and compare a
fresh build with the committed trees. Never edit generated instructions alone.

The eleven existing entry routes load only the reference needed for the task.
`architect` shares the impact reference; `maintain-verification-skill` and
`principle-prove-it-works` share case admission. Reading a reference does not
invoke another orchestrator. Existing tools and human approval boundaries
continue to apply. Installation, actual model use and effectiveness require
separate host evidence; repository checks establish distribution integrity.
