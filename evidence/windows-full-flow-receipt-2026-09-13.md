# Windows 全流程回据（info → setup → doctor → 仓库门禁，windows-latest runner）

> 日期：2026-09-13（Asia/Shanghai）· 环境：GitHub Actions `windows-latest` runner，Python 3.11.9，Git Bash · 对象：checkout 托管安装全流程（issue #224，parent #218）· 仓库状态：`main@52e9b99`
> 隐私口径：runner 路径为通用临时目录（`D:\a\…`、`$RUNNER_TEMP`），无用户身份、无会话内容。
> 原始输出：Actions run 34754444254（job summary 与日志逐行留存）。

## 执行与结果

| 步骤 | 命令（`scripts/azhou_hub.py`） | 结果 |
|---|---|---|
| info | `info --json` | 仓库/运行时信息正常输出；`verification_command` 如实回显 |
| setup 计划 | `setup --skill session-insights --target "$RUNNER_TEMP/skills-home" --mode link --json` | `status: dry_run / planned`；`planId: 181bded9…78f2`；`source_digest: 71a9a524…b53c` |
| setup 应用 | `setup … --apply --plan-id <planId> --json` | `status: pass`；`status: installed`；source/installed digest 一致 |
| doctor | `doctor --skill session-insights --target … --verify --json` | `status: unhealthy`——不健康项只有 `--verify` 腿（在 runner 上复跑单测），详见下节；repository_shape / python 3.11.9 / git_metadata / package / target 各检查全部 `pass` |
| 仓库门禁 | `python scripts/verify.py` | repository policy 通过、whitespace 通过；单测出现 **4 failures + 5 errors + 8 skipped**，exit 1——全部同根因，见下 |

## 同根因分歧（已建档 #236）

Git Bash 下 runner 的 stdout 编码是 cp1252：session-insights CLI 打印 CJK fixture 文本即 `UnicodeEncodeError`（`session_insights.py` `print(rendered)`，:867），excalidraw 品牌校验子进程同因出错。CI 的 Windows 腿同 commit 全绿，说明现有 Windows 声明依赖 runner 的控制台配置，而非代码级 UTF-8 保证——这违反跨平台规范的 explicit UTF-8 纪律，已开 #236（含代码级修复方向：console 输出面显式 `reconfigure(encoding="utf-8")`）。

## 结论

Windows 上的托管安装主流程（info → 计划 → 应用 → doctor 结构检查）真实走通；doctor 的 `--verify` 腿与单测套件暴露了一个此前不可见的控制台编码分歧（#236）。安装指南的回据注记据此更新：回据已入库，但附此分歧说明，直至 #236 关闭后改为全绿引用。
