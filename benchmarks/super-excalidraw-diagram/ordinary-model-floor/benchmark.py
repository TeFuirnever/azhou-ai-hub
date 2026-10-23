#!/usr/bin/env python3
"""Ordinary-Model Floor v1 — does an ordinary agent produce a USABLE diagram on attempt 1?

A delivery gate for the super-excalidraw-diagram skill, not a model leaderboard.
A run is firstPassUsable only when all three gates pass:

  1. Semantic   — every required text exists; every required flow is drawn as an
                  arrow whose endpoints sit on the labeled boxes.
  2. Deterministic — style gate (hand-drawn preset), scene hygiene, and the
                  geometric overlap audit all pass.
  3. Visual review — an identified reviewer inspected the rendered artifact and
                  reported `passed` with no defects. `skipped` can NEVER produce
                  firstPassUsable; failures are reported truthfully, never upgraded.
                  A skipped review must be explicit: run.json may carry
                  visual_review.holds (for example ["sandbox blocked preview"],
                  copied from the visual-check.py schema-2 receipt); verify
                  surfaces the holds verbatim, and a skipped review without any
                  holds gets the explicit "visual review not recorded" hold —
                  a silent skip cannot pass through unnoticed.

Commands:
  benchmark.py check [--manifest manifest.json]
      Validate suite integrity: manifest shape, the reference fixture verifies,
      and the sandbox-blocked fixture holds explicitly with firstPassUsable
      false.
  benchmark.py verify --case <case.json> --candidate <scene.excalidraw> --run <run.json>
      One machine-readable receipt to stdout. Exit 0 = first-pass usable,
      1 = a gate failed, 2 = invalid invocation/inputs.
  benchmark.py record-failure --case <case.json> --run <run.json> --failure timeout|no_candidate|provider_error
      Truthful operational-failure receipt; quality gates stay not_run.
  benchmark.py report --results <results.jsonl> --manifest manifest.json
      Aggregate a complete matrix; separates operational / semantic /
      deterministic / visual-review failure clusters and lists the distinct
      visual-review holds. evidenceEligible is true only when every case has
      exactly one attempt-1 receipt.

Fair-run protocol lives in README.md — same prompt, same skill tree, same time
limit, frozen attempt-1, no post-hoc edits (including human ones).
"""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL = REPO_ROOT / "skills" / "super-excalidraw-diagram"
SCRIPTS = SKILL / "scripts"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load("handdrawn_gate", "check-handdrawn-style.py")
hygiene = _load("scene_hygiene", "check-scene-hygiene.py")


def _box_texts(data: dict):
    """Map element-id -> concatenated bound text for labeled container shapes."""
    texts = {e["id"]: e.get("text", "") for e in data["elements"] if e["type"] == "text"}
    out = {}
    for e in data["elements"]:
        if e["type"] in ("rectangle", "ellipse", "diamond"):
            label = " ".join(
                texts[b["id"]] for b in (e.get("boundElements") or [])
                if isinstance(b, dict) and b.get("id") in texts
            )
            out[e["id"]] = label
    return out


def _pt_in(px, py, e, m=1.0):
    return e["x"] - m <= px <= e["x"] + e.get("width", 0) + m and e["y"] - m <= py <= e["y"] + e.get("height", 0) + m


def check_semantic(data: dict, case: dict) -> list[dict]:
    diags = []
    all_text = "\n".join(e.get("text", "") for e in data["elements"] if e["type"] == "text")
    for needle in case["semantic"].get("required_texts", []):
        if needle not in all_text:
            diags.append({"code": "SEM-TEXT", "subject": needle, "evidence": "not found in any text element",
                          "fixes": ["add a labeled node carrying the exact term"]})
    boxes = {eid: e for eid, e in ((e["id"], e) for e in data["elements"]
                                   if e["type"] in ("rectangle", "ellipse", "diamond"))}
    labels = _box_texts(data)
    arrows = [e for e in data["elements"] if e["type"] == "arrow"]
    for flow in case["semantic"].get("required_flows", []):
        f, t = flow["from"], flow["to"]
        hit = False
        for a in arrows:
            pts = a.get("points") or []
            if len(pts) < 2:
                continue
            sx, sy = a["x"] + pts[0][0], a["y"] + pts[0][1]
            ex, ey = a["x"] + pts[-1][0], a["y"] + pts[-1][1]
            for bid, lab in labels.items():
                if f not in lab or not _pt_in(sx, sy, boxes[bid]):
                    continue
                for tid, tlab in labels.items():
                    if t in tlab and _pt_in(ex, ey, boxes[tid]):
                        hit = True
                        break
                if hit:
                    break
            if hit:
                break
        if not hit:
            diags.append({"code": "SEM-FLOW", "subject": f"{f} -> {t}",
                          "evidence": "no arrow starts on a box labeled with the from-term and ends on a to-term box",
                          "fixes": ["draw the arrow edge-to-edge between the labeled boxes"]})
    return diags


def visual_review_ok(vr: dict) -> bool:
    """The one first-pass visual-review criterion, shared by verify and report.

    A named reviewer reported `passed` with no defects and no holds; anything
    else — including a missing reviewer, recorded defects, or unresolved
    holds — never counts as first-pass usable."""
    if not isinstance(vr, dict):
        return False
    reviewer = vr.get("reviewer")
    # The reviewer must be a real non-empty string: JSON null/false/0/[] all
    # stringify to non-empty words and must not pass as an identified person.
    if (
        vr.get("status") != "passed"
        or not isinstance(reviewer, str)
        or not reviewer.strip()
    ):
        return False
    if vr.get("defects") or vr.get("holds"):
        return False
    return True


def cmd_verify(args) -> int:
    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    cand = Path(args.candidate)
    run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    if not cand.exists():
        print(json.dumps({"schema": 1, "case_id": case["id"], "status": "invalid", "reason": "candidate missing"}))
        return 2
    if run.get("attempt") != 1:
        print(json.dumps({"schema": 1, "case_id": case["id"], "status": "invalid", "reason": "only attempt 1 is evidence-eligible"}))
        return 2

    data = json.loads(cand.read_text(encoding="utf-8"))
    sem = check_semantic(data, case)
    style, _cjk, _txt = gate.check_scene(cand)
    hyg = hygiene.check_scene(data)
    geo = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit-overlaps.py"), str(cand)],
        capture_output=True, text=True)

    vr = run.get("visual_review", {})
    vr_status = vr.get("status", "skipped")
    # Holds are preserved verbatim (str-form): a blank or malformed entry is
    # kept, so verify and report judge the same data and malformed input can
    # never be filtered into a pass.
    holds = [str(h) for h in (vr.get("holds") or [])]
    if not holds and vr_status == "skipped":
        holds = ["visual review not recorded"]
    vr_ok = visual_review_ok(vr)

    receipt = {
        "schema": 1, "case_id": case["id"],
        "agent": run.get("agent"), "model": run.get("model"), "attempt": 1,
        "gates": {
            "semantic": {"pass": not sem, "diagnostics": sem},
            "deterministic": {
                "pass": not style and not hyg and geo.returncode == 0,
                "style_gate": style[:5], "hygiene": hyg[:5],
                "overlap_exit": geo.returncode,
            },
            "visual_review": {"status": vr_status, "reviewer": vr.get("reviewer"),
                              "defects": vr.get("defects", []), "holds": holds},
        },
    }
    receipt["firstPassUsable"] = (
        receipt["gates"]["semantic"]["pass"]
        and receipt["gates"]["deterministic"]["pass"]
        and vr_ok)
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["firstPassUsable"] else 1


def cmd_record_failure(args) -> int:
    if args.failure not in ("timeout", "no_candidate", "provider_error"):
        return 2
    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    print(json.dumps({
        "schema": 1, "case_id": case["id"], "attempt": 1,
        "agent": run.get("agent"), "model": run.get("model"),
        "status": "operational-failure", "failure": args.failure,
        "gates": {"semantic": "not_run", "deterministic": "not_run", "visual_review": "not_run"},
        "firstPassUsable": False,
    }))
    return 0


def cmd_check(args) -> int:
    man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    base = Path(args.manifest).parent
    ids = [c["id"] for c in man["cases"]]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    for c in man["cases"]:
        path = Path(c["case_file"])
        if not path.is_absolute():
            path = base / path
        assert path.exists(), f"missing case file {c['case_file']}"
        case = json.loads(path.read_text(encoding="utf-8"))
        assert case["id"] == c["id"], f"{c['id']}: manifest/case id mismatch"
        assert case["semantic"].get("required_texts"), f"{c['id']}: no required_texts"
        assert case["semantic"].get("required_flows"), f"{c['id']}: no required_flows"
    # reference fixture must verify green — proves the verifier is wired
    ref = Path(__file__).parent / "fixtures" / "reference"
    rc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()),
         "verify",
         "--case", str(Path(__file__).parent / "cases" / "layered-architecture.case.json"),
         "--candidate", str(ref / "reference.architecture.excalidraw"),
         "--run", str(ref / "reference.run.json")],
        capture_output=True, text=True)
    assert rc.returncode == 0, f"reference fixture failed verify:\n{rc.stdout}\n{rc.stderr}"

    # sandbox-blocked fixture must hold explicitly — a silent skip cannot wire
    rc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()),
         "verify",
         "--case", str(Path(__file__).parent / "cases" / "layered-architecture.case.json"),
         "--candidate", str(ref / "reference.architecture.excalidraw"),
         "--run", str(ref / "reference.sandbox-blocked.run.json")],
        capture_output=True, text=True)
    assert rc.returncode == 1, (
        f"sandbox-blocked fixture must not verify usable:\n{rc.stdout}\n{rc.stderr}")
    receipt = json.loads(rc.stdout)
    holds = receipt["gates"]["visual_review"]["holds"]
    assert holds == ["sandbox blocked preview"], f"holds drift: {holds}"
    assert receipt["firstPassUsable"] is False

    # the sandbox-friendly visual-check fallback receipt must bind the exact
    # fixture bytes and a clean geometry audit
    fallback_svg = ref / "reference.architecture.svg"
    fallback_receipt_path = ref / "reference.architecture.svg.visual-check.json"
    assert fallback_svg.exists(), "missing sandbox fallback fixture SVG"
    fallback = json.loads(fallback_receipt_path.read_text(encoding="utf-8"))
    assert fallback["schema"] == 2, f"fallback receipt schema drift: {fallback.get('schema')}"
    assert fallback["status"] == "skipped", f"fallback receipt status drift: {fallback.get('status')}"
    assert fallback["holds"] == ["sandbox blocked preview"], f"fallback holds drift: {fallback.get('holds')}"
    assert fallback["visual_review"] == "pending"
    assert fallback["artifact"]["sha256"] == hashlib.sha256(fallback_svg.read_bytes()).hexdigest(), \
        "fallback receipt artifact digest does not bind the fixture SVG"
    assert fallback["fallback"]["scene"]["sha256"] == \
        hashlib.sha256((ref / "reference.architecture.excalidraw").read_bytes()).hexdigest(), \
        "fallback receipt scene digest does not bind the fixture scene"
    assert fallback["fallback"]["geometry_audit"] == {"exit": 0, "issues": 0}, \
        f"fallback geometry audit drift: {fallback['fallback']['geometry_audit']}"

    print(f"OK — {len(ids)} cases, unique ids, reference fixture verifies green, "
          "sandbox-blocked fixture holds explicitly "
          "(fixtures prove wiring only; they are never benchmark evidence)")
    return 0


def cmd_report(args) -> int:
    man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in Path(args.results).read_text(encoding="utf-8").splitlines() if l.strip()]
    expected = {c["id"] for c in man["cases"]}
    clusters = {"operational": 0, "semantic": 0, "deterministic": 0, "visual-review": 0}
    usable = 0
    holds = set()
    seen: dict = {}
    unknown_case_ids: set = set()
    later_attempts = 0
    for r in rows:
        if r.get("case_id") not in expected:
            unknown_case_ids.add(str(r.get("case_id")))
            continue
        seen.setdefault(r["case_id"], []).append(r)
        attempt = r.get("attempt")
        # JSON true compares equal to 1; the attempt identity must be a real
        # integer, so boolean rows count as later attempts, never as attempt 1.
        if isinstance(attempt, bool) or attempt != 1:
            later_attempts += 1
        if r.get("status") == "operational-failure":
            clusters["operational"] += 1
            continue
        g = r.get("gates") or {}
        vr = g.get("visual_review", {}) if isinstance(g, dict) else {}
        holds.update(str(h) for h in ((vr or {}).get("holds") or []))
        if not isinstance(g, dict) or not g.get("semantic", {}).get("pass"):
            clusters["semantic"] += 1
        elif not g.get("deterministic", {}).get("pass"):
            clusters["deterministic"] += 1
        elif not visual_review_ok(vr):
            clusters["visual-review"] += 1
        elif isinstance(attempt, int) and not isinstance(attempt, bool) and attempt == 1:
            usable += 1
    missing = sorted(expected - set(seen))
    duplicates = sum(len(v) - 1 for v in seen.values())
    eligible = not missing and not unknown_case_ids and duplicates == 0 and later_attempts == 0
    print(json.dumps({
        "schema": 1, "cases": len(expected), "receipts": len(rows),
        "firstPassUsable": usable, "failureClusters": clusters,
        "holds": sorted(holds),
        "matrix": {
            "missing": len(missing), "duplicates": duplicates,
            "unknownCaseIds": len(unknown_case_ids), "laterAttempts": later_attempts,
        },
        "evidenceEligible": eligible,
    }, ensure_ascii=False))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("check"); s.add_argument("--manifest", default=str(Path(__file__).parent / "manifest.json"))
    s = sub.add_parser("verify")
    s.add_argument("--case", required=True); s.add_argument("--candidate", required=True); s.add_argument("--run", required=True)
    s = sub.add_parser("record-failure")
    s.add_argument("--case", required=True); s.add_argument("--run", required=True); s.add_argument("--failure", required=True)
    s = sub.add_parser("report")
    s.add_argument("--results", required=True); s.add_argument("--manifest", default=str(Path(__file__).parent / "manifest.json"))
    args = ap.parse_args()
    return {"check": cmd_check, "verify": cmd_verify,
            "record-failure": cmd_record_failure, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
