# Brand compliance receipt — live skill sessions — 2026-10-22

This receipt records a redacted real-host check that representative Azhou skills emit brand startup and stage anchors under the paren-field grammar shipped in PR #324 (`6ae1f87`), and that consumer-side validators reject grammar-violating emissions. It contains no raw transcript, user identity, or account data.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `6ae1f87d9c7fe6fb552114cc9c273b6899a512a0` (brand-layer v2 merge)
- Host: macOS arm64, Claude Code `2.1.307`, headless `claude -p --output-format json` sessions in the repository worktree
- Validators: `scripts/check_repository.py` (`SKILL_BRAND_CONTRACTS`), `skills/super-repo-pedant/scripts/validate_execution_protocol.py`, `skills/excalidraw-diagram/scripts/check-brand-startup.py`
- Mode: attempt-1 per skill; assistant-emitted broadcast lines only; SKILL.md contract examples and hook/api-request injected bytes excluded from live counts

## Pre-declared thresholds

| Metric | Threshold |
|---|---|
| Startup-line compliance | ≥95% |
| Success / fail / hold (and scored stage) anchors | 100% |

## Results

| Check | Result | Evidence |
|---|---|---|
| `azhou-info` startup + success anchors | `PASS` | Live startup `🦊 阿舟 · Azhou Info 启动（mode=info, scope=checkout）` and `✅ 验证通过（mode=info, scope=checkout）` match foundation brand protocol. |
| `super-repo-pedant` multi-stage anchors | `PASS` | Startup with concrete path scope; `🧭 范围锁定` / `🗂️ 清单完成` / `🕸️ 影响确认` / `🧹 同步完成` fullmatch `MESSAGE_PATTERNS`; hold `🔒 阿舟暂停这一项` emitted instead of unearned `✅`. |
| `super-llm-wiki` multi-stage anchors | `PASS` | Startup `operation=list` with concrete repo scope; `🧭 知识范围锁定` and `🔎 Wiki 检索完成` in paren-field grammar; empty store did not invent success. |
| `eli5` startup line | `FAIL` | Emitted `🦊 阿舟 · 舟5 启动（mode=explain，scope=…）` — display name `舟5` ≠ `Eli5`, full-width `，` used as field separator. Hold anchor itself valid. |
| Startup-line rate vs threshold | **FAIL (75% = 3/4)** | Below pre-declared ≥95%. |
| Success/fail/hold + scored stage anchors vs threshold | **PASS (100% = 9/9)** | Meets 100% pre-declared threshold. |
| Adversarial consumer rejection | **PASS (11/11)** | Value-internal delimiters, mixed pipe/paren grammar, and template leakage all rejected; zero misses. See `brand-effect-audit-2026-10-22/adversarial-probes.json`. |
| Render matrix (plain / Markdown / no-Unicode) | `PASS` | Same anchors rendered three ways; no-Unicode strip preserves `（k=v, k=v）` and fixed labels; token counts recorded in `render/render-matrix.json`. |

## Aggregate numbers

```text
startup_emitted:           4
startup_compliant:         3
startup_compliance_rate:   0.75   (threshold ≥0.95 → NOT MET)
anchors_scored:            9
anchors_compliant:         9
anchor_compliance_rate:    1.00   (threshold 1.00 → MET)
adversarial_rejected:      11 / 11
adversarial_missed:        0
```

Machine-readable score: `evidence/brand-effect-audit-2026-10-22/brand-compliance-score.json`.

## Defects (recorded only; not fixed in this task)

1. **DEFECT-A** — `eli5` live startup line violates display-name and field-separator discipline (see score JSON `sessions.eli5.startup`).
2. **DEFECT-B** — Codex-side Hindsight `systemMessage` bank line visibility not captured in transcript; not an Azhou skill defect.

## Claim boundary

This proves on this machine, at commit `6ae1f87`, in four Claude Code headless sessions: three of four startups were contract-compliant; every scored success/fail/hold/stage anchor that was emitted matched the fixed grammar; and the repository consumer validators reject the recorded adversarial emissions. It does not prove interactive TUI behavior, other harnesses for Azhou skills, long-run compliance rates, memory-credit emission when a memory actually contributes (no live credit sample this run), or Codex-visible Hindsight banner parity. Raw JSONL stays Git-external; digests only are in-repo. Nothing private is committed.
