#!/usr/bin/env python3
"""Disposable-profile cold-start E2E for the ZCode Agent Skin host (design L4).

One fresh disposable profile per run (no daily data access): driver cold launch
into an isolated --zcode-state-root with its own --log journal, ordered/complete
event-chain assertion with zero refusal events, shadow-aware DOM probing of both
wallpaper surfaces and the sidebar entry chip, then dispose cleanup. The
assertable logic (journal parsing, verdict assembly) lives in importable pure
functions; main() only orchestrates and defaults to --plan, which prints the
steps it would take without starting any process.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EVENT_SCHEMA = "azhou-startup.event.v1"
# Full observed cold chain (evidence: build 41 daily acceptance, 2026-11-08):
# launcher-start -> zcode-open-request -> zcode-open-selected-process ->
# zcode-target-summary -> zcode-page-bound -> zcode-controller-ready ->
# startup-ready, closed by launcher-exit. ZCode stages ride inside
# event="zcode-runtime" records as a "stage" field (Native/App.swift
# emitZCodeRuntimeEvent; Native/ZCodeSkinRuntime.swift onEvent).
COLD_START_CHAIN = (
    "launcher-start",
    "zcode-open-request",
    "zcode-open-selected-process",
    "zcode-target-summary",
    "zcode-page-bound",
    "zcode-controller-ready",
    "startup-ready",
    "launcher-exit",
)
REFUSAL_STAGES = frozenset({"zcode-runtime-failed", "zcode-validate-identity-refused"})
READY_OUTCOME = "startup-ready"
PROBE_TOOL = ROOT / "tools/probe_dom.mjs"
DEFAULT_RECEIPT = Path.home() / "Library/Application Support/Azhou AI Lab/ZCode/launch-receipt.json"
# Native/App.swift makeZCodeDriver: an explicit --zcode-state-root redirects the
# receipt/state directory away from the daily profile.
LAUNCHER_ARGUMENTS = ("--zcode-state-root", "--log")
# build-macos.sh native_executable=AzhouZCodeStartup (same canonical name as
# e2e-daily.py DEFAULT_LAUNCHER); a mistyped default cannot be seen from --plan,
# so the name is pinned by a unit test instead.
DEFAULT_LAUNCHER = Path.home() / "Applications/阿舟 AI 实验室 for ZCode.app/Contents/MacOS/AzhouZCodeStartup"


def parse_event_lines(lines: list[str]) -> tuple[list[dict], list[str]]:
    """Parse a launcher journal into records; report every unparsable line.

    The journal must be self-proving: a line that is not a JSON object is a
    problem, never silently skipped. Returns (records, problems) where problems
    are human-readable "line N: ..." strings.
    """
    records: list[dict] = []
    problems: list[str] = []
    for number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            value = json.loads(text)
        except ValueError as error:
            problems.append(f"line {number}: not JSON ({error})")
            continue
        if not isinstance(value, dict):
            problems.append(f"line {number}: not a JSON object")
            continue
        records.append(value)
    return records, problems


def journal_events(records: list[dict]) -> list[dict]:
    """Schema-bearing startup events only; other lines are diagnostics."""
    return [record for record in records if record.get("schema") == EVENT_SCHEMA]


def effective_stage(record: dict) -> str | None:
    """Journal event name; ZCode runtime stages come from their stage field."""
    if record.get("event") == "zcode-runtime":
        stage = record.get("stage")
        return stage if isinstance(stage, str) and stage else None
    event = record.get("event")
    return event if isinstance(event, str) and event else None


def assert_event_chain(records: list[dict], problems: list[str] | None = None) -> dict:
    """Ordered, complete, refusal-free cold-start chain verdict.

    Green requires: every COLD_START_CHAIN stage present in order (by first
    occurrence), zero refusal stages anywhere, exactly one launcher-exit with
    outcome=startup-ready and exitCode 0, non-decreasing "seconds" (the native
    writer already clamps them monotonic), and a parsable journal.
    """
    parse_problems = list(problems or [])
    events = journal_events(records)
    stages = [effective_stage(record) for record in events]
    first_positions: dict[str, int] = {}
    for index, stage in enumerate(stages):
        if stage in COLD_START_CHAIN and stage not in first_positions:
            first_positions[stage] = index
    missing = [stage for stage in COLD_START_CHAIN if stage not in first_positions]
    present = [stage for stage in COLD_START_CHAIN if stage in first_positions]
    out_of_order = []
    for earlier, later in zip(present, present[1:]):
        if first_positions[later] < first_positions[earlier]:
            out_of_order.append(f"{later} before {earlier}")
    refusals = []
    for index, record in enumerate(events):
        stage = effective_stage(record)
        if stage not in REFUSAL_STAGES:
            continue
        refusals.append({"index": index, "stage": stage,
                         "reason": record.get("reason"), "point": record.get("point"),
                         "observed": record.get("observed")})
    exits = [{"outcome": record.get("outcome"), "exitCode": record.get("exitCode")}
             for record in events if record.get("event") == "launcher-exit"]
    seconds = [record.get("seconds") for record in events]
    seconds_monotonic = all(
        isinstance(before, (int, float)) and isinstance(after, (int, float)) and after >= before
        for before, after in zip(seconds, seconds[1:])
    )
    outcome_problems = []
    if len(exits) != 1:
        outcome_problems.append(f"expected exactly one launcher-exit, saw {len(exits)}")
    else:
        if exits[0].get("outcome") != READY_OUTCOME:
            outcome_problems.append(f"launcher-exit outcome {exits[0].get('outcome')!r} != {READY_OUTCOME!r}")
        if exits[0].get("exitCode") != 0:
            outcome_problems.append(f"launcher-exit exitCode {exits[0].get('exitCode')!r} != 0")
    verdict_problems = []
    if parse_problems:
        verdict_problems.append("journal has unparsable lines")
    if missing:
        verdict_problems.append(f"missing stages: {', '.join(missing)}")
    if out_of_order:
        verdict_problems.append(f"out of order: {'; '.join(out_of_order)}")
    if refusals:
        verdict_problems.append(f"refusal events: {', '.join(item['stage'] for item in refusals)}")
    if outcome_problems:
        verdict_problems.extend(outcome_problems)
    if not seconds_monotonic:
        verdict_problems.append("journal seconds are not non-decreasing")
    return {
        "check": "event-chain",
        "passed": not verdict_problems,
        "chainRequired": list(COLD_START_CHAIN),
        "chainObserved": [stage for stage in stages if stage in COLD_START_CHAIN],
        "missing": missing,
        "outOfOrder": out_of_order,
        "refusals": refusals,
        "exits": exits,
        "secondsMonotonic": seconds_monotonic,
        "journalProblems": parse_problems,
        "problems": verdict_problems,
    }


def assert_wallpaper_surfaces(probe: dict) -> dict:
    """Both ZCode wallpaper surfaces active: full window (#root) + main pane."""
    problems: list[str] = []
    wallpaper = probe.get("wallpaper") if isinstance(probe, dict) else None
    if not isinstance(wallpaper, dict):
        return {"check": "wallpaper-surfaces", "passed": False,
                "problems": ["probe has no wallpaper section"],
                "documentElement": None, "surfaces": []}
    document_element = wallpaper.get("documentElement")
    if document_element != "active":
        problems.append(f"documentElement data-azhou-wallpaper is {document_element!r}, expected 'active'")
    surfaces = [surface for surface in wallpaper.get("surfaces", []) if isinstance(surface, dict)]
    active = [surface for surface in surfaces if surface.get("marker") == "active"]

    def largest(surfaces: list[dict]) -> dict | None:
        return max(surfaces, key=lambda surface: (surface.get("rect") or {}).get("width", 0), default=None)

    roots = [surface for surface in active if surface.get("role") == "root"]
    mains = [surface for surface in active if surface.get("role") == "main"]
    if not roots:
        problems.append("no active full-window (#root) wallpaper surface")
    if not mains:
        problems.append("no active main-pane (main) wallpaper surface")
    root, main = largest(roots), largest(mains)
    for label, surface in (("root", root), ("main", main)):
        if surface:
            rect = surface.get("rect") or {}
            if rect.get("width", 0) <= 0 or rect.get("height", 0) <= 0:
                problems.append(f"{label} wallpaper surface has an empty rect")
    if root and main and not problems:
        root_rect, main_rect = root.get("rect") or {}, main.get("rect") or {}
        if root_rect.get("width", 0) < main_rect.get("width", 0) or root_rect.get("height", 0) < main_rect.get("height", 0):
            problems.append("full-window surface does not cover the main pane")
    return {"check": "wallpaper-surfaces", "passed": not problems,
            "documentElement": document_element,
            "surfaces": surfaces, "problems": problems}


def assert_entry_chip(probe: dict) -> dict:
    """Sidebar entry chip verdict, probed through its shadow root (P5.1).

    textContent/innerHTML on the light DOM cannot see the chip; the probe JSON
    must come from [data-agent-skin-entry].shadowRoot. Green requires the chip
    host, its open shadow root, label, aria-label, loaded avatar, a non-empty
    rect and placement inside the sidebar.
    """
    problems: list[str] = []
    entry = probe.get("entry") if isinstance(probe, dict) else None
    if not isinstance(entry, dict):
        return {"check": "entry-chip", "passed": False, "problems": ["probe has no entry section"], "entry": None}
    if not entry.get("found"):
        problems.append("entry host [data-agent-skin-entry] not found in the light DOM")
    if not entry.get("shadowRoot"):
        problems.append("entry host has no probed open shadow root")
    for field, label in (("label", "label text"), ("ariaLabel", "aria-label")):
        value = entry.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"entry chip {label} is missing or empty")
    avatar = entry.get("avatar")
    if not isinstance(avatar, dict) or not avatar.get("present"):
        problems.append("entry chip avatar image is missing from the shadow root")
    elif avatar.get("complete") is not True or avatar.get("naturalWidth", 0) <= 0:
        problems.append("entry chip avatar image did not load")
    rect = entry.get("rect")
    if not isinstance(rect, dict) or rect.get("width", 0) <= 0 or rect.get("height", 0) <= 0:
        problems.append("entry chip rect is empty")
    if entry.get("inSidebar") is not True:
        problems.append("entry chip is not inside aside[data-testid='sidebar']")
    if entry.get("visible") is False:
        problems.append("entry chip rect is not visible (zero width/height)")
    return {"check": "entry-chip", "passed": not problems, "entry": entry, "problems": problems}


def assemble_verdicts(records: list[dict], probe: dict, problems: list[str] | None = None) -> dict:
    """Combine every cold-start assertion into one strict-exit report."""
    checks = [assert_event_chain(records, problems), assert_wallpaper_surfaces(probe), assert_entry_chip(probe)]
    return {"kind": "e2e-cold-start", "schema": 1, "passed": all(check["passed"] for check in checks),
            "checks": checks}


def build_plan(*, profile: str, launcher: Path, state_root: Path, journal: Path,
               receipt: Path, probe_tool: Path, ready_wait_seconds: float) -> dict:
    """The exact steps a cold-start run takes; --plan prints exactly this."""
    return {
        "kind": "e2e-cold-start-plan", "schema": 1, "profile": profile,
        "launcher": str(launcher), "startsProcess": True,
        "steps": [
            {"id": "prepare", "action": "create disposable state root",
             "path": str(state_root), "mode": "0o700", "removesExisting": False},
            {"id": "cold-launch", "action": "run launcher once with isolated state",
             "command": [str(launcher), LAUNCHER_ARGUMENTS[0], str(state_root),
                         LAUNCHER_ARGUMENTS[1], str(journal)],
             "note": "plain cold start; no --probe/--preview/--smoke-test"},
            {"id": "receipt-wait", "action": "bounded wait for the disposable receipt",
             "path": str(receipt), "budgetSeconds": ready_wait_seconds},
            {"id": "dom-probe", "action": "shadow-aware read-only CDP probe",
             "command": ["node", str(probe_tool), "--receipt", str(receipt)]},
            {"id": "journal-assert", "action": "parse journal and assert the ordered refusal-free chain",
             "path": str(journal)},
            {"id": "dispose", "action": "remove the disposable state root and verify removal",
             "path": str(state_root)},
        ],
    }


def run_cold_start(plan: dict) -> dict:
    """Execute against a newly owned state root; retain evidence on failure.

    Isolated tests mock only the host/process boundary. They are not live-host
    acceptance. An existing path is never removed to make a new run possible.
    """
    state_root = Path(plan["steps"][0]["path"])
    failure = {"kind": "e2e-cold-start", "schema": 1, "passed": False}
    try:
        state_root.mkdir(parents=True, mode=0o700)
    except OSError as error:
        return {**failure, "problems": [f"cannot acquire fresh state root; existing content preserved: {error}"]}
    journal = Path(plan["steps"][4]["path"])
    launch = plan["steps"][1]
    try:
        completed = subprocess.run(launch["command"], capture_output=True, text=True, timeout=120, check=False)
        if completed.returncode != 0:
            return {**failure, "launcherExit": completed.returncode,
                    "problems": ["launcher failed; no successful journal may override its exit code"]}
        receipt = Path(plan["steps"][2]["path"])
        budget = plan["steps"][2]["budgetSeconds"]
        deadline = time.monotonic() + budget
        while not receipt.is_file() and time.monotonic() < deadline:
            time.sleep(0.2)
        if not receipt.is_file():
            return {**failure, "problems": [f"receipt never appeared within {budget}s"],
                    "launcherExit": completed.returncode, "stdout": completed.stdout[-2000:]}
        probe_run = subprocess.run(plan["steps"][3]["command"], capture_output=True, text=True, timeout=60, check=False)
        if probe_run.returncode != 0:
            return {**failure, "problems": [f"probe failed: {probe_run.stderr.strip()}"]}
        probe = json.loads(probe_run.stdout)
        lines = journal.read_text(encoding="utf-8").splitlines() if journal.is_file() else []
        records, problems = parse_event_lines(lines)
        report = assemble_verdicts(records, probe, problems)
        if report["passed"]:
            shutil.rmtree(state_root)
        report["disposed"] = not state_root.exists()
        report["passed"] = report["passed"] and report["disposed"]
        return report
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        return {**failure, "problems": [f"cold-start execution failed: {error}"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("disposable",), default="disposable",
                        help="disposable: fresh isolated state root, no daily data access")
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER)
    parser.add_argument("--state-root", type=Path, default=None,
                        help="disposable state root (default .local/e2e-cold-start/<timestamp>)")
    parser.add_argument("--journal", type=Path, default=None,
                        help="isolated --log journal path (default <state-root>/events.jsonl)")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--probe-tool", type=Path, default=PROBE_TOOL)
    parser.add_argument("--ready-wait", type=float, default=8.0,
                        help="bounded receipt wait in seconds (rc36 lesson: never assert an unready world)")
    plan_mode = parser.add_mutually_exclusive_group()
    plan_mode.add_argument("--plan", action="store_true", default=True,
                           help="print the plan and exit without starting any process (default)")
    plan_mode.add_argument("--execute", action="store_true",
                           help="actually run the cold start (starts the launcher and ZCode)")
    options = parser.parse_args(argv)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    state_root = options.state_root or ROOT / f".local/e2e-cold-start/{stamp}"
    journal = options.journal or state_root / "events.jsonl"
    receipt = options.receipt if options.receipt != DEFAULT_RECEIPT else state_root / "launch-receipt.json"
    plan = build_plan(profile=options.profile, launcher=options.launcher, state_root=state_root,
                      journal=journal, receipt=receipt, probe_tool=options.probe_tool,
                      ready_wait_seconds=options.ready_wait)
    if options.execute:
        report = run_cold_start(plan)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("passed") else 2
    # Plan mode only prints; a clean print is a clean exit (exit-code discipline:
    # a plan must not read as a failed run in a pipeline).
    report = {**plan, "startsProcess": False, "executed": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
