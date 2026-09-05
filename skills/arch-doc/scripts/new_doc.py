#!/usr/bin/env python3
"""new_doc.py — Arch Doc 模板脚手架（标准库，无第三方依赖）。

从 references/templates/ 的只读模板实例化一份新文档：不改模板本身，
只在副本上盖文档控制信息（标题 / ID / 版本 / 状态 / 日期）。

用法:
    python3 new_doc.py <profile> <doc-id> "<标题>" --out <路径.md> [--status Draft]

  <profile>  software-implementation-architecture | feature-detailed-design | prd | design-doc
  <doc-id>   形如 ARCH-2026-002 / DETAIL-2026-014 / PRD-2026-002
  --status   默认 Draft

行为:
  1. 复制模板到 --out（模板本体不动，PROVENANCE 哈希不受影响）。
  2. 标题占位 `<产品或系统名称>` / `<主题>` 替换为给定标题。
  3. 在首个一级标题后插入文档控制行：ID / 版本 0.1 / 状态 / 日期。
退出码: 0 成功；1 参数或文件错误。
"""
import argparse
import datetime
import shutil
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "references" / "templates"
PROFILES = ("software-implementation-architecture", "design-doc",
            "feature-detailed-design", "prd")


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a new document from a read-only template")
    ap.add_argument("profile", choices=PROFILES)
    ap.add_argument("doc_id", help="形如 ARCH-2026-002")
    ap.add_argument("title")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--status", default="Draft")
    args = ap.parse_args()

    src = TEMPLATES / f"{args.profile}.md"
    if not src.is_file():
        print(f"FAIL template not found: {src}")
        return 1
    if args.out.exists():
        print(f"FAIL output already exists (never overwrite): {args.out}")
        return 1

    text = src.read_text(encoding="utf-8")
    for placeholder in ("<产品或系统名称>", "<主题>", "<产品需求主题>"):
        text = text.replace(placeholder, args.title)
    # 模板内的选择器链接只在 skill 包内可达；实例化副本改为纯文本标注，
    # 否则产物在任何输出路径都会带断链（含锚点链接一并处理）。
    import re
    text = re.sub(r"\[([^\]]+)\]\(design-doc\.md(#[^)]*)?\)",
                  r"\1（arch-doc skill 内 design-doc.md\2）", text)
    control = (f"> 文档 ID：`{args.doc_id}` · 版本：`0.1` · 状态：`{args.status}`"
               f" · 日期：`{datetime.date.today().isoformat()}`\n\n")
    lines = text.split("\n")
    h1 = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), None)
    if h1 is None:
        lines = [control] + lines
    else:
        lines.insert(h1 + 1, "\n" + control.rstrip("\n"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"scaffolded: {args.out} (profile={args.profile}, id={args.doc_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
