# 0.5.1：安装升级与唯一入口实际验收

> 历史范围：本文记录0.5.1/build3的升级、重复问题与验收证据。现行版本与操作以 [项目 README](../README.md) 为准；后续0.5.2图标及安装包验证见 [图标验收](app-icon-0.5.2-verification.md)。

日期：2026-10-24。项目：`/Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation`。
本轮响应用户指出“安装新版本仍留下旧入口，应沉淀到项目”的问题。修改范围限于构建、安装、应用登记、启动脚本及对应回归；没有改动本轮动画画面和时间轴。

## 根因与上次验收遗漏

实际盘点发现两份0.5.0/build2应用，Bundle ID均为 `local.azhou.codex-startup`，主可执行文件均为 `AzhouCodexStartup`，完整树指纹同为：

`7a39526e155c2b1fd06d1f60dc74f3d6cf3e85a7bdf3d5e86b0e1381828fc680`

两条实体路径为：

1. `/Users/guanxueliang/Applications/阿舟启动 Codex.app`
2. `/Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation/dist/阿舟启动 Codex.app`

Spotlight与公开的NSWorkspace全部应用URL查询均同时列出这两处。旧 `~/Applications/Codex.app` 已不存在，两个历史旧Bundle ID的登记列表为空。Dock相关固定项只有官方 `/Applications/ChatGPT.app`，未发现固定的项目旧入口。

因此本次已重现的重复来自“保留可发现的dist构建应用，再复制安装到Applications”的输出方式。上次将dist视为构建副本而排除在日常入口唯一性结论外，验收范围不足。版本和内容相同仍然会成为两条系统应用入口。

另一个已确认的代码缺口是：`扩展启动Codex.command` 在旧dist存在时跳过构建，可能沿用旧产物。此分支一并移除。

证据：`.local/evidence/20261024-upgrade/before.json`、`before-registry.json`、`before-check.log`。新检查器在清理前实际返回失败，并明确列出上述两条路径。

## 固化的行为

- 构建只产出隐藏目录 `.build/azhou-payload`，无 `.app` 后缀；构建与安装的暂存载荷同样无 `.app` 后缀。
- 安装首先核验并原子更新唯一规范入口 `~/Applications/阿舟启动 Codex.app`，随后退役已证实的额外项目包。
- 在用户Applications和项目dist第一层发现候选；依据身份、版本、来源标记、签名和完整指纹判断，不按名字删除，不进入包内处理Helper。
- 同版本、同内容副本仍需清理；来源未知、其他项目根目录、较高版本、符号链接或官方身份保留并报告。
- 删除前重新核对候选及运行状态，先保存退休凭据，再对旧路径定点注销并删除。
- 正常安装始终用公开 `LSRegisterURL(force=true)` 更新已核实规范入口的登记；不会先注销新包。
- 最后同时复扫磁盘与三个项目Bundle ID的全部登记URL；不满足一个实体安装入口、dist零应用、一个规范登记路径时返回失败。
- 双击启动入口始终重建当前源码并完成安装检查。两种 `--check` 命令均为只读，不构建、不清理、不登记。
- 不生成ZIP备份。安装记录只保存版本、指纹、路径和退休证明；必要的事务回滚能力保留。

持久规则详见 [installation-lifecycle.md](installation-lifecycle.md)。

## 实际升级中发现并修复的问题

第一次实机迁移已成功替换0.5.1新包并退役dist旧包；随后多余的“注销规范新路径”步骤返回 `-10814`。安装器返回失败，并将收据保持为 `cleanup-pending`，没有误报全部成功。原始失败日志保留为 `upgrade.log`。

已删除这一步，改为只对旧退休路径注销，规范新包直接调用公开登记API。增加了三项对应回归：升级时不注销规范包；pending且登记缺失时补登记；pending且URL已经正确时仍刷新登记元信息。修复后重新执行完整构建安装并成功收尾，再重复正常构建安装成功。

## 最终实际结果

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 当前安装版本 | 0.5.1/build3；身份 `local.azhou.codex-startup / AzhouCodexStartup` | `.local/installation.json` |
| 安装目录项目应用数 | 1，规范Applications路径 | `final-state.json` |
| 项目内实体.app目录 | 0，包含对隐藏目录的完整项目遍历 | `final-state.json` |
| dist应用数 | 0 | `final-state.json` |
| 系统登记的项目路径数 | 1；两个历史项目ID列表为空 | `final-state.json` |
| Spotlight查询 | 仅返回规范Applications路径 | `final-state.json` |
| 重复正常构建安装 | 成功；无新增dist应用或注册payload | `repeat-install.log` |
| 只读检查 | 成功；安装记录、载荷/安装Info.plist、marker及登记工具的mtime与SHA未变 | `final-check.log`、`final-state.json` |
| 备份及暂存 | recovery目录不存在，没有遗留安装暂存目录 | `final-state.json` |
| 资源一致性 | 源码、隐藏载荷、安装版的HTML/CSS/JS及两份私有素材文件SHA一致 | `final-state.json` |
| 官方应用保护 | 官方Info.plist与主可执行文件的SHA和mtime均未改变 | `official-before.json`、`final-state.json` |
| 私有范围 | 原素材SHA未变；私有资源和产物无Git跟踪、无暂存 | `final-state.json` |

当前安装包完整树指纹：

`692af1c0e04fa6b5de78e852ff88a0c6567426318643a75a752263a766c76224`

最终应用从规范绝对路径实际运行一次。日志记录一次player-start、一次target-reused、一次animation-complete、一次激活请求、一次handoff-fade-complete、一次player-terminated，failure为0，target-open-request为0。交接后官方 `/Applications/ChatGPT.app`、ID `com.openai.codex`、PID68117处于前台；启动器PID89135已退出。

完整12秒屏幕录像 `launch-0.5.1.mov`、运行日志 `launch-0.5.1.jsonl`、摘要 `launch-result.json` 和每0.5秒抽帧总览 `launch-filmstrip.jpg` 均保留。主执行者已查看连续抽帧，序列包含开场前、完整动画、淡出和交接后的主程序。此轮未修改动画，因此没有重新宣称一次独立审美评审。录屏可能含用户已有的外部桌面宠物叠层。

## 回归与独立复核的范围

`python3 -B tools/test-install-macos.py` 在目标Mac执行，21个隔离回归全部通过。它们模拟codesign、ditto、NSWorkspace登记和原子交换调用，验证的是安装决策与错误路径，不能代替上表中的真实升级。覆盖同hash继续清理、改名副本、已核实0.5.0迁移、官方/未知/高版本保护、运行中副本、源变化、原子失败、回滚和登记恢复等。

独立代码审查完成，未发现阻塞升级或删除安全的具体问题；其结论仅限静态源码，不等同于独立Mac运行验收。

未额外实测已删除路径仍残留登记时的 `lsregister -u` 情形，因为这台Mac在实际退役后已经收敛；该恢复路径只有隔离回归证据。没有测试其他macOS版本或人工复制到授权管理目录之外的副本；这些路径会被报告，未经确认不会自动删除。没有退出官方主程序，因此没有新增冷启动验证。

## 文件与命令

| 文件 | 作用 |
| --- | --- |
| `tools/build-macos.sh` | 0.5.1/build3，隐藏无.app载荷、构建输入记录、签名、原子发布。 |
| `tools/verify-artifacts.py` | 身份、来源、指纹及载荷验证；将构建检查和安装入口检查明确分开。 |
| `Native/InstallRegistry.swift` | 公开API查询全部登记及登记规范路径的CLI。 |
| `tools/install-macos.py` | 升级事务、已确认副本清理、退休凭据、磁盘与登记最终断言。 |
| `tools/test-install-macos.py` | 21项必要安装回归。 |
| `tools/install-macos.sh`、`tools/build-extension.sh`、`扩展启动Codex.command` | 统一调用链，移除有旧构建就跳过更新的分支。 |
| `README.md`、`docs/installation-lifecycle.md` | 持久升级约定、正常命令和保护边界。 |

```sh
cd "/Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation"
bash tools/install-macos.sh
bash tools/install-macos.sh --check
open "$HOME/Applications/阿舟启动 Codex.app"
```

所有本轮证据位于 `/Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation/.local/evidence/20261024-upgrade/`。原有0.5.0的视觉验收文档及其dist存在性记录属于当时历史状态，本次0.5.1的入口结果以本文为证据，现行入口状态见项目README。本轮没有commit或push。

官方依据和工具的稳定性边界见 [安装升级约定](installation-lifecycle.md#官方依据)。
