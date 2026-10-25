# 阿舟原生 Codex pet：2026-10-25 交付与验证

> 历史记录：以下结论来自原项目工作树当时的证据。引用的 `.local/evidence/`、`.local/pets/` 与用户级安装目录均未迁入本包；本文件不证明本包或当前机器的安装状态。

## 交付结论

已为当前项目实际生成、审阅并安装同主题原生 pet **「阿舟 · Agent 实验室」**，ID 为 `azhou-agent-lab`，采用原生 v2 图集。本轮通过 Remote Desktop Commander 读取及写入用户 Mac 项目；图像生成使用 ImageGen 与本机原生 hatch-pet 契约。

截至本轮最后核对，源主题、项目候选包与原生安装目录一致。独立验证程序没有导入管理脚本，而是从三个位置重新读取实际 WebP 字节、完整解码、计算文件与像素 SHA256；三处全部一致。**运行状态仍为 `pending-refresh-selection`：尚未观察宿主选择此 pet 后的实际显示、完整播放及鼠标方向交互。** 安装成功不能代替已应用验收。[E03–E05]

| 层次 | 本轮结果 | 可证明的范围 |
| --- | --- | --- |
| 源主题 | 四项冻结输入与当前源一致 | 本次 pet 对应哪组项目主题字节 |
| 实际图集 | 完整解码及 v2 结构通过 | 格式、尺寸、透明、使用格、真实摘要 |
| 图像审阅 | 标准帧、方向盲测与最终标注审阅通过，保留轻微方向提示 | 身份、逐帧语义、方向和静态连续性；不等于实机完整播放 |
| 项目候选 | 已选择且通过独立读回 | 包内数据属于当前主题与已审阅图集 |
| 原生安装 | 已安装，字节及像素匹配 | 实际安装内容正确 |
| 宿主运行 | 待正常刷新并选择 | 本轮没有宣称已经激活 |

这次新增 pet 数据、管理脚本与文档，没有实现此前审计规划中的三槽位任意替换平台，也没有改动启动器安装流程。[E01、E06]

## 1. 文件、位置与使用入口

项目根目录为 `/Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation`。本文所有相对路径均以此为根。

| 新增或更新内容 | 用途 |
| --- | --- |
| `pet/theme.json` | 角色、主题输入、来源、v2 约束 |
| `tools/manage-codex-pet.py` | prepare、validate、package、install、sync、status、recover |
| `tools/test-codex-pet.py` | 隔离的拒绝条件、事务及状态测试 |
| `docs/codex-pet.md` | 完整操作与恢复说明 |
| `docs/codex-pet-verification-2026-10-25.md` | 本次交付与验证边界 |
| `README.md` 的新增 pet 章节 | 入口索引；保留并行更新后的原有内容 |
| `.local/pets/azhou-agent-lab/` | 私有快照、已审阅 run、候选与选择记录 |
| `.local/evidence/20261025-pet-feature/` | 本轮命令输出、独立检查与证据索引 |

实际原生目录是 `/Users/guanxueliang/.codex/pets/azhou-agent-lab/`，包含 `pet.json`、`spritesheet.webp` 和独立所有权 receipt。没有创建额外 `.app` 入口，也没有设置宿主当前选择项。[E03–E05]

日常核对与同步：

```bash
cd /Users/guanxueliang/Desktop/Matrix/社区工程/codex-startup-animation
python3 -B tools/manage-codex-pet.py status
python3 -B tools/manage-codex-pet.py sync
```

随后在原生应用的 Pets 界面正常刷新并选择「阿舟 · Agent 实验室」。官方使用说明为 [Codex Pets](https://developers.openai.com/codex/pets)，当前重定向到 [ChatGPT Learn · Pets](https://learn.chatgpt.com/docs/pets)。本轮没有代替用户切换正在使用的 pet 或重启宿主。

### “同步生成”的准确边界

本轮已实际完成新的图像生成。后续 `sync` 负责将**已生成、已审阅、与当前主题匹配**的候选安全同步至原生目录；它没有调用 ImageGen 的凭据或 API。主题变化后，`sync` 会报告 `generation-required`，保留原安装，而不会把旧图复制一遍称作新生成。

```bash
python3 -B tools/manage-codex-pet.py prepare
```

`prepare` 冻结主题并生成 brief；后续须通过 ImageGen/hatch-pet 生成、审阅，再执行 `validate/package/sync`。因此当前能力是“真实生成交付 + 可复用的安全同步入口”，不承诺无人值守的一条命令自动生图。完整参数见 [操作说明](codex-pet.md)。[E02、E06]

## 2. 主题身份、来源与资产事实

采用女性 Q 版阿舟的正式身份：橙色卷发、棕眼、双狐耳、单条奶白尾尖的尾巴、大头小身体、短四肢、奶白/暖橙/棕色服装、狐形胸饰和短靴。人物自身左侧的蝴蝶结与腰包保持侧别，不用镜像整行替代独立的向左动作。正式参考和原 IP 库仅被读取。[E02、E07、E09]

| 输入 | SHA256 | 角色 |
| --- | --- | --- |
| `assets/private/working.png` | `34dc9a8e9c06c226ec0cc80878548f118ff4a23b4a87d160674e66db4a905e58` | 已采用的启动角色主题 |
| `assets/private/wallpaper-scene-q-v3.png` | `566eee5034343bb8463fa684dc0b90fe3d2c5d8f2adde1c9d71356bf192acbcb` | 已采用的全景配色与环境 |
| `style.css` | `3fa95e58d12ffa5b79498f67b7630c47386204a5dd67f67fe1157ab7531047be` | 当前项目界面视觉上下文 |
| `pet/theme.json` | `f10f190a100694f614d40139654878868c4408951386e9ea51955a7a9d04645e` | pet 身份及生成约束 |
| 正式 `01-master-idle.png` | `e38132192c8056dadff424eead7856625c9752810813ab5795e1cd6c0385b9de` | 正式身份来源；摘要记录在 theme 中 |

正式主形象位置：`/Users/guanxueliang/Desktop/oh-my-ai/IP/azhou/assets/characters/azhou-chibi-pet/v1.0.0/images/01-master-idle.png`。同目录的 `04-working.png` 与项目工作姿态同摘要。末次独立读取确认两张正式图都未变化。[E07]

四项主题输入的规范 JSON 摘要构成修订：

```text
themeRevision = 916ed5e9bfb47d99770f65f6d9954ceaa52057150edfb124c25a89272ca772ae
atlasSHA256   = bbd296d914e44eaf3306519006d635c90687a9dcc318559ac66b32561e890a04
pixelSHA256   = 9b867a032c3b49966cab35fcce2598c04ab3c03b5a907e7c20559a2b2d8c2446
manifestSHA256= b4fc418c87d5211e57e47a8322aff861d781ad09d428fb706549c0644be12a3e
```

实际图集为无损 WebP，3,143,106 字节，1536×2288 RGBA；8 列、11 行、每格 192×208。透明区域、每格角色占用、全透明格和完整解码已实测。图集是新生成的 pet 资产，不是启动动画录屏或 `scene.js` 的换名副本。[E04、E08]

本次采用 run：`.local/pets/azhou-agent-lab/runs/20261025-azhou-v2/`。

快照：`.local/pets/azhou-agent-lab/snapshots/916ed5e9bfb47d99770f65f6d9954ceaa52057150edfb124c25a89272ca772ae/theme-snapshot.json`。

候选目录使用 `themeRevision-atlasSHA256` 命名，实际完整路径记录在 `status-final.json`；同主题但不同图集不会被误判为同一个包。[E03、E06]

## 3. 原生消费者与帧布局

精确契约依据是本机 `/Applications/ChatGPT.app` 的实际 pet loader/schema、原生前端模块，以及本机 hatch-pet 工具；官方产品介绍页不用于推导内部 JSON 字段。宿主版本为 26.1021.31345 / build 21828，Bundle ID 为 `com.openai.codex`。[E01]

| 图集行 | 原生状态 | 帧数 |
| --- | --- | ---: |
| 0 | idle | 6 |
| 1 | running-right | 8 |
| 2 | running-left | 8 |
| 3 | waving | 4 |
| 4 | jumping | 5 |
| 5 | failed | 8 |
| 6 | waiting | 6 |
| 7 | running | 6 |
| 8 | review | 6 |
| 9–10 | look，顺时针每 22.5° 一格 | 16 |

57 个标准动画格加 16 个方向格，共 **73 个当前宿主映射格**。hatch-pet 的 assembler/validator 另使用 `(row=0,col=6)` 辅助 neutral 格，因此物理占用 **74 格**，剩余 **14 格完全透明**。它不增加 idle 帧数。[E01、E04、E08]

本机 `app-initial-feb30b196d11.js` 中 `gaa()` 给出各行帧数；`Paa()` 的方向死区返回 null，正常回退到 idle，16 个方向映射只覆盖最后两行。没有证据证明当前宿主消费那个辅助 neutral 格。neutral 经工具链重新去底、适配和最终去色溢，可以与 idle00 像素不同；`neutralMatchesIdle00:false` 是观察字段，不能据此误拒绝合规图集。整个图集仍受完整摘要及视觉审阅绑定。[E01、E04、E06]

原生 manifest 严格保持五个字段：`id`、`displayName`、`description`、`spriteVersionNumber:2`、`spritesheetPath:"spritesheet.webp"`。安装所有权与修订存放在独立 receipt，不向原生 schema 填入自定义字段。[E04]

另一个已落实的消费者事实：原生 loader 枚举 `pets/` 下所有目录，包括隐藏目录。因此事务 stage/previous 放在 `CODEX_HOME` 根目录且要求同文件系统，避免隐藏副本也出现在 pet 列表。测试覆盖了这个边界。[E01、E06]

## 4. 实际生成及视觉审阅

实际生成包含 13 项逻辑任务：1 个基础角色、9 个标准状态条带、1 个包含四个 cardinal 锚点的条带、2 个方向条带。失败尝试保留在修复记录里，没有进入最终包。采用来源、实际图像生成路径及参考适配写入 run 的 `generation-provenance.json`、`qa/generation-adapter.json`、`qa/repair-log.json`。[E09]

修复记录包括：idle 初稿相邻帧接触；向右动作的蝴蝶结侧别不对；第二行方向初稿仅检测到七个分离组件；后续版本尾部方向不正确。最终采用经过修正的整行结果。跳跃保留统一缩放和各帧的垂直位移，避免把每格分别居中后消除跳跃高度。[E09]

本轮已完成：

1. 标准状态 57 帧的身份、身体完整性和动作语义审阅。
2. 最终去色溢及原生 v2 validator：通过，最终结构 errors/warnings 为空，全透明像素 RGB 残留为 0。
3. 三个独立审阅者在只看盲测图片、不看答案的条件下完成方向配对判断；合并盲测四个 cardinal 硬门禁全部通过。
4. 最终标注方向及完整 contact sheet 独立审阅：通过，没有 major blocker。
5. 最终预览由**实际最终 WebP 解码后逐格裁取**，并记录来源摘要；不用清理前的旧帧冒充最终预览。[E08–E10]

### 保留的轻微视觉提示

盲测中 112.5°、292.5° 的垂直分量不够显著；最终标注审阅确认象限和上下符号正确。067.5°、112.5°、247.5°、292.5° 接近水平方向，保留 minor 提示。四个 cardinal 不含 warning，未豁免任何硬失败。[E10]

连续性指标指出 000° 的 y=16、180° 的 y=20 有分离区域，最终图检查认为是耳尖与顶部发形的自然负空间；157.5→180 的 2599 个差异像素对应从侧向到正面低头的形变，静态序列未见位置或缩放跳变。这些是**有标签的有序静帧判断**，不等于观察过实时循环。[E10]

`qa/visual-qa.json` 的 `labeledLoopReviewed:true` 在本次指向上述有序静帧审阅；同文件明确 `runtimeObserved:false`。该审阅发生在安装前，所以其中“尚未测试安装”是当时的边界；后续安装由 E03–E05 新证据覆盖，实际宿主播放仍未覆盖。不得修改早先记录，使其看起来已见到后来发生的安装。[E03–E05、E10]

### 预览节奏

最终 `idle.gif` 按已读取的原生 idle 时长 ×6 生成，一轮 6.6 秒。早期 standard review 的 1.1 秒是清理前工具默认时长，保留为历史静帧证据，不能代替最终节奏说明。`look-directions.gif` 为每方向 300ms 的审阅循环；实际宿主依据鼠标角度选择方向，不按这段循环播放。[E01、E11]

九个状态 GIF 与方向预览均在 `run/qa/previews/`。它们可供查看，但不能作为已经在宿主内播放的录像。

## 5. 同步实现与失败行为

管理入口将 source、package、installed、runtime 分层报告，并把影响显示的四项输入共同纳入修订。候选验证会完整解码真实 WebP，重新计算字节及像素摘要，将视觉 QA 绑定到这一个图集和主题。相同主题下选择新图集后，旧安装会报告 `stale-package`。[E03、E06]

| 情况 | 行为及边界 |
| --- | --- |
| 候选不存在或主题已变 | `generation-required`；保留现有安装，要求重新生成及审阅 |
| 损坏图、格式/尺寸/透明格错误 | 拒绝；不只相信头部、扩展名或 QA 自报值 |
| 图集、主题与 QA 摘要错配 | 拒绝；只变辅助 neutral 格也会触发完整图集摘要错配 |
| cardinal 未通过、方向缺失或重复 | 拒绝；minor 中间方向须显式审阅接受 |
| 同名未知目标、symlink、未知文件、receipt 不符 | `unknown-target` 或对应拒绝；不接管其他 pet |
| 项目或用户目标锁被占用 | `busy`；不抢锁、不杀进程 |
| 交换前后异常、中断 | 有限 stage/previous 与持久 journal；按实际落盘状态恢复 |
| 已提交后清理中断 | 完成已提交的新包，不把它描述为恢复旧包 |
| 中断后主题又变化 | `recover` 仍能根据已知事务恢复，不依赖当前主题相等 |
| 安装完成但未刷新选择 | `installed` 与 `pending-refresh-selection` 同时报告 |

常规候选保留当前与上一份已审阅包，未知内容不随意删除。恢复只覆盖本工具的 pet 包和选择事务，不恢复启动器、壁纸、宿主会话或宿主所选 pet。完整退出码与命令见 [操作说明](codex-pet.md)。[E06]

## 6. 本轮实测、历史记录与未覆盖项

### 本轮最终实测

| 检查 | 结果 | 原始证据 |
| --- | --- | --- |
| 最终代码隔离测试，用户 Mac | **34 项通过，3.468 秒，退出 0** | `isolated-tests-macos-accepted.txt` |
| 相同最终实现，生成工作环境 | 34 项通过，20.489 秒 | `implementation-manifest.json`、最终本地测试输出 |
| 实际图集完整解码和 native v2 校验 | 通过 | `candidate-validation.json`、run `final/validation-extended.json` |
| 原生 sync | 安装成功，退出 0 | `sync-install.json` |
| 管理脚本最终 status | 当前源、包、安装匹配；待刷新选择 | `status-final.json` |
| 独立三处实际字节及像素读回 | 三处摘要一致 | `independent-byte-readback.json` |
| 正式 IP 两张参考 | 摘要未变化 | `preservation-check-before-docs.json` |
| pets 目录既有文件 | 11/11 未变化：五个既有 pet 的十个文件及一个目录元数据文件 | 同上 |
| 原官方宿主进程 | PID 6822，启动时间仍为 2026-10-25 05:14:31 | 同上 |
| 官方应用签名 | `codesign --verify --deep --strict` 退出 0 | 同上 |
| pet 事务 stage/previous/journal | 末次核对无残留 | 同上 |
| 并行更新后的启动器只读检查 | 16:03 UTC：0.7.1 / current；实体应用及登记路径各一处 | `startup-install-check-latest.json` |

测试覆盖合法 PNG 头但坏内容、错格式/尺寸、使用格及空格、QA/图片/主题错配、方向重复/cardinal 门禁、两个真实进程锁、同名目标与路径保护、交换异常、模拟进程中断、提交后清理、主题变化后恢复、同主题新包旧安装，以及辅助 neutral 重处理和后续篡改。测试在临时项目和模拟 `CODEX_HOME` 中进行；合成测试图不作为阿舟视觉证据。[E06]

独立传输校验确认 43 个文件落盘，其中索引列出的 42 个数据文件逐一重算 SHA256。约 7.52MB 的临时传输 ZIP 与 Base64 分块在核验后清除；它们不是持久应用恢复包。[E05]

### 保留为历史、不能当作最终通过的记录

早期 Mac 测试因 `/var` 与 `/private/var` 规范路径差异出现四项失败；修正测试根目录规范化后，最终 34 项全部通过。早期 31/33 项通过及 neutral 规则调整过程的日志保留，不计为新的验收项。`isolated-tests-macos-accepted.txt` 才是本次最终代码的 Mac 结果。[E06]

此前资产审计、0.7.0 启动器和壁纸验收仍保留各自日期、范围；本次没有重跑它们，也不把历史“通过”挪用到 pet 运行验收。

### 未覆盖，不能宣称通过

- 宿主 Pets 界面刷新、选择此 pet 后的实际渲染截图与完整播放。
- 鼠标真实移动时四个 cardinal 和中间方向的实际帧选择。
- 宿主各任务状态触发、DPR、显示器切换及长时间使用。
- 真实断电、磁盘硬件故障；事务测试为受控异常与进程中断模拟。
- 新增宠物不会自动同步到其他设备或网页端；本轮交付为本机原生目录。

## 7. 对现有项目的保护，以及并行工作树变化

开始时保存 1407 个既有文件摘要。整理文档前再比对：无既有文件缺失，但有 12 个既有路径发生变化，包括 README、AGENTS、壁纸源/测试、构建脚本和历史壁纸文档。当前 AGENTS/README 已显示 0.7.1 / build 8 的壁纸工作；这些变化不在本轮 pet 源码写入清单里，已原样保留。README 首次写入因基线不匹配而被保护检查阻止；随后读取新内容，仅追加 pet 章节。不能声称整个工作树都没有变化。[E07、E12]

16:00 UTC 的交付检查确认：pet 的五个项目实现/文档文件摘要一致、README 追加前的 15,718 字节完全保留、此前观察到的另 11 个并行变化文件保持原样、22 个文档链接可定位、私有产物被 Git 忽略。该时刻相对初始基线的变化增至 20 个路径，新增八项包括安装登记、Python 缓存及六项构建载荷文件；完整路径保存在 `final-delivery-check.json`。仅凭摘要不能判定每一项的写入者；本轮操作记录没有启动器构建或安装命令。随后又单独只读观察了这次并行安装的最终状态，见下表。[E12、E15]

本轮 pet 没有写入 `assets/private/`，启动图片、全景原图、图标、`scene.js`、`index.html`、`animation.js`、`style.css` 和 `Native/App.swift` 保持基线字节。既有 7.8 秒启动节奏、三项固定文案和唯一日常应用入口未被 pet 集成改动。[E07]

现有应用构建摘要递归包含 `assets/private/`；因此 pet 图集与证据放在已经忽略的 `.local/pets/`，不会因新增 pet 图集而扩大旧应用的构建输入。pet 是原生用户数据，不是新增的 macOS 应用；本轮不对官方宿主重签名，也不构建或重装启动器。[E01、E07]

### 必须按时间点单列的启动器安装状态

| 观察时间（UTC） | 结果 | 范围 |
| --- | --- | --- |
| 本轮开始 | current，版本 0.7.0 | 初始安装状态 |
| 整理文档前 | `--check` 退出 1，源码/载荷摘要不一致 | 当时并行 0.7.1 源码变化尚未与载荷一致 |
| 15:54:05 | 已安装应用 12/12 文件仍匹配初始载荷 | 只证明这个时间点的旧安装未变化 |
| 16:03:12 | `--check` 退出 0，current，版本 0.7.1 | 并行更新已完成；实体应用 1、dist 应用 0、登记路径 1 |

中间失败输出原文为“编译期间源码或私有素材发生变化，未发布；请在修改完成后重新构建。”该证据保留，不改写成通过。最新只读检查另存 `startup-install-check-latest.json`；其树摘要为 `2a2831efa487d88f86c4f91aacc7448042179764c6e959aa0dd7ecb9123ce467`。它是另一个时间点的安装器检查，不作为 pet 的视觉或运行验收。[E13–E15]

15:54 的**独立只读检查**将已安装 `~/Applications/阿舟启动 Codex.app` 全部 12 个文件逐一与最初 `.build/azhou-payload/` 基线比对，12/12 相同，无缺失、差异或额外文件。此后并行更新改变了载荷及安装登记，故不能把这份旧基线匹配推延为 16:03 的现状。本轮 pet 工作没有构建、重签名或安装启动器；0.7.1 的构建及安装属于并行工作，单列观察、不归入 pet 交付成果。[E12–E15]

官方宿主 PID 与启动时间保持不变，签名检查通过。没有退出或重启现有 Codex 会话，没有 reset/clean、公开私有资产、删除历史素材，或修改原 IP 库。[E07]

## 8. 复现与后续实际消费验收

只读状态与隔离测试：

```bash
python3 -B tools/manage-codex-pet.py status
python3 -B tools/test-codex-pet.py
shasum -a 256 /Users/guanxueliang/.codex/pets/azhou-agent-lab/spritesheet.webp
```

第三条应得到上文完整 `atlasSHA256`；只验 SHA 仍不能证明宿主实际展示。后续正常使用时，在原生 Pets 界面刷新并选择阿舟，记录实际选择项、真实截图、完整状态播放和上下左右鼠标响应。若宿主仍显示旧 pet，则安装状态仍可为正确，运行状态不得晋升为 applied；如果现场结果与图集/方向契约不符，应据实否证当前运行验收。

本次 `status` 没有观察宿主的能力，始终保守报告待刷新选择；即使用户已选择，也需独立运行证据补充，不能靠脚本字段自行证明。操作中的中断恢复使用 `recover`，不自动退出宿主。[E03、E06]

## 9. 本地证据索引

下列 E 编号用于本文定位原始材料。`E` 为 `.local/evidence/20261025-pet-feature/`；`R` 为 `.local/pets/azhou-agent-lab/runs/20261025-azhou-v2/`。全部保存在本地受忽略目录。完整文件级 SHA 索引见 `R/asset-file-index.json`；报告收尾后的新增文本另列于 E 的索引，不改写已完成传输的历史记录。

| 编号 | 实际材料 | 能证明什么 |
| --- | --- | --- |
| E01 | `E/native-contract/app-pet-loader-excerpts.json`、`native-frame-layout.json`、`native-direction-layout.json`、`avatar-overlay-native-page.js` | 实际原生 schema、扫描范围、帧数、idle ×6、方向死区与映射 |
| E02 | `R/theme-snapshot.json`、`R/generation-provenance.json`、项目 snapshot 的 `inputs/`、`pet/theme.json` | 本次使用的冻结主题、正式身份及采用来源 |
| E03 | `E/candidate-validation.json`、`E/sync-install.json`、`E/status-final.json` | 管理入口各层结果与安装路径 |
| E04 | `E/independent-byte-readback.json` | 不导入管理脚本的三处字节、解码像素与 native manifest 独立验证 |
| E05 | `E/transfer-verification.json`、`R/asset-file-index.json` | 43 文件交付及 42 个数据条目摘要核对 |
| E06 | `E/isolated-tests-macos-accepted.txt`、`E/implementation-manifest.json`、最终实现与测试源码 | 最终 34 项隔离测试、实现摘要和拒绝/恢复行为 |
| E07 | `E/original-files.json`、`other-pets-baseline.json`、`preservation-check-before-docs.json` | 原文件及其他 pet、IP、宿主进程/签名保护，包含并行差异 |
| E08 | `R/final/validation-extended.json`、`R/qa/chroma-despill-extended.json` | 最终图集结构与去色溢结果 |
| E09 | `R/qa/repair-log.json`、`generation-adapter.json`、`jumping-extraction-decision.json`、`standard-visual-qa.json` | 拒绝与修复历史、参考适配、跳跃提取及早期逐帧视觉审阅 |
| E10 | `R/qa/direction-blind-verdicts-1/2/3.json`（三个独立文件）、`direction-blind-validation.json`、`direction-semantics.json`、`final-labeled-review.json`、`blind-review-resolution.json`、`visual-qa.json`、`look-continuity.json` | 盲测、最终标注判断、轻微提示与明确的未观察边界 |
| E11 | `R/qa/preview-provenance.json`、`R/qa/previews/`、`contact-sheet-extended.png`、`look-directions.png` | 最终字节来源的可视预览与节奏；不是宿主录像 |
| E12 | `E/README-before-pet-addition.md`、`readme-append-verification.json`、`git-status-before-docs.txt`、`final-delivery-check.json` | 追加前 README、保留原字节、最终交付文件和已有并行变化 |
| E13 | `E/startup-install-check-before.json`、`startup-install-check-after.json` | 开始时 current 与收尾时源码摘要不匹配两个不同时间的事实 |
| E14 | `E/startup-independent-baseline-readback.json` | 已安装启动器的 12 个实际文件仍与初始载荷基线一致 |
| E15 | `E/startup-install-check-latest.json` | 16:03 UTC 并行更新后的只读结果：0.7.1 / current，实体及登记各一处 |

具体证据目录入口原为 `.local/evidence/20261025-pet-feature/EVIDENCE-INDEX.md`，该本地证据目录没有随源码迁入。
