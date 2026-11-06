"""Offline-only command evidence and supervision; never launches a user App."""
from __future__ import annotations
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone

_DEFAULT_SCOPE = None


class Scope:
    """An explicit file boundary, not a security sandbox or a live lease proof."""
    def __init__(self, root):
        self.root = Path(root)
        if (not self.root.is_absolute() or self.root.resolve() != self.root
                or not self.root.is_dir() or self.root.stat().st_uid != os.getuid()):
            raise ValueError("scope requires an existing canonical owned root")

    def own(self, path):
        path = Path(path)
        if (not path.is_absolute() or not path.is_relative_to(self.root)
                or path.resolve() != path):
            raise ValueError("path outside exclusive recovery directory")
        for parent in [path, *path.parents]:
            if parent == self.root.parent:
                break
            if parent.is_symlink():
                raise ValueError("symlink in recovery path")
        return path

    def write_new(self, path, data):
        return write_new(path, data, root=self.root)

    def json_new(self, path, value):
        return json_new(path, value, root=self.root)


def configure_scope(root):
    """Legacy single-scope callers only; concurrent callers must pass root explicitly."""
    global _DEFAULT_SCOPE
    _DEFAULT_SCOPE = Scope(root)
    return _DEFAULT_SCOPE


def scope_root(root=None):
    if root is not None:
        return Scope(root).root
    if _DEFAULT_SCOPE is None:
        raise ValueError("an explicit recovery scope is required")
    return _DEFAULT_SCOPE.root


IDENTITY_UNAVAILABLE = False
MODES = {"bytes", "exit37", "hold", "ignore-term", "artifact", "partial"}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def own(path, *, root=None):
    return Scope(scope_root(root)).own(path)


def write_new(path, data, *, root=None):
    path = own(path, root=root)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        while view:
            n = os.write(fd, view)
            if n <= 0:
                raise OSError("short write")
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)


def json_new(path, value, *, root=None):
    write_new(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode(), root=root)


def validate_result(result):
    state, code = result["execution_state"], result["exit_code"]
    if state not in {"exited", "signaled", "timed_out", "not_started", "exit_unknown"}:
        raise ValueError("unrecognized execution state")
    if result.get("kind") != ("C" if code is not None else "E"):
        raise ValueError("only an observed wait result is a completion receipt")
    when = datetime.fromisoformat(result["observed_at"].replace("Z", "+00:00"))
    if when.utcoffset() is None or when.utcoffset().total_seconds() != 0:
        raise ValueError("UTC observed_at required")
    if not isinstance(result.get("argv"), list) or not all(isinstance(x, str) for x in result["argv"]):
        raise ValueError("argv must preserve actual string arguments")
    if code is not None and (isinstance(code, bool) or not isinstance(code, int)):
        raise ValueError("exit code must be an actual integer or null")
    actual_signal = result.get("signal")
    expected_signal = -code if code is not None and code < 0 else None
    if (type(actual_signal) is not type(expected_signal) or actual_signal != expected_signal):
        raise ValueError("signal must match the actual wait result for every state")
    if state == "exited" and code is not None and code < 0:
        raise ValueError("negative native return code must retain signal semantics")
    if state in {"exited", "signaled"} and code is None:
        raise ValueError("completed command requires an observed wait result")
    if state == "signaled" and (code >= 0 or result["signal"] != -code):
        raise ValueError("signal must preserve native Python wait semantics")
    if state in {"not_started", "exit_unknown"} and code is not None:
        raise ValueError("unknown execution cannot invent a wait result")
    if not result.get("argv") or not result.get("observed_at"):
        raise ValueError("actual argv and UTC required")
    return result


class Journal:
    def __init__(self, path, argv, command_id, *, root=None):
        self.path, self.argv, self.command_id = own(path, root=root), list(argv), command_id
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)

    def emit(self, event, **fields):
        if set(fields) & {"kind", "observed_at", "command_id", "argv", "exit_code", "event"}:
            raise ValueError("event fields cannot override receipt identity")
        value = {"kind": "E", "observed_at": utc(), "command_id": self.command_id,
                 "argv": self.argv, "exit_code": None, "event": event, **fields}
        view = memoryview((json.dumps(value, sort_keys=True) + "\n").encode())
        while view:
            n = os.write(self.fd, view)
            if n <= 0:
                raise OSError("journal short write")
            view = view[n:]
        os.fsync(self.fd)

    def close(self):
        os.close(self.fd)


class DirectChildIdentity:
    """Only this supervisor's unreaped synthetic Python child, never a host PID."""
    def __init__(self, expected_override=None):
        self.expected_override = expected_override
        self.unavailable = False
        self.lib = None
        self.expected = None

    def path(self, pid):
        global IDENTITY_UNAVAILABLE
        if self.unavailable or IDENTITY_UNAVAILABLE:
            raise PermissionError("identity interface previously unavailable; no retry")
        try:
            if self.lib is None:
                self.lib = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
                self.lib.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
                self.lib.proc_pidpath.restype = ctypes.c_int
            buf = ctypes.create_string_buffer(4096)
            if self.lib.proc_pidpath(pid, buf, len(buf)) <= 0:
                raise PermissionError(ctypes.get_errno(), "proc_pidpath unavailable")
            return str(Path(os.fsdecode(buf.value)).resolve())
        except (OSError, AttributeError):
            self.unavailable = True
            IDENTITY_UNAVAILABLE = True
            raise

    def verify(self, child):
        if threading.active_count() != 1 or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
            return False
        if child.returncode is not None:
            return False
        if not all(hasattr(os, x) for x in ("waitid", "P_PID", "WEXITED", "WNOHANG", "WNOWAIT")):
            return False
        observed = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if observed is not None:
            child.wait(timeout=0)
            return False
        if self.expected is None:
            self.expected = self.expected_override or self.path(os.getpid())
        return self.path(child.pid) == self.expected


class SupervisorSignal(BaseException):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(signal.Signals(signum).name)


class Recorder:
    def __init__(self, directory, fixture, identity=None, *, root, owner_thread):
        self.root = scope_root(root)
        self.directory = own(directory, root=self.root)
        self.fixture = own(fixture, root=self.root)
        if self.fixture != self.root / "tests/child_fixture.py":
            raise ValueError("only the registered test child is executable")
        if (not isinstance(owner_thread, str) or not owner_thread
                or json.loads((self.root / "OWNERSHIP.json").read_text())["thread_id"] != owner_thread):
            raise ValueError("wrong recovery owner declaration")
        self.fixture_sha = sha(self.fixture)
        self.identity = identity or DirectChildIdentity()

    def run(self, label, mode, timeout=1.0, handoff=None):
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("supervisor requires main thread")
        previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
        if (previous[signal.SIGINT] != signal.default_int_handler
                or any(previous[sig] != signal.SIG_DFL for sig in (signal.SIGTERM, signal.SIGHUP))):
            raise ValueError("existing signal handlers require review")
        installed = []
        first_signal = None
        def signal_received(signum, frame):
            nonlocal first_signal
            if first_signal is not None:
                return
            # Latch before raising: another signal during exception handling cannot escape.
            first_signal = signum
            raise SupervisorSignal(signum)
        try:
            for sig in previous:
                signal.signal(sig, signal_received)
                installed.append(sig)
            return self._run(label, mode, timeout, handoff)
        finally:
            for sig in reversed(installed):
                signal.signal(sig, previous[sig])

    def _run(self, label, mode, timeout=1.0, handoff=None):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,60}", label) or mode not in MODES:
            raise ValueError("only registered synthetic fixture modes may run")
        if sha(self.fixture) != self.fixture_sha:
            raise ValueError("synthetic fixture changed")
        case = self.directory / label
        case.mkdir(mode=0o700)
        argv = [sys.executable, "-B", str(self.fixture), mode]
        cid, nonce = str(uuid.uuid4()), str(uuid.uuid4())
        journal = Journal(case / "events.jsonl", argv, cid, root=self.root)
        evidence_errors = []
        def emit(event, **fields):
            try:
                journal.emit(event, **fields)
            except Exception as exc:
                evidence_errors.append({"event": event, "type": type(exc).__name__, "message": str(exc)})
        child = None
        code = None
        error = None
        state = "not_started"
        cleanup = "not_needed"
        identity_state = "not_checked"
        timed_out = False
        started_at = utc()
        stdout_path, stderr_path = case / "stdout.raw", case / "stderr.raw"
        outfd = errfd = None
        try:
            for name in ("home", "tmp"):
                (case / name).mkdir(mode=0o700)
            outfd = os.open(stdout_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            errfd = os.open(stderr_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            emit("spawn_intent", cleanup_owner="supervisor", nonce=nonce)
            env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "LC_CTYPE") if k in os.environ}
            env.update(HOME=str(case / "home"), TMPDIR=str(case / "tmp"),
                       RECOVERY_CASE=str(case), RECOVERY_NONCE=nonce, PYTHONDONTWRITEBYTECODE="1")
            child = subprocess.Popen(argv, cwd=case, env=env, stdout=outfd, stderr=errfd,
                                     close_fds=True, start_new_session=True)
            state = "running"
            emit("spawned_unverified", pid=child.pid)
            if mode in {"hold", "ignore-term"}:
                ready_path = case / "ready.json"
                until = time.monotonic() + 1.0
                ready = None
                while time.monotonic() < until:
                    try:
                        ready = json.loads(ready_path.read_bytes())
                        break
                    except (FileNotFoundError, json.JSONDecodeError):
                        time.sleep(0.005)
                if ready != {"pid": child.pid, "nonce": nonce}:
                    raise RuntimeError("synthetic readiness not established")
                if not self.identity.verify(child):
                    identity_state = "unverified"
                    raise RuntimeError("synthetic child identity unverified")
                identity_state = "verified_direct_synthetic_child"
                emit("identity_bound", pid=child.pid, executable=self.identity.expected)
                offer = {"command_id": cid, "pid": child.pid, "nonce": nonce,
                         "cleanup_owner": "supervisor", "authority": "synthetic_probe_only"}
                json_new(case / "handoff-offer.json", offer, root=self.root)
                emit("offered", pid=child.pid)
                ack = handoff(dict(offer)) if handoff else dict(offer)
                if ack != offer:
                    raise RuntimeError("handoff acknowledgment mismatch")
                json_new(case / "handoff-accepted.json", ack, root=self.root)
                emit("accepted", pid=child.pid, cleanup_owner="supervisor")
            try:
                code = child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                state = "timed_out"
                emit("timed_out", pid=child.pid, timeout_seconds=timeout)
        except BaseException as exc:
            error = {"type": type(exc).__name__, "message": str(exc), "signal": getattr(exc, "signum", signal.SIGINT if isinstance(exc, KeyboardInterrupt) else None)}
            # Diagnostic metadata is not claimed to be original stderr.
            emit("operation_error", error=error)
        finally:
            # These are our handlers; do not let repeated termination interrupt cleanup.
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                signal.signal(sig, signal.SIG_IGN)
            try:
                if child is not None and child.returncode is None:
                    emit("closing", pid=child.pid, cleanup_owner="supervisor")
                    try:
                        verified = self.identity.verify(child)
                    except (OSError, ChildProcessError) as exc:
                        verified = False
                        identity_state = "unavailable"
                        emit("identity_unavailable", reason=type(exc).__name__)
                    if verified:
                        identity_state = "verified_direct_synthetic_child"
                        child.terminate()
                        emit("terminate_sent", pid=child.pid)
                        try:
                            code = child.wait(timeout=0.5)
                            cleanup = "direct_child_exited_ports_unchecked"
                        except subprocess.TimeoutExpired:
                            # No escalation to blind group kill. The fixture has a bounded self-exit.
                            cleanup = "unverified_after_terminate"
                    else:
                        cleanup = "identity_unverified_no_signal"
                    if child.returncode is None:
                        try:
                            code = child.wait(timeout=2.5)
                        except subprocess.TimeoutExpired:
                            code = None
                            cleanup = "unverified_child_still_running"
                if child is not None and child.returncode is not None:
                    code = child.returncode
                    emit("exit_observed", pid=child.pid, actual_returncode=code,
                                 cleanup=cleanup)
                for fd in (outfd, errfd):
                    if fd is not None:
                        try:
                            os.fsync(fd)
                        except OSError as exc:
                            evidence_errors.append({"event": "raw_stream_fsync", "type": type(exc).__name__, "message": str(exc)})
            finally:
                for fd in (outfd, errfd):
                    if fd is not None:
                        os.close(fd)
                journal.close()
        if code is None:
            state = "exit_unknown" if child is not None else "not_started"
        elif not timed_out:
            state = "signaled" if code < 0 else "exited"
        raw_files = [{"path": str(p.relative_to(self.root)), "sha256": sha(p)}
                     for p in (stdout_path, stderr_path) if p.is_file()]
        artifacts = []
        for name in ("ready.json", "artifact.json", "partial.json"):
            p = case / name
            if p.is_file():
                artifacts.append({"source_path": str(p.relative_to(self.root)), "source_sha256": sha(p),
                                  "relation": "produced", "file_state": "partial" if name == "partial.json" else "present"})
        receipt = {"kind": "C" if code is not None else "E", "command_id": cid,
                   "observed_at": utc(), "started_at": started_at, "argv": argv,
                   "cwd": str(case), "execution_state": state, "exit_code": code,
                   "signal": -code if code is not None and code < 0 else None,
                   "error": error, "identity": identity_state, "cleanup": cleanup,
                   "evidence_errors": evidence_errors, "evidence_complete": not evidence_errors,
                   "supervisor_artifacts": [{"path": str((case / name).relative_to(self.root)), "relation": "checked-not-child-produced", "producer": "enclosing supervisor command receipt"}
                                            for name in ("handoff-offer.json", "handoff-accepted.json") if (case / name).is_file()],
                   "outputs": {"mode": "separate", "stability": "wait-observed" if code is not None else "unverified-live-writer", "raw_files": raw_files},
                   "events": {"path": str(journal.path.relative_to(self.root)), "sha256": sha(journal.path)},
                   "artifacts": artifacts, "scope": "synthetic-only; not host or H1 evidence"}
        validate_result(receipt)
        json_new(case / "command-result.json", receipt, root=self.root)
        return receipt, case


if __name__ == "__main__":
    raise SystemExit("OFFLINE LIBRARY: host execution is disabled")
