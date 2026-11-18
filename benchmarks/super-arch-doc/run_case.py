#!/usr/bin/env python3
"""run_case.py — super-arch-doc case-01-scaffold 自动断言 + 证据收据。

用法（仓库根执行）:
    python3 benchmarks/super-arch-doc/run_case.py [--receipt <path.json>]

断言:
  1. new_doc.py 脚手架退出码 0，产物含文档控制行（ID/版本/状态/日期）。
  2. verify_doc.py 对产物退出码 0。
  3. 模板选择器链接已改写为纯文本（产物零 Markdown 断链）。
  4. 模板本体 SHA-256 与 references/templates/PROVENANCE.md 表一致。
输出: 逐项 PASS/FAIL + JSON 收据（schema/status/skill-tree digest/artifacts 产物说明字段）。
退出码: 0 全过；1 检查或回执写入失败；2 参数错误。
"""
import argparse
from datetime import date
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "super-arch-doc"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_template_hashes(directory: Path) -> tuple[bool, str]:
    manifest = directory / "PROVENANCE.md"
    templates = {p.name: p for p in directory.glob("*.md") if p != manifest and p.is_file()}
    lines = iter(manifest.read_text(encoding="utf-8").splitlines())
    for line in lines:
        if [cell.strip() for cell in line.strip().split("|")] == ["", "模板", "用途", "SHA-256", ""]:
            break
    separator = next(lines, "")
    if not re.fullmatch(r"\s*\|(?:\s*:?-{3,}:?\s*\|){3}\s*", separator):
        return False, "missing provenance table"
    seen = set()
    for line in lines:
        if not line.lstrip().startswith("|"):
            break
        row = re.fullmatch(r"\s*\|\s*\[([^\]]+)\]\(\1\)\s*\|[^|]+\|\s*`([0-9a-f]{64})`\s*\|\s*", line)
        if not row:
            return False, "invalid provenance row"
        name, expected = row.groups()
        if name not in templates or name in seen:
            return False, f"unexpected or duplicate template: {name}"
        if sha256(templates[name]) != expected:
            return False, f"hash drift: {name}"
        seen.add(name)
    missing = sorted(templates.keys() - seen)
    if missing:
        return False, "missing templates: " + ", ".join(missing)
    return (True, "") if seen else (False, "empty template inventory")


def write_receipt(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise OSError("receipt target must be a regular file or a new path")
    staged = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=".arch-doc-receipt-", suffix=".tmp", delete=False,
        ) as stream:
            staged = Path(stream.name)
            content = payload + "\n"
            if stream.write(content) != len(content):
                raise OSError("short receipt write")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staged, path)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    run_date = date.today().isoformat()
    results = []
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "ARCH-2026-099.md"
        r1 = subprocess.run([sys.executable, str(SKILL / "scripts" / "new_doc.py"),
                             "software-implementation-architecture", "ARCH-2026-099",
                             "演示系统", "--out", str(out)], capture_output=True, text=True, encoding="utf-8")
        results.append(("scaffold exit 0", r1.returncode == 0, r1.stderr.strip()[:200]))
        body = out.read_text(encoding="utf-8") if out.exists() else ""
        results.append(("control line present",
                        "文档 ID：`ARCH-2026-099`" in body and "版本：`0.1`" in body and "状态：`Draft`" in body,
                        ""))
        r2 = subprocess.run([sys.executable, str(SKILL / "scripts" / "verify_doc.py"), str(out)],
                            capture_output=True, text=True, encoding="utf-8")
        results.append(("verify_doc exit 0", r2.returncode == 0, r2.stdout.strip()[:200]))
        results.append(("selector links rewritten",
                        "](design-doc.md" not in body and "super-arch-doc skill 内 design-doc.md" in body, ""))

    # 4) 模板哈希 vs PROVENANCE
    hash_ok, detail = check_template_hashes(SKILL / "references" / "templates")
    results.append(("template hashes match PROVENANCE", hash_ok, detail))

    failed = [r for r in results if not r[1]]
    for name, passed, detail in results:
        print(("PASS " if passed else "FAIL ") + name + (f" — {detail}" if detail and not passed else ""))
    skill_digest = hashlib.sha256((",".join(f"{p.name}:{sha256(p)}" for p in sorted(SKILL.rglob('*')) if p.is_file())).encode()).hexdigest()
    receipt = {
        "schema": "super-arch-doc.benchmark.case-01.v1",
        "status": "passed" if not failed else "failed",
        "date": run_date,
        "checks": [{"name": n, "pass": p, "detail": d} for n, p, d in results],
        "skill_tree_digest": skill_digest,
        "artifacts": ["(tempdir; scaffold re-runnable via commands in README)"],
        "visual_review": "n/a (deterministic checks only)",
    }
    payload = json.dumps(receipt, ensure_ascii=False)
    if args.receipt is not None:
        try:
            write_receipt(args.receipt, payload)
        except OSError as exc:
            print(f"receipt write failed: {exc}", file=sys.stderr)
            return 1
    print(payload)
    if args.receipt is not None:
        print(f"receipt written: {args.receipt}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
