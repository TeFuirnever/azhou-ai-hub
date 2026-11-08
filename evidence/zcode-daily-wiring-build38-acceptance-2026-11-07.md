# ZCode 日常接入与入口验收回执（2026-11-07，build 36–38）

范围：build 37（#377）落地后的日常使用反馈驱动的一轮修复。三个提交（分支 `codex/agent-skin-zcode-daily-wiring-20261107`，基于含 #381 的 main）：

- `c50a010` 共享接线：原生冷启动不再把宿主钉进隔离 profile。此前 `environment()` 覆盖 HOME/ZCODE_DATA_BASE_DIR/ZCODE_DESKTOP_USER_DATA_DIR/ZCODE_DESKTOP_SESSION_DATA_DIR/TMPDIR，冷启动打开的是空实例——2026-11-07 第一次真人冷启动暴露。现返回空环境字典，经无覆盖 open 路径继承用户环境（NSWorkspace 不设置 configuration.environment），冷启动打开用户真实 profile；状态根只存 launch-receipt。
- `958804d` 入口锚定：外观入口从侧栏末尾（压账号行）改为锚定 Plugin Marketplace 行之下（稳定导航标签 'Plugin Marketplace'/'插件市场' + `insertAdjacentElement('afterend')`，找不到标签回退末尾）。
- `372a134` 壁纸主区可见性 + 像素护栏 + 入口风格：首次每日 profile 冷启动报告"壁纸只在侧栏"。活体 CDP 探针（`elementFromPoint` 祖先链，含伪元素/backdrop 排除）定位真凶：main 的祖先 `<section>` 画不透明 `rgb(22,22,22)`，而验收只断言控制器状态（applied/decoded）从不断言像素。修复：wallpaper port CSS 增加 `#root :has(main)` 祖先透明化；验收在壁纸生效步后对主区三点采样渲染链、任何不透明非 MAIN 层即失败（`wallpaperBlockers`/`colorAlpha` 进 `acceptance-harness.mjs` 并带单测）；外观入口镜像 ChatGPT-desktop 芯片风格。
- `ed71fda` 入口 chrome 精确镜像：按维护者指认的参照（ChatGPT-desktop 的 Codex 宿主入口截图），采用 Codex 实现的精确值——32px 头像（radius 10px）、44px 行高、14px 芯片圆角、`box-shadow:0 2px 8px #0002`、12px/18px 字体，标签公式 `characterName + ' Appearance'`（EN "Azhou Appearance" / zh "阿舟外观"），替换第一版误用的 openAppearance 文案。

验收与安装。

- rc36（c50a010，payload ecbd2fbe）：10/10 exit 0，安装为 build 36。
- rc37（372a134，payload 71a1677e）：11/11 exit 0——含首上岗的 `main-area-wallpaper-pixels-uncovered` 像素步；用户冷启动确认对话在、入口位置正确；壁纸主区可见性随 build 37 修复。
- rc38（ed71fda，payload 4ca64c4e）：11/11 exit 0（前一轮 `animation-completion-timeout` 经重试定性为可见状态下的环境抖动——同载荷重试即绿）；用户冷启动确认入口与 ChatGPT-desktop 一致。OBSERVATION sha `d0cbac9c…`，安装为 build 38。

门禁：四语言 UT ≥95%（JS 95.44%/Py 96.24%/Swift 95.03%/Shell 97.14%）、`scripts/verify.py` exit 0（每个提交后均跑）。

用户视觉确认（2026-11-07，build 38 冷启动）：日常对话/项目在；入口位于 Plugin Marketplace 下方且与 ChatGPT-desktop 样式一致；壁纸主区可见。

诚实边界。验收监督链在 rc36/rc38 之间经历多次事故并全部修复（缺拷贝的截图器模块、EEXIST 多轮残留、双实例并发——flock 单例锁、日志截断模式、600s 退避移到 finally 后）；一次 rebind 相对路径事故把 rc36 运行目录文件改写为 rc37 内容（靠 mv 救援，不影响已安装产物与已固化证据）。原生冷启动入口的"用户在场视觉确认"即本回执的冷启动本身；热附着（宿主已运行时点击入口）仍未验收。`animation-completion-timeout` 的可见态抖动未做根因分析，仅以重试通过——记录为已知 flake。

## 补记：热附着验收（2026-11-08）

日常 ZCode 运行中（PID 50032，2026-11-07 23:38 由验收 runner 自动重开的普通启动、无调试端口）点击 `阿舟 AI 实验室 for ZCode.app`：主进程 PID 不变、无第二实例、`launch-receipt.json` 未重写（仍是上一次冷启动的 144B 收据）、驱动进程激活即退、无动画重播（维护者确认）。三个硬指标（PID 稳定/收据不动/驱动退出）全部通过——build 39 的热附着路径与冷启动路径双验证。
