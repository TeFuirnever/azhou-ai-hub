# 0.7.1 / build 8 — 聊天装饰渐隐层修复验收

日期：2026-10-25（Asia/Shanghai）。项目：`/Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation`。

## 结论

用户红框指出的输入框上方横向暗带已修复，并通过最终安装包在原“阅读 MOSS 验证报告”会话中完成前后截图与真实计算样式对照。同类排查发现的主内容顶部渐变同时修复。当前安装与运行页均为 **0.7.1 / build 8**。

原生纯校验 **97 项通过**；隔离浏览器 **15 组通过**，包含真实 0.7.0 源码的漏报复现。统一安装、签名与唯一入口核查通过。当前真实深色窗口验收通过；浅色、窄窗、多行输入和故障注入在隔离模拟宿主中完成，不将其表述为真实宿主全场景验收。

## 原因与同类缺口

1. 原 footer 底板已透明，但底部32px渐隐位于 `.thread-scroll-container` 内的非交互 sticky 容器，处于 footer 之外；旧 CSS 与 status 都遗漏它。
2. 主内容顶部另有40px `_MainContentTopFade_` 装饰，同样沿用原生不透明底色假设。
3. 原模拟页面只有 footer 底板，缺少独立渐隐分支；成功选择器和验证范围共享盲点。
4. 原生端仅接受少量 renderer 成功字段，未独立约束全部图层检查，也未完整输出逐页诊断。

## 实现

- `wallpaper/wallpaper.css` 定点处理 footer、已识别的底部 sticky fade 与顶部 fade 及其伪元素；清除装饰背景、阴影和 backdrop。使用零权重分支聚合，避免单个复杂分支抬高全部规则的覆盖权重。
- composer、代码、菜单、弹窗、输入元素和编辑区域被排除；布局、点击事件、宿主颜色变量与输入区自身 mask 保持。
- `wallpaper/renderer.js` 增加 `footerFadeSurfaces/footerFadeClear`、`topFadeSurfaces/topFadeClear`、`decorationEffectsClear`、`unsupportedDecorations`。对已知装饰检查背景、有效伪元素、阴影、backdrop、filter 与 mask；不主动清除未知 mask/filter。
- 独立检查已知 sticky 容器、footer 直接子层以及滚动区的背景/fade 候选。未知绘制层返回固定分类并使应用检查失败，不能因成功选择器匹配数为零而自证无问题。此扫描有明确结构边界，并非任意页面全部视觉遮挡检测器。
- `Native/Wallpaper.swift` 独立检查真实 Boolean、合法计数、完整透明表面覆盖、全部图层标志、未知装饰列表及页面版本一致性。旧版不完整报告、部分失败、空页面集合或混合版本不再作为成功。
- apply 的不合格结果、明确 renderer 异常和独立复查失败保留已处理页面、失败页索引与未核查数量，并停止后续页面。异常状态不可用时明确标记，不转发异常原文、页面文字或私有图片数据。
- `preview.html` 与 `test-wallpaper.mjs` 重建真实分支结构，并保护模拟菜单和输入区内部渐隐；测试使用独立临时 Chrome profile。
- 更新 README、项目规则和当前版本；为0.7.0历史验收追加更正，保留其历史执行事实，不将其继续当作全部底部装饰已通过的依据。

## 本轮验证

| 范围 | 结果 | 证据 |
| --- | --- | --- |
| Native 纯校验 | 97项通过，包含缺字段/数字冒充Boolean/数量不一致/未知装饰/混版本/部分应用失败报告 | native-validation.log |
| 旧版缺陷复现 | 使用本轮快照的真实0.7.0 renderer/CSS；applied=true时上下渐变仍存在 | fixture/report.json；fixture/00-baseline-fade-0.7.0.png |
| 隔离浏览器回归 | 15组全部通过 | fixture-run.log；fixture/report.json |
| 故障反例 | 恢复上下渐变、注入伪元素/阴影/backdrop、父选择器漂移均被检测；恢复后成功 | fixture/report.json |
| 输入与生命周期 | 深浅色、宽窄、动态新分支、多行、滚动、焦点、命中、菜单/代码/输入mask保护、失败回滚、dispose、CSP通过 | fixture/report.json |
| 隔离进程清理 | 自己启动的Chrome退出、临时profile删除、HTTP服务关闭 | fixture/report.json cleanup |
| 构建与统一安装 | 0.7.1/build8，签名及产物核验通过 | build-install.log |
| 安装唯一性 | status=current；1个安装应用、0个dist应用、1个登记路径 | installed-check.json |
| 原场景实机 | 同一MOSS会话、相同1512×889点/DPR2；底部暗带及顶部装饰渐变消失 | before-moss-live.png；after-moss-live.png；对应live-facts.json |
| 输入框实机对照 | 位置/尺寸/底色/圆角/阴影/pointer-events及内部mask一致 | final-comparison.json |
| 最终实时状态 | version=0.7.1；applied=true；footerFadeClear/topFadeClear/decorationEffectsClear均true；verificationIssues为空 | final-status.json |

15组含原11组、3组新增必跑检查及1组可选历史基线检查。本轮使用 `--baseline-dir` 执行了历史检查。4张新版模拟截图覆盖1512×889与840×900的深浅主题；另有1张旧版缺陷截图。状态面板、阅读卡片与模拟菜单均属于测试页面，不是向真实宿主添加的产品组件。

伪元素反例先检查真实计算背景仍为渐变，再断言失败，防止故障被正常清理后出现无效反例。输入测试没有向真实会话输入或发送消息；不据模拟输入宣布真实中文输入法完成验收。

## 真实页面前后数据

| 对象 | 修复前 | 修复后 |
| --- | --- | --- |
| 底部渐隐位置 | x186.5/y739，1167.5×32 CSS px | 相同 |
| 底部渐隐 background-image | 深色→透明 linear-gradient | none |
| 顶部渐隐位置 | x340.5/y44，1167.5×40 CSS px | 相同 |
| 顶部渐隐 background-image | 深色→透明 linear-gradient | none |
| 输入框根位置与尺寸 | x402.25/y771，736×98 CSS px | 相同 |
| 输入框底色/圆角 | rgb(54,54,54) / 22px | 相同 |
| 输入框内部滚动mask | 宿主原生渐变mask | 相同 |
| 底部额外绘制带独立检查 | 1 | 0 |

实际切回原截图会话取证后，已返回“检查项目问题”会话。前后宿主为同一 `/Applications/ChatGPT.app`、PID6822、回环端口56667。本轮没有退出或重启宿主。有限helper应用用时约0.715秒；最终只读状态检查约0.444秒，不将单次测量表述为性能基准。

新安装包在应用前读取旧0.7.0页面时已返回 `not-applied`，列出缺失的 fade/effect 字段；应用新版后全部通过。这是新原生判据实际拒绝旧不完整报告的运行证据，见 installed-pre-apply-status.json 与 apply-installed.jsonl。

## 安装与源码一致性

- 唯一安装路径：`/Users/guanxueliang/Applications/阿舟启动 Codex.app`。
- Bundle ID / executable：`local.azhou.codex-startup / AzhouCodexStartup`。
- 包树SHA256：`2a2831efa487d88f86c4f91aacc7448042179764c6e959aa0dd7ecb9123ce467`。
- 构建输入SHA256：`23e98e50bdaae75a79d41aeed5d1f867e12f0e32dcd8811adcf30364d0374f09`。
- 与此前安装标记比较，仅 Native/Wallpaper.swift、build-macos.sh、verify-artifacts.py、renderer.js、wallpaper.css 五个运行构建输入发生改变。私有资产及启动动画输入字节未变。
- 启动动画7.8秒流程本轮未重新录制；本轮实际运行验收针对最终安装包的壁纸helper与真实页面，不将历史动画录像称为新证据。
- 工作基于现有 main 工作树与既有未提交改造，保留原有工作。本轮不自动 commit/push。

## 验证边界

真实视觉对照覆盖当前深色1512×889窗口；未改变用户真实主题或窗口大小。浅色、窄窗、多行及故障注入属于隔离模拟验收。图片cover裁切、原生像素放大和全场景文字对比度仍保持0.7.0审计中的边界，不因本次暗带修复宣称全部视觉质量通过。

同类检查聚焦当前已核实的装饰结构，未来宿主完全改名或重新组织未知容器仍需实机复查。没有新增常驻observer、动画循环或服务。调试端口仍属于宿主进程，helper退出不等于端口关闭。

## 复核命令与证据位置

证据根目录：`.local/evidence/20261025-footer-fade-fix/`。源码快照、私有截图与日志保持Git忽略。

```sh
node tools/test-wallpaper.mjs --image wallpaper-scene-q-v3.png \
  --baseline-dir .local/evidence/20261025-footer-fade-fix/source-before \
  --out .local/evidence/20261025-footer-fade-fix/fixture
python3 tools/install-macos.py --check
"$HOME/Applications/阿舟启动 Codex.app/Contents/MacOS/AzhouCodexStartup" --wallpaper-status
```

浏览器CDP截图接口在当前宿主上超时，未把失败截图当作验收。本轮实机截图通过已核实PID的系统窗口号截图取得，原始尺寸3024×1778；review JPEG仅用于快速查看。
