# Autoresearch package load and fail-closed boundary receipt — Codex — 2026-09-04

This receipt records a redacted real-host check that the Codex CLI host loads the linked `autoresearch` package and that its documented `mode=prepare` environment checks fail closed on a host without an NVIDIA GPU. It contains no temporary path, user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `7d16d6da321745b0fec8657c85d8b226e7755e12` (the linked user-scope package resolves to this content)
- Host: macOS (Apple Silicon, no NVIDIA GPU), Codex CLI `codex-cli 0.152.0`, model `gpt-5.6-sol` (reasoning effort `xhigh`)
- Mode: headless `codex exec` run in an empty disposable Git-initialized working directory, user-scope Agent Skills root, attempt-1

## Results

| Check | Result | Evidence |
|---|---|---|
| Package load | `PASS` | The headless run resolved `autoresearch` from the user-scope linked root and executed its documented `mode=prepare` checks. |
| Prepare check: uv present | `PASS` | `uv` found on PATH in the run. |
| Prepare check: NVIDIA CUDA GPU visible | `FAIL` (documented fail-closed point) | `nvidia-smi` returned exit code `127` (command not found); the host GPU is Apple Silicon — no NVIDIA CUDA device. |
| Prepare check: user-owned pinned checkout | `NOT RUN` (boundary) | The fail-first rule stopped preparation at the CUDA check; nothing was cloned or scanned, matching the documented contract. |
| Fail-closed behavior | `PASS` | The run stopped at the missing CUDA check, reported no ready state, and closed with the skill's `autoresearch.receipt.v1` stable receipt, `status: fail`. |

## Claim boundary

This proves the Codex CLI host loads the linked `autoresearch` package and that its safety boundary behaves exactly as documented on a CUDA-less host: preparation fails closed instead of degrading. It does not prove a training run, GPU-path behavior, or cross-host parity; a positive full-path receipt requires an NVIDIA GPU machine and remains unclaimed. Raw outputs stay Git-external; nothing private is committed.
