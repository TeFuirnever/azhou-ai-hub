#!/usr/bin/env python3
"""Daily-path double-click E2E for the ZCode Agent Skin host (design L5).

Runs against the installed daily launcher and its real daily state (journal,
receipt, live ZCode): the first click must complete the ordered refusal-free
startup chain with exit 0; receipt(pid/port), the lsof listener row, process
liveness and the probed DOM skin must agree four ways (P6.2), with the P6.1
trap state - receipt present, skin absent - reported red together with a
cold-restart advice; the second click must only activate the target without
replaying the injection (P7.1). Process identity always follows the receipt
pid and its port: the ZCode argv is overwritten by process.title, so pgrep by
executable path is blind (P5.2). The assertable logic (journal increment
parsing, chain verdicts, four-way audit, idempotence) lives in importable
pure functions; main() only orchestrates and defaults to --plan, which prints
the steps it would take without starting any process.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EVENT_SCHEMA = "azhou-startup.event.v1"
# Full observed daily chains (evidence: build 41 daily journal, 2026-11-08,
# launcherPIDs 62070 cold and 48011 hot; Native/App.swift emitFinal and
# resolveZCode). ZCode stages ride inside event="zcode-runtime" records as a
# "stage" field; the hot path trusts the receipt and never re-injects.
COLD_CHAIN = (
    "launcher-start",
    "zcode-open-request",
    "zcode-open-selected-process",
    "zcode-target-summary",
    "zcode-page-bound",
    "zcode-controller-ready",
    "startup-ready",
    "launcher-exit",
)
HOT_CHAIN = ("launcher-start", "target-activated", "launcher-exit")
# A second click that carries any of these replayed the cold injection.
REPLAY_STAGES = frozenset({
    "zcode-open-request", "zcode-open-selected-process", "zcode-target-summary",
    "zcode-page-bound", "zcode-controller-ready", "startup-ready",
})
REFUSAL_STAGES = frozenset({"zcode-runtime-failed", "zcode-validate-identity-refused"})
READY_OUTCOME = "startup-ready"
ACTIVATED_OUTCOME = "activated"
# P6.1 advice: the hot path trusted the receipt, so only a quit + cold start
# can bring the skin back. Shown verbatim in the red audit verdict.
TRAP_STATE_ADVICE = (
    "receipt names a live ZCode process on the expected port but the probed page "
    "has no Agent Skin: this is the P6.1 trap state (the hot path trusted the "
    "receipt and only activated the window without injecting). Quit ZCode "
    "completely and double-click the launcher again so the next start is cold "
    "and re-injects the skin."
)
# Native/Wallpaper.swift StartupEventJournal.directory(host: .zcode) and
# StartupLogPolicy.filePath: a plain double-click logs to this daily sink.
DEFAULT_LAUNCHER = Path.home() / "Applications/阿舟 AI 实验室 for ZCode.app/Contents/MacOS/AzhouZCodeStartup"
DEFAULT_JOURNAL = Path.home() / "Library/Logs/AzhouZCodeStartup/events.jsonl"
# probe_dom.mjs DEFAULT_RECEIPT; written by Native/ZCodeSkinRuntime.swift with
# pid/launchTime/port/executableSHA256 of the ZCode main process.
DEFAULT_RECEIPT = Path.home() / "Library/Application Support/Azhou AI Lab/ZCode/launch-receipt.json"
DEFAULT_PROBE_TOOL = ROOT / "tools/probe_dom.mjs"
DEFAULT_MARKER = ROOT / ".local/e2e-daily/marker.json"
DEFAULT_LSOF = "/usr/sbin/lsof"


def parse_receipt(text: str) -> dict:
    """Parse a launch receipt exactly like probe_dom.mjs parseReceipt.

    Raises ValueError with stable codes; the receipt pid is the ZCode main
    process (not the launcher), which is why every identity check below keys
    off receipt pid + port instead of pgrep on argv (P5.2).
    """
    try:
        value = json.loads(str(text))
    except ValueError as error:
        raise ValueError("receipt-not-json") from error
    if not isinstance(value, dict):
        raise ValueError("receipt-not-object")
    port, pid = value.get("port"), value.get("pid")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("receipt-port-invalid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 1:
        raise ValueError("receipt-pid-invalid")
    sha = value.get("executableSHA256")
    if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
        raise ValueError("receipt-sha-invalid")
    launch_time = value.get("launchTime")
    if (not isinstance(launch_time, (int, float)) or isinstance(launch_time, bool)
            or not math.isfinite(launch_time) or launch_time <= 0):
        raise ValueError("receipt-launch-time-invalid")
    return {"pid": pid, "port": port, "launchTime": float(launch_time), "executableSHA256": sha}


def parse_lsof_listen(lines: list[str]) -> list[dict]:
    """Parse `lsof -nP -iTCP:<port> -sTCP:LISTEN` rows into command/pid/port.

    The COMMAND column is whatever process.title left there, so it is carried
    as evidence only; identity comes from pid + port (P5.2).
    """
    entries: list[dict] = []
    for line in lines:
        text = line.strip()
        if not text or text.startswith("COMMAND"):
            continue
        parts = text.split()
        if len(parts) < 9 or "(LISTEN)" not in text:
            continue
        try:
            pid = int(parts[1])
            port = int(parts[8].rsplit(":", 1)[1])
        except (ValueError, IndexError):
            continue
        entries.append({"command": parts[0], "pid": pid, "port": port})
    return entries


def skin_in_place(probe: dict) -> dict:
    """DOM side of the audit: is the Agent Skin present on the probed page?

    Deliberately a presence check, not the full L4 geometry verdict: the
    audit only needs to know whether the hot path's trust in the receipt is
    visible in the page. The entry chip must be probed through its open
    shadow root (P5.1) - a light-DOM-only miss counts as absent.
    """
    if not isinstance(probe, dict):
        return {"check": "dom-skin", "passed": False,
                "problems": ["probe payload is not a JSON object"], "entry": None, "wallpaper": None}
    problems: list[str] = []
    wallpaper = probe.get("wallpaper") if isinstance(probe.get("wallpaper"), dict) else None
    entry = probe.get("entry") if isinstance(probe.get("entry"), dict) else None
    if wallpaper is None:
        problems.append("probe has no wallpaper section")
    else:
        if wallpaper.get("documentElement") != "active":
            problems.append("documentElement data-azhou-wallpaper is not active")
        active = [surface for surface in wallpaper.get("surfaces", [])
                  if isinstance(surface, dict) and surface.get("marker") == "active"
                  and (surface.get("rect") or {}).get("width", 0) > 0]
        if not active:
            problems.append("no active wallpaper surface with a non-empty rect")
    if entry is None:
        problems.append("probe has no entry section")
    else:
        if entry.get("found") is not True or entry.get("shadowRoot") is not True:
            problems.append("entry chip host is missing or was not probed through its open shadow root")
        elif not isinstance(entry.get("label"), str) or not entry["label"].strip():
            problems.append("entry chip label is missing from the shadow root")
    return {"check": "dom-skin", "passed": not problems, "problems": problems,
            "entry": entry, "wallpaper": wallpaper}


def audit_four_way(*, receipt: dict | None = None, receipt_problem: str | None = None,
                   lsof_lines: list[str] | None = None, process: dict | None = None,
                   probe: dict | None = None, probe_problem: str | None = None) -> dict:
    """Four-way consistency audit (P6.2): receipt <-> lsof <-> process <-> DOM.

    Pure over the collected snapshots; every missing or inconsistent side
    becomes a structured problem. The P6.1 trap state - receipt valid, port
    held by the receipt pid, process alive, yet no skin in the DOM - turns
    the verdict red and carries the cold-restart advice verbatim.
    """
    problems: list[str] = []
    sides = {"receipt": "unknown", "lsof": "unknown", "process": "unknown", "domSkin": "unknown"}
    if receipt is None:
        sides["receipt"] = "missing"
        problems.append(f"receipt unavailable: {receipt_problem or 'not read'}")
    else:
        sides["receipt"] = "ok"
    listeners = parse_lsof_listen(list(lsof_lines or []))
    if receipt is not None:
        holders = sorted({entry["pid"] for entry in listeners if entry["port"] == receipt["port"]})
        if not listeners:
            sides["lsof"] = "missing"
            problems.append(f"lsof found no LISTEN row for port {receipt['port']}")
        elif receipt["pid"] not in holders:
            sides["lsof"] = "inconsistent"
            problems.append(f"port {receipt['port']} is held by pid {holders}, receipt says pid {receipt['pid']}")
        else:
            sides["lsof"] = "ok"
    if receipt is None:
        sides["process"] = "unknown"
    elif not isinstance(process, dict):
        sides["process"] = "missing"
        problems.append("no process-aliveness snapshot for the receipt pid")
    elif process.get("alive") is not True:
        sides["process"] = "dead"
        problems.append(f"receipt pid {receipt['pid']} is not alive")
    elif process.get("pid") != receipt["pid"]:
        sides["process"] = "inconsistent"
        problems.append(f"process snapshot pid {process.get('pid')!r} != receipt pid {receipt['pid']}")
    else:
        sides["process"] = "ok"
    skin = skin_in_place(probe) if probe is not None else None
    if probe is None:
        sides["domSkin"] = "missing"
        problems.append(f"DOM probe unavailable: {probe_problem or 'not run'}")
    elif skin["passed"]:
        sides["domSkin"] = "ok"
    else:
        sides["domSkin"] = "absent"
        problems.extend(f"dom skin: {problem}" for problem in skin["problems"])
    trap_state = (receipt is not None and sides["lsof"] == "ok" and sides["process"] == "ok"
                  and sides["domSkin"] == "absent")
    if trap_state:
        problems.append(TRAP_STATE_ADVICE)
    return {"check": "four-way-consistency", "passed": not problems, "sides": sides,
            "listeners": listeners, "skin": skin, "trapState": trap_state,
            "advice": TRAP_STATE_ADVICE if trap_state else None, "problems": problems}


def _journal_events(records: list[dict]) -> list[dict]:
    return [record for record in records if record.get("schema") == EVENT_SCHEMA]


def _effective_stage(record: dict) -> str | None:
    """Journal event name; ZCode runtime stages come from their stage field."""
    if record.get("event") == "zcode-runtime":
        stage = record.get("stage")
        return stage if isinstance(stage, str) and stage else None
    event = record.get("event")
    return event if isinstance(event, str) and event else None


def parse_journal_increment(lines: list[str], start_line: int = 0) -> dict:
    """Group a journal increment by launcherPID with absolute line ranges.

    Only lines after start_line (the pre-run line count recorded in the
    marker) are attributed, so pre-existing daily runs cannot poison this
    run's slices. Each schema event joins the group of its launcherPID in
    first-appearance order; the journal stays self-proving - unparsable,
    non-object, or unattributable lines become problems, never silent skips.
    """
    records: list[tuple[int, dict]] = []
    problems: list[str] = []
    for offset, line in enumerate(lines[max(0, start_line):], start=max(0, start_line)):
        number = offset + 1
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
        records.append((number, value))
    groups: list[dict] = []
    group_index: dict[int, int] = {}
    for number, record in records:
        if record.get("schema") != EVENT_SCHEMA:
            continue
        pid = record.get("launcherPID")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            problems.append(f"line {number}: schema event without a valid launcherPID")
            continue
        if pid not in group_index:
            group_index[pid] = len(groups)
            groups.append({"launcherPID": pid, "startLine": number, "endLine": number, "records": []})
        group = groups[group_index[pid]]
        group["records"].append(record)
        group["endLine"] = number
    return {"groups": groups, "problems": problems, "lineCount": len(lines), "startLine": max(0, start_line)}


def _records_of(slice_value) -> list[dict]:
    """Accept a parsed increment group or a bare records list."""
    if isinstance(slice_value, dict):
        records = slice_value.get("records")
        return records if isinstance(records, list) else []
    if isinstance(slice_value, list):
        return slice_value
    return []


def assert_chain(records: list[dict], problems: list[str] | None = None, *,
                 required: tuple[str, ...], expected_outcome: str, check: str) -> dict:
    """Ordered, complete, refusal-free chain verdict for one launcherPID slice.

    Green requires every required stage present in order (by first
    occurrence), zero refusal stages anywhere in the slice, exactly one
    launcher-exit with the expected outcome and exitCode 0, non-decreasing
    "seconds" (each launcher clamps its own writer; monotonicity holds within
    one pid group and is only claimed there), and a parsable journal.
    """
    parse_problems = list(problems or [])
    events = _journal_events(records)
    stages = [_effective_stage(record) for record in events]
    first_positions: dict[str, int] = {}
    for index, stage in enumerate(stages):
        if stage in required and stage not in first_positions:
            first_positions[stage] = index
    missing = [stage for stage in required if stage not in first_positions]
    present = [stage for stage in required if stage in first_positions]
    out_of_order = []
    for earlier, later in zip(present, present[1:]):
        if first_positions[later] < first_positions[earlier]:
            out_of_order.append(f"{later} before {earlier}")
    refusals = []
    for index, record in enumerate(events):
        stage = _effective_stage(record)
        if stage not in REFUSAL_STAGES:
            continue
        refusals.append({"index": index, "stage": stage, "reason": record.get("reason"),
                         "point": record.get("point"), "observed": record.get("observed")})
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
        if exits[0].get("outcome") != expected_outcome:
            outcome_problems.append(f"launcher-exit outcome {exits[0].get('outcome')!r} != {expected_outcome!r}")
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
    verdict_problems.extend(outcome_problems)
    if not seconds_monotonic:
        verdict_problems.append("journal seconds are not non-decreasing")
    return {"check": check, "passed": not verdict_problems,
            "chainRequired": list(required),
            "chainObserved": [stage for stage in stages if stage in required],
            "missing": missing, "outOfOrder": out_of_order, "refusals": refusals,
            "exits": exits, "secondsMonotonic": seconds_monotonic,
            "journalProblems": parse_problems, "problems": verdict_problems}


def assert_daily_chain(group, problems: list[str] | None = None) -> dict:
    """Family-1 verdict for one increment group: the full daily cold chain."""
    if not isinstance(group, dict) or not isinstance(group.get("records"), list):
        verdict = assert_chain([], problems, required=COLD_CHAIN,
                               expected_outcome=READY_OUTCOME, check="daily-cold-chain")
        verdict["problems"] = ["increment group is malformed"] + verdict["problems"]
        verdict["passed"] = False
        return verdict
    verdict = assert_chain(group["records"], problems, required=COLD_CHAIN,
                           expected_outcome=READY_OUTCOME, check="daily-cold-chain")
    verdict["launcherPID"] = group.get("launcherPID")
    verdict["startLine"] = group.get("startLine")
    verdict["endLine"] = group.get("endLine")
    return verdict


def assert_idempotent_second_click(first, second, problems: list[str] | None = None,
                                   *, receipt_before: dict | None = None,
                                   receipt_after: dict | None = None) -> dict:
    """Family-3 verdict (P7.1 daily face): the second click only activates.

    The first slice must have proven the cold startup chain; the second slice
    must be the hot chain (launcher-start, target-activated, launcher-exit
    with outcome activated and exitCode 0), must name the activated targetPID
    (Native/App.swift resolveZCode), must replay none of the injection stages
    (no zcode-open-request and friends), and must not have rewritten the
    receipt the first click left behind.
    """
    journal_problems = list(problems or [])
    first_verdict = assert_chain(_records_of(first), journal_problems, required=COLD_CHAIN,
                                 expected_outcome=READY_OUTCOME, check="first-click-chain")
    second_events = _journal_events(_records_of(second))
    second_verdict = assert_chain(_records_of(second), journal_problems, required=HOT_CHAIN,
                                  expected_outcome=ACTIVATED_OUTCOME, check="second-click-chain")
    replay = [stage for stage in (_effective_stage(record) for record in second_events)
              if stage in REPLAY_STAGES]
    replay_problems = [f"second click replayed injection stages: {', '.join(replay)}"] if replay else []
    activations = [record for record in second_events if record.get("event") == "target-activated"]
    activation_problems = []
    if len(activations) != 1:
        activation_problems.append(f"expected exactly one target-activated in the second click, saw {len(activations)}")
    else:
        target_pid = activations[0].get("targetPID")
        if not isinstance(target_pid, int) or isinstance(target_pid, bool) or target_pid <= 0:
            activation_problems.append("target-activated does not name a valid targetPID")
    receipt_problems = []
    if receipt_before is not None and receipt_after is None:
        receipt_problems.append("receipt disappeared during the second click")
    elif receipt_before is not None and receipt_after is not None:
        changed = [key for key in ("pid", "port", "launchTime", "executableSHA256")
                   if receipt_before.get(key) != receipt_after.get(key)]
        if changed:
            receipt_problems.append(f"receipt was rewritten during the second click: {', '.join(changed)}")
    verdict_problems = []
    if not first_verdict["passed"]:
        verdict_problems.append("first click did not prove the cold startup chain")
    if not second_verdict["passed"]:
        verdict_problems.append("second click is not the clean activation chain")
    verdict_problems.extend(replay_problems + activation_problems + receipt_problems)
    return {"check": "idempotent-second-click", "passed": not verdict_problems,
            "first": first_verdict, "second": second_verdict,
            "injectionReplay": replay, "receiptRewritten": bool(receipt_problems),
            "receiptProblems": receipt_problems, "problems": verdict_problems}


def assemble_daily_report(cold: dict, four_way: dict, idempotent: dict) -> dict:
    """Combine every daily-path assertion into one strict-exit report."""
    checks = [cold, four_way, idempotent]
    return {"kind": "e2e-daily", "schema": 1,
            "passed": all(check["passed"] for check in checks), "checks": checks}


def build_plan(*, launcher: Path, journal: Path, receipt: Path, marker: Path,
               probe_tool: Path, lsof_bin: str, ready_wait_seconds: float,
               click_timeout_seconds: float) -> dict:
    """The exact steps a daily run takes; --plan prints exactly this."""
    return {
        "kind": "e2e-daily-plan", "schema": 1, "profile": "daily",
        "launcher": str(launcher), "journal": str(journal), "receipt": str(receipt),
        "marker": str(marker), "startsProcess": True,
        "precondition": "ZCode must not be running before the first click; a hot first click fails the cold-chain assertion on purpose",
        "readyWaitSeconds": ready_wait_seconds,
        "steps": [
            {"id": "increment-marker", "action": "record the pre-run journal line count",
             "path": str(marker), "journal": str(journal)},
            {"id": "first-click", "action": "run the installed launcher once with no arguments (double-click equivalent)",
             "command": [str(launcher)], "arguments": [], "timeoutSeconds": click_timeout_seconds},
            {"id": "first-increment", "action": "group the journal increment by launcherPID and assert the ordered refusal-free startup chain",
             "chain": list(COLD_CHAIN)},
            {"id": "four-way-audit", "action": "cross-check receipt pid/port, the lsof LISTEN row, process liveness and the probed DOM skin",
             "receipt": str(receipt), "lsofBin": lsof_bin,
             "lsofCommand": [lsof_bin, "-nP", "-w", "-iTCP:<receipt.port>", "-sTCP:LISTEN"],
             "probeCommand": ["node", str(probe_tool), "--receipt", str(receipt)],
             "note": "identity follows the receipt pid and its port; the ZCode argv is overwritten by process.title, so no pgrep by path"},
            {"id": "second-click", "action": "run the launcher again with no arguments",
             "command": [str(launcher)], "arguments": [], "timeoutSeconds": click_timeout_seconds},
            {"id": "second-increment", "action": "assert the second click only activated: hot chain, no injection replay, receipt not rewritten",
             "chain": list(HOT_CHAIN)},
            {"id": "marker-cleanup", "action": "remove the increment marker so no daily-run residue stays behind",
             "path": str(marker)},
        ],
    }


def _read_journal_lines(journal: Path) -> list[str]:
    return journal.read_text(encoding="utf-8").splitlines() if journal.is_file() else []


def _wait_for_exit(journal: Path, start_line: int, budget_seconds: float) -> dict:
    """Bounded poll (rc36 lesson: never assert an unready world) until the
    increment grows a launcherPID group that holds launcher-exit."""
    deadline = time.monotonic() + budget_seconds
    increment = parse_journal_increment(_read_journal_lines(journal), start_line)
    while not any(record.get("event") == "launcher-exit" for group in increment["groups"]
                  for record in group["records"]) and time.monotonic() < deadline:
        time.sleep(0.2)
        increment = parse_journal_increment(_read_journal_lines(journal), start_line)
    return increment


def _single_new_group(increment: dict) -> tuple[dict | None, str | None]:
    groups = increment.get("groups", [])
    if len(groups) != 1:
        return None, (f"journal increment holds {len(groups)} launcherPID groups, "
                      "expected exactly the one from this click")
    return groups[0], None


def _read_receipt(path: Path) -> tuple[dict | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return None, f"receipt unreadable at {path}: {error}"
    try:
        return parse_receipt(text), None
    except ValueError as error:
        return None, f"receipt invalid: {error}"


def _lsof_lines(lsof_bin: str, port: int) -> list[str]:
    completed = subprocess.run([lsof_bin, "-nP", "-w", f"-iTCP:{port}", "-sTCP:LISTEN"],
                               capture_output=True, text=True, timeout=15, check=False)
    return completed.stdout.splitlines()


def _process_snapshot(pid: int) -> dict:
    """Alive check by receipt pid only (P5.2): signal 0, never pgrep by path."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return {"pid": pid, "alive": False}
    except PermissionError:
        return {"pid": pid, "alive": True}
    return {"pid": pid, "alive": True}


def _probe_snapshot(command: list[str]) -> tuple[dict | None, str | None]:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
    if completed.returncode != 0:
        return None, f"probe exited {completed.returncode}: {completed.stderr.strip()[:200]}"
    try:
        return json.loads(completed.stdout), None
    except ValueError:
        return None, "probe stdout is not JSON"


def _collect_four_way(step: dict) -> dict:
    receipt, receipt_problem = _read_receipt(Path(step["receipt"]))
    lsof_lines: list[str] = []
    process: dict | None = None
    if receipt is not None:
        lsof_lines = _lsof_lines(step["lsofBin"], receipt["port"])
        process = _process_snapshot(receipt["pid"])
    probe, probe_problem = _probe_snapshot(step["probeCommand"])
    return {"receipt": receipt, "receipt_problem": receipt_problem, "lsof_lines": lsof_lines,
            "process": process, "probe": probe, "probe_problem": probe_problem}


def run_daily(plan: dict) -> dict:
    """Execute a plan. Real-launch path: never invoked by --plan and untested
    against a live host in this change (L5 stage; starts the daily launcher
    and ZCode). The marker is removed in finally so the run leaves no residue
    (design L5: clean up own event-increment marker)."""
    marker = Path(plan["steps"][0]["path"])
    journal = Path(plan["steps"][0]["journal"])
    launcher = plan["steps"][1]["command"][0]
    audit_step = plan["steps"][3]
    wait = plan["readyWaitSeconds"]
    click_timeout = plan["steps"][1]["timeoutSeconds"]
    checks: list[dict] = []
    early_problems: list[str] = []
    try:
        start_line = len(_read_journal_lines(journal))
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"journal": str(journal), "startLine": start_line}),
                          encoding="utf-8")
        subprocess.run([str(launcher)], capture_output=True, text=True,
                       timeout=click_timeout, check=False)
        first_increment = _wait_for_exit(journal, start_line, wait)
        first_group, first_problem = _single_new_group(first_increment)
        cold = (assert_daily_chain(first_group, first_increment["problems"]) if first_group is not None
                else assert_daily_chain(None, [first_problem]))
        checks.append(cold)
        snapshot = _collect_four_way(audit_step)
        checks.append(audit_four_way(**snapshot))
        second_start = first_increment["lineCount"]
        subprocess.run([str(launcher)], capture_output=True, text=True,
                       timeout=click_timeout, check=False)
        second_increment = _wait_for_exit(journal, second_start, wait)
        second_group, second_problem = _single_new_group(second_increment)
        if second_group is not None:
            receipt_after, _ = _read_receipt(Path(audit_step["receipt"]))
            checks.append(assert_idempotent_second_click(
                first_group or {"records": []}, second_group, second_increment["problems"],
                receipt_before=snapshot["receipt"], receipt_after=receipt_after))
        else:
            checks.append(assert_idempotent_second_click(
                {"records": []}, {"records": []}, [*second_increment["problems"], second_problem]))
        if first_group is None:
            early_problems.append(first_problem or "first increment produced no group")
    finally:
        marker.unlink(missing_ok=True)
    report = assemble_daily_report(checks[0], checks[1], checks[2])
    report["markerCleanedUp"] = not marker.exists()
    report["passed"] = report["passed"] and report["markerCleanedUp"] and not early_problems
    report["problems"] = early_problems
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launcher", type=Path, default=DEFAULT_LAUNCHER)
    parser.add_argument("--journal", type=Path, default=DEFAULT_JOURNAL,
                        help="daily append-only event sink of the installed launcher")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--probe-tool", type=Path, default=DEFAULT_PROBE_TOOL)
    parser.add_argument("--marker", type=Path, default=DEFAULT_MARKER,
                        help="increment marker noting the pre-run journal line count")
    parser.add_argument("--lsof", default=DEFAULT_LSOF)
    parser.add_argument("--ready-wait", type=float, default=8.0,
                        help="bounded wait per click for the run's launcher-exit (rc36 lesson: never assert an unready world)")
    parser.add_argument("--click-timeout", type=float, default=90.0)
    plan_mode = parser.add_mutually_exclusive_group()
    plan_mode.add_argument("--plan", action="store_true", default=True,
                           help="print the plan and exit without starting any process (default)")
    plan_mode.add_argument("--execute", action="store_true",
                           help="actually run the daily double-click path (starts the launcher and ZCode)")
    options = parser.parse_args(argv)
    plan = build_plan(launcher=options.launcher, journal=options.journal, receipt=options.receipt,
                      marker=options.marker, probe_tool=options.probe_tool, lsof_bin=options.lsof,
                      ready_wait_seconds=options.ready_wait, click_timeout_seconds=options.click_timeout)
    if options.execute:
        report = run_daily(plan)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("passed") else 2
    # Plan mode only prints; a clean print is a clean exit (exit-code discipline:
    # a plan must not read as a failed run in a pipeline).
    report = {**plan, "startsProcess": False, "executed": False}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
