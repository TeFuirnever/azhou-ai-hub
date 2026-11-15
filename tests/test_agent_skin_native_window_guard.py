import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "packages/agent-skin/tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


native = load("test-startup-native")
payload = load("test-startup-payload-browser")


def observations():
    rows = []
    for control in (True, False):
        for revealed in (False, True):
            rows.append({"schema": "azhou-cold-window-order.v1", "event": "observation",
                "control": control, "revealed": revealed, "coverWindowID": 101, "hostWindowID": 102,
                "coverIndex": 3 if control else 1, "hostIndex": 1 if control else 3,
                "foregroundPIDBefore": 42, "foregroundPID": 42, "probePID": 99,
                "coverLevel": 0 if control else 3, "hostLevel": 0,
                "applicationActiveBeforeHostOrder": False, "applicationActive": False,
                "webViewID": "view-1", "webViewCount": 1, "webViewMounted": True,
                "webViewHidden": not revealed, "coverPresent": not revealed,
                "coverIsKey": False, "canJoinAllSpaces": False, "moveToActiveSpace": False})
        rows.append({"schema": "azhou-cold-window-order.v1", "event": "cleanup", "control": control,
            "coverWindowID": 101, "hostWindowID": 102, "coverWindowPresent": False,
            "hostWindowPresent": False, "geometryEmpty": True, "secondDiscardEmpty": True})
    return rows


def stream(rows):
    return "\n".join(json.dumps(row) for row in rows) + "\n"


class WindowEvidenceTests(unittest.TestCase):
    def test_four_actual_pairs_and_two_teardowns_in_any_order(self):
        rows = observations()
        self.assertEqual(rows, native.validate_window_observations(stream(rows), 0))
        self.assertEqual(rows[::-1], native.validate_window_observations(stream(rows[::-1]), 0))

    def test_requires_inactive_probe_and_actual_expected_window_levels(self):
        for index in (0, 1, 3, 4):
            for field, bad in (("coverLevel", None), ("coverLevel", True),
                    ("coverLevel", 7), ("hostLevel", 3), ("hostLevel", False),
                    ("applicationActiveBeforeHostOrder", True),
                    ("applicationActiveBeforeHostOrder", None),
                    ("applicationActive", True), ("applicationActive", 0)):
                rows = observations()
                rows[index][field] = bad
                with self.subTest(index=index, field=field, bad=bad), self.assertRaises(ValueError):
                    native.validate_window_observations(stream(rows), 0)

    def test_rejects_noop_summary_partial_duplicate_and_nonzero_output(self):
        valid = observations()
        for stdout, code in [("", 0), ("Cold-window ordering checks: 10", 0), ("{}", 0),
                ("[]", 0), ('{"rendered":true,"drawCommitted":true,"isVisible":true}', 0),
                (stream(valid[:2]), 0), (stream(valid[:-1]), 0), (stream(valid + [valid[0]]), 0),
                (stream(valid + [valid[2]]), 0), (stream(valid), 1), (stream(valid), False),
                (stream(valid), 0.0), (stream(valid)[:-4], 0)]:
            with self.subTest(stdout=stdout[:40], code=code), self.assertRaises((ValueError, TypeError)):
                native.validate_window_observations(stdout, code)

    def test_each_observation_validates_types_identity_rank_reveal_focus_and_spaces(self):
        bad_fields = [("schema", "other"), ("event", "summary"), ("control", 1), ("revealed", 0),
            ("control", "false"), ("revealed", None), ("coverWindowID", True), ("coverWindowID", 0),
            ("hostWindowID", -1), ("hostWindowID", 101), ("coverIndex", True), ("hostIndex", -1),
            ("foregroundPIDBefore", None), ("foregroundPID", 0), ("foregroundPID", True),
            ("foregroundPID", 43), ("probePID", 0), ("webViewID", ""), ("webViewCount", True),
            ("webViewCount", 2), ("webViewMounted", False), ("coverIsKey", True),
            ("canJoinAllSpaces", True), ("moveToActiveSpace", True)]
        for index in (0, 1, 3, 4):
            for field, value in bad_fields:
                rows = observations()
                rows[index][field] = value
                with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                    native.validate_window_observations(stream(rows), 0)
            for field in ("webViewHidden", "coverPresent"):
                rows = observations()
                rows[index][field] = not rows[index][field]
                with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                    native.validate_window_observations(stream(rows), 0)
            rows = observations()
            rows[index]["coverIndex"], rows[index]["hostIndex"] = rows[index]["hostIndex"], rows[index]["coverIndex"]
            with self.assertRaises(ValueError):
                native.validate_window_observations(stream(rows), 0)
        for field, value in (("coverWindowID", 201), ("hostWindowID", 202), ("webViewID", "replaced"),
                             ("foregroundPID", 43), ("probePID", 100)):
            rows = observations()
            rows[1][field] = value
            with self.assertRaises(ValueError):
                native.validate_window_observations(stream(rows), 0)

    def test_cleanup_observes_absence_and_stable_owned_identities(self):
        for index in (2, 5):
            for field, value in (("coverWindowPresent", True), ("hostWindowPresent", True),
                    ("geometryEmpty", False), ("secondDiscardEmpty", False), ("coverWindowID", 999)):
                rows = observations()
                rows[index][field] = value
                with self.assertRaises(ValueError):
                    native.validate_window_observations(stream(rows), 0)

    def test_probe_failure_output_and_source_or_binary_drift_are_retained(self):
        for mode in ("success", "partial", "nonzero", "timeout", "missing", "changed", "added", "removed", "binary"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                binary = root / "binary"
                binary.write_bytes(b"binary")
                out = root / "out"
                out.mkdir()
                before = {"input": "one"}
                after = {"input": "two"} if mode == "changed" else dict(before)
                if mode == "added":
                    after["added"] = "x"
                if mode == "removed":
                    after.clear()
                def run(command, **kwargs):
                    self.assertEqual(command, [str(binary), "--probe-cold-window-ordering"])
                    self.assertEqual(kwargs["timeout"], 25)
                    if mode == "timeout":
                        raise subprocess.TimeoutExpired(command, 25, output=b"partial", stderr=b"timeout")
                    if mode == "missing":
                        raise FileNotFoundError("missing binary")
                    if mode == "binary":
                        binary.write_bytes(b"changed")
                    return SimpleNamespace(stdout=stream(observations()[:2] if mode == "partial" else observations()),
                                           stderr="diagnostic", returncode=1 if mode == "nonzero" else 0)
                digest = hashlib.sha256(binary.read_bytes()).hexdigest()
                with patch.object(native.subprocess, "run", side_effect=run), \
                        patch.object(native, "source_fingerprint", return_value=after):
                    result = native.window_ordering_checks(binary, out, before, digest)
                report = json.loads((out / "report.json").read_text())
                self.assertEqual(mode == "success", result == 0)
                self.assertIs(report["unitCoverageInput"], False)
                self.assertEqual("not-measured", report["visualContinuity"])
                self.assertTrue((out / "stdout.jsonl").is_file())
                self.assertTrue((out / "stderr.log").is_file())


class NativeRoutingTests(unittest.TestCase):
    def test_portable_default_skip_and_explicit_functional_failure(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(native.sys, "platform", "linux"), \
                patch.object(native.subprocess, "run") as run:
            with patch.object(sys, "argv", ["native"]):
                self.assertEqual(0, native.main())
            with patch.object(sys, "argv", ["native", "--window-ordering", "--out", str(Path(temporary) / "new")]):
                self.assertEqual(1, native.main())
            run.assert_not_called()

    def test_no_flag_does_not_run_graphics_and_explicit_flag_routes_exact_probe(self):
        for functional in (False, True):
            with self.subTest(functional=functional), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for name in native.NATIVE_INPUTS:
                    target = root / name
                    target.parent.mkdir(exist_ok=True, parents=True)
                    target.write_text(name)
                calls = []
                def run(command, **kwargs):
                    calls.append(command)
                    if command[0] == "xcrun":
                        Path(command[command.index("-o") + 1]).write_bytes(b"compiled")
                    stdout = ""
                    if "--emit-helper-expressions" in command:
                        stdout = json.dumps({name: "expression" for name in (
                            "statusSource", "applyGuardSource", "retrySource", "restoreSource")})
                    elif "--probe-cold-window-ordering" in command:
                        stdout = stream(observations())
                    return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
                argv = ["native"] + (["--window-ordering", "--out", str(root / "out")] if functional else [])
                with patch.object(native, "ROOT", root), patch.object(native.sys, "platform", "darwin"), \
                        patch.object(native, "handshake_checks"), patch.object(native.subprocess, "run", side_effect=run), \
                        patch.object(sys, "argv", argv):
                    self.assertEqual(0, native.main())
                self.assertEqual(functional, any("--probe-cold-window-ordering" in command for command in calls))
                if functional:
                    self.assertTrue(json.loads((root / "out/report.json").read_text())["passed"])

    def test_old_or_symlink_output_is_refused_before_children(self):
        for module, flag in ((native, ["--window-ordering"]), (payload, ["--native-window-ordering"])):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                existing = root / "existing"
                existing.mkdir()
                link = root / "link"
                link.symlink_to(root / "missing")
                for out in (existing, link):
                    with patch.object(sys, "argv", ["runner", *flag, "--out", str(out)]), \
                            patch.object(module.subprocess, "run") as run, self.assertRaises(FileExistsError):
                        module.main()
                    run.assert_not_called()


class PayloadRoutingTests(unittest.TestCase):
    def test_payload_forwards_requested_probe_and_propagates_failure_or_noop_browser(self):
        for mode in ("default", "functional", "native-failed", "native-noop", "native-partial",
                     "native-stale", "native-mismatch", "native-error", "browser-noop", "missing-case"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                out = Path(temporary) / "evidence"
                calls = []
                def clone(root):
                    root.mkdir()
                def load_module(path, name):
                    if path.name == "test-startup-native.py":
                        return SimpleNamespace(source_fingerprint=lambda: {"source": "current"},
                            validate_window_observations=native.validate_window_observations)
                    return SimpleNamespace(build_startup=lambda *args, **kwargs: None)
                helpers = SimpleNamespace(clone_source_tree=clone, load_module=load_module)
                def run(command, **kwargs):
                    calls.append(command)
                    if "tools/test-startup-native.py" in command:
                        if "--window-ordering" in command and mode not in {"native-failed", "native-noop"}:
                            binary = kwargs["cwd"] / ".build/startup-native-tests"
                            binary.parent.mkdir(exist_ok=True)
                            binary.write_bytes(b"compiled")
                            evidence = out / "native-window-ordering"
                            evidence.mkdir()
                            rows = observations()[:2] if mode == "native-partial" else observations()
                            digest = hashlib.sha256(binary.read_bytes()).hexdigest()
                            fingerprint = {"source": "stale" if mode == "native-stale" else "current"}
                            (evidence / "stdout.jsonl").write_text(stream(rows))
                            (evidence / "report.json").write_text(json.dumps({"passed": True, "returncode": 0,
                                "error": "failed" if mode == "native-error" else None,
                                "sourceBefore": fingerprint, "sourceAfter": fingerprint,
                                "binaryBefore": digest, "binaryAfter": digest,
                                "observations": rows[:-1] if mode == "native-mismatch" else rows}))
                        return SimpleNamespace(returncode=7 if mode == "native-failed" else 0)
                    if any(str(value).endswith("test-startup-browser.mjs") for value in command) and mode != "browser-noop":
                        (out / "report.json").write_text(json.dumps({"passed": True, "missingChecks": [],
                            "selectedChecks": ["required"], "cleanup": {"ownChromeStopped": True,
                                "temporaryProfileRemoved": True, "serverClosed": True, "errors": [], "profilePath": None}, "checks": [
                                {"name": "other" if mode == "missing-case" else "required", "passed": True}]}))
                    return SimpleNamespace(returncode=0)
                flag = [] if mode == "default" else ["--native-window-ordering"]
                with patch.object(sys, "argv", ["payload", "--out", str(out), "--only", "required", *flag]), \
                        patch.object(payload.sys, "platform", "darwin"), patch.object(payload.shutil, "which", return_value="tool"), \
                        patch.object(payload, "build_test_helpers", return_value=helpers), \
                        patch.object(payload.subprocess, "run", side_effect=run), patch.dict("os.environ", {"AZHOU_RUN_NATIVE_EVENT_ASSESSMENT": "0"}):
                    result = payload.main()
                rejected_native = {"native-failed", "native-noop", "native-partial", "native-stale", "native-mismatch", "native-error"}
                self.assertEqual(7 if mode == "native-failed" else 1 if mode in rejected_native | {"browser-noop", "missing-case"} else 0, result)
                native_command = calls[0]
                self.assertEqual(mode != "default", "--window-ordering" in native_command)
                if mode != "default":
                    self.assertEqual(str(out / "native-window-ordering"), native_command[-1])
                self.assertEqual(mode not in rejected_native, len(calls) > 1)


class BrowserEvidenceTests(unittest.TestCase):
    def test_requires_consistent_check_and_cleanup_evidence(self):
        valid = {"passed": True, "missingChecks": [], "selectedChecks": ["required"],
            "checks": [{"name": "required", "passed": True}, {"name": "unselected", "skipped": True}],
            "cleanup": {"ownChromeStopped": True, "temporaryProfileRemoved": True,
                        "serverClosed": True, "errors": [], "profilePath": None}}
        invalid = []
        for field, value in (("fatalError", "failed"), ("cleanupError", "failed"), ("passed", 1),
                             ("cleanup", None), ("missingChecks", ["required"]), ("checks", [])):
            report = copy.deepcopy(valid)
            report[field] = value
            invalid.append(report)
        for field, value in (("ownChromeStopped", False), ("temporaryProfileRemoved", 1),
                ("serverClosed", False), ("errors", ["failed"]), ("profilePath", "/retained/profile")):
            report = copy.deepcopy(valid)
            report["cleanup"][field] = value
            invalid.append(report)
        for row in ({"name": "required", "passed": True, "skipped": True},
                    {"name": "required", "passed": True, "error": "failed"},
                    {"name": "required", "passed": 1}, {"name": "required", "skipped": True},
                    {"name": "unselected", "passed": False, "skipped": True},
                    {"name": "unselected", "skipped": True, "error": "failed"},
                    {"name": "unselected", "skipped": 1}, {"name": "", "passed": True}):
            report = copy.deepcopy(valid)
            report["checks"][1 if row["name"] == "unselected" else 0] = row
            invalid.append(report)
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out / "report.json").write_text(json.dumps(valid))
            payload.validate_browser_report(out, ["required"])
            for index, report in enumerate(invalid):
                with self.subTest(index=index), self.assertRaises(ValueError):
                    (out / "report.json").write_text(json.dumps(report))
                    payload.validate_browser_report(out, ["required"])

    def test_full_run_requires_both_payload_cases_and_no_skipped_rows(self):
        names = ["compiled native helper status and apply guard execute against the live fixture API objects",
                 "generated Escape keeps Appearance hidden until host UI is ready"]
        valid = {"passed": True, "missingChecks": [], "selectedChecks": [],
            "checks": [{"name": name, "passed": True} for name in names],
            "cleanup": {"ownChromeStopped": True, "temporaryProfileRemoved": True,
                        "serverClosed": True, "errors": [], "profilePath": None}}
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            (out / "report.json").write_text(json.dumps(valid))
            payload.validate_browser_report(out, [])
            for checks in (valid["checks"][:1], valid["checks"] + [{"name": "unrun", "skipped": True}]):
                with self.assertRaises(ValueError):
                    (out / "report.json").write_text(json.dumps({**valid, "checks": checks}))
                    payload.validate_browser_report(out, [])


if __name__ == "__main__":
    unittest.main()
