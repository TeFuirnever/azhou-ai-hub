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
