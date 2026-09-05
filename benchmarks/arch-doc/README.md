# arch-doc benchmark

行为基准：验证「脚手架 → 收尾门」闭环在真实模板上可用。

## case-01-scaffold

命令（在仓库根执行）：

```bash
python3 skills/arch-doc/scripts/new_doc.py software-implementation-architecture \
  ARCH-2026-099 "演示系统" --out /tmp/bench_arch_demo.md
python3 skills/arch-doc/scripts/verify_doc.py /tmp/bench_arch_demo.md
```

期望：

1. `new_doc.py` 退出码 0；产物含文档控制行 `文档 ID：\`ARCH-2026-099\``。
2. `verify_doc.py` 退出码 0（空图配平、零断链、无未入账图注、空白合规）。
3. 模板内的 3 处 `design-doc.md` 选择器链接被改写为纯文本标注（产物 `grep -c "design-doc.md#"` 为 3，但无 Markdown 断链）。
4. 模板本体哈希不变（`references/templates/PROVENANCE.md` 表仍一致）。

当前状态：已人工执行，期望 1–4 全部满足（2026-09-04）。升级为自动断言的 runner 待排期。
