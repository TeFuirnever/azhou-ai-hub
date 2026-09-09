# Windows CI 实测收据（win-13 根因诊断与转绿）

> 日期：2026-09-09（Asia/Shanghai）· 环境：GitHub Actions `windows-latest`（Python 3.11.9、Git for Windows）· 命令：`python scripts/verify.py`（`Verify on Windows (experimental evidence)` job）· 载体：PR #186（squash 合并 f77dc4e）

## 残余失败归零链

| 轮次 | Run | 结果 | 说明 |
|---|---|---|---|
| 基线（main 56c6b14） | 34314295231 / job 102347158842 | 437 测试：2 ERROR | test_capability_and_trigger_integrity + test_exact_diff_approval_requires_bound_record，均 `FileNotFoundError [WinError 2]` |
| PR #186 c24d107 | 34329334514 / job 102393969181 | 单元测试 **437/437 绿**；repo-pedant benchmark 红：`verify command could not complete (FileNotFoundError)` | 根因一修复实证；暴露根因二 |
| PR #186 2dda4ce | 34336516564 / job 102417059400 | **全绿**（440 测试 OK skipped=8，政策/基准/空白检查全过） | 两个根因均修复 |

## 根因一：测试环境清空假设（POSIX-only）

`tests/test_super_caveman_benchmark.py` 的 exact-diff 审批测试用 `mock.patch.dict(os.environ, {}, clear=True)` 隔离环境变量。POSIX execvp 在 PATH 清空后回退默认搜索路径（/bin:/usr/bin），git 仍可解析；Windows CreateProcess **只**经 PATH 解析可执行文件，清空后即 WinError 2，击中 `benchmark.py` 两处无 try 保护的 git 子进程（`check()` 的 index 刷新、`is_approved_exact_diff()` 的状态追踪）。修复：`_cleared_environ()` 清空时保留 PATH，统一 9 处 `clear=True` 调用点（commit c24d107，纯测试侧，不触晋级绑定路径）。

## 根因二：repo-pedant verify_command 启动器

`benchmarks/repo-pedant` 四个 case 的 `verify_command` 均为 `["./verify.sh"]`（POSIX shell 脚本），Windows CreateProcess 无法直接 exec。修复：nt 下 `.sh` 命令经 Git Bash 启动（`which bash` → `which sh` → `C:\Program Files\Git\bin\bash.exe` 等已知路径兜底；缺失时显式 `BenchmarkError` 声明 shell 前提），POSIX 行为逐字节不变；附 3 个启动器单测，模块以唯一名 `repo_pedant_benchmark` 加载，避免与 super-caveman 测试的 `benchmark` 模块名在 sys.modules 冲突（commit 0f71580 + 2dda4ce）。

## 过程中的自伤与修正（留档）

第一版单测 patch 全局 `os.name` 为 "nt"，导致 pathlib 在 Linux 3.11 实例化 `WindowsPath` 报 NotImplementedError（Windows 上对称：patch "posix" → PosixPath 报错），Linux CI Python 3.11 红（run 34334060603）。修正为 `benchmark.py` 暴露模块级 `_ON_WINDOWS` 旗标、测试直接 patch 旗标，零全局副作用。教训：patch 共享标准库模块属性有跨平台级联风险。

## 结论

win-13 验收第一条成立：Windows job 转绿且根因入库。剩余：移除 `continue-on-error` 翻转 Required + support-matrix/README 双语同步——`.github/workflows/ci.yml`、`docs/support-matrix.md`、`README.md`、`README.zh-CN.md`、`CHANGELOG.md` 均在 revision-8f493670 晋级收据 `reviewed_blobs` 内，须走 maintainer 晋级流程携新收据落地。
