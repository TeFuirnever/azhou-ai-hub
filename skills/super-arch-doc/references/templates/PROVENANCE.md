# 模板 Provenance（只读锁）

模板为**只读**：生成文档时按剖面选用，一个字节都不改；需要调整时先回来源仓库更新原版，再同步副本并更新本文件的 SHA-256。

有意分歧注记（2026-11-18）：对 [design-doc.md](design-doc.md)（ADR 行改为指向 [adr-template.md](../adr-template.md)）与 [feature-detailed-design.md](feature-detailed-design.md)（术语表行改为生成时附加件机制）做了两处本地准确性修正，来源仓（MatrixContextController，非公开可达）未回源。未来从来源仓同步原版时，须先保留或重放这两行修正，再重算并更新本表摘要，否则同步会静默回退修正。

来源：MatrixContextController `docs/templates/`（2026-09，模板版本随 ARCH-2026-001 v0.17 流水线验证）。许可证：随来源仓库整体许可（同 owner 内部引用）；对外分发前先核对来源仓库 LICENSE。

| 模板 | 用途 | SHA-256 |
|---|---|---|
| [software-implementation-architecture.md](software-implementation-architecture.md) | 软件实现架构说明书（ARCH）剖面 | `d2351055543c444c4a3ec874460c584228419dc1b363624771709611941ca52d` |
| [design-doc.md](design-doc.md) | 设计文档通用剖面 | `29d3d36482ce0914dde426869566d30751032c4fe668417c1b7c48bcaa89e774` |
| [feature-detailed-design.md](feature-detailed-design.md) | 功能详细设计（DETAIL）剖面 | `2e94ff773d492aab7494b5f3cca6f75a08d333e8fc8738e2e8d5cfa66d5c33a1` |
| [prd.md](prd.md) | 产品需求文档（PRD）剖面 | `a2ceb916621d130559634dda2c266ddfd817fb2f761970a2d510eed9998db617` |
| [industry-best-practice-baseline.md](industry-best-practice-baseline.md) | 业界基线引用（RFC 2119 / 42010 等） | `1606c765747e8b3a5ff008d0d14b1a9b45f16c744dc3a6d91c6cd60160b9ca63` |

校验命令（在 skill 目录执行）：

```bash
shasum -a 256 references/templates/*.md
```

无 `shasum` 的平台（如 Windows）用标准库等价命令，输出同为 `哈希 文件名`：

```bash
python -c "import sys,hashlib; [print(hashlib.sha256(open(p,'rb').read()).hexdigest(), p) for p in sys.argv[1:]]" references/templates/*.md
```

哈希与本表不一致 = 模板被改动，先恢复再使用。

## 同步流程（来源模板演进时）

1. 在来源仓库更新模板原版，记录变更点。
2. 重拷副本到本目录，重算 `shasum -a 256`，更新上表哈希。
3. 跑 `<skill-dir>/scripts/verify_doc.py`（对既有产出文档回归一次），并在来源仓库与本仓库各留一条变更记录。
