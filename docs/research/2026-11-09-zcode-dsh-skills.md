# ZCode and DeepSeek Harness Skill comparison

Date: 2026-11-09. Baseline: Hub `bc927303f41b6db843febf70da6c007e28b0c015`.

## Scope and verdicts

The inventory covers every tracked `/SKILL.md` at the two immutable source
commits, including development skills, bundled product skills, aliases and test
fixtures. It does not count local installations or infer the latest upstream
version. The [machine-readable record](2026-11-09-zcode-dsh-skills.json) records
all paths, source-byte hashes, decisions, target owners and review depth.

`adapt` means the applicable engineering method is rewritten into an existing
pstack reference. `reuse` means an existing owner serves the relevant Hub need,
not that all source behavior or host capabilities are equivalent. `host-specific`
keeps an external runtime/installation owner; it is not an implementation hold
on these references. `out-of-scope` records a product-specific or conflicting
method. `fixture` is test input, not an installable capability. Applicability
screening uses entry/tool contracts; adapted methods received body/owner review.
No source scripts, app runtimes, private histories, notes corpus, UI art or
third-party bundled skills are copied.

## What changes

Eight conditional references extend eleven existing pstack entry points. The
[provenance and update contract](../../packages/pstack-agent-harness/ENGINEERING-SOURCES.md)
maps the exact sources, substitutions and MIT/Apache-2.0 notices. Existing
pstack behavior is retained; the patch queue adds task-triggered reading routes.
No new canonical Skill, orchestrator, task store, hook or global installation
is introduced. Hub contributors can reach the same references from
[the engineering router](../agents/engineering.md) without installing pstack.

The adaptation retains semantic consumer tracing; architecture ownership and
legacy-baseline discipline; independent review; failure/cleanup guarantees;
reliable fixtures; truthful coverage and promotion; actual UI/recording evidence;
model-visible context; realistic performance measurement; and complete current
prose. Source-specific selective checks, retired unit tests, automatic note
deletion, native stack merge commits and mandatory re-approval are not adopted.

## Verification boundary

Distribution tests verify the pinned inventory shape, reachable local routes,
reference parity and retained notices in all four generated trees. Negative
controls remove a reference or license and must reject the incomplete bundle.
A fresh generator build must equal the committed output. The Hub root verifier
remains required. These checks do not prove model adherence, semantic benefit,
actual installed discovery, host invocation or visual acceptance. Those claims
need a separate execution with its actual host/model and artifacts. Existing
resume-checkpoint and RSI-promotion gaps are not closed by these instructions.

## Individual decisions

Each row names the exact tracked source path. Read the JSON record for its
source SHA-256 and inspection depth. Targets are existing owners or the adapted
reference, not claims that external runtimes are installed.

### ZCode: 54 entries

Commit: `a9fe401eede6e6e5e01be9048679c206fe6f02d9`.

| Entry | Decision | Target / reason |
| --- | --- | --- |
| `.agents/skills/agent-browser/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Browser CLI integration is an external runtime; use mounted browser tools and package-owned verification, not a new required install. |
| `.agents/skills/ai-elements/SKILL.md` | out-of-scope | [docs](../../docs/principles.md): React chat component library guidance; this change adds engineering disciplines, not a chat frontend. |
| `.agents/skills/architecture-governance/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/blast-radius/references/semantic-impact.md): One owner, event order, managed-boundary coverage and legacy-baseline exceptions; no ZCode layer policy or automatic adoption. |
| `.agents/skills/dep-refs/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/blast-radius/references/semantic-impact.md): Trace re-exports and dynamic consumers; use available indexing/search, not the source TypeScript CLI. |
| `.agents/skills/dogfood/SKILL.md` | reuse | [create-verification-skill](../../packages/pstack-agent-harness/pstack/skills/create-verification-skill/SKILL.md): Existing feature-map and real journey evidence owner; case-admission adds UI and recording truth boundaries. |
| `.agents/skills/e2e-case-lifecycle/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/create-verification-skill/references/case-admission.md): Per-assertion evidence, independent replay expectations and safe promotion; retain current case owner and approval rules. |
| `.agents/skills/electron/SKILL.md` | host-specific | [docs](../../packages/agent-skin/docs/local-install-sop.md): CDP automation and host permissions belong to actual host/tool owner; no blanket connection to user apps. |
| `.agents/skills/feature-boundary-planner/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/blast-radius/references/semantic-impact.md): Trace distinct entries to validation and committed effects; classify and prune cases without a second feature graph. |
| `.agents/skills/react-best-practices/SKILL.md` | out-of-scope | [docs](../../docs/principles.md): Third-party React/Next optimization corpus; no affected React product or imported framework. |
| `.agents/skills/session-management/SKILL.md` | out-of-scope | [docs](../../docs/integrations.md): ZCode task database, organization and CLI persistence invariants are product-specific; do not replace Hub task/runtime owners. |
| `.agents/skills/zcode-large-task-fixture/SKILL.md` | out-of-scope | [docs](../../docs/skill-standard.md): Writes ZCode user databases; Hub benchmarks use synthetic isolated fixtures, not private host persistence. |
| `apps/zcode-cli/.agents/skills/opentui/SKILL.md` | out-of-scope | [docs](../../docs/principles.md): OpenTUI-specific API and terminal app development; no Hub runtime consumer. |
| `apps/zcode-cli/.agents/skills/vercel-react-best-practices/SKILL.md` | out-of-scope | [docs](../../docs/principles.md): Vendored React/Next guidance, not imported under the parent repository license. |
| `apps/zcode-cli/.agents/skills/vercel-react-view-transitions/SKILL.md` | out-of-scope | [docs](../../docs/principles.md): React experimental transitions and Next integration; no corresponding change or runtime. |
| `apps/zcode-cli/packages/android-emulator-plugin/skills/android-dev/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Requires source emulator/simulator MCP tools absent from the Hub package; no native tool capability is inferred. |
| `apps/zcode-cli/packages/browser-use-plugin/skills/control-browser/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Requires mounted browser/native-control tools and their permissions; verification journeys use the active host capability. |
| `apps/zcode-cli/packages/browser-use-plugin/skills/web-gui-tester/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Requires mounted browser/native-control tools and their permissions; verification journeys use the active host capability. |
| `apps/zcode-cli/packages/bundled-skills/skills/dynamic-workflows/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Requires CreateWorkflow/EvalWorkflowSnippet and source journal engine; existing orchestrator keeps task ownership. |
| `apps/zcode-cli/packages/documents-plugin/skills/docx-viewer/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Office/document/viewer plugin requires its source runtime and may carry nested third-party grants; no content or runtime imported. |
| `apps/zcode-cli/packages/documents-plugin/skills/docx/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Office/document/viewer plugin requires its source runtime and may carry nested third-party grants; no content or runtime imported. |
| `apps/zcode-cli/packages/ios-simulator-plugin/skills/ios-dev/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Requires source emulator/simulator MCP tools absent from the Hub package; no native tool capability is inferred. |
| `apps/zcode-cli/packages/pdf-plugin/skills/pdf-viewer/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Office/document/viewer plugin requires its source runtime and may carry nested third-party grants; no content or runtime imported. |
| `apps/zcode-cli/packages/pdf-plugin/skills/pdf/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Office/document/viewer plugin requires its source runtime and may carry nested third-party grants; no content or runtime imported. |
| `apps/zcode-cli/packages/plugin-creator-plugin/skills/plugin-creator/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Native marketplace and plugin lifecycle remain with host-specific integration owner. |
| `apps/zcode-cli/packages/presentations-plugin/skills/pptx-viewer/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Office/document/viewer plugin requires its source runtime and may carry nested third-party grants; no content or runtime imported. |
| `apps/zcode-cli/packages/presentations-plugin/skills/pptx/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Office/document/viewer plugin requires its source runtime and may carry nested third-party grants; no content or runtime imported. |
| `apps/zcode-cli/packages/restore-legacy-sessions-plugin/skills/restore-legacy-sessions/SKILL.md` | out-of-scope | [docs](../../docs/integrations.md): Legacy ACP-to-ZCode database restoration is a product migration, not a portable Skill capability. |
| `apps/zcode-cli/packages/skill-creator-plugin/skills/skill-creator/SKILL.md` | reuse | [docs](../../docs/skill-standard.md): Existing package/evidence/evolution authority; retain neutral metadata and human promotion rules, no bundled creator import. |
| `apps/zcode-cli/packages/spreadsheets-plugin/skills/xlsx-viewer/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Office/document/viewer plugin requires its source runtime and may carry nested third-party grants; no content or runtime imported. |
| `apps/zcode-cli/packages/spreadsheets-plugin/skills/xlsx/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Office/document/viewer plugin requires its source runtime and may carry nested third-party grants; no content or runtime imported. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/brainstorming/SKILL.md` | reuse | [architect](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/architect/SKILL.md): Existing grounding/design owner; do not import a mandatory approval round for every authorized change. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/dispatching-parallel-agents/SKILL.md` | reuse | [swarm](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/swarm/SKILL.md): Existing isolated task ownership; host/user delegation permission still applies. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/executing-plans/SKILL.md` | reuse | [poteto-mode](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/poteto-mode/SKILL.md): Existing task execution and recovery playbooks; checkpoint helper remains unshipped. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/finishing-a-development-branch/SKILL.md` | reuse | [babysit](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/babysit/SKILL.md): Existing check/review/merge gates plus Treehouse lifecycle; no guessed base or local merge alternative. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/receiving-code-review/SKILL.md` | reuse | [get-pr-comments](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/get-pr-comments/SKILL.md): Existing review intake, technical assessment and addressed-thread handling. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/requesting-code-review/SKILL.md` | reuse | [interrogate](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/interrogate/SKILL.md): Existing explicit review owner; new independent-contract reference supplements it. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/subagent-driven-development/SKILL.md` | reuse | [poteto-mode](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/poteto-mode/SKILL.md): Existing orchestration owner; no second framework or unconditional subagents. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/systematic-debugging/SKILL.md` | reuse | [principle-fix-root-causes](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/principle-fix-root-causes/SKILL.md): Existing hypothesis and root-cause discipline; no source-specific mandatory global workflow. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/test-driven-development/SKILL.md` | reuse | [tdd](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/tdd/SKILL.md): Existing explicit TDD owner; preserve destination invocation policy. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/using-git-worktrees/SKILL.md` | reuse | [docs](../../docs/worktree-policy.md): Existing durable Treehouse leases and guarded return; no implicit raw-git fallback. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/using-superpowers/SKILL.md` | out-of-scope | [docs](../../docs/skill-standard.md): Always-on dispatcher duplicates orchestration and broadens invocation; preserve current composition rule. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/verification-before-completion/SKILL.md` | reuse | [principle-prove-it-works](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/principle-prove-it-works/SKILL.md): Existing real-output proof, supplemented by case-admission evidence. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/writing-plans/SKILL.md` | reuse | [architect](../../packages/pstack-agent-harness/harness/pstack/skills-root/skills/architect/SKILL.md): Existing design and implementation planning; no duplicate task database. |
| `apps/zcode-cli/packages/superpowers-plugin/skills/writing-skills/SKILL.md` | reuse | [docs](../../docs/skill-standard.md): Existing package-local workflow and regression/promotion authority; no mandatory second TDD orchestration chain. |
| `apps/zcode-cli/packages/visualize-plugin/skills/visualize/SKILL.md` | reuse | [super-archify](../../skills/super-archify/SKILL.md): Existing diagrams owner for supported outputs; does not claim parity with ZCode inline visualization host. |
| `apps/zcode-cli/packages/zcode-cua-plugin/skills/computer-use/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): Requires mounted browser/native-control tools and their permissions; verification journeys use the active host capability. |
| `apps/zcode-cli/packages/zcode-guide-plugin/skills/diagnosing-commands/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): ZCode native configuration/discovery precedence and UI diagnostics; keep original host owner, not a portable policy claim. |
| `apps/zcode-cli/packages/zcode-guide-plugin/skills/diagnosing-hooks/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): ZCode native configuration/discovery precedence and UI diagnostics; keep original host owner, not a portable policy claim. |
| `apps/zcode-cli/packages/zcode-guide-plugin/skills/diagnosing-mcp/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): ZCode native configuration/discovery precedence and UI diagnostics; keep original host owner, not a portable policy claim. |
| `apps/zcode-cli/packages/zcode-guide-plugin/skills/diagnosing-plugins/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): ZCode native configuration/discovery precedence and UI diagnostics; keep original host owner, not a portable policy claim. |
| `apps/zcode-cli/packages/zcode-guide-plugin/skills/diagnosing-skills/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): ZCode native configuration/discovery precedence and UI diagnostics; keep original host owner, not a portable policy claim. |
| `apps/zcode-cli/packages/zcode-guide-plugin/skills/zcode-configuration-guide/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): ZCode native configuration/discovery precedence and UI diagnostics; keep original host owner, not a portable policy claim. |
| `apps/zcode-cli/packages/zcode-site-plugin/skills/site-deploy/SKILL.md` | host-specific | [docs](../../docs/support-matrix.md): ZCode Sites deployment API and publication authority are external, not part of Hub engineering adaptation. |
| `packages/desktop/test/e2e/fixtures/plugin-mcp-skill/e2e-plugin-mcp-ping/skills/plugin-mcp-ping/SKILL.md` | fixture | [docs](../../docs/skill-standard.md): Test-only discovery or replay input, not a deployable engineering capability. |

### deepseek-harness: 38 entries

Commit: `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`.

| Entry | Decision | Target / reason |
| --- | --- | --- |
| `.agents/skills/agent-experience/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/principle-guard-the-context-window/references/model-interface.md): Deferred discovery, parameter-local rules, omitted context and measured total work; development entry aliases preset source. |
| `.agents/skills/cordis-styling-nitpicking/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/principle-boundary-discipline/references/failure-ownership.md): Resource ownership and consumer completion before releasing dependencies; do not import Cordis services or blanket P0 labels. |
| `.agents/skills/dsh-archive-agent-notes/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/technical-writing/references/current-contracts.md): Check full/partial supersession and durable rationale; no inherited deletion policy, notes store or memory writes. |
| `.agents/skills/dsh-ci-test-reliability/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/principle-test-behavior-not-implementation/references/reliable-fixtures.md): Atomic resources, exact global restoration, readiness barriers, platform semantics and quiescent teardown. |
| `.agents/skills/dsh-client-ui-ux/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/create-verification-skill/references/case-admission.md): Actual assembled-screen review and state/consumer scope; no import of source design tokens or full-audit quotas. |
| `.agents/skills/dsh-code-review/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/interrogate/references/independent-contracts.md): Requirements independent of the diff, direct/alternate denial paths and actual shipped entries. |
| `.agents/skills/dsh-create-upgrade-guide/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/technical-writing/references/current-contracts.md): Explain externally visible break, affected release, migration, verification and recovery at existing owner. |
| `.agents/skills/dsh-cua-macos-signing/SKILL.md` | host-specific | [docs](../../packages/agent-skin/docs/local-install-sop.md): Personal signing identity and macOS grants require the actual host installer and explicit scope; no key creation. |
| `.agents/skills/dsh-doc/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/technical-writing/references/current-contracts.md): One current owner, source-before-generated edits, consumer docs and migration guidance; no DSH taxonomy. |
| `.agents/skills/dsh-error-handling/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/principle-boundary-discipline/references/failure-ownership.md): Typed errors, state guarantees, owned retries, visible unknown outcomes and independent reporting fallback. |
| `.agents/skills/dsh-find-simplifications/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/interrogate/references/independent-contracts.md): Remove maintained obligations only after tracing consumers and preservation requirements; no autonomous deletion. |
| `.agents/skills/dsh-merging-stacked-prs/SKILL.md` | reuse | [references](../../packages/pstack-agent-harness/hub-skills/poteto-mode/references/merge-safety.md): Existing merge owner and exact-head gates; DSH native-stack merge-commit mandate conflicts with Hub squash-only policy. |
| `.agents/skills/dsh-official-plugin-artwork/SKILL.md` | out-of-scope | [docs](../../docs/skill-standard.md): Official DSH icon library/design approval and assets are not Hub brand assets; keep current brand/visual review ownership. |
| `.agents/skills/dsh-pr-description/SKILL.md` | reuse | [playbooks](../../packages/pstack-agent-harness/pstack/skills/poteto-mode/playbooks/opening-a-pr.md): Existing PR owner and evidence; source-specific AI percentage declaration/GIF upload policy not adopted. |
| `.agents/skills/dsh-pre-push-checks/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/interrogate/references/independent-contracts.md): Exact base/head and current evidence; Hub full verification remains mandatory; scope command already landed separately. |
| `.agents/skills/dsh-prose-standard/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/technical-writing/references/current-contracts.md): Preserve actors, timing, modality, exceptions, effects and failure consequences when trimming. |
| `.agents/skills/dsh-responsive-ui/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/create-verification-skill/references/case-admission.md): Action access, wrapping, touch/hover/keyboard and focus preservation; target product owns viewport limits. |
| `.agents/skills/dsh-session-projection/SKILL.md` | out-of-scope | [docs](../../docs/integrations.md): Session projection/reader/checkpoint ABI is DSH runtime-specific; no parallel Hub event-sourcing engine. |
| `.agents/skills/dsh-speed-up-perf/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/benchmark-checklist/references/user-paths.md): Realistic dimensions, production endpoint, retained memory, cold/warm parity and negative controls. |
| `.agents/skills/dsh-translate-docs/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/technical-writing/references/current-contracts.md): Keep bilingual meaning and terminology; no delegated translation, pairing hash scheme or global workflow invocation. |
| `.agents/skills/dsh-trim-cot-leakage/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/technical-writing/references/current-contracts.md): Replace private session citations with current facts while preserving legitimate historical evidence. |
| `.agents/skills/record-browser-gif/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/create-verification-skill/references/case-admission.md): Bind recordings to actual revision/server and fixture/live conditions; no automatic upload or mandatory source encoder. |
| `packages/experimental/webworker-runtime/tests/fixtures/vfs-example/workspace/.agents/skills/preview-tour/SKILL.md` | fixture | [docs](../../docs/skill-standard.md): Test-only discovery or replay input, not a deployable engineering capability. |
| `packages/preset/agent-preset/skills/agent-experience/SKILL.md` | adapt | [references](../../packages/pstack-agent-harness/hub-skills/principle-guard-the-context-window/references/model-interface.md): Deferred discovery, parameter-local rules, omitted context and measured total work; development entry aliases preset source. |
| `packages/preset/agent-preset/skills/cordis-composition-reference/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Cordis composition/plugin editing requires DSH runtime services and native permission checks; no second Hub installer. |
| `packages/preset/agent-preset/skills/cordis-plugin-development/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Cordis composition/plugin editing requires DSH runtime services and native permission checks; no second Hub installer. |
| `packages/preset/agent-preset/skills/editing-cordis-compositions/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Cordis composition/plugin editing requires DSH runtime services and native permission checks; no second Hub installer. |
| `packages/sandbox/sandbox-windows-acl/assets/diagnose-windows-sandbox-acl/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Windows ACL diagnosis is bound to the DSH sandbox owner; Hub does not ship that subsystem. |
| `packages/skill/skill-office/assets/office-docx/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Office tool APIs and document runtimes belong to the DSH plugin; not needed for engineering skill adaptation. |
| `packages/skill/skill-office/assets/office-export-pdf/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Office tool APIs and document runtimes belong to the DSH plugin; not needed for engineering skill adaptation. |
| `packages/skill/skill-office/assets/office-pptx/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Office tool APIs and document runtimes belong to the DSH plugin; not needed for engineering skill adaptation. |
| `packages/skill/skill-office/assets/office-recalculate/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Office tool APIs and document runtimes belong to the DSH plugin; not needed for engineering skill adaptation. |
| `packages/skill/skill-office/assets/office-render/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Office tool APIs and document runtimes belong to the DSH plugin; not needed for engineering skill adaptation. |
| `packages/skill/skill-office/assets/office-xlsx/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Office tool APIs and document runtimes belong to the DSH plugin; not needed for engineering skill adaptation. |
| `packages/skill/skill-office/assets/office/SKILL.md` | host-specific | [docs](../../docs/integrations.md): Office tool APIs and document runtimes belong to the DSH plugin; not needed for engineering skill adaptation. |
| `snapshots/session/skill-load/workspace/.dsh/skills/model-only-skill/SKILL.md` | fixture | [docs](../../docs/skill-standard.md): Test-only discovery or replay input, not a deployable engineering capability. |
| `snapshots/session/skill-load/workspace/.dsh/skills/snapshot-skill/SKILL.md` | fixture | [docs](../../docs/skill-standard.md): Test-only discovery or replay input, not a deployable engineering capability. |
| `snapshots/session/skill-load/workspace/.dsh/skills/user-only-skill/SKILL.md` | fixture | [docs](../../docs/skill-standard.md): Test-only discovery or replay input, not a deployable engineering capability. |
