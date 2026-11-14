# 宿主防腐层设计

## 目标与限制

用户要求宿主或 agent harness 更新不能对皮肤造成毁灭性影响。设计目标是把变化限制在宿主适配器，失配时关闭受影响的皮肤能力并恢复原生可操作状态。不能保证未知宿主更新永不破坏兼容，也不能靠宽泛选择器继续注入来掩盖失配。

本层保护 Codex 与 DSH 运行时边界。pstack 只是开发流程工具，不进入运行时依赖，不为本功能升级、修补或重配。防腐层不修改官方宿主、签名、权限、数据或其他插件。

## 复用现有边界

当前 `Native/SkinHostContract.swift` 已包含宿主身份、版本、build、能力证据和拒绝原因。`extension/codex-page-adapter.mjs` 已隔离主页面、主题 token 和设置环境。`extension/hosts/dsh.mjs` 有独立宿主入口。方案扩展这些边界，不另建通用 Coordinator 或插件框架。

仍存在泄漏。基线 `wallpaper/apply.js` 的 fallback 直接识别 `data-app-shell-*`。P10 先审计选择器、路由、token、存储、CSP、生命周期与原生窗口细节的所有消费者，把宿主知识迁入相应适配器，并迁移调用方后移除旧 fallback。不得只新包一层名称而保留核心中的猜测逻辑。

## 稳定能力契约

以下是设计形状，不声称当前 API 已提供。

```text
HostBinding = hostID + appVersion + appBuild + verifiedIdentity
AdapterBinding = adapterID + adapterRevision + contractSchema
PageBinding = targetID + connectionGeneration + documentGeneration
CapabilityReport = bindings + capability + supported|unsupported|unverified
SurfaceMap = mainWorkspace + sidebar? + header? + composer? + auxiliaryPanels[]
Appearance = resolvedTheme + locale + validatedColorTokens + reducedMotion
WorkspaceProof = bindings + supportedSurfaces + settingsProof + wallpaperResult
HostFailure = identityMismatch|unsupportedVersion|ambiguousPage|missingSurface|
              storageSchemaUnsupported|cspRejected|staleEvidence|ownerConflict
```

动画、主题和壁纸核心只使用标准能力、只读外观和不透明的已验证区域句柄。核心不接受 Codex URL、任意CSS选择器、CDP objectId、DSH slots 或 NSWindow 作为通用数据。宿主专用 DOM、原生几何及存储接口只在各自适配器内解释。

契约按能力拆分。壁纸、整窗材质、设置快照、早期遮罩、原图标触发和安全恢复分别报告，不能用一个 ready 布尔量代替。缺少可选侧板只停该侧板皮肤，缺少当前主页面或设置权威证明则不开始相关注入或个性化播放。

保持已安装协议与命名空间的迁移兼容。历史协议字符串不能为美化命名直接改掉。新字段和枚举须一次迁移全部生产消费者、回执和测试，未知schema明确拒绝。降级不写回未知设置格式，不删除用户主题。

## 版本与能力同时验证

宿主版本命中已验矩阵只是候选适配器选择依据，不是运行成功证据。应用签名与来源、version、build、adapter revision、schema以及当前页面代际全部绑定到能力证据。内容形态与实际样式效果还要在运行时核验。

宿主升级、进程重启、页面替换、CSP改变或适配器更换使对应旧证据失效。旧ready不得跨代际复用。未知版本默认不启用未经证明的侵入式主题能力，只保留已验证的原生激活与有界退出。不能仅看版本字符串前缀就把未来版本加入支持范围。

选择器注册表按已验证宿主构建维护，注明语义、唯一性、支持页面、拥有者和失效条件。禁止自动放宽为全局main、任意div或第一个匹配。多个主页面或同名区域必须拒绝歧义。DOM夹具仅含结构，禁止采集聊天正文或用户文件内容。

## 失败安全与恢复

在修改样式、属性或创建覆盖层前记录自身所有权和恢复依据。能力失效时移除仍归自己所有的样式、节点和监听器，解除自有遮挡，停止自有音频与动画。保留用户宿主进程和设置，不能杀宿主或反复抢焦点。

资源清理幂等。晚到事件不能重建覆盖、重复应用主题或重新激活窗口。新宿主已改写的属性不按旧快照覆盖回去。另一主题或插件占有同一名称时停止该能力，不删除对方节点。

原生底板与DSH早期gate各有独立watchdog，不依赖可能根本没加载的客户端finally。全部阶段消耗同一个绝对总期限。失配时优先恢复可输入、可导航的官方界面，显示克制且可诊断的“不兼容，已停用皮肤”状态。恢复入口不得依赖已经损坏的主题UI。

设置快照的已接受内容与当前工作区就绪分开处理。页面变化使workspace proof失效，不强制重播已接受快照。未知存储schema则停止读取个性化配置，不以默认值覆盖原记录。

## 兼容矩阵

每行至少记录宿主ID、平台、应用version与build、身份校验、adapter revision、contract schema、各能力状态、单元契约结果、真实版本验收和回退证据。日期与精确候选不可省略。矩阵记录在当前支持文档的受审附表，不增设竞争性的支持权威。

DSH web与desktop分行，Codex各实际构建分行。当前未知版本先记unverified，不造出“最新版通用支持”。宿主自动升级后重新探测并仅恢复已证实能力。宿主范围变动需同步 `docs/support-matrix.md`，不得只更新内部fixture就宣称受支持。

## 升级契约与发布门禁

P10覆盖以下故障注入与回归。

- 选择器删除、重命名、嵌套结构变化和多个主页面。
- Pet、mini、detached路由与正常工作区同时存在。
- 颜色token缺失、无效值、样式被CSP拒绝和另一主题冲突。
- 设置schema更新、读取失败、大快照中途断开及错误摘要。
- 旧回执、旧build、旧page generation和晚到完成事件。
- 宿主升级中重连、退役页面重现和适配器版本变化。
- 重复安装、应用、停用和卸载，只撤销自有资源。
- 注入失败后官方输入、发送、导航、菜单与窗口操作仍然可用。

契约测试验证标准输入输出与故障分类，不只断言某个选择器字串。边界检查禁止宿主选择器和传输对象重新进入动画或主题核心。变化前后真实宿主版本都需生产入口smoke、完整交接录屏和失效恢复验收。

发布门禁要求精确版本矩阵、版本漂移探测测试、失败安全测试、回退记录、视觉审阅及仓库必需检查通过。未知或未测构建不能复用旧通过结论。若无法获得新宿主，暂停相应兼容声明与发布能力，不阻止无关文档或已验证宿主工作。

防腐层的完成指标是升级失配影响被限制在明确能力，并可验证恢复原生操作。它不是“永不受上游变化影响”的保证。

## 首个真实升级案例

P10建立共享边界与故障fixture，P05以 [DSH rc.1到rc.3](DSH-UPGRADE-CASE.md)落实真实版本漂移、能力失效与回退。新版在官方nightly发现但未下载实测。多个profile共享插件实体，不能当隔离环境。不修改DSH官方源码以通过适配。
