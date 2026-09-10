# Research: zcode 会话存储格式实测（session-insights #162）

> 日期：2026-09-10（Asia/Shanghai）
> 性质：只读结构侦察——目录布局、文件命名、记录类型分类与顶层字段名；**未读取任何会话正文**，路径均已脱敏为模式。
> 对象版本：ZCode.app **3.11.2**（macOS，`CFBundleShortVersionString`）+ 其 CLI 存储 `~/.zcode/`。其他平台/版本未验证。
> 用途：session-insights 的 zcode 适配器（M3 前置，issue #161 spec §Implementation Decisions 要求"未验证前 fail closed"）。

## 结论（go/no-go）

**原生 zcode 会话转写：no-go（fail closed）。** 本机 3.11.2 上不存在明文、稳定、逐轮次的原生会话转写存储：任务元数据在 sqlite，模型调用日志是请求/响应级而非会话级，桌面端状态在 Electron IndexedDB（非文本、无稳定合同）。适配器应如实返回 `unsupported` 并进 holds（spec user story 8）。

**导入的 Claude 会话：可解析但与 Claude Code 适配器冗余。** `v2/sessions` 下的 `claude-import-*` 是 Claude 会话的迁移副本，格式简单可解析；但同源内容应归 Claude Code 适配器直读 `~/.claude/projects/` 覆盖，zcode 适配器读导入副本会重复计数（spec 硬边界 4：同源比较）。

## 实测布局（`~/.zcode/`，3.11.2）

| 路径 | 内容 | 结构事实 |
|---|---|---|
| `v2/sessions/<workspace-hash>/claude-import-<hex24>.json` ×19 | Claude 导入会话 | 顶层 `{"meta", "messages"}`；`messages[]` 键 = `content, role, timestamp, turnIndex`（无 `type` 字段）；`role` ∈ {user, assistant}（实测 232/201）；`timestamp` 为整数（epoch 风格）；`meta` 键 = `createdAt, migrationSource, status, taskId, title, traceId, updatedAt, workspacePath` |
| `v2/tasks-index.sqlite` | 任务元数据索引（197 行 tasks） | 表：`tasks, task_groups, task_group_members, task_group_view_node_orders, task_group_workspace_bootstraps, automations, automation_runs, off_peak_tasks`；`tasks` 主键 `(workspace_key, task_id)`，`task_id` 形如 `sess_<uuid>`，列含 `title, task_status, provider, mode, model, created_at, updated_at, meta_json, searchable_text` 等——**无转写正文列** |
| `v2/checkpoints/<hash>/state.json` ×13 | 上传/同步状态 | 键 = `workspacePath, workspaceKey, lastCompressedSize, failureCount, lastAcceptedManifestHash, lastAcceptedManifestPath, activeUpload, pendingUpload`——非转写 |
| `cli/rollout/model-io-sess_<uuid>.jsonl` ×3 | 模型调用 I/O 日志 | 逐行 JSON，键 = `attempt, completedAt, durationMs, model, querySource, request, requestId, response, sessionId, startedAt, traceId, turnId, type`；`request`/`response` 为完整载荷——请求级而非会话轮次级，且体量重 |
| `cli/artifacts/sess_<uuid>/call_<hex>-tool-result-<uuid>.json` | 单次工具调用产物 | 按会话分目录，每调用一文件 |
| `cli/exec/sess_<uuid>/` ×695 | 执行工作目录 | 全部为空目录 |
| `cli/log/zcode-YYYY-MM-DD.jsonl` | 应用日志（按日） | 非会话转写 |
| `cli/db.sqlite` | 结构探测无表（可能锁/空） | 不作为来源 |
| `~/Library/Application Support/ZCode/` | Electron 运行时（IndexedDB、Cache、Session Storage 等） | 非文本存储，无稳定合同，不读 |

## 对 spec 的修正建议

- spec 假设 zcode 适配器读 `~/.zcode/v2/sessions`——该路径真实存在，但当前版本只装 Claude 导入副本，不是原生 zcode 转写。
- zcode 适配器维持 fail-closed `unsupported` 是**当前正确实现**，不是缺口；待 zcode 提供转写导出或文档化存储格式后再议。
- `claude-import-*` 副本不进 zcode 适配器范围；如要覆盖，应在 Claude Code 适配器侧以 `migrationSource` 去重（本仓 spec 边界 4 同源比较已隐含）。

## 方法与边界

- 只读：`find/ls/sqlite3 .schema/Python json 键集合`，未 `SELECT` 任何内容行，未读取 `messages[].content`、`request/response` 载荷或 `workspacePath` 明文值。
- 单机器单版本（macOS + ZCode 3.11.2）；Windows/Linux 或其他版本的 zcode 存储未验证。
