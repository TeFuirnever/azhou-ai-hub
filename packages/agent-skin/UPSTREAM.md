# 上游来源与授权边界

本文件记录既有 Hub 源码的原始导入来源。2026-10-27 设定 `agent-skin` 为 canonical Hub package 时保留了既有 `packages/codex-startup-animation/` 源目录；本次没有改写原始仓库、commit 或本地安装/Pet 回执身份。

## 来源

- 上游仓库：<https://github.com/panding999/codex-startup-animation>（用户提供的来源地址）
- 本地源仓 `origin`：<https://github.com/TeFuirnever/codex-startup-animation.git>
- 检查时的源仓 `HEAD`：`c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248`
- 工作树基线：上述 `HEAD` 加上 2026-10-26 检查到的未提交修改及未跟踪维护文件。`HEAD` 不代表完整迁移内容，完整输入来自当时的源工作树。

迁移修改包括包路径和失效历史证据链接说明、包级忽略规则与来源元数据，以及八个导入文本文件的 EOF 空行规范化。活动代码的语义保持原样；导入不是原始提交的逐字节镜像。

## 授权状态

源仓根目录没有 `LICENSE`、`NOTICE` 或 `COPYING` 文件，也没有发现授予本包再分发权的许可文本。源仓 `docs/references.md` 说明历史参考项目仅用于研究、未复制其源码；该说明不能替代本项目代码许可，也不覆盖素材权利。

用户已授权本地迁移。Hub 包中记录该上游归属，并保留源工作树当时维护的代码与文档。2026-10-26 导入时，用户联系上游维护者确认许可，并在得到明确许可前暂停对外发布。本文件不推定上游的开源许可，也不构成权利转让。

[#441](https://github.com/TeFuirnever/azhou-ai-hub/pull/441)（2026-11-11）按 [衍生面清点](../../evidence/agent-skin-derivative-surface-audit-2026-11-08.md) 独立重写了仍与迁入快照重合的代码段。自此本包代码按仓库根 [MIT 许可证](../../LICENSE) 发布。上游仓库及 Git 历史中已删除的 `packages/codex-startup-animation/` 字节仍未获许可，MIT 不覆盖它们，本包也不再分发它们。

2026-11-13 复核：上游只有 3 个提交，`c743c2b5` 为最新；其中 23 个代码文件共 951 行有效内容（去空白后不少于 25 个字符）中，只有 31 行在当前包内出现，均为通用 API 或样板写法，例如 `import UniformTypeIdentifiers`、`let app = NSApplication.shared`、`codesign --force --sign - "$bundle"`、`<link rel="stylesheet" href="style.css">`。Pet、壁纸、安装器、校验器及其测试从未出现在上游任何提交中，它们来自本地维护工作树。包内也没有上游文件头或版权行；`vendor/dream-image-metadata.mjs` 是另一个 MIT 依赖，许可证保留在旁。

MIT 只覆盖代码。`assets/private/` 的私有阿舟图像、Pet 素材及用其构建的产物不在此许可内，其授权尚未决定，不得对外发布。

2026-10-26 的源码导入排除了私有阿舟图像、生成素材和本地机器验收产物。同日的本地交接将构建所需私有输入放在 Hub 包内被 Git 忽略的 `assets/private/`；它们仍不属于跟踪源码或公开分发内容。参见 [迁移清单](MIGRATION-INVENTORY.md)和 [本地交接记录](../../evidence/optional-integrations-local-handoff-2026-10-26.md)。

## Hub 运行评估

Hub adapter 按已核验的 App 版本选择日志评估方式：0.7.1 继续走旧事件评估；0.8.0 及更高版本要求被消费事件符合 `azhou-startup.event.v1`。已知诊断事件可以没有 schema，但不会被当作启动成功证据。合成事件测试验证适配器判定，不证明原生启动器实际产生日志、不构成上游许可，也不扩大素材使用权。
