# 参考、素材与版本范围

当前实现、准备步骤和日常入口以 [项目 README](../README.md) 为准。素材原件、包含素材的应用和验收画面均不得公开提交或发布。

## 当前阿舟版

- 动画使用素材库中的女性Q版工作姿态 `azhou-chibi-pet/v1.0.0/images/04-working.png`，1254×1254 RGBA。准备脚本逐字节复制到 `assets/private/working.png`，生成本地 `scene.js`；不覆写素材库。
- 工作姿态是合成图，没有独立关节图层；现有 WebGL 局部网格只表现小幅敲键、前倾和收束。精确构图和实机动效证据见 [0.5.0视觉验收](azhou-vivid-maximized-verification.md)。
- 原项目使用用户提供的方形PNG作为应用图标。私有源图和副本没有迁入；动画角色素材不随图标替换。历史来源、尺寸与系统显示记录见 [0.5.2图标验收](app-icon-0.5.2-verification.md)。
- 动效重做参考本机 `emil-design-eng`、`improve-animations`、`animation-performance`、`review-animations` 技能，并复用旧实现中的粒子预分配、SVG刻度和渐变光带能力；执行计划见 [动效计划](../plans/001-vivid-lab-motion.md)。
- 动画由本地 HTML / CSS / SVG / WebGL 绘制，无音轨、远程字体、CDN或在线图片请求。0.6.0通过原生辅助模式接入Codex内部静态壁纸，范围与实际验收见 [壁纸记录](azhou-wallpaper-0.6.0-verification.md)。

- 新壁纸使用 `assets/private/working-v2.png`，为依据正式女性v2身份图和Q版工作图，经内置ImageGen生成的项目私有衍生。原库只读，未写入正式资产路径，也不代表正式IP资产转正。精确提示词、来源SHA与生成记录保存在私有本地证据及 `wallpaper-provenance.json` 中。
- 新版壁纸只改变已核实外壳背景，保留输入区、菜单与代码块的原始颜色变量。模拟截图的视觉审阅与真实宿主确认分开记录。

## 历史实现参考

以下项目用于研究实现方式；除下一节明确列出的尺寸解析器外，未复制其源代码，也不需要安装或运行它们。

| 参考项目 | 当时研究的范围 |
| --- | --- |
| [Tangc/codex-skin-launcher](https://github.com/Tangc/codex-skin-launcher) | macOS 原生窗口、应用标识与独立启动入口 |
| [Fei-Away/Codex-Dream-Skin](https://github.com/Fei-Away/Codex-Dream-Skin) | Codex内部整窗壁纸、透明表面、本机CDP接入及目标进程校验 |
| [NativeDog1/dsh-boot-animation](https://github.com/NativeDog1/dsh-boot-animation) | 可跳过的覆盖式片头、完成后移除、素材就绪后播放和超时兜底 |

DSH 使用自己的覆盖层接口，不能直接安装到 Codex。旧扩展实现已从本包排除，范围与理由见 [迁移清单](../MIGRATION-INVENTORY.md)。

## 当前运行时源码复用

- `vendor/dream-image-metadata.mjs` 原样引入 Codex Dream Skin 的 `runtime/image-metadata.mjs`，固定于提交 [`6fc42df48a6a5365011f55cc349e20c038e56d1d`](https://github.com/Fei-Away/Codex-Dream-Skin/blob/6fc42df48a6a5365011f55cc349e20c038e56d1d/runtime/image-metadata.mjs)。其 MIT 条款保存在旁边的 `vendor/dream-image-metadata.LICENSE`；来源仓库的 [NOTICE](https://github.com/Fei-Away/Codex-Dream-Skin/blob/6fc42df48a6a5365011f55cc349e20c038e56d1d/macos/NOTICE.md) 将软件许可与图片素材权利区分开。
- `tools/build-startup.py` 只从原件装配 `readRawDimensions()` 及其私有格式解析辅助函数；移除该导出声明后解析算法未修改，也不装入分类器、50 MP 上限或 16384px 限制。直页面加载从原件确定性生成的 classic `image-metadata-reader.js`，生成载荷也从同一解析函数装配。
- 头部读取最多 2 MiB。本机尺寸样本包括 688,079 字节的 JPEG（SOF 位于偏移 156）和 1,999,598 字节的无损 WebP；超过预算或格式边界不完整时回到既有解码与最终尺寸校验。
- 更新时先固定新的上游提交并核对源文件和 MIT 许可，再保留完整原件、修订 classic 装配边界并运行原件及双入口回归。不要把未许可素材、生成输出或上游 50 MP 分类策略引入本包。

旧版 `assets/avatar.jpg`、`assets/artwork.jpg` 来自所有者提供的图片，并做缩放和居中裁切；`assets/contours.js` 由 macOS Vision 提取轮廓。旧自定义背景由本机 Canvas 生成轮廓，旧粉色启动图标由花形标志改色。这些素材和“头像碎片→线稿→彩色背景”的序列已不属于当前动画构建。

早期原型曾使用参考视频截图及 ImageGen 重建的备用图片；相关备用图片、截图与视频不在公开提交范围。人物素材、品牌标志与项目代码的权利分别归属；项目代码的使用说明不额外授予第三方素材许可。
