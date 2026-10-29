# Applications 安装补齐与验收

> 历史路径已按[迁移清单](../MIGRATION-INVENTORY.md)脱敏；变量仅定位原项目环境，原始证据仍留在本地，不证明本包当前已安装或生效。

> 历史记录：本文描述0.5.0之前的设计或验收，文中的版本、命令和数量均属于当时状态。旧 `~/Applications/Codex.app` 及恢复备份已按用户要求删除，历史恢复命令不再适用。现行入口、构建安装步骤和验收索引以 [项目 README](../README.md) 为准。

日期：2026-10-24。用户指出本项目已有本地 Applications 安装入口。首次交付只更新了项目 dist，没有同步该安装副本；本次已补齐。

## 已核实并更新的对象

| 项目 | 安装前 | 安装后 |
| --- | --- | --- |
| 物理路径 | $HOME/Applications/Codex.app | 原路径不变 |
| Bundle ID | local.aemeath.extension | local.azhou.codex-startup |
| 主可执行文件 | CodexStartup | AzhouCodexStartup |
| 版本 | 0.3.5 | 0.4.0 |
| 包内显示名称 | Codex | 阿舟启动 Codex |

原路径不是符号链接，旧身份、主可执行文件和 web 资源均与本项目旧启动器一致。保留 Codex.app 物理文件名以兼容既有入口，不宣称所有 Finder / Dock 缓存显示已自动改名；没有清理系统入口记录。

真正主程序仍为 /Applications/ChatGPT.app，Bundle ID com.openai.codex。没有覆盖、退出或修改它。

## 实现

- tools/install-macos.sh：正常构建后调用安装步骤；单独 build-macos.sh 仍只构建。
- tools/install-macos.py：只接受本项目已核实的旧身份或新身份；拒绝未知身份、正式主程序及符号链接。
- 将构建副本暂存到用户 Applications 同一文件系统，校验签名及文件内容 / 权限指纹，完整归档旧安装后原子交换。
- 安装后校验失败则交换回旧包；如果回滚也失败，保留原包所在暂存目录并明确报错。
- 内容已一致时返回 current，不重复复制或创建备份。
- 扩展启动Codex.command：同步当前构建，再打开现有 Applications 路径。
- README 已将日常入口改为已安装路径，明确区分构建与安装副本。

## 实际验收

1. 正常命令 bash tools/install-macos.sh 执行成功；安装包通过 codesign --verify --strict，内容 / 权限指纹与 dist 构建一致。
2. 从 $HOME/Applications/Codex.app 实际启动。运行中的主可执行路径明确为 $HOME/Applications/Codex.app/Contents/MacOS/AzhouCodexStartup，PID 96182。
3. 动画完整播放 7.8 秒，并覆盖播放中再次打开入口：一次 player-start、一次 target-reused、一次 reopen-existing-player、一次 target-activation-request；没有 target-open-request 或 failure。
4. 淡出完成时实际前台是 /Applications/ChatGPT.app，仍为原 PID 45354；启动器随后退出，无进程残留。
5. ~/Applications 中按本项目新旧 Bundle ID 核查，只找到现有 Codex.app 一个项目入口；没有另建“阿舟启动 Codex.app”安装副本。
6. 再次执行安装同步返回 current，恢复 ZIP 数量不变；--check 只读检查成功。
7. 真正主程序 Info.plist 和主可执行文件 SHA-256 与安装前一致。所有代码检查和操作都没有把主程序路径作为写入目标。

本次没有改变视觉实现；继续适用初次验收中“冷启动、其他显示条件和异常分支故障注入未实测”的边界。此次独立复核仅为安装脚本静态检查；实机安装与启动来自主流程。

## 证据和恢复

证据目录：.local/evidence/20261024/

- installation-before.json：安装前新旧身份及主程序校验值。
- install-local-application.log：正常构建、归档及安装日志。
- installed-target-probe.jsonl：从已安装包执行的路径和真实目标探针。
- installed-launch.mov / installed-launch.jsonl：已安装入口完整运行记录。
- installed-acceptance.json：运行路径、事件计数、交接、残留、唯一性和重复安装检查。

旧安装应用已完整归档：

.local/recovery/20261024-145128-553171-Codex.zip

对应 JSON 清单包含原始路径、Bundle ID、可执行文件及 ZIP SHA-256。恢复时先解压到临时目录，核实当前 ~/Applications/Codex.app 仍属于本项目后恢复整包；不要覆盖后来安装的正式或未知身份应用。

## 日常命令

```sh
cd "$ORIGINAL_PROJECT_ROOT"
bash tools/install-macos.sh
open "$HOME/Applications/Codex.app"

# 仅核对安装副本
python3 tools/install-macos.py --check
```
