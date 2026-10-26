# 应用安装与升级约定

本约定随构建/安装脚本执行，适用于当前项目的macOS本地启动器。它没有自动更新服务，也不会修改真正的Codex主程序。

## 唯一入口

唯一日常启动路径为：

`~/Applications/阿舟启动 Codex.app`

身份为 `local.azhou.codex-startup / AzhouCodexStartup`。构建载荷位于忽略目录 `.build/azhou-payload`，无 `.app` 后缀。构建、安装及失败保留的事务暂存载荷同样不使用 `.app` 后缀。正常工作流程不保留 `dist/*.app` 构建副本。

曾经保留 `dist/阿舟启动 Codex.app` 与Applications副本的做法会让两份实体被系统同时登记；版本及内容相同也会造成两个入口。因此“安装内容一致”和“入口唯一”是两项独立的验收条件。

## 正常命令

```sh
bash tools/install-macos.sh          # 构建、安装、退役旧项目副本、复查
bash tools/install-macos.sh --open   # 同上；全部通过后打开规范安装路径
bash tools/install-macos.sh --check  # 只读，不构建、不登记、不清理
python3 tools/install-macos.py --check
```

`扩展启动Codex.command` 始终转入第一条安装流程并带 `--open`。它不能因已有旧构建就跳过源码构建。

`bash tools/build-macos.sh` 只更新隐藏载荷；`bash tools/build-extension.sh` 是同一构建的兼容名称。构建不会在新安装验证之前先删除旧的可用应用。

## 从旧项目目录接管现有安装

在最终 Hub 包目录构建并核查新载荷后，可一次性执行：

```sh
python3 tools/install-macos.py --migrate-from /absolute/old/project/root
python3 tools/install-macos.py --check
```

旧路径必须是仍然存在的实体目录。接管要求旧项目 `.local/installation.json`、`.build/azhou-payload` 和当前唯一安装入口的身份、来源标记、版本与完整包指纹一致；旧 `dist` 不得留有应用，系统登记必须只指向当前入口。操作同时锁住固定用户入口、新旧项目的安装记录。只有这一个精确旧包可进入现有的原子替换流程；普通安装仍拒绝其他项目目录的来源标记。新记录中的 `sourceHandoff` 保存新旧目录和指纹。新入口验证完成之前不要删除旧目录；失败后先核查入口与记录，再使用原命令重试。

## 升级次序与判断依据

安装器核对载荷身份、版本、来源标记、签名及完整包指纹；检查当前项目播放器没有使用待替换或退休路径。新包复制到无 `.app` 后缀的暂存目录，再校验指纹；替换前重新检查原目标未变化。规范目标以原子交换更新，替换后再次验证，失败则回滚。

新包有效后才清理已经确认的旧项目入口。扫描范围是用户Applications及项目dist；遇到其他位置的系统登记时报告路径，不擅自扩大删除范围。判断使用Bundle ID、主可执行文件、版本及来源证据，不根据文件名删除；同版本、同指纹的另一个实体也是重复入口。

新版包带 `Contents/Resources/azhou-build.json`，包含固定项目ID、真实项目目录、身份、版本、构建号和输入摘要。已实际核实的0.5.0旧包通过固定完整指纹和迁移记录建立来源；未确认的历史包保留并报告，不因“看起来像旧版”就删除。

正式主程序 `com.openai.codex`、未知身份、来源不明、无法解析版本、较高版本和符号链接受保护。安装目录中相同项目ID的冲突会使安装或检查返回非成功状态。包内正常Helper不会被递归当作入口处理。

退休前再次核对指纹，将待退休路径与证明信息保存为小型安装元数据，然后针对该路径注销并删除。元数据支持删除后登记状态尚未收敛时的定点重试；不保存旧应用或素材副本。

## 系统登记检查

`Native/InstallRegistry.swift` 编译为本地CLI：

```sh
.build/azhou-install-registry inventory
.build/azhou-install-registry register "$HOME/Applications/阿舟启动 Codex.app"
```

它使用公开的 `NSWorkspace.urlsForApplications(withBundleIdentifier:)` 查询三个项目身份的全部URL，保留不存在的旧路径记录；通过 `LSRegisterURL` 登记唯一规范路径。不能用只返回一个“首选应用”的API证明没有重复。

旧路径注销是针对这台macOS已经核实支持的 `lsregister -u` 的有限维护调用。Apple将该工具定位为调试工具、非稳定API；代码必须记录调用失败，并依靠公开API的最终复查决定登记是否已收敛。禁止全局清空、重建或递归重新登记系统数据库。

成功条件同时包括：规范安装内容等于当前载荷、管理范围只剩一个实体入口、项目dist没有额外实体应用、所有项目Bundle ID的已登记URL只有规范路径。文件已统一但登记未收敛时应明确失败，不得输出“全部通过”。

## 备份与版本记录

用户要求删除的历史恢复包已删除。正常更新不生成ZIP备份；原子操作失败时保留必要的临时原包用于恢复，成功后清除暂存目录。记录保存在忽略的 `.local/installation.json` 等本地元数据中，不包含可运行应用备份。

原素材及含素材的载荷、安装包和验收记录不得公开提交。源码与回归检查可保存在项目中；本次不自动commit或push。

## 必要回归

运行 `python3 -B tools/test-install-macos.py`。这些是隔离文件系统与模拟macOS调用的逻辑检查；实际构建、登记和启动以实机验收记录为准。

## 官方依据

- [NSWorkspace.urlsForApplications](https://developer.apple.com/documentation/appkit/nsworkspace/urlsforapplications(withbundleidentifier:))：查询同一身份的全部应用路径。
- [LSRegisterURL](https://developer.apple.com/documentation/coreservices/1446350-lsregisterurl)：登记并更新指定应用URL。
- [Launch Services Concepts](https://developer.apple.com/library/archive/documentation/Carbon/Conceptual/LaunchServicesConcepts/LSCConcepts/LSCConcepts.html)：应用发现与登记数据库。
- [Apple DTS的工具边界说明](https://developer.apple.com/forums/thread/725805)：`lsregister` 仅供调试维护，不应视作稳定API。

本机结果和回归记录见 [0.5.1实际验收](upgrade-0.5.1-verification.md)。
