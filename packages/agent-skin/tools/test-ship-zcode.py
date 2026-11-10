#!/usr/bin/env python3
"""Unit tests for the ZCode ship chain: stamp digest, clean, dry-run, fail-stop."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1]
TOOLS = PACKAGE / "tools"
BUILD_COMMAND = ["bash", "tools/build-macos.sh", "--host", "zcode"]
SIGN_ARGUMENTS = ["codesign", "--force", "--sign", "-"]
VERIFY_ARGUMENTS = ["codesign", "--verify", "--strict"]
HOST_FINGERPRINTS = {
    "infoSHA256": "aa29610c3c02fb37416d8a12322adf58bf1a27270718f07bbbc5ea3efe77c593",
    "executableSHA256": "a9279c2cb198fa58efe564b417ff6717cff388c5fa391c17fc2766a6b1b2121d",
    "appAsarSHA256": "12a2fc939df2fcb4188699772590f5151f1f2b90556bd34ecb6d44cf0d793cc6",
}
STAMP_FIELDS = {
    "schema", "contractVersion", "version", "infoSHA256", "executableSHA256",
    "appAsarSHA256", "recordID", "recordSHA256", "observedAt", "payloadSHA256",
    "evidenceIDs", "ownedAppearanceSurface", "persistentSettings",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot_tree(root: Path):
    return sorted(str(item.relative_to(root)) for item in Path(root).rglob("*"))


class ShipChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module(TOOLS / "ship-zcode.py", "agent_skin_ship_zcode_under_test")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-ship-zcode-")
        self.addCleanup(self.temporary.cleanup)
        self.root = (Path(self.temporary.name) / "source").resolve()
        self.root.mkdir(parents=True)
        self.payload = self.root / ".build/azhou-zcode-payload"
        self.resources = self.payload / "Contents/Resources"
        self.install_js = self.resources / "startup/install.js"
        self.stamp_path = self.resources / "zcode-validation.json"
        self.observation = self.root / ".local/zcode-ship/OBSERVATION.json"
        self.install_js_bytes = b"// startup install.js fixture; embeds build 41\n"
        self.calls = []
        self.codesign_exit = {}
        self.codesign_side_effect = None

        evidence_directory = Path(self.temporary.name) / "zcode-build41-20261108"
        evidence_directory.mkdir()
        self.evidence = evidence_directory / "OBSERVATION.json"
        self.evidence.write_text(json.dumps({
            "schema": "agent-skin-zcode-ui-evidence/v1",
            "hostVersion": "3.17.2.9661",
            "hostFingerprints": dict(HOST_FINGERPRINTS),
            "evidenceIDs": [
                "RC41-real-ZCode-3.17.2.9661-production-builder-UI-exit0",
                "RC41-main-area-wallpaper-pixels-uncovered",
            ],
            "ownedAppearanceSurface": True,
            "persistentSettings": True,
            "observedAt": "2026-11-08T09:38:03.7791Z",
            "run": {
                "runID": "rc41-zcode-observation",
                "startedAt": "2026-11-08T09:00:00Z",
                "endedAt": "2026-11-08T09:38:03.7791Z",
                "evidenceIDs": [
                    "RC41-real-ZCode-3.17.2.9661-production-builder-UI-exit0",
                    "RC41-main-area-wallpaper-pixels-uncovered",
                ],
            },
            "observations": [
                {"runID": "rc41-zcode-observation", "fact": "ownedAppearanceSurface",
                 "outcome": "observed", "observedAt": "2026-11-08T09:35:00Z",
                 "evidenceID": "RC41-real-ZCode-3.17.2.9661-production-builder-UI-exit0"},
                {"runID": "rc41-zcode-observation", "fact": "persistentSettings",
                 "outcome": "observed", "observedAt": "2026-11-08T09:36:00Z",
                 "evidenceID": "RC41-main-area-wallpaper-pixels-uncovered"},
            ],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # --- scripted subprocess environment ---------------------------------

    def runner(self, command, **_kwargs):
        self.calls.append(list(command))
        if command[0] == "git":
            stdout = "ship-tests-branch\n" if "--abbrev-ref" in command else "1a2b3c4\n"
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")
        if command == BUILD_COMMAND:
            (self.resources / "startup").mkdir(parents=True, exist_ok=True)
            self.install_js.write_bytes(self.install_js_bytes)
            (self.resources / "azhou-build.json").write_text(json.dumps(
                {"version": "0.9.0", "build": "41", "inputSHA256": "0" * 64}), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[0] == "codesign":
            exit_code = self.codesign_exit.get(command[1], 0)
            if exit_code == 0 and self.codesign_side_effect:
                self.codesign_side_effect(command)
            if exit_code != 0:
                return subprocess.CompletedProcess(command, exit_code, stdout="",
                                                   stderr=f"codesign fixture failure {command[1]}\n")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected subprocess call: {command}")

    def run_ship(self, argv):
        stdout = io.StringIO()
        with mock.patch.object(self.module, "ROOT", self.root), \
                mock.patch.object(self.module.subprocess, "run", side_effect=self.runner), \
                contextlib.redirect_stdout(stdout):
            code = self.module.main(argv)
        return code, json.loads(stdout.getvalue())

    def successful_run(self, argv=None):
        return self.run_ship(argv or ["--evidence", str(self.evidence)])

    # --- coverage 1: digest is measured from the built install.js --------

    def test_success_chain_stamps_and_receipts_fresh_install_js_digest(self):
        code, receipt = self.successful_run()
        self.assertEqual(code, 0)
        self.assertTrue(receipt["ok"])
        self.assertFalse(receipt["dryRun"])
        digest = hashlib.sha256(self.install_js_bytes).hexdigest()
        self.assertEqual(receipt["payloadSHA256"], digest)
        self.assertEqual([step["step"] for step in receipt["steps"]],
                         ["clean-residue", "build", "stamp", "codesign", "codesign-verify", "verify-stamp"])
        self.assertTrue(all(step["exitCode"] == 0 for step in receipt["steps"]))
        self.assertEqual(receipt["build"], {"version": "0.9.0", "build": "41"})
        self.assertNotIn("failure", receipt)

        stamp = json.loads(self.stamp_path.read_text(encoding="utf-8"))
        self.assertEqual(stamp["payloadSHA256"], digest)
        verify = receipt["steps"][5]
        self.assertEqual(verify["detail"]["stampPayloadSHA256"], digest)
        self.assertEqual(verify["detail"]["measuredInstallJSSHA256"], digest)
        self.assertTrue(verify["detail"]["match"])

        self.assertEqual(self.calls[0], BUILD_COMMAND)
        sign = [*SIGN_ARGUMENTS, str(self.payload)]
        verify_seal = [*VERIFY_ARGUMENTS, str(self.payload)]
        self.assertIn(sign, self.calls)
        self.assertIn(verify_seal, self.calls)
        self.assertLess(self.calls.index(sign), self.calls.index(verify_seal))
        git_calls = [call for call in self.calls if call[0] == "git"]
        self.assertEqual(len(git_calls), 2)
        self.assertLess(self.calls.index(git_calls[-1]), self.calls.index(sign))

    # --- coverage 2: the stamp carries the complete runtime proof schema -

    def test_stamp_carries_the_complete_runtime_proof_schema(self):
        self.successful_run()
        stamp = json.loads(self.stamp_path.read_text(encoding="utf-8"))
        self.assertEqual(set(stamp), STAMP_FIELDS)
        self.assertEqual(stamp["schema"], "agent-skin-zcode-ui-evidence/v1")
        self.assertEqual(stamp["contractVersion"], "agent-skin-zcode-contract/v0.1")
        self.assertEqual(stamp["version"], "3.17.2.9661")
        digest = hashlib.sha256(self.install_js_bytes).hexdigest()
        self.assertEqual(stamp["payloadSHA256"], digest)
        self.assertEqual(stamp["recordSHA256"],
                         hashlib.sha256(self.evidence.read_bytes()).hexdigest())
        self.assertEqual(stamp["recordID"], "zcode-build41-20261108/1a2b3c4/OBSERVATION.json")
        self.assertEqual(stamp["evidenceIDs"],
                         ["RC41-real-ZCode-3.17.2.9661-production-builder-UI-exit0",
                          "RC41-main-area-wallpaper-pixels-uncovered"])
        for field, value in HOST_FINGERPRINTS.items():
            self.assertEqual(stamp[field], value)
        self.assertIs(stamp["ownedAppearanceSurface"], True)
        self.assertIs(stamp["persistentSettings"], True)
        self.assertLess(len(self.stamp_path.read_bytes()), 16384)

    def test_stamp_refuses_evidence_without_real_ui_attestation(self):
        record = json.loads(self.evidence.read_text(encoding="utf-8"))
        record.pop("persistentSettings")
        self.evidence.write_text(json.dumps(record), encoding="utf-8")
        code, receipt = self.run_ship(["--evidence", str(self.evidence)])
        self.assertEqual(code, 1)
        self.assertEqual(receipt["failure"]["step"], "stamp")
        self.assertIn("persistentSettings", receipt["failure"]["error"])
        self.assertFalse(self.stamp_path.exists())
        self.assertFalse(any(call[0] == "codesign" for call in self.calls))

    def test_full_ship_refuses_true_flags_without_observed_trail(self):
        """The public CLI must fail at stamp, before codesign, even for true flags."""
        record = json.loads(self.evidence.read_text(encoding="utf-8"))
        record.pop("observations")
        self.evidence.write_text(json.dumps(record), encoding="utf-8")
        code, receipt = self.run_ship(["--evidence", str(self.evidence)])
        self.assertEqual(code, 1)
        self.assertFalse(receipt["ok"])
        self.assertEqual(receipt["failure"]["step"], "stamp")
        self.assertIn("observations", receipt["failure"]["error"])
        self.assertFalse(self.stamp_path.exists())
        self.assertFalse(any(call[0] == "codesign" for call in self.calls))

    # --- coverage 3: stale payload residue is removed before the build ---

    def test_stale_payload_residue_is_removed_before_build(self):
        stale = self.payload / "stale-stamped-payload.json"
        self.payload.mkdir(parents=True)
        stale.write_text('{"payloadSHA256": "stale"}\n', encoding="utf-8")
        code, receipt = self.successful_run()
        self.assertEqual(code, 0)
        self.assertFalse(stale.exists())
        self.assertEqual(receipt["steps"][0]["step"], "clean-residue")
        self.assertEqual(receipt["steps"][0]["exitCode"], 0)
        self.assertEqual(receipt["steps"][0]["detail"], "removed stale payload")
        self.assertTrue(self.install_js.is_file())

    def test_symlink_payload_residue_is_refused_fail_closed(self):
        outside = Path(self.temporary.name) / "outside-payload"
        outside.mkdir()
        (outside / "payload").mkdir()
        self.payload.parent.mkdir(parents=True)
        self.payload.symlink_to(outside / "payload")
        code, receipt = self.successful_run()
        self.assertEqual(code, 1)
        self.assertEqual(receipt["failure"]["step"], "clean-residue")
        self.assertIn("符号链接", receipt["failure"]["error"])
        self.assertEqual(self.calls, [])
        self.assertTrue(self.payload.is_symlink())

    # --- coverage 4: --dry-run prints the plan with zero side effects ----

    def test_dry_run_prints_plan_with_zero_side_effects(self):
        stale = self.payload / "stale-stamped-payload.json"
        self.payload.mkdir(parents=True)
        stale.write_text("stale\n", encoding="utf-8")
        receipt_path = Path(self.temporary.name) / "receipt.json"
        before = snapshot_tree(self.temporary.name)
        stdout = io.StringIO()
        runner = mock.Mock()
        with mock.patch.object(self.module, "ROOT", self.root), \
                mock.patch.object(self.module.subprocess, "run", runner), \
                contextlib.redirect_stdout(stdout):
            code = self.module.main(["--dry-run", "--evidence", str(self.evidence),
                                     "--receipt", str(receipt_path)])
        self.assertEqual(code, 0)
        runner.assert_not_called()
        self.assertEqual(snapshot_tree(self.temporary.name), before)
        self.assertFalse(receipt_path.exists())
        self.assertFalse(self.observation.exists())

        receipt = json.loads(stdout.getvalue())
        self.assertTrue(receipt["ok"])
        self.assertTrue(receipt["dryRun"])
        self.assertIsNone(receipt["payloadSHA256"])
        self.assertEqual([step["step"] for step in receipt["steps"]],
                         ["clean-residue", "build", "stamp", "codesign", "codesign-verify", "verify-stamp"])
        self.assertTrue(all(step["planned"] is True for step in receipt["steps"]))
        self.assertTrue(all("exitCode" not in step for step in receipt["steps"]))
        self.assertEqual(receipt["steps"][1]["command"], BUILD_COMMAND)
        self.assertEqual(receipt["steps"][3]["command"], [*SIGN_ARGUMENTS, str(self.payload)])
        self.assertTrue(stale.exists())

    def test_install_never_runs_without_the_explicit_flag(self):
        with mock.patch.object(self.module, "zcode_installation_name",
                               side_effect=AssertionError("install path must stay closed")):
            code, _ = self.successful_run()
        self.assertEqual(code, 0)
        install_calls = [call for call in self.calls if call[0] == "ditto"]
        self.assertEqual(install_calls, [])

    def test_dry_run_lists_install_as_planned_without_executing_it(self):
        stdout = io.StringIO()
        runner = mock.Mock()
        with mock.patch.object(self.module, "ROOT", self.root), \
                mock.patch.object(self.module.subprocess, "run", runner), \
                contextlib.redirect_stdout(stdout):
            code = self.module.main(["--dry-run", "--install"])
        self.assertEqual(code, 0)
        runner.assert_not_called()
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt["steps"][-1]["step"], "install")
        self.assertTrue(receipt["steps"][-1]["planned"])
        self.assertFalse(self.payload.exists())

    # --- coverage 5: a failing step stops the chain and is receipted -----

    def test_failing_step_stops_the_chain_and_is_recorded(self):
        self.codesign_exit = {"--force": 3}
        receipt_path = Path(self.temporary.name) / "failed-receipt.json"
        code, receipt = self.run_ship(["--evidence", str(self.evidence),
                                       "--receipt", str(receipt_path)])
        self.assertEqual(code, 1)
        self.assertFalse(receipt["ok"])
        self.assertEqual(receipt["failure"]["step"], "codesign")
        self.assertEqual(receipt["failure"]["exitCode"], 3)
        self.assertIn("fixture failure", receipt["failure"]["error"])
        self.assertEqual(receipt["steps"][-1]["step"], "codesign")
        self.assertEqual(receipt["steps"][-1]["exitCode"], 3)
        self.assertEqual([step["step"] for step in receipt["steps"]],
                         ["clean-residue", "build", "stamp", "codesign"])
        self.assertNotIn([*VERIFY_ARGUMENTS, str(self.payload)], self.calls)
        written = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(written["failure"], receipt["failure"])

    def test_post_stamp_digest_mismatch_fails_closed_at_verify_step(self):
        def tamper(_command):
            if _command[1] == "--force":
                with open(self.install_js, "ab") as handle:
                    handle.write(b"// post-stamp mutation\n")
        self.codesign_side_effect = tamper
        code, receipt = self.run_ship(["--evidence", str(self.evidence)])
        self.assertEqual(code, 1)
        self.assertEqual(receipt["failure"]["step"], "verify-stamp")
        stamped = json.loads(self.stamp_path.read_text(encoding="utf-8"))
        self.assertNotEqual(stamped["payloadSHA256"],
                            hashlib.sha256(self.install_js.read_bytes()).hexdigest())
        self.assertIn("不等于实测", receipt["failure"]["error"])
        detail = receipt["steps"][-1]["detail"]
        self.assertEqual(detail["stampPayloadSHA256"], stamped["payloadSHA256"])
        self.assertEqual(detail["measuredInstallJSSHA256"],
                         hashlib.sha256(self.install_js.read_bytes()).hexdigest())

    def test_missing_evidence_refuses_to_fabricate_a_stamp(self):
        code, receipt = self.run_ship([])
        self.assertEqual(code, 1)
        self.assertEqual(receipt["failure"]["step"], "stamp")
        self.assertIn("--evidence", receipt["failure"]["error"])
        self.assertEqual(self.calls[0], BUILD_COMMAND)
        self.assertFalse(self.stamp_path.exists())
        self.assertFalse(any(call[0] == "codesign" for call in self.calls))
        self.assertFalse(self.observation.exists())

    def test_failing_build_step_is_recorded_and_chain_stops(self):
        def failing_runner(command, **_kwargs):
            self.calls.append(list(command))
            if command == BUILD_COMMAND:
                return subprocess.CompletedProcess(command, 7, stdout="",
                                                   stderr="fixture: missing private assets\n")
            return self.runner(command)
        stdout = io.StringIO()
        with mock.patch.object(self.module, "ROOT", self.root), \
                mock.patch.object(self.module.subprocess, "run", side_effect=failing_runner), \
                contextlib.redirect_stdout(stdout):
            code = self.module.main(["--evidence", str(self.evidence)])
        self.assertEqual(code, 1)
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt["failure"]["step"], "build")
        self.assertEqual(receipt["failure"]["exitCode"], 7)
        self.assertIn("missing private assets", receipt["failure"]["error"])
        self.assertEqual(len(receipt["steps"]), 2)
        self.assertEqual(self.calls, [BUILD_COMMAND])

    # --- observation increment and receipt persistence -------------------

    def test_observation_increment_appends_across_runs(self):
        self.successful_run()
        self.assertTrue(self.observation.is_file())
        first = json.loads(self.observation.read_text(encoding="utf-8"))
        self.assertEqual(first["schema"], "agent-skin-zcode-ui-evidence/v1")
        self.assertEqual(first["branch"], "ship-tests-branch")
        self.assertEqual(first["commit"], "1a2b3c4")
        self.assertEqual(first["hostFingerprints"], HOST_FINGERPRINTS)
        self.assertEqual(len(first["gates"]), 1)
        self.assertEqual(first["gates"][0]["gate"], "tools/ship-zcode.py")
        self.assertEqual(first["gates"][0]["exit"], 0)
        self.assertIn(hashlib.sha256(self.install_js_bytes).hexdigest(),
                      first["gates"][0]["result"])

        self.install_js_bytes = b"// startup install.js fixture; embeds build 42\n"
        self.successful_run()
        second = json.loads(self.observation.read_text(encoding="utf-8"))
        self.assertEqual(len(second["gates"]), 2)
        self.assertIn(hashlib.sha256(self.install_js_bytes).hexdigest(),
                      second["gates"][1]["result"])

    def test_receipt_option_writes_the_same_json_as_stdout(self):
        receipt_path = Path(self.temporary.name) / "ship-receipt.json"
        stdout = io.StringIO()
        with mock.patch.object(self.module, "ROOT", self.root), \
                mock.patch.object(self.module.subprocess, "run", side_effect=self.runner), \
                contextlib.redirect_stdout(stdout):
            code = self.module.main(["--evidence", str(self.evidence),
                                     "--receipt", str(receipt_path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(receipt_path.read_text(encoding="utf-8")),
                         json.loads(stdout.getvalue()))

    def test_cli_entry_point_exits_zero_for_dry_run(self):
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", [str(TOOLS / "ship-zcode.py"), "--dry-run"]), \
                contextlib.redirect_stdout(stdout), \
                self.assertRaises(SystemExit) as exit_state:
            runpy.run_path(str(TOOLS / "ship-zcode.py"), run_name="__main__")
        self.assertEqual(exit_state.exception.code, 0)
        receipt = json.loads(stdout.getvalue())
        self.assertTrue(receipt["dryRun"])
        self.assertEqual(receipt["workspace"], str(PACKAGE))



class ShipInputValidationTests(unittest.TestCase):
    """Validate receipt and stamp refusal paths using only synthetic data."""

    def setUp(self):
        self.module = load_module(TOOLS / "ship-zcode.py", "ship_input_validation")
        self.temp = tempfile.TemporaryDirectory(prefix="agent-skin-ship-input-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.evidence = self.root / "evidence.json"
        self.record = {"hostVersion": "fixture.1", "hostFingerprints": dict(HOST_FINGERPRINTS),
                       "evidenceIDs": ["synthetic-unit-control"], "ownedAppearanceSurface": True,
                       "persistentSettings": True, "observedAt": "2026-11-10T00:05:00Z",
                       "run": {"runID": "rc42-synthetic-observation",
                               "startedAt": "2026-11-10T00:00:00Z",
                               "endedAt": "2026-11-10T00:05:00Z",
                               "evidenceIDs": ["synthetic-unit-control"]},
                       "observations": [
                           {"runID": "rc42-synthetic-observation", "fact": fact,
                            "outcome": "observed", "observedAt": "2026-11-10T00:02:00Z",
                            "evidenceID": "synthetic-unit-control"}
                           for fact in ("ownedAppearanceSurface", "persistentSettings")],
                       }
        self.evidence.write_text(json.dumps(self.record), encoding="utf-8")

    def test_evidence_refuses_missing_nonobject_and_invalid_contract_fields(self):
        for path in (self.root / "absent", self.root):
            with self.subTest(path=path), self.assertRaises(self.module.ShipFailure):
                self.module.load_evidence(path, "abc")
        samples = ["bad json", "[]", json.dumps({**self.record, "hostVersion": ""}),
                   json.dumps({**self.record, "hostFingerprints": {}}),
                   json.dumps({**self.record, "evidenceIDs": []}),
                   json.dumps({**self.record, "ownedAppearanceSurface": False}),
                   json.dumps({**self.record, "persistentSettings": False}),
                   json.dumps({**self.record, "observedAt": ""}),
                   json.dumps({**self.record, "observedAt": "not-a-date"}),
                   json.dumps({**self.record, "recordID": "bad\nvalue"})]
        for text in samples:
            with self.subTest(text=text[:60]):
                self.evidence.write_text(text, encoding="utf-8")
                with self.assertRaises(self.module.ShipFailure):
                    self.module.load_evidence(self.evidence, "abc")

    def _record_with_trail(self):
        end = "2026-11-10T00:05:00Z"
        run_id = "rc42-synthetic-observation"
        evidence = list(self.record["evidenceIDs"])
        return {
            **self.record,
            "observedAt": end,
            "run": {
                "runID": run_id, "startedAt": "2026-11-10T00:00:00Z",
                "endedAt": end, "evidenceIDs": evidence,
            },
            "observations": [
                {"runID": run_id, "fact": fact, "outcome": "observed",
                 "observedAt": "2026-11-10T00:02:00Z", "evidenceID": evidence[0]}
                for fact in ("ownedAppearanceSurface", "persistentSettings")
            ],
        }

    def test_evidence_accepts_proven_observations_and_unrelated_context(self):
        record = self._record_with_trail()
        record["observations"].append({
            "runID": record["run"]["runID"], "fact": "wallpaper",
            "outcome": "observed", "observedAt": "2026-11-10T00:03:00Z",
            "evidenceID": "not-a-capability",
        })
        self.evidence.write_text(json.dumps(record), encoding="utf-8")
        evidence = self.module.load_evidence(self.evidence, "abc")
        self.assertEqual(evidence["recordSHA256"], hashlib.sha256(self.evidence.read_bytes()).hexdigest())
        self.assertTrue(self.module.build_stamp(evidence, "a" * 64)["persistentSettings"])

    def test_true_flags_without_provenance_are_refused(self):
        base = self._record_with_trail()
        for field in ("run", "observations", "observedAt"):
            record = json.loads(json.dumps(base))
            record.pop(field)
            self.evidence.write_text(json.dumps(record), encoding="utf-8")
            with self.subTest(missing=field), self.assertRaises(self.module.ShipFailure):
                self.module.load_evidence(self.evidence, "abc")

    def test_contradicted_or_foreign_observations_are_refused(self):
        changes = [
            ("failed", {"outcome": "failed"}),
            ("refused", {"outcome": "refused"}),
            ("unverified", {"outcome": "unverified"}),
            ("unknown-outcome", {"outcome": "maybe"}),
            ("missing-outcome", {"outcome": None}),
            ("unhashable-outcome", {"outcome": []}),
            ("blank-fact", {"fact": " "}),
            ("foreign-run", {"runID": "previous-run"}),
            ("stale", {"observedAt": "2026-11-09T00:02:00Z"}),
            ("future", {"observedAt": "2026-11-10T00:06:00Z"}),
            ("unbound-evidence", {"evidenceID": "foreign-proof"}),
            ("missing-evidence", {"evidenceID": None}),
            ("bad-timestamp", {"observedAt": "2026-02-30T00:01:00Z"}),
        ]
        for label, change in changes:
            record = self._record_with_trail()
            record["observations"][0].update(change)
            self.evidence.write_text(json.dumps(record), encoding="utf-8")
            with self.subTest(label=label), self.assertRaises(self.module.ShipFailure):
                self.module.load_evidence(self.evidence, "abc")

    def test_malformed_trail_and_run_window_are_refused(self):
        corruptions = [
            ("wrong-trail", "observations", "not-a-list"),
            ("null-trail", "observations", None),
            ("non-object", "observations", [7]),
            ("null-run", "run", None),
            ("bad-run-time", "run", {"runID": "r", "startedAt": "bad", "endedAt": "2026-11-10T00:05:00Z"}),
            ("wrong-record-time", "observedAt", "2026-11-10T00:04:00Z"),
        ]
        for label, field, value in corruptions:
            record = self._record_with_trail()
            record[field] = value
            self.evidence.write_text(json.dumps(record), encoding="utf-8")
            with self.subTest(label=label), self.assertRaises(self.module.ShipFailure):
                self.module.load_evidence(self.evidence, "abc")

    def test_stamp_validation_refuses_each_mismatched_identity(self):
        evidence = self.module.load_evidence(self.evidence, "abc")
        digest = "a" * 64
        stamp = self.module.build_stamp(evidence, digest)
        self.module.validate_stamp(stamp, digest)
        changes = [("schema", "bad"), ("contractVersion", "bad"), ("version", ""),
                   ("infoSHA256", "bad"), ("recordID", ""), ("recordSHA256", "bad"),
                   ("observedAt", "invalid-date"), ("payloadSHA256", "bad"),
                   ("payloadSHA256", "b" * 64), ("evidenceIDs", []),
                   ("ownedAppearanceSurface", False), ("persistentSettings", False)]
        for field, value in changes:
            with self.subTest(field=field, value=value), self.assertRaises(self.module.ShipFailure):
                self.module.validate_stamp({**stamp, field: value}, digest)
        for invalid in ([], {}, {**stamp, "unexpected": True}):
            with self.assertRaises(self.module.ShipFailure):
                self.module.validate_stamp(invalid, digest)
        with mock.patch.object(self.module, "MAX_STAMP_BYTES", 1), self.assertRaises(self.module.ShipFailure):
            self.module.validate_stamp(stamp, digest)

    def test_marker_and_observation_reject_malformed_existing_data(self):
        payload = self.root / "payload"
        marker = payload / self.module.MARKER_RELATIVE
        with self.assertRaises(self.module.ShipFailure):
            self.module.read_build_marker(payload)
        marker.parent.mkdir(parents=True)
        for text in ("bad", "[]", '{"version":"1", "build":true}'):
            marker.write_text(text, encoding="utf-8")
            with self.assertRaises(self.module.ShipFailure):
                self.module.read_build_marker(payload)
        observation = self.root / "observation.json"
        kwargs = dict(branch="fixture", commit="abc", fingerprints=HOST_FINGERPRINTS,
                      digest="a" * 64, build_marker={"version": "1", "build": "2"})
        for text in ("bad", "[]", "{}"):
            observation.write_text(text, encoding="utf-8")
            with self.assertRaises(self.module.ShipFailure):
                self.module.write_observation_increment(observation, **kwargs)
            self.assertEqual(observation.read_text(encoding="utf-8"), text)
        with self.assertRaises(self.module.ShipFailure):
            self.module.write_observation_increment(self.root, **kwargs)

    def test_git_identity_and_cli_unexpected_failure_cannot_report_success(self):
        with mock.patch.object(self.module.subprocess, "run",
                return_value=subprocess.CompletedProcess([], 1, "", "synthetic git failure")), \
                self.assertRaises(self.module.ShipFailure):
            self.module.git_identity(self.root)
        with mock.patch.object(self.module, "ship", side_effect=OSError("synthetic permission denial")), \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as outcome:
            self.module.main([])
        self.assertEqual(outcome.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
