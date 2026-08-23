# Excalidraw Diagram

`excalidraw-diagram` turns natural-language workflows, architectures, and concepts into editable `.excalidraw` scenes, then renders and validates them before delivery.

## Runtime package

The installable package is [`skills/excalidraw-diagram/`](../skills/excalidraw-diagram/SKILL.md). It contains only runtime instructions, references, scripts, vendored libraries, fonts, and renderer assets.

It intentionally contains no OpenAI-specific metadata and no benchmark prompts, assertions, fixtures, or expected answers. Codex, Claude, zcode, and other compatible harnesses use the same package.

Install it with a compatible skills manager:

```bash
npx skills add TeFuirnever/azhou-ai-hub --skill excalidraw-diagram
```

For manual installation, copy the whole runtime directory to the harness's skill location without copying repository-level `benchmarks/`. Repository contributors may instead symlink `skills/excalidraw-diagram/` under the canonical name `excalidraw-diagram`; do not use a model-specific package variant.

## Dependencies

Read [`references/setup.md`](../skills/excalidraw-diagram/references/setup.md) before first render. It provides:

- harness-neutral path variables;
- dry-run previews before `uv sync` and `npm ci`;
- pinned Python and Node installation commands;
- Chromium, offline asset, and script smoke checks;
- dependency-upgrade verification boundaries.

No installation command modifies agent configuration or imports browser credentials.

## Evaluation and evolution

The development-only suite lives at [`benchmarks/excalidraw-diagram/`](../benchmarks/excalidraw-diagram/README.md). Ordinary-model results require semantic, deterministic, and identified visual-review gates on a frozen attempt-1 artifact.

Compare harnesses or skill revisions with identical prompts, runtime package trees, time limits, and tool access. Keep raw private runs outside Git; commit only synthetic cases, aggregate receipts, failure mechanisms, paired decisions, and known limitations. Promotion remains a human checkpoint.

Interactive runs use the [`阿舟品牌层`](../skills/excalidraw-diagram/references/brand-layer.md): fixed factual stage anchors and an `excalidraw-diagram.receipt.v1` that separates deliverables, automated gates, identified visual review, holds, and learning signals. Cross-harness history intake follows [`history-evolution.md`](../skills/excalidraw-diagram/references/history-evolution.md); candidate promotion follows the [`evolution contract`](../skills/excalidraw-diagram/references/evolution-contract.md).

## Provenance

The maintained Azhou workflow uses MIT-licensed Agents365 and official Excalidraw code/assets. Public no-license prior art is excluded from redistribution. Exact bundled versions, boundaries and notices live in [`references/provenance.md`](../skills/excalidraw-diagram/references/provenance.md) and [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
