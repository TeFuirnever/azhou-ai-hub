# arch-doc benchmark

行为基准：验证「脚手架 → 收尾门」闭环在真实模板上可用。

## case-01-scaffold

自动 runner（在仓库根执行）：

```bash
python3 benchmarks/arch-doc/run_case.py [--receipt <path.json>]
```

`run_case.py` 逐项断言下列期望，输出逐项 PASS/FAIL 与 JSON 收据（schema / status / skill-tree digest / artifact digest），退出码 0 全过、1 有失败：

1. `new_doc.py` 脚手架退出码 0；产物含文档控制行 `文档 ID：\`ARCH-2026-099\``（及版本 / 状态 / 日期）。
2. `verify_doc.py` 退出码 0（空图配平、零断链、无未入账图注、空白合规）。
3. 模板内的 3 处 `design-doc.md` 选择器链接被改写为纯文本标注（产物 `grep -c "design-doc.md#"` 为 3，但无 Markdown 断链）。
4. 模板本体哈希不变（`references/templates/PROVENANCE.md` 表仍一致）。

当前状态：自动断言 runner 已交付并实跑通过，收据见 `evidence/arch-doc-benchmark-receipt-2026-09-04.json`（2026-09-04）。接入 `scripts/verify.py` 公开 gate 待排期（sibling-gap GAP#4 的剩余半步）；在接入之前，公开 gate 的 benchmark 完整性主张仍为三套（repo-pedant / super-caveman / excalidraw）。
