# Windows 全流程回据 2026-10-17(#236 修复后全绿)

> 日期：2026-10-17（Asia/Shanghai）· 环境：GitHub Actions `windows-latest` runner，Python 3.11.9，Git Bash 默认控制台编码（未设 `PYTHONUTF8`/`PYTHONIOENCODING`）· 对象：托管安装全流程（info → setup → doctor → 仓库门禁），`.github/workflows/windows-full-flow.yml` · 仓库状态：`main@71645a4`
> 原始输出：Actions run `39021580061`（成功，job summary 与日志逐行留存）。
> 隐私口径：runner 路径为通用临时目录（`D:\a\…`、`C:\Users\RUNNER~1\…`），无用户身份、无会话内容。

## 执行与结果

| 步骤 | 结果 |
|---|---|
| info | 正常输出；`verification_command` 如实回显 |
| setup 计划 + 应用 | `status: pass`；source/installed digest 一致 |
| doctor（已装 skill） | 结构检查全 pass；`repository_verification`：`exit 0; OK (skipped=8)`，`status: pass` |
| 仓库门禁 | **`verification passed`**（8/8 门，569 tests，skipped=8），exit 0 |

## 对照历史

- **2026-09-13 收据**（`windows-full-flow-receipt-2026-09-13.md`，commit `52e9b99`）：门禁段红——4 unit failures + 5 errors，session-insights CJK 打印与 excalidraw 品牌校验在 cp1252 stdout 上 `UnicodeEncodeError`（#236）。
- **中间验证 run `39019712458`**（首修 #284 后）：仍红，`2 of 8 gates failed`——写侧修复后**解码侧**翻车：super-llm-wiki `emit()` 与 execution-protocol 校验器同因写崩；session-insights benchmark 的 locale 管道在子进程转 UTF-8 后 reader 线程 `UnicodeDecodeError`（#285 的实证）。
- **本 run**：三类全部收口后全绿。

## 修复构成（#284 + #285）

四个 skill 脚本入口 `_force_utf8_stdio()`（session-insights、excalidraw 品牌校验器、super-llm-wiki 仅输出侧、super-repo-pedant execution-protocol 校验器）+ benchmark/test harness 管道显式 `encoding="utf-8"`；回归测试在 `PYTHONIOENCODING=cp1252` 下驱动真实调用面。

## 结论

门禁段全绿，`docs/installation.md` 的分歧注记解除，#236 关闭。cp1252 类分歧在本仓库可动控制面内收口：其余 ~80 处 locale 管道位于 promotion 受保护的 super-caveman 面或纯 ASCII 子进程，清扫以独立工单跟进，不入本回据范围。
