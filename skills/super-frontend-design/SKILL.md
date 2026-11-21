---
name: super-frontend-design
description: "Azhou skill. Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults. Use when a task must choose or execute the visual direction of a frontend surface — palette, typography, layout, and avoiding the AI-generated default looks — for a new UI or a restyle of an existing one. MUST trigger for 前端视觉设计, 界面风格方向, 让界面不像 AI 生成的, 重设计界面外观. Diagram maps and one-page explainers belong to super-archify; annotated browser feedback loops on a generated page belong to super-lavish; zero-background topic explainers belong to super-eli5; editable .excalidraw source scenes belong to super-excalidraw-diagram."
invocation: both
---

# Frontend Design

**🦊 阿舟 · Frontend Design**

> 🎨 每个界面长出自己的身份，而不是模板的回声。

This package is the hub's canonical adoption of the upstream `frontend-design` skill. The upstream guidance body below is preserved verbatim at the pinned commit recorded in [provenance](references/provenance.md); the hub adds only the wrapper layer — neutral frontmatter, this identity anchor and brand protocol, the boundaries, and the stable receipt. The capability-by-capability comparison lives in [upstream-compatibility.md](references/upstream-compatibility.md).

## Brand protocol

Emit this exact display event once, at the start of every run, with the resolved mode and input scope:

```text
🦊 阿舟 · Frontend Design 启动（mode=<new-ui|restyle>, scope=<brief-or-codebase>）
```

Use `✅ 验证通过` only after the design plan has been reviewed against the brief and the delivered artifact actually exists, and only as the final stage event. Use `❌ 验证失败` when no direction can be delivered or the review cannot run, and `🔒 阿舟暂停这一项` when the request contradicts the boundary: the brief already pins a direction and the ask is to silently override it, or an unreviewed design is being presented as verified. Emoji is display-only; keep JSON keys, schema values, digests, paths, commands, test names, and raw evidence emoji-free. A host without Unicode may remove the leading emoji while preserving the fixed text, `（k=v, k=v）` field groups, fields, and values. Raw evidence such as conversation excerpts or user paths stays out of the receipt unless the user supplied it.

In a Markdown chat host, wrap each brand broadcast as `> <emoji> **<label>**<protocol-tail>` (S1). Peeling the leading `>` and paired `**` must restore the protocol line. Emit the startup broadcast before any tool call. Headless, CI logs, receipts, and machine fields stay protocol-only.

Approach this as the design lead at a design studio known for giving every client a distinct visual identity that is not mistaken for anyone else's. This client has already rejected proposals that felt cliché or templated, and is paying for a distinctive point of view: make deliberate, opinionated choices about palette, typography, and layout that are specific to this brief, and take aesthetic risk if justified.

## Ground your designs in the subject matter

If the brief does not identify what the product or subject matter is, identify it yourself before designing, and confirm with the client. You can come up with one concrete subject, the design's audience, and the design's primary job, as a proposal. If there's any information in your memory about the client's preferences or context about what they're building, use that as a hint. The subject's industry, subject matter, materials, and vernacular are where distinctive visual choices come from — a design for a toy for girls aged 8–11 will be very aesthetically different from a dashboard for financial analysts. Build with the brief's real content and subject matter throughout.

## Design principles

For web designs, the hero is the first thing viewers will see. Open with the most characteristic thing in the subject's world, in the form that is most appropriate: a headline, an image, an animation, a live demo, an interactive moment, or other treatments. Be deliberate with your choice: a big number with a small label, supporting stats, and a gradient accent is the default treatment, so only use it if that's truly the best option.

Typography carries the personality of the page. You don't need a different typeface for display or headline text and body content: use one family or two, and if two, make them clearly distinct.

Choose your typefaces deliberately, not the default families you would reach for on any other project, and set a clear type scale following the default guidance of The Elements of Typographic Style with intentional weights, widths, and spacing. When type is used as a headline or visual element, use the type treatment itself as an active part of the design, not a neutral delivery vehicle for the content.

Default to line lengths of less than 80 characters. Serif typefaces can have slightly longer line lengths; give serif body text slightly more line-height than a sans-serif.

Avoid these default typographic treatments; they are the commonest tells of a generated page:
- Accenting just a single word or phrase in a headline, like putting one word in italic/bold or a different color.
- Using all caps for labels.
- Adding unnecessary typographic labels above content.

Visual structure is information. Structural devices like outlines, borders, numbering, eyebrows, dividers, labels, etc., encode useful information about the content rather than decorate it. Many generic designs use numbered markers (01 / 02 / 03), but that's only appropriate if the content actually is a sequence — like a stepped process or a timeline. Before adding numbered markers, check the content really is a sequence.

Use non-user-triggered motion sparingly and deliberately, only to draw attention. A single orchestrated moment — one page-load sequence or one reveal — lands better than scattered effects; fade-and-slide-up entrances on each section and hover transitions on every card are the generic default and read as AI-generated. Motion that answers a person's action (opening, expanding, confirming) is welcome when it shows what changed.

Consider written content carefully. Often a design brief may not contain real content, and it's up to you to come up with copy and placeholder content. Copy can make a design feel as templated as the design itself. See the below section on writing for more guidance.

## Process: plan, review against the brief, build, critique

For calibration, AI-generated design right now clusters around some traits:
1. a warm cream background (near #F4F1EA) with a high-contrast serif display and a terracotta or warm-clay accent (often near #D97757 — Anthropic's own Claude-interaction accent, so on a user's brief it reads as a tell);
2. a near-black background with a single bright acid-green or vermilion accent;
3. a broadsheet-style layout with hairline rules, zero border-radius, and dense newspaper-like columns;
4. the SaaS-card kit: content chopped into identical rounded cards, one border-radius on everything regardless of hierarchy, the same soft grey shadow (rgba(0,0,0,.1)) under each, and gradient washes as decoration;
5. template chrome that appears whatever the subject: a tracked-out ALL-CAPS eyebrow label above every heading; meta strings joined with middle dots ('A · B · C'); labels built as 'WORD — fragment' with a spaced em dash; tinted near-black (#0B0B0B, #111) standing in for black; a monospace face for small data labels; a '→' appended to link and button text.

All traits are legitimate for some briefs, but they are defaults rather than choices, and they appear regardless of subject. Where the brief pins down a visual direction, follow it exactly — the brief's own words always win, including when it asks for one of these looks. Where it leaves an axis free, don't spend that freedom on one of these defaults. As with a hired human designer, there's often a careful balance between doing what you're good at and taking each project as a chance to experiment and learn.

Work in two passes. First, brainstorm a short design plan based on the client's design brief: create a compact token system with color, type, layout, and principles.
- Color: describe the core base palette as 4–6 named hex values.
- Type: the typefaces and their roles.
- Layout: a layout concept, using one-sentence prose descriptions and ASCII wireframes to ideate and compare. Include alignment guidance; should the content be left aligned, center aligned, justified?
- Principles: the high-level guidance for what makes this page unique.

Then review that plan against the brief before building: if any part of it reads like the generic default you would produce for any similar page (work through a similar prompt to see if you arrive somewhere similar) rather than a choice made for this specific brief — revise that part, say what you changed and why. Only after you've confirmed the relative uniqueness of your design plan should you start to write the code, following the revised plan.

When writing the code, be careful of structuring your CSS selector specificities. It's easy to generate CSS classes that cancel each other out (especially with a type-based selector like .section and an element-based selector like .cta). This can happen often with padding/margin between sections.

## Restraint and self-critique

Spend your boldness in one place. Let one element be the memorable thing, keep everything around it quiet and disciplined, and cut any decoration that does not serve the brief. Build to a quality floor without announcing it: responsive down to mobile, visible keyboard focus, reduced motion respected, visually accessible, harmonious color palettes. Critique your own work as you build, taking screenshots to review if your environment supports it — a picture is worth 1000 tokens. Consider Chanel's advice: before leaving the house, take a look in the mirror and remove one accessory. Human creatives have memory and always try to do something new, so if you have a space to quickly jot down notes about what you've tried, it can help you in future passes.

## More on writing in design

Words appear in a design for one reason: to make it easier to understand and use. They are design content, not decoration. Bring the same intentionality and minimalism to copywriting that you would bring to spacing and color. Before writing anything, ask what the design needs to say, and how it can best be said to help the person navigate the experience.

Write from the end user's perspective. Name things by what users will understand in simple language, not by how the system is built. A user manages notifications, not webhook config. Describe what something is or does in plain terms rather than selling it. Being specific and legible to new users is always better than being clever.

Use active voice as default. A CTA says exactly what happens when it is used: "Save changes," not "Submit." An action keeps the same name through the whole flow, so the button that says "Publish" produces a toast that says "Published." The vocabulary of an interface is the signposting for someone navigating the product. Cohesion and consistency are how people learn their way around.

Treat failure and emptiness as moments for direction, not mood. Explain what went wrong and how to fix it, in the interface's voice rather than a person's. Errors don't apologize, and they are never vague about what happened. An empty screen is an invitation to act.

Keep the tone conversational: plain verbs, sentence case, no filler, with tone matched to the brand and the audience. Let each written element do exactly one job.

## Azhou boundaries

- The brief's own words always win, including when the brief asks for one of the listed default looks; the wrapper adds no exception to that upstream rule.
- Screenshot self-review and design memory are conditional capabilities (the upstream wording is "if your environment supports it"). When the host lacks them, name the limitation and continue with the prose critique instead of claiming a critique that never ran; see [setup](references/setup.md).
- This package guides visual direction. It does not inject any Azhou visual identity into the user's product; the Azhou anchor lives in this wrapper, the receipt, and provenance only.
- The guidance is advisory input to whatever builds or changes the code. Repository rules, the user's explicit brief, and the host's own constraints outrank it.

## Receipt

The upstream method defines no output contract of its own; this receipt is the hub's single permitted closing block.

```text
schema: super-frontend-design.receipt.v1
status: <passed|failed|hold>
current_truth: <the design direction produced, the brief-review step that ran, and what was delivered>
artifacts: <the token plan, critique notes, or code delivered inline or at written paths>
verification: <what actually ran — screenshot critique, quality-floor checks — or the named limitation>
holds: <none, or the paused item with its fact>
next_action: <one concrete step, or none>
learning_signal: <a design rule, trigger or boundary worth recording, or none>
```

The `verification` line states only checks that actually ran; a skipped screenshot critique is a named limitation and can never back `✅ 验证通过`.
