# Autoresearch package load and fail-closed boundary receipt — zcode — 2026-09-03

This receipt records a redacted real-host check that the zcode host loads the linked `autoresearch` package and that its documented `mode=prepare` environment checks fail closed on a host without an NVIDIA GPU. It contains no user identity, account data or raw transcript.

## Tested source

- Repository: `TeFuirnever/azhou-ai-hub`
- Local default-branch commit: `cb8a26efe8cee76eea850a256599c6d2bd2b0bf4` (the linked user-scope package resolves to this content)
- Host: macOS (Apple Silicon, Apple M5 GPU), zcode GUI app session (interactive; user-scope Agent Skills root)
- Mode: interactive GUI session; package loaded from the linked install and its documented `mode=prepare` environment checks executed in the host session, attempt-1

## Install step

Same Foundation CLI linked install as the eli5 receipt of this date (`--plan-id 8d64ab4ad4a26f348e9e1c767d771f8dcb32bd5cad0a15de6cb600149273d7fd`, apply exit `0`); `autoresearch` had no prior user-scope install and was linked new.

## Results

| Check | Result | Evidence |
|---|---|---|
| Package load | `PASS` | The linked package resolves; SKILL.md carries the frontmatter, the `🦊 阿舟 · Autoresearch` identity anchor, brand protocol and the setup/provenance references. |
| Prepare check: uv present | `PASS` | `uv 0.11.14 (aarch64-apple-darwin)` on PATH. |
| Prepare check: NVIDIA CUDA GPU visible | `FAIL` (documented fail-closed point) | `nvidia-smi` absent; `system_profiler` reports the host GPU as Apple M5 — no NVIDIA CUDA device. |
| Prepare check: user-owned pinned checkout | `NOT RUN` (boundary) | The contract requires a user-supplied checkout path pinned to the recorded upstream commit; none was supplied, so the check correctly refused to scan or clone anything. |
| Fail-closed behavior | `PASS` | Per SKILL.md "Every missing check fails closed; no partial state is reported as ready": `mode=prepare` stopped at the missing CUDA check and reported no ready state. |

## Claim boundary

This proves the zcode GUI host loads the linked `autoresearch` package and that its safety boundary behaves exactly as documented on a CUDA-less host: preparation fails closed instead of degrading. It does not prove a training run, GPU-path behavior, or cross-host parity; a positive full-path receipt requires an NVIDIA GPU machine and remains unclaimed. Raw outputs stay Git-external; nothing private is committed.
