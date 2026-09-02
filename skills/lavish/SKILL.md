---
name: lavish
description: Turn complex or visual agent responses into rich, reviewable HTML artifacts that users can annotate and send feedback on through the Lavish Editor CLI, and relay a PRD, RFC, design spec, or technical plan with comments, selected-text annotations, feedback disposition, and next-owner state inside one portable HTML file. Use for visual artifacts, HTML explainers, interactive prototypes, review surfaces, product or technical plans, team spec review or transfer, comparisons, diagrams, tables, code views, reports, slides, or browser-based feedback loops.
---

# Lavish Editor

Lavish Editor turns rich HTML artifacts into collaborative human review surfaces. First generate an interactive HTML artifact for the request, then run `npx -y lavish-axi@0.1.47 <html-file>` so the user can inspect it, annotate elements or selected text, queue prompts, and send feedback.

**🦊 阿舟 · Lavish**

> 把复杂结果变成可审阅的界面。In relay mode, the HTML itself is the handoff packet.

Emit once when the skill starts:

```text
🦊 阿舟 · Lavish 启动｜mode=<artifact|relay|review|export|share>｜scope=<short scope>
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

If the request above is non-empty, the user invoked `/lavish` explicitly. Use relay mode when it asks to package, relay, or hand off a spec or plan for team review; otherwise build an HTML artifact for that request now.
If it is empty, infer from the conversation. Relay mode is for PRDs, RFCs, design specs, technical specs, implementation plans, and team handoffs; artifact mode is for every other complex or visual response.

## Artifact mode workflow

1. Create the HTML artifact. Default to `.lavish/<name>.html` in the working directory.
2. Run `npx -y lavish-axi@0.1.47 <html-file>` to open or resume a review session in the browser.
   If the output carries a `self_paint_warning`, fix the unpainted page surface and save before polling. Lavish live-reloads the artifact.
3. Run `npx -y lavish-axi@0.1.47 poll <html-file>` to long-poll for the user's annotations and queued prompts.
   On the first poll, prefer `--agent-reply "<one-line summary of what you built and what to review first>"` so the conversation panel opens with context.
   Browser-detected layout issues are filed passively in the user's Layout issues inbox and arrive as an ordinary `layout-warnings` prompt only when the user selects and queues them. Never edit an issue the user has not queued. The only response that arrives without user action is `artifact_failures`, when the review surface itself is unusable.
   The poll stays silent until the user acts or a fatal artifact failure makes the review surface unusable. Leave it running; never kill it.
   Cosmetic, intentional, transient, tiny, and uncertain observations remain silent.
   Keep the poll in the foreground by default and let it return the feedback directly to the agent.
   A background poll is allowed only through a harness-native tracked background-job facility whose completion result is guaranteed to resume or notify the same agent.
   Never use `nohup`, shell `&`, `disown`, redirected fire-and-forget processes, or a detached terminal without an explicit verified callback merely to keep polling alive.
   If the harness has no completion-aware background facility, use the foreground poll or first wire a verified wake callback into the surrounding supervisor.
   Do not tell the user the artifact is being monitored until that wake path is live.
   If the poll gets killed or times out, re-run it. Queued feedback is not lost.
4. If polling returns feedback, apply the user's prompts. A `layout-warnings` prompt is an explicit repair request; apply every listed fix in one pass before saving, then let Lavish re-check it after a newer artifact load.
5. Apply human feedback, then poll again with `--agent-reply "<message>"` to reply in the browser and keep the loop going under the same foreground-or-verified-wake-path rule.
6. Run `npx -y lavish-axi@0.1.47 end <html-file>` when the review is finished.
7. `Send & End` ends the session. Its final feedback is still delivered once. After that response, stop polling and do not reopen the session uninvited. Deliver any remaining updates directly in the conversation.

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
5. Validate, close, and hand off. Run `end` when the review finishes and process one final `Send & End` return. After the last write, run `python3 <skill-dir>/scripts/relay_state.py validate <html-file>`. Run `export` when a portable file is requested and validate the export too. Run `share` only with explicit publication authorization; sharing sends the embedded comments to the third-party `ht-ml.app`.
   Completion: the [brand-layer](references/brand-layer.md) relay receipt names the source and revision, artifact, state schema, session, feedback counts, unresolved owners, transport, publication, named checks, and one next action.

## Authorization boundaries

- Create local artifacts and open local review sessions when they are in scope.
- Do not install global packages, install session hooks, or change global agent configuration without explicit authorization.
- Do not run `share` without explicit publication authorization. A share uses the third-party `ht-ml.app` service and is public by default unless a password is supplied.
- Do not treat authorization to create or review an artifact as authorization to publish it.
- Relay packets are review data: copying, exporting, or sharing the file also transfers the embedded comments and annotations. A selected, sanitized packet may be committed only when the user explicitly requests it.
- Do not reopen a session the user ended from the browser unless the user asks; when important new material requires reopening, explain why first.

## Visual guidance

- Use visual hierarchy to make the most important decisions, risks, tradeoffs, and next actions obvious at a glance.
- Use sections, cards, tables, diagrams, annotated snippets, and side-by-side comparisons instead of long prose.
- Conclusions, evidence, boundaries, and next actions come before decoration; each card or region completes one cognitive action.
- Choose typography, spacing, color, and layout deliberately so the artifact has a clear point of view.
- Prevent horizontal overflow at every nesting level. Nested grid and flex children need `minmax(0, 1fr)` tracks and `min-width: 0`; wrap, truncate, or contain long unbreakable text deliberately.
- When the artifact describes existing UI or state, show it. Capture screenshots of the real pages in read-only mode and embed them; reserve prose for rationale, tradeoffs, and open questions.
- The HTML never carries Azhou identity, emoji, character art, or skill colors, and the source's own brand is never overwritten.

## Playbooks

Run `npx -y lavish-axi@0.1.47 playbook <id>` for focused guidance. One artifact can combine several playbooks, so open each matching playbook before writing HTML.
For flows, architecture, state, or sequence diagrams, do not hand-build boxes and arrows with divs or flexbox. Open the diagram playbook and use the theme-aware Mermaid snippet from `npx -y lavish-axi@0.1.47 design` unless richly annotated SVG nodes are required.

- `diagram` - Map relationships, flows, state, and architecture.
- `table` - Turn dense records into scan-friendly review surfaces.
- `comparison` - Show options, tradeoffs, and current versus target behavior.
- `plan` - Explain a product or technical plan before implementation.
- `code` - Render source code, code files, patches, PR diffs, and before/after code.
- `input` - Use when collecting decisions, preferences, triage, scope, or other structured feedback inside the artifact.
- `slides` - Create a deliberate presentation when slides are requested.

## Commands and rules

- Run `npx -y lavish-axi@0.1.47 <html-file>` to open or resume a review session. If the user explicitly ended the session from the browser, this refuses to reopen it and explains why; pass `--reopen` only when the user asks or important new material requires their attention.
- Unless the user specifies another location, create HTML artifacts under `.lavish/` in the working directory.
- Lavish serves the HTML file through a local server. If HTML references other filesystem assets, copy them into the same artifact directory and use relative paths. Never prepend `/` to asset paths.
- Run `npx -y lavish-axi@0.1.47 poll <html-file>` to wait for feedback. Leave it running in the foreground or through a verified harness callback. Never detach it with shell fire-and-forget mechanisms.
- Rendered Mermaid diagrams in `.mermaid` containers become embedded, editable Excalidraw whiteboards in the browser. Queue feedback returns a bounded edit summary plus local scene and preview paths. Read the summary first, inspect files only when needed, then update the Mermaid source in the artifact. Never write the scene file back.
- Run `npx -y lavish-axi@0.1.47 end <html-file>` to end a session as the agent. Agent-ended sessions may be reopened normally; browser-ended sessions require explicit `--reopen`.
- Run `npx -y lavish-axi@0.1.47 export <html-file> [--out <path>]` to write one portable HTML file with local assets inlined. Remote CDN and font references remain network dependencies.
- After explicit publication authorization, run `npx -y lavish-axi@0.1.47 share <html-file> [--password <pw>] [--token <t>]` to publish on `ht-ml.app`. Shares are public by default; use `--password` for a private page. The command returns a URL and secret update key.
- Run `npx -y lavish-axi@0.1.47 stop` to stop the background server. It also self-stops when idle or after the last session ends with nothing connected.
- Run `npx -y lavish-axi@0.1.47 playbook <playbook_id>` for focused artifact guidance. Open every matching playbook before writing HTML.
- Lavish does not inject a design system. Choose the design direction in this order: use the user's requested look; otherwise inspect and match the subject project's design system; only if both yield nothing use the Tailwind CSS browser runtime v4 plus DaisyUI v5 recommended by `npx -y lavish-axi@0.1.47 design`. State the selected design source and reason on delivery.
- In relay mode, resolve `<skill-dir>` to the installed `skills/lavish/` directory and drive the embedded packet state with `python3 <skill-dir>/scripts/relay_state.py init|add-feedback|update-feedback|update-metadata|refresh-ledger|show|validate <html-file>`; the exact commands and flags are defined in the [Spec Relay contract](references/spec-relay.md).

## Completion

End with the stable receipt defined in [brand-layer.md](references/brand-layer.md): `lavish.receipt.v1` for artifact mode, `spec-relay.receipt.v1` for relay mode. Keep `complete`, `complete_with_holds`, `hold`, and `failed` distinct; none substitutes for another. A local artifact or open session does not prove human review, export portability, or publication. Browser feedback is only deliverable after the poll returns and the relay packet persists it; an open session does not prove feedback was persisted.
