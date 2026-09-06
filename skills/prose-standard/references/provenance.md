# Provenance

## Source of the adapted material

Three upstream capabilities from one repository, merged into one package because this repository's package rule forbids sibling-directory dependencies and because their trigger surfaces overlap (two always-loaded model-invoked descriptions with overlapping branches trade invocation predictability):

1. **Editorial standard and coverage matrix** — https://github.com/deepseek-ai/deepseek-harness (MIT), commit `0a53fb55bea101816fa226bb964ae2bed71c343b`, `.agents/skills/dsh-prose-standard/SKILL.md`: complete-proposition rule and required-coverage-by-location.
2. **Chain-of-thought leakage taxonomy, keep-list, and recall batteries** — same pin, `.agents/skills/dsh-trim-cot-leakage/SKILL.md` and its `references/` (recall-batteries.md, examples.md).
3. **Fact-check procedure** — same pin, the documentation standard's "Fact-check procedure: test, do not assume" section in `.agents/skills/dsh-doc/SKILL.md`.

## Capability baseline and adaptation boundary

- The complete-proposition rule, the coverage matrix (re-expressed for this repository's surface vocabulary: entries, references, benchmarks, receipts), the eight-class taxonomy, the keep-list, the battery calibration philosophy (over-match by design, semantic judgment required, known-positive and near-miss-negative calibration), and the run-it-or-delete-it fact-check procedure are preserved. Deliberately not ported from the upstream editorial standard: the terms-to-check vocabulary rule, the borderline-decision protocol, and the emphasis-preservation detail — this repository's standard of record already governs those; the upstream overcorrection traps are folded into the taxonomy workflow instead.
- The recall batteries are ported from ripgrep one-liners to a deterministic standard-library Python probe (`scripts/recall_batteries.py`); probe families cover citations, vantage, change narration, indexical stamps, review choreography, hedges, draft-section markers, and Chinese change-narration stamps in Chinese-mirror surfaces. The upstream's Chinese-residue-in-English-code probes (TypeScript/JSDoc-specific) are not ported; this repository's primary prose language differs.
- Upstream-specific surfaces are re-pointed: vendor/ and archived Agent Notes exclusions become runtime-state and frozen-archive exclusions; upstream gate names become this repository's verification gate.
- The batteries' known false-positive families (instrumental "used to", runtime old/new, "PR" in process documentation, protocol version identifiers, §-citations with committed owners, and review-process nouns like 评审 in Chinese-mirror surfaces) are folded into the keep-list and the pinned keep corpus.
- MIT notice: the upstream repository is MIT-licensed; the retained methodology is re-expressed, and the upstream license and this notice satisfy the attribution requirement. The upstream license text is available at the pinned commit (`LICENSE`).

## Reproducible update path

1. Diff the pinned upstream skills against the current pin (the two SKILL.md files, trim-cot-leakage's references, and dsh-doc's fact-check section).
2. Map every methodology change onto this package's entry and references; keep probe patterns in sync with the taxonomy section by section.
3. Update the pin above only after the mapped change lands, in the same commit.
