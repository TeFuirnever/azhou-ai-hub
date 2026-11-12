#!/usr/bin/env python3
"""Run native protocol fixtures and real loopback WebSocket handshake regressions."""

from __future__ import annotations

import http.server
import json
import platform
import threading
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]



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


def main() -> int:
    if sys.platform != "darwin":
        print("SKIPPED: native startup protocol tests require macOS and AppKit")
        return 0

    output = ROOT / ".build/startup-native-tests"
    output.parent.mkdir(parents=True, exist_ok=True)
    target = f"{platform.machine()}-apple-macos13.0"
    command = [
        "xcrun", "--sdk", "macosx", "swiftc", "-DAGENT_SKIN_NATIVE_EVENT_TESTS", "-target", target,
        "Native/App.swift", "Native/Wallpaper.swift", "Native/SkinHostContract.swift",
        "Native/CodexSkinDriver.swift", "Native/StartupNativeTests.swift",
        "-o", str(output), "-framework", "AppKit", "-framework", "WebKit",
    ]
    print("==> " + " ".join(command), flush=True)
    compiled = subprocess.run(command, cwd=ROOT, check=False)
    if compiled.returncode:
        return compiled.returncode
    tested = subprocess.run([str(output)], cwd=ROOT, check=False)
    if tested.returncode:
        return tested.returncode

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
