"""The Agent Skin Hub entry resolves to its canonical package."""
from __future__ import annotations

import io
import hashlib
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import azhou_integrations
from scripts import integration_common as common
from scripts import integration_startup_animation as animation
from scripts import azhou_runtime_state as state
from package_fixture import configure_package


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

        current = common.load_lock("agent-skin")
        legacy = common.load_lock("startup-animation")
        self.assertNotEqual(
            (legacy["runtime_version"], legacy["runtime_build"]),
            (current["runtime_version"], current["runtime_build"]),
            "the canonical Agent Skin runtime may advance while the legacy launcher stays frozen",
        )
        for field in ("repository", "local_source_origin", "commit"):
            self.assertEqual(legacy[field], current[field], field)
        legacy_inputs = set(legacy["build_inputs"])
        self.assertEqual(
            legacy["build_inputs"],
            [name for name in current["build_inputs"] if name in legacy_inputs],
            "the canonical package keeps every frozen launcher input in order",
        )
        self.assertEqual(
            [name for name in current["build_inputs"] if name not in legacy_inputs],
            ["tools/build-startup.py", "tools/build-startup-assets.swift", "hub-package.json",
             "extension/renderer.mjs", "image-settings.js"],
            "the canonical Agent Skin package adds its complete startup builder and renderer inputs",
        )


class AgentSkinLegacyCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.hub = self.base / "hub"
        self.workspace = self.base / "workspace"
        self.agent_source = configure_package(self.hub, "agent-skin", [])
        self.legacy_source = configure_package(
            self.hub,
            "startup-animation",
            [".gitignore", "Native/App.swift", "tools/verify-artifacts.py"],
            build_inputs=["Native/App.swift"],
            runtime_version="0.7.0",
            runtime_build="7",
        )
        (self.legacy_source / ".gitignore").write_text("fixture inputs\n", encoding="utf-8")
        (self.legacy_source / "Native/App.swift").parent.mkdir(parents=True)
        (self.legacy_source / "Native/App.swift").write_text("old launcher input\n", encoding="utf-8")
        verifier = """import hashlib\nimport json\nfrom pathlib import Path\n\ndef verify_product(bundle):\n    return {\n        \"CFBundleIdentifier\": \"local.azhou.codex-startup\",\n        \"CFBundleExecutable\": \"AzhouCodexStartup\",\n        \"CFBundleShortVersionString\": \"0.7.0\",\n        \"CFBundleVersion\": \"7\",\n    }\n\ndef read_marker(bundle, required=False):\n    return json.loads((Path(bundle) / \"Contents/Resources/azhou-build.json\").read_text())\n\ndef fingerprint(bundle):\n    digest = hashlib.sha256()\n    for path in sorted(Path(bundle).rglob(\"*\")):\n        if path.is_file():\n            digest.update(path.relative_to(bundle).as_posix().encode(\"utf-8\"))\n            digest.update(path.read_bytes())\n    return digest.hexdigest()\n"""
        verifier_path = self.legacy_source / "tools/verify-artifacts.py"
        verifier_path.parent.mkdir(parents=True)
        verifier_path.write_text(verifier, encoding="utf-8")
        self.lock = common.load_lock("startup-animation", hub_root=self.hub)
        self.snapshot = common.snapshot_source("startup-animation", self.legacy_source, self.workspace, hub_root=self.hub)

    def install_legacy_receipt_fixture(self) -> tuple[Path, Path, bytes]:
        target_root = state.state_path(self.workspace, "hub", "test-installations", "startup-animation")
        target = target_root / animation.APP_NAME
        resources = target / "Contents/Resources"
        (target / "Contents/MacOS").mkdir(parents=True)
        (target / "Contents/MacOS/AzhouCodexStartup").write_text("frozen app\n", encoding="utf-8")
        web = resources / "web"
        web.mkdir(parents=True)
        resource_hashes = {}
        for name in ("index.html", "style.css", "animation.js", "assets/private/working.png", "assets/private/scene.js"):
            path = web / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("frozen " + name, encoding="utf-8")
            resource_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        marker = {
            "projectRoot": str(self.snapshot),
            "inputs": {
                **{name: item["sha256"] for name, item in self.lock["files"].items() if name in self.lock["build_inputs"]},
                **resource_hashes,
            },
            "inputSHA256": "fixture source input digest",
        }
        resources.mkdir(parents=True, exist_ok=True)
        (resources / "azhou-build.json").write_text(json.dumps(marker), encoding="utf-8")
        registry = self.snapshot / ".build/azhou-install-registry"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text("frozen registry helper\n", encoding="utf-8")
        registry.chmod(0o700)

        digest = hashlib.sha256()
        for path in sorted(target.rglob("*")):
            if path.is_file():
                digest.update(path.relative_to(target).as_posix().encode("utf-8"))
                digest.update(path.read_bytes())
        record = target_root / "receipt.json"
        receipt = {
            "schema": "azhou-hub.animation-test-install.v1",
            "component": "startup-animation",
            "path": str(target),
            "sha256_tree": digest.hexdigest(),
            "source_lock_sha256": common.plan_digest(self.lock),
        }
        common.write_receipt(record, receipt)
        return target, record, record.read_bytes()

    def test_agent_skin_can_plan_cleanup_from_an_unchanged_legacy_snapshot(self) -> None:
        target, record, original_receipt = self.install_legacy_receipt_fixture()

        verifier_path = self.legacy_source / "tools/verify-artifacts.py"
        verifier_path.write_text("raise RuntimeError('live verifier must not be used')\n", encoding="utf-8")
        inventory = {name: [] for name in animation.REGISTRY_IDS}
        with patch.object(animation, "_registry_inventory", return_value=inventory):
            plan = animation.test_uninstall_plan(self.agent_source, self.workspace, hub_root=self.hub)

        self.assertEqual("startup-animation", plan["target"]["source"]["component"])
        self.assertEqual(str(self.snapshot), plan["target"]["native_source_root"])
        self.assertEqual(str(self.legacy_source), plan["target"]["source"]["source"])
        self.assertEqual(original_receipt, record.read_bytes())

    def test_legacy_receipt_blocks_new_install_then_public_cleanup_preserves_other_registrations(self) -> None:
        target, record, original_receipt = self.install_legacy_receipt_fixture()
        with patch.object(animation, "inspect_bundle") as inspect:
            with self.assertRaisesRegex(common.IntegrationError, "legacy startup-animation test install.*test-uninstall"):
                animation.test_install_plan(self.agent_source, self.snapshot / "unused-payload", self.workspace,
                                            hub_root=self.hub)
            inspect.assert_not_called()
        self.assertEqual(original_receipt, record.read_bytes())
        self.assertEqual("startup-animation", common.read_receipt(record)["component"])

        production = str(self.base / "production" / animation.APP_NAME)
        unrelated = str(self.base / "other-project" / "Other.app")
        registry = {name: [] for name in animation.REGISTRY_IDS}
        registry[animation.REGISTRY_IDS[0]] = sorted([str(target), production])
        registry[animation.REGISTRY_IDS[1]] = [unrelated]
        commands = []

        def inventory(_tool: Path) -> dict[str, list[str]]:
            return {name: list(paths) for name, paths in registry.items()}

        def native(command: list[str], **_options: object) -> dict[str, object]:
            commands.append(command)
            if command[0] == animation.LSREGISTER:
                self.assertEqual([animation.LSREGISTER, "-u", str(target)], command)
                registry[animation.REGISTRY_IDS[0]].remove(str(target))
            else:
                self.assertEqual(["/bin/ps", "-axo", "pid=,comm="], command)
            return {"command": command, "returncode": 0, "stdout": "", "stderr": ""}

        with patch.object(animation, "_registry_inventory", side_effect=inventory), \
                patch.object(animation, "_run", side_effect=native):
            plan = animation.test_uninstall_plan(self.agent_source, self.workspace, hub_root=self.hub)
            self.assertEqual("startup-animation", plan["target"]["source"]["component"])
            result = animation.test_uninstall(self.agent_source, self.workspace, plan["plan_id"], hub_root=self.hub)

        self.assertEqual("test-uninstalled", result["status"])
        self.assertEqual([production], result["registry_after"][animation.REGISTRY_IDS[0]])
        self.assertEqual([unrelated], result["registry_after"][animation.REGISTRY_IDS[1]])
        self.assertFalse(target.exists())
        self.assertFalse(record.exists())
        self.assertEqual(1, sum(command[0] == animation.LSREGISTER for command in commands))

    def test_apply_rechecks_legacy_owner_before_committing_new_test_install(self) -> None:
        payload = self.snapshot / ".build/azhou-payload"
        payload.mkdir(parents=True)
        (payload / "bundle-data").write_text("new Agent Skin bundle", encoding="utf-8")
        workspace = self.base / "race-workspace"
        target, record = animation._test_paths(workspace)
        legacy_target, legacy_record = animation._test_paths(workspace, "startup-animation")

        with patch.object(animation, "inspect_bundle", side_effect=lambda source, bundle, **_kwargs: {
                "path": str(bundle), "sha256_tree": "bundle digest", "native_source_root": str(self.snapshot),
                "source": {"source": str(source), "source_lock_sha256": "source digest"}}):
            plan = animation.test_install_plan(self.agent_source, payload, workspace, hub_root=self.hub)

            original_copytree = animation.shutil.copytree

            def copy_then_add_legacy_owner(source: Path, destination: Path, **kwargs: object) -> None:
                original_copytree(source, destination, **kwargs)
                legacy_target.mkdir(parents=True)
                common.write_receipt(legacy_record, {
                    "schema": "azhou-hub.animation-test-install.v1", "component": "startup-animation",
                    "path": str(legacy_target), "sha256_tree": "old receipt digest",
                    "source_lock_sha256": "old source digest",
                })

            with patch.object(animation.shutil, "copytree", side_effect=copy_then_add_legacy_owner):
                with self.assertRaisesRegex(common.IntegrationError, "legacy startup-animation test install.*test-uninstall"):
                    animation.test_install(self.agent_source, payload, workspace, plan["plan_id"], hub_root=self.hub)

        self.assertTrue(legacy_target.is_dir())
        self.assertEqual("startup-animation", common.read_receipt(legacy_record)["component"])
        self.assertFalse(target.exists())
        self.assertFalse(record.exists())
        self.assertEqual([], list(target.parent.glob(".test-install-*")))

    def test_a_plan_reviewed_under_the_legacy_package_name_cannot_build_agent_skin(self) -> None:
        assets = self.base / "private-inputs"
        assets.mkdir()
        for name in animation.PRIVATE_FILES:
            (assets / name).parent.mkdir(parents=True, exist_ok=True)
            (assets / name).write_bytes(("private fixture " + name).encode("utf-8"))
        plan_workspace = self.base / "reviewed-plan-workspace"

        current_component = animation.COMPONENT
        try:
            animation.COMPONENT = animation.LEGACY_COMPONENT
            legacy_plan = animation.build_plan(self.legacy_source, plan_workspace, assets, hub_root=self.hub)
        finally:
            animation.COMPONENT = current_component

        output = io.StringIO()
        with redirect_stdout(output):
            status = animation.main(
                ["build", "--workspace", str(plan_workspace), "--private-assets", str(assets),
                 "--apply", "--plan-id", legacy_plan["plan_id"]],
                hub_root=self.hub,
            )

        self.assertEqual(1, status)
        result = json.loads(output.getvalue())
        self.assertEqual("blocked", result["status"])
        self.assertIn("exact current plan_id", result["error"])
        self.assertFalse(plan_workspace.exists())


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
            self.event("preview-result", error=""),
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


if __name__ == "__main__":
    unittest.main()
