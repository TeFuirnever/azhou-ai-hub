"""The Agent Skin Hub entry resolves to its canonical package."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import azhou_integrations
from scripts import integration_common as common
from scripts import integration_startup_animation as animation


class AgentSkinComponentTests(unittest.TestCase):
    def test_agent_skin_is_the_catalogued_codex_entry_for_the_canonical_source(self) -> None:
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                status = azhou_integrations.main(["agent-skin", "check-source"])
        except SystemExit as exc:
            self.fail(f"agent-skin is not a selectable Hub integration: {exc}")

        self.assertEqual(0, status)
        selected = json.loads(output.getvalue())
        self.assertEqual("agent-skin", selected["component"])
        self.assertEqual("agent-skin", selected["package"])
        self.assertEqual(str(common.ROOT / "packages" / "agent-skin"), selected["source"])

        catalog = azhou_integrations.catalog()["integrations"]
        ids = [item["id"] for item in catalog]
        self.assertEqual(1, ids.count("agent-skin"))
        self.assertNotIn("startup-animation", ids)
        item = next(entry for entry in catalog if entry["id"] == "agent-skin")
        self.assertEqual("Agent Skin (Codex)", item["name"])
        self.assertEqual(str(common.ROOT / "packages" / "agent-skin"), item["path"])
        lock = common.load_lock("agent-skin")
        self.assertEqual("agent-skin", lock["component"])


class AgentSkinAssessmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.bundle = root / animation.APP_NAME
        self.bundle.mkdir()
        self.source = root / "source"
        self.source.mkdir()
        self.target = root / "Codex.app"
        self.target.mkdir()
        self.verified = {
            "path": str(self.bundle),
            "version": "0.8.0",
            "build": "9",
        }
        self.clock = 0

    def event(self, name: str, **fields: object) -> dict[str, object]:
        self.clock += 1
        return {
            "schema": "azhou-startup.event.v1",
            "event": name,
            "seconds": float(self.clock),
            "launcherPID": 2468,
            "launcherPath": str(self.bundle),
            **fields,
        }

    def assess(self, mode: str, events: list[dict[str, object]], *, returncode: int = 0,
               verified: dict[str, object] | None = None) -> dict[str, object]:
        return animation.assess_execution(
            mode,
            {"returncode": returncode, "stdout": "\n".join(json.dumps(item) for item in events), "stderr": ""},
            self.bundle,
            verified_bundle=verified or self.verified,
        )

    def test_versioned_ready_does_not_require_playback_or_handoff_completion(self) -> None:
        events = [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing"),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]

        result = self.assess("launch", events)

        self.assertEqual("startup-ready", result["status"])
        self.assertEqual("startup-ready", result["launcher_status"])
        self.assertEqual("ready", result["startup"]["status"])
        self.assertEqual("unobserved", result["playback_completion"])
        self.assertEqual("not-attempted", result["wallpaper_status"])

    def test_hot_activation_is_not_reported_as_injection(self) -> None:
        result = self.assess("launch", [
            self.event("launcher-start"),
            self.event("target-activated", targetPID=3579),
            self.event("launcher-exit", outcome="activated", exitCode=0),
        ])

        self.assertEqual("activated", result["status"])
        self.assertEqual("activated", result["launcher_status"])
        self.assertEqual("not-attempted", result["startup"]["status"])
        self.assertEqual("not-attempted", result["startup"]["injection"])
        self.assertFalse(result["startup"]["installed"])

    def test_early_skip_is_distinct_from_ready_and_player_completion(self) -> None:
        result = self.assess("launch", [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-skipped", targetPID=3579, runId=1, completed=True,
                       completion={"cause": "skip", "beforeReady": True}, overlay=False),
            self.event("launcher-exit", outcome="skipped", exitCode=0),
        ])

        self.assertEqual("skipped", result["status"])
        self.assertEqual("skipped", result["startup"]["status"])
        self.assertEqual("unobserved", result["playback_completion"])

    def test_bad_versioned_events_and_nonzero_exit_never_become_success(self) -> None:
        ready = self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing")
        malformed = self.event("startup-installed", targetPID=3579, runId=1, schema="other.schema")
        valid_prefix = [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            malformed,
            ready,
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]
        self.assertEqual("behavior-not-proven", self.assess("launch", valid_prefix)["status"])

        contradicted = [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-ready", targetPID=3579, runId=2, ready=True, phase="playing"),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]
        self.assertEqual("behavior-not-proven", self.assess("launch", contradicted)["status"])

        valid = [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing"),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]
        self.assertEqual("behavior-not-proven", self.assess("launch", valid, returncode=1)["status"])

        bad_clock = [dict(item) for item in valid]
        bad_clock[3]["seconds"] = True
        self.assertEqual("behavior-not-proven", self.assess("launch", bad_clock)["status"])

        overwritten_failure = [
            self.event("launcher-start"),
            self.event("startup-failed", reason="owner-conflict"),
            self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing"),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]
        self.assertEqual("behavior-not-proven", self.assess("launch", overwritten_failure)["status"])

    def test_versioned_failure_event_cannot_be_overwritten_by_later_ready(self) -> None:
        events = [
            self.event("launcher-start"),
            self.event("startup-port-error", reason="listener-mismatch",
                       operation="bind-loopback", errno=98),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing"),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]

        result = self.assess("launch", events)

        self.assertEqual("behavior-not-proven", result["status"])
        self.assertEqual("failed", result["startup"]["status"])
        self.assertEqual("listener-mismatch", result["startup"]["reason"])
        self.assertEqual("bind-loopback", result["startup"]["operation"])
        self.assertEqual(98, result["startup"]["errno"])

        malformed_operation = self.assess("launch", [
            self.event("launcher-start"),
            self.event("startup-port-error", reason="listener-mismatch", operation=[], errno=98),
            self.event("launcher-exit", outcome="behavior-not-proven", exitCode=1),
        ], returncode=1)
        self.assertEqual("behavior-not-proven", malformed_operation["status"])
        self.assertTrue(any("invalid startup port failure operation" in error
                            for error in malformed_operation["event_errors"]))

    def test_schema_less_supported_diagnostic_does_not_invalidate_launch(self) -> None:
        diagnostic = {"event": "target-activation-after-startup"}
        events = [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing"),
            diagnostic,
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]

        result = self.assess("launch", events)

        self.assertEqual("startup-ready", result["status"])
        self.assertEqual([], result["event_errors"])

    def test_versioned_launch_requires_one_launcher_identity_and_boundary_events(self) -> None:
        mismatched_pid = [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing",
                       launcherPID=2469),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]
        self.assertEqual("behavior-not-proven", self.assess("launch", mismatched_pid)["status"])

        duplicated_start = [
            self.event("launcher-start"),
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing"),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]
        self.assertEqual("behavior-not-proven", self.assess("launch", duplicated_start)["status"])

        duplicated_exit = [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-ready", targetPID=3579, runId=1, ready=True, phase="playing"),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
            self.event("launcher-exit", outcome="startup-ready", exitCode=0),
        ]
        self.assertEqual("behavior-not-proven", self.assess("launch", duplicated_exit)["status"])

    def test_versioned_event_object_without_name_fails_closed_without_crashing(self) -> None:
        events = [
            self.event("launcher-start"),
            {"schema": "azhou-startup.event.v1", "seconds": 2.0},
            self.event("launcher-exit", outcome="activated", exitCode=0),
        ]

        result = self.assess("launch", events)

        self.assertEqual("behavior-not-proven", result["status"])
        self.assertEqual("not-attempted", result["wallpaper_status"])
        self.assertTrue(any("missing event name" in error for error in result["event_errors"]))

    def test_failure_and_interruption_keep_real_progress_prefixes(self) -> None:
        interrupted = self.assess("launch", [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("startup-interrupted", targetPID=3579, runId=1, reason="startup-interrupted"),
            self.event("launcher-exit", outcome="partial", exitCode=2),
        ], returncode=2)
        self.assertEqual("partial", interrupted["status"])
        self.assertTrue(interrupted["startup"]["installed"])
        self.assertEqual("startup-interrupted", interrupted["startup"]["reason"])

        conflict = self.assess("launch", [
            self.event("launcher-start"),
            self.event("target-opened", targetPID=3579),
            self.event("startup-failed", targetPID=3579, reason="owner-conflict"),
            self.event("launcher-exit", outcome="behavior-not-proven", exitCode=1),
        ], returncode=1)
        self.assertEqual("behavior-not-proven", conflict["status"])
        self.assertEqual("owner-conflict", conflict["startup"]["reason"])

        invalid_order = self.assess("launch", [
            self.event("launcher-start"),
            self.event("startup-installed", targetPID=3579, runId=1),
            self.event("target-opened", targetPID=3579),
            self.event("startup-interrupted", targetPID=3579, runId=1, reason="startup-interrupted"),
            self.event("launcher-exit", outcome="partial", exitCode=2),
        ], returncode=2)
        self.assertEqual("behavior-not-proven", invalid_order["status"])

    def test_smoke_proves_independent_playback_without_target_events(self) -> None:
        events = [
            self.event("player-start"),
            self.event("playback-start"),
            self.event("animation-complete"),
            self.event("preview-result", success=True, error=""),
            self.event("player-terminated", completed=True, failed=False),
        ]

        result = self.assess("smoke", events)

        self.assertEqual("behavior-passed", result["status"])
        self.assertEqual("not-run", result["startup"]["status"])
        self.assertEqual("completed", result["playback_completion"])

        mismatched_pid = [dict(item) for item in events]
        mismatched_pid[1]["launcherPID"] = 2469
        self.assertEqual("behavior-not-proven", self.assess("smoke", mismatched_pid)["status"])

        promoted = [dict(item) for item in events]
        promoted.insert(4, {"event": "preview-promoted-to-launch"})
        self.assertEqual("behavior-not-proven", self.assess("smoke", promoted)["status"])

        events.insert(2, self.event("startup-installed", targetPID=3579, runId=1))
        self.assertEqual("behavior-not-proven", self.assess("smoke", events)["status"])

    def test_smoke_requires_preview_result_success_to_be_true(self) -> None:
        preview_results = [
            {"success": False, "error": ""},
            {"error": ""},
            {"success": 1, "error": ""},
            {"success": "true", "error": ""},
        ]
        for preview_fields in preview_results:
            with self.subTest(preview_fields=preview_fields):
                result = self.assess("smoke", [
                    self.event("player-start"),
                    self.event("playback-start"),
                    self.event("animation-complete"),
                    self.event("preview-result", **preview_fields),
                    self.event("player-terminated", completed=True, failed=False),
                ])
                self.assertEqual("behavior-not-proven", result["status"])

    def test_verified_071_bundle_keeps_legacy_assessment(self) -> None:
        legacy = {"path": str(self.bundle), "version": "0.7.1", "build": "8"}
        events = [{"event": name, "launcherPath": str(self.bundle)} for name in
                  ("player-start", "playback-start", "animation-complete", "target-reused",
                   "target-activation-request", "handoff-fade-complete", "player-terminated")]
        events[-1].update(completed=True, failed=False)
        events[4]["allowed"] = True

        result = self.assess("launch", events, verified=legacy)

        self.assertEqual("behavior-passed", result["launcher_status"])
        self.assertEqual("partial", result["status"])
        self.assertEqual("legacy", result["startup"]["schema"])

    def test_status_is_read_only_and_restore_scope_preserves_saved_settings(self) -> None:
        startup = {"installed": False}
        status_event = self.event("wallpaper-result", action="status", state="not-applied",
                                  applied=False, startup=startup)
        status = self.assess("wallpaper-status", [status_event])
        self.assertEqual("not-applied", status["wallpaper_status"])
        self.assertEqual(startup, status["startup"])

        with patch.object(animation, "inspect_bundle", return_value=self.verified), \
                patch.object(animation, "_directory", return_value=self.target):
            read_plan = animation.execution_plan(self.source, self.bundle, "wallpaper-status")
            restore_plan = animation.execution_plan(
                self.source, self.bundle, "disable-wallpaper", target_pid=3579, target_bundle=self.target,
            )
        self.assertEqual([], read_plan["effects"])
        self.assertIn("read-only", read_plan["scope"])
        self.assertIn("saved settings", restore_plan["scope"])
        self.assertIn("--action", restore_plan["command"])

    def test_plan_selects_event_schema_from_verified_app_version(self) -> None:
        with patch.object(animation, "inspect_bundle", return_value=self.verified):
            current = animation.execution_plan(self.source, self.bundle, "launch")
        self.assertEqual("azhou-startup.event.v1", current["event_schema"])

        old_verified = {"path": str(self.bundle), "version": "0.7.1", "build": "8"}
        with patch.object(animation, "inspect_bundle", return_value=old_verified):
            legacy = animation.execution_plan(self.source, self.bundle, "launch")
        self.assertEqual("legacy", legacy["event_schema"])


class AgentSkinOverlayPlanTests(unittest.TestCase):
    """Optional assets/private overlays are file-by-file and bound to the approved plan."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.workspace = self.root / "workspace"
        self.overlay = self.root / "overlay"
        self.overlay.mkdir()
        self.snapshot = self.root / "snapshot"
        (self.snapshot / ".git").mkdir(parents=True)

    def write(self, base: Path, name: str, data: bytes) -> None:
        path = base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def run_build(self, private_assets: Path | None, *, marker: dict[str, object] | None = None):
        plan = animation.build_plan(None, self.workspace, private_assets)
        calls = []

        def run(command, **_kwargs):
            calls.append(command)
            return {"command": command, "returncode": 0, "stdout": "", "stderr": ""}

        bundle = self.snapshot / ".build/azhou-payload"
        if marker is not None:
            self.write(bundle, "Contents/Resources/azhou-build.json", json.dumps(marker).encode())
        with patch.object(animation, "_mac"), patch.object(animation.os, "access", return_value=True), \
                patch.object(common, "snapshot_source", return_value=self.snapshot), \
                patch.object(common, "verify_snapshot"), patch.object(animation, "_run", side_effect=run), \
                patch.object(animation, "inspect_bundle", return_value={"path": str(bundle)}):
            result = animation.build(None, self.workspace, private_assets, plan["plan_id"])
        return plan, result, calls

    def test_partial_overlay_plans_only_supplied_assets(self) -> None:
        self.write(self.overlay, "app-icon/source.png", b"custom icon")
        plan = animation.build_plan(None, self.workspace, self.overlay)
        self.assertEqual(["app-icon/source.png"], list(plan["private_inputs"]))
        full = animation.build_plan(None, self.workspace, None)
        self.assertEqual({}, full["private_inputs"])
        self.assertNotEqual(plan["plan_id"], full["plan_id"])

    def test_empty_overlay_and_incomplete_legacy_overlay_are_rejected(self) -> None:
        with self.assertRaisesRegex(common.IntegrationError, "holds none of"):
            animation.build_plan(None, self.workspace, self.overlay)
        self.write(self.overlay, "working.png", b"legacy")
        origin = common.inspect_source(animation.COMPONENT, None)
        with patch.object(common, "inspect_source", return_value={**origin, "version": "0.8.0"}), \
                self.assertRaises(common.IntegrationError):
            animation.build_plan(None, self.workspace, self.overlay)

    def test_partial_overlay_is_copied_and_bound_through_the_marker(self) -> None:
        self.write(self.overlay, "app-icon/source.png", b"custom icon")
        digest = animation._hash(self.overlay / "app-icon/source.png")
        marker = {"inputs": {"assets/private/app-icon/source.png": digest},
                  "assetSources": {"app-icon/source.png": "private", "working.png": "azhou"}}
        _plan, result, calls = self.run_build(self.overlay, marker=marker)
        self.assertEqual("built", result["status"])
        self.assertEqual(b"custom icon", (self.snapshot / "assets/private/app-icon/source.png").read_bytes())
        self.assertIn(["bash", "tools/build-macos.sh"], calls)

    def test_reused_snapshot_overlay_is_rejected_for_a_library_only_plan(self) -> None:
        self.write(self.snapshot, "assets/private/working.png", b"earlier custom skin")
        with self.assertRaisesRegex(common.IntegrationError, "outside the approved plan"):
            self.run_build(None)

    def test_reused_snapshot_overlay_outside_a_partial_plan_is_rejected(self) -> None:
        self.write(self.overlay, "app-icon/source.png", b"custom icon")
        self.write(self.snapshot, "assets/private/working.png", b"earlier custom skin")
        with self.assertRaisesRegex(common.IntegrationError, "outside the approved plan"):
            self.run_build(self.overlay)

    def test_marker_private_source_outside_the_plan_fails_validation(self) -> None:
        marker = {"inputs": {}, "assetSources": {"working.png": "private"}}
        with self.assertRaisesRegex(common.IntegrationError, "unapproved private overlay asset: working.png"):
            self.run_build(None, marker=marker)
        receipt = json.loads((self.snapshot / ".hub-build.json").read_text(encoding="utf-8"))
        self.assertEqual("failed-validation", receipt["status"])


if __name__ == "__main__":
    unittest.main()
