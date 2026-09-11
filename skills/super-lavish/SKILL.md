---
name: super-lavish
description: Renamed from lavish (the old name still triggers this skill). Turn complex or visual agent responses into rich, reviewable HTML artifacts that users can annotate and send feedback on through the Lavish Editor CLI, and relay a PRD, RFC, design spec, or technical plan with comments, selected-text annotations, feedback disposition, and next-owner state inside one portable HTML file. Use for visual artifacts, HTML explainers, interactive prototypes, review surfaces, product or technical plans, team spec review or transfer, comparisons, diagrams, tables, code views, reports, slides, or browser-based feedback loops.
invocation: user-invoked orchestrator
---

# Super Lavish Editor

Super Lavish Editor turns rich HTML artifacts into collaborative human review surfaces. First generate an interactive HTML artifact for the request, then run `npx -y lavish-axi@0.1.47 <html-file>` so the user can inspect it, annotate elements or selected text, queue prompts, and send feedback.

**🦊 阿舟 · Super Lavish**

> 把复杂结果变成可审阅的界面。In relay mode, the HTML itself is the handoff packet.

Emit once when the skill starts:

```text
🦊 阿舟 · Super Lavish 启动｜mode=<artifact|relay|review|export|share>｜scope=<short scope>
```

Pick exactly one mode for each request:

- `artifact` (default): build the review surface for the current request and run the browser feedback loop.
- `relay`: Spec Relay — package a source spec, its comments, selected-text annotations, feedback disposition, and next-owner state into one portable HTML handoff packet.

Azhou only hosts the agent process; it is not an HTML brand. Artifacts keep the source content's own brand and design system; the skill never injects Azhou names, emoji, character assets, or colors into HTML bodies, embedded state, paths, commands, or evidence.

Before first use, read [setup](references/setup.md). Before changing the imported workflow, read [provenance](references/provenance.md) and [upstream compatibility](references/upstream-compatibility.md). For interactive sessions, follow the [Azhou interaction layer](references/brand-layer.md). In relay mode, also read the [Spec Relay contract](references/spec-relay.md) before generating the packet.

You do not need `lavish-axi` installed globally. Invoke the locked baseline with `npx -y lavish-axi@0.1.47 <html-file>`.
If `lavish-axi` output shows a follow-up command starting with `lavish-axi`, run it as `npx -y lavish-axi@0.1.47 ...` instead.
In restricted subprocess sandboxes, CI, or agent harnesses where `npx -y` exits opaquely, use an already-installed copy directly: `node "$(npm root)/lavish-axi/dist/cli.mjs" <html-file>` for a local install, `node "$(npm root -g)/lavish-axi/dist/cli.mjs" <html-file>` for a global install, or the bare `lavish-axi <html-file>` bin after installing version `0.1.47` once.

## Request

$ARGUMENTS

If the request above is non-empty, the user invoked `/super-lavish` (or the compatibility name `/lavish`) explicitly. Use relay mode when it asks to package, relay, or hand off a spec or plan for team review; otherwise build an HTML artifact for that request now.
If it is empty, infer from the conversation. Relay mode is for PRDs, RFCs, design specs, technical specs, implementation plans, and team handoffs; artifact mode is for every other complex or visual response.
## Artifact mode workflow

Follow [artifact mode](references/artifact-mode.md): create the HTML artifact (default `.lavish/<name>.html`), open the review session, long-poll for feedback in the foreground or through a verified harness callback, apply prompts, and `end` when finished. The reference carries the step-by-step workflow, visual guidance, playbooks, and the full command rules.

## Relay mode workflow

Follow the five material stages in order; each completion condition is a named check in the receipt.

1. Lock scope and authority. Choose the content authority: a source file, a user-supplied URL, or `conversation:<scope>`. Record the source revision, review goal, review status, next owner, allowed files, and publication boundary. An unknown revision is a visible hold on traceability, not permission to invent one.
   Completion: the receipt can name one authority, one review goal, and an explicit scope.
2. Build the review model and write the HTML. Apply every rule in the [Spec Relay contract](references/spec-relay.md): source metadata, scope and non-goals, requirements and acceptance criteria, decisions, risks, and open questions; one review responsibility per region; a stable unique `data-review-id` per material item. Pick the design source and open each matching playbook; default path `.lavish/<name>.html`. After the body is complete, run `relay_state.py init` to embed `spec-relay.html-state.v1`; the visible feedback ledger is a deterministic view of that embedded state.
   Completion: every material source item is mapped or recorded as intentionally omitted; IDs are unique; source and revision are visible; packet ID, state revision, and target resolve; the page passes narrow-screen and overflow checks.
3. Open a real browser review and poll. Use the same CLI, `self_paint_warning`, and foreground-polling rules as artifact mode, with `--agent-reply` naming the packet and the first review point.
   Completion: a real session is open and polling is attached; record an exact hold when it cannot connect, and never write "HTML opens" as review completed.
4. Persist every returned feedback item into the HTML. Read the current `state_revision`, then use `add-feedback --expected-revision <n>` to store the complete comment, selection or element target, disposition (`accepted`, `rejected`, `deferred`, or `needs_clarification`), rationale, source change, owner, and timestamps. Use `update-feedback` when a comment, owner, source change, or disposition changes; `update-metadata` when the source revision, review status, or next owner changes; `refresh-ledger` when the visible ledger was edited or the renderer was upgraded; on a stale revision, read the current packet and reconcile instead of silently overwriting. Accepted items update the artifact; sync the source spec only when the task authorizes that file change, otherwise record the proposal in `source_change`. Keep polling in the same session after handling feedback.
   Completion: every returned item keeps its original text, target, disposition, rationale, and unresolved owner; the complete visible ledger is the exact projection of the embedded state.
5. Validate, close, and hand off. Run `end` when the review finishes and process one final `Send & End` return. After the last write, run `python <skill-dir>/scripts/relay_state.py validate <html-file>`. Run `export` when a portable file is requested and validate the export too. Run `share` only with explicit publication authorization; sharing sends the embedded comments to the third-party `ht-ml.app`.
   Completion: the [brand-layer](references/brand-layer.md) relay receipt names the source and revision, artifact, state schema, session, feedback counts, unresolved owners, transport, publication, named checks, and one next action.
   Resolve `<skill-dir>` to the installed `skills/super-lavish/` directory when driving `relay_state.py`.
## Authorization boundaries

- Create local artifacts and open local review sessions when they are in scope.
- Do not install global packages, install session hooks, or change global agent configuration without explicit authorization.
- Do not run `share` without explicit publication authorization. A share uses the third-party `ht-ml.app` service and is public by default unless a password is supplied.
- Do not treat authorization to create or review an artifact as authorization to publish it.
- Relay packets are review data: copying, exporting, or sharing the file also transfers the embedded comments and annotations. A selected, sanitized packet may be committed only when the user explicitly requests it.
- Do not reopen a session the user ended from the browser unless the user asks; when important new material requires reopening, explain why first.
## Completion

End with the stable receipt defined in [brand-layer.md](references/brand-layer.md): `super-lavish.receipt.v1` for artifact mode, `spec-relay.receipt.v1` for relay mode. Keep `complete`, `complete_with_holds`, `hold`, and `failed` distinct; none substitutes for another. A local artifact or open session does not prove human review, export portability, or publication. Browser feedback is only deliverable after the poll returns and the relay packet persists it; an open session does not prove feedback was persisted.
