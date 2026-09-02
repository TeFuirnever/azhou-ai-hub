# Setup and external dependency boundary

All upstream dependencies are external. This package ships no upstream code; it drives a user-owned checkout of [karpathy/autoresearch](https://github.com/karpathy/autoresearch) pinned at commit `228791fb499afffb54b46200aca536f79142f117`.

## Minimum environment

| Requirement | Check | Failure boundary |
|---|---|---|
| NVIDIA CUDA GPU; the upstream README documents a single-GPU setup tested on H100, and other GPUs are unverified | `nvidia-smi` | fail closed with `❌ 验证失败`; do not start a CPU fallback run |
| `uv` package manager | `uv --version` | fail closed; do not install implicitly |
| Pinned upstream checkout | `git -C <checkout> rev-parse HEAD` equals `228791fb499afffb54b46200aca536f79142f117` | fail closed; request the pin, never advance or rewrite the user's checkout |

## Locate and verify the source

```bash
git -C <checkout> remote get-url origin
git -C <checkout> rev-parse HEAD
```

The remote must be the upstream repository and the head must equal the pin. If the user has no checkout, print the clone command and stop; acquire the checkout only when the user runs it or explicitly delegates it. The upstream repository publishes no `LICENSE` file, so this repository never vendors its files; see [provenance](provenance.md).

## Install and verify

```bash
git -C <checkout> checkout 228791fb499afffb54b46200aca536f79142f117
cd <checkout> && uv sync --locked
```

Run the pin command only on a freshly cloned checkout, or after the user explicitly confirms moving an existing checkout's head to the pin.

Upstream documents the remaining steps in its README; treat durations and download sizes as upstream claims, not verified facts:

1. `uv run prepare.py` performs the one-time data download and tokenizer training. Hold with `🔒 阿舟暂停这一项` on metered connections or shared machines before the download starts.
2. `uv run train.py` performs a single baseline experiment. The environment is ready only when this run completes and prints its validation metric; record that output as part of the receipt's verification.

## System modification boundary

Every write stays inside the user checkout, the uv cache, and the upstream data cache at `~/.cache/autoresearch/`, which the upstream `prepare.py` creates outside the checkout. This skill does not install hooks, edit shell profiles, change global configuration, or move artifacts into any Git repository. Verification is complete only when every check above has run and been read back; skipped checks are reported as holds, never as readiness.
