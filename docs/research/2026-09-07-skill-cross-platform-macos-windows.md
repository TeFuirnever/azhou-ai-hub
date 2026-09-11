# 研究：Skill 包的 OS 层跨平台能力（macOS 与 Windows）

- 研究日期：2026-09-07（Asia/Shanghai）
- 范围：本仓库 `skills/` 下全部 15 个 canonical 包、`docs/` 声明面、`scripts/` 与 `.github/workflows/` 门禁的 **操作系统层**（macOS / Windows）能力盘点；业界一手文档对标。
- 说明：本文为纯研究观察，不修改任何 skill、门禁或声明文档。所有仓库内行号以 2026-09-07 工作区为准；外部主张一律引官方一手来源。1.6 节纳入同日获得的一份外部 Windows 实测报告（未入库）。文末"验证方式"给出复核路径。

## 结论（TL;DR）

1. **真实能力等级**：本仓库 skill 的 **Python 代码层**在 macOS 与 Windows 上基本等价（普遍使用 `pathlib`、显式 `encoding="utf-8"`、`sys.executable`，收据路径统一 `as_posix()` 规范化）；但 **文档命令面与合同命令面是 100% POSIX 形态**——`python3` 出现约 136 处（skills 内 `.md`/`.py`），全部配合 `$VAR`、`$()`、`shasum` 等 bash/Unix 惯用法。Windows 用户按文档逐步执行，**第一步就会卡住**。这不是推演：本笔记落稿当日获得的一份 v0.7.0 非官方 Windows 单测实测（427 个测试，73 FAIL + 21 ERROR + 2 skipped，见 1.6 节）已把上述面基本坐实。
2. **最大风险点**：
   - 全部 10 个 workflow 仅跑 `ubuntu-latest`，Python 矩阵（3.11/3.14）不含 OS 维度——所有 "supported" 主张事实上只被 Linux 验证，macOS 靠维护者本机，**Windows 无 CI 验证**——同日获得的 v0.7.0 非官方实测（1.6 节）确认 94 个失败/错误全部为平台兼容性问题，无一业务逻辑缺陷；
   - 生命周期 hook / adapter 的 command 是 `shlex.quote(sys.executable)` 生成的 POSIX 引号文本（super-caveman 三个 adapter、llm-wiki adapter），repo-pedant 的 hook 片段甚至字面硬编码 `python3` 与 `|| true`。这些依赖宿主用 Git Bash 执行 hook；Claude Code 官方明确"未装 Git Bash 时 fallback 到 PowerShell"，此时这些命令不再兼容；
   - Foundation CLI 默认安装模式 `--mode link` 用 `symlink_to`，Windows 上创建符号链接需要开发者模式或特权，而 `docs/installation.md` 的全部示例是 bash 语法（实测命中：21 个 ERROR + 约 10 个连带 FAIL，见 1.6 分类 1）。
3. **建议优先级**：P0 = 让公开声明与门禁反映 OS 现实（support-matrix 增加 OS 维度或显式不声明 + CI 增加 Windows runner 跑纯 stdlib 门禁）；P1 = 技能代码实测缺陷修复（super-caveman 三 adapter `atomic_write` 清理分支，实测约 45 项失败）与文档命令面双平台化（`python3` → `python`、`shasum` 复算合同补 `python -c hashlib` 等价命令）；P2 = 局部修复与测试护栏（`excalidraw_lib.py` 的 `/tmp` 硬编码、hook 片段生成器化、installation.md 补 Windows 注意事项、SIGALRM 平台降级与权限位断言跳过）。注意：凡触及公共 skill 面，必须按仓库标准与 `docs/support-matrix.md` 同步并走 promotion 流程，不能只改文档。

## 边界

[docs/research/azhou-skill-portability.md](azhou-skill-portability.md) 已回答 **harness 层**问题：Agent Skills 不标准化发现路径、调用语法（`/` vs `$`）、hooks、权限与配置所有权，因此本仓库选择"中立确定性 CLI（`scripts/azhou_hub.py`）+ 标准 `SKILL.md` 包 + 薄安装面"（同文件 "Direct answer" 与 "Decision for Azhou AI Hub" 节）。本文不重复该结论，只研究其下方的 **OS 层**：同一份包在 macOS 与 Windows 上，代码能否跑、文档能否照做、合同能否复算、hooks 能否触发。support-matrix 现有条目全部按 harness 分列（[docs/support-matrix.md](../support-matrix.md) 第 5 行表头），本文补的是它没有的第三个维度。

---

## 一、观察：仓库现状

### 1.1 声明面：现有平台声明在哪里，缺什么

**观察 1**：`docs/support-matrix.md` 的全部维度是 harness（Codex / Claude Code / zcode / 其他），**没有任何 OS（macOS/Windows/Linux）列或行**；开头的免责声明只划清 harness 边界："Portable package does not mean every harness exposes identical lifecycle hooks or memory APIs"（[docs/support-matrix.md](../support-matrix.md) 第 3 行、第 5 行表头）。

**观察 2**：全仓库声明面文档中，"跨平台"一词只出现一次，且指 harness 而非 OS："不伪装跨平台完全等价。Codex、Claude Code、zcode 共用运行包，但 hook 与历史适配能力在支持矩阵中分开写"（[README.zh-CN.md](../../README.zh-CN.md) 第 113 行）。OS 维度处于**未声明**状态：既没有"支持 Windows"，也没有"仅验证过 macOS/Linux"。

**观察 3**：依赖声明是逐包、精确的（这一层做得好）：Excalidraw 要 Python 3.11 + uv + Node 20+ + Playwright Chromium；LLM Wiki / Super Caveman（压缩）/ Arch Doc 为标准库 only；Lavish 要 Node 22+；Foundation 四件套要 Python 3.11+ 与显式 checkout（[docs/installation.md](../installation.md) 第 113-118 行）。但依赖**版本**有声明，依赖的 **OS 可得性**没有：例如所有示例命令写作 `python3 scripts/azhou_hub.py ...`（[docs/installation.md](../installation.md) 第 33-34 行；[README.md](../../README.md) 第 63-67、201 行）。

**观察 4**：`docs/skill-standard.md` 要求包内 setup 写明外部依赖的"最低版本、定位方式、失败边界和验证命令"（[docs/skill-standard.md](../skill-standard.md) 第 16 行），并规定 emoji 只进展示层、"不支持 Unicode 的 host 可移除 emoji，不能改机器字段和值"（同文件第 56 行）。前者为 OS 声明提供了规范入口但目前只被用于版本号；后者只约束 Unicode/emoji，未覆盖编码（代码页）问题。

**观察 5**：唯一一处贴近 OS 的诚实声明在 azhou-verify："它不证明每个外部 harness、平台或人工评审条件"（"it does not prove every external harness, platform, or human-review condition"，[skills/azhou-verify/references/setup.md](../../skills/azhou-verify/references/setup.md) 第 18 行）——门禁自己承认不覆盖平台维度。

### 1.2 逐包 OS 敏感点

排查方法：逐包阅读 `SKILL.md`、`references/`、`scripts/`、`assets/`，grep `python3`、`sed -i`、`readlink`、`mktemp`、`shasum`、`uname`、`/tmp`、`os.path`、`encoding`、`symlink`、hook command 等。

**全仓共性（好消息）**——Python 代码层：

- 全部脚本用 `pathlib` 为主拼路径（如 [skills/super-caveman/scripts/claude_adapter.py](../../skills/super-caveman/scripts/claude_adapter.py) 第 51 行、[skills/arch-doc/scripts/new_doc.py](../../skills/arch-doc/scripts/new_doc.py) 第 24 行等 30+ 处）；
- 文件读写普遍显式 `encoding="utf-8"`（[skills/excalidraw-diagram/scripts/svg-to-excalidraw.py](../../skills/excalidraw-diagram/scripts/svg-to-excalidraw.py) 第 27、68 行；[skills/llm-wiki/scripts/llm_wiki.py](../../skills/llm-wiki/scripts/llm_wiki.py) 第 266 行还带 `newline="\n"`；[skills/lavish/scripts/relay_state.py](../../skills/super-lavish/scripts/relay_state.py) 第 43、56 行），原子写用 `os.fdopen` 描述符而非 shell 重定向；
- 收据/状态文件中的路径统一 `as_posix()` 规范化（[skills/repo-pedant/scripts/azhou_runtime_state.py](../../skills/super-repo-pedant/scripts/azhou_runtime_state.py) 第 130-193 行；[skills/llm-wiki/scripts/llm_wiki.py](../../skills/llm-wiki/scripts/llm_wiki.py) 第 287 行；[scripts/azhou_hub.py](../../scripts/azhou_hub.py) 第 349、355 行）——路径分隔符不会进机器字段，收据跨平台字节稳定；
- 运行时状态层拒绝 symlink 根与路径内 symlink（[scripts/azhou_runtime_state.py](../../scripts/azhou_runtime_state.py) 第 26-27、58 行），不依赖 POSIX 权限位语义（实现层属实；但其测试直接断言 `0o700`/`0o640` 模式位且无平台跳过，见 1.6 分类 5）。

**全仓共性（坏消息）**——文档命令面：

- `python3` 在 skills 的 `.md`/`.py` 中共出现约 136 处（`grep -rn python3 skills/ --include="*.md" --include="*.py"` 排除 `node_modules` 与 `references/upstream` 后计数），配合 `"$SKILL_DIR"` 变量（如 [skills/excalidraw-diagram/SKILL.md](../../skills/excalidraw-diagram/SKILL.md) 第 156-190 行、[skills/super-caveman/references/setup.md](../../skills/super-caveman/references/setup.md) 第 12-95 行、[skills/llm-wiki/references/setup.md](../../skills/llm-wiki/references/setup.md) 第 17-56 行）。Windows 官方 Python 安装器的标准命令是 `python` / `py` / `pymanager`；`python3` 只是一个"捕获 POSIX 习惯误用"的 shim，官方明确"不打算被广泛使用或推荐"（Python 官方文档，见 2.4 节）。
- `shasum -a 256` 是四个包的 provenance/收据复算合同：[skills/arch-doc/references/templates/PROVENANCE.md](../../skills/arch-doc/references/templates/PROVENANCE.md) 第 18、26 行；[skills/eli5/references/provenance.md](../../skills/eli5/references/provenance.md) 第 28 行；[skills/lavish/references/provenance.md](../../skills/super-lavish/references/provenance.md) 第 37 行；[skills/excalidraw-diagram/references/provenance.md](../../skills/excalidraw-diagram/references/provenance.md) 第 22、28 行（后者还是 `find -print0 | sort -z | xargs -0 | shasum` 管线）。`shasum` 是 macOS 自带的 Perl 脚本，Windows 与多数 Linux 默认没有。

**逐包分级**（详见第三节对照表）：

- **ask-azhou / ci-test-reliability / prose-standard / eli5**：方法论或纯文档型，交付物（路由、HTML）OS 无关；eli5 的 HTML 生成是模型写文件，不依赖 shell（[skills/eli5/SKILL.md](../../skills/eli5/SKILL.md) 第 29 行）。仅 eli5 的 provenance 复算命令 POSIX-only（维护者层）。
- **azhou-doctor / azhou-info / azhou-setup / azhou-verify**（Foundation）：CLI 本体 `sys.executable` + 列表参数 subprocess（[scripts/azhou_hub.py](../../scripts/azhou_hub.py) 第 1163-1166 行），代码跨平台；但 setup 默认 `--mode link`（[scripts/azhou_hub.py](../../scripts/azhou_hub.py) 第 1331 行），执行 `destination.symlink_to(...)`（第 669、870 行）——Windows 上需要开发者模式或 `SeCreateSymbolicLinkPrivilege`（Microsoft 文档，见 2.4 节）；文档全程 `python3` + `$SKILLS_HOME`。
- **arch-doc**：`new_doc.py`/`verify_doc.py` 纯标准库，包内自述"无第三方依赖、无网络访问"（[skills/arch-doc/references/setup.md](../../skills/arch-doc/references/setup.md) 第 3 行）；仅 PROVENANCE 的 `shasum` 复算是 POSIX-only，PlantUML 可选渲染门在 CLI 缺席时"诚实跳过"（[docs/installation.md](../installation.md) 第 118 行）。
- **llm-wiki**：核心为标准库且收据路径 `as_posix()` 规范化（[skills/llm-wiki/scripts/llm_wiki.py](../../skills/llm-wiki/scripts/llm_wiki.py) 第 266、287 行）；MCP 配置用 `command + args` 数组形式（不经 shell，天然跨平台，[skills/llm-wiki/scripts/llm_wiki_adapter.py](../../skills/llm-wiki/scripts/llm_wiki_adapter.py) 第 175-182 行）；但 `render-hooks` 生成的 hook command 是 `shlex.quote` 拼接的 POSIX 引号文本（同文件第 128-132 行），setup 文档还含 `$(command -v python3)`（[skills/llm-wiki/references/setup.md](../../skills/llm-wiki/references/setup.md) 第 37 行）。
- **repo-pedant**：脚本为标准库；但 `assets/hooks/claude-hooks.fragment.json` 的 command **字面硬编码** `python3` 与 POSIX `|| true`（该文件win-08已删除并由渲染器取代，历史内容见 Git 历史；删除前第 9、19 行）；setup 指引用 `readlink` 验证链接（[skills/repo-pedant/references/setup.md](../../skills/super-repo-pedant/references/setup.md) 第 29 行）；`collect_agent_history.py` 在无 `--output` 时 `sys.stdout.write` 输出含品牌 emoji 的报告（[skills/repo-pedant/scripts/collect_agent_history.py](../../skills/super-repo-pedant/scripts/collect_agent_history.py) 第 56-57、696 行），在 Windows 默认 cp936 控制台下打印 emoji/中文是典型 `UnicodeEncodeError` 场景（仓库任何文档均未提及 `PYTHONUTF8`/`PYTHONIOENCODING`）。
- **super-caveman**：仓库内 **Windows 意识最强**的包——压缩备份目录显式分支 `os.name == "nt"` 走 `LOCALAPPDATA`（[skills/super-caveman/scripts/compression_guard.py](../../skills/super-caveman/scripts/compression_guard.py) 第 179-183 行），权限位测试显式 `skipIf(os.name == "nt")`（[tests/test_super_caveman.py](../../tests/test_super_caveman.py) 第 276 行）；但三个 adapter 的 hook command 与 llm-wiki 同样是 `shlex.quote(sys.executable)` 文本（[skills/super-caveman/scripts/claude_adapter.py](../../skills/super-caveman/scripts/claude_adapter.py) 第 390 行；codex_adapter 第 77 行同构），写入 `.claude/settings.json` / `.codex/hooks.json` / `.zcode/cli/config.json`（claude_adapter 第 379 行、codex_adapter 第 66 行、zcode_adapter 第 74 行），setup 文档全部 `python3 "$SKILL_DIR/..."`。实测另发现三个 adapter 共用的 `atomic_write` 清理分支在 Windows 触发 `WinError 32`（见 1.6 分类 2；[claude_adapter.py](../../skills/super-caveman/scripts/claude_adapter.py) 第 108 行、[codex_adapter.py](../../skills/super-caveman/scripts/codex_adapter.py) 第 276 行、[zcode_adapter.py](../../skills/super-caveman/scripts/zcode_adapter.py) 第 116 行）。
- **excalidraw-diagram**（最重运行时）：依赖 uv + Playwright Chromium + Node（[skills/excalidraw-diagram/references/setup.md](../../skills/excalidraw-diagram/references/setup.md) 第 12-28 行）；磁盘估算明确写着"current **macOS arm64** Python environment"（同文件第 13 行），Linux CI 系统库有专段（第 77 行），**Windows 无一字**；`scripts/excalidraw_lib.py` 硬编码 `CACHE = "/tmp/excalidraw-libs"`（第 39 行），且第 53 行 `json.load(open(...))` 缺显式 encoding（Windows 上按 locale 编码读 JSON，遇非 ASCII 会 mojibake/报错）；provenance 的 SHA-256 manifest 复算是 `find -print0 | sort -z | xargs -0 shasum` 纯 Unix 工具链（[skills/excalidraw-diagram/references/provenance.md](../../skills/excalidraw-diagram/references/provenance.md) 第 28 行）；高级工作流文档写死 `/tmp/excalidraw-libs/`（[skills/excalidraw-diagram/references/advanced-workflows.md](../../skills/excalidraw-diagram/references/advanced-workflows.md) 第 93 行）。
- **lavish**：relay 模式的 Python 侧跨平台良好（见上）；artifact 模式的回退命令是 `node "$(npm root)/lavish-axi/dist/cli.mjs"`——`$()` 命令替换是 POSIX shell 语法（[skills/lavish/SKILL.md](../../skills/super-lavish/SKILL.md) 第 31 行）；provenance 复算用 `shasum`（[skills/lavish/references/provenance.md](../../skills/super-lavish/references/provenance.md) 第 37 行）；浏览器评审面依赖本机浏览器与端口轮询，未做 OS 声明。
- **autoresearch**：fail-closed 设计正确——`mode=prepare` 在缺 CUDA/uv 时诚实 `hold`（[skills/autoresearch/SKILL.md](../../skills/autoresearch/SKILL.md) 第 27 行；[docs/support-matrix.md](../support-matrix.md) 第 41 行记录了 `nvidia-smi` exit 127 的 fail-closed 收据）；真实训练环境（NVIDIA CUDA + uv）现实中几乎总是 Linux，Windows 上 uv 可用但该包从未在 Windows 验证。

**未发现**的敏感点（如实记录）：无 `sed -i`、无 `uname`/`mktemp` shell 依赖、无反斜杠路径字面量、无 `C:\` 硬编码、无 `#!/bin/bash` 执行依赖（shebang 均为 `#!/usr/bin/env python3`，且宿主通过显式解释器调用）。

### 1.3 门禁与 CI

**观察 6**：门禁脚本本身是仓库内跨平台工程质量最高的部分：`scripts/verify.py` 全部用 `sys.executable` + 列表参数 subprocess，并提供 `--python` 覆盖（[scripts/verify.py](../../scripts/verify.py) 第 14-47 行）；`scripts/check_repository.py` 的 git 调用同为列表参数（[scripts/check_repository.py](../../scripts/check_repository.py) 第 191-196 行）；三个 benchmark 入口同为 `#!/usr/bin/env python3` + 列表 subprocess（[benchmarks/repo-pedant/benchmark.py](../../benchmarks/super-repo-pedant/benchmark.py) 第 125-135 行、[benchmarks/super-caveman/benchmark.py](../../benchmarks/super-caveman/benchmark.py) 第 205 行）。**理论上这些门禁今天就能在任何有 Python 3.11+ 与 git 的平台运行，包括 Windows。**

**观察 7**：但 CI 从未验证过这一点——全部 10 个 workflow job 均为 `runs-on: ubuntu-latest`（[.github/workflows/ci.yml](../../.github/workflows/ci.yml) 第 20、45、66、97 行；[.github/workflows/fuzz.yml](../../.github/workflows/fuzz.yml) 第 22 行；release/scorecard/codeql/dependency-review 同）。测试矩阵是 Python 版本（3.11/3.14，ci.yml 第 24-28 行），**不是 OS**。

**观察 8**：行尾与空白合同对 Windows 有明确设计：`.gitattributes` 首行 `* text=auto eol=lf` 强制工作区 checkout 为 LF（[.gitattributes](../../.gitattributes) 第 1 行；Git 官方语义见 2.4 节），`.editorconfig` 同步 `end_of_line = lf`，`verify.py` 内建 `git diff --check` working/staged 空白门（[scripts/verify.py](../../scripts/verify.py) 第 36-41 行）。这意味着 Windows 贡献者即使用 `core.autocrlf=true` 也会被 `eol=lf` 归一，不会踩 CRLF 空白门——但代价是 Windows 工作区中所有文件保持 LF，对 CRLF 敏感的本地工具需自行适配。

### 1.4 品牌/收据合同在 Windows 路径分隔符下的稳定性

**观察 9**：机器字段层是稳定的。收据与状态中的路径经 `as_posix()` 强制正斜杠（见 1.2 共性），namespace 校验正则限定 `[a-z0-9-]`（[scripts/azhou_runtime_state.py](../../scripts/azhou_runtime_state.py) 第 11 行 `_NAMESPACE`），品牌合同规定 JSON key、schema enum、digest、路径、命令、测试名与原始证据不带 emoji（[docs/skill-standard.md](../skill-standard.md) 第 56 行；[skills/excalidraw-diagram/references/brand-layer.md](../../skills/excalidraw-diagram/references/brand-layer.md) 第 104-107 行）。**跨平台读写同一收据不会因分隔符或大小写产生字段漂移。**

**观察 10**：展示层与控制台输出层不稳。品牌启动行/收据头含 emoji 与中文（品牌合同样例见 [scripts/check_repository.py](../../scripts/check_repository.py) 第 102-171 行；repo-pedant 报告头第 56-57 行），当脚本把这些文本 `print`/`sys.stdout.write` 到 Windows 默认 cp936 控制台时会触发 `UnicodeEncodeError`（触发点实例：[skills/repo-pedant/scripts/collect_agent_history.py](../../skills/super-repo-pedant/scripts/collect_agent_history.py) 第 696 行）。仓库文档与门禁均未提及 `PYTHONUTF8=1`/`PYTHONIOENCODING` 前置条件；Python 官方要到 3.15 才默认 UTF-8 模式（见 2.4 节），而仓库声明的支持下限是 3.10/3.11。

### 1.5 与公共 gate 的关系（合规性确认）

**观察 11**：最新 promotion 记录 `benchmarks/super-caveman/results/revision-93f38a6b-exact-diff-approval.json` 的 `reviewed_blobs` 共 8 条：`CHANGELOG.md`、`benchmarks/repo-pedant/results.tsv`、`benchmarks/super-caveman/manifest.json`、`benchmarks/super-caveman/results/revision-e04ba7c3-attempt-1-summary.json`、`skills/super-caveman/SKILL.md`、`skills/super-caveman/references/brand-layer.md`、`skills/super-caveman/references/setup.md`、`tests/test_brand_startup_discipline.py`。**不含 `docs/research/` 下任何路径**——新增本笔记不会触发"公共 gate 需要新 promotion receipt"的失败条件。

### 1.6 实测证据：v0.7.0 Windows 单测运行（2026-09-07 报告）

来源：维护者当日提供的外部实测报告，已按 `evidence/` 惯例收编为 [evidence/windows-unit-test-v0.7.0-2026-09-07.md](../../evidence/windows-unit-test-v0.7.0-2026-09-07.md)（报告原文未改动，仅前置收编说明）。环境：Windows x64（内核版本串 10.0.26200）、Python 3.11.9、Git 2.53.0，命令 `python -m unittest discover -s tests -v`，检出标称 v0.7.0（本地标签仅到 v0.6.0，0.7.0 的落点提交为 `07090d5`）。结果：**427 个测试，73 FAIL + 21 ERROR + 2 skipped，331 通过**，报告自述"全部失败均为 Windows 平台兼容性问题，无业务逻辑缺陷"。对照：同日 macOS HEAD 上 `verify.py` 全绿（429 测试；两者相差的 2 个来自 HEAD 比 v0.7.0 新增的测试）。

按六类根因记录，并标注与本文前文预测的关系：

1. **符号链接特权（21 ERROR + 约 10 个连带 FAIL）——预测命中**（见 1.2 Foundation 行与 2.4 Microsoft 文档）。`Path.symlink_to()` 在无开发者模式/特权的标准 Windows 上抛 `OSError: [WinError 1314]`，受影响面正是安全模型里"拒绝 symlink"的全部测试与 link 模式安装；报告建议的开启开发者模式即可让这批转绿。
2. **adapter `atomic_write` 清理分支（约 45 FAIL + 2 ERROR + 6 个次生 TypeError/KeyError）——新发现，前文未预测**。堆栈显示 `PermissionError: [WinError 32]` 抛在 [claude_adapter.py](../../skills/super-caveman/scripts/claude_adapter.py) 第 108 行的 `tmp_path.unlink()`。结合源码可精确还原机制：成功路径上 `os.replace` 已把临时文件移走，`finally` 的 `unlink()` 只会得到被吞掉的 `FileNotFoundError`；能在 `unlink` 处抛 WinError 32，说明 `os.replace` 先已失败（Windows 语义：源或目标被任何其他句柄占用即失败；占用者常见为实时杀毒/索引服务对新写文件的即时扫描，报告未给出占用者身份，此处不越权断言），原异常被包装为 `AdapterError` 后，`finally` 对仍存在且仍被占用的临时文件做 `unlink`，而该分支只吞 `FileNotFoundError`，于是 `PermissionError` 反向掩盖了原始错误。这不是测试专属：真实 Windows 用户执行 super-caveman 安装/状态写入走同一路径。[codex_adapter.py](../../skills/super-caveman/scripts/codex_adapter.py) 第 276 行与 [zcode_adapter.py](../../skills/super-caveman/scripts/zcode_adapter.py) 第 116 行同构。
3. **`python3` 不存在（4 FAIL，退出码 9009）——预测命中**（见 1.2、2.4）。被 Microsoft Store 应用执行别名存根拦截："Python was not found"。
4. **`signal.SIGALRM`（1 FAIL）——新发现，且暴露 1.2 排查范围的盲区**：`SIGALRM` 位于仓库级 [scripts/fuzz_relay_state.py](../../scripts/fuzz_relay_state.py) 第 254、269 行，而 1.2 的 grep 只扫了 `skills/`。POSIX 专有 API，Windows 需 `threading.Timer` 一类降级或显式跳过。
5. **POSIX 权限位断言（3 FAIL）——半命中**：实现层确不依赖模式位（1.2 好消息），但 [tests/test_azhou_runtime_state.py](../../tests/test_azhou_runtime_state.py) 第 23 行断言 `0o700`、[tests/test_lavish_relay_state.py](../../tests/test_super_lavish_relay_state.py) 第 66 行断言 `0o640`，均无平台跳过；既有先例是 [tests/test_super_caveman.py](../../tests/test_super_caveman.py) 第 276 行的 `skipIf(os.name == "nt")`。`os.chmod` 在 Windows 仅实现只读位，故有 `448 != 511`（0o700 vs 0o777）、`416 != 438`（0o640 vs 0o666）。
6. **证据/环境混合（约 10 FAIL）——报告自身的"内容性问题"判断需要修正**。报告猜测 `revision-93f38a6b-attempt-1-summary.json` 属"上游遗漏提交"；经核对，该文件与 manifest 对它的引用在 0.7.0 落点提交 `07090d5` **均已存在**（复核命令见文末第 11 条），且本仓 macOS 门禁对同一内容全绿——更可能是 Windows 侧差异（校验器路径分隔符或文本模式读取导致的 digest 漂移）或检出树偏移，**待复核**。`gh` CLI 缺失（3 FAIL）属环境缺工具；两个 git worktree 行为断言（`unexpectedly None`）待 Windows 复现定性。

**对结论的修正**：本文原判断"Windows 零验证"更新为"**无 CI 验证 + 已有一份非官方 v0.7.0 实测**"。实测同时做到三件事：验证了本文的阻断面预测（符号链接、`python3`）；暴露两个前文未捕获的代码/脚本层缺陷（atomic_write 清理、SIGALRM）与一个测试层缺口（权限位断言无护栏）；并给出 Windows 首跑的基线清单——约 35 个失败可由环境配置消除（开发者模式 + `python3` 别名处理），其余约 55 个需要上游修复或测试护栏。

---

## 二、观察：业界实践

### 2.1 Anthropic 官方 skill 生态：以"正斜杠 + 显式依赖"为可移植性主轴

- Agent Skills 官方最佳实践将可移植性具体化为路径规则："Always use forward slashes in file paths, even on Windows"，因为"Unix-style paths work across all platforms"（检查清单项为 "No Windows-style paths (all forward slashes)"）；依赖要求"在 SKILL.md 中列出所需包"并给出显式安装命令，不得假设工具存在。来源：[platform.claude.com Agent Skills Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)。
- 同页指出平台能力差异是**宿主属性**而非 skill 属性：claude.ai "Can install packages from npm and PyPI"，Claude API "Has no network access and no runtime package installation"。
- [agentskills.io 规范](https://agentskills.io/specification) 中与平台相关的只有两处：可选 `compatibility` 字段（"Indicates environment requirements (intended product, system packages, network access, etc.)"，自由文本，官方示例 `Requires Python 3.14+ and uv`）与 `scripts/` 一节（"Supported languages depend on the agent implementation. Common options include Python, Bash, and JavaScript"）。**规范没有 OS 级可移植性要求，也不要求声明目标 OS。**
- [anthropics/skills](https://github.com/anthropics/skills) 的重技能（docx/pptx/xlsx/pdf）技术栈是 **Python 编排脚本 + 领域库**：docx 用 `pandoc` + `docx-js`(npm) + 自带 `scripts/office/unpack.py/pack.py/validate.py`，pptx 用 `markitdown`(pip) + `pptxgenjs`(npm) + LibreOffice 转换（[skills/docx/SKILL.md](https://github.com/anthropics/skills/blob/master/skills/docx/SKILL.md)、[skills/pptx/SKILL.md](https://github.com/anthropics/skills/blob/master/skills/pptx/SKILL.md) 的 Dependencies 节）。其所有命令示例写 **`python`**（非 `python3`）+ 相对正斜杠路径，并把 `soffice.py` 打包为"沙盒环境自动配置 LibreOffice"的适配层——OS 差异被吸收进 Python 脚本而不是暴露给文档。
- 该仓库**没有任何 `.github/workflows`**（GitHub API 确认），即业界事实标准 skill 集合并未用 CI 矩阵验证跨平台。

### 2.2 OpenAI Codex：skill 文档对 OS 几乎不置一词

- [Codex skills 官方文档](https://learn.chatgpt.com/docs/build-skills)（原 developers.openai.com/codex/skills/ 308 重定向至此）写明发现位置为 repo（`.agents/skills`，沿 CWD 向上）/ user（`$HOME/.agents/skills`）/ admin（`/etc/codex/skills`）/ system，"follows the symlink target when scanning"；调用为 `$`/`@` 提及或隐式触发。**全文无 Windows 专属 skill 路径或 shell 约定**，管理路径是 Unix 风格；脚本执行环境仅写"Optional: executable code"，无解释器细节。

### 2.3 Claude Code / hooks 在 Windows 上的执行边界（对 hook 合同最关键）

- Windows 支持：系统要求 Windows 10 1809+；"Git for Windows is recommended on native Windows so Claude Code can use the Bash tool"；**未装则 "Claude Code uses PowerShell as the shell tool instead"**；WSL 2 才支持 sandboxing；npm 安装路径要求 Node 22+（[code.claude.com Setup](https://code.claude.com/docs/en/setup)）。
- Hook 的执行 shell（原文引用）："the command string is passed to `sh -c` on macOS and Linux, **Git Bash on Windows, or PowerShell when Git Bash isn't installed**"；Windows 上 exec 形式要求 command 解析到真实 `.exe`，"The `.cmd` and `.bat` shims that npm, npx, eslint, and other tools install ... are not executables"；command hook 经 stdin 收 JSON、以 exit code/stdout/stdout 回传；默认 timeout 600s（[code.claude.com Hooks reference](https://code.claude.com/docs/en/hooks)）。`CLAUDE_CODE_GIT_BASH_PATH` 可显式指定 bash.exe（[code.claude.com Env vars](https://code.claude.com/docs/en/env-vars)）。
- **对本仓库的含义**：`shlex.quote(sys.executable)` 生成的单引号命令在 Git Bash 下语义正确（bash 引号规则与 POSIX 一致）；一旦宿主回退 PowerShell（未装 Git for Windows 的原生 Windows），单引号 quoting、`|| true`、`$(...)` 全部失效。这正好命中本仓库四个 adapter/hook 片段的命令形态。

### 2.4 跨平台脚本工程的一手依据

- **Python `python` vs `python3`**：Windows 官方安装器（Python Install Manager）提供 `python`、`py`、`pymanager`；`python3` 仅是"捕获 POSIX 习惯"的 shim："intended to catch accidental uses of the typical POSIX command on Windows, but is not meant to be widely used or recommended"（[docs.python.org Using Python on Windows](https://docs.python.org/3/using/windows.html) 4.1 节）。→ 本仓库 136 处 `python3` 文档命令在 Windows 的标准安装上不是推荐入口。
- **PEP 686（UTF-8 mode 默认化）**："Python will enable UTF-8 mode by default from **Python 3.15**"；此前 Windows 上默认编码是 legacy ANSI 代码页，"Inconsistent default encoding causes many bugs"（[peps.python.org/pep-0686](https://peps.python.org/pep-0686/)）。→ 仓库声明的 3.10/3.11 下限在 Windows 上默认仍走 cp936，显式 `encoding="utf-8"` 与 `PYTHONUTF8` 才是保险；仓库前者做得好、后者无文档。
- **POSIX shell 可移植性坑**：`sed -i` 是 GNU 扩展（BSD/macOS 要求 `-i` 带备份后缀参数）、`readlink -f`/`realpath` 非 POSIX（GNU coreutils 扩展）、`mktemp` 非 POSIX 且 GNU/BSD 模板参数不同（GNU coreutils 手册与 ShellCheck wiki 生态，代表条目 [SC2006](https://www.shellcheck.net/wiki/SC2006)；综述见 [ShellCheck wiki](https://www.shellcheck.net/wiki/) 与 [easy-rsa #478 "Use of mktemp is not POSIX compliant"](https://github.com/OpenVPN/easy-rsa/issues/478)）。→ 本仓库幸运地几乎不踩这些坑（无 `sed -i`/`mktemp`），仅 `readlink`（无 `-f`，[skills/repo-pedant/references/setup.md](../../skills/super-repo-pedant/references/setup.md) 第 29 行）与 `shasum`、`find|sort -z|xargs` 管线属此类。
- **PowerShell 7**：微软官方定位为跨平台——"PowerShell is a cross-platform task automation solution ... PowerShell runs on Windows, Linux, and macOS"（[learn.microsoft.com PowerShell overview](https://learn.microsoft.com/en-us/powershell/scripting/overview)）；文档平台元数据即 `ms.tgtfr: windows, macos, linux`（[What's New in PowerShell 7.x](https://learn.microsoft.com/en-us/powershell/scripting/whats-new/what-s-new-in-powershell-73)）。→ 它是合法的跨平台兜底 shell，但其引号/管道语法与 POSIX 不同，skill 文档若以 bash 语法为唯一形态，PowerShell 用户需自行翻译。
- **Git 行尾语义**：`text` 属性控制"是否转换"（入库统一 LF），`eol` 控制检出到工作区的形态——`eol=lf` 即"uses the same line endings in the working directory as in the index"，且"specifying `eol` automatically sets `text`"（[git-scm.com gitattributes](https://git-scm.com/docs/gitattributes)）。→ 本仓库 `* text=auto eol=lf` 的效果是 Windows 工作区也保持 LF，配合 whitespace 门是自洽的设计。
- **Windows 符号链接**：创建 symlink 是特权操作，需 `SeCreateSymbolicLinkPrivilege` 或开启开发者模式；"Enabling Developer mode requires administrator access"（[Microsoft Learn: Settings for developers](https://learn.microsoft.com/en-us/windows/apps/get-started/developer-mode-features-and-debugging)；mklink/特权语义见 [Windows commands: mklink](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/mklink)）。→ Foundation CLI 的默认 `link` 模式与 installation.md 的"Development symlink"章节（[docs/installation.md](../installation.md) 第 82-97 行）在 Windows 上都需要这一前提，文档未提示。

### 2.5 对标结论

- **anthropics/skills**：跨平台策略 = "Python 编排 + 正斜杠 + 依赖显式列出 + 无 CI"。它把 OS 差异藏进脚本，文档层只有一种命令形态（`python` + 相对路径），单形态即跨平台。
- **mattpocock/skills**：仅有 `release.yml` 一个 workflow（GitHub API 确认），无测试矩阵。
- **本仓库**：门禁文化（确定性 check、benchmark-integrity、收据）远强于上述两者，但 **runner 维度反而比"多平台框架类项目"的行业惯例（`matrix.os: [ubuntu-latest, macos-latest, windows-latest]`）单薄**；且文档命令面是"POSIX 单形态"，没有吸收 anthropics/skills 那种把 OS 差异藏进 Python 的做法。

---

## 三、差距对照表

等级定义：**等价** = 双平台按文档可复现；**降级** = 核心可用但需变通/部分合同不可复现；**Windows 阻断** = 按当前文档/默认路径在标准 Windows 安装上无法完成；**host 决定** = OS 无关，取决于 harness。

| Skill 包 | Python 代码核心 | 文档命令面 | hooks / adapter 合同 | 重运行时依赖 | 双平台等级（macOS → Windows） |
|---|---|---|---|---|---|
| ask-azhou | 无脚本 | 无 shell 命令 | 无 | 无 | 等价（host 决定） |
| ci-test-reliability | 无脚本 | 仅 `scripts/verify.py` 引用 | 无 | 无 | 等价（host 决定） |
| prose-standard | `recall_batteries.py`（pathlib） | `python3` | 无 | 无 | 等价 / 降级（命令名需换 `python`） |
| eli5 | 无（模型写 HTML） | `python3`（收据） | 无 | 无 | 等价 / 降级；provenance `shasum` 复算 Windows 阻断（维护者层） |
| autoresearch | 无（fail-closed 检查） | `uv` 命令 | 无 | uv + NVIDIA CUDA | 等价（fail-closed）/ 现实目标环境几乎总是 Linux |
| arch-doc | `new_doc.py`/`verify_doc.py`（stdlib） | `python3`；PROVENANCE `shasum` | 无 | PlantUML 可选 | 基本等价 / 降级（shasum 复算阻断、命令名） |
| azhou-doctor / azhou-info / azhou-verify | `azhou_hub.py`（sys.executable） | `python3` + `$SKILLS_HOME` | 无 | Python 3.11+ | 等价 / 降级（命令名；doctor 的 treehouse 检查为可选外部工具） |
| azhou-setup | 同上 + `symlink_to` | `python3`；默认 `--mode link` | 无 | Python 3.11+ | macOS 等价 / **Windows 阻断（默认 link 需开发者模式，实测 21 ERROR 命中；`--mode copy` 可绕行）** |
| llm-wiki | stdlib + `as_posix()` 收据 | `python3` + `$(command -v python3)` | hook command = `shlex.quote` 文本；MCP 为 args 数组（跨平台） | 无 | 基本等价 / 降级（hooks 依赖 Git Bash；MCP 路径等价） |
| repo-pedant | stdlib + symlink 拒绝 | `python3` + `readlink` | 片段 JSON 字面 `python3` + `\|\| true` | 无 | 基本等价 / **降级偏阻断**（hook 片段在 PowerShell 下必然失败；历史收集 stdout 打印 emoji 在 cp936 有编码风险） |
| super-caveman | stdlib；显式 `os.name=="nt"` 分支与 `skipIf(nt)` | `python3` + `$SKILL_DIR` | 三 adapter hook command = `shlex.quote(sys.executable)` 文本 | 无 | 基本等价 / **状态写入阻断 + hooks 降级**（v0.7.0 实测：`atomic_write` 清理分支 WinError 32，约 45 项失败；hooks 依赖 Git Bash） |
| lavish | relay 模式 stdlib 良好 | `node "$(npm root)/..."`（POSIX 替换） | 无 | Node 22+、锁版本 npm 包、本机浏览器 | relay 等价 / artifact 模式降级 |
| excalidraw-diagram | pathlib + 显式 utf-8；但 `excalidraw_lib.py:39` 硬编码 `/tmp`、`:53` 缺 encoding | `python3` + `$SKILL_DIR`；provenance `find\|sort -z\|xargs\|shasum` 管线 | 无 | uv + Node 20+ + Playwright Chromium | macOS 参考（setup 自述按 macOS arm64 计） / **降级偏阻断**（Windows 全链路未声明未测；网络 fallback 与 provenance 复算不可用） |

风险归类汇总：

- **Windows 阻断**（按文档走不通）：Foundation 默认 `--mode link` 安装；excalidraw 网络 fallback（`/tmp` 硬编码）与 provenance SHA-256 manifest 复算；四包 provenance 的 `shasum` 复算合同；全部文档示例的 `python3` 入口（标准安装无此推荐命令）；super-caveman 三个 adapter 的状态/设置写入（`atomic_write` 清理分支，实测约 45 项失败）。
- **降级**（需 Git Bash/变通）：super-caveman、llm-wiki、repo-pedant 的 hook command（POSIX 引号文本）；lavish artifact 回退命令；repo-pedant `readlink` 指引；emoji 输出的 cp936 控制台编码风险。
- **测试/门禁层（实测新增，见 1.6）**：符号链接特权（21 ERROR，环境可消除）；POSIX 模式位断言无平台跳过；fuzz 的 SIGALRM；Windows 上证据配对校验疑似路径/读取模式差异（待复核）。
- **无影响/已良好处理**：收据与状态机器字段（`as_posix` + 无 emoji + ASCII namespace）；行尾（`.gitattributes eol=lf` + whitespace 门）；Python 文件编码（显式 utf-8 为主）；门禁脚本本体（sys.executable + 列表 subprocess）；super-caveman 压缩备份目录（显式 Windows 分支）。

## 四、建议

约束提醒：本仓库标准要求"公开支持主张必须与 `docs/support-matrix.md` 一致"（AGENTS.md "Repository shape" 节），且触及 skill 公共面/品牌层/promotion 覆盖路径的修改需要确定性门禁 + 配对评审 + 精确 diff 人工批准的 promotion receipt（AGENTS.md "Verification" 节）。以下建议均按此标准给出验收标准，本文不执行。

**P0 — 让声明与门禁反映 OS 现实**

1. **CI 增加 Windows（可选 macOS）runner 跑纯 stdlib 门禁**。`verify.py` 的 repository policy、unit tests、三个 benchmark-integrity 全是标准库 + git，理论上无须改动即可在 `windows-latest` 运行；新增 job 只需在 ci.yml 的 matrix 或独立 job 加 OS 维度（Python 3.11 单版本即可起步）。已知风险点：`tests/test_super_caveman.py:276` 已有 `skipIf(nt)`，其余测试未见 OS 断言；v0.7.0 非官方实测（1.6 节）已给出首跑失败清单的绝大部分，CI 首跑与其后的修复可按其六类逐类销号。
   验收：`windows-latest` job 连续绿；若某门禁无法在 Windows 跑，在 support-matrix 或该 job 名中显式记录原因，不允许静默跳过。
2. **support-matrix 增加 OS 维度或显式"OS 未声明"条目**。最小方案：新增一行说明"本矩阵按 harness 分列；OS 层能力见 2026-09-07 研究笔记，公开主张限于'Python 3.11+ 的确定性门禁可在 macOS/Windows 复现'并以 P0-1 的 CI 证据为前提"。声明变更与 CI 变更同一提交落地，避免文档先行的"空主张"。
   验收：support-matrix 中每个新增 OS 主张都能指向一个 CI job 或 checked-in 收据；README（中英）同步更新（同一提交）。

**P1 — 命令面与合同双平台化**

3. **adapter `atomic_write` 清理分支的 Windows 加固（实测确认的技能代码缺陷）**。super-caveman 三个 adapter 的 `finally` 清理只吞 `FileNotFoundError`；`os.replace` 在 Windows 因源/目标被占用而失败后，清理分支会以 `WinError 32` 掩盖原始错误（1.6 分类 2，实测约 45 项失败）。修法：清理分支补 `except PermissionError: pass`（临时文件清理本就是尽力而为），并评估 `os.replace` 的短重试；对 `scripts/azhou_hub.py` 与 llm-wiki、repo-pedant 的同型原子写实现做一次同型核查。
   验收：在无开发者模式的 Windows 上连续运行 super-caveman 全套 adapter 测试，无 `WinError 32` 掩盖现象。
4. **文档命令统一为 `python`（或提供显式 Windows 变体）**。`python` 是三大平台官方安装器的公共命令（Windows 官方主命令、macOS via python.org/Homebrew 可得、CI 自带）；anthropics/skills 已示范"单形态 = `python` + 相对正斜杠"即可跨平台。改动面：`docs/installation.md`、两份 README、各 `SKILL.md`/`references/setup.md` 中的 `python3`（skills 公共面变更需与品牌/promotion 流程合并处理）。可让 `scripts/check_repository.py` 的品牌/合同检查扩展一条"setup 命令形态"lint 以防回潮。
   验收：仓库内文档不再出现裸 `python3`（或全部伴随 `python`/`py` 变体）；`check_repository.py` 对应 lint 门禁绿。
5. **`shasum -a 256` 复算合同补等价命令**。四个 provenance 文件各加一行标准库等价：`python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <file>`（manifest 管线同理可用 Python 一段脚本替代 `find|sort -z|xargs|shasum`）。hashlib 十六进制输出与 `shasum -a 256` 完全一致，不改变收据机器字段。
   验收：在 macOS 与 Windows（Git Bash 或 PowerShell）各照文档复算一次 excalidraw bundle digest 与一个 manifest digest，结果与 checked-in 值一致并留对照记录。

**P2 — 局部修复与前瞻**

5. **测试层平台护栏**。[scripts/fuzz_relay_state.py](../../scripts/fuzz_relay_state.py) 第 254 行的 `SIGALRM` 在 Windows 降级为 `threading.Timer`（或按 `hasattr(signal, "SIGALRM")` 显式跳过）；[tests/test_azhou_runtime_state.py](../../tests/test_azhou_runtime_state.py) 第 23 行、[tests/test_lavish_relay_state.py](../../tests/test_super_lavish_relay_state.py) 第 66 行等模式位断言补 `skipIf(os.name == "nt")`（先例：[tests/test_super_caveman.py](../../tests/test_super_caveman.py) 第 276 行）。
   验收：Windows 单测失败集合相对 1.6 节清单单调收敛。
6. **`skills/excalidraw-diagram/scripts/excalidraw_lib.py`：`CACHE` 改 `tempfile.gettempdir()/excalidraw-libs`，第 53 行补 `encoding="utf-8"`**；`references/advanced-workflows.md` 的 `/tmp` 示例同步。验收：Windows 上执行 `search`/网络 fallback 路径不再依赖 `/tmp`；vendored 主路径行为不变（回归：现有 scene-hygiene/style 检查照常绿）。
7. **hook 片段生成器化**：repo-pedant 的 `claude-hooks.fragment.json` 由文档静态片段改为由 `closeout_hook.py`（或 doctor）用 `sys.executable` 渲染生成，消除字面 `python3` 与 `|| true`；同时在三个 adapter 的 setup 文档声明宿主 shell 前提（"Windows 需要 Git Bash 或安装 Git for Windows，hooks 在 PowerShell fallback 下不受支持"）。验收：Windows + Git Bash 下 SessionStart/Stop 触发冒烟收据一份（照 super-caveman live 收据的格式）；PowerShell fallback 行为显式标注 not claimed。
8. **installation.md 补"Windows 注意事项"小节**：默认 `--mode link` 需要开发者模式/特权，无权限环境请用 `--mode copy`；`$SKILLS_HOME` 的 PowerShell 等价写法（`$env:SKILLS_HOME`）；可选提及 `PYTHONUTF8=1` 对含 emoji 输出脚本的兜底作用。验收：一位 Windows 用户仅凭 installation.md 完成 `info` → `setup --mode copy` → `verify` 全流程（可作 checked-in 复现记录）。
9. **前瞻（不在本轮）**：Python 3.15 默认 UTF-8 模式落地后（PEP 686），cp936 输出风险自动收窄，届时可移除相关 workaround；support-matrix 的 harness × OS 二维化可在有 Windows 实测收据后再考虑，避免无证据扩表。

## 验证方式

本笔记的主张可按以下方式复核（2026-09-07 工作区）：

1. 声明面缺 OS 维度：读 [docs/support-matrix.md](../support-matrix.md) 第 3、5 行与全文表头；`grep -rn -iE "macos|windows|linux" docs/ README.md README.zh-CN.md`，确认仅 README.zh-CN.md:113 一处"跨平台"且指 harness。
2. `python3` 计数：`grep -rn python3 skills/ --include="*.md" --include="*.py" | grep -v __pycache__ | grep -v node_modules | grep -v references/upstream | wc -l`（约 136）。
3. POSIX 合同证据：`skills/repo-pedant/assets/hooks/claude-hooks.fragment.json`（win-08 已删除并由渲染器取代，历史内容可用 `git log -- skills/repo-pedant/assets/hooks/` 追溯；删除前第 9、19 行为 `python3`、`|| true`）；[skills/super-caveman/scripts/claude_adapter.py](../../skills/super-caveman/scripts/claude_adapter.py) 第 390 行（`shlex.quote(sys.executable)`）；[skills/excalidraw-diagram/references/provenance.md](../../skills/excalidraw-diagram/references/provenance.md) 第 22、28 行（`shasum`、`find|sort -z|xargs`）。
4. 硬编码路径与编码缺口：[skills/excalidraw-diagram/scripts/excalidraw_lib.py](../../skills/excalidraw-diagram/scripts/excalidraw_lib.py) 第 39、53 行。
5. 安装模式与 symlink：[scripts/azhou_hub.py](../../scripts/azhou_hub.py) 第 1331 行（`default="link"`）、第 669、870 行（`symlink_to`）；[docs/installation.md](../installation.md) 第 82-97 行（Development symlink 节）。
6. CI runner 单一：`grep -n "runs-on" .github/workflows/*.yml`（全部 `ubuntu-latest`）；Python 矩阵见 [.github/workflows/ci.yml](../../.github/workflows/ci.yml) 第 24-28 行。
7. Windows 意识先行证据：[skills/super-caveman/scripts/compression_guard.py](../../skills/super-caveman/scripts/compression_guard.py) 第 179-183 行；[tests/test_super_caveman.py](../../tests/test_super_caveman.py) 第 276 行。
8. reviewed_blobs 覆盖：`python3 -c "import json;d=json.load(open('benchmarks/super-caveman/results/revision-93f38a6b-exact-diff-approval.json'));print([b for b in d['reviewed_blobs']])"`，确认无 `docs/research/` 前缀。
9. 门禁跨平台性：`python3 scripts/verify.py`（本机 macOS 已由维护者例行运行）；同一命令在 Windows（`py -3 scripts/verify.py`）是否通过即为 P0-1 的实验起点。
10. 外部主张：逐条访问第二节所列官方 URL（code.claude.com setup/hooks、agentskills.io specification、platform.claude.com best-practices、docs.python.org using/windows、peps.python.org/pep-0686、git-scm.com/docs/gitattributes、learn.microsoft.com developer-mode 与 PowerShell overview、learn.chatgpt.com/docs/build-skills、github.com/anthropics/skills）。
11. Windows 实测报告已收编至 [evidence/windows-unit-test-v0.7.0-2026-09-07.md](../../evidence/windows-unit-test-v0.7.0-2026-09-07.md)；1.6 分类 6 的时序复核：`git cat-file -e 07090d5:benchmarks/super-caveman/results/revision-93f38a6b-attempt-1-summary.json && git show 07090d5:benchmarks/super-caveman/manifest.json | grep -c 93f38a6b`（两条均应成功）。
