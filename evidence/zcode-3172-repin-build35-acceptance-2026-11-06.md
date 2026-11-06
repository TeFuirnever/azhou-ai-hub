# ZCode 3.17.2 重钉 build 35 验收回执（2026-11-06）

范围：ZCode 桌面自动更新 3.17.1.9553 → 3.17.2.9661 后，build 34 候选的宿主身份门 fail-closed（点击无反应）。本回执记录重钉、门禁、真实宿主验收与安装。

重钉（提交 `91bc922`，分支 `codex/agent-skin-zcode-rc35-20261104`）。

- `Native/ZCodeSkinRuntime.swift`：`expectedFiles` 三指纹、`validateInstallation` 守卫（version `3.17.2` / build `3.17.2.9661`）、内嵌 proof 三指纹与证据标签全部重绑到实测 3.17.2.9661（executable `a9279c2c…`、Info.plist `aa29610c…`、app.asar `12a2fc93…`）。
- 夹具同步：`StartupNativeTests.swift` 两处、`ZCodeSkinDriverTests.swift` 一处；`extension/hosts/zcode.mjs` 头注释；`hub-package.json` runtime_build 34→35。
- 门禁：UT 覆盖率四语言全过（JavaScript 95.27%、Python 95.13%、Swift 95.03%、Shell 97.14%，`tools/test-unit-coverage.py`）；主套件 684 项与 zcode-native 套件通过；`scripts/verify.py` exit 0。

真实宿主验收（隔离一次性 profile 实例，真实 3.17.2.9661 宿主与 build 35 生产载荷）。

- 生产构建器 UI 十步全绿（exit 0）：工厂安装、动画就绪并完成、预览取消不落盘、保存后只读事务回读、壁纸应用并解码、设置面板重开持久化、自有重复 dispose、页面重载后二次安装、二次动画完成、新文档重装与持久化。观察记录 SHA256 `247fc05d…`（`.local/zcode-rc35-20261105/real-production-ui-01/OBSERVATION.json`，按项目惯例保留在私有运行目录，不随源码提交）。
- 主窗口 CDP 页面截图在注入前捕获，捕获时无操作者在线，复苏会话事后由 agent 审阅确认为正常空主工作区（无错误弹窗、无登录墙、无崩溃页）。
- 验收监督链只读探针 rev3 基线钉 3.17.1，按其自身先例制 rev4 重绑 3.17.2.9661；监督 runner 由 launchd LaunchAgent 托管，git/租约以挂机时受信快照 `armed-context.json` 核对，UI 的不可变提交检查指向运行目录内裸克隆，全程零 `~/Desktop` 依赖。

盖章与安装。

- `zcode-validation.json`（schema `agent-skin-zcode-ui-evidence/v1`）以观察记录真实值组装，嵌入载荷 Resources，ad-hoc 重签通过 strict 校验。
- `~/Applications/阿舟 AI 实验室 for ZCode.app`：build 34（含旧验证文件）整体退役，替换为 build 35；安装后校验：签名 strict 通过、`CFBundleVersion=35`、验证文件 version `3.17.2.9661`、payload `a313f59a…`、record `247fc05d…`。

未声明。原生入口冷启动验收仍属独立项；日常 ZCode 已在运行时的热附着行为未在本回执范围内验证；根 README 两语言条目的 build 号同步留给集成合并。运行目录含 65MB 裸克隆等私有验收材料，不随源码分发。
