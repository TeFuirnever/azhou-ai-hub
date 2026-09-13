# autoresearch 具名 unsupported 回据（真实 Apple Silicon 主机，macOS）

> 日期：2026-09-13（Asia/Shanghai）· 环境：本机 macOS（Apple Silicon），Python 3（标准库）· 对象：`skills/autoresearch` 的 prepare 探测契约（issue #219，parent #218）· 上游 pin：`karpathy/autoresearch@228791fb499afffb54b46200aca536f79142f117`
> 隐私口径：只记录探测命令的存在性结果与芯片型号；不记录序列号、磁盘卷名或任何会话内容。

## 探测执行与结果（当日实跑）

| 序 | 命令 | 结果 |
|---|---|---|
| 1 | `nvidia-smi` | not found（exit 1）——NVIDIA CUDA GPU 缺失 |
| 2 | `system_profiler SPDisplaysDataType`（`Chipset Model`/`Metal` 行） | `Chipset Model: Apple M5`；`Metal Support: Metal 4` → 检测到 Apple Silicon |
| 3 | `rocm-smi` / `amd-smi` / `xpu-smi` | 均 not found |
| 4 | `uv --version` | uv 0.11.14（aarch64-apple-darwin）在场 |

## 具名 hold

按 `skills/autoresearch/references/setup.md` 的 named unsupported probe，本机 prepare 记录：

```text
unsupported: detected apple-silicon accelerator; upstream supports NVIDIA CUDA only
```

fail-closed 边界不变：不启动任何训练或 CPU fallback 运行；hold 不升级为 ready。

## 结论

T1 的具名探测级联在真实目标主机（恰好是维护者日常主机）上验证：无 NVIDIA 工具时能给出对用户有用的失败原因。support matrix 的 "other GPUs are unverified" 措辞不变——本回据只证明失败报告升级，不构成任何非 NVIDIA 平台支持声明。
