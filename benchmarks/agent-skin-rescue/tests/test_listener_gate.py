"""Targeted offline gate tests; only owned synthetic TCP listeners, no traffic.

CLI requires a fresh --out under this worktree/.scratch.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import listener_gate as gate
from offline_runtime import DirectChildIdentity, validate_result

OUT = None
NATIVE = []


def write_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def expectation(run, pid=34567, port=54321):
    return gate.GateExpectation(run, pid, "synthetic-birth", Path("/usr/bin/python3"), port)


def declaration(e, argv=None):
    return {"pid": e.pid, "started_lstart": e.birth, "run": str(e.ownrun), "port": e.port,
            "argv": argv or [str(e.exe), "--remote-debugging-port=" + str(e.port)],
            "profile_paths": {"ZCODE_DESKTOP_SESSION_DATA_DIR": str(e.ownrun / "electron-session")}}


def dtap(e):
    return {"port": e.port, "browser_path": "/devtools/browser/synthetic"}


def snapshot(e, address="127.0.0.1", port=None, pid=None, exit=0):
    return {"exit": exit, "records": [{"pid": e.pid if pid is None else pid,
            "address": address, "port": e.port if port is None else port, "loopback": True}]}


class PredicateTests(unittest.TestCase):
    def setUp(self):
        self.run = OUT / self._testMethodName
        self.run.mkdir(mode=0o700)
        (self.run / "electron-session").mkdir(mode=0o700)
        self.e = expectation(self.run)

    def save_dtap(self, data=None):
        p = self.run / "electron-session/DevToolsActivePort"
        p.write_bytes(data if data is not None else b"54321\n/devtools/browser/synthetic\n")
        p.chmod(0o600)
        return p

    def test_declarations_before_any_read_or_backend(self):
        bads = [(replace(self.e, pid=True), declaration(self.e)),
                (replace(self.e, port=True), declaration(self.e)),
                (replace(self.e, ownrun=Path("/tmp/outside")), declaration(self.e)),
                (self.e, {**declaration(self.e), "profile_paths": []}),
                (self.e, {**declaration(self.e), "port": True}),
                (self.e, {**declaration(self.e), "argv": ["wrong"]})]
        for e, receipt in bads:
            with self.subTest(receipt=type(receipt.get("profile_paths")).__name__), patch.object(gate, "bounded_dtap", side_effect=AssertionError("read-before-validation")) as reader:
                backend = unittest.mock.Mock(side_effect=AssertionError("metadata-before-validation"))
                result = gate.evaluate_gate(e, receipt, session_dir=e.ownrun / "electron-session", guard_process=backend, listeners=backend)
                self.assertEqual(result["status"], "refused")
                reader.assert_not_called()
                backend.assert_not_called()

    def test_literal_addresses_and_extra_owned_loopback(self):
        for address in ("127.0.0.1", "::1", "127.12.1.2"):
            value = snapshot(self.e, address)
            value["records"].append({"pid": self.e.pid, "address": "::1", "port": 54322})
            result = gate.classify_snapshot(self.e, declaration(self.e), dtap(self.e), value)
            self.assertEqual(result["status"], "preauth-transport-ready")
            self.assertFalse(result["R05_complete"])

    def test_wildcard_hostname_foreign_and_partial_errors_refuse(self):
        for address in ("0.0.0.0", "::", "*", "localhost", "::1%lo0", "8.8.8.8", ""):
            self.assertEqual(gate.classify_snapshot(self.e, declaration(self.e), dtap(self.e), snapshot(self.e, address))["status"], "refused")
        for value in (snapshot(self.e, pid=7), snapshot(self.e, exit=1), {"exit": False, "records": []}):
            self.assertEqual(gate.classify_snapshot(self.e, declaration(self.e), dtap(self.e), value)["status"], "refused")

    def test_missing_expected_pending_and_dual_mismatch_refused(self):
        for value in ({"exit": 1, "records": []}, snapshot(self.e, port=54322)):
            self.assertEqual(gate.classify_snapshot(self.e, declaration(self.e), dtap(self.e), value)["status"], "pending")
        self.assertEqual(gate.classify_snapshot(self.e, declaration(self.e), {"port": 1}, snapshot(self.e))["status"], "refused")

    def test_dtap_valid_and_missing(self):
        with self.assertRaises(gate.GateStop) as caught:
            gate.bounded_dtap(self.e, self.run / "electron-session")
        self.assertTrue(caught.exception.pending)
        self.save_dtap()
        self.assertEqual(gate.bounded_dtap(self.e, self.run / "electron-session"), dtap(self.e))

    def test_dtap_symlink_fifo_hardlink_oversize_shape_refuse(self):
        p = self.run / "electron-session/DevToolsActivePort"
        target = self.run / "synthetic-target"
        target.write_bytes(b"54321\n/devtools/browser/synthetic\n")
        for mode in ("symlink", "fifo", "hardlink", "oversize", "shape"):
            if mode == "symlink": p.symlink_to(target)
            elif mode == "fifo": os.mkfifo(p, 0o600)
            elif mode == "hardlink": os.link(target, p)
            else: p.write_bytes(b"x" * 4097 if mode == "oversize" else b"54321\nthird\nextra\n")
            with self.subTest(mode=mode), self.assertRaises(gate.GateStop):
                gate.bounded_dtap(self.e, self.run / "electron-session")
            p.unlink()

    def test_ancestor_symlink_before_open_refuses(self):
        self.save_dtap()
        original_open = gate.os.open
        swapped = False
        def swap_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if path == self.run.name and kwargs.get("dir_fd") is not None and not swapped:
                swapped = True
                self.run.rename(self.run.with_name(self.run.name + "-preserved"))
                self.run.symlink_to(self.run.with_name(self.run.name + "-preserved"), target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)
        with patch.object(gate.os, "open", side_effect=swap_open), self.assertRaises(gate.GateStop):
            gate.bounded_dtap(self.e, self.run / "electron-session")
        self.assertTrue(swapped)

    def test_postread_session_replacement_refuses(self):
        self.save_dtap()
        original_read = gate.os.read
        swapped = False
        def swap_read(fd, size):
            nonlocal swapped
            data = original_read(fd, size)
            if data and not swapped:
                swapped = True
                session = self.run / "electron-session"
                session.rename(self.run / "session-preserved")
                session.mkdir(mode=0o700)
                (session / "DevToolsActivePort").write_bytes(b"54321\n/devtools/browser/synthetic\n")
            return data
        with patch.object(gate.os, "read", side_effect=swap_read), self.assertRaises(gate.GateStop) as caught:
            gate.bounded_dtap(self.e, self.run / "electron-session")
        self.assertTrue(swapped)
        self.assertEqual(caught.exception.reason, "session-directory-changed")

    def test_backend_drift_refuses_without_free_text(self):
        self.save_dtap()
        callback = unittest.mock.Mock(side_effect=[None, RuntimeError("PRIVATE_AUTH_URL")])
        result = gate.evaluate_gate(self.e, declaration(self.e), session_dir=self.run / "electron-session", guard_process=callback, listeners=lambda p: snapshot(self.e))
        self.assertEqual(result["reason"], "metadata-backend-unverified")
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_fake_handle_rejected(self):
        with self.assertRaises(ValueError):
            gate.OwnedSupervisor(unittest.mock.Mock(pid=self.e.pid), self.e, guard_process=lambda *a: None, listeners=lambda p: {})


class Metadata:
    def __init__(self):
        self.processes = DirectChildIdentity()
    def path(self, pid):
        return self.processes.path(pid)
    def birth(self, pid):
        result = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "lstart="], stdin=subprocess.DEVNULL, capture_output=True, close_fds=True, check=True)
        return result.stdout.decode("ascii").strip()
    def guard(self, pid, exe, birth):
        if self.path(pid) != str(exe) or self.birth(pid) != birth:
            raise ValueError("owned-metadata-mismatch")
    def current(self, pid):
        return {"pid": pid, "exe": self.path(pid), "birth": self.birth(pid)}
    def listeners(self, pid):
        argv = ["/usr/sbin/lsof", "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN", "-FpfnT"]
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, close_fds=True)
        if result.returncode not in (0, 1) or result.stderr:
            raise ValueError("owned-listener-unavailable")
        records, owner = [], None
        for line in result.stdout.decode("ascii").splitlines():
            if line.startswith("p"): owner = int(line[1:])
            if line.startswith("n"):
                address, sep, port = line[1:].rpartition(":")
                if not sep or not port.isdigit(): raise ValueError("listener-invalid")
                records.append({"pid": owner, "address": address.strip("[]"), "port": int(port)})
        return {"argv": argv, "exit": result.returncode, "records": records}


HELPER = '''import os,socket,sys,time
from pathlib import Path
address,mode,port,root=sys.argv[1:5]
r=Path(root)
s=None
if mode != "timeout":
 s=socket.socket();s.bind((address,int(port)));s.listen(1)
 (r/"electron-session/DevToolsActivePort").write_bytes((port+"\\n/devtools/browser/synthetic\\n").encode("ascii"))
(r/"helper-ready").write_bytes(b"ready")
os.write(1,b"synthetic\\x00stdout\\n");os.write(2,b"synthetic\\xffstderr\\n")
time.sleep(3)
if s:s.close()
'''


class NativeTests(unittest.TestCase):
    def launch(self, mode, wrapped=False):
        case = OUT / self._testMethodName
        case.mkdir(mode=0o700)
        run = case / "run"
        run.mkdir(mode=0o700)
        helper = case / "owned_child.py"
        helper.write_text(HELPER)
        helper.chmod(0o600)
        with socket.socket() as temporary:
            temporary.bind(("127.0.0.1", 0))
            port = temporary.getsockname()[1]
        executable = Path(sys.base_prefix) / "Resources/Python.app/Contents/MacOS/Python"
        if not executable.is_file(): executable = Path(sys.executable)
        executable = executable.resolve()
        prefix, policy_sha = None, None
        if wrapped:
            from host_guard import compile_policy, PUBLIC_READ_ROOTS
            bundle = case / "Synthetic.app"
            bundle.mkdir(mode=0o700)
            execs = list(dict.fromkeys([Path(sys.executable).resolve(), executable]))
            policy, binding = compile_policy(run, original_bundle=bundle,
                read_roots=[*PUBLIC_READ_ROOTS, Path(sys.base_prefix).resolve()],
                executable_paths=execs, read_files=[helper], scope="fixture-only")
            # Fixed loopback-only fixture transport delta; existing file/exec/link
            # rules unchanged. No GUI/Mach/HTTPS or host compatibility assertion.
            if policy.count("(deny network*)") != 1:
                raise AssertionError("unexpected fixed fixture policy")
            policy = policy.replace("(deny network*)", '(allow network-bind (local tcp "localhost:*"))\n(allow network-inbound (local tcp "localhost:*"))')
            policy_sha = hashlib.sha256(policy.encode()).hexdigest()
            prefix = ["/usr/bin/sandbox-exec", "-p", policy]
            (case / "fixture.sb").write_text(policy)
            (case / "fixture.sb").chmod(0o600)
            write_json(case / "fixture-binding.json", {"scope": "fixture-only", "policy_sha256": policy_sha, "base_binding": binding})
        (run / "electron-session").mkdir(mode=0o700)
        stdout = os.open(run / "stdout.bin", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        stderr = os.open(run / "stderr.bin", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        argv = [str(executable), "-B", str(helper), "0.0.0.0" if mode == "wildcard" else "127.0.0.1", mode, str(port), str(run), "--remote-debugging-port=" + str(port)]
        started = datetime.now(timezone.utc).isoformat()
        try:
            child = subprocess.Popen((prefix or []) + argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, close_fds=True, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
        finally:
            os.close(stdout); os.close(stderr)
        deadline = time.monotonic() + 2
        while not (run / "helper-ready").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue((run / "helper-ready").is_file())
        backend = Metadata()
        expected = gate.GateExpectation(run, child.pid, backend.birth(child.pid), Path(backend.path(child.pid)), port)
        supervisor = gate.OwnedSupervisor(child, expected, guard_process=backend.guard, listeners=backend.listeners, current=backend.current, wrapper_prefix=prefix, wrapper_policy_sha256=policy_sha)
        return run, child, expected, supervisor, started

    def finish(self, run, result, started):
        validate_result(result["cleanup"])
        self.assertEqual(result["cleanup"]["kind"], "C")
        self.assertTrue(result["cleanup"]["wait_observed"])
        self.assertEqual(result["cleanup"]["exit_code"], -signal.SIGTERM)
        self.assertIn("started_at", result["cleanup"])
        write_json(run / "result.json", result)
        NATIVE.append({"case": self._testMethodName, "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "result": str((run / "result.json").relative_to(OUT)), "exit_code": result["cleanup"]["exit_code"]})

    def test_native_loopback_ready_cleanup_wait(self):
        run, child, e, supervisor, started = self.launch("loopback")
        result = supervisor.wait_gate(declaration(e, list(child.args)), session_dir=run / "electron-session", timeout=0.5)
        write_json(run / "gate-observed.json", result)
        self.assertEqual(result["gate"]["status"], "preauth-transport-ready")
        result["cleanup"] = supervisor.cleanup("test-finished")
        self.finish(run, result, started)

    def test_native_fixed_sandbox_wrapper_and_binding(self):
        run, child, e, supervisor, started = self.launch("loopback", wrapped=True)
        with self.assertRaises(ValueError):
            gate.OwnedSupervisor(child, e, guard_process=supervisor.guard_process, listeners=supervisor.listeners,
                                 wrapper_prefix=supervisor.wrapper_prefix, wrapper_policy_sha256="0" * 64)
        with self.assertRaises(ValueError):
            gate.OwnedSupervisor(child, e, guard_process=supervisor.guard_process, listeners=supervisor.listeners,
                                 wrapper_prefix=["/usr/bin/env", "-p", supervisor.wrapper_prefix[2]],
                                 wrapper_policy_sha256=hashlib.sha256(supervisor.wrapper_prefix[2].encode()).hexdigest())
        result = supervisor.wait_gate(declaration(e, list(child.args)[3:]), session_dir=run / "electron-session", timeout=0.5)
        write_json(run / "gate-observed.json", result)
        self.assertEqual(result["gate"]["status"], "preauth-transport-ready")
        result["cleanup"] = supervisor.cleanup("test-finished")
        self.finish(run, result, started)
        self.assertEqual(result["cleanup"]["argv"], list(child.args))

    def test_native_wildcard_refused_cleanup_wait(self):
        run, child, e, supervisor, started = self.launch("wildcard")
        result = supervisor.wait_gate(declaration(e, list(child.args)), session_dir=run / "electron-session", timeout=0.5)
        write_json(run / "gate-observed.json", result)
        self.assertEqual(result["gate"]["status"], "refused")
        self.assertEqual(result["gate"]["reason"], "listener-not-literal-loopback")
        self.finish(run, result, started)

    def test_native_timeout_cleanup_wait(self):
        run, child, e, supervisor, started = self.launch("timeout")
        result = supervisor.wait_gate(declaration(e, list(child.args)), session_dir=run / "electron-session", timeout=0.08, interval=0.02)
        write_json(run / "gate-observed.json", result)
        self.assertEqual(result["gate"]["reason"], "gate-timeout")
        self.finish(run, result, started)

    def test_ownership_unknown_and_mutated_handle_never_signal(self):
        run, child, e, supervisor, started = self.launch("timeout")
        old_pid = child.pid
        child.pid = old_pid + 1000000
        with patch.object(child, "poll", side_effect=AssertionError("must-not-poll")), patch.object(child, "terminate", side_effect=AssertionError("must-not-signal")) as term:
            result = supervisor.cleanup()
            self.assertEqual(result["kind"], "E")
            validate_result(result)
            term.assert_not_called()
        child.pid = old_pid
        original_args = child.args
        child.args = list(child.args) + ["mutated-handle"]
        with patch.object(child, "terminate") as term:
            self.assertEqual(supervisor.cleanup()["kind"], "E")
            term.assert_not_called()
        child.args = original_args
        child.returncode = 0
        with patch.object(child, "terminate") as term:
            self.assertEqual(supervisor.cleanup()["kind"], "E")
            term.assert_not_called()
        child.returncode = None
        with patch.object(gate.signal, "getsignal", return_value=signal.SIG_IGN), patch.object(child, "terminate") as term:
            self.assertEqual(supervisor.cleanup()["kind"], "E")
            term.assert_not_called()
        with self.assertRaises(ValueError):
            gate.OwnedSupervisor(child, e, guard_process=supervisor.guard_process, listeners=supervisor.listeners,
                                 wrapper_prefix=["/usr/bin/env", "-p", "(version 1)"], wrapper_policy_sha256=hashlib.sha256(b"(version 1)").hexdigest())
        with patch.object(gate.os, "waitid", side_effect=ChildProcessError()), patch.object(child, "terminate") as term:
            unknown = supervisor.cleanup()
            self.assertEqual(unknown["kind"], "E")
            term.assert_not_called()
        supervisor.guard_process = lambda *a: (_ for _ in ()).throw(RuntimeError("PRIVATE_AUTH_URL"))
        with patch.object(child, "terminate") as term:
            self.assertEqual(supervisor.cleanup()["kind"], "E")
            term.assert_not_called()
        supervisor.guard_process = Metadata().guard
        result = supervisor.cleanup("test-finished")
        self.finish(run, {"gate": {"status": "synthetic-ownership-tests"}, "cleanup": result}, started)
        write_json(run / "unknown.json", {"mutated": unknown})

    def test_retained_argv_mismatch_before_gate_reads(self):
        run, child, e, supervisor, started = self.launch("timeout")
        receipt = declaration(e)
        with patch.object(gate, "evaluate_gate", side_effect=AssertionError("must-not-read")) as evaluate:
            result = supervisor.wait_gate(receipt, session_dir=run / "electron-session")
            self.assertEqual(result["gate"]["reason"], "retained-argv-mismatch")
            evaluate.assert_not_called()
        self.finish(run, result, started)


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    OUT = args.out
    if not OUT.is_absolute() or ".." in OUT.parts or not OUT.is_relative_to(gate.WORKTREE / ".scratch") or OUT.exists() or OUT.parent.resolve() != OUT.parent:
        parser.error("--out must be a fresh canonical worktree/.scratch directory")
    OUT.mkdir(mode=0o700)
    started = datetime.now(timezone.utc).isoformat()
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    raw = OUT / "suite-output.bin"
    raw.write_bytes(stream.getvalue().encode()); raw.chmod(0o600)
    summary = {"scope": gate.SCOPE, "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "tests": result.testsRun,
               "passed": result.testsRun - len(result.failures) - len(result.errors), "failures": len(result.failures), "errors": len(result.errors),
               "native": NATIVE, "actual_exit": 0 if result.wasSuccessful() else 1, "R05_complete": False,
               "source_sha256": hashlib.sha256((ROOT / "listener_gate.py").read_bytes()).hexdigest(),
               "test_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    write_json(OUT / "summary.json", summary)
    print(json.dumps(summary))
    return summary["actual_exit"]


if __name__ == "__main__":
    raise SystemExit(main())
