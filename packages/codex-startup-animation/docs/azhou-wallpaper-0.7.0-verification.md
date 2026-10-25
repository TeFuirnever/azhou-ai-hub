# 0.7.0 / build 7 — Q版全景壁纸验收

日期：2026-10-24。项目：`/Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation`。

## 本轮目标与纠正

用户要求借用本机 `/Users/guanxueliang/Desktop/oh-my-ai/IP/azhou` 正式资产，将右下角人物背景扩展为完整场景；随后明确纠正：“为啥不用Q版了？”

第一轮普通动漫比例全景偏离了既有Q版设定，未接入运行中的壁纸。最终重新以正式 `azhou-chibi-pet/v1.0.0/images/04-working.png` 为造型、比例、画风主参考，女性v2正式身份图仅用于核对身份细节。保留大头、小躯干、短四肢、暖棕眼、橙色卷发、狐耳单尾、观者右侧发饰、狐脸胸针及白橙服装；场景扩展为完整实验室。

## 当前素材

- 文件：`assets/private/wallpaper-scene-q-v3.png`。
- ImageGen原生输出：1672×941，8-bit RGB PNG，2,249,930字节。
- SHA256：`566eee5034343bb8463fa684dc0b90fe3d2c5d8f2adde1c9d71356bf192acbcb`。
- 完整提示词与两张参考的来源、摘要：`assets/private/provenance/wallpaper-scene-q-v3.json`。
- 这是项目私有衍生图，未正式晋升为IP库资产。原参考文件摘要与生成前一致，未覆盖素材库。
- 启动动画仍使用正式Q版 `working.png` 和已校准的 `scene.js`；本轮未修改它们。最终安装包中的这两份文件与项目源文件一致，working.png与正式04-working.png逐字节一致。
- 旧 `working-v2.png` 留存。普通比例草稿只留在忽略的证据目录，不被构建引用。

## 实现

背景第二层使用 `cover` 等比铺满视口，横屏焦点60%、窄窗焦点88%；第一层为随宿主底色变化的阅读遮罩。移除了角落人物的宽度上限和无用resize监听。

保留0.6.1对真实 `data-thread-scroll-footer` 装饰背景的定点透明修复，输入框、菜单和代码块继续使用宿主自身底色。未覆盖宿主全局颜色变量。

renderer新增 `coverMatched`、`fixedViewport` 成功判据，报告源图尺寸、视口、DPR、铺放位置和实际设备像素放大比。构建与产物核验支持受限横向RGB/RGBA PNG，记录真实颜色类型、透明通道、尺寸、displayMode及各项摘要。

## 验证结果

| 范围 | 本轮结果 | 证据 |
| --- | --- | --- |
| 原生纯校验 | 42项通过；不代表实机视觉 | native-validation.log |
| 隔离模拟宿主 | 11组通过；深浅主题、1512×889与840×900共4张截图 | fixture/report.json、fixture-run.log |
| 原有保护 | footer透明、输入框/代码/输入保护、失败回滚、CSP与恢复通过 | fixture/report.json |
| 全景新增保护 | 图片实际层为cover/fixed/no-repeat；错误contain候选被拒绝，原API保留 | fixture/report.json |
| 资源清理 | 重复应用保持1个Blob、0个resize监听、1个style；dispose后均清理 | fixture/report.json |
| 正常构建安装 | 统一安装器成功，版本0.7.0/build 7 | build-install.log |
| 安装唯一性 | 1个安装应用、0个dist应用、1个系统登记路径，状态current | installed-check.json |
| 当前真实主界面 | 已应用并查看实机截图：全景延伸至窗口，Q版脸型、表情、工作姿态可辨，底部没有整条不透明装饰遮挡 | after-live.png、after-footer-layout.json |
| 输入框实机保护 | 更新前后均为rgb(54,54,54)，x556.25/y821、736×48点，位置、尺寸、底色一致 | final-facts.json |

模拟宿主的11组由原9组加全景覆盖、非cover回滚2组组成。模拟截图中的状态面板和阅读卡片是测试界面，不是向真实Codex添加的组件。

## 本机运行与安装

- 唯一入口：`/Users/guanxueliang/Applications/阿舟启动 Codex.app`。
- 身份：`local.azhou.codex-startup / AzhouCodexStartup`。
- 通过最终安装应用的有限helper接入，`applied:true`、`coverMatched:true`、`fixedViewport:true`、`footerBackgroundClear:true`。
- 宿主仍为原 `/Applications/ChatGPT.app`、PID80172、回环端口62554；本轮没有退出或重启宿主。
- 实机视口1512×889点、DPR2；实际图像设备像素放大比约1.8895。不是原生4K/Retina分辨率素材。
- 安装包树摘要：`ff75b32a7abbbb6c526e4f593a45d74a1bb689e127a6ea0474974e20f320aa9e`。
- 构建输入摘要：`5c108edbf72bfd0a94f800c3eb84abf079339a04902899e74aa8f207a626c6e3`。
- 安装来源指向当前项目。Git分支main，HEAD为`c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248`；工作区保留既有及本轮未提交修改，本轮未提交或推送。

## 范围与限制

全景铺满使用等比裁切，窄窗会裁掉部分环境；真实聊天气泡、正文、输入框可能覆盖人物部分区域，不能宣称所有窗口尺寸下全身无遮挡。窄窗fixture中的阅读卡片与状态面板遮住了人物大部分上身，因此该截图仅证明布局与裁切行为，不证明窄窗人物完整可见。

深浅色、宽窄窗口已做隔离模拟；真实主界面本轮视觉验收覆盖当前深色1512×889窗口。未为验收切换用户主题或调整工作窗口，也未重启当前会话。7.8秒启动动画本轮未重新播放；其素材与逻辑保持原样，历史完整播放验收见0.6.x与动效记录，不把历史录像称为本轮新录制。

## 证据目录

`.local/evidence/20261024-wallpaper-scene/`

包含source-before、生成提示词、fixture四张截图与报告、native-validation.log、build-install.log、installed-check.json、before/after-live.png、before/after-footer-layout.json、apply-installed.jsonl、final-facts.json。普通比例草稿的传输与提示词亦在此，仅作为被纠正的私有过程记录。私有图、生成载荷、应用和截图均保持Git忽略，不公开发布。


## 2026-10-25 后续复查更正

用户截图与当前真实DOM确认：本记录核对的footer底板虽已透明，但footer外另有32px底部渐隐层，主内容顶部另有40px渐隐层，均未被0.7.0的选择器和模拟结构覆盖。因此上表“底部没有整条不透明装饰遮挡”仅保留为当时记录，不再作为当前全部底部装饰已通过的依据。0.7.1将两类渐隐、漏检反例、原生逐页状态与真实前后画面对照列为本次验收范围，结果见 [0.7.1专项验收](azhou-wallpaper-0.7.1-verification.md)。历史测试结果不改写为本轮重新执行。
