# 启动动画迁移清单

状态：2026-10-26 从当时源仓维护工作树完成源码迁移并修正包内路径。本清单中的“源工作树”“本次”均指该次导入；同日后续本地安装交接见 [Hub 验证记录](../../evidence/optional-integrations-local-handoff-2026-10-26.md)。用户正联系上游维护者确认许可；在收到明确许可前不对外发布或再分发。历史验证文件仍只代表原工作树当时的证据。

## 候选运行时与维护面

| 范围 | 当前源工作树中的候选文件 | 迁移处理 |
|---|---|---|
| 原生播放器与校验 | `Native/App.swift`, `Native/Wallpaper.swift`, `Native/InstallRegistry.swift`, `Native/WallpaperValidationTests.swift` | 以检查时的工作树内容为准；不得用旧 `HEAD` 覆盖本地维护版本。测试为纯校验范围，不代表宿主接入验收。 |
| 动画前端 | `index.html`, `style.css`, `animation.js` | 保留当前 7.8 秒动画实现；私有角色图不包含在本包。 |
| 壁纸运行时 | `wallpaper/preview.html`, `wallpaper/renderer.js`, `wallpaper/wallpaper.css` | 保留源实现和显式宿主边界；不在迁移中安装或重启 Codex。 |
| 构建、安装与检查 | `tools/build-macos.sh`, `tools/build-extension.sh`, `tools/build-wallpaper.py`, `tools/install-macos.sh`, `tools/install-macos.py`, `tools/verify-artifacts.py`, `tools/prepare-azhou-assets.py` | 保留正式安装保护；仅修正包内路径和 Git 忽略检查，不执行安装。 |
| 回归与维护工具 | `tools/test-install-macos.py`, `tools/test-wallpaper.mjs`, `tools/manage-codex-pet.py`, `tools/test-codex-pet.py` | 运行前核对各自隔离范围；不使用真实 `CODEX_HOME`、宿主或安装状态。 |
| Pet 契约 | `pet/theme.json` | 随当前项目维护面保留；生成图集和用户级安装状态不迁移。 |
| 操作入口 | `扩展启动Codex.command`, `预览动画.command` | 保留当前安装/预览入口；只修正相对目录定位，不执行安装。 |
| 说明与证据文档 | `README.md`, `docs/references.md`, `docs/installation-lifecycle.md`, `docs/azhou-startup-design.md`, `docs/azhou-startup-verification.md`, `docs/azhou-vivid-maximized-verification.md`, `docs/azhou-installation-verification.md`, `docs/azhou-wallpaper-0.6.0-verification.md`, `docs/azhou-wallpaper-0.6.1-verification.md`, `docs/azhou-wallpaper-0.7.0-verification.md`, `docs/azhou-wallpaper-0.7.1-verification.md`, `docs/app-icon-0.5.2-verification.md`, `docs/upgrade-0.5.1-verification.md`, `docs/codex-pet.md`, `docs/codex-pet-verification-2026-10-25.md`, `docs/codex-pet-maintenance-2026-10-26.md`, `docs/asset-audit-and-replacement-plan.md`, `plans/README.md`, `plans/001-vivid-lab-motion.md` | 保留历史结论与未覆盖边界；只调整包根命令、失效链接和私人本机路径，不把历史验证写成此次验证。 |

## 排除项

- `.git/`、`.azhou/`、`.local/`、`.build/`、`dist/`、缓存、临时输出及安装产物。
- `assets/private/` 中的 `working.png`、`scene.js`、`wallpaper-scene-q-v3.png`、图标源图、来源记录及其他私有/生成素材。构建仍需要用户在本机单独提供并授权的输入；源码迁移不等于素材可用或允许分发。
- `docs/audits/` 下的机器盘点、绝对路径、文件摘要和本地证据索引。
- 源项目 `AGENTS.md`：其规则服务于原项目 checkout 与本地验收状态，不是播放器运行面；素材和历史路径约束已在本包说明中保留。
- 旧 `Native/Extension.swift`、`extension/` 动画覆盖实现、`image-settings.js`、`tools/extension-preview.mjs`、`tools/extension.test.mjs`，以及旧头像/图片/轮廓/粉色图标和 `tools/prepare-defaults.*`、`tools/trace-contours.swift`。源项目 README 与 `docs/references.md` 将它们标为不属于当前动画构建链路；保留它们会复活被弃用的动画覆盖和图片设置流程。

## 包内路径改造与验证边界

历史文档中的个人机器路径已脱敏：`$ORIGINAL_PROJECT_ROOT` 表示旧 checkout，`$PRIVATE_IP_ROOT` 表示原私有 IP 库，`$CODEX_HOME` 表示当时的 Codex 用户目录，`$HOME` 表示用户主目录，`$ICON_SOURCE` 表示用户提供的图标源，`$PET_RECOVERY_ROOT` 表示实际恢复记录指向的目录。这些是历史定位占位符，不是新包配置或可直接套用的安装命令。旧仓原始位置与恢复材料在删除旧 checkout 前归档至 Hub 的忽略目录 `.local/orphan-recovery/2026-10-26/`；公开交接摘要见上述验证记录。

源 shell 与 Python 工具多数从自身位置解析源项目根目录，迁入子目录后仍应指向本包根。包级 `.gitignore` 补充屏蔽 `.build/`、`dist/`、`assets/private/`、`.local/`、`.azhou/`、`docs/audits/` 和 `.app` 产物；需在子目录工作目录验证 `git check-ignore` 与 `git ls-files` 的实际结果。

README 与 `.command` 操作入口改用本包根路径；历史验证记录保留当时的运行环境并注明其为历史证据。源码导入没有复制私有图像与图标输入；后续本地交接把这些输入放入本包的忽略目录 `assets/private/`，并从最终 Hub 路径完成原生构建和安装交接。纯原生校验测试和安装器隔离测试本身不触发安装、宿主重启、CDP 注入或生产壁纸接入；实际执行范围以交接记录为准。
