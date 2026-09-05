# Artifact mode

Run artifact mode per this reference; the entry keeps the mode choice, authorization boundaries, and receipts. Everything here is written for `artifact` mode; relay mode follows the [Spec Relay contract](spec-relay.md), and relay stage 3 reuses the polling rules below (`self_paint_warning`, foreground-or-verified-callback).

## Artifact mode workflow

1. Create the HTML artifact. Default to `.lavish/<name>.html` in the working directory.
   Completion: the artifact file exists at the recorded path and renders as a reviewable page.
2. Run `npx -y lavish-axi@0.1.47 <html-file>` to open or resume a review session in the browser.
   If the output carries a `self_paint_warning`, fix the unpainted page surface and save before polling. Lavish live-reloads the artifact.
   Completion: the review session is live in the browser and its session output is recorded.
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
   Completion: a poll is attached under the foreground-or-verified-wake-path rule and its tracked reference is recorded.
4. If polling returns feedback, apply the user's prompts. A `layout-warnings` prompt is an explicit repair request; apply every listed fix in one pass before saving, then let Lavish re-check it after a newer artifact load.
   Completion: every returned prompt is applied or explicitly dispositioned, and the artifact was saved after the last edit.
5. Apply human feedback, then poll again with `--agent-reply "<message>"` to reply in the browser and keep the loop going under the same foreground-or-verified-wake-path rule.
   Completion: the reply is visible in the conversation panel and the next poll is attached.
6. Run `npx -y lavish-axi@0.1.47 end <html-file>` when the review is finished.
   Completion: `end` returned its closing summary and no queued feedback remains.
7. `Send & End` ends the session. Its final feedback is still delivered once. After that response, stop polling and do not reopen the session uninvited. Deliver any remaining updates directly in the conversation.
   Completion: the session is closed with no further polling; remaining updates go through the conversation, not the review surface.

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
- In relay mode, resolve `<skill-dir>` to the installed `skills/lavish/` directory and drive the embedded packet state with `python3 <skill-dir>/scripts/relay_state.py init|add-feedback|update-feedback|update-metadata|refresh-ledger|show|validate <html-file>`; the exact commands and flags are defined in the [Spec Relay contract](spec-relay.md).
