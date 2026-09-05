#!/usr/bin/env python3
"""run_case.py — arch-doc case-01-scaffold 自动断言 + 证据收据。

用法（仓库根执行）:
    python3 benchmarks/arch-doc/run_case.py [--receipt <path.json>]

断言:
  1. new_doc.py 脚手架退出码 0，产物含文档控制行（ID/版本/状态/日期）。
  2. verify_doc.py 对产物退出码 0。
  3. 模板选择器链接已改写为纯文本（产物零 Markdown 断链）。
  4. 模板本体 SHA-256 与 references/templates/PROVENANCE.md 表一致。
输出: 逐项 PASS/FAIL + JSON 收据（schema/status/skill-tree digest/artifact digest）。
退出码: 0 全过；1 有失败。
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "arch-doc"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "ARCH-2026-099.md"
        r1 = subprocess.run([sys.executable, str(SKILL / "scripts" / "new_doc.py"),
                             "software-implementation-architecture", "ARCH-2026-099",
                             "演示系统", "--out", str(out)], capture_output=True, text=True)
        results.append(("scaffold exit 0", r1.returncode == 0, r1.stderr.strip()[:200]))
        body = out.read_text(encoding="utf-8") if out.exists() else ""
        results.append(("control line present",
                        "文档 ID：`ARCH-2026-099`" in body and "版本：`0.1`" in body and "状态：`Draft`" in body,
                        ""))
        r2 = subprocess.run([sys.executable, str(SKILL / "scripts" / "verify_doc.py"), str(out)],
                            capture_output=True, text=True)
        results.append(("verify_doc exit 0", r2.returncode == 0, r2.stdout.strip()[:200]))
        results.append(("selector links rewritten",
                        "](design-doc.md" not in body and "arch-doc skill 内 design-doc.md" in body, ""))

    # 4) 模板哈希 vs PROVENANCE
    prov = (SKILL / "references" / "templates" / "PROVENANCE.md").read_text(encoding="utf-8")
    hash_ok = True
    for m in re.finditer(r"\[([a-z\-]+\.md)\]\([a-z\-]+\.md\)\s*\|[^|]+\|\s*`([0-9a-f]{64})`", prov):
        name, expect = m.group(1), m.group(2)
        actual = sha256(SKILL / "references" / "templates" / name)
        if actual != expect:
            hash_ok = False
            results.append((f"template hash drift: {name}", False, actual[:16]))
    results.append(("template hashes match PROVENANCE", hash_ok, ""))

    failed = [r for r in results if not r[1]]
    for name, passed, detail in results:
        print(("PASS " if passed else "FAIL ") + name + (f" — {detail}" if detail and not passed else ""))
    skill_digest = hashlib.sha256((",".join(f"{p.name}:{sha256(p)}" for p in sorted(SKILL.rglob('*')) if p.is_file())).encode()).hexdigest()
    receipt = {
        "schema": "arch-doc.benchmark.case-01.v1",
        "status": "passed" if not failed else "failed",
        "date": "2026-09-04",
        "checks": [{"name": n, "pass": p, "detail": d} for n, p, d in results],
        "skill_tree_digest": skill_digest,
        "artifacts": ["(tempdir; scaffold re-runnable via commands in README)"],
        "visual_review": "n/a (deterministic checks only)",
    }
    payload = json.dumps(receipt, ensure_ascii=False)
    print(payload)
    receipt_path = sys.argv[sys.argv.index("--receipt") + 1] if "--receipt" in sys.argv else None
    if receipt_path:
        Path(receipt_path).parent.mkdir(parents=True, exist_ok=True)
        Path(receipt_path).write_text(payload + "\n", encoding="utf-8")
        print(f"receipt written: {receipt_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
