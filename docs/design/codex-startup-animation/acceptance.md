# 验收设计与本次文档交付记录

2026-10-27 更新：T08/T26 的设置入口按[冷启动验收修订](host-acceptance-fixes.md)执行，旧快捷键不再拦截；其余适用验收仍需分别留证。

本文分开记录未来实现的验收计划和本次实际执行结果。需求入口见[详细设计](detailed-design.md)，具体字段见[运行契约](runtime-contracts.md)。未经实际执行的项目均为 Planned。

## 1. 未来实现验收矩阵（Planned）

| ID / 需求 | 输入、操作与环境 | 必须观察到的结果 | 最小证据 / 失败动作 |
|---|---|---|---|
| T01 / FR01 | 官方应用未运行；从唯一启动 App 冷启动；分别在模拟与获准真实宿主执行 | 可信主窗口中出现 iframe；installed→ready可区分；辅助ready后退出；12s后iframe消失 | 页面状态、进程/端口记录、窗口录像；阻断同窗口声明 |
| T02 / FR02 | 官方应用已有编辑中会话，分别有/无调试端口；再次打开入口 | 激活同一真实PID，不新建实例、不退出、不默认重播；日志为activated而非ready | PID/进程与页面只读快照；任何重启或会话中断阻断 |
| T03 / FR03 | 固定素材按3个窗口尺寸和两种DPR播放；在0、1.15、4.18、4.74、5.08、7.18、7.43、11、12s采样 | 阶段、左到右描线和颜色配准符合RC3；百分比是动画进度 | 同时钟采样和逐帧截图；不以源码常量代替画面 |
| T04 / FR03 | 首秒、转场、末秒分别点击skip或按Esc，重复发送complete | complete幂等，下一帧进入清理，父iframe在事件处理后移除；官方输入可点击/键入 | DOM/事件日志与真实交互；残留遮罩阻断 |
| T05 / FR03 | 启动前开启reduce；播放中切换reduce | 没有碎片旋转、闪光、粒子位移；仍可跳过；完成语义不变 | matchMedia fake + 系统真实设置复核；违反无障碍要求阻断 |
| T06 / FR04 | PNG/JPEG/WebP；0 bytes、坏解码、伪MIME、恰好30MiB、超1byte、极端尺寸、超过序列化上限 | 有效输入成功；无效输入固定错误，不写库；busy期间不能并行提交；输入URL撤销 | importImage对外结果与数据库读回；漏校验阻断 |
| T07 / FR04 | 横/竖/方图，透明图，纯色/低边缘图，固定梯度与边缘fixture | 头像512²、背景1536×1024；同裁切配准；空轮廓拒绝；点数/坐标有限且有上限 | 输出尺寸、路径与配准截图；不要求Vision/Sobel逐点相同 |
| T08 / FR05 | 完成后父页面按⌘⌥B；播放中焦点在iframe内再次按；改图、文字、强度，保存；完整刷新后再次接入 | 两个焦点上下文都可打开且同页只有一份面板；transaction complete后新值持久；旧设置iframe销毁，新runId重播 | 键盘真实派发、事务故障fake与IDB读回；旧completed不能冒充新轮成功 |
| T09 / FR05 | 修改后×/Esc关闭；点击恢复默认后取消；busy时按Esc，再令操作超时后按Esc | 非busy取消丢弃草稿且不重播；busy的Esc不关闭/提交；超时恢复可取消；原值完整 | committed前后比较；任何静默覆盖或无限busy阻断 |
| T10 / FR04–05 | IDB读失败、quota/abort；应用候选解码失败；持久化后wallpaper apply失败 | 读失败保留记录并用默认；写失败保留旧值且不重播；已提交后壁纸失败显示部分成功 | 注入故障的行为结果；混称“已保存/未保存”阻断 |
| T11 / FR06 | 深/浅色，长聊天滚动，侧栏、菜单、代码块、输入框，窄窗；未知装饰DOM | wallpaper实际解码与surface/decorations验证；官方可读可操作；未知结构不全局透明化 | 模拟反例 + 获准真实窗口截图；不把模拟结果说成真实通过 |
| T12 / FR06 | 播放中/设置中/完成后restore；重复dispose；宿主在安装后修改某style | ownediframe/样式/监听/URL释放；数据保留；条件恢复保留宿主新值；CDP端口仍明确报告 | 快照差异、资源计数和交互；任意宿主修改丢失阻断 |
| T13 / FR07 | 错BundleID、正确ID但错误签名主体、自身App、嵌套Helper、symlink真实路径 | 注入前拒绝；不执行可疑包内运行时 | 原生validator fake / 隔离fixture；任一放行阻断 |
| T14 / FR07 | wildcard/远程监听、错UID/PID、已释放端口被抢占、WebSocket错端口/凭据/browser路径/redirect | 拒绝连接或及时关闭；不向未知目标发送payload | transport fixture、请求发送计数为0；任一越界阻断 |
| T15 / FR07 | quick-chat/avatar/mini页面；另一iframe伪造同type/runId；旧frame迟到；未知action | 不选辅助页；伪造消息无副作用；新frame生命周期不受旧回调影响 | 页面/消息对外测试；只测字符串匹配不足 |
| T16 / FR07 | 正式包导入本机图、保存、播放、恢复；观察此功能新增的资源请求与日志 | 新增外部请求0；图片、聊天、完整脚本日志0；无本机资源HTTP服务 | 自己资源请求分类与脱敏日志检查；不将官方自身联网误算为本功能 |
| T17 / FR08 | never-ready、malformed-CDP、连接关闭、丢complete、加载异常 | 父25swatchdog释放iframe；原生60s总预算内退出；pending全拒绝；官方可用 | 可控时钟/故障transport；不得等测试真的卡满一分钟才定位 |
| T18 / FR08 | 同版本二次install、未知全局、旧已知壁纸、refresh、新窗口、dispose时解码回调迟到；显式helper status/apply/restore与自动接入并发 | 幂等或owner-conflict；status只读，已有startup时apply报startup-active，restore清完整控制器；PID锁串行，无后台重注入，disposed后不复活 | 模拟宿主状态转移；版本混用或双控制器阻断 |
| T19 / FR08 | 默认与允许上限素材各播放并设置重播10次；完成后观察5s | rAF/纹理在完成后释放，无持续增长的URL/iframe；测JS/rAF与系统内存分别报告 | RC6门限；无系统测量时内存标未验证，不能编造PASS |
| T20 / FR09 | 同App --preview，官方应用已运行但无端口；浏览器独立预览 | 不连接/启动官方应用；时间轴/暂停/重播有效；存储与正式隔离 | 进程/请求记录和读回；把预览当真实接入阻断 |
| T21 / FR10 | clean build、篡改payload、改变新runtime输入、source-only无私有图 | 现有核验检测变化；新runtime_paths/build_inputs参与计划；缺素材明确失败 | 构建/inspect隔离结果；不得绕过校验以出包 |
| T22 / FR10 | 包安装器隔离fixture；已有更高版本、未知来源、冲突登记、运行中项目App、官方App；以前向修复版本回退到旧行为 | 拒绝直接降级；失败事务恢复旧安装；高于当前版本且来源有效的修复包可通过正常校验；不删未知或官方App；Hub只管自己的测试安装 | 既有安装suite及新增相关断言；生产安装必须另获授权 |
| T23 / FR10 | 全仓verify、manifest/lifecycle、Pet既有回归，支持和授权文档核对 | 代码改动对应门通过；Pet未受损；双语README与支持声明一致 | `scripts/verify.py` + 必要专项；许可未清不发布 |
| T24 / FR11 | 缺startup资源、篡改install.js/默认裁切/轮廓、增加未进INPUT_FILES的新源码、fixture:true生产载荷、只改manifest版本 | 新build/inspect同时核对源码和生成资源，拒绝缺项/错摘要/协议/私有输入；正常单载荷可核验 | 新build suite及隔离bundle；只验证文件存在不算通过 |
| T25 / FR11 | 旧版原生fixture、新版ready、热激活、早期skip、无complete日志、坏事件字段、非零退出却伪success | 按已验证App版本选择schema；新ready不需要原生fade/complete；activated不算接入；非零/不完整事件不能成功 | adapter assessment行为测试；保留旧snapshot评估与清理 |
| T26 / FR11 | IDB未load先Esc/⌘⌥B，ready→complete快于轮询，保存后重播超时，dispose时事务/解码迟到，跨页并发保存，样式/data/Blob被CSP阻断 | loading skip能释放且原生不重装；双侧loading守卫；所有轮次统一timeout；迟到不复活；并发冲突不覆盖；样式/图被阻断不假ready | controller/transport/真实浏览器三层；显式核对RC1/4/7结果 |
| T27 / FR12 | 按固定候选构建完整走G2–G5，含下一次日常启动和用户正常官方重开 | gate与receipt可复现；唯一安装App行为与测试一致；恢复官方入口后不自动美化；没有假定许可或人类视觉已批准 | production-runbook现场回执；任何必需门not_run/blocked不得Production |
| T28 / FR10–11 | 新package内容已变，旧Hub-owned test-install仍要清理；旧source/snapshot缺失/未知owner | 只能用原freeze snapshot及receipt清理；未知来源保留，不从变化后的live源码加载核验器 | 既有test-uninstall隔离fixture；不得删收据/绕所有权消除失败 |
| T29 / FR12 | 已装新版直接装旧版；旧行为作为更高修复版重建；官方版本更新后重用旧PASS | 拒绝直接降级；合法高版本修复走正常核验；官方新版本标未验证，重做受影响真实宿主/视觉门后才能宣称支持 | 安装隔离反例+生产回执审查；不能通过改版本字符串跳过真实修复验证 |

每次真实宿主验收记录：H commit及工作树差异、payload构建输入、官方版本/签名身份、macOS、机器、窗口/DPR、素材来源、操作序列、页面状态与结果。原始截图、私有图、安装收据和路径放在 Git 忽略的本地 evidence；提交文档仅保留脱敏摘要与定位说明。

## 2. 执行入口与分层

下文`SOURCE_CHECKOUT`和`HUB_CHECKOUT`分别为实施者已按source-analysis§1核验的S源仓与Hub绝对根目录；执行前在本机设置并核对，不使用维护者个人路径。

命名/迁移前置单N复用现有验收ID，增加以下隔离场景：T21验证新`agent-skin`入口、canonical路径与manifest一致，旧输入plan在更名后不得继续授权；T22验证现有安装source标记的保留/接管顺序，无法证明来源时保持拒绝；T23验证公开说明、组件名与实际支持范围一致；T28验证更名后旧Hub-owned测试安装仍由原snapshot/receipt及核验器清理；T29验证更名不绕过版本检查。前置单完成不替代G5日常安装或真实宿主验收，更不表示其他AI工具已支持。

以下前两组是**现有**命令；新增测试路径在实现切片中建立后，再将真实命令补入回执，本文不伪造可执行入口。

```sh
# 源项目：三个既有Node行为测试，不启动真实官方应用
cd "$SOURCE_CHECKOUT"
node --test tools/extension.test.mjs
```

```sh
# Hub：全仓交接门
cd "$HUB_CHECKOUT"
python scripts/verify.py

# 安装器和Pet既有隔离回归；实际代码变更按适用性运行
python -B packages/codex-startup-animation/tools/test-install-macos.py
python -B packages/codex-startup-animation/tools/test-codex-pet.py
python -B packages/codex-startup-animation/tools/test-import-codex-pet.py
```

同窗口模拟测试必须运行真正的Page Controller和载荷，fake只替换官方DOM/transport。真实官方应用启动、安装、重启和设置写入必须在未来实现阶段按当时授权执行；本次没有这些操作。

新测试路径与CI接线由[执行指南§2.3](implementation-guide.md#23-新测试入口实施时创建)规定；生产现场步骤由[生产操作](production-runbook.md)规定。新增T24–T29是必须实现或实际执行的验收要求，不把这些行的存在当作测试已实现。

验收分层：协议与图像单元测试证明确定性规则；模拟宿主证明DOM/消息/清理；真实窗口证明集成与操作；视觉评审证明身份、构图、节奏和可读性；安装测试证明归属与恢复。一个层次不能替另一个签字。

## 3. v0.1文档交付记录（历史）

| 项目 | 实际结果 |
|---|---|
| 用户授权 | 初始请求只产出供Hub重实现的详细设计；允许主工作区只新增文档；最终明确采用S的CDP同窗口方案 |
| 工作区 | Hub主工作区；未创建任务分支、未commit/push；Treehouse v3.1.0获取lease失败：10个工作区都in-use或dirty，max_trees=8；未修改池配置、回收或清理其他工作区 |
| 源状态 | S HEAD与干净状态见source-analysis §1；三个源Node测试本轮执行，3/3通过 |
| 模板与写作 | 使用super-arch-doc feature-detailed-design Baseline；new_doc.py在临时文件实例化模板；按writing-for-agents重组步骤与按需引用 |
| Hindsight | 已搜索、列页并读相关initiative；返回正文只有Generating content，未作为行为证据 |
| 图覆盖 | S graph Verify与全部依赖路径coverage；tools/docs/CSS缺口用源码读取补齐；H核查以当前代码为准 |
| 架构方向变更 | 初始原生建议被用户最新CDP决定替代；所有目标章节以同窗口CDP为准，不保留双路线实现开关 |
| 文档确定性校验 | 五份文档的配平、链接、图注/变更记录与空白检查通过；本机未检测到PlantUML CLI，真实渲染门跳过 |
| 独立回源与评审 | 结果见[REVIEW.md](REVIEW.md) |
| 真实/视觉/安装/发布 | 本次均未执行；目标代码未实现 |

### 校验结果

| 实际命令 / gate | 退出码 / 结果 | 证明范围 |
|---|---|---|
| S `node --test tools/extension.test.mjs` | 0；3/3通过 | S既有协议行为，不证明目标实现 |
| H `scripts/verify.py` 首轮（本机Python 3执行） | 1；8 gates中7项通过，repository policy失败 | 本轮新增文档最初的绝对链接、示例命令和未建REVIEW链接问题；之后均已修复 |
| 首轮中的unit tests | 0；584项通过 | 现有Hub行为 |
| 首轮中的package/lifecycle | 0；manifest通过，model-router42项、startup installer26项通过 | 现有包和隔离安装行为；未安装真实App |
| 首轮中的benchmark integrity与whitespace | 0 | 既有benchmark接线、工作区/暂存区空白；不是模型或视觉成绩 |
| 修复后的 `scripts/check_repository.py`（本机Python 3执行） | 0；1576 public files checked | 首轮唯一失败gate的修复复验；未重复运行无相关代码变化的测试 |
| `verify_doc.py <document> --plantuml-cli`，逐份5文件 | 全部0；render gate提示skipped | 配平、文件链接、图注入账、变更记录、空白；不证明PlantUML已渲染 |
| 独立技术问题修订复核 | 无剩余已报P2/P3 | 仅文档协议闭合，不证明运行 |

本轮组合证据覆盖仓库8项gate：首轮7项加修复后policy；没有声称首轮整条命令退出0。最终只新增5份文档，现役运行代码、manifest、安装和私有素材未改。实际执行记录使用本机的python3；可移植命令示例按仓库策略写python。

### 下一步

维护者评审Draft的Interface、默认素材与目标支持版本；开始实现后先做详细设计§14切片A，取得可信主页面和最小可清理覆盖层的证据，再进入动画和设置。

## 4. v0.2生产设计校准记录

| 项目 | 本轮实际结果 / 证据边界 |
|---|---|
| 授权与产物 | 用户要求继续回源检视并补到可指导agent进入生产；更新原5份文档，新增implementation-guide和production-runbook；未改目标运行代码或安装配置 |
| 回源深度 | S/H仍为source-analysis§1的HEAD；图索引S generation14:28:22Z、H14:56:59Z，依赖路径coverage核验；源码与集成adapter直接读回，不把图无缺口当完整性证明 |
| 源语义修正 | 明确loading提前skip、子frame loading守卫、预热/ready顺序、保存后watchdog和realm/CSP条件；有意改进均与源事实分开 |
| 实施闭合 | 6张A–F工作单含输入、Owner、依赖、测试面和完成判据；FR01–FR12、T01–T29和G0–G6无缺号；新测试入口明确为Planned |
| 集成闭合 | 固定startup资源和manifest、目标版本同步点、INPUT_FILES及runtime_paths、inspect与新旧adapter schema；ready不再冒充complete |
| 只读宿主元数据 | Info.plist和codesign描述读取：官方26.1021.31345/build21828，Team2DC432GLL2；未深验签名、启动、连接或注入真实Codex |
| 文档确定性门 | 7份文档的verify_doc.py配平/链接/图注入账/变更记录/空白检查通过；最终结果以此节后实际校验为准 |
| 真实PlantUML渲染 | 复用本机已有@plantuml/core1.2026.6和其Viz引擎，在chrome-devtools-axi隔离Chrome中渲染4/4，无错误，截图目检无截断或重叠；未安装CLI或修改系统配置 |
| 渲染定位 | 截图留于维护者本地证据目录，不进入Git；SVG仅为临时校验，权威图仍为Markdown内PlantUML |
| 本轮全仓门 | 本机Python3执行scripts/verify.py，退出0，8/8 gate通过：repository policy1578文件、584单元、42 router、26 installer及benchmark wiring/whitespace；均为现有代码/隔离测试，不证明新设计已实现 |
| 未重复项 | S三个Node测试代码未变，引用v0.1结果；Pet运行时未变，不扩大本轮专项；未作真实宿主、视觉资产或生产安装验收 |
| 独立复核 | 源行为explorer+生产契约reviewer；结构5/5、技术4/5；已报P1/P2/P3修订后定向复核全部闭合，见REVIEW§5 |
| 当前结论 | 设计可作为agent实施基线；当前目标实现仍Planned，G1–G6未执行，不声明Production。G0的设计批准仍由维护者对具体范围决定 |

下一步：新实现agent从implementation-guide§1接手，先执行工作单A。只有固定构建、真实支持版本、视觉/资源与日常安装证据满足production-runbook的门，才可把限定本机使用标为Production；对外分发另过许可和发布门。
