# Agent执行指南：Agent Skin 首期 Codex 适配

本文件是[详细设计](detailed-design.md)的执行分支，全部新代码和命令为Planned。它不登记tracker状态；工作单完成情况写在实际任务回执中。只改文档时不执行下列产品实现、安装或宿主写入。

用户已确认产品名 Agent Skin、包名 `agent-skin`，面向 AI 工具的启动动画、壁纸和外观设置，本轮仅完成 Codex 适配。当前真实包目录和 Hub 入口尚未更名；下文现有路径仍指实际对象。命名/迁移前置单完成时同步修正未来命令与调用方，不新增其他宿主实现。

## 1. 接手与基线

1. 读取仓库AGENTS、详细设计§0–§4、source-analysis§1。运行`git status --short`并核对S/H HEAD；保留已有改动。当前S为`c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248`，H基线为`f6f309ccedf4f9d0f1febcd7958aee36729824b0`。变化只要求重查相关事实与接口，不得用旧报告跳过。完成条件：回执记录实际HEAD、工作树范围和差异影响。
2. 按[worktree policy](../../worktree-policy.md)取得实现工作区和durable lease，验证common-dir和归属后创建任务分支。本次文档专用主工作区例外不延伸为未来实现例外。完成条件：路径、lease ID/holder、分支可核验；拿不到时保留工作而不清理别人的工作区。
3. 选择§3第一张依赖已满足的工作单，读它的输入契约。通过真实Interface建立会失败的行为测试，再实现该切片。完成条件：红/绿命令、退出码、失败原因和新增行为对应，未把不存在的测试命令当现成入口。
4. 每单只修改其Owner范围。接口改变先更新runtime-contracts、消费方与测试再继续，不能以“内部实现”绕过调用契约。完成条件：相关T编号均有证据，交接字段齐全。

## 2. 构建与集成衔接

### 2.1 确定的输出与输入

保留Codex适配的Bundle ID、主可执行文件、唯一安装App和`.build/azhou-payload`；产品包/Hub组件更名的绑定与旧来源衔接先按详细设计§12处理，不能全局替换宿主身份。预览继续是同一App的`--preview/--smoke-test`。目标建议版本`0.8.0/build9`，实施前检查实际已安装最高版本；若不是严格升级则选择更高值。不是让运行时按版本自动切路线。

| 包内目标资源 | 来源 / 生成方式 | 核验责任 |
|---|---|---|
| `Contents/Resources/startup/install.js` | 新`tools/build-startup.py`封装Page Controller、Animation、Settings、授权默认图、轮廓和壁纸调用 | 当前本地输入生成；对完整输出检查24MiB上限；不得嵌外链或fixture开关 |
| `Contents/Resources/startup/manifest.json` | 同构建生成，`schema=1`、`protocolVersion=1`、App version/build、input摘要、每个产物路径/摘要、默认图尺寸及对应轮廓坐标 | 扩展既有build marker核验，未知schema拒绝；不再发明另一套来源链 |
| `Contents/Resources/web/{index.html,style.css,animation.js,image-settings.js}` | canonical源码复制，供独立预览；同一算法也进入install.js | 每份字节与build marker对应；预览不加载生产CDP transport |
| `Contents/Resources/web/assets/defaults/` | 从私有输入生成的avatar.png、artwork.png、contours.js；不复制源角色图 | 同一裁切背景生成彩图和轮廓；manifest记录实际输出摘要 |
| `Contents/Resources/wallpaper/{install.js,manifest.json}` | 保留显式legacy wallpaper apply能力；共用新的Wallpaper实现与原有私有全景图 | 正常CDP启动不另调用它；它和startup产物都必须被核验 |
| `Contents/Resources/AzhouAppIcon.icns` | 现有私有图标源及生成流程 | 保持既有图标尺寸、签名及安装核验 |

继续接收H现有4个私有输入`working.png/scene.js/wallpaper-scene-q-v3.png/app-icon/source.png`，本轮不迁移外部图库或修改素材库。默认头像由working.png中心裁切512²；默认背景由wallpaper-scene-q-v3.png中心cover裁切1536×1024；默认线稿从这份裁切后的背景生成。scene.js保留为原始维护输入，目标播放不再依赖旧人物网格。完整旧输入保留是兼容当前Hub private manifest，不把其存在当新增运行资源必须加载。

用已有系统图像框架完成默认图裁切，不为此加入运行时第三方依赖；默认描边必须可在构建中离线执行。可新增一个只用于构建的Swift素材工具并进入INPUT_FILES；使用Vision时保留RC3的同图配准标准。所有生成私有产物只进被忽略的stage/载荷。安装payload与预览都从同一生成物取图，避免两份不一致默认值。

Builder沿用H `build-wallpaper.py`的约束：只处理受控的单入口自包含函数，拒绝unexpected import/多个导出，固定模板组合；不把Python正则当任意JS或HTML安全清洗器。新增源码必须参与源码摘要，生成资源必须参与产物摘要；私有图内容不可进入Git diff。

### 2.2 必须一起修改的消费方

| 消费方 | H当前绑定（回源H11–H13） | 目标修改与通过条件 |
|---|---|---|
| `tools/build-macos.sh` | 编译原生动画，复制working/scene，构建壁纸 | 编译可信Launcher+预览，调用startup builder，复制新增预览资源；只生成隐藏载荷，绝不隐式安装 |
| `tools/verify-artifacts.py` | 固定VERSION/BUILD、INPUT_FILES、verify_wallpaper | 同步App版本、输入列表和verify_startup；产物缺失、错协议、错误裁切/轮廓、内容篡改全部拒绝；保留verify_wallpaper/图标/签名 |
| `hub-package.json` | 固定runtime_version/build，runtime_paths/build_inputs | 所有新运行源码、构建工具与必要说明进入对应列表；历史commit仍为来源，不换成虚构重实现基点 |
| `inspect_bundle` | 硬编码核对5份旧web文件与wallpaper | 对新App版本核对目标资源清单及startup manifest，仍核对原始私有输入与marker；不能仅检查install.js存在 |
| `execution_plan/assess_execution` | launch要求player完成与handoff-fade日志 | 新版本launch按RC7事件，只证明activated/ready/skipped；smoke仍证明独立播放器完成；更新effects/scope/limits和wallpaper评估 |
| `--wallpaper-status`与restore | 只读取/恢复Wallpaper | 保持原字段与返回语义；添加startup分项；restore清完整控制器；apply冲突明确返回startup-active |
| 安装器、登记工具 | 来源、版本、原子替换、唯一入口 | 保留门限；新增产物通过共同verify_product验证，不引入降级参数或绕过未知来源 |

版本同步点：Info.plist、verify-artifacts常量、hub-package runtime metadata、Wallpaper payload manifest/renderer VERSION及adapter断言必须一致；Page Controller `protocolVersion=1`另有语义，不能用App版本数字替代。

旧snapshot由它记录的源和核验器处理，不能拿新版本资源表重验旧清理包，也不能在cleanup时回读已变化的live源码。新旧assessment只按已验证App版本选择明确schema；不按“日志看起来差不多”自动猜测。T24/T25要包含旧版fixture，以证明维护没有破坏既有恢复和测试卸载。

### 2.3 新测试入口（实施时创建）

下表路径是工作单交付要求，当前不存在时不得运行并报告通过。原有全仓命令仍可运行，见acceptance§2。

| 预计命令 | 测试面 | Owner / 依赖 |
|---|---|---|
| `node --test packages/codex-startup-animation/tools/startup.test.mjs` | controller消息、clock、Settings、包装后payload，模拟宿主 | B/C/D；Node仅开发测试依赖 |
| `python -B packages/codex-startup-animation/tools/test-startup-build.py` | builder资源/摘要、篡改反例、版本一致 | E；标准库fixture，图像部分按macOS条件运行 |
| `python -B packages/codex-startup-animation/tools/test-startup-native.py` | Swift编译后的validator/transport测试可执行程序，不接真实Codex | A；测试时注入fake transport/目标信息 |
| `node packages/codex-startup-animation/tools/test-startup-browser.mjs` | 独立临时Chrome profile，真实iframe/IDB/CSP与包装产物 | B–E；只连模拟宿主 |

新用例必须接到现有verify或对应macOS CI leg，不能只把测试文件提交。现有Linux标准库门不强制装AppKit/Pillow/浏览器。Swift编译、浏览器与真实宿主分别报告条件；被跳过的关键macOS测试仍阻断生产门。

## 3. Agent工作单

每单开头读取详细设计§0–§4和本单输入，末尾按§4交接。A–F保留模块/文件Owner约束；用户已于2026-10-27批准“更名前置票 + 八张行为/集成/验收票”，本节维护唯一映射，不产生第二套运行契约或独立安装包。

| 票据 | 交付切片 | 模块/工作单映射 | 完成依赖 |
|---|---|---|---|
| 00 | 统一 agent-skin 包名，保护旧安装与快照 | N：新增命名/迁移前置票 | 无 |
| 01 | 可信启动，打通最小同窗口接入 | A + B 的最小链路 | 00 |
| 02 | 壁纸可核查，恢复外观不损伤官方页面 | B 的完整页面生命周期 | 01 |
| 03 | 播放完整 12 秒两图动画，共用独立预览 | C | 02 |
| 04 | 修改设置，可靠保存并开始新一轮播放 | D + C 导入能力的设置接线 | 03 |
| 05 | 从完整源码生成可核验的单一启动载荷 | E：构建与资源核验 | 04 |
| 06 | Hub 正确评估新版本，安全升级和清理旧测试安装 | E：adapter、安装兼容与文档 | 05 |
| 07 | 在固定官方版本验证完整同窗口体验 | F：G3 真实宿主 | 06 |
| 08 | 完成视觉与资源验收，再切换本地日常入口 | F：G4/G5；G6 明确排除 | 07 |

Tracker完成依赖：00→01→02→03→04→05→06→07→08。每张票的实时状态、issue编号和原生阻塞关系以GitHub为准。本次批准只授权立票，不授权执行实现或真实宿主操作。

### N：产品更名与既有安装衔接（前置，Planned）

- 输入：详细设计§12；当前package manifest、Hub组件选择、安装source标记、旧receipt/snapshot及其清理入口。
- Owner：命名/集成Owner统一处理包目录、Hub组件入口、manifest与文档/测试同步；不改Codex应用身份、页面协议、用户设置或历史来源。
- 行为：在隔离环境证明`agent-skin`新入口识别正确源码；旧输入plan失效后要求重做plan，旧owned快照仍能按原证据清理；来源不明保持拒绝。
- 依赖：产品名和首期宿主范围已确认；9票粒度与依赖已获用户确认，issue编号与状态以GitHub为准。
- 完成：T21/T22/T23/T28/T29中更名适用项及全仓verify通过，明确旧安装来源的保留/接管顺序。已有日常安装仍依赖旧目录且无法安全衔接时不得移动/删除该目录，也不得把本单标完成；日常安装切换仍走G5。

### A：可信冷/热启动和原生协议

- 输入：RC6/RC7；S Native/Extension与run/cdp；H WallpaperTarget/Validation/Transport。
- Owner：`Native/App.swift`与`Native/Wallpaper.swift`原生部分、新原生测试driver。预览代码保留，普通启动改为CDP而非原生动画；停止旧startWallpaper自动apply。
- 行为：真实PID/UID/签名/端口核验，0/1/2退出，单socket顺序id，fixed target、deadline和不重注入。先用极小mock payload验证，不等待C的视觉。
- 依赖：命名/迁移前置单N完成；schema以RC为准。假transport与算法准备可提前，不能借准备工作标记依赖已完成。
- 完成：T01/T02/T13/T14/T17/T26原生部分通过；fake失败不触发真实open/kill；测试入口进入macOS gate。

### B：页面控制器和单一壁纸所有权

- 输入：RC1/RC5/RC7；S renderer/payload；H Wallpaper.status/dispose及实际surface反例。
- Owner：新`extension/renderer.mjs`、`wallpaper/renderer.js`及CSS、controller测试；与A只通过已固定payload/result schema衔接。
- 行为：唯一iframe、双焦点快捷键、play/settings intent、runId、提前skip、统一expire、CSP实际哨兵、条件恢复和旧版精确识别。
- 依赖：A的协议schema已冻结即可开发；与A的真实集成是完成门。
- 完成：T11/T12/T15/T17/T18/T26页面部分通过，含restore后迟到解码、body迟到和未知owner反例；不新增永久扫描。

### C：两图动画与同图描线

- 输入：RC2/RC3及源algorithm出处；使用授权测试图，不用正式私有图做公开fixture。
- Owner：`animation.js/index.html/style.css`和图像/动画测试；image-settings的importImage函数归C，事务函数归D，合并由单一文件Owner执行。
- 行为：固定坐标裁切、描线/碎片、12秒时钟、位图预热后ready、跳过、减少动态实时变化、预览同实现；无需像素级重现源角色和字体。
- 依赖：B mount/消息Interface；没有B的mock时不可自造第二套通信。
- 完成：T03–T07/T19/T20通过；逐阶段截图、URL/帧资源计数有效；JS时间不当GPU成绩。

### D：设置持久化与并发

- 输入：RC1/RC2/RC4，acceptance T08–T10。
- Owner：`image-settings.js`load/save、设置UI事件与IDB测试；C导入函数合并时由D担任该文件最终Owner。
- 行为：draft/candidate/committed、先事务后应用、busy预算、取消与dispose、跨页基线冲突、保存后新iframe/runId；无自动S数据迁移。
- 依赖：B+C；只读旧库与quota/abort/blocked都必须有fixture。
- 完成：T08–T10/T26设置部分通过；取消不写库，写失败旧壁纸不变；持久化后壁纸失败为可辨识部分成功。

### E：构建、adapter、安装升级与文档

- 输入：本文件§2；RC7；当前manifest、verify-artifacts、integration adapter及安装器测试。
- Owner：§2消费方及新build/native gate wiring；更新包README、UPSTREAM维护说明、双语Hub README、support matrix、integrations。保留历史验收记录。
- 行为：单载荷、生产/fixture分离、完整输入/产物核验、新旧版本assessment、前向修复和仅owned cleanup。
- 依赖：A–D集成；不能为通过构建放宽安装所有权或丢弃私有输入门。
- 完成：T21–T25/T28/T29隔离部分、全仓verify及新增专项通过；生成App/图像未跟踪；未获分发许可不公开包。

### F：真实宿主到本地生产

- 输入：E的固定构建和回执、[production-runbook](production-runbook.md)；继承当前有效用户授权。
- Owner：agent执行可自动验证项，维护者决定视觉、资产和发布；单一操作Owner记录共享宿主状态。
- 行为：按runbook晋级，验证冷启动、热激活、设置、完整dispose、性能与恢复官方入口；新官方版本不继承旧版本PASS。
- 依赖：A–E全部完成；真实宿主写入和安装在授权范围内才执行，缺授权时交具体可审安装plan/构建/evidence请求。
- 完成：T01–T29适用项全部有证据，G3–G5门符合runbook；否则保持Implemented/Verified或hold，不能写Production。

模块完成依赖以边表达：N→A；A的schema→B；B→C；B+C→D；A+B+C+D→E；E→F。已批准Tracker切片将A与B最小链路合成01行为票，并细分E/F；完成依赖按本节9票映射执行。允许C的纯算法与A的fake transport提前准备，但`Native/App.swift`、`wallpaper/renderer.js`、`image-settings.js`和manifest各自始终一位最终合并Owner。

## 4. 每单交接与继续条件

回执最少字段：工作单ID、H/S实际HEAD、工作树diff范围、工作区/lease/分支、变更文件、对应FR/T、真实命令和退出码、输出证据位置、未满足项及下一单。仅原生/真实宿主单需要App版本/签名/PID/端口，只有素材单记录素材来源，不复制图片和用户设置。

新agent读回执与该单要求的文档分支，先复核未满足项和接口变化，再接下一单；不需要重读整个历史。关联输入有变化时重跑受影响测试，未变化的已通过检查直接引用本轮证据。没有完成判据证据时，报告哪一项未满足及可继续的独立工作，不用“大致完成”推进依赖。
