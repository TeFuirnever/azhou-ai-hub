"""Preauth metadata gate, not full R05 or continuous/all-process isolation.

No spawn, HTTP, CDP, auth, or arbitrary-PID signal API. The caller retains a genuine
Popen child and owns its binary stdout/stderr files. No raw logs are read here.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import ipaddress
import hashlib
import os
import re
import signal
import stat
import subprocess
import threading
import time

WORKTREE = Path(__file__).resolve().parents[2]
SCOPE = "preauth-local-not-R05-complete"


@dataclass(frozen=True)
class GateExpectation:
    ownrun: Path
    pid: int
    birth: str
    exe: Path
    port: int
    browser_path: str = None


class GateStop(Exception):
    def __init__(self, reason, pending=False):
        self.reason, self.pending = reason, pending


def _result(status, reason, **facts):
    return {"scope": SCOPE, "status": status, "reason": reason,
            "R05_complete": False, "visual_confirmed": False, **facts}


def validate_declarations(expected, receipt, session_dir):
    """Pure role/schema checks, before metadata callbacks or filesystem opens."""
    if not isinstance(expected, GateExpectation):
        return _result("refused", "invalid-expectation")
    run, exe = expected.ownrun, expected.exe
    if (not isinstance(run, Path) or not isinstance(exe, Path)
            or not run.is_absolute() or ".." in run.parts or not exe.is_absolute()
            or ".." in exe.parts or run == WORKTREE / ".scratch"
            or not run.is_relative_to(WORKTREE / ".scratch")
            or type(expected.pid) is not int or expected.pid <= 0
            or type(expected.port) is not int or not 1 <= expected.port <= 65535
            or not isinstance(expected.birth, str) or not expected.birth
            or (expected.browser_path is not None and (not isinstance(expected.browser_path, str)
                or re.fullmatch(r"/devtools/browser/[A-Za-z0-9_-]+", expected.browser_path) is None))):
        return _result("refused", "invalid-expectation")
    if not isinstance(session_dir, Path) or session_dir != run / "electron-session":
        return _result("refused", "session-outside-own-run")
    if not isinstance(receipt, dict) or not isinstance(receipt.get("profile_paths"), dict):
        return _result("refused", "launch-declaration-mismatch")
    argv = receipt.get("argv")
    if (type(receipt.get("pid")) is not int or receipt["pid"] != expected.pid
            or type(receipt.get("port")) is not int or receipt["port"] != expected.port
            or receipt.get("started_lstart") != expected.birth or receipt.get("run") != str(run)
            or not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv)
            or argv[0] != str(exe)
            or [a for a in argv if a.startswith("--remote-debugging-port")] != ["--remote-debugging-port=" + str(expected.port)]
            or receipt["profile_paths"].get("ZCODE_DESKTOP_SESSION_DATA_DIR") != str(session_dir)):
        return _result("refused", "launch-declaration-mismatch")
    return None


def bounded_dtap(expected, session_dir):
    """Read only the exact DTAP through a fixed .scratch dirfd, no alias traversal.

    The worktree/.scratch anchor belongs to the trusted supervisor. This does not
    defend against a same-UID adversary replacing the entire worktree/anchor.
    """
    run, session = expected.ownrun, session_dir
    if (not isinstance(run, Path) or not isinstance(session, Path) or not run.is_absolute()
            or ".." in run.parts or run == WORKTREE / ".scratch"
            or not run.is_relative_to(WORKTREE / ".scratch") or session != run / "electron-session"):
        raise GateStop("session-outside-own-run")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    handles, links, fd = [], [], None
    try:
        anchor = os.open(WORKTREE / ".scratch", flags)
        handles.append(anchor)
        parent = anchor
        parts = (*run.relative_to(WORKTREE / ".scratch").parts, "electron-session")
        for index, name in enumerate(parts):
            directory = os.open(name, flags, dir_fd=parent)
            handles.append(directory)
            links.append((parent, name, directory))
            info = os.fstat(directory)
            if info.st_uid != os.getuid() or (index >= len(parts) - 2 and stat.S_IMODE(info.st_mode) != 0o700):
                raise GateStop("session-not-private-owned")
            parent = directory
        fd = os.open("DevToolsActivePort", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_uid != os.getuid() or not 0 <= before.st_size <= 4096):
            raise GateStop("dtap-not-small-singlelink-regular")
        data = bytearray()
        while len(data) <= 4096:
            part = os.read(fd, 4097 - len(data))
            if not part:
                break
            data.extend(part)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_nlink,
                              s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        named = os.stat("DevToolsActivePort", dir_fd=parent, follow_symlinks=False)
        if (len(data) != before.st_size or len(data) > 4096
                or identity(before) != identity(os.fstat(fd)) or identity(before) != identity(named)):
            raise GateStop("dtap-changed")
        for base, name, directory in links:
            named, held = os.stat(name, dir_fd=base, follow_symlinks=False), os.fstat(directory)
            if not stat.S_ISDIR(named.st_mode) or (named.st_dev, named.st_ino) != (held.st_dev, held.st_ino):
                raise GateStop("session-directory-changed")
    except FileNotFoundError:
        raise GateStop("dtap-pending", True)
    except OSError:
        raise GateStop("dtap-unavailable")
    finally:
        for handle in ([fd] if fd is not None else []) + list(reversed(handles)):
            os.close(handle)
    try:
        lines = bytes(data).decode("ascii").splitlines()
    except UnicodeError:
        raise GateStop("dtap-invalid")
    if (len(lines) != 2 or re.fullmatch(r"[0-9]{1,5}", lines[0]) is None
            or not 1 <= int(lines[0]) <= 65535
            or re.fullmatch(r"/devtools/browser/[A-Za-z0-9_-]+", lines[1]) is None):
        raise GateStop("dtap-invalid")
    return {"port": int(lines[0]), "browser_path": lines[1]}


def classify_snapshot(expected, receipt, dtap, snapshot):
    invalid = validate_declarations(expected, receipt, expected.ownrun / "electron-session") if isinstance(expected, GateExpectation) and isinstance(expected.ownrun, Path) else _result("refused", "invalid-expectation")
    if invalid:
        return invalid
    if (not isinstance(dtap, dict) or type(dtap.get("port")) is not int or dtap["port"] != expected.port
            or not isinstance(dtap.get("browser_path"), str)
            or re.fullmatch(r"/devtools/browser/[A-Za-z0-9_-]+", dtap["browser_path"]) is None
            or (expected.browser_path is not None and dtap["browser_path"] != expected.browser_path)):
        return _result("refused", "dual-declaration-mismatch")
    if (not isinstance(snapshot, dict) or type(snapshot.get("exit")) is not int
            or snapshot["exit"] not in (0, 1) or not isinstance(snapshot.get("records"), list)
            or (snapshot["exit"] != 0 and snapshot["records"])):
        return _result("refused", "listener-snapshot-invalid")
    ports = []
    for record in snapshot["records"]:
        if not isinstance(record, dict) or type(record.get("pid")) is not int or record["pid"] != expected.pid:
            return _result("refused", "listener-foreign-pid")
        address, port = record.get("address"), record.get("port")
        if not isinstance(address, str) or type(port) is not int or not 1 <= port <= 65535:
            return _result("refused", "listener-snapshot-invalid")
        try:
            if "%" in address or not ipaddress.ip_address(address).is_loopback:
                return _result("refused", "listener-not-literal-loopback")
        except ValueError:
            return _result("refused", "listener-not-literal-loopback")
        ports.append(port)
    if expected.port not in ports:
        return _result("pending", "expected-listener-pending", observed_loopback_ports=sorted(set(ports)))
    return _result("preauth-transport-ready", "owned-loopback-dual-declaration",
                   observed_loopback_ports=sorted(set(ports)), expected_port=expected.port,
                   browser_path=dtap["browser_path"])


def evaluate_gate(expected, receipt, *, session_dir, guard_process, listeners, current=None):
    invalid = validate_declarations(expected, receipt, session_dir)
    if invalid:
        return invalid
    try:
        def identity():
            guard_process(expected.pid, expected.exe, expected.birth)
            if current is not None and current(expected.pid) != {"pid": expected.pid, "birth": expected.birth, "exe": str(expected.exe)}:
                raise ValueError()
        identity()
        dtap = bounded_dtap(expected, session_dir)
        snapshot = listeners(expected.pid)
        identity()
        return classify_snapshot(expected, receipt, dtap, snapshot)
    except GateStop as error:
        allowed = {"session-outside-own-run", "session-not-private-owned", "dtap-not-small-singlelink-regular",
                   "dtap-changed", "session-directory-changed", "dtap-pending", "dtap-unavailable", "dtap-invalid"}
        if error.reason not in allowed:
            return _result("refused", "metadata-backend-unverified")
        return _result("pending" if error.pending and error.reason == "dtap-pending" else "refused", error.reason)
    except Exception:
        return _result("refused", "metadata-backend-unverified")


class OwnedSupervisor:
    """Retained Popen only; native unreaped-child proof precedes every wait/signal.

    Same mechanism as offline_runtime.DirectChildIdentity: single thread, default
    SIGCHLD, native waitid(WNOWAIT). No poll fallback (ECHILD could fabricate 0).
    A competing native reaper/same-UID malicious supervisor is outside this model.
    """
    def __init__(self, child, expected, *, guard_process, listeners, current=None, wrapper_prefix=None, wrapper_policy_sha256=None):
        if (type(child) is not subprocess.Popen or not isinstance(expected, GateExpectation)
                or child.pid != expected.pid or child.returncode is not None
                or not isinstance(child.args, (list, tuple)) or not child.args
                or not all(isinstance(a, str) for a in child.args)):
            raise ValueError("retained live own Popen handle required")
        if wrapper_prefix is None:
            self.wrapper_prefix = []
        else:
            if (not isinstance(wrapper_prefix, (list, tuple)) or len(wrapper_prefix) != 3
                    or list(wrapper_prefix[:2]) != ["/usr/bin/sandbox-exec", "-p"]
                    or not isinstance(wrapper_prefix[2], str)
                    or not wrapper_prefix[2].startswith("(version 1)")
                    or not isinstance(wrapper_policy_sha256, str)
                    or hashlib.sha256(wrapper_prefix[2].encode()).hexdigest() != wrapper_policy_sha256):
                raise ValueError("fixed sandbox-exec -p policy binding required")
            self.wrapper_prefix = list(wrapper_prefix)
        self.child, self.expected = child, expected
        self.pid, self.argv = child.pid, list(child.args)
        self.guard_process, self.listeners, self.current = guard_process, listeners, current
        self.bound_at, self.observed_code = datetime.now(timezone.utc).isoformat(), None

    def _observe(self):
        child = self.child
        if (type(child) is not subprocess.Popen or child.pid != self.pid or list(child.args) != self.argv
                or threading.active_count() != 1 or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL):
            raise ValueError()
        if self.observed_code is not None:
            if child.returncode != self.observed_code:
                raise ValueError()
            return self.observed_code
        if child.returncode is not None or not all(hasattr(os, n) for n in ("waitid", "P_PID", "WEXITED", "WNOHANG", "WNOWAIT")):
            raise ValueError()
        terminal = os.waitid(os.P_PID, self.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if terminal is not None:
            if terminal.si_pid != self.pid:
                raise ValueError()
            self.observed_code = child.wait(timeout=0)
            return self.observed_code
        self.guard_process(self.pid, self.expected.exe, self.expected.birth)
        if self.current is not None and self.current(self.pid) != {"pid": self.pid, "birth": self.expected.birth, "exe": str(self.expected.exe)}:
            raise ValueError()
        return None

    def cleanup(self, reason="gate-refused", timeout=2):
        if reason not in {"gate-refused", "gate-timeout", "child-exited", "test-finished", "operator-stop"} or not 0 < timeout <= 5:
            raise ValueError("fixed cleanup reason and bounded deadline required")
        attempted = False
        try:
            code = self._observe()
            if code is None:
                # Recheck retained handle/kernel relationship immediately before TERM.
                code = self._observe()
                if code is None:
                    attempted = True
                    self.child.terminate()
                    self.observed_code = code = self.child.wait(timeout=timeout)
            return self._completion(code, "terminated-and-waited" if attempted else "already-exited-and-waited", reason, attempted)
        except Exception:
            return self._completion(None, "cleanup_unknown", reason, attempted)

    def _completion(self, code, cleanup, reason, attempted):
        return {"scope": SCOPE, "kind": "C" if code is not None else "E",
                "started_at": self.bound_at, "observed_at": datetime.now(timezone.utc).isoformat(), "argv": self.argv,
                "pid": self.pid, "execution_state": "exit_unknown" if code is None else "signaled" if code < 0 else "exited",
                "exit_code": code, "signal": -code if code is not None and code < 0 else None,
                "cleanup": cleanup, "child_state": "child_exit_unknown" if code is None else "waited",
                "cleanup_reason": reason, "term_attempted": attempted, "wait_observed": code is not None}

    def wait_gate(self, receipt, *, session_dir, timeout=30, interval=0.05):
        if not 0 <= timeout <= 30 or not 0 < interval <= 1:
            raise ValueError("bounded gate deadline required")
        invalid = validate_declarations(self.expected, receipt, session_dir)
        if invalid is None and self.wrapper_prefix + receipt["argv"] != self.argv:
            invalid = _result("refused", "retained-argv-mismatch")
        if invalid:
            return {"gate": invalid, "cleanup": self.cleanup("gate-refused")}
        deadline = time.monotonic() + timeout
        while True:
            try:
                code = self._observe()
            except Exception:
                return {"gate": _result("refused", "ownership-unverified"), "cleanup": self._completion(None, "cleanup_unknown", "gate-refused", False)}
            if code is not None:
                return {"gate": _result("refused", "child-exited-before-ready"), "cleanup": self.cleanup("child-exited")}
            gate = evaluate_gate(self.expected, receipt, session_dir=session_dir,
                                 guard_process=self.guard_process, listeners=self.listeners, current=self.current)
            if gate["status"] == "preauth-transport-ready" and time.monotonic() >= deadline:
                return {"gate": _result("refused", "gate-timeout"), "cleanup": self.cleanup("gate-timeout")}
            if gate["status"] == "preauth-transport-ready":
                return {"gate": gate, "cleanup": None}
            if gate["status"] == "refused":
                return {"gate": gate, "cleanup": self.cleanup("gate-refused")}
            if time.monotonic() >= deadline:
                return {"gate": _result("refused", "gate-timeout"), "cleanup": self.cleanup("gate-timeout")}
            time.sleep(min(interval, max(0, deadline - time.monotonic())))
