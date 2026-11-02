"""Offline isolation API tests. All case data is retained beneath --out."""
from pathlib import Path
import argparse
import json
import os
import sys
import subprocess
import datetime
import hashlib
import unittest

L = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(L))
import isolation

TEST_ROOT = None

class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.case = TEST_ROOT / self._testMethodName
        self.case.mkdir(mode=0o700)
        self.isolation = isolation.Isolation(TEST_ROOT)
        self.guard_path = self.case / "static-source.json"
        self.guard_path.write_bytes(b'{"scope":"synthetic-static-source"}\n')
        self.guard_path.chmod(0o600)
        self.guard_sha = hashlib.sha256(self.guard_path.read_bytes()).hexdigest()

    def test_layout_separates_private_roots_and_actual_log_expectation(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        self.assertEqual(layout["app_logs"], str(self.case / "run/business/.zcode/v2/logs"))
        self.assertEqual(len({layout[k] for k in ("home", "tmp", "business", "electron_user", "electron_session", "logs", "empty_workspace")}), 7)
        for value in layout["directories"]:
            self.assertEqual(Path(value).stat().st_mode & 0o777, 0o700)
        self.isolation.validate_layout(layout)

    def test_dirty_parent_environment_is_not_forwarded(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        parent = {"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": "/synthetic-daily",
                  "TMPDIR": "/synthetic-shared", "XDG_CONFIG_HOME": "/synthetic-config",
                  "HTTP_PROXY": "http://synthetic-proxy", "TOKEN": "synthetic-secret",
                  "ZCODE_ENV": "test", "ZCODE_E2E_RUNTIME_LOG_DIR": "/synthetic-shared-log",
                  "ZCODE_DATA_BASE_DIR": "/synthetic-old-business"}
        env = self.isolation.child_environment(parent, layout)
        self.assertEqual(env, {"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": layout["home"],
                              "TMPDIR": layout["tmp"], "ZCODE_DATA_BASE_DIR": layout["business"],
                              "ZCODE_DESKTOP_USER_DATA_DIR": layout["electron_user"],
                              "ZCODE_DESKTOP_SESSION_DATA_DIR": layout["electron_session"]})

    def test_existing_run_is_never_reused(self):
        run = self.case / "run"; self.isolation.prepare_layout(run)
        with self.assertRaises(FileExistsError): self.isolation.prepare_layout(run)

    def test_parent_escape_and_lookalike_are_rejected(self):
        for path in (TEST_ROOT.parent / "outside", TEST_ROOT / ".." / "outside", Path(str(TEST_ROOT)+"-other") / "run"):
            with self.assertRaises(ValueError): self.isolation.prepare_layout(path)

    def test_symlink_parent_and_preexisting_run_link_are_rejected(self):
        target = self.case / "target"; target.mkdir(mode=0o700)
        link = self.case / "link"; link.symlink_to(target)
        with self.assertRaises(OSError): self.isolation.prepare_layout(link / "run")
        run = self.case / "run"; run.symlink_to(target)
        with self.assertRaises(FileExistsError): self.isolation.prepare_layout(run)
        self.assertEqual(list(target.iterdir()), [])

    def test_parent_mode_and_changed_root_identity_are_rejected(self):
        bad = self.case / "bad"; bad.mkdir(mode=0o755); bad.chmod(0o755)
        with self.assertRaises(ValueError): self.isolation.prepare_layout(bad / "run")
        layout = self.isolation.prepare_layout(self.case / "run")
        path = Path(layout["business"]); path.rename(self.case / "retained-business")
        path.mkdir(mode=0o700)
        with self.assertRaises(ValueError): self.isolation.validate_layout(layout)

    def test_configuration_fallback_stops_without_reading_contents(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        config = Path(layout["home"]) / ".zcode"; config.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, "configuration fallback"):
            self.isolation.validate_layout(layout)

    def test_host_plan_stays_blocked_even_with_historical_static_guard(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        guard = {"path": str(self.guard_path), "sha256": self.guard_sha}
        plan = self.isolation.launch_plan(layout, "/Applications/ZCode.app/Contents/MacOS/ZCode", configuration_guard=guard)
        self.assertFalse(plan["hostLaunchAllowed"])
        self.assertEqual(plan["configurationGuard"]["status"], "caller-supplied-static-checked")
        self.assertEqual(plan["expectedApplicationLogs"], layout["app_logs"])
        self.assertEqual(plan["actualElectronPaths"], "unverified")
        self.assertTrue(all(v == "unverified" for v in plan["sharedBoundaries"].values()))
        self.assertIn("new-serial-window-not-confirmed", plan["blockers"])
        self.assertIsNone(plan["argv"])

    def test_missing_or_untrusted_static_guard_is_not_a_pass(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        plan = self.isolation.launch_plan(layout, "/Applications/ZCode.app/Contents/MacOS/ZCode")
        self.assertIn("bootstrap-source-guard-unverified", plan["blockers"])
        guard = {"path": str(self.guard_path), "sha256": "0" * 64}
        with self.assertRaises(ValueError):
            self.isolation.launch_plan(layout, "/Applications/ZCode.app/Contents/MacOS/ZCode", configuration_guard=guard)

    def test_configuration_guard_fifo_is_rejected_without_blocking(self):
        self.guard_path.unlink()
        os.mkfifo(self.guard_path, 0o600)
        code = ("import sys\nfrom pathlib import Path\n"
                "sys.path.insert(0,sys.argv[1])\nfrom isolation import Isolation\n"
                "try:\n    Isolation(Path(sys.argv[2]))._check_configuration_guard({'path':sys.argv[3],'sha256':sys.argv[4]})\n"
                "except ValueError as error:\n    raise SystemExit(0 if str(error)=='untrusted static source permissions' else 2)\n"
                "raise SystemExit(1)\n")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(L), str(TEST_ROOT),
                                 str(self.guard_path), self.guard_sha],
                                capture_output=True, text=True, encoding="utf-8", timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_own_controlled_child_observation_is_only_synthetic(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        env = self.isolation.child_environment({"PATH": "/usr/bin:/bin", "HOME": "/synthetic-daily"}, layout)
        code = "import json,os,pathlib; keys=('HOME','TMPDIR','ZCODE_DATA_BASE_DIR','ZCODE_DESKTOP_USER_DATA_DIR','ZCODE_DESKTOP_SESSION_DATA_DIR'); logs=pathlib.Path(os.environ['ZCODE_DATA_BASE_DIR'])/'.zcode/v2/logs'; (logs/'synthetic-child.log').write_bytes(b'synthetic-only\\x00\\xff'); print(json.dumps({'scope':'synthetic-child','env':{k:os.environ[k] for k in keys},'app_logs':str(logs)}))"
        argv = [sys.executable, "-B", "-c", code]
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (self.case / "child-stdout.raw").open("xb") as stdout, (self.case / "child-stderr.raw").open("xb") as stderr:
            child = subprocess.Popen(argv, cwd=layout["empty_workspace"], env=env, stdout=stdout, stderr=stderr)
            result = child.wait(timeout=5)
        receipt = {"scope": "synthetic-test-child", "argv": argv, "startedAt": started,
                   "finishedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "pid": child.pid, "exitCode": result, "signal": -result if result < 0 else None,
                   "outputs": [{"path": str(self.case/name), "sha256": hashlib.sha256((self.case/name).read_bytes()).hexdigest()}
                               for name in ("child-stdout.raw", "child-stderr.raw")]}
        with (self.case / "child-command.json").open("x") as output: json.dump(receipt, output, indent=2)
        self.assertEqual(result, 0)
        observation = json.loads((self.case / "child-stdout.raw").read_bytes())
        checked = self.isolation.validate_fixture_observation(layout, observation)
        self.assertEqual(checked["status"], "synthetic-match")
        self.assertEqual(checked["host_validation"], "not_run")
        self.assertEqual((Path(layout["app_logs"]) / "synthetic-child.log").read_bytes(), b"synthetic-only\x00\xff")

    def test_observation_rejects_host_scope_and_path_mismatch(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        env = self.isolation.child_environment({}, layout)
        observation = {"scope": "host", "env": env, "app_logs": layout["app_logs"]}
        with self.assertRaises(ValueError): self.isolation.validate_fixture_observation(layout, observation)
        observation["scope"] = "synthetic-child"; observation["env"]["HOME"] = "/synthetic-outside"
        with self.assertRaises(ValueError): self.isolation.validate_fixture_observation(layout, observation)

    def test_post_prepare_permission_change_and_new_home_link_stop(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        Path(layout["tmp"]).chmod(0o755)
        with self.assertRaises(ValueError): self.isolation.validate_layout(layout)
        other = self.isolation.prepare_layout(self.case / "other")
        (Path(other["home"]) / ".zcode").symlink_to(self.case / "never-read-synthetic")
        with self.assertRaises(ValueError): self.isolation.validate_layout(other)

    def test_environment_nul_and_non_fresh_port_shapes_stop(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        with self.assertRaises(ValueError): self.isolation.child_environment({"PATH": "bad\x00path"}, layout)
        for port in (True, 0, -1, 65536, "9222"):
            with self.assertRaises(ValueError): self.isolation.launch_plan(layout, isolation.ZCODE_EXECUTABLE, port=port)
        plan = self.isolation.launch_plan(layout, isolation.ZCODE_EXECUTABLE, port=12345)
        self.assertEqual(plan["argv"], [isolation.ZCODE_EXECUTABLE, "--remote-debugging-port=12345"])
        self.assertFalse(plan["hostLaunchAllowed"])

    def test_source_guard_cannot_inject_scope_or_status_claims(self):
        layout = self.isolation.prepare_layout(self.case / "run")
        guard = {"path": str(self.guard_path), "sha256": self.guard_sha,
                 "scope": "actual-host-proven"}
        with self.assertRaises(ValueError):
            self.isolation.launch_plan(layout, isolation.ZCODE_EXECUTABLE, configuration_guard=guard)
        with self.assertRaises(ValueError):
            self.isolation.launch_plan(layout, isolation.ZCODE_EXECUTABLE, configuration_guard=True)

if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--out", required=True)
    args,rest=parser.parse_known_args();TEST_ROOT=Path(args.out)
    if TEST_ROOT.resolve()!=TEST_ROOT or not TEST_ROOT.is_relative_to(L.parents[1] / ".scratch"):raise SystemExit("test output outside candidate")
    TEST_ROOT.mkdir(mode=0o700)
    unittest.main(argv=[sys.argv[0],*rest],verbosity=2)
