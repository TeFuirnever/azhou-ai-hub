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


if __name__ == "__main__":
    unittest.main()
