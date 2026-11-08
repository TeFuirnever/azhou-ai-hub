# Agent Skin 衍生面清点（2026-11-08）

范围：量化 `packages/agent-skin` 相对上游 `panding999/codex-startup-animation`（基础提交 `c743c2b5`，本地保留源树 `packages/codex-startup-animation/`，即 2026-10-26 迁入时的工作树状态）的血统分布，并估算"去衍生化"（以原创实现替换上游血统，使包不再含衍生代码）的工程量。方法：对迁移清单中的每对文件做 `git diff --no-index --numstat` 量化；"可能保留行数"按 旧行数−删除行数 估算（上界，含改写行）。数据截至 main `2a501cc`（#395 合入后）。

## 结论先行

- **ZCode 产品面（build 39 载荷）的衍生血统约 950 行**，集中在四处：`Native/Wallpaper.swift`（~441 行可能保留）、`wallpaper/renderer.js`（~227）、`Native/App.swift`（~188）、`wallpaper/wallpaper.css`（91 行近逐字）。
- **仓库级**另有六处逐字/近逐字与三个高保留测试（勘误后全量）：`tools/install-macos.py`（~495 行近逐字，Codex 宿主安装器）、`tools/manage-codex-pet.py`（819 行逐字）、`tools/test-wallpaper.mjs`（~542）、`tools/test-codex-pet.py`（~637）、`tools/test-install-macos.py`（~435）、`pet/theme.json`（43 行逐字）、`wallpaper/preview.html`（158 行近逐字）、`tools/prepare-azhou-assets.py` 与 `tools/build-extension.sh`（逐字小件）。
- **ZCode/DSH 宿主特有线全部为本项目原创**：`ZCodeSkinDriver/ZCodeSkinRuntime/ZCodeTransportTests`、`SkinHostContract`、`CodexSkinDriver`、`StartupNativeTests`（284K）、`extension/codex-page-adapter.mjs`、`extension/renderer.mjs`、`extension/hosts/*`、`extension/bootstrap.mjs`、`localization.js`、`image-metadata-reader.js`、`wallpaper/apply.js`、`tools/build-preflight.py`、`tools/build-startup.py`、`tools/build-startup-assets.swift`、`tools/build-dsh-plugin.py`、`image-settings.js`（旧版在 2026-10-26 导入时被明确排除，现 88K 文件为本项目重写）。共享基础设施 `InstallRegistryCore.swift` 为**部分例外**：主体提取自上游 `InstallRegistry.swift`（~28 行直接搬移 + 注册/溯源检查段保留上游实现），勘误改判非全原创。
- `vendor/dream-image-metadata.mjs` 为第三方依赖但**带 MIT 许可证**，保留合法，不需要去衍生。

## 逐文件量化（迁移对）

| 文件 | 上游行数 | 现行数 | 增量 | 可能保留（上界） | 血统浓度 |
|---|---:|---:|---|---:|---|
| `wallpaper/wallpaper.css` | 94 | 95 | +4−3 | 91 | **96% 近逐字** |
| `pet/theme.json` | 43 | 43 | 逐字 | 43 | **100% 逐字** |
| `wallpaper/preview.html` | 159 | 159 | +1−1 | 158 | **99% 近逐字**（非构建输入夹具） |
| `tools/install-macos.py` | 506 | 566 | +71−11 | 495 | **87%**（Codex 宿主安装器） |
| `wallpaper/renderer.js` | 270 | 512 | +285−43 | 227 | **44%** |
| `Native/Wallpaper.swift` | 574 | 1663 | +1222−133 | 441 | **26%** |
| `Native/App.swift` | 433 | 1884 | +1696−245 | 188 | **10%** |
| `tools/build-wallpaper.py` | 65 | 85 | +24−4 | 61 | 72%（构建工具） |
| `tools/build-macos.sh` | 87 | 66 | +42−63 | 24 | 重构 |
| `animation.js` | 201 | 1996 | +1991−196 | ≤5 | **已基本去衍生**（vivid-lab-motion 重设计） |
| `Native/InstallRegistry.swift` | 112 | 21 | +12−103 | 9 | 已拆分至原创的 InstallRegistryCore |
| `Native/WallpaperValidationTests.swift` | 125 | 2068 | +1945−2 | ≤123 | 已重写 |
| `index.html` / `style.css` | 76/47 | 32/79 | 重构 | 少量 | 结构性重写 |
| `tools/verify-artifacts.py` | 316 | 1198 | +894−12 | 304 | 26%（校验框架） |
| `tools/manage-codex-pet.py` | 819 | 819 | 逐字 | 819 | **100% 逐字**（勘误补入：初版清点遗漏） |
| `tools/test-wallpaper.mjs` | 543 | 628 | +86−1 | 542 | **86%**（勘误补入） |
| `tools/test-codex-pet.py` | 637 | 794 | +157−0 | 637 | **80%**（勘误补入） |
| `tools/test-install-macos.py` | 453 | 934 | +499−18 | 435 | **48%**（勘误补入） |
| `tools/prepare-azhou-assets.py` | 42 | 42 | 逐字 | 42 | **100% 逐字**（勘误补入） |
| `tools/build-extension.sh` | 5 | 5 | 逐字 | 5 | **100% 逐字**（勘误补入） |
| `Native/InstallRegistryCore.swift` | （提取自 InstallRegistry） | 128 | 对上游 InstallRegistry +100−84 | ≤28+注册/溯源检查段 | **搬移≠原创**（勘误改判：47–74 行 plist 读取与 inventory 实现自上游搬移） |

## 去衍生化工作量估计（勘误后全量）

| 范围 | 需重写行数 | 估计工作量 |
|---|---:|---|
| **仅 ZCode 产品面**（若只分发 ZCode 入口 App） | ~950 行：Wallpaper.swift 血统段 + wallpaper/renderer.js 血统段 + wallpaper.css 重写 + App.swift 血统段 | 数天级（ Swift 壁纸核心与 JS 渲染器各占一半；有 2068 行验证测试和像素护栏兜底） |
| **全仓去衍生**（含 Codex 工具链与测试，勘误后全量） | ZCode 产品面 ~950 + install-macos.py ~495 + manage-codex-pet.py 819 + test-wallpaper 542 + test-codex-pet 637 + test-install-macos 435 + theme.json 43 + preview.html 158 + prepare-azhou-assets 42 + build-extension.sh 5 + InstallRegistryCore 搬移段 ~28 ≈ **~4200 行** | 二至三周级 |

### 勘误（2026-11-08，Codex 评审发现）

初版清点遗漏了迁移清单中的 `tools/manage-codex-pet.py`（819 行逐字）、`tools/build-extension.sh`、`tools/prepare-azhou-assets.py`、`tools/test-wallpaper.mjs`、`tools/test-codex-pet.py`、`tools/test-install-macos.py`，且 `tools/verify-artifacts.py` 的 304 行保留未计入全仓总数；`Native/InstallRegistryCore.swift` 被误标"原创"——其 47–74 行 plist 读取与 inventory 实现系自上游 `InstallRegistry.swift` **搬移**（搬移不等于原创），注册/溯源检查段亦保留大量上游实现。全仓总数由 ~1650 修正为 **~4200 行**；ZCode 产品面 ~950 的估算不受影响（遗漏文件均非 ZCode 构建输入）。

替代路径对比：上游（panding999）一句再分发授权 = 零工程量；去衍生化 = 上述工作量但永久解除上游依赖。两者可并行：清点本表可直接作为与上游维护者沟通的附件（明确请求范围仅限列出的血统段）。

## 边界

- "可能保留行数"是 numstat 推导的上界；逐行确认需三 way 对比（上游 HEAD/迁移工作树/现行），本表给量级。
- 素材门与代码门相互独立：即便代码去衍生化完成，`assets/private` 私有美术仍受其自身授权约束，不在本清点范围。
- 本清点为工程记录，不含私有素材与机器路径；可随包公开。
