# Execution protocol

Repo Pedant 的交互阶段是可验证协议，不是自由文案。运行时 record 默认写到受影响项目的 `.azhou/repo-pedant/execution.json`；schema 为 `repo-pedant.execution.v1`，机器定义见 `../assets/execution-protocol.schema.json`。

## 固定顺序

1. `start`
2. `scope`
3. `inventory`
4. `impact`
5. `sync`
6. `verify_failure` 或 `verify_success`

前五个阶段必须各出现一次并保持顺序。失败事件可在修复与重跑过程中保留；成功事件只能出现一次，必须是最后事件。

## 固定检查

`checks` 至少包含 `inventory`、`readback`、`tests`、`links`、`diff`、`coverage`。每项记录：

- `passed`：`evidence` 写精确命令、artifact 或读回事实；
- `not_applicable`：同时写 `reason` 和替代 evidence；
- `failed`：evidence 写失败事实，run 的 `result` 必须为 `failed`。

`verify_success.completed_checks` 必须与声明的 check id 全量、同序一致。成功消息中的逗号列表也必须完全一致。

## 验证时点

先完成所有检查，再把准备发送的成功事件写进 record。运行：

```bash
python3 <skill-dir>/scripts/validate_execution_protocol.py \
  /absolute/project/.azhou/repo-pedant/execution.json
```

退出码 `0` 后原样发送 record 里的成功消息，不再执行工具或修改文件。退出码 `1` 时发送确定性失败锚点，修复后重跑相关检查并重新验证 record。JSON schema 约束形状；脚本额外约束顺序、固定文案、check 完整性和成功时点。

开发期正反例位于仓库级 `benchmarks/repo-pedant/protocol/`，不随安装包复制。
