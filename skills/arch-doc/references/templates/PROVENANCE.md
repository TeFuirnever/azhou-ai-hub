# 模板 Provenance（只读锁）

模板为**只读**：生成文档时按剖面选用，一个字节都不改；需要调整时先回来源仓库更新原版，再同步副本并更新本文件的 SHA-256。

来源：MatrixContextController `docs/templates/`（2026-09，模板版本随 ARCH-2026-001 v0.17 流水线验证）。许可证：随来源仓库整体许可（同 owner 内部引用）；对外分发前先核对来源仓库 LICENSE。

| 模板 | 用途 | SHA-256 |
|---|---|---|
| [software-implementation-architecture.md](software-implementation-architecture.md) | 软件实现架构说明书（ARCH）剖面 | `d2351055543c444c4a3ec874460c584228419dc1b363624771709611941ca52d` |
| [design-doc.md](design-doc.md) | 设计文档通用剖面 | `bb03fb8648b5d4faca82efd802d853fe61e26053879faf3ff712e5c1cd0cb73c` |
| [feature-detailed-design.md](feature-detailed-design.md) | 功能详细设计（DETAIL）剖面 | `09a7c19d61619c686d561cfe5456c324ab566ab3a9f9be7bb02c5426f9bce862` |
| [prd.md](prd.md) | 产品需求文档（PRD）剖面 | `a2ceb916621d130559634dda2c266ddfd817fb2f761970a2d510eed9998db617` |
| [industry-best-practice-baseline.md](industry-best-practice-baseline.md) | 业界基线引用（RFC 2119 / 42010 等） | `1606c765747e8b3a5ff008d0d14b1a9b45f16c744dc3a6d91c6cd60160b9ca63` |

校验命令（在 skill 目录执行）：

```bash
shasum -a 256 references/templates/*.md
```

哈希与本表不一致 = 模板被改动，先恢复再使用。

## 同步流程（来源模板演进时）

1. 在来源仓库更新模板原版，记录变更点。
2. 重拷副本到本目录，重算 `shasum -a 256`，更新上表哈希。
3. 跑 `scripts/verify_doc.py`（对既有产出文档回归一次），并在来源仓库与本仓库各留一条变更记录。
