# Codex Pet 旧根回执属主交接链路执行回执（2026-11-11，票 #443）

范围：`packages/codex-startup-animation/`（退役旧根，下称旧根）所装 Pet/App 回执属主向本包
（agent-skin，下称新根）的文档化交接链路执行、机器实况与维护者决策面。本回执是 #446 删除旧根前的
维护者审阅对象。工作分支 `codex/decommission-20261111`（HEAD 9a8b283a）；worktree
`.treehouse/azhou-ai-hub-2cc7ce/13/azhou-ai-hub`，lease `85f68592e96ed249409428de5fe9bf6f`
（holder `decommission-20261111`）。

## 工具链新家状态（无需复制）

Pet 工具链五件（`tools/manage-codex-pet.py`、`tools/import-codex-pet.py`、runbook
`docs/codex-pet.md`、`tools/test-codex-pet.py`、`tools/test-import-codex-pet.py`）已随 #441
去衍生化合并以独立重写形态落在本包（重写版 manage 83.9K 对旧根 42.5K；runbook 20.6K 对 15.6K），
预言套件当时 167/167 + 22/22 通过。本票不把旧根衍生字节复制过来覆盖重写版；根 `AGENTS.md`
Verification 的两条测试命令与 `README.md` 的 status/sync 命令已改指本包路径。

## 链路执行环境（字节保真沙箱）

真实回执属主迁移的持久落点在主 checkout（本任务只读面），且真实 `~/.codex` 回执不能指向临时
worktree 路径，故按 runbook 明文支持的隔离预演模式（`--project-root` / `--codex-home`）在沙箱
全保真执行，真实机器状态零写入：

- 沙箱 `/private/tmp/pet-handoff-443/`；
- `old-root/`：从主 checkout 旧根只读复制的 `.local/`（pets 候选/快照/选择记录、
  `installation.json`、锁）与 `assets/private/`，加上与旧根同提交的 `style.css`、`pet/theme.json`；
- `new-root/`：本分支 `packages/agent-skin` 的字节副本（剥离 `.build/`、`.local/`）；
- `codex-home/pets/azhou-agent-lab/`：真实 `~/.codex/pets/azhou-agent-lab/` 的副本；
- 路径映射改写仅限两份回执副本的 `projectRoot` 位置元数据（真实旧根绝对路径 → 沙箱旧根路径），
  主题/图集/清单等全部内容摘要逐字节未动。

## 交接前基线（旧根态完整可验）

`python3 -B new-root/tools/manage-codex-pet.py status --project-root old-root --codex-home codex-home`：

- `source.themeRevision` = `916ed5e9…772ae`（与真实安装回执一致）；
- `package` = verified（atlas `bbd296d9…904`，目录名
  `916ed5e9…-bbd296d9…`）；
- `installed` = verified，`bytesVerified: true`（真实安装字节与旧根候选逐项吻合）。

## 链路执行结果（按设计拒绝）

1. 候选导入（文档链路第一步）：
   `python3 -B new-root/tools/import-codex-pet.py --from-project old-root --project-root new-root`
   → 退出码 2，`status: target-conflict`，`error: 目標固定主题输入与源 revision 不匹配：style.css`，
   `installed: unchanged`、`generation: not-performed`。
2. 直接接管：`python3 -B new-root/tools/manage-codex-pet.py handoff --previous-project-root old-root …`
   → 退出码 2：新根无任何已审阅候选（无 `selection.json`）；其附带 `status` 显示新根当前主题
   `a88c838e…53a9`（`style.css` 摘要 `eb987202…e51c`，与旧根 `3fa95e58…47be` 不同）。

根因：`style.css` 是四个冻结主题输入之一；本包自 #361 起是深色重写产品，旧根浅色主题自 #346
合并后未变。`INSTALL_IDENTITY_KEYS = (atlasSHA256, themeRevision, manifestSHA256)` 要求接管两侧
themeRevision 逐字节一致——除非回退 #361 的产品决策，该安装的属主迁移会被工具按
「不允许借接管夹带内容变更」的安全语义持续拒绝。这是链路的正确行为，不是缺陷。

## App 侧机器实况

- 旧根 `.local/installation.json` 记录 `installedPath` = `~/Applications/阿舟启动 Codex.app`、
  status `installed`（v0.7.1 build 8，含 2026-10-26 的 sourceHandoff 史）；
- 本机 `~/Applications/` 实测无该 App（现存为本包的 `阿舟 AI 实验室.app` 与
  `阿舟 AI 实验室 for ZCode.app`）——没有活的旧根 App 安装可供 `--migrate-from` 接管，该记录是
  保留在 Git 外的陈旧历史。`--migrate-from` 未执行：其核对面（固定用户入口、系统登记）在本机
  必然拒绝，且没有可迁属主的对象。

## 未跟踪本地态保全（全程零删除、零改写）

- 真实 `~/.codex/pets/azhou-agent-lab/.azhou-pet-receipt.json` 仍指向旧根（执行前后各核对一次）；
- 主 checkout 旧根 `.local/`、`assets/private/` 的 mtime 全部停在 2026-10-26（执行后核对）；
- 后续 pet 工作若迁到本包根，需把旧根 `assets/private/` 的两张主题输入图
  （`working.png` sha `34dc9a8e…`、`wallpaper-scene-q-v3.png` sha `566eee50…`）按原字节归置到
  本包根同路径（Git 外，两侧均已忽略）；沙箱中新根以同字节图集计算出了自身主题修订
  （`a88c838e…`，深色 style.css 之下）。

## 持久根回放命令（维护者在主 checkout、合并落地后执行；主题分叉未消除前同样会被拒绝）

```bash
cd packages/agent-skin
python3 -B tools/import-codex-pet.py --from-project ../codex-startup-animation
python3 -B tools/manage-codex-pet.py handoff --previous-project-root ../codex-startup-animation
python3 -B tools/manage-codex-pet.py status
```

## 维护者决策面（#446 前置审阅项）

1. 接受拒绝为终局：旧根删除后 `~/.codex` 中该 Pet 的回执成为指向已删根的孤儿（Pet 本身自包含、
   继续可用）；本包未来按新主题走 prepare→生成→审阅新链路，安装前需先按原生方式移除
   `~/.codex/pets/azhou-agent-lab/`（普通 install 对他属回执按约拒绝）。
2. 若要保住该安装的属主迁移，唯一文档路径是让本包四项主题输入与旧根逐字节一致（回退 #361 的
   style.css 产品决策）后重跑上方回放命令——与去衍生化产品方向冲突，不推荐。
3. App 侧无需动作：没有活安装；旧根 `.local/installation.json` 与 `.build/azhou-payload` 作为
   Git 外历史随旧根目录归宿由 #446/收尾处理。

历史先例：2026-10-26 的安装态本地交接见仓库级
`evidence/optional-integrations-local-handoff-2026-10-26.md`。
