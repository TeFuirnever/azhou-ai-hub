# 离线真实验收 runbook（ZCode 宿主）

> 供下一次宿主版本漂移后的离线验收复用。2026-11-06 的 build 35 验收跑了十轮才全绿；本文把每一轮的败因固化成清单与检查，机械类已进 `tools/acceptance-harness.mjs` 的测试。

## 触发条件

ZCode 桌面自动更新（或任何宿主指纹漂移）后，身份门按设计 fail-closed。重钉指纹后必须重跑真实验收，才能盖章 `zcode-validation.json` 并安装。监督链要求启动时**全机无任何 ZCode 进程**（含 Helper），所以验收必须走串行窗口：用户退出宿主 → 自动跑完 → 自动重开。

## 挂机前清单（每项完成即勾）

1. **枚举全部钉点面**：grep 旧指纹的 version/build/三个 SHA，范围是 Native、测试夹具、`hub-package.json`、`extension/hosts/zcode.mjs`，**以及验收工具自身的 EXPECTED 类常量**（探针 `EXPECTED` 基线、frozen-run 网关、UI 脚本内嵌 git 检查）。完成标准：rg 旧字面量在受影响目录零命中，且每个带基线的工具都被逐文件读过。
2. **跑全部门禁**：`tools/test-unit-coverage.py` 四语言 ≥95% + `scripts/verify.py`。完成标准：两个 gate 的真实退出码为 0（`cmd > log; echo EXIT=$?`，不要接管道尾巴）。
3. **构建候选载荷**：`bash tools/build-macos.sh --host zcode`。完成标准：`azhou-build.json` 的 build 号正确、`Resources/` 下无 `zcode-validation.json`。
4. **运行目录就位**（0700，含 home/tmp/business/electron-user/electron-session/empty-workspace/real-production-ui-01；**目录本体也要 0700**，`mkdir -p -m 700` 只作用于叶子）。完成标准：`stat -f "%Sp"` 逐个为 `drwx------`。
5. **TCC 消毒**：launchd 裸进程没有"桌面文件夹"权限，监督链的每个触面（git、探针、UI 脚本）都不得读写 `~/Desktop`。做法：git/租约 → 会话内预快照 `armed-context.json`（含 runner 自身 sha）；仓库 → 裸克隆进运行目录（`git clone --bare --single-branch --branch <branch> file://<worktree> <run>/source.git`，用 `env -i` 验证）；探针 → 拷进运行目录并钉 sha。完成标准：`env -i` 逐文件可读，监督链全文无 `~/Desktop` 路径。
6. **守护化**：LaunchAgent plist（RunAtLoad + KeepAlive{SuccessfulExit:false, ThrottleInterval:600}）+ `launchctl bootstrap gui/$(id -u)`；失败退避放 finally **之后**（否则压住 closeout/PIPELINE-DONE/自动重开落盘）。`launchctl submit` 不要用：失败自动重生成造成风暴，同 label 快速重挂会静默死。完成标准：`launchctl print` state=running，心跳文件 30 秒内在跳，存活实测超过 2 分钟。
7. **屏幕清醒**：监督链起隔离实例时挂 `caffeinate -d -w <隔离实例pid>`；隐藏页面的 rAF 会被系统节流，动画 `complete` 相位永远不来（表象：progress 100 却超时）。用户需留在机前、不锁屏。完成标准：caffeinate 子进程与实例同生命周期。
8. **告知用户**：⌘Q 退出 → 等 5–10 分钟 → 收到通知且 ZCode 自动重开 → 期间不要手动开。

## 十轮败因速查

| 轮 | 败因 | 类别 | 去处 |
|---|---|---|---|
| 1 | Bash 工具内 `start_new_session` 守护化，宿主退出连带清除 | 环境 | 本清单第 6 条 |
| 2 | launchd 裸进程读 `~/Desktop` 的 gitdir：`not a git repository: (null)`，且 submit 重生成成风暴 | 环境 | 第 5、6 条 |
| 3 | submit 同 label remove+快速重挂，~2 分钟静默死 | 环境 | 第 6 条 |
| 4 | 运行目录本体 755（`mkdir -p -m` 只作用叶子），断言 700 拒绝 | 机械 | 第 4 条 |
| 5 | 探针 rev3 自带 EXPECTED 基线钉旧宿主：`installed-identity-differs-from-fixed-baseline` | 隐藏钉点 | 第 1 条；照 rev 先例制 rev+1 重绑 |
| 6 | CDP 页面 URL 带 `?locale=en-GB`，精确后缀匹配 0 页 | 机械 | `acceptance-harness.mjs` + 测试 |
| 7 | UI 脚本内嵌 `git cat-file`（cwd=worktree，TCC）+ 缺 frozen-run 网关 | 环境 | 第 5 条 + 网关照 rc 版先例重制 |
| 8 | 输出目录预存在，非递归 mkdir 抛 EEXIST | 机械 | `ensureDir` + 测试 |
| 9 | 用户离开→屏幕锁定→页面 hidden→rAF 节流→动画 completion 挂起（progress 已 100） | 环境 | 第 7 条 |
| 10 | —（全绿） | — | — |

复盘口径：失败时先读 `failure_observation`（OBSERVATION.json 里）和 `runner.log` 的 stage 序列再动手；截图与错误信息截取要取**头部**（消息在首行）。

## 复苏后（跑完全绿）

1. 先亲眼看 `zcode-window.png`（捕获时无人审阅；本仓图像 Read 只回 CDN URL，主视觉 MCP 可能 401，备一条可用通道）。完成标准：确认为正常空主工作区。
2. 核对 OBSERVATION 十步、closeout waitExit=0、UI exit 0。
3. 组装 `zcode-validation.json`（真实值：recordSHA=OBSERVATION sha、payloadSHA=startup/install.js sha、宿主三指纹、evidenceIDs 用真实 RC 项），嵌入 `Resources/`，`codesign --force --sign -` 重签并 strict 校验。
4. 替换安装 `~/Applications/阿舟 AI 实验室 for ZCode.app`，安装后逐项核验（签名、build 号、validation 内容）。
5. 收尾：`launchctl bootout` + 删 plist、evidence 回执、README build 号、提交。声明未验收项（原生冷启动入口、热附着按例保留）。
