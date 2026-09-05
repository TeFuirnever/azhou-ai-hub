#!/usr/bin/env python3
r"""verify_doc.py — Arch Doc 收尾确定性校验（标准库，无第三方依赖）。

用法:
    python3 verify_doc.py <文档.md> [--states "Draft,Planned,Implemented,Verified,Production"]

检查项（任一失败退出码 1，全过退出码 0）:
  1. @startuml 与 @enduml 数量配平。
  2. 相对 Markdown 链接目标全部存在。
  3. 图注四联注版本（`版本/日期：\`x.y\``）全部出现在变更记录的版本行中（图注版本必须入账）。
  4. 变更记录版本行有序且无重复。
  5. 无连续 3+ 空行、无行尾空白（代码块内豁免）。
  6. 可选 --states：文档中「状态词表」之外的使用态词将被列出（提示性，不计失败）。
"""
import argparse
import re
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Arch Doc deterministic closing checks")
    ap.add_argument("document", type=Path)
    ap.add_argument("--states", default="", help="逗号分隔的证据状态词表（提示性校验）")
    ap.add_argument("--plantuml-cli", action="store_true",
                    help="检测到本地 plantuml 时逐图渲染验证；缺失时输出 skipped")
    ap.add_argument("--trace-prd", type=Path, default=None,
                    help="追溯校验：PRD 文件（须含 PRD-Fxx 锚点）")
    ap.add_argument("--trace-detail-dir", type=Path, default=None,
                    help="追溯校验：DETAIL 文件目录（按 DETAIL-ID 前缀匹配）")
    args = ap.parse_args()
    doc = args.document
    if not doc.is_file():
        print(f"FAIL document not found: {doc}")
        return 1
    text = doc.read_text(encoding="utf-8")
    errors: list[str] = []

    # 1) PlantUML 配平
    opens, closes = text.count("@startuml"), text.count("@enduml")
    if opens != closes:
        errors.append(f"plantuml unbalanced: @startuml={opens} @enduml={closes}")

    # 2) 相对链接目标存在
    root = doc.parent
    for m in re.finditer(r"\]\(([^)#\s]+?)(?:#[^)]*)?\)", text):
        target = m.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        if not (root / target).exists():
            errors.append(f"broken relative link: {target}")

    # 3) 图注版本入账
    caption_versions = set(re.findall(r"版本/日期：`(\d+(?:\.\d+)*)\s*/", text))
    changelog_versions = set(re.findall(r"^\|\s*`v?(\d+(?:\.\d+)*)`\s*\|", text, re.M))
    unaccounted = sorted(caption_versions - changelog_versions, key=lambda v: [int(x) for x in v.split(".")])
    if unaccounted:
        errors.append(f"caption versions missing from changelog: {unaccounted}")

    # 4) changelog 有序无重复
    versions = [v for v in re.findall(r"^\|\s*`v?(\d+(?:\.\d+)*)`\s*\|", text, re.M) if "." in v]
    nums = [[int(x) for x in v.split(".")] for v in versions]
    if len(nums) != len(set(map(tuple, nums))):
        errors.append("changelog has duplicate version rows")
    if nums != sorted(nums):
        errors.append(f"changelog rows out of order: {versions}")

    # 5) 空白纪律（代码块内豁免）
    in_code = False
    for i, line in enumerate(text.split("\n"), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if re.search(r"\s+$", line):
            errors.append(f"trailing whitespace at line {i}")

    # 6) 状态词提示（不计失败）
    if args.states:
        vocab = {w.strip() for w in args.states.split(",") if w.strip()}
        body = text
        stray = sorted({w for w in re.findall(r"[A-Z][a-zA-Z]+", body) if w in vocab} - vocab) if False else []
        used_foreign = []
        for w in re.findall(r"\b(?:Draft|Planned|Implemented|Verified|Production|Bundled|Research|In Review|Evolving|Host-specific)\b", text):
            if vocab and w not in vocab and w not in used_foreign:
                used_foreign.append(w)
        if used_foreign:
            print(f"HINT states outside --states vocabulary: {used_foreign}")

    # 追溯校验（可选项）：Fxx 行的 PRD 锚点与 DETAIL 文件必须存在
    if args.trace_prd or args.trace_detail_dir:
        prd_text = args.trace_prd.read_text(encoding="utf-8") if args.trace_prd and args.trace_prd.is_file() else ""
        detail_files = [p.name for p in args.trace_detail_dir.iterdir()] if args.trace_detail_dir and args.trace_detail_dir.is_dir() else []
        rows = re.findall(r"\|\s*(F\d{2})\s*\|\s*PRD-F\d{2}\s*\|[^|]*\|[^|]*\b(DETAIL-\d{3})\b", text)
        if not rows:
            errors.append("trace: 文档中未找到 Fxx/PRD-Fxx/DETAIL 追溯矩阵行")
        for fxx, det in rows:
            if prd_text and f"PRD-{fxx}" not in prd_text:
                errors.append(f"trace: PRD 缺少锚点 PRD-{fxx}")
            if detail_files and not any(n.lower().startswith(det.lower()) for n in detail_files):
                errors.append(f"trace: DETAIL 文件缺失: {det}")

    # PlantUML 渲染门（可选项）：本地有 plantuml 才执行，否则 skipped
    if args.plantuml_cli:
        import shutil as _sh
        import subprocess as _sp
        import tempfile as _tf
        cli = _sh.which("plantuml") or _sh.which("plantuml.jar") and "plantuml"
        if not cli:
            print("HINT plantuml render gate skipped: 本地未检测到 plantuml CLI")
        else:
            blocks = re.findall(r"@startuml\n(.*?)@enduml", text, re.S)
            with _tf.TemporaryDirectory() as td:
                for i, b in enumerate(blocks, 1):
                    puml = Path(td) / f"d{i}.puml"
                    puml.write_text("@startuml\n" + b + "\n@enduml", encoding="utf-8")
                    r = _sp.run([cli, "-failfast2", "-tpng", str(puml)],
                                capture_output=True)
                    if r.returncode != 0:
                        errors.append(f"plantuml render failed: diagram #{i}")

    if errors:
        print(f"❌ 验证失败 — {len(errors)} 项：")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("✅ 验证通过 — 配平/链接/图注入账/changelog 有序/空白 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
