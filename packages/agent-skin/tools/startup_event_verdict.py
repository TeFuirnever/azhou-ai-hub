"""Pure native-launch receipt checks shared by Hub and installed acceptance.

These checks establish consistency of launcher evidence, not visual continuity.
They consume only the versioned native terminal emitted by NativeStartupEventStream.
"""
from __future__ import annotations

import math
from pathlib import PurePosixPath, PureWindowsPath
from uuid import UUID

SCHEMA = "azhou-startup.event.v1"
NATIVE_RESULT = "startup-native-result"
_CRITICAL = frozenset({"launcher-start", "target-opened", "target-activated", "startup-installed",
    "startup-ready", "startup-skipped", "startup-interrupted", "startup-failed", NATIVE_RESULT,
    "launcher-exit", "failure", "duplicate-entry", "lock-error", "startup-port-error"})
_FORBIDDEN = _CRITICAL - {"launcher-start", "target-opened", "startup-installed", NATIVE_RESULT, "launcher-exit"}
_ENDS = {"completed": ("startup-ready", 0, "native-completed", "completed"),
         "skipped": ("skipped", 0, "skipped", "skipped"),
         "interrupted": ("partial", 2, "partial", "interrupted"),
         "failed": ("behavior-not-proven", 1, "behavior-not-proven", "failed")}


def _absolute_path(value: object) -> bool:
    return isinstance(value, str) and (
        PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
    )


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def assess_native_launch(events: list[dict], returncode: object,
                         launcher_path: str | None = None) -> dict | None:
    """Return a fail-closed native assessment, or None for an entirely old stream."""
    if not any(item.get("event") == NATIVE_RESULT for item in events):
        return None
    refused = {"status": "behavior-not-proven", "startup": {
        "status": "not-attempted", "injection": "not-proven", "installed": False}}
    if any(not isinstance(item.get("event"), str) or
           "schema" in item and (item["schema"] != SCHEMA or item["event"] not in _CRITICAL) for item in events):
        return refused
    critical = [item for item in events if item.get("event") in _CRITICAL]
    names = [item["event"] for item in critical]
    if (names.count("launcher-start") != 1 or names.count(NATIVE_RESULT) != 1
            or names.count("launcher-exit") != 1 or names[0] != "launcher-start"
            or names[-2:] != [NATIVE_RESULT, "launcher-exit"] or _FORBIDDEN.intersection(names)):
        return refused
    path = launcher_path if launcher_path is not None else critical[0].get("launcherPath")
    pid = critical[0].get("launcherPID")
    previous = 0.0
    for item in critical:
        seconds = item.get("seconds")
        if (item.get("schema") != SCHEMA or not _positive(pid) or not _positive(item.get("launcherPID"))
                or item.get("launcherPID") != pid
                or not _absolute_path(path) or item.get("launcherPath") != path
                or type(seconds) not in (int, float)):
            return refused
        try:
            if not math.isfinite(seconds) or seconds < previous:
                return refused
        except (OverflowError, ValueError):
            return refused
        previous = seconds
    terminal, exit_event = critical[-2:]
    nonce = terminal.get("runNonce")
    try:
        if not isinstance(nonce, str) or str(UUID(nonce)).lower() != nonce.lower():
            return refused
    except ValueError:
        return refused
    end = terminal.get("presentation")
    if not isinstance(end, str) or end not in _ENDS:
        return refused
    outcome, code, status, startup_status = _ENDS[end]
    if (type(returncode) is not int or returncode != code or type(exit_event.get("exitCode")) is not int
            or exit_event["exitCode"] != code or exit_event.get("outcome") != outcome
            or terminal.get("outcome") != outcome or exit_event.get("runNonce") != nonce
            or terminal.get("visualContinuity") != "not-measured"):
        return refused
    opened = [item for item in critical if item["event"] == "target-opened"]
    installed = [item for item in critical if item["event"] == "startup-installed"]
    if len(opened) > 1:
        return refused
    target = opened[0].get("targetPID") if opened else None
    if (opened and not _positive(target) or "targetPID" not in terminal or "targetPID" not in exit_event
            or terminal["targetPID"] != target or exit_event["targetPID"] != target):
        return refused
    if target is not None and (not _positive(terminal["targetPID"]) or not _positive(exit_event["targetPID"])):
        return refused
    if installed and (not opened or names.index("target-opened") > names.index("startup-installed")):
        return refused
    for item in installed:
        if (not _positive(item.get("targetPID")) or item.get("targetPID") != target or not _positive(item.get("runId"))
                or not isinstance(item.get("pageTargetID"), str) or not item["pageTargetID"]):
            return refused
    cover = terminal.get("cover")
    if (not isinstance(cover, dict) or cover.get("runNonce") != nonce
            or type(cover.get("drawCommitted")) is not bool
            or type(terminal.get("coverDrawCommitted")) is not bool
            or cover["drawCommitted"] != terminal["coverDrawCommitted"]):
        return refused
    workspace = terminal.get("workspace")
    page = terminal.get("pageTargetID")
    if "pageTargetID" not in terminal or page is not None and (not isinstance(page, str) or not page):
        return refused
    if ("workspace" not in terminal or type(terminal.get("workspaceObserved")) is not bool
            or terminal["workspaceObserved"] != isinstance(workspace, dict)
            or workspace is not None and not isinstance(workspace, dict)):
        return refused
    if workspace is not None:
        disposition = workspace.get("wallpaperDisposition")
        if (workspace.get("runNonce") != nonce or not _positive(workspace.get("runId"))
                or not isinstance(terminal.get("pageTargetID"), str) or not terminal["pageTargetID"]
                or workspace.get("pageTargetID") != terminal["pageTargetID"]
                or installed and (workspace["runId"] != installed[-1]["runId"]
                    or workspace.get("pageTargetID") != installed[-1]["pageTargetID"])
                or not isinstance(disposition, str) or disposition not in {"applied", "disabled", "degraded"}
                or not isinstance(workspace.get("wallpaperReason"), str)
                or disposition == "applied" and workspace["wallpaperReason"] != ""
                or disposition == "disabled" and workspace["wallpaperReason"] != "disabled"
                or disposition == "degraded" and workspace["wallpaperReason"] not in {
                    "wallpaper-unsupported", "storage-unavailable", "owner-conflict"}
                or not opened or not cover["drawCommitted"]):
            return refused
    if end == "completed" and (not cover["drawCommitted"] or workspace is None or not opened):
        return refused
    reason = terminal.get("reason")
    if (end in {"completed", "skipped"} and reason is not None
            or end == "interrupted" and reason != "startup-interrupted"
            or end == "failed" and (not isinstance(reason, str) or not reason)):
        return refused
    startup = {"status": startup_status, "presentation": "native", "runNonce": nonce,
        "injection": "installed" if installed or workspace is not None else "not-confirmed",
        "installed": bool(installed) or workspace is not None,
        "cover": cover, "workspace": workspace, "visualContinuity": "not-measured"}
    if reason is not None:
        startup["reason"] = reason
    return {"status": status, "startup": startup}
