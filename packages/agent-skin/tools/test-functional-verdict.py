#!/usr/bin/env python3
"""Unit checks of the functional runner's refusal and evidence predicates."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("installed_acceptance", Path(__file__).with_name("test-installed-acceptance.py"))
acceptance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(acceptance)


class FunctionalVerdictTests(unittest.TestCase):
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
