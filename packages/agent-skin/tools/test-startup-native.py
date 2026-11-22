#!/usr/bin/env python3
"""Run native fixtures and handshakes, with an explicit owned-window functional gate."""

from __future__ import annotations

import http.server
import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
import os
import tempfile
import threading
import time
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NATIVE_INPUTS = ("Native/App.swift", "Native/Wallpaper.swift", "Native/SkinHostContract.swift",
                 "Native/CodexSkinDriver.swift", "Native/OptionalStartupMedia.swift",
                 "Native/OptionalStartupAVPlayback.swift", "Native/OptionalStartupPresentation.swift",
                 "Native/OptionalStartupVideoResolver.swift", "Native/OptionalStartupVideoFiles.swift",
                 "Native/StartupNativeTests.swift", "Native/OptionalStartupMediaTests.swift",
                 "Native/OptionalStartupAVPlaybackTests.swift", "Native/OptionalStartupVideoResolverTests.swift",
                 "Native/OptionalStartupVideoFilesTests.swift",
                 "tools/test-startup-native.py",
                 "tools/test-native-warning-contract.py")


def source_fingerprint() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in NATIVE_INPUTS}


def validate_window_observations(stdout: str, returncode: int) -> list[dict]:
    if type(returncode) is not int or returncode != 0:
        raise ValueError(f"window probe exited {returncode}")
    rows = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    observations, cleanup = {}, {}
    for row in rows:
        if not isinstance(row, dict) or row.get("schema") != "azhou-cold-window-order.v2" \
                or type(row.get("control")) is not bool:
            raise ValueError("invalid window observation record")
        control = row["control"]
        for key in ("coverWindowID", "hostWindowID"):
            if type(row.get(key)) is not int or row[key] <= 0:
                raise ValueError(f"invalid {key}")
        if row["coverWindowID"] == row["hostWindowID"]:
            raise ValueError("owned windows must have distinct identities")
        if row.get("event") == "cleanup":
            if control in cleanup or any(row.get(key) is not expected for key, expected in (
                    ("coverWindowPresent", False), ("hostWindowPresent", False),
                    ("geometryEmpty", True), ("secondDiscardEmpty", True))):
                raise ValueError("missing or duplicate owned-window teardown")
            expected_hits = {} if control else {
                "opaque": row["coverWindowID"], "transparentBeforeDiscard": row["hostWindowID"],
                "restored": row["coverWindowID"], "afterDiscard": row["hostWindowID"],
            }
            hits = row.get("mouseDownHitTargets")
            if not isinstance(hits, dict) or hits != expected_hits or any(type(hit) is not int for hit in hits.values()):
                raise ValueError("missing or incorrect owned-window mouse-down hit targets")
            cleanup[control] = row
        elif row.get("event") == "observation":
            if type(row.get("revealed")) is not bool:
                raise ValueError("revealed must be boolean")
            pair = (control, row["revealed"])
            if pair in observations:
                raise ValueError("duplicate observation pair")
            for key in ("coverIndex", "hostIndex"):
                if type(row.get(key)) is not int or row[key] < 0:
                    raise ValueError(f"invalid {key}")
            if row["coverIndex"] == row["hostIndex"] or \
                    (row["hostIndex"] < row["coverIndex"]) != control:
                raise ValueError("negative control or production window order regressed")
            for key in ("foregroundPIDBefore", "foregroundPID", "probePID"):
                if type(row.get(key)) is not int or row[key] <= 0:
                    raise ValueError(f"unavailable {key}")
            if type(row.get("coverLevel")) is not int or row["coverLevel"] != (0 if control else 3) \
                    or type(row.get("hostLevel")) is not int or row["hostLevel"] != 0:
                raise ValueError("actual window levels do not match normal control or floating cover")
            if row.get("applicationActiveBeforeHostOrder") is not False or row.get("applicationActive") is not False:
                raise ValueError("window probe must remain inactive")
            if row["foregroundPID"] != row["foregroundPIDBefore"]:
                raise ValueError("probe changed foreground application")
            if not isinstance(row.get("webViewID"), str) or not row["webViewID"] \
                    or type(row.get("webViewCount")) is not int or row["webViewCount"] != 1:
                raise ValueError("missing real WKWebView identity")
            expected_flags = {"webViewMounted": True, "webViewHidden": not row["revealed"],
                              "coverPresent": not row["revealed"], "coverIsKey": False,
                              "canJoinAllSpaces": False, "moveToActiveSpace": False}
            if any(row.get(key) is not expected for key, expected in expected_flags.items()):
                raise ValueError("reveal hierarchy, activation or Space behavior regressed")
            observations[pair] = row
        else:
            raise ValueError("unknown window observation event")
    if set(observations) != {(control, revealed) for control in (False, True) for revealed in (False, True)} \
            or set(cleanup) != {False, True}:
        raise ValueError("requires four observations and two cleanup records")
    for control in (False, True):
        before, after = (observations[(control, revealed)] for revealed in (False, True))
        if any(before[key] != after[key] for key in ("coverWindowID", "hostWindowID", "webViewID")) \
                or any(cleanup[control][key] != before[key] for key in ("coverWindowID", "hostWindowID")):
            raise ValueError("owned window or WKWebView identity changed")
    if len({row["foregroundPID"] for row in observations.values()}) != 1 \
            or len({row["probePID"] for row in observations.values()}) != 1:
        raise ValueError("foreground or probe identity drifted")
    return rows


def _ordering_attempt(output: Path, evidence: Path, source_before: dict, binary_before: str) -> tuple[dict, str, str]:
    command = [str(output), "--probe-cold-window-ordering"]
    report = {"kind": "synthetic-owned-window-ordering", "unitCoverageInput": False,
              "scope": "owned-window ordering and mouse-down target queries with a synthetic same-process host",
              "visualContinuity": "not-measured", "passed": False, "command": command,
              "startedAt": datetime.now(timezone.utc).isoformat(),
              "sourceBefore": source_before, "binaryBefore": binary_before}
    stdout, stderr = "", ""
    try:
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False, timeout=25)
        stdout, stderr = run.stdout, run.stderr
        report["returncode"] = run.returncode
        report["observations"] = validate_window_observations(stdout, run.returncode)
        report["passed"] = True
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        if isinstance(error, subprocess.TimeoutExpired):
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            stdout = stdout.decode(errors="replace") if isinstance(stdout, bytes) else stdout
            stderr = stderr.decode(errors="replace") if isinstance(stderr, bytes) else stderr
        report["error"] = str(error)
    finally:
        try:
            report["sourceAfter"] = source_fingerprint()
            report["binaryAfter"] = hashlib.sha256(output.read_bytes()).hexdigest()
            if report["sourceAfter"] != source_before or report["binaryAfter"] != binary_before:
                raise ValueError("native source or binary changed during verification")
        except (OSError, ValueError) as error:
            report.update(passed=False, error=str(error), integrityViolation=True)
        report["finishedAt"] = datetime.now(timezone.utc).isoformat()
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "stdout.jsonl").write_text(stdout, encoding="utf-8")
        (evidence / "stderr.log").write_text(stderr, encoding="utf-8")
        (evidence / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report, stdout, stderr


def window_ordering_checks(output: Path, out: Path, source_before: dict, binary_before: str) -> int:
    # The probe's assertions are timing-sensitive (WindowServer teardown latency,
    # WebKit layer windows on headless runners): one crashed run is not a verdict.
    # A signal death gets exactly one re-run on a fresh probe process after a
    # settle delay; both attempts stay in evidence and a real regression fails
    # both attempts.
    retry_evidence = out.with_name(out.name + "-attempt1")
    if os.path.lexists(retry_evidence):
        print(f"FAILED: retry evidence path already exists: {retry_evidence}", file=sys.stderr)
        return 1
    report, stdout, stderr = _ordering_attempt(output, out, source_before, binary_before)
    if not report["passed"] and not report.get("integrityViolation") \
            and report.get("returncode") is not None and report["returncode"] < 0:
        first = {"passed": report["passed"], "returncode": report["returncode"], "error": report.get("error")}
        time.sleep(5)
        retry_evidence = out.with_name(out.name + "-attempt1")
        retry_evidence.mkdir(parents=True, exist_ok=True)
        for item in out.iterdir():
            item.rename(retry_evidence / item.name)
        report, stdout, stderr = _ordering_attempt(output, out, source_before, binary_before)
        report["attempts"] = [first, {"passed": report["passed"], "returncode": report.get("returncode"),
                                      "error": report.get("error")}]
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Owned-window ordering evidence: {out} (passed={report['passed']})", flush=True)
    return 0 if report["passed"] else 1


def handshake_checks(output: Path) -> None:
    """The real Foundation WebSocket client must preserve handshake distinctions."""
    class HandshakeHandler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            status = int(self.path.rsplit("/", 1)[-1])
            if status not in (404, 500, 401, 503) or self.headers.get("Upgrade", "").lower() != "websocket":
                status = 400
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

        def log_message(self, format: str, *args: object) -> None:
            pass

    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), HandshakeHandler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for status, candidate in ((404, True), (500, True), (401, False), (503, False)):
                endpoint = f"ws://127.0.0.1:{server.server_port}/devtools/page/{status}"
                run = subprocess.run([str(output), "--probe-startup-handshake", endpoint],
                                     cwd=ROOT, check=True, capture_output=True, text=True, timeout=8)
                result = json.loads(run.stdout)
                assert result == {"candidate": candidate, "reason": "protocol-error", "host": False,
                                  "errorDomain": "NSURLErrorDomain", "errorCode": -1011,
                                  "httpStatus": status}, (status, result)
                print(f"Real URLSession handshake {status}: candidate={candidate}", flush=True)
        finally:
            server.shutdown()
            thread.join(timeout=2)


def theme_bridge_checks(output: Path) -> int:
    """Exercise the production source/Native/player boundary without graphics or real hosts."""
    with tempfile.TemporaryDirectory(prefix="azhou-theme-bridge-") as temporary:
        root = Path(temporary).resolve()
        environment = dict(os.environ,
            AZHOU_THEME_BRIDGE_INPUT=str(root / "bundled-input.json"),
            AZHOU_THEME_BRIDGE_OUTPUT=str(root / "bundled-output.json"),
            AZHOU_THEME_BRIDGE_KIND="bundled")
        environment.pop("NODE_TEST_CONTEXT", None)
        print("==> production theme bridge: bundled", flush=True)
        prepared = subprocess.run(["node", "--test", "--test-name-pattern=native theme bridge prepares",
            "tools/image-settings.test.mjs"], cwd=ROOT, env=environment, check=False)
        if prepared.returncode:
            return prepared.returncode
        tested = subprocess.run([str(output)], cwd=ROOT, env=environment, check=False)
        if tested.returncode:
            return tested.returncode
        consumed = subprocess.run(["node", "--test", "--test-name-pattern=native theme bridge consumes",
            "tools/animation.unit.test.mjs"], cwd=ROOT, env=environment, check=False)
        if consumed.returncode:
            return consumed.returncode

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-ordering", action="store_true", help="require the real owned-window functional probe")
    parser.add_argument("--out", type=Path, help="fresh functional evidence directory")
    args = parser.parse_args()
    if args.window_ordering != (args.out is not None):
        parser.error("--window-ordering and --out must be supplied together")
    if args.out:
        # mkdir rejects existing directories and dangling symlinks before any child runs.
        args.out = args.out.absolute()
        args.out.mkdir(parents=True, exist_ok=False)
    if sys.platform != "darwin":
        if args.window_ordering:
            print("FAILED: requested window ordering requires macOS and an active graphical desktop", file=sys.stderr)
            return 1
        print("SKIPPED: native startup protocol tests require macOS and AppKit")
        return 0

    warning_contract = subprocess.run([sys.executable, "-B", str(ROOT / "tools/test-native-warning-contract.py")], check=False)
    if warning_contract.returncode:
        return warning_contract.returncode

    source_before = source_fingerprint() if args.window_ordering else None
    output = ROOT / ".build/startup-native-tests"
    output.parent.mkdir(parents=True, exist_ok=True)
    target = f"{platform.machine()}-apple-macos13.0"
    command = [
        "xcrun", "--sdk", "macosx", "swiftc", "-DAGENT_SKIN_NATIVE_EVENT_TESTS", "-target", target,
        "Native/App.swift", "Native/Wallpaper.swift", "Native/SkinHostContract.swift",
        "Native/CodexSkinDriver.swift", "Native/OptionalStartupMedia.swift",
        "Native/OptionalStartupAVPlayback.swift", "Native/OptionalStartupPresentation.swift",
        "Native/OptionalStartupVideoResolver.swift", "Native/OptionalStartupVideoFiles.swift",
        "Native/StartupNativeTests.swift", "Native/OptionalStartupMediaTests.swift",
        "Native/OptionalStartupAVPlaybackTests.swift", "Native/OptionalStartupVideoResolverTests.swift",
        "Native/OptionalStartupVideoFilesTests.swift",
        "-o", str(output), "-framework", "AppKit", "-framework", "WebKit",
    ]
    print("==> " + " ".join(command), flush=True)
    compiled = subprocess.run(command, cwd=ROOT, check=False)
    if compiled.returncode:
        return compiled.returncode
    binary_before = hashlib.sha256(output.read_bytes()).hexdigest() if args.window_ordering else None
    bridge_result = theme_bridge_checks(output)
    if bridge_result:
        return bridge_result


    handshake_checks(output)

    emitted = subprocess.run(
        [str(output), "--emit-helper-expressions"], cwd=ROOT,
        check=False, capture_output=True, text=True,
    )
    if emitted.returncode:
        print(emitted.stderr, file=sys.stderr, end="")
        return emitted.returncode
    try:
        expressions = json.loads(emitted.stdout)
        expected = {"statusSource", "applyGuardSource", "retrySource", "restoreSource"}
        if set(expressions) != expected or not all(isinstance(expressions[key], str) and expressions[key] for key in expected):
            raise ValueError("native helper expression output has an unexpected shape")
    except (ValueError, TypeError) as error:
        print(f"FAILED: native helper expression output is invalid: {error}", file=sys.stderr)
        return 1
    receipt = ROOT / ".build/startup-helper-expressions.json"
    receipt.write_text(json.dumps(expressions, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Native helper expressions emitted for isolated browser checks: {receipt}")
    if args.window_ordering:
        return window_ordering_checks(output, args.out, source_before, binary_before)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
