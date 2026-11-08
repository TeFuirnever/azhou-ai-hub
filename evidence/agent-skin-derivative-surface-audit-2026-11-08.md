# Agent Skin 衍生面清点（2026-11-08）

范围：量化 `packages/agent-skin` 相对上游 `panding999/codex-startup-animation`（基础提交 `c743c2b5`，本地保留源树 `packages/codex-startup-animation/`，即 2026-10-26 迁入时的工作树状态）的血统分布，并估算"去衍生化"（以原创实现替换上游血统，使包不再含衍生代码）的工程量。方法：对迁移清单中的每对文件做 `git diff --no-index --numstat` 量化；"可能保留行数"按 旧行数−删除行数 估算（上界，含改写行）。数据截至 main `2a501cc`（#395 合入后）。

## 结论先行

- **ZCode 产品面（build 39 载荷）的衍生血统约 950 行**，集中在四处：`Native/Wallpaper.swift`（~441 行可能保留）、`wallpaper/renderer.js`（~227）、`Native/App.swift`（~188）、`wallpaper/wallpaper.css`（91 行近逐字）。
- **仓库级**另有三处：`tools/install-macos.py`（~495 行近逐字，Codex 宿主安装器）、`pet/theme.json`（43 行逐字）、`wallpaper/preview.html`（158 行近逐字，非构建输入的夹具）。
- **ZCode/DSH 宿主线全部为本项目原创**：`ZCodeSkinDriver/ZCodeSkinRuntime/ZCodeTransportTests`、`SkinHostContract`、`InstallRegistryCore(+Tests)`、`StartupNativeTests`（284K）、`extension/codex-page-adapter.mjs`、`extension/renderer.mjs`、`extension/hosts/*`、`extension/bootstrap.mjs`、`localization.js`、`image-metadata-reader.js`、`wallpaper/apply.js`、`tools/build-preflight.py`、`tools/build-startup.py`、`tools/build-startup-assets.swift`、`tools/build-dsh-plugin.py`、`image-settings.js`（旧版在 2026-10-26 导入时被明确排除，现 88K 文件为本项目重写）。
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

## 去衍生化工作量估计

| 范围 | 需重写行数 | 估计工作量 |
|---|---:|---|
| **仅 ZCode 产品面**（若只分发 ZCode 入口 App） | ~950 行：Wallpaper.swift 血统段 + wallpaper/renderer.js 血统段 + wallpaper.css 重写 + App.swift 血统段 | 数天级（ Swift 壁纸核心与 JS 渲染器各占一半；有 2068 行验证测试和像素护栏兜底） |
| **全仓去衍生**（含 Codex 工具链） | ~950 + install-macos.py ~495 + theme.json 43 + preview.html 158 ≈ **~1650 行** | 一至两周级 |

替代路径对比：上游（panding999）一句再分发授权 = 零工程量；去衍生化 = 上述工作量但永久解除上游依赖。两者可并行：清点本表可直接作为与上游维护者沟通的附件（明确请求范围仅限列出的血统段）。

## 边界

- "可能保留行数"是 numstat 推导的上界；逐行确认需三 way 对比（上游 HEAD/迁移工作树/现行），本表给量级。
- 素材门与代码门相互独立：即便代码去衍生化完成，`assets/private` 私有美术仍受其自身授权约束，不在本清点范围。
- 本清点为工程记录，不含私有素材与机器路径；可随包公开。
