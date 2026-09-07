# Provenance hashlib 等价命令对照记录

> 日期：2026-09-07（Asia/Shanghai）· 工单：win-06-provenance-hashlib · 环境：macOS（维护者检出），shasum 2.0.0-vs 标准库 hashlib

验收标准：新增标准库等价命令与既有 `shasum` 命令在 macOS 上输出（摘要部分）逐字节一致；四包锁定摘要不变。

## 1. excalidraw bundle（单文件）

```
$ shasum -a 256 skills/excalidraw-diagram/references/vendor/excalidraw-all.esm.js
f0a616466292610789f05a2da3f529b44d57cb1a44b3ca91081bb8d074fc542c  skills/excalidraw-diagram/references/vendor/excalidraw-all.esm.js
$ python -c "import hashlib; print(hashlib.sha256(open(...).read()).hexdigest())"
f0a616466292610789f05a2da3f529b44d57cb1a44b3ca91081bb8d074fc542c
```

## 2. excalidraw libraries manifest（管线）

```
$ find ... -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256
bb265f168a10338f095143d7d56387e9fc44d3d4ad994521b1be989a87ab124a  -
$ python - <<PY（provenance.md 内联脚本）
bb265f168a10338f095143d7d56387e9fc44d3d4ad994521b1be989a87ab124a
```

## 3. arch-doc 模板表（glob 批量）

```
$ shasum -a 256 references/templates/*.md（在 skills/arch-doc 下）
02c67ea41740a67b916a212d5559c47902419344f98685391dbd73d352f98798  references/templates/PROVENANCE.md
bb03fb8648b5d4faca82efd802d853fe61e26053879faf3ff712e5c1cd0cb73c  references/templates/design-doc.md
09a7c19d61619c686d561cfe5456c324ab566ab3a9f9be7bb02c5426f9bce862  references/templates/feature-detailed-design.md
1606c765747e8b3a5ff008d0d14b1a9b45f16c744dc3a6d91c6cd60160b9ca63  references/templates/industry-best-practice-baseline.md
a2ceb916621d130559634dda2c266ddfd817fb2f761970a2d510eed9998db617  references/templates/prd.md
d2351055543c444c4a3ec874460c584228419dc1b363624771709611941ca52d  references/templates/software-implementation-architecture.md
$ python -c 列表推导等价（在 skills/arch-doc 下）
02c67ea41740a67b916a212d5559c47902419344f98685391dbd73d352f98798 references/templates/PROVENANCE.md
bb03fb8648b5d4faca82efd802d853fe61e26053879faf3ff712e5c1cd0cb73c references/templates/design-doc.md
09a7c19d61619c686d561cfe5456c324ab566ab3a9f9be7bb02c5426f9bce862 references/templates/feature-detailed-design.md
1606c765747e8b3a5ff008d0d14b1a9b45f16c744dc3a6d91c6cd60160b9ca63 references/templates/industry-best-practice-baseline.md
a2ceb916621d130559634dda2c266ddfd817fb2f761970a2d510eed9998db617 references/templates/prd.md
d2351055543c444c4a3ec874460c584228419dc1b363624771709611941ca52d references/templates/software-implementation-architecture.md
```

## 结论

- 1/2/3 三组：摘要逐字节一致；arch-doc 表中 5 个锁定模板摘要未变（PROVENANCE.md 自身不在锁定表内）。
- eli5 / lavish 的 curl 管线等价命令属同型单文件摘要，未重复演练（远端内容锁定，本地无从对比时以 bundle 组为准）。
