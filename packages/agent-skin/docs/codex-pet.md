# 阿舟原生 Codex pet：生成、主题绑定与安全同步

本项目的原生 pet 为 **阿舟 · Agent 实验室**，目录 ID 为 `azhou-agent-lab`。它保持正式女性 Q 版阿舟的大头、小身体、短四肢及暖橙、奶白、棕色主题。启动器动画、壁纸和 pet 使用相关参考，但拥有各自的运行消费者；安装 pet 不等于修改或播放启动器动画。

此集成不改变现有启动器、官方宿主、7.8 秒启动节奏、固定文案或应用入口，不修改原 IP 素材库。它也不设置宿主当前所选 pet。原生安装完成后仍需正常刷新选择界面并选择阿舟。

本轮 pet 图像来自 ImageGen/hatch-pet 的真实生成 run；生成图集及其视觉证据由本轮生成交付记录关联。下述 `sync` 的后续职责是同步已经生成并审阅的同主题包，不是无凭据的命令行生图入口。

原生接口依据为本机 `app.asar` 内实际 pet loader/schema 与 `hatch-pet/references/codex-pet-contract.md` 的交叉核对。原始 loader 摘录保存于本轮证据的 `native-contract/app-pet-loader-excerpts.json`。产品使用说明见官方 [Codex Pets](https://developers.openai.com/codex/pets)（当前跳转至 [ChatGPT Learn · Pets](https://learn.chatgpt.com/docs/pets)）。精确尺寸和 manifest 门禁以本次实读的原生契约为准，不把产品介绍页当作所有内部字段的依据。

## 工作方式

`manage-codex-pet.py` 负责冻结输入、核验已生成的图集和审阅记录、打包、安装及状态报告。**生成由 ImageGen 与原生 hatch-pet 流程完成。** CLI 没有生成 API，不会把复制旧图集描述为重新生成，也不会在主题变化后静默安装旧 pet。

新集成文件仅为：

- `pet/theme.json`：主题与角色约束、采用来源、v2 网格信息。
- `tools/manage-codex-pet.py`：命令入口。
- `tools/test-codex-pet.py`：完全隔离的测试。
- 本文档。

私有生成数据和候选包放在 `.local/pets/azhou-agent-lab/`。**不要把 pet 生成产物放入 `assets/private/`**：现有应用构建摘要会递归包含该目录，新增 pet 数据会令旧安装包与源摘要失配。此能力不运行现有应用构建或安装器。

## 依赖与入口

需要 Python 3.10+、带 WebP 解码能力的 Pillow，以及 POSIX 文件锁。目录发布还要求 macOS `renamex_np` 或 Linux `renameat2` 的排他重命名能力；接口或文件系统不支持时停止并保留待核对内容。本次排他发布仅在 macOS 本地验证，Linux 尚未实测。先使用已经存在的运行环境；脚本不安装依赖。

```bash
python3 -c 'from PIL import features; print(features.check("webp"))'
python3 -B tools/manage-codex-pet.py --help
```

默认项目根目录为脚本所在项目。默认原生安装位置为 `${CODEX_HOME:-$HOME/.codex}/pets/azhou-agent-lab/`。隔离测试和预演可显式传入 `--project-root` 与 `--codex-home`。

### 从旧项目复用已审阅候选

已有同主题候选时，可使用 `tools/import-codex-pet.py --from-project OLD --project-root NEW` 生成只读计划，审阅后以 `--apply --plan-id PLAN_ID` 导入。它使用本包现有校验器重新解码图集、验证冻结主题和六份 QA，保留原图集与 QA 字节，并为新项目创建候选归属与原始来源记录；不会伪造新生成或新审阅。

新项目的 `style.css` 和 `pet/theme.json` 必须匹配，私有主题图只能补缺或复用完全相同的文件。未知状态、冲突素材、变更后的计划或无效 QA 均拒绝；仅本次导入记录绑定的中断状态可在重新审阅计划后续跑。先保存旧项目工作树与私有候选链，原项目保持不变。

此操作只准备新项目候选，不读取或修改用户安装目录，不转移原安装 receipt，也不刷新、选择或播放 pet。完整命令与边界见 Hub [接入操作说明](../../../docs/integrations.md#pet-maintenance-after-the-import)。对应隔离测试为 `python3 -B tools/test-import-codex-pet.py`。

导入的 Hub 候选复验通过后，若原生 Pet 仍带旧项目 receipt，可从最终 Hub 包目录执行一次明确的归属接管：

```bash
python3 -B tools/manage-codex-pet.py handoff --previous-project-root /absolute/old/project/root
python3 -B tools/manage-codex-pet.py status
```

`handoff` 要求旧项目当前候选、实际安装及 Hub 候选的主题、图集和清单摘要一致；它同时取得旧项目锁和用户 Pet 锁，并通过原有事务安装新项目 receipt。旧项目不再存在时，仅已完成且与 Hub 当前候选完全一致的安装可被识别为重试完成。普通 `install`/`sync` 不接管其他项目；`handoff` 也不改变宿主当前所选 Pet。删除旧项目之前，应核对 Hub `status` 的安装字节结果并保存旧候选证据。

### 1. 冻结主题

```bash
python3 -B tools/manage-codex-pet.py prepare
```

冻结以下四项实际字节：

| 输入 | 作用 |
| --- | --- |
| `assets/private/working.png` | 已采用的启动角色主题参考 |
| `assets/private/wallpaper-scene-q-v3.png` | 已采用的全景场景与配色参考 |
| `style.css` | 当前界面的视觉上下文 |
| `pet/theme.json` | pet 身份、生成与主题约束 |

输出 `themeRevision`、`theme-snapshot.json` 路径和 `generation-brief.md` 路径。快照旁 `inputs/` 保存冻结字节，预览和生成应使用这一份快照。正式 `01-master-idle.png` 的摘要只记录在来源信息中，不要求普通 clone 自动访问原 IP 库。

修订算法为：按上述固定顺序构造 `inputs=[{"path":...,"sha256":...}, ...]`，对 `{"schemaVersion":1,"inputs":inputs}` 的 UTF-8 规范 JSON 计算 SHA256。规范 JSON 使用 `sort_keys=True`、`ensure_ascii=False`、`separators=(",", ":")`。图片相同而 `style.css` 或 `theme.json` 变化，同样产生新修订。

快照本身必须明确声明整数 `schemaVersion: 1`；缺失、非整数或未知版本不会被按 v1 推测解释，原文件保留待核对。快照是事实记录，不代表已经生成或已经视觉验收。准备阶段不会安装任何 pet。 返回前会重新核对冻结输入和当前主题，并检查任务说明是包含该主题修订的非空 UTF-8 普通文件。说明缺失、无法核验或修订不匹配时保留原文件并报冲突；发布后主题变化则保留快照并要求重新准备。

### 2. 由 ImageGen/hatch-pet 生成与审阅

生成过程须保留实际 run 目录。原生 v2 图集为 `1536×2288`，8 列 × 11 行，每格 `192×208`。前九行使用帧数依次为 `6,8,8,4,5,8,6,6,6`；后两行使用全部 16 格表示顺时针 look 方向。`000` 是向上，`090` 是屏幕右，`180` 是向下，`270` 是屏幕左。

实际 hatch-pet 工具链还有一个**辅助保留格 `(row=0,col=6)`**：`assemble_extended_atlas.py` 的 `paste_neutral_cell()` 写入该格，`validate_atlas.py` 的 `EXTENDED_NEUTRAL_LOOK_FRAME` 将其视为非空格。`load_neutral_cell()` 既可采用已有基础格，也允许外部 neutral 参考经 `remove_chroma_background()` 和 `fit_to_cell()` 再处理；随后还有最终去色溢步骤，因此 neutral 与 idle00 的像素或 alpha 可以不同。CLI 只要求该格非空且有透明背景，不强制逐像素相等；`neutralMatchesIdle00` 是观察字段，不是通过门禁。图集应有 74 个占用格、14 个透明空格；用于当前宿主动画及方向映射的格仍是 57 + 16 = 73 个，辅助格不改变动画帧数。

该工具链保留格**不能用来证明当前宿主会消费它**。本轮实读的 `app-initial-feb30b196d11.js` 中，`Paa()` 在无向量死区返回 null，方向映射只指向最后两行的 16 格，`Maa` 回退到普通 idle；定位记录见本轮 `native-contract/native-direction-layout.json`。`theme.json` 的 frame counts 描述动画，未用格定义不包括上述保留格，主题快照无需改变。

完整动画播放、关键帧、身份一致性、动作可读性、左右方向与中间方向仍需审阅。文件解码和 QA JSON 不能自行证明这些视觉结论正确。

### 3. 验证并打包已审阅 run

以下命令中的路径应替换为实际 run 和 `prepare` 输出的快照路径：

```bash
python3 -B tools/manage-codex-pet.py validate \
  --run /absolute/path/to/run \
  --snapshot /absolute/path/to/theme-snapshot.json

python3 -B tools/manage-codex-pet.py package \
  --run /absolute/path/to/run \
  --snapshot /absolute/path/to/theme-snapshot.json
```

选择记录、标准目录名及实际候选的主题和图集摘要必须一致；状态、验证、安装和交接发现冲突时会停止并保留内容。 若回据含目录身份，已选候选和导入来源、目标须与当前实体匹配；字段缺失的已选旧候选仍可读取和原位复用，不能按新绑定认领或清理。字段存在但缺损或不匹配时报告 `source-conflict` 并保留现场。`package` 只在项目私有目录产生候选，不安装到原生目录。选择记录原子更新，候选由完整 `themeRevision-atlasSHA256` 命名。常规清理只保留当前和上一份已审阅候选；未知内容不会被直接删除。 新候选发布后，先完成受限历史清理并重新核验候选，才更新选择；清理失败保留旧选择和新候选，已经完成的清理不回滚。若选择替换后目录同步失败，选择可能已改变，需检查实际记录。冻结输入保留为来源记录，不属于可随意清理的事务暂存。

### 4. 同步原生目录

```bash
python3 -B tools/manage-codex-pet.py sync
python3 -B tools/manage-codex-pet.py status
```

当已安装 Pet 与候选图集、主题相同但 manifest 不同时，`status` 显示 `stale-package`，安装返回 `source-conflict` 并保留原对象，需核对来源；不能仅凭图集和主题称为已安装。

候选目录按主题修订和图集摘要命名。同名候选仅在既有 QA、快照和 manifest 摘要均与本次提交的字节一致时复用；证据不同则返回 `source-conflict`，保留旧候选、当前选择和新材料待核对。现有命名不能为相同图集与主题并列保存不同审阅版本；不要自行删除旧候选来绕过冲突。

`sync` 只安装主题仍匹配的已审阅候选。也可为 `sync` 同时提供 `--run` 与 `--snapshot`，在同一次项目锁内完成验证、打包与安装。没有候选或主题变更时返回 `generation-required`，指向 `prepare → ImageGen/hatch-pet → 审阅 → package/validate → sync`，不会自动生图。

`install` 安装当前已选候选；`sync` 额外提供无候选时的生成引导。二者均不会启动或退出宿主，也不会自报已激活。

## run 输入契约

| 必须存在的文件 | 接受条件 |
| --- | --- |
| `final/spritesheet-extended.webp` | 实际为静态 WebP；完整解码通过；准确尺寸及透明格契约 |
| `final/validation-extended.json` | 明确 `ok:true` 或等价通过状态，无 errors/failures |
| `qa/chroma-despill-extended.json` | 明确通过，无 errors/failures |
| `qa/review.json` | 明确 `errors:[]` |
| `qa/direction-semantics.json` | 16 个唯一方向，覆盖 `000` 至 `337.5`，没有失败项 |
| `qa/direction-blind-validation.json` | 明确通过，无 errors/failures/unconfirmed |
| `qa/visual-qa.json` | 明确通过，且 `atlasSHA256`、`themeRevision` 与实际图集和冻结主题一致 |

通过状态兼容 `ok:true`、`pass:true`、`status:"pass"`、`result:"pass"`、`verdict:"pass"`。方向语义可使用 `directions`、`results` 或 `checks`，并以 `direction`、`angle` 或 `id` 记录度数。

四个 cardinal 必须明确通过。中间方向的 `verdict:"warning"` 仅在其严重程度为 minor，且 `visual-qa.json` 同时包含以下显式审阅结论时接受：

```json
{
  "pass": true,
  "atlasSHA256": "实际 WebP 字节的 SHA256",
  "themeRevision": "实际快照修订",
  "labeledLoopReviewed": true,
  "blindResolution": {"decision": "accept", "severity": "minor"}
}
```

盲测报告带 `warnings` 或 `reviewRequired:true` 时，也要求上述审阅结论。任何明确 fail/failed、`ok:false`、`pass:false`、非空 `failures`、未确认方向或 cardinal warning 都不能由这个例外放行；矛盾证据需重新审阅，工具不自动改写原件。

脚本独立解码真实 WebP，并重新计算字节摘要和 RGBA 像素摘要；校验 74 个占用格都有角色与透明背景、14 个未用格完全透明、全透明像素无 RGB 残留。结果分别报告 `occupiedCells:74`、`renderedCells:73`、`animationCells:57`、`lookDirectionCells:16`、`neutralCells:1`、`unusedCells:14`；兼容字段 `usedCells` 表示物理占用格数 74。尺寸正确的坏图、只剩合法 PNG 头的坏图、9 行中间图集、缺失的 neutral 格、错主题审阅或错图片审阅均会被拒绝。整个图集的 SHA256 与独立视觉审阅绑定，因此即使只在审阅后改变辅助格，也会因字节摘要失配被拒绝。QA 自报的宽高或摘要不能替代独立解码和实际摘要检查。

## 原生目录与所有权

安装后的原生目录包含：

```text
azhou-agent-lab/
  pet.json
  spritesheet.webp
  .azhou-pet-receipt.json
```

`pet.json` 严格只有 `id`、`displayName`、`description`、`spriteVersionNumber:2`、`spritesheetPath:"spritesheet.webp"` 五项。独立 receipt 保存本项目所有权、实际字节摘要及主题修订，供后续更新和恢复使用；它不是原生契约字段，也不是签名或视觉验收的替代品。

同名目录没有本项目 receipt、属于其他项目、存在未知文件、含符号链接或内容与 receipt 不符时，普通安装被拒绝。明确的 `handoff` 只接管上述三方摘要一致的旧项目安装；未知 pet 仍会被拒绝。已知且完整的本项目安装允许更新。

## 锁、事务与恢复范围

变更命令先取项目锁，安装再取用户级目标锁；两个项目不能并发改同一目标。锁冲突返回 `busy`，不杀进程、不强占锁。安装前后均检查当前主题，避免生成期间主题变化后仍默默安装旧图。

候选构建使用有限暂存及原子选择记录。新候选的回执绑定创建时的目录设备与身份，仅自动清理仍匹配且内容完整的旧候选；旧版未绑定或身份变化的候选保留待核对。安装的隐藏 stage/previous 目录放在 `CODEX_HOME` 根目录，处于 `pets/` 扫描范围之外；同时要求两者属于同一文件系统。实际原生 loader 会枚举 `pets/` 下所有目录，隐藏目录也不能用于存放含 `pet.json` 的事务副本，否则刷新时可能出现重复 pet。`pets/` 下只保留正式目标，以及不会被目录扫描当作 pet 的日志和锁文件。

持久事务日志记录 `stagingLocation:"codex-home"`；交换后同步两个父目录。在新包完成独立读回、日志提交之前保留上一份安装。普通异常尝试恢复上一包；提交后的清理中断会完成已经提交的安装，不假称恢复旧包。旧版或未知暂存布局不会被猜测为当前布局，而是报告需人工核对。

回执发布失败时，仅清理仍与已完成写入的文件身份和内容一致的临时文件；部分写入或无法核验的内容会保留，需人工检查。发布后原临时名被重新占用时不予删除。

快照、候选包及安装暂存的恢复清理只处理事务日志中列出的文件；安装恢复在处理目标或备份前也会复验暂存；发现计划外条目会保留并停止，日志仍在。已删除的计划内文件不会自动恢复；如果只剩陌生文件或空目录，需人工核对，不能假称事务已回滚。历史候选和安装恢复目标、备份也在原来源验证前捕获精确文件计划，删除前复核身份和摘要；完整对象缺少计划文件时停止。计划名称下的同字节替换及最后一次检查后的竞态仍不能完全识别。

快照、候选包、备份及安装发布使用排他重命名；目标在发布时出现会保留冲突对象，不覆盖它。源路径仍可能在最终检查和重命名之间被其他同用户进程替换；不要并发修改事务目录。

Pet 审核、状态、回据和恢复日志的 JSON 不接受任意层级的重复字段；发现后停止并保留原件，旧日志也需人工核对。Pet 输入捕获会核对文件实体、长度、修改时间和状态变更时间；读取时发现变化会停止，不能排除最后核验后的并发改动。候选或已安装的 Pet manifest 不是 JSON 对象时，状态检查分别报告无效或 `unknown-target`，安装停止并保留文件。已安装回据的主题修订必须是 64 位小写十六进制摘要；缺失或格式错误时在创建升级事务、移动旧目标前报 `unknown-target` 并保留原件。安装标记为已提交之前会将发布后目录的图集、主题与 manifest 三项摘要全部对照候选；发生冲突时保留未提交日志和无法核验的对象。新事务分别记录候选和旧安装的图集、主题修订及 manifest 摘要；恢复时须与实际对象及属主一致。缺少这些绑定的旧日志、未知状态、未知或不匹配的暂存内容会保留并报告 `recovery-required`，不能仅凭同名、图集或自报属主删除。人工核对日志、目标、备份和来源后再决定恢复方式；不要批量删除待核对目录。snapshot、package 和 install 暂存必须匹配事务记录的目录设备与 inode；已有暂存的旧日志若缺少该绑定，需人工核对。候选暂存至少有一个完整文件且写到已记录文件边界时可自动恢复；空暂存、缺少绑定、部分写入或内容变化则保留。读取使用不跟随末级链接的文件描述符并检查前后身份；父目录替换、同用户伪造元数据、最后一次检查后的并发替换、断电和部分删除仍不受完整保护。

```bash
python3 -B tools/manage-codex-pet.py recover
```

`recover` 获取两层锁后检查已知事务。它不要求原主题仍是当前主题，因此中断后再改主题也可以恢复。恢复依据正式目录、暂存目录、receipt 和重新读取的字节；发现未知内容或无法证明归属时停止并报 `recovery-required`。`status` 只读，不擅自执行恢复。

恢复只覆盖本工具管理的 pet 包与选择事务，不恢复启动器应用、壁纸、宿主会话或用户选择状态。运行状态始终为 `pending-refresh-selection`，直到宿主的实际选择与显示由独立观察确认；本脚本没有把该观察伪装成已完成。

## 状态与退出码

| 状态 | 含义 |
| --- | --- |
| `generation-required` | 缺少已审阅候选，或主题已变化，需要重新生成和审阅 |
| `packaged` / `validated` | 项目候选通过检查；不代表原生目录已更新 |
| `installed` / `already-installed` | 原生目录实际字节已核验；仍待刷新选择 |
| `installed-with-recovery` | 已提交的新包经恢复完成；附带原异常及恢复说明 |
| `stale-theme` | 候选或安装仍属于旧主题 |
| `stale-package` | 安装内容独立有效且主题相同，但不是当前选中的图集 |
| `unknown-target` | 同名目标无法证明属于本项目或已被外部修改 |
| `busy` | 有另一个操作持锁，本次没有强行修改 |
| `install-failed` | 安装失败并已给出具体恢复结果；检查随附分层状态 |
| `recovery-required` | 仍有未完成事务或无法安全恢复，不能宣称全部恢复 |

`status` 分别给出 source、package、installed、runtime。 主题或候选快照的结构、输入路径或摘要格式损坏时，相应状态报告 invalid 并保留数据。安装层另含 `bytesVerified`、`matchesCurrentTheme` 和 `matchesSelectedPackage`；相同主题修订不等于安装了相同图集。错误输出也尽可能附带只读状态快照。

退出码：成功命令为 `0`，拒绝/校验/安装错误为 `2`，需要生成为 `3`，锁冲突为 `4`，需要恢复为 `5`。`prepare` 成功产生快照时返回 `0`，输出的业务状态仍是 `generation-required`，表示下一步需要生成。

## 隔离测试与验收边界

```bash
python3 -B tools/test-codex-pet.py
```

测试使用系统临时目录、明确指定的模拟项目和模拟 `CODEX_HOME`；所有图集与 QA 都标识为合成测试数据，不构成阿舟视觉通过证据。覆盖坏图解码、未用格、每格透明、主题及图片错配、方向 warning 门禁、未知同名目标、符号链接、路径逃逸、两进程锁冲突、交换后写入失败、进程中断、提交后清理、主题漂移后恢复、同主题不同候选状态，以及只读 status。

事务测试包含注入异常和模拟进程终止；不把它们称为真实断电测试。真实图集仍需按 hatch-pet 原生流程完成完整播放与视觉审阅，并在原生宿主刷新、选择后记录实际显示证据。
