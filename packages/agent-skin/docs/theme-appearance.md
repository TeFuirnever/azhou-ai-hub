# 主题与外观配置

点击阿舟外观入口进入设置。Home 导航存在唯一可见的 Your dot 时，入口位于其下方、Pinned 上方；无法确定唯一目标时尝试使用备用位置，无空位时暂时隐藏。设置标题下显示当前运行载荷的版本与 build，可用于核对是否已加载新安装。页面按工作区背景、启动动画和关于与状态组织；修改留在草稿，保存成功后才应用，取消不保存。预览动画使用草稿，不会保存设置或改变工作区背景。在宿主设置页内嵌呈现（`settings.section`）时，同一面板以非模态内联展示：Tab 可进出该区块，Escape 把焦点交还宿主页面，保存后面板保持打开可继续编辑，取消仅丢弃草稿；面板随宿主卸载该区块而移除。

## 配置覆盖

| 配置 | 当前来源与所有者 | 页面能力 | 生效方式 |
| --- | --- | --- | --- |
| App 中英名称、安装文件名 | `theme-config.json` 的 `identity`；构建所有 | 只读展示，展开修改流程 | 修改配置，重新构建并按安装生命周期安装 |
| App 图标、bot 头像 | `identity.iconInput`、`identity.entryAvatarInput` 指定的 `assets/azhou/` 文件（可被同名覆盖层替换） | 展示各自来源；bot 头像用于入口和页面标识 | 替换文件后重新构建安装；两者不能共用路径 |
| bot 中英名称 | `identity.botName` | 只读，跟随界面语言显示 | 重新构建安装 |
| 版本、build | `hub-package.json`，构建注入 `themeConfig.identity` | 只读展示 | 新构建；没有第二份可写版本定义 |
| 启动标题、标题说明、背景字幕 | `startup.text` 为双语默认值；用户可覆盖 | 编辑、恢复默认、预览草稿 | 保存后供下次启动使用；已保存自定义文字不因语言切换而改写 |
| 启动头像 | 构建默认图；当前页面 IndexedDB 用户覆盖 | 选择图片、预览草稿 | 保存后供下次启动使用；不改变 App 图标或 bot 头像 |
| 背景图片 | 构建默认图；当前页面 IndexedDB 用户覆盖 | 选择图片、查看草稿预览 | 保存后应用到工作区；壁纸失败单独报告 |
| 背景强度 | `wallpaper.strength` 默认 42；用户覆盖 | 0–75 滑块 | 保存后应用到工作区；0 关闭背景效果 |
| 背景布局 | 现有 wallpaper CSS | 只读说明 | cover 填满，保留右侧主体；窄屏调整位置 |
| 动画时长与阶段 | `startup.durationMs` 声明固定 12000ms 的运行契约 | 只读说明；保留现有跳过与预览控制 | 构建拒绝其他时长；不新增速度偏好 |
| 语言、深浅色、基础颜色 | 官方应用当前页面的属性与颜色 token | 只读显示当前语言、深浅色、解析背景色及来源 | 随宿主变化即时更新，不写入本地偏好 |
| 减少动态 | 系统 `prefers-reduced-motion` | 只读显示当前值 | 即时更新；控制器转发宿主媒体变化，释放时移除监听 |
| 当前保存来源 | 设置读取结果 | 显示构建默认、本机用户值或读取失败后的默认回退 | 只描述当前页面所在存储空间，不声称跨应用同步 |

## 定义与保存边界

`theme-config.json` 是构建所有的主题定义，包含双语显示身份、身份素材路径、启动默认文案和背景默认强度。构建器校验此文件，把完整定义随现有 `assets` 注入启动载荷与独立预览；本地化工厂、设置页、Info.plist/InfoPlist.strings、原生窗口和菜单使用该构建结果。配置及构建器均纳入现有输入指纹，不另加常驻服务或可写全局配置。

保留的 `--wallpaper-helper` 维护入口也使用同一 `wallpaper.strength` 构建默认值，包含 `0`；它不读取或写入用户 IndexedDB 覆盖。

显示名称不参与安装归属证明。Bundle ID `local.azhou.codex-startup`、可执行文件 `AzhouCodexStartup`、日志和 IndexedDB 身份保持现有合同；安装器仍核验来源、载荷、唯一登记与恢复条件。具体安装步骤见 [installation-lifecycle.md](installation-lifecycle.md)。

从 build 11 开始，Info.plist 中的默认 Bundle 名称与固定安装文件名（去掉 `.app`）保持一致，让 Finder 能识别中英文 `InfoPlist.strings`。Finder 显示语言由 macOS 决定；应用内界面跟随官方宿主，独立维护命令的人类可读消息跟随系统首选语言。测试分别检查系统 Finder 显示结果和两种资源选择，不把进程语言覆盖当作系统 Finder 语言切换。

主题改名与来源接管可以一起执行：`--migrate-from` 仍须证明旧来源记录、旧构建载荷、已安装入口、签名与指纹全部吻合，并核对唯一登记。旧名称可以不同于新目标，但只能是受管 Applications 目录中的直接 `.app` 入口。中断后的重试使用回执记录的精确旧路径，不按名称猜测归属。

用户图片、文字和强度继续使用 `azhou-codex-startup` 数据库、`settings` store 的 `images` 记录，schemaVersion 1 不变。构建主题、官方偏好、系统偏好和 bot 头像不进入用户记录。保存继续采用完整候选校验与事务内基线冲突检查；取消、配额、超时和资源释放沿用现有合同。恢复默认只修改草稿，保存后才替换用户覆盖。

素材路径写成 `assets/azhou/<名称>`，构建先找 `assets/private/<名称>` 覆盖层，再用 `assets/azhou/`；不接受穿越或符号链接。启动文案上限为 UTF-16 16/48/60 单位；背景强度范围和 12 秒阶段结构是现有运行契约，不是新增调节项。更改这些限制需要实现和验证运行时，不能只修改 JSON。

## 双入口图标构建

构建读取 `identity.iconInput`（`assets/azhou/app-icon/source.png`，可被同名覆盖层替换）。该 PNG 不得与 `identity.entryAvatarInput` 共用路径；嵌入应用的主题保留原有三段结构和已选定的 `identity.iconInput` 字符串；历史 Codex 配置无需增加映射。

`bash tools/build-macos.sh` 构建 Codex 候选。图标源图要求至少 1024×1024 的方形 PNG；图标与 bot、启动动画素材分别管理。

自定义素材以原字节放入 `assets/private/` 同名路径，并保留来源、SHA-256 和审阅边界；覆盖层、ICNS 与应用产物均不得提交到 Git。`assets/azhou/` 的发布素材按 CC BY-NC-ND 4.0 授权，名称与形象见根目录 TRADEMARKS.md。产物检查需核对候选构建的图标；候选构建成功不代表 Finder、Dock、启动台的已安装入口已经完成实机验收。

## 验证边界

Build 12 修复工作区外壳晚于启动动画出现时壁纸失效的问题：等待最长 60 秒，动画自然结束不再取消同一轮仍有效的壁纸请求。取消、覆盖或释放仍使旧请求失效。生成载荷浏览器测试覆盖自然结束后挂载、60 秒超时及观察器清理；真实冷启动仍须在用户完整退出官方应用后观察，不主动重启现有会话。

本功能候选使用合成图片、隔离 Chrome、原生假宿主及 Hub 适配器测试验证。生成载荷测试实际执行构建出的完整启动脚本，覆盖保存、草稿预览及严格样式 CSP 下的设置入口。候选界面截图用于检查中英、深浅色和窄屏排版，不代表私有素材审定或官方宿主视觉验收。

官方宿主的语言、主题、bot 和实际呈现仍须单独验收；此前官方 App 的 Computer Use 拒绝不通过其他自动化规避。安装、签名与唯一入口验收仍属于安装生命周期中的独立步骤，历史测试不能代替当前安装的核验。


## Codex 活动工作区合同

Codex 页面适配器的 `codex-active-workspace/v1` 能力按当前 Document、页面代际和唯一可见主工作区观察绘制平面。生产 bootstrap 将该观察贯穿图片准备、解码、首次写入与持续检查；缺失、歧义或失效不会退回旧私有选择器猜测。独立 legacy/preview 入口仍有兼容目录，DSH 继续使用自己的完整 wallpaper ports；这不是全仓宿主边界迁移完成的声明。

背景样式只标记本实例已观察的平面，未知消息区域或辅助面板保持 `unknown`，不能由空匹配或 `applied` 推导全页面覆盖。失效先释放本实例资源，再由现有页面控制器在当前请求仍有效时有界重新观察。已知同 Document 导航可恢复已批准背景，不重播动画、不更新旧设置快照的身份。禁用、取消、新设置、卸载及不同 Document 使旧恢复失效；超时保留失败状态，不无限循环。Native 准备结果与之后的当前壁纸状态分别保留，背景曾成功提交不等于原生动画 ready 或宿主可操作。

能力字段属于已加载的控制器，而非磁盘上的源码。只有已知标签与三个 own-data 观察／当前性／监听函数完整时才暴露该字段；字段不是 ready 证明。声明了契约却缺成员、使用继承／getter 成员或未知标签时，生产链拒绝该壁纸能力，不丢弃 adapter 后转入 legacy。同版本旧控制器不会因重复注入自动获得此合同；验证新能力需要重新加载对应页面并核对控制器及生成载荷身份。不得因此主动重启用户会话。单元、合成 DOM 和生成载荷浏览器检查不等于官方宿主验收；Dot、侧栏、其他页面、真实输入与升级回退仍须绑定实际安装版本分别验证。


工作区重新观察期间对外仍是 `applied: false`，但不会把正常的有界恢复立即作为失败通知插入导航；只有恢复已结束且失败、结构不支持或超时才显示错误。当前仍会对已观察祖先的宿主 class/style 变化保守地撤销并重新解码背景，例如侧栏网格宽度变化。此策略的可见闪烁、首帧连续性与代价尚须同版真实宿主视觉和独占性能验收；功能测试通过不表示这些指标已通过。

## P07 theme foundation candidate

This engineering subset adds one bundled Azhou theme and per-theme readability preferences. It does not deliver the full theme library, imported themes, or full Dream Skin parity. The Codex adapter grants only the named `workspaceReadability` capability. Menus, composer, dialogs, sidebars and other UI surfaces remain outside this capability. Unknown capabilities reject theme application without expanding selectors or changing native controls. A successful settings transaction is not proof of successful appearance application. DSH theme surfaces are not yet admitted.

Legacy wallpaper strength keeps its 0–75 semantics. The theme readability treatment replaces, rather than stacks with, the legacy wash. It does not lower text opacity. Real-host visual continuity, keyboard/IME interaction, reduced-motion flows and performance remain unverified until separately exercised against the exact loaded candidate.

The candidate keeps the scene image in its existing single body background plane. A color-only SVG replaces the wash inside the adapter-authorized workspace rectangle; it contains no artwork, text, or external resources and creates no foreground layer. Geometry is versioned and bound to the document/workspace epoch. The existing workspace observer and lease deliver resize and captured-scroll geometry; a second controller or observer is not introduced. Unknown geometry, transforms, masks, or adapter contracts refuse the theme rather than guessing.

Mask decoding shares the existing 4000 ms anti-hang ceiling with scene decoding. This is not a performance or recovery SLO: on a geometry or appearance change, the owner restores the legacy treatment synchronously before awaiting a fresh mask. `themePending`, `themeApplied`, `themeFailure`, and `fallbackApplied` distinguish a pending/degraded theme from a persisted settings record. A late decode cannot overwrite a newer generation or a foreign wash. Native-host rendering, responsiveness, and the full theme surface library still require separate acceptance.

### Appearance file boundary

Codex and DSH accept images selected by the user and individual Azhou JSON
presets. They do not offer an external theme catalog or import external theme
packages. Settings are local to the respective Azhou store; opening Appearance
does not scan or copy another project's files.

An older saved external-theme selection is not applied. The runtime uses a
valid retained Azhou appearance when available, otherwise the configured Azhou
default. Loading settings neither rewrites existing records nor deletes old
theme data. This is separate from upgrading or rolling back an Azhou launcher
or DSH package.

### Geometry and pending decode boundary

The current Codex adapter admits only finite, axis-aligned workspace geometry. Ordinary ancestor overflow clips must demonstrably contain the entire workspace rectangle; partial clips, reserved scrollbar ambiguity, rounded ancestor clips, extended overflow clip margins, transforms and complex clipping are not supported for theme treatment. Same-size ancestor style changes invalidate the existing lease. This restores native presentation, not a claim that the previous wallpaper survives; a later supported workspace may be admitted by the existing recovery flow. Legacy wallpaper admission is unchanged.

Every pending startup wallpaper application has an abort signal owned by the existing PageController generation. Disable, replacement and disposal cancel initial scene/mask decoding and release its timers and image references; the four-second deadline is only an anti-hang ceiling, not a recovery or performance target. Settled owners retain their existing disposal and handover lifecycle. Synthetic Chrome proves the cancellation path and native input, not installed Codex or DSH visual acceptance.

After a workspace lease is revoked, the existing startup owner attempts bounded recovery once the startup/overlay gate permits it. If clipping remains unsupported, this attempt ends with the existing apply-failed notice and Retry action. Restoring supported geometry alone does not start indefinite polling: the user can choose Retry to apply the saved theme. Saved settings are not erased by this failure. The current notice is the generic background-application failure, not a claim that saving failed.

### Theme draft round trips and defaults

Within an open settings panel, Existing appearance and the Azhou theme retain their own artwork/contour drafts; switching between them does not overwrite an unsaved custom image or transparency edit. Cancel discards both draft states. Disabling a theme normally preserves its remembered transparency, while Restore all defaults explicitly resets that preference to Follow theme when saved. Restoring defaults and then cancelling does not change saved images or preferences. Both records still share the same conflict-checked save transaction.

### Skip 与已准入的背景解码

Skip 立即退出启动层，不等待背景解码。仅在 Skip 之前已由版本化适配器取得固定工作区 observation 与有效 lease、并进入图片解码的同一请求，可以继续收尾。此权限绑定原请求、代际、文档 token 和工作区 epoch；不会在 Skip 后获取新工作区。仍在等待外壳、未报告准入的旧适配器、取消设置、页面隐藏、节点替换、卸载及新请求继续使旧工作失效。动画 ready 不是背景准入。

该边界由生成载荷的受控 decode、真实 Skip 点击及取消/替换负例检查；不代表真实宿主视觉衔接已经验收。

## P07 theme-control usability slice

The theme and reading-mask mode use visible, associated labels and full-width native selects within the existing settings field grid. The transparency slider spans its row; its adjacent readout and accessible value show the actual override percentage, or **Follow theme** when author-defined mask values apply. Increasing transparency clears the reading mask, not the text or icons. Existing appearance and Follow theme explain why the slider is unavailable. These labels and explanations follow the current host language, without persisting a language preference.

Background strength remains a separate 0–75 setting. For the Azhou theme, nonzero strength does not replace the reading-mask preference; zero still disables the background. The UI change does not change image/theme records, draft round trips, atomic save/conflict rules, cancel behavior, or the separate embedded-settings work.

Verification for this slice covers visible label association, override 0/50/100, Follow theme, disabled explanations, language changes, actual keyboard range input and Tab, narrow-window hit testing and overflow, and independent strength-zero behavior. Generated-browser fixtures are engineering evidence, not real-host acceptance. Branded artwork previews, host visual approval and performance acceptance remain separate gates; synthetic screenshots do not satisfy them.

### Current verification status: BLOCKED

The UI candidate passed focused layout, keyboard, Restore All and localization checks, independent review, repository validation and coverage. Its latest full generated-browser run did not pass: a transient settings-open assertion and later natural-playback, decode and CDP timeouts were observed. A bounded follow-up reproduced neither the later timeouts nor a cause; focused passes do not replace the failed aggregate gate. The settings-open check now requires a strictly newer loading-or-ready settings run and retains the subsequent open-dialog, persisted-value and resource checks. This recovery checkpoint is not a release-ready or merge-ready claim. Full aggregate validation, real-host acceptance and branded visual review remain open.
