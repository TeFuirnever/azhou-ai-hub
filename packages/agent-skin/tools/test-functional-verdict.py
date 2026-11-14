#!/usr/bin/env python3
"""Unit checks of the functional runner's refusal and evidence predicates."""
import importlib.util
import copy
import json
import os
import runpy
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("installed_acceptance", Path(__file__).with_name("test-installed-acceptance.py"))
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


class FunctionalVerdictTests(unittest.TestCase):
    def assess_native(self, events, code=0, path=None):
        return runpy.run_path(str(Path(__file__).with_name("startup_event_verdict.py")))["assess_native_launch"](events, code, path)

    def native_events(self):
        nonce = "11111111-2222-4333-8444-555555555555"
        events = [{"event": "launcher-start"}, {"event": "target-opened", "targetPID": 42},
            {"event": "startup-installed", "targetPID": 42, "runId": 7, "pageTargetID": "page"},
            {"event": "startup-native-result", "presentation": "completed", "outcome": "startup-ready",
             "runNonce": nonce, "targetPID": 42, "coverDrawCommitted": True, "workspaceObserved": True,
             "pageTargetID": "page",
             "cover": {"runNonce": nonce, "drawCommitted": True},
             "workspace": {"runNonce": nonce, "runId": 7, "pageTargetID": "page",
                           "wallpaperDisposition": "disabled", "wallpaperReason": "disabled"},
             "visualContinuity": "not-measured"},
            {"event": "launcher-exit", "outcome": "startup-ready", "exitCode": 0, "runNonce": nonce, "targetPID": 42}]
        return [{"schema": "azhou-startup.event.v1", "seconds": index, "launcherPID": 10,
                 "launcherPath": "/Applications/Agent Skin.app", **event} for index, event in enumerate(events)]

    def test_native_completion_requires_bound_receipts_and_remains_only_technical_evidence(self):
        valid = self.native_events()
        self.assertTrue(acceptance.cold_start_observed(valid))
        for index in (3, 4):
            for field in valid[index]:
                candidate = copy.deepcopy(valid)
                candidate[index].pop(field)
                self.assertFalse(acceptance.cold_start_observed(candidate), (index, field))
        for end, outcome, code in [("skipped", "skipped", 0), ("interrupted", "partial", 2),
                                    ("failed", "behavior-not-proven", 1)]:
            candidate = copy.deepcopy(valid)
            candidate[3].update(presentation=end, outcome=outcome, workspace=None, workspaceObserved=False)
            if end != "skipped":
                candidate[3]["reason"] = "startup-interrupted" if end == "interrupted" else "attach-timeout"
            candidate[4].update(outcome=outcome, exitCode=code)
            self.assertFalse(acceptance.cold_start_observed(candidate))
        for section in ("cover", "workspace"):
            candidate = copy.deepcopy(valid)
            candidate[3][section]["runNonce"] = "other-run"
            self.assertFalse(acceptance.cold_start_observed(candidate))
        self.assertFalse(acceptance.cold_start_observed(valid + [{"event": "startup-ready"}]))

    def test_native_terminal_outcomes_use_receipts_instead_of_exit_zero_alone(self):
        self.assertIsNone(self.assess_native([{"event": "startup-ready"}]))
        for end, outcome, code, status in [("completed", "startup-ready", 0, "native-completed"),
                ("skipped", "skipped", 0, "skipped"), ("interrupted", "partial", 2, "partial"),
                ("failed", "behavior-not-proven", 1, "behavior-not-proven")]:
            candidate = self.native_events()
            candidate[3].update(presentation=end, outcome=outcome)
            candidate[4].update(outcome=outcome, exitCode=code)
            if end != "completed":
                candidate[3].update(workspace=None, workspaceObserved=False)
            if end in {"interrupted", "failed"}:
                candidate[3]["reason"] = "startup-interrupted" if end == "interrupted" else "attach-timeout"
            result = self.assess_native(candidate, code)
            self.assertEqual(status, result["status"])
            self.assertEqual(end, result["startup"]["status"])
            self.assertEqual("not-measured", result["startup"]["visualContinuity"])
        candidate = self.native_events()
        candidate.pop(2)
        self.assertEqual("native-completed", self.assess_native(candidate)["status"])
        early = self.native_events()
        early = [early[0], early[3], early[4]]
        early[1].update(presentation="skipped", outcome="skipped", targetPID=None, pageTargetID=None,
            workspace=None, workspaceObserved=False, coverDrawCommitted=False)
        early[1]["cover"]["drawCommitted"] = False
        early[2].update(outcome="skipped", targetPID=None)
        self.assertEqual("skipped", self.assess_native(early)["status"])

    def test_native_receipts_reject_conflicting_targets_and_unready_completion(self):
        valid = self.native_events()
        duplicated = copy.deepcopy(valid)
        duplicated.insert(2, copy.deepcopy(duplicated[1]))
        self.assertEqual("behavior-not-proven", self.assess_native(duplicated)["status"])

        out_of_order = copy.deepcopy(valid)
        out_of_order[1], out_of_order[2] = out_of_order[2], out_of_order[1]
        out_of_order[1]["seconds"], out_of_order[2]["seconds"] = 1, 2
        self.assertEqual("behavior-not-proven", self.assess_native(out_of_order)["status"])

        unready = copy.deepcopy(valid)
        unready[3].update(workspace=None, workspaceObserved=False)
        self.assertEqual("behavior-not-proven", self.assess_native(unready)["status"])

    def test_native_verdict_rejects_foreign_missing_or_unfinished_evidence(self):
        valid = self.native_events()
        for index, key, bad in [(0, "schema", "other"), (0, "launcherPID", 0), (1, "launcherPID", 20),
                (0, "launcherPath", "relative"), (1, "launcherPath", "/different"), (1, "seconds", True),
                (1, "seconds", -1), (1, "seconds", float("nan")), (1, "seconds", 10 ** 400),
                (3, "runNonce", []), (3, "runNonce", "bad-uuid"), (3, "presentation", []),
                (3, "presentation", "disabled"), (1, "targetPID", 0), (3, "targetPID", None),
                (4, "targetPID", True), (2, "targetPID", 42.0), (2, "runId", True), (2, "pageTargetID", ""),
                (3, "cover", []), (3, "workspace", []), (3, "workspaceObserved", False),
                (3, "workspaceObserved", 1), (3, "coverDrawCommitted", False), (3, "coverDrawCommitted", 1),
                (3, "visualContinuity", "passed"), (3, "reason", "startup-interrupted")]:
            candidate = copy.deepcopy(valid)
            candidate[index][key] = bad
            self.assertEqual("not-attempted", self.assess_native(candidate)["startup"]["status"], (index, key))
        for section, key, bad in [("cover", "runNonce", "other"), ("cover", "drawCommitted", False),
                ("cover", "drawCommitted", 1), ("workspace", "runNonce", "other"), ("workspace", "runId", 2),
                ("workspace", "pageTargetID", "retired"), ("workspace", "wallpaperDisposition", "pending"),
                ("workspace", "wallpaperReason", None)]:
            candidate = copy.deepcopy(valid)
            candidate[3][section][key] = bad
            self.assertEqual("not-attempted", self.assess_native(candidate)["startup"]["status"])
        for disposition in ("applied", "degraded"):
            candidate = copy.deepcopy(valid)
            candidate[3]["workspace"].update(wallpaperDisposition=disposition,
                wallpaperReason="" if disposition == "applied" else "wallpaper-unsupported")
            self.assertEqual("native-completed", self.assess_native(candidate)["status"])
        for candidate in [valid[1:], valid[:-1], valid + [valid[-1]], valid[:3] + [valid[3], valid[3], valid[4]],
                valid + [{"event": []}], valid + [{"event": "foreign-terminal", "schema": "azhou-startup.event.v1"}],
                [valid[0], valid[2], valid[1], valid[3], valid[4]],
                [valid[0], valid[2], valid[3], valid[4]]]:
            self.assertEqual("not-attempted", self.assess_native(candidate)["startup"]["status"])
        candidate = [valid[0], valid[3], valid[4]]
        self.assertEqual("not-attempted", self.assess_native(candidate)["startup"]["status"])
        self.assertEqual("not-attempted", self.assess_native(valid, path="/foreign")["startup"]["status"])

    def test_native_verdict_accepts_absolute_windows_receipt_paths(self):
        path = r"C:\Program Files\Azhou\Agent Skin.app"
        events = self.native_events()
        for event in events:
            event["launcherPath"] = path
        self.assertEqual("native-completed", self.assess_native(events, path=path)["status"])

    def test_actual_native_producer_samples_are_consumed_when_available(self):
        root = os.environ.get("AZHOU_AGENT_SKIN_NATIVE_EVENT_SAMPLES")
        if not root:
            self.skipTest("native producer sample directory not supplied")
        for end in ("completed", "skipped", "interrupted", "failed"):
            values = acceptance.records((Path(root) / f"native-{end}.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(end == "completed", acceptance.cold_start_observed(values))

    def test_native_verdict_is_a_fingerprinted_canonical_tool(self):
        manifest = json.loads((Path(__file__).resolve().parents[1] / "hub-package.json").read_text(encoding="utf-8"))
        self.assertIn("tools/startup_event_verdict.py", manifest["runtime_paths"])

    def test_ready_cold_events_cannot_be_replaced_by_hot_or_incomplete_events(self):
        values = [{"event": event} for event in ("launcher-start", "target-opened", "startup-installed", "startup-ready")]
        values.append({"event": "launcher-exit", "exitCode": 0, "outcome": "startup-ready"})
        self.assertTrue(acceptance.cold_start_observed(values))
        self.assertFalse(acceptance.cold_start_observed(values[1:]))
        self.assertFalse(acceptance.cold_start_observed(values + [{"event": "target-activated"}]))
        self.assertFalse(acceptance.cold_start_observed(values[:-1] + [{"event": "launcher-exit", "exitCode": 0, "outcome": "activated"}]))

    def test_cold_start_requires_one_verified_probe_and_no_running_host(self):
        probe = {"event": "probe", "targetBundleID": "com.openai.codex", "targetPath": "/Applications/ChatGPT.app", "running": []}
        self.assertTrue(acceptance.cold_start_allowed([probe]))
        for values in [[], [probe, probe], [{**probe, "running": [{}]}],
                       [{**probe, "targetBundleID": "other"}], [{**probe, "running": None}],
                       [{**probe, "targetPath": ""}]]:
            self.assertFalse(acceptance.cold_start_allowed(values))

    def test_installation_requires_current_bytes_and_one_entity_and_registration(self):
        value = {"status": "current", "installedProjectAppCount": 1, "distAppCount": 0, "registeredProjectPathCount": 1}
        self.assertTrue(acceptance.unique_installation([value]))
        for key, bad in [("status", "installed"), ("installedProjectAppCount", 2), ("distAppCount", 1), ("registeredProjectPathCount", 2)]:
            self.assertFalse(acceptance.unique_installation([{**value, key: bad}]))

    def test_wallpaper_never_accepts_only_historical_or_partial_success(self):
        self.assertFalse(acceptance.verified_wallpaper([{"event": "wallpaper-result", "state": "applied", "applied": True}]))
        value = {key: True for key in ("applied", "imageDecoded", "backgroundMatched", "coverMatched", "fixedViewport",
                 "rootClear", "workspaceBackgroundClear", "footerBackgroundClear", "footerFadeClear", "topFadeClear", "decorationEffectsClear")}
        value.update(event="wallpaper-result", state="applied", verificationIssues=[])
        self.assertTrue(acceptance.verified_wallpaper([value]))
        for field in ["imageDecoded", "rootClear", "decorationEffectsClear"]:
            self.assertFalse(acceptance.verified_wallpaper([{**value, field: False}]))
        self.assertFalse(acceptance.verified_wallpaper([{**value, "verificationIssues": ["unsupported"]}]))

    def test_dock_filter_returns_only_the_owned_entry_and_preserves_old_label(self):
        app = Path("/Users/test/Applications/阿舟 AI 实验室.app")
        owned = {"tile-data": {"bundle-identifier": acceptance.BUNDLE_ID, "file-label": "旧名",
                 "file-data": {"_CFURLString": app.as_uri()}}}
        other = {"tile-data": {"bundle-identifier": "com.example.other", "file-label": "Other"}}
        entries = acceptance.dock_entries({"persistent-apps": [owned, other]}, app)
        self.assertEqual(entries, [{"group": "persistent-apps", "label": "旧名", "path": str(app)}])
        self.assertEqual(acceptance.dock_entries({}, app), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
