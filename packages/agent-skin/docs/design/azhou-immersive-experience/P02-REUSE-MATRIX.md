# 现有能力与参考项目融合矩阵

本矩阵补充P02动态媒体合同。用户要求全面对齐参考组合、仅替换Azhou IP，同时融合现有能力：能合法引入源码就引入，能复用就复用。不是推倒重写，也不是只复制视觉。

参考固定版本：Dream 6fc42df48a6a5365011f55cc349e20c038e56d1d，Dragon c63a203e5857e85fb3c8a9891eddb570e7a27b54。引入时使用完整提交ID、文件摘要、原许可证及notice，保留原样vendor与明确适配差异；不从浮动分支复制。媒体与软件授权分别核验。

| 能力 | 决策 | 源码/素材证据 | 融合与防腐约束 | 验证 |
| --- | --- | --- | --- | --- |
| Hub设置、不可变快照和保存取消语义 | 保留复用 | Native/Wallpaper.swift、extension/renderer.mjs及settings测试 | 沿用现有命名空间和generation，不另建播放器偏好库 | 真实保存/取消/重开、快照晚到与代际失效 |
| 原生cover、workspace协调、显式退出与清理 | 保留复用 | 已合入PR469（fa8967b3）与NH契约 | 继承已合入修复并核对当前差异，不照搬旧实现；视频只是presentation实现，不另造controller | #406/#431等价，绘制/媒体失败后真实输入，释放后资源 |
| DSH host扩展和启动gate | 保留复用 | extension/hosts/dsh.mjs、dsh-startup-gate.js | video/主题走同一稳定能力接口，DSH源码不可改；共享载荷不可实验 | 真隔离rc.1/rc.3，Web和Desktop独立 |
| 阿舟角色资产 | 保留复用 | 已获授权的 assets/azhou 素材 | 新全身动作保持角色特征 | 角色身份审阅 |
| 图片元数据解析 | 复用已有vendor | Hub vendor/dream-image-metadata.mjs及许可证 | 已有MIT依赖，不再复制第二套；先比版本与补丁 | 既有图片格式/尺寸/损坏输入测试 |
| SafeCSS验证及策略 | 源码引入候选 | Dream runtime/safe-css-validator.mjs、safe-css-policy.json，MIT | 分别引入验证逻辑与编译映射；compileRuntimeCss含root→body和composer-toolbar宿主class桥，须归适配边界，不整体视为宿主中立；不扩大权限 | 恶意CSS/外链/超限、应用时再次验证、合法参考主题兼容 |
| 主题包格式/媒体验证 | 源码引入候选 | Dream runtime/theme-package-validator.mjs，MIT | 该文件验证已解压目录并写stage，不负责ZIP安全解压；manifest.sig为signatureIgnored，不证明真实性。Node依赖留在导入服务；10MiB图像限制不当视频传输上限 | ZIP穿越/符号链接/重名/损坏/超限、拒绝后当前主题不变 |
| 主题透明度规则与库事务 | 部分源码引入、存储适配 | runtime/theme-preferences.mjs、ThemeTransparency.swift、SavedThemeLibrary.swift | theme-preferences仅只读偏好，SavedThemeLibrary也仅去重/排序；删除恢复须另审SavedThemeDeletion与导入事务；复用优先级及范围规则，不写CodexDreamSkinStudio目录，接入Azhou设置/owner合同 | 0/中间/100/跟随主题、并发切换、删除到废纸篓及恢复 |
| 全窗CSS和工作面外观 | 按授权代码引入并适配 | Dream runtime/dream-skin.css、renderer-inject.js，MIT | 视觉规则可复用；DOM发现/路由/token/注入归宿主adapter，不整体复制injector或CDP启动器 | 全页面/窗口、Dot、隐藏缓存、动态节点、未知结构fail-safe |
| Dragon时间与音量配置、淡出曲线 | 局部源码引入 | LauncherConfiguration.swift与测试，MIT/Foundation | 复用有限值/时间顺序规则；Hub animation.js已有smoothstep，不重复vendor数学函数；重新校准Azhou成片，不照搬品牌/路径/等待总时长 | 损坏媒体、非法时间、自然结束/hold恢复/跳过 |
| 视频停滞检测 | 局部源码引入/适配 | PlaybackProgressWatchdog.swift及测试，MIT/Foundation | 区分主动hold与真正停滞；不能重置Hub总期限或新开25秒隐含预算 | 解码不前进、恢复不追帧、hold不误报、期限统一 |
| AVFoundation播放器和窗口几何 | 提取组件，不另起整套App | Dragon macos/main.swift、src/macos/main.swift，MIT/AppKit/AVFoundation | 在现有Native owner下承载；保留真实身份检查、窗口策略与可操作证据，不用isFinishedLaunching当ready | fill/fit对应平台模式、四角/多屏、焦点不被抢，退出停止音频 |
| 入口监听、安装卸载和恢复 | 复用机制，整合现有安装器 | Dragon可选LaunchAgent脚本与入口记录，MIT | 不默认覆盖Dock或官方包、不自动开监视器；自己的安装ownership+恢复记录统一 | 开关/并存/重复安装/卸载/用户改动后不误恢复 |
| Dragon电影/角色/音轨 | 仅参考，原创重建 | MEDIA_NOTICE明确MIT不扩展到角色和音轨 | 不抽取复用，不向生成服务上传原片做换脸；按自写运动描述及Azhou素材制作 | 完整动态质量、声音、许可与来源，逐帧身份连续 |
| Dream预设/截图与品牌 | 分类处理，不整包搬运 | macos/NOTICE | abstract demo有MIT范围，Gothic有贡献来源，Arina与相关截图明确排除；Azhou产品不用这些替代IP，删去赞助/推广配置 | 素材清单逐项许可，截图不是壁纸，无未请求网络推广 |
| Windows DWM与macOS交接 | 平台实现分离 | Dragon README/CONFIGURATION/MACOS | 保留对齐目标但不伪称相同机制；macOS不抄移动宿主做法，Windows能力另验 | 分平台真实窗口录屏、真实输入，未覆盖明确列出 |

## 引入与依赖门禁

- 保留原始来源、MIT全文、版权notice、完整commit、文件摘要、依赖清单和可重放适配差异。不是把来源头删掉再当原创。
- Hub旧panding999无许可历史实现不恢复；#441之后独立重写边界不倒退。pstack不改。
- 纯解析/时间规则可共用，宿主选择器/路由/设置桥/节点生命周期只能在adapter。适配输出绑定host版本/build/schema/page generation，未知能力不猜。
- 不照搬参考默认的全盘快捷方式扫描替换、宣传链接、账户配置、宽松路径或弱ready。安全差异显式记录，不用它暗减用户可见体验。
- 原功能与新媒体同步回归。新视频不是替代现有失败恢复、settings、Pet或安装器的理由；也不能因为旧功能测试通过就认定新动态质量通过。

路径以表内项目根为准。Hub路径相对packages/agent-skin，Dream与Dragon路径相对各自仓库根。此表为复用候选审查，不表示已vendor或逐文件摘要审核完成。GIF仅有有限透明表达，不等价于半透明通道。

## 固定来源复核

本轮只读审计核对以下SHA256。Dream四文件在runtime/macOS/Windows副本逐字节相同，只选runtime一份作为权威来源。源码审计不是已引入或运行通过。

| 文件 | SHA256 |
| --- | --- |
| Dream runtime/safe-css-validator.mjs | 98a626655a4167ba0bbbff5eab96e78de7a5a74371e4a4ff6d8ac15211e5b24e |
| Dream runtime/safe-css-policy.json | c784dd3a16d71395fca0b2695047395dc6f951f44df962284976faeb0b3ea551 |
| Dream runtime/theme-package-validator.mjs | 8f249d726367c383d8c5894890e2b6d1c3b56a7282d7441a80cfb6470955b5f8 |
| Dream runtime/theme-preferences.mjs | ca6ecbd2337e9cc471bfd1c62b7b84c975670a5a5c6adcb4214a4dda52f2c326 |
| Dragon macos/Sources/DragonCodexBootCore/LauncherConfiguration.swift | e7d99673b62fce6f660aa33321adb83a0231440ec8e8be403f65a267ea5f84b9 |
| Dragon src/macos/PlaybackProgressWatchdog.swift | 40fa10d84823fa9ee99ece2127c089006003c482eb2a2615fdf1b8540ba22c8e |

SafeCSS policy JSON只是执行契约镜像，不能单改JSON期待运行规则变化。偏好读取的fs.open(r)不等于O_NOFOLLOW；Swift原子写入不等于多writer事务。watchdog将任意方向进度变化视为进展，须补时钟倒退、seek回跳、小幅抖动与总预算测试。现有StartupBudget已管总期限，不额外添加25秒。

可借鉴Dream safe-css-validator/theme-package-validator/theme-preferences测试及Dragon LauncherConfigurationTests、tests/macos-watchdog/main.swift。Dragon scripts/test-macos-standalone.sh先打包并签名，不当纯单测运行；提取纯watchdog测试到独占TMP再验证。逐项保留原MIT版权与媒体NOTICE，不把源码许可延伸到角色/音轨。
