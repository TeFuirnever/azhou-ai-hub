# Codex pet：文件核验、用户级清理与动作扩展边界（2026-10-26）

## 结论与适用范围

本轮通过 Remote Desktop Commander **重新读取本机文件并运行测试**，不是照搬前次验收。关键 pet 源码、主题和安装内容一致，`0.7.1` 启动器安装器 `--check` 返回 `current`，用户 Applications 实体包一份、dist 额外包零份、系统登记一条。原生 pet 的实际刷新、选择与完整动画 **仍未观察**，不可宣称已应用。

本轮的“移除”范围是当前 `~/.codex/pets/` 可扫描的用户自定义 pet 文件夹，不是在线账户 pet 库或官方宿主安装包。官方内置 pet 由应用自己的资源提供，不在此次删除路径内。应用配置存在另外的 `selected-avatar-id = pet_…`，它不对应本轮扫描到的自定义目录 ID；其真实来源/有效性尚未从 UI 独立确认，**没有强制切换或删除**。

## 1. 相关项目文件的更新核验

| 项目 | 新核查结论 |
| --- | --- |
| `README.md` | 已含 pet 使用、同步、主题失配处理及验收链接；链接存在 |
| `AGENTS.md` | 原来缺少 pet 维护边界；本轮仅插入 `Native Codex pet` 小节，原字节内容完整保留 |
| `pet/theme.json` | 当前四项主题输入摘要匹配，源修订 `916ed5e9…772ae` |
| `tools/manage-codex-pet.py` | 命令及 SHA 与前次经过测试的版本相同；`status` 确认候选、安装同源 |
| `tools/test-codex-pet.py` | 本轮隔离测试 **34/34 通过**（实际执行），涉及损坏资产、锁、事务与拒绝条件 |
| `docs/codex-pet.md` | 命令和运行边界存在；相关文档链接核查通过 |
| `docs/codex-pet-verification-2026-10-25.md` | 保留上轮实际生成/安装/视觉证据，不能替代本轮宿主运行测试 |
| `~/.codex/pets/azhou-agent-lab/` | 原生 manifest、图集、receipt 完整；图集完整解码，项目包、安装与主题匹配 |
| 启动器 | 实际安装 `0.7.1 / current`；本轮不构建或修改它 |

局部检查确认 20 处 README/pet 文档链接有效；`.local/pets` 与审计证据仍被 Git 忽略。大部分 pet 源码和文档在此工作树尚为**未被 Git 跟踪的新文件**，不应把本机可用等同于已提交或发布。

一致性边界：`sync` 安装的是已生成、已审阅的候选包，不会在主题改变后自动调用 ImageGen 创作新动作或皮肤。当前修订输入不是全部视觉代码；例如单改 `wallpaper/wallpaper.css` 不一定令 pet 修订失效。若以后要求全主题一键联动，需要明确哪些共享设计 Token 必须进入统一的主题 manifest，不能把当前实现称为全自动生图。

## 2. 已执行的自定义 pet 清理

从用户级扫描目录移出以下五个经过目录结构、JSON 身份和 10 个文件摘要核对的项目：

- `clawd`（Clawd；属于自定义文件，并非 Codex 内置 pet）
- `deepseek-whalechan--qimi`（蓝色大肥鱼·Q版女仆）
- `guga`（咕嘎）
- `monthly-salary-cat`（Monthly Salary Cat）
- `rem--l1`（Rem）

移除使用相同 APFS 卷上的原子重命名；未删除未识别文件。执行后 `~/.codex/pets/` 的用户级目录仅有 `azhou-agent-lab`。系统内置的 `codex`、`dewey`、`fireball`、`hoots`、`rocky`、`seedy` 位于官方资源，未触碰。阿舟 `pet.json`、WebP、receipt 的三项 SHA 均与移除前相同。

本地恢复路径：
`/Users/guanxueliang/.codex/.pet-removal-recovery/20261026-010348-c27a29d9/`

五个目录已离开 app 的自动扫描范围，但**恢复副本仍在磁盘上**，不是永久粉碎。恢复前确认同名目录尚未重新安装，只把需要恢复的单个目录移回 `~/.codex/pets`。不要把整个恢复目录移入 `pets`：当前宿主连隐藏子目录也会扫描。没有修改选中 pet 设置、退出宿主、清理 IP 素材或执行 `git clean/reset`。

证据：`.local/evidence/20261026-pet-cleanup/cleanup-result.json`、`post-cleanup-verification.json`、`agents-pet-update.json`；恢复目录内另有 `cleanup-journal.json` 和 `README.txt`。本轮仅验证本机用户目录，无法据此推定在线账户或其他设备上没有自定义宠物。

## 3. 能否增加更多动作

**可以增加动画表现，但当前 v2 原生协议没有自由添加第十个状态的接口。** 本机 `26.1021.31345 / build 21828` 的原生 UI 代码固定接受图集 `1536×2288`，8 列×11 行、格 `192×208`。前九行依次是 `idle(6)`、`running-right(8)`、`running-left(8)`、`waving(4)`、`jumping(5)`、`failed(8)`、`waiting(6)`、`running(6)`、`review(6)`；后两行是 16 个视线方向。工具链还有一个不进入宿主动画映射的辅助 neutral 格。未用格直接绘制新动作不会触发额外状态，改写 `pet.json` 加自定义键也不能替宿主注册事件。

可直接实现的下一批质量改进（不改宿主、不增加图集行数）：

1. **待机**：在现有六帧里重新编排呼吸、眨眼、耳朵和尾巴的微动作，建立统一脚部基线与高光连续性。
2. **等待/工作/审阅**：分别呈现思考、专注敲键、读完点头或微庆祝；仍由原生 `waiting/running/review` 事件触发，不能擅自声明新增“写代码完成”等事件。
3. **移动/跳跃/失败**：左右动作独立画，不生硬镜像腰包和蝴蝶结；强化起跳、腾空、落地和失败后收束的逐帧节奏。
4. **16 方向**：改善接近水平的斜向眼神及头部朝向；保留四个 cardinal 的严格门禁。
5. **交付门禁**：全部重新生图和去色边后，按一个图集做逐格尺寸、alpha、角色 ID、基线、低尺寸可读性、盲测及宿主实际状态播放；减弱动态模式应使用静态帧。

若确需新增“睡觉、吃东西、拿书、欢呼”等**独立可触发状态**，需要等待官方格式/消费者支持，或另建受控自有渲染层；现阶段不能靠填入 v2 空白格实现，更不应改写官方宿主或私有 IP 库。官方 deep-link 参数目前也只接受 `spriteVersionNumber` 1 或 2（[Developer Commands](https://learn.chatgpt.com/docs/reference/commands)）；[Pets 使用文档](https://learn.chatgpt.com/docs/pets) 描述了可用端、选择/刷新及减少动态效果，未提供任意自定义事件 API。

## 4. 仍待实际生效验收的项目

- 应用设置里刷新自定义 pet 并确认清理的五个不再出现（不自动切换/刷新，以免打断当前工作）。
- 确认选择阿舟后的真实界面图集、完整动作播放及鼠标四方向与斜向响应；脚本的 `pending-refresh-selection` 是保守状态。
- 配置里 `pet_…` 所属来源尚未从宿主选择器核实。它并不位于被清理的五个本地目录；若 UI 中另有来源的自定义 pet，需要单独辨认和处理，不能声称已清空所有注册来源。
- 想增加新的原生事件前先核验新版宿主契约，不能沿用旧版协议推断未来支持。
