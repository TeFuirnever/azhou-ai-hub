"""Read the same CDP identity as the P07 collector, from an owned Chrome."""
import argparse
from contextlib import contextmanager
from http.client import HTTPConnection, HTTPException
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

FLAGS = (
    "--headless=new", "--no-first-run", "--no-default-browser-check",
    "--disable-background-networking", "--disable-default-apps", "--disable-sync",
    "--disable-extensions", "--disable-component-update", "--no-pings",
    "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
)
MARKER = re.compile(r"([1-9][0-9]{0,4})\r?\n(/devtools/browser/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\r?\n?", re.ASCII)
BROWSER = re.compile(r"Chrome/[0-9]+(?:\.[0-9]+){3}", re.ASCII)
PROTOCOL = re.compile(r"[0-9]+\.[0-9]+", re.ASCII)


class ProbeError(Exception):
    pass


def read_port_marker(path):
    with path.open("rb") as marker:
        data = marker.read(257)
    if len(data) > 256:
        raise ProbeError("oversized DevToolsActivePort")
    match = MARKER.fullmatch(data.decode("ascii", errors="replace"))
    if not match or not 1 <= int(match[1]) <= 65535:
        raise ProbeError("invalid or incomplete DevToolsActivePort")
    return int(match[1]), match[2]


@contextmanager
def http_wall_timeout(seconds):
    # CLI is single-threaded on macOS/Linux. A socket timeout alone can be
    # extended by a partial response arriving a byte at a time.
    def timed_out(_signal, _frame):
        raise TimeoutError("identity HTTP request exceeded its deadline")

    old_handler = signal.signal(signal.SIGALRM, timed_out)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def read_identity(port, token, timeout):
    connection = HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        with http_wall_timeout(timeout):
            connection.request("GET", "/json/version")
            response = connection.getresponse()
            if response.status != 200:
                raise ProbeError("unexpected HTTP status from /json/version")
            if not response.headers.get("Content-Type", "").startswith("application/json"):
                raise ProbeError("unexpected Content-Type from /json/version")
            body = response.read(16385)
    finally:
        connection.close()
    if len(body) > 16384:
        raise ProbeError("oversized /json/version")
    try:
        identity = json.loads(body)
    except (ValueError, UnicodeError):
        raise ProbeError("invalid JSON from /json/version") from None
    if not isinstance(identity, dict):
        raise ProbeError("unexpected /json/version shape")
    browser = identity.get("Browser")
    protocol = identity.get("Protocol-Version")
    if not isinstance(browser, str) or not BROWSER.fullmatch(browser):
        raise ProbeError("missing or invalid Chrome Browser value")
    if not isinstance(protocol, str) or not PROTOCOL.fullmatch(protocol):
        raise ProbeError("missing or invalid Protocol-Version")
    if identity.get("webSocketDebuggerUrl") != f"ws://127.0.0.1:{port}{token}":
        raise ProbeError("/json/version is not bound to the owned browser")
    return {"browser": browser, "protocolVersion": protocol}


def stop_owned(process):
    # Popen made a fresh process group. Never inspect or terminate other Chrome.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        if sig == signal.SIGTERM:
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
    process.wait(timeout=3)


def stderr_category(stream):
    stream.seek(0)
    lower = stream.read(4096).lower()
    if any(term in lower for term in (b"namespace", b"no usable sandbox", b"zygote")):
        return "sandbox-or-namespace"
    if b"devtools listening" in lower:
        return "devtools-listening"
    return "browser-stderr-present" if lower else "browser-stderr-empty"


def probe(executable, seconds):
    with tempfile.TemporaryDirectory(prefix="p07-chrome-identity-") as work:
        profile = Path(work) / "profile"
        profile.mkdir(mode=0o700)
        with tempfile.TemporaryFile() as stderr:
            try:
                chrome = subprocess.Popen(
                    [str(executable), *FLAGS, f"--user-data-dir={profile}",
                     "--window-size=1512,889", "about:blank"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=stderr, start_new_session=True,
                )
            except OSError as error:
                raise ProbeError(f"cannot launch isolated Chrome (errno={error.errno})") from None
            try:
                deadline = time.monotonic() + seconds
                stage = "waiting for DevToolsActivePort"
                while (remaining := deadline - time.monotonic()) > 0:
                    if chrome.poll() is not None:
                        raise ProbeError(f"isolated Chrome exited (status={chrome.returncode})")
                    try:
                        port, token = read_port_marker(profile / "DevToolsActivePort")
                    except (FileNotFoundError, ProbeError) as marker_error:
                        if isinstance(marker_error, ProbeError):
                            stage = str(marker_error)
                        time.sleep(min(0.05, remaining))
                        continue
                    stage = "waiting for /json/version"
                    try:
                        return read_identity(port, token, min(remaining, 1.0))
                    except (OSError, HTTPException):
                        time.sleep(min(0.05, max(0, deadline - time.monotonic())))
                raise ProbeError(f"timed out: {stage}")
            except ProbeError as error:
                raise ProbeError(f"{error}; stderr_category={stderr_category(stderr)}") from None
            finally:
                stop_owned(chrome)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chrome", type=Path, help="explicit Chrome executable")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    if not 0 < args.timeout <= 30:
        parser.error("--timeout must be within (0, 30]")
    if not args.chrome.is_absolute():
        parser.error("Chrome executable must be an absolute path")
    try:
        print(json.dumps(probe(args.chrome, args.timeout), sort_keys=True))
    except (ProbeError, subprocess.TimeoutExpired) as error:
        message = "owned Chrome did not terminate" if isinstance(error, subprocess.TimeoutExpired) else str(error)
        print(f"Chrome CDP identity failed: {message}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
