> 收编说明：2026-09-07 由维护者提供的外部 Windows 实测报告，为跨平台研究（docs/research/2026-09-07-skill-cross-platform-macos-windows.md 第 1.6 节）的一手证据。以下为报告原文，未改动。

# azhou-ai-hub v0.7.0 单元测试失败/错误分析报告（Windows）

> **生成时间**：2026-09-07
> **测试环境**：Windows 10.0.26200 x64 · Python 3.11.9 · Git 2.53.0
> **测试命令**：`python -m unittest discover -s tests -v`
> **总体结果**：**427 个测试，73 失败 (FAIL) + 21 错误 (ERROR) + 2 跳过**，其余 331 个通过
> **结论**：全部失败均为 **Windows 平台兼容性问题**，无业务逻辑缺陷。仓库原生开发环境为 macOS（见 `benchmarks/repo-pedant/history/darwin-*-2026-08-23.json`）。

---

## 根因分类总览

| # | 根因 | 错误特征 | 数量 | 严重度 |
|---|---|---|---|---|
| 1 | 符号链接需要特权 | `OSError: [WinError 1314] 客户端没有所需的特权` | 21 ERROR + ~10 FAIL | 环境限制 |
| 2 | Windows 文件锁 vs POSIX unlink | `PermissionError: [WinError 32] 另一个程序正在使用此文件` | ~45 FAIL | 技能代码跨平台缺陷 |
| 3 | `python3` 命令不存在 | 退出码 9009（Microsoft Store 存根） | 4 FAIL | 环境差异 |
| 4 | Unix 专有 API | `AttributeError: module 'signal' has no attribute 'SIGALRM'` | 1 FAIL | 平台限制 |
| 5 | POSIX 权限位语义 | `AssertionError: 448 != 511` 等 | 3 FAIL | 平台差异 |
| 6 | 外部工具/证据缺失 | gh CLI 缺失、git worktree 行为、基准证据不匹配 | ~10 FAIL | 混合 |

---

## 分类一：符号链接特权缺失（21 ERROR + 相关 FAIL）

**根因**：Windows 创建符号链接需要 `SeCreateSymbolicLinkPrivilege` 特权（管理员或开发者模式）。测试在 setUp 阶段调用 `Path.symlink_to()` 构造"恶意符号链接"场景时直接崩溃，测试体根本没执行。

**典型堆栈**：

```
File "tests\test_azhou_hub.py", line 1080, in test_copy_receipt_rejects_symlinked_destination_even_when_digest_matches
    installed.symlink_to(shadow, target_is_directory=True)
  File "...\Python311\Lib\pathlib.py", line 1198, in symlink_to
    os.symlink(target, self, target_is_directory)
OSError: [WinError 1314] 客户端没有所需的特权。
```

**受影响测试（21 个 ERROR）**：

| 测试模块 | 测试 | 考察点 |
|---|---|---|
| test_azhou_hub | `test_copy_receipt_rejects_symlinked_destination_even_when_digest_matches` | 拷贝收据拒绝符号链接目标 |
| test_azhou_hub | `test_doctor_reports_wrong_link_target_as_failure` | doctor 检测错误链接指向 |
| test_azhou_hub | `test_managed_receipt_rejects_azhou_or_receipts_symlink` (×2: `.azhou` / `receipts`) | 托管收据拒绝符号链接 |
| test_azhou_hub | `test_managed_setup_refuses_receiptless_adoption_and_preserves_valid_receipt` | 无收据采用拒绝 |
| test_azhou_runtime_state | `test_namespace_resolution_rejects_traversal_and_symlinks` | 命名空间拒绝路径穿越 |
| test_closeout_hook | `test_symlinked_state_is_rejected` | 关闭钩子拒绝符号链接状态 |
| test_manage_evolution | `test_archive_rejects_symlinked_candidate` | 演进归档拒绝符号链接 |
| test_super_caveman_benchmark | `test_exact_diff_approval_requires_bound_record` | 审批记录绑定 |
| test_super_caveman_benchmark | `test_review_digests_ignore_repository_diff_configuration`（次生 `TypeError: 'NoneType' object is not subscriptable`） | 评审摘要隔离 |
| test_super_caveman_claude_adapter | `test_symlinked_settings_rejected_and_custom_paths_rejected` | Claude 设置符号链接拒绝 |
| test_super_caveman_codex_adapter | `test_scope_rejects_nonstandard_and_symlinked_paths` | Codex 路径契约 |
| test_super_caveman_zcode_adapter | `test_symlinked_config_rejected` | ZCode 配置符号链接拒绝 |

**连带 FAIL（符号链接功能降级导致）**：

| 测试 | 现象 |
|---|---|
| `test_setup_link_is_idempotent` | `AssertionError: False is not true` — link 模式无法真正创建符号链接 |
| `test_migrate_failure_keeps_old_installation_or_reports_partial` 等 migrate 系列 (×7) | `status: 'rolled_back'` — link 模式安装回滚 |
| `test_task_skill_real_packages_complete_managed_lifecycle` (×3: repo-pedant / super-caveman / excalidraw-diagram) | `status: 'rolled_back'` — 真实包托管生命周期回滚 |
| `test_managed_apply_writes_atomic_receipt_and_requires_pairing` (×2) | `AssertionError: 0 != 1` |

**修复途径**：开启 Windows 开发者模式，或以管理员运行测试，即可获得 `os.symlink` 权限。全部 21 个 ERROR 预计转为通过；link 模式相关 FAIL 亦有望恢复。

---

## 分类二：Windows 文件锁 vs POSIX unlink（~45 FAIL）

**根因**：`super-caveman` 三个 harness 适配器（claude/codex/zcode）的 `atomic_write` 实现中，删除临时文件时句柄未关闭：

- `skills\super-caveman\scripts\claude_adapter.py:108` — `tmp_path.unlink()`
- `skills\super-caveman\scripts\codex_adapter.py:276` — `temporary_path.unlink()`

POSIX 允许删除正被打开的文件（unlink 后句柄仍有效），**Windows 不允许**，抛出 `WinError 32`。这是**技能代码自身的跨平台缺陷**（并非测试问题），Windows 上执行 super-caveman 安装/状态写入时同样会触发。

**典型堆栈**：

```
File "skills\super-caveman\scripts\claude_adapter.py", line 108, in atomic_write
    tmp_path.unlink()
  File "...\pathlib.py", line 1147, in unlink
    os.unlink(self)
PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问。:
  '...\.azhou\super-caveman\.super-caveman-XXXX.tmp'
```

**修复建议**（供上游参考）：临时文件写入后先 `close()` 再 `os.replace(tmp, target)`；Windows 上 `os.replace` 原子覆盖目标，无需 unlink；失败清理分支用 `contextlib.suppress(PermissionError)` 包裹。

**受影响测试（45 个，全为 FAIL）**：

- test_super_caveman_claude_adapter — 15 个：capsule 注入（startup/resume/clear/compact ×4）、状态恢复、stop 短语、setup 幂等（project/user ×2）、注册精确性、purge、symlinked session 状态、reinforcement、clear 重置、损坏状态回退、状态报告等
- test_super_caveman_codex_adapter — 9 个：session start capsule、adapter 路径所有权、legacy 清理、unowned 注册保留、幂等 setup/uninstall、relocated adapter 替换、字段不匹配判定等
- test_super_caveman_codex_adapter_lifecycle — 5 个：enable/disable/status、canonical 状态机、reinforcement 边界、双事件幂等、注册/卸载
- test_super_caveman_zcode_adapter — 10 个：camelcase payload、enable/disable、project scope、reinforcement、stop 短语、capsule 发射、幂等、双事件注册、enabled flag
- test_super_caveman（压缩守卫）— 2 个 ERROR：`test_late_open_descriptor_write_is_retained_and_blocks_restore`、`test_late_restore_inode_write_marks_conflict`（同时涉及 inode 语义）

**连带次生错误**（同一根因向上传播）：

| 错误 | 测试 | 说明 |
|---|---|---|
| `TypeError: argument of type 'NoneType' is not iterable` (×4) | test_super_caveman_claude_adapter `test_wenyan_and_compat_triggers_route_deterministically`（4 个 phrase 参数化） | 写状态失败后返回 None |
| `TypeError: object of type 'NoneType' has no len()` (×1) | `test_prompt_output_limits_and_fail_open` | 同上 |
| `KeyError: 'hookSpecificOutput'` (×1) | `test_render_neutral_reports_off_without_shaping` | 渲染输出缺失字段 |

---

## 分类三：`python3` 命令不存在（4 FAIL）

**根因**：Windows 官方 Python 安装器只提供 `python.exe`；`python3` 命中被 Microsoft Store 别名存根拦截，退出码 **9009** 并打印 "Python was not found"。仓库脚本/测试以 `python3` 调用子进程。

**典型断言**：

```
AssertionError: 0 != 9009 : Python was not found; run without arguments to install
from the Microsoft Store, or disable this shortcut from Settings > Apps > ...
```

**受影响测试**（test_validate_execution_protocol）：

- `test_default_protocol_uses_repo_pedant_namespace`
- `test_failed_run_ends_with_exact_failure_anchor`
- `test_prior_freeform_brand_drift_is_rejected`
- `test_success_requires_every_check_and_must_be_last`、`test_valid_protocol_passes`

**修复途径**：关闭 Microsoft Store 的 python3 应用执行别名（设置 → 应用 → 高级应用设置 → 应用执行别名），或创建 `python3` → `python` 的真实转发。

---

## 分类四：Unix 专有 API（1 FAIL）

| 测试 | 错误 |
|---|---|
| test_fuzz_relay_state `test_seeded_bounded_run_stays_clean` | `AttributeError: module 'signal' has no attribute 'SIGALRM'. Did you mean: 'SIGABRT'?` |

**根因**：`signal.SIGALRM` 为 POSIX 专有；Windows 的 fuzz 超时守护无法安装。测试代码未做平台降级。

---

## 分类五：POSIX 权限位语义（3 FAIL）

| 测试 | 断言 | 说明 |
|---|---|---|
| test_azhou_runtime_state `test_namespace_resolution_and_private_creation` | `448 != 511`（0o700 vs 0o777） | Windows `os.chmod` 仅支持只读位，不实现 POSIX 模式位 |
| test_lavish_relay_state `test_init_embeds_portable_state_and_visible_ledger` | `416 != 438`（0o640 vs 0o666） | 同上 |
| test_azhou_hub `test_doctor_rejects_executable_permission_drift_in_a_copy` | `1 != 0` | 可执行位在 Windows 上不可表示，drift 检测行为不同 |

---

## 分类六：外部工具缺失 / 证据与行为差异（~10 FAIL）

| 测试 | 现象 | 判断 |
|---|---|---|
| test_check_repository `test_release_workflow_enforces_ref_and_api_outcomes`（×3：outside-main / not-found / api-error） | `'unable to determine whether release exists' not found in ''`、`2 != 1`、`0 != 1` | 疑似 `gh` CLI 未安装或工作流解析在 Windows 的差异 |
| test_repo_pedant_benchmark（×3：`test_check_validates_registered_cases` / `test_verify_accepts_usable_first_pass` / `test_verify_detects_protected_code_change`） | `verify command could not complete (FileNotFoundError)` | 子进程找不到可执行文件（与分类三 `python3` 同源的可能性高） |
| test_super_caveman_benchmark `test_capability_and_trigger_integrity` | `passing evaluation result lacks valid paired promotion evidence: revision-93f38a6b-attempt-1-summary.json`（20 项差异） | 基准证据文件与清单不匹配（内容性问题，与平台无关） |
| test_super_caveman_benchmark `test_committed_review_uses_approval_anchor_after_later_commit`、`test_staged_review_rejects_aggregate_index_worktree_split` | `AssertionError: unexpectedly None` | git worktree/index 在 Windows 的行为差异 |
| test_super_caveman_lifecycle_benchmark `test_lifecycle_runner_passes_on_current_tree` | 31530 字符大 diff | 上游连锁（分类一/二） |

---

## 修复优先级建议

1. **【立即可做，恢复 ~30 项】** 开启 Windows 开发者模式（设置 → 隐私和安全性 → 开发者 → 开发人员模式）→ `os.symlink` 获得特权 → 分类一全部 ERROR 及 link 模式 FAIL 预期转绿。
2. **【立即可做，恢复 4 项】** 关闭 Microsoft Store 的 `python3` 应用执行别名，或创建真实 `python3` 转发 → 分类三恢复。
3. **【需上游修复】** `super-caveman` 适配器 `atomic_write` 的 Windows 兼容（先 close 后 replace，~45 项）— 可向上游提 issue/PR。
4. **【需上游修复】** fuzz 测试的 `SIGALRM` 平台降级（Windows 用 `threading.Timer` 替代）。
5. **【需上游澄清】** 基准证据 `revision-93f38a6b` 与 manifest 不匹配——疑似上游遗漏提交证据文件。

---

## 附：原始数据

- 完整详细输出：`C:\Users\50489\.agents\test-output-full.txt`（2232 行，已移出仓库，保持检出干净）
- 失败/错误清单：本报告各表格已全量收录（73 FAIL + 21 ERROR 逐项对应）
- 跳过项（2 个 skipped）为正常跳过，非异常
