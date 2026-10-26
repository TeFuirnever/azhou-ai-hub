# 上游来源与授权边界

## 来源

- 上游仓库：<https://github.com/panding999/codex-startup-animation>（用户提供的来源地址）
- 本地源仓 `origin`：<https://github.com/TeFuirnever/codex-startup-animation.git>
- 检查时的源仓 `HEAD`：`c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248`
- 工作树基线：上述 `HEAD` 加上 2026-10-26 检查到的未提交修改及未跟踪维护文件。`HEAD` 不代表完整迁移内容，完整输入来自当时的源工作树。

迁移修改包括包路径和失效历史证据链接说明、包级忽略规则与来源元数据，以及八个导入文本文件的 EOF 空行规范化。活动代码的语义保持原样；导入不是原始提交的逐字节镜像。

## 授权状态

源仓根目录没有 `LICENSE`、`NOTICE` 或 `COPYING` 文件，也没有发现授予本包再分发权的许可文本。源仓 `docs/references.md` 说明历史参考项目仅用于研究、未复制其源码；该说明不能替代本项目代码许可，也不覆盖素材权利。

用户已授权本地迁移。Hub 包中记录该上游归属，并保留源工作树当前维护的代码与文档；用户正在联系上游维护者确认许可。本文件不推定开源许可，也不构成权利转让。在得到明确许可前，不得对外发布或再分发本包。

2026-10-26 的源码导入排除了私有阿舟图像、生成素材和本地机器验收产物。同日的本地交接将构建所需私有输入放在 Hub 包内被 Git 忽略的 `assets/private/`；它们仍不属于跟踪源码或公开分发内容。参见 [迁移清单](MIGRATION-INVENTORY.md)和 [本地交接记录](../../evidence/optional-integrations-local-handoff-2026-10-26.md)。
