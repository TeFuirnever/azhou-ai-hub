"""Failure/ownership checks for the animation boundary; native macOS evidence is separate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from package_fixture import configure_package
from scripts import integration_common as common
from scripts import integration_startup_animation as animation


class AnimationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.hub = self.base / "hub"
        self.assets = self.base / "private"
        self.workspace = self.base / "isolated"
        self.source = configure_package(self.hub, animation.COMPONENT,
            [".gitignore", "Native/App.swift", "tools/verify-artifacts.py"],
            build_inputs=["Native/App.swift"], runtime_version="0.7.0", runtime_build="7")
        for name in (".gitignore", "Native/App.swift", "tools/verify-artifacts.py"):
            file = self.source / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("fixture input " + name, encoding="utf-8")
        for name in animation.PRIVATE_FILES:
            file = self.assets / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(("private fixture " + name).encode("utf-8"))
        self.snapshot = self.base / "frozen-snapshot"
        self.snapshot.mkdir(parents=True)
        common.write_receipt(self.snapshot / ".hub-source.json",
            {"schema": "azhou-hub.integration-snapshot.v1", "source": str(self.source)})
        self.payload = self.snapshot / ".build/azhou-payload"
        (self.payload / "Contents/MacOS").mkdir(parents=True)
        (self.payload / "Contents/MacOS/AzhouCodexStartup").write_text("fake executable", encoding="utf-8")
        helper = self.snapshot / ".build/azhou-install-registry"
        helper.write_text("fake registry helper", encoding="utf-8")
        helper.chmod(0o700)
        self.production_path = str(self.base / "production" / animation.APP_NAME)
        self.registry = {name: [] for name in animation.REGISTRY_IDS}
        self.registry[animation.REGISTRY_IDS[0]] = [self.production_path]
        registry_patcher = patch.object(animation, "_registry_inventory",
            side_effect=lambda _tool: {key: list(value) for key, value in self.registry.items()})
        registry_patcher.start()
        self.addCleanup(registry_patcher.stop)

    def fake_inspect(self, source, bundle, *, hub_root, _cleanup_snapshot_only=False):
        origin = common.inspect_source(animation.COMPONENT, source, hub_root=hub_root)
        if bundle.is_symlink() or not bundle.is_dir():
            raise common.IntegrationError("invalid fixture bundle")
        digest = hashlib.sha256()
        for path in sorted(bundle.rglob("*")):
            if path.is_symlink():
                raise common.IntegrationError("fixture symlink")
            if path.is_file():
                digest.update(path.relative_to(bundle).as_posix().encode("utf-8"))
                digest.update(path.read_bytes())
        return {"path": str(bundle), "sha256_tree": digest.hexdigest(), "native_source_root": str(self.snapshot), "source": origin}

    def install(self):
        plan = animation.test_install_plan(self.source, self.payload, self.workspace, hub_root=self.hub)
        return animation.test_install(self.source, self.payload, self.workspace, plan["plan_id"], hub_root=self.hub)

    def test_build_cli_defaults_to_canonical_package_without_source_flag(self):
        from contextlib import redirect_stdout
        import io

        output = io.StringIO()
        with redirect_stdout(output):
            result = animation.main(["build", "--workspace", str(self.workspace), "--private-assets", str(self.assets)],
                                    hub_root=self.hub)
        self.assertEqual(0, result)
        plan = json.loads(output.getvalue())
        self.assertEqual(str(self.source), plan["source"]["source"])
        self.assertFalse(self.workspace.exists())

    def owned_snapshot_fixture(self):
        snapshot = common.snapshot_source(animation.COMPONENT, self.source, self.workspace, hub_root=self.hub)
        target, record = animation._test_paths(self.workspace)
        target.mkdir(parents=True)
        lock = common.load_lock(animation.COMPONENT, hub_root=self.hub)
        inputs = {"Native/App.swift": lock["files"]["Native/App.swift"]["sha256"]}
        for name in ("index.html", "style.css", "animation.js", "assets/private/working.png", "assets/private/scene.js"):
            file = target / "Contents/Resources/web" / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("installed fixture " + name, encoding="utf-8")
            inputs[name] = hashlib.sha256(file.read_bytes()).hexdigest()
        marker = {"projectRoot": str(snapshot), "inputs": inputs, "inputSHA256": "fixture inputs"}
        (target / "Contents/Resources/azhou-build.json").write_text(json.dumps(marker), encoding="utf-8")
        helper = snapshot / ".build/azhou-install-registry"
        helper.parent.mkdir()
        helper.write_text("built registry fixture", encoding="utf-8")
        helper.chmod(0o700)
        def fingerprint(bundle):
            digest = hashlib.sha256()
            for file in sorted(bundle.rglob("*")):
                if file.is_file():
                    digest.update(file.relative_to(bundle).as_posix().encode("utf-8"))
                    digest.update(file.read_bytes())
            return digest.hexdigest()
        common.write_receipt(record, {"schema": "azhou-hub.animation-test-install.v1", "component": animation.COMPONENT,
            "path": str(target), "sha256_tree": fingerprint(target), "source_lock_sha256": common.plan_digest(lock)})
        info = {"CFBundleIdentifier": animation.REGISTRY_IDS[0], "CFBundleExecutable": animation.EXECUTABLE,
                "CFBundleShortVersionString": "0.7.0", "CFBundleVersion": "7"}
        native = {"verify_product": lambda _bundle: info, "read_marker": lambda _bundle, **_kw: marker,
                  "fingerprint": fingerprint}
        return snapshot, target, record, native

    def test_build_plan_does_not_write_and_private_changes_invalidate_plan(self):
        first = animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)
        self.assertFalse(self.workspace.exists())
        (self.assets / "working.png").write_bytes(b"changed")
        second = animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)
        self.assertNotEqual(first["plan_id"], second["plan_id"])
        with patch.object(animation, "_run") as run:
            with self.assertRaisesRegex(common.IntegrationError, "plan_id"):
                animation.build(self.source, self.workspace, self.assets, first["plan_id"], hub_root=self.hub)
            run.assert_not_called()

    def test_missing_private_asset_fails_without_workspace_write(self):
        (self.assets / "scene.js").unlink()
        with self.assertRaisesRegex(common.IntegrationError, "ordinary file missing"):
            animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)
        self.assertFalse(self.workspace.exists())

    def test_package_edit_is_valid_but_stales_reviewed_build_before_native_execution(self):
        plan = animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)
        (self.source / "Native/App.swift").write_text("concurrent change", encoding="utf-8")
        fresh = animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)
        self.assertNotEqual(plan["plan_id"], fresh["plan_id"])
        with patch.object(animation, "_mac") as native, patch.object(animation, "_run") as run:
            with self.assertRaisesRegex(common.IntegrationError, "exact current plan_id|regenerate"):
                animation.build(self.source, self.workspace, self.assets, plan["plan_id"], hub_root=self.hub)
            native.assert_not_called()
            run.assert_not_called()
        self.assertFalse(self.workspace.exists())

    def test_package_change_after_build_plan_check_is_rejected_before_native_execution(self):
        plan = animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)
        snapshot_source = common.snapshot_source
        mutated = []

        def mutate_then_snapshot(component, source, workspace, *, hub_root, expected_digest=None):
            (self.source / "Native/App.swift").write_text("unreviewed source input", encoding="utf-8")
            mutated.append(True)
            return snapshot_source(component, source, workspace, hub_root=hub_root, expected_digest=expected_digest)

        with patch.object(animation, "_mac") as native, patch.object(animation.os, "access", return_value=True), \
                patch.object(animation, "_run") as run, patch.object(common, "snapshot_source", side_effect=mutate_then_snapshot):
            with self.assertRaisesRegex(common.IntegrationError, "changed after the reviewed plan"):
                animation.build(self.source, self.workspace, self.assets, plan["plan_id"], hub_root=self.hub)
            native.assert_called_once()
            run.assert_not_called()

        self.assertEqual([True], mutated)
        self.assertFalse(self.workspace.exists())
        self.assertFalse(Path(plan["snapshot"]).exists())

    def test_native_build_cannot_substitute_an_unapproved_private_input(self):
        plan = animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)
        original = (self.assets / "working.png").read_bytes()
        def native(command, *, cwd=None, timeout=90):
            if command == ["bash", "tools/build-macos.sh"]:
                (cwd / "assets/private/working.png").write_bytes(b"changed after approval")
                payload = cwd / ".build/azhou-payload"
                marker = payload / "Contents/Resources/azhou-build.json"
                marker.parent.mkdir(parents=True)
                inputs = {"assets/private/" + name: hashlib.sha256((cwd / "assets/private" / name).read_bytes()).hexdigest()
                          for name in animation.PRIVATE_FILES}
                marker.write_text(json.dumps({"inputs": inputs}), encoding="utf-8")
            return {"command": command, "returncode": 0, "stdout": "native build completed", "stderr": ""}
        with patch.object(animation, "_mac"), patch.object(animation.os, "access", return_value=True), \
                patch.object(animation, "_run", side_effect=native), \
                patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            with self.assertRaisesRegex(common.IntegrationError, "built private input differs from the approved plan: working.png"):
                animation.build(self.source, self.workspace, self.assets, plan["plan_id"], hub_root=self.hub)
        self.assertEqual(original, (self.assets / "working.png").read_bytes())
        record = common.read_receipt(Path(plan["snapshot"]) / ".hub-build.json")
        self.assertEqual("failed-validation", record["status"])
        self.assertNotIn("approved_private_inputs_verified", record)

    def test_private_symlink_and_source_workspace_are_refused(self):
        with self.assertRaisesRegex(common.IntegrationError, "outside"):
            animation.build_plan(self.source, self.source / "build", self.assets, hub_root=self.hub)
        file = self.assets / "scene.js"
        file.unlink()
        file.symlink_to(self.assets / "working.png")
        with self.assertRaisesRegex(common.IntegrationError, "symlink"):
            animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)

    def test_test_install_is_repeatable_and_uninstall_preserves_unrelated_files(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            first = self.install()
            self.assertEqual("test-installed", first["status"])
            self.assertEqual("current", self.install()["status"])
            sentinel = self.workspace / "keep.txt"
            sentinel.write_text("user data", encoding="utf-8")
            plan = animation.test_uninstall_plan(self.source, self.workspace, hub_root=self.hub)
            with patch.object(animation, "_run", return_value={"returncode": 0, "stdout": "", "stderr": ""}):
                result = animation.test_uninstall(self.source, self.workspace, plan["plan_id"], hub_root=self.hub)
            self.assertEqual("test-uninstalled", result["status"])
            self.assertEqual("user data", sentinel.read_text(encoding="utf-8"))
            self.assertTrue(self.payload.exists())

    def test_isolated_private_symlink_cannot_escape_to_another_directory(self):
        snapshot = common.snapshot_source(animation.COMPONENT, self.source, self.workspace, hub_root=self.hub)
        outside = self.base / "outside"
        outside.mkdir()
        (snapshot / "assets").symlink_to(outside, target_is_directory=True)
        plan = animation.build_plan(self.source, self.workspace, self.assets, hub_root=self.hub)
        with patch.object(animation, "_mac"), patch.object(animation.os, "access", return_value=True), patch.object(animation, "_run") as run:
            with self.assertRaisesRegex(common.IntegrationError, "isolated private asset path is a symlink"):
                animation.build(self.source, self.workspace, self.assets, plan["plan_id"], hub_root=self.hub)
            run.assert_not_called()
        self.assertEqual([], list(outside.iterdir()))

    def test_unowned_or_modified_test_app_is_never_overwritten_or_removed(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            self.install()
            target, receipt = animation._test_paths(self.workspace)
            (target / "user-file.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(common.IntegrationError, "preserve"):
                animation.test_install_plan(self.source, self.payload, self.workspace, hub_root=self.hub)
            with self.assertRaisesRegex(common.IntegrationError, "preserved"):
                animation.test_uninstall_plan(self.source, self.workspace, hub_root=self.hub)
            receipt.unlink()
            with self.assertRaisesRegex(common.IntegrationError, "cannot read receipt"):
                animation.test_install_plan(self.source, self.payload, self.workspace, hub_root=self.hub)
            self.assertEqual("keep", (target / "user-file.txt").read_text(encoding="utf-8"))

    def test_test_install_cannot_write_in_read_only_source(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            with self.assertRaisesRegex(common.IntegrationError, "outside the read-only source"):
                animation.test_install_plan(self.source, self.payload, self.source, hub_root=self.hub)
            with self.assertRaisesRegex(common.IntegrationError, "outside the read-only source"):
                animation.test_install_plan(self.source, self.payload, self.source / "another/../.", hub_root=self.hub)
        self.assertFalse((self.source / ".azhou").exists())

    def test_failed_test_copy_leaves_no_install_or_receipt(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            plan = animation.test_install_plan(self.source, self.payload, self.workspace, hub_root=self.hub)
            with patch.object(animation.shutil, "copytree", side_effect=OSError("copy failed")):
                with self.assertRaisesRegex(OSError, "copy failed"):
                    animation.test_install(self.source, self.payload, self.workspace, plan["plan_id"], hub_root=self.hub)
            target, record = animation._test_paths(self.workspace)
            self.assertFalse(target.exists())
            self.assertFalse(record.exists())
            self.assertEqual([], list(target.parent.iterdir()))

    def test_running_test_app_prevents_removal(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            self.install()
            target, record = animation._test_paths(self.workspace)
            plan = animation.test_uninstall_plan(self.source, self.workspace, hub_root=self.hub)
            process = {"returncode": 0, "stdout": f"123 {target}/Contents/MacOS/AzhouCodexStartup\n", "stderr": ""}
            with patch.object(animation, "_run", return_value=process):
                with self.assertRaisesRegex(common.IntegrationError, "still running"):
                    animation.test_uninstall(self.source, self.workspace, plan["plan_id"], hub_root=self.hub)
            self.assertTrue(target.exists())
            self.assertTrue(record.exists())

    def test_test_uninstall_unregisters_only_owned_path_and_preserves_production(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            self.install()
            target, record = animation._test_paths(self.workspace)
            self.registry[animation.REGISTRY_IDS[0]].append(str(target))
            self.registry[animation.REGISTRY_IDS[0]].sort()
            plan = animation.test_uninstall_plan(self.source, self.workspace, hub_root=self.hub)
            self.assertEqual([animation.LSREGISTER, "-u", str(target)], plan["registry"]["unregister_command"])
            commands = []
            def native(command, **_options):
                commands.append(command)
                if command[0] == animation.LSREGISTER:
                    self.assertEqual([animation.LSREGISTER, "-u", str(target)], command)
                    self.registry[animation.REGISTRY_IDS[0]].remove(str(target))
                else:
                    self.assertEqual(["/bin/ps", "-axo", "pid=,comm="], command)
                return {"returncode": 0, "stdout": "", "stderr": ""}
            with patch.object(animation, "_run", side_effect=native):
                result = animation.test_uninstall(self.source, self.workspace, plan["plan_id"], hub_root=self.hub)
            self.assertEqual("test-uninstalled", result["status"])
            self.assertEqual([self.production_path], result["registry_after"][animation.REGISTRY_IDS[0]])
            self.assertEqual(1, sum(command[0] == animation.LSREGISTER for command in commands))
            self.assertFalse(target.exists())
            self.assertFalse(record.exists())

    def test_registration_cleanup_failure_preserves_test_app_and_receipt(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            self.install()
            target, record = animation._test_paths(self.workspace)
            self.registry[animation.REGISTRY_IDS[0]].append(str(target))
            self.registry[animation.REGISTRY_IDS[0]].sort()
            plan = animation.test_uninstall_plan(self.source, self.workspace, hub_root=self.hub)
            # A successful exit without an actual registry change is insufficient.
            with patch.object(animation, "_run", return_value={"returncode": 0, "stdout": "", "stderr": ""}):
                with self.assertRaisesRegex(common.IntegrationError, "registration removal did not preserve"):
                    animation.test_uninstall(self.source, self.workspace, plan["plan_id"], hub_root=self.hub)
            self.assertTrue(target.exists())
            self.assertTrue(record.exists())
            self.assertIn(self.production_path, self.registry[animation.REGISTRY_IDS[0]])

    def test_unexpected_other_registration_change_is_not_reported_as_success(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            self.install()
            target, record = animation._test_paths(self.workspace)
            self.registry[animation.REGISTRY_IDS[0]].append(str(target))
            self.registry[animation.REGISTRY_IDS[0]].sort()
            plan = animation.test_uninstall_plan(self.source, self.workspace, hub_root=self.hub)
            def wrong_scope(command, **_options):
                if command[0] == animation.LSREGISTER:
                    self.registry[animation.REGISTRY_IDS[0]] = []
                return {"returncode": 0, "stdout": "", "stderr": ""}
            with patch.object(animation, "_run", side_effect=wrong_scope):
                with self.assertRaisesRegex(common.IntegrationError, "registration removal did not preserve"):
                    animation.test_uninstall(self.source, self.workspace, plan["plan_id"], hub_root=self.hub)
            self.assertTrue(target.exists())
            self.assertTrue(record.exists())

    def test_owned_cleanup_uses_frozen_snapshot_after_live_package_edit_and_removal(self):
        snapshot, target, record, native = self.owned_snapshot_fixture()
        recorded_manifest = common.snapshot_lock(animation.COMPONENT, snapshot)
        (self.source / "Native/App.swift").write_text("another session's new source", encoding="utf-8")
        self.assertNotEqual(recorded_manifest, common.load_lock(animation.COMPONENT, hub_root=self.hub))
        self.registry[animation.REGISTRY_IDS[0]].append(str(target))
        self.registry[animation.REGISTRY_IDS[0]].sort()

        def run(command, **_options):
            if command[0] == animation.LSREGISTER:
                self.assertEqual([animation.LSREGISTER, "-u", str(target)], command)
                self.registry[animation.REGISTRY_IDS[0]].remove(str(target))
            return {"returncode": 0, "stdout": "", "stderr": ""}
        with patch.object(animation.runpy, "run_path", return_value=native) as loader:
            self.assertEqual(recorded_manifest, common.snapshot_lock(animation.COMPONENT, snapshot))
            self.assertEqual(str(snapshot), common.verify_snapshot(animation.COMPONENT, snapshot)["snapshot"])
            plan = animation.test_uninstall_plan(self.source, self.workspace, hub_root=self.hub)
            self.assertEqual("another session's new source", (self.source / "Native/App.swift").read_text(encoding="utf-8"))
            shutil.rmtree(self.source)
            with patch.object(animation, "_run", side_effect=run):
                result = animation.test_uninstall(self.source, self.workspace, plan["plan_id"], hub_root=self.hub)
            self.assertTrue(all(call.args[0] == str(snapshot / "tools/verify-artifacts.py") for call in loader.call_args_list))
        self.assertEqual("test-uninstalled", result["status"])
        self.assertFalse(target.exists())
        self.assertFalse(record.exists())
        self.assertEqual([self.production_path], self.registry[animation.REGISTRY_IDS[0]])
        self.assertFalse(self.source.exists())

    def test_owned_cleanup_rejects_tampered_frozen_snapshot(self):
        snapshot, target, record, native = self.owned_snapshot_fixture()
        (snapshot / "Native/App.swift").write_text("untrusted snapshot edit", encoding="utf-8")
        with patch.object(animation.runpy, "run_path", return_value=native) as loader, patch.object(animation, "_run") as run:
            with self.assertRaisesRegex(common.IntegrationError, "content drift"):
                animation.test_uninstall_plan(self.source, self.workspace, hub_root=self.hub)
            loader.assert_not_called()
            run.assert_not_called()
        self.assertTrue(target.exists())
        self.assertTrue(record.exists())

    def test_install_plan_rejects_payload_from_stale_snapshot_without_host_side_effects(self):
        snapshot, target, record, native = self.owned_snapshot_fixture()
        recorded_manifest = common.snapshot_lock(animation.COMPONENT, snapshot)
        payload = snapshot / ".build/azhou-payload"
        shutil.copytree(target, payload)
        payload_fingerprint = native["fingerprint"](payload)
        record_before = record.read_bytes()
        registry_before = {name: list(paths) for name, paths in self.registry.items()}
        (self.source / "Native/App.swift").write_text("new live package input", encoding="utf-8")
        self.assertNotEqual(recorded_manifest, common.load_lock(animation.COMPONENT, hub_root=self.hub))

        with patch.object(animation.runpy, "run_path", return_value=native) as loader, patch.object(animation, "_run") as run:
            with self.assertRaisesRegex(common.IntegrationError, "different package inputs"):
                animation.inspect_bundle(self.source, payload, hub_root=self.hub)
            with self.assertRaisesRegex(common.IntegrationError, "different package inputs"):
                animation.test_install_plan(self.source, payload, self.workspace, hub_root=self.hub)
            loader.assert_not_called()
            run.assert_not_called()

        self.assertEqual(recorded_manifest, common.snapshot_lock(animation.COMPONENT, snapshot))
        self.assertEqual(payload_fingerprint, native["fingerprint"](payload))
        self.assertEqual(record_before, record.read_bytes())
        self.assertEqual(registry_before, self.registry)
        self.assertTrue(target.exists())

    def test_install_plan_rejects_a_payload_built_directly_in_the_live_package(self):
        snapshot, target, record, native = self.owned_snapshot_fixture()
        payload = self.base / "direct-payload"
        shutil.copytree(target, payload)
        marker_path = payload / "Contents/Resources/azhou-build.json"
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["projectRoot"] = str(self.source)
        marker_path.write_text(json.dumps(marker), encoding="utf-8")
        record_before = record.read_bytes()
        registry_before = {name: list(paths) for name, paths in self.registry.items()}

        with patch.object(animation.runpy, "run_path", return_value=native), patch.object(animation, "_run") as run:
            inspected = animation.inspect_bundle(self.source, payload, hub_root=self.hub)
            self.assertEqual(str(self.source), inspected["native_source_root"])
            with self.assertRaisesRegex(common.IntegrationError, "frozen build snapshot"):
                animation.test_install_plan(self.source, payload, self.workspace, hub_root=self.hub)
            run.assert_not_called()

        self.assertEqual(record_before, record.read_bytes())
        self.assertEqual(registry_before, self.registry)
        self.assertTrue(target.exists())

    def test_install_plan_rejects_identical_package_from_a_different_checkout(self):
        snapshot, target, record, native = self.owned_snapshot_fixture()
        payload = snapshot / ".build/azhou-payload"
        shutil.copytree(target, payload)

        hub_b = self.base / "hub-b"
        source_b = hub_b / "packages" / common.PACKAGES[animation.COMPONENT]
        source_b.parent.mkdir(parents=True)
        shutil.copytree(self.source, source_b)
        origin_a = common.inspect_source(animation.COMPONENT, self.source, hub_root=self.hub)
        origin_b = common.inspect_source(animation.COMPONENT, source_b, hub_root=hub_b)
        self.assertEqual(origin_a["source_lock_sha256"], origin_b["source_lock_sha256"])
        self.assertNotEqual(origin_a["source"], origin_b["source"])
        self.assertEqual(str(self.source), common.read_receipt(snapshot / ".hub-source.json")["source"])

        workspace_b = self.base / "hub-b-workspace"
        registry_before = {name: list(paths) for name, paths in self.registry.items()}
        with patch.object(animation.runpy, "run_path", return_value=native) as loader, patch.object(animation, "_run") as run:
            with self.assertRaisesRegex(common.IntegrationError, "different package checkout"):
                animation.inspect_bundle(source_b, payload, hub_root=hub_b)
            with self.assertRaisesRegex(common.IntegrationError, "different package checkout"):
                animation.test_install_plan(source_b, payload, workspace_b, hub_root=hub_b)
            loader.assert_not_called()
            run.assert_not_called()

        self.assertFalse(workspace_b.exists())
        self.assertTrue(payload.exists())
        self.assertTrue(target.exists())
        self.assertTrue(record.exists())
        self.assertEqual(registry_before, self.registry)

    def test_successful_exit_without_player_events_is_not_behavior_success(self):
        result = animation.assess_execution("smoke", {"returncode": 0, "stdout": "", "stderr": ""}, self.payload)
        self.assertEqual("behavior-not-proven", result["status"])

    def test_complete_player_evidence_rejects_wrong_path_or_host_launch(self):
        events = [{"event": name, "launcherPath": str(self.payload)} for name in
                  ("player-start", "playback-start", "animation-complete", "preview-result", "player-terminated")]
        events[-1].update(completed=True, failed=False)
        def assess(items):
            return animation.assess_execution("smoke", {"returncode": 0, "stdout": "\n".join(json.dumps(x) for x in items), "stderr": ""}, self.payload)
        self.assertEqual("behavior-passed", assess(events)["status"])
        self.assertEqual("behavior-not-proven", assess(events + [{"event": "target-reused", "launcherPath": str(self.payload)}])["status"])
        events[1]["launcherPath"] = "/another/app"
        self.assertEqual("behavior-not-proven", assess(events)["status"])

    def test_native_plan_exposes_blocker_and_never_executes_installer(self):
        with patch.object(animation, "_run") as run:
            result = animation.native_plan(self.source, "install", hub_root=self.hub)
        run.assert_not_called()
        self.assertEqual("blocked_source_contract", result["status"])
        self.assertIn("no alternate destination", result["blockers"][0])

    def test_launcher_and_wallpaper_results_are_independent(self):
        events = [{"event": name, "launcherPath": str(self.payload)} for name in
                  ("player-start", "playback-start", "animation-complete", "target-reused",
                   "target-activation-request", "handoff-fade-complete", "player-terminated")]
        events[-1].update(completed=True, failed=False)
        events[4]["allowed"] = True
        def assess(extra):
            return animation.assess_execution("launch", {"returncode": 0,
                "stdout": "\n".join(json.dumps(x) for x in events + extra), "stderr": ""}, self.payload)
        missing = assess([])
        self.assertEqual("behavior-passed", missing["launcher_status"])
        self.assertEqual("not-attempted", missing["wallpaper_status"])
        self.assertEqual("partial", missing["status"])
        for native_state, status in (("needs-restart", "needs-restart"), ("connection-failed", "failed"),
                                     ("not-applied", "not-applied"), ("pending", "pending")):
            result = assess([{"event": "wallpaper-helper-complete", "launcherPath": str(self.payload),
                              "result": {"state": native_state, "applied": False}}])
            self.assertEqual("behavior-passed", result["launcher_status"])
            self.assertEqual(status, result["wallpaper_status"])
            self.assertEqual("partial", result["status"])
        applied = assess([{"event": "wallpaper-helper-complete", "launcherPath": str(self.payload),
                           "result": {"state": "applied", "applied": True}}])
        self.assertEqual("runtime-events-passed", applied["status"])
        self.assertEqual("reported-applied", applied["wallpaper_status"])
        self.assertEqual("not performed", applied["wallpaper_evidence"]["live_status_check"])
        self.assertEqual("pending", applied["visual_review"])

    def test_launch_exposes_wallpaper_scope_and_restore_requires_explicit_target(self):
        with patch.object(animation, "inspect_bundle", side_effect=self.fake_inspect):
            plan = animation.execution_plan(self.source, self.payload, "launch", hub_root=self.hub)
            self.assertIn("wallpaper", plan["scope"])
            with self.assertRaisesRegex(common.IntegrationError, "explicit positive target PID"):
                animation.execution_plan(self.source, self.payload, "disable-wallpaper", hub_root=self.hub)


if __name__ == "__main__":
    unittest.main()
