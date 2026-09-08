# Windows CI 实测收据（win-05）

> 日期：2026-09-08（Asia/Shanghai）· 环境：GitHub Actions `windows-latest`（Windows Server、管理员权限、Python 3.11.9、Git for Windows）· 命令：`python scripts/verify.py`（PR #172 的 `Verify on Windows (experimental evidence)` job，continue-on-error 证据采集）

## 两轮对照

| 轮次 | 环境 | 结果 |
|---|---|---|
| Run 1 | 默认 locale（cp1252） | 435 测试：52 FAIL + 15 ERROR + 2 skip |
| Run 2 | `PYTHONUTF8=1`（文档声明前提） | 435 测试：51 FAIL + 9 ERROR + 2 skip；**7 项编码集群精准转绿，零新增失败** |

## PYTHONUTF8 修复的 7 项（编码集群，跨 4 模块）

- excalidraw 品牌启动测试 ×4（subprocess stdin 写 🦊，cp1252 无法编码 U+1F98A）
- llm-wiki CJK slug/bigram 确定性 ×1；prose-standard leakage fixture ×1；validate_execution_protocol 品牌漂移 ×1

## 剩余 50 项的唯一根因分簇

- **super-caveman 集群 44 项**（adapter ×47 计数去重后 44 唯一名 + benchmark 级联）：39 项 trace 含 PermissionError（WinError 32）——与 win-02 归因的 `atomic_write` finally-unlink/replace 文件锁机制完全一致；**随 win-02 晋级落地解决**
- **check_repository ×3、repo_pedant_benchmark ×3**：Windows 残余，独立于晋级门控，立 win-11 工单跟进
- 符号链接特权类 **0 失败**（CI 管理员权限，实证 v0.7.0 报告分类一是消费机环境限制而非代码缺陷）

## 运行链接

- Run 1: https://github.com/TeFuirnever/azhou-ai-hub/actions/runs/34190698728/job/101947985179
- Run 2: https://github.com/TeFuirnever/azhou-ai-hub/actions/runs/34191267269/job/101949651635

## 结论

win-05 收据成立：Windows 残余失败集 = { win-02 晋级集群 } ∪ { 6 项 check/benchmark 残余 }。`PYTHONUTF8=1` 前提有效且与 installation.md 文档一致。CI job 保留为常驻证据传感器（continue-on-error，不入 Required）。

## 追加：fchmod 根因修复对照（2026-09-08，PR #175）

PR #174 的 Windows job 将真实根因从“清理掩盖”推进到确定结论：**`os.fchmod` 为 POSIX-only API，Windows 上 `atomic_write` 直接 AttributeError → CLI exit 1**，45 项断言失败与 19 项 lifecycle 级联均由此单一根因产生（此前“WinError 32 文件锁”为另一消费机上掩盖后的表象）。

| 轮次 | 环境 | 结果 |
|---|---|---|
| Run 4 | promotion 分支（无守卫） | 435 测试：45 FAIL + 9 ERROR + 6 skip；46 唯一失败全部 super-caveman |
| Run 5 | + fchmod hasattr 守卫 + 2 项 inode 测试 skipIf(nt) | 435 测试：**6 FAIL + 1 ERROR + 8 skip；46 → 7 唯一失败** |

剩余 7 项全部位于 test_super_caveman_benchmark：3 项为绑定/配对校验（新字节无新晋级记录时按设计拒绝——随晋级骑行落地转绿），4 项为同源级联（capability/trigger、review digests、staged/committed review 场景）。

- Run 4: https://github.com/TeFuirnever/azhou-ai-hub/actions/runs/34212619018/job/102016911113
- Run 5: https://github.com/TeFuirnever/azhou-ai-hub/actions/runs/34219846175/job/102040246435
- 修复分支: fix/win-12-fchmod（PR #175，落地须随下一轮晋级骑行）
