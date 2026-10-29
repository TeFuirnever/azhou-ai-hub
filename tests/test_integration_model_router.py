"""Adapter ownership/rollback tests with a synthetic native API, never inference.

The fixed source's independent tests and on-device discovery validate its native
installer; these tests exercise the Hub boundary and deliberately wrong inputs.
The pstack compatibility verdict is the Kit's real shipped implementation, so
Hub-boundary tests judge targets exactly as the Kit's direct entry does.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

from package_fixture import configure_package
from scripts import integration_common as common
from scripts import integration_model_router as adapter


def _load_real_installer():
    path = Path(__file__).resolve().parents[1] / "packages/agent-orchestration-kit/scripts/install_codex.py"
    spec = importlib.util.spec_from_file_location("model_router_real_install_codex", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REAL_INSTALLER = _load_real_installer()


class FakeInstaller:
    PROFILE = "test-profile"
    ROLE_MODELS = {"worker": ("test-model", "high")}
    SETTINGS = {"model": "test-root"}
    verified_roots = []
    mode_ledger: dict[Path, int] = {}
    mode_stat_baselines: dict[Path, int] = {}
    use_virtual_modes = os.name == "nt"

    @staticmethod
    def check_parents(path):
        if any(p.is_symlink() for p in path.parents):
            raise RuntimeError("symlink ancestor")

    @staticmethod
    def regular_bytes(path):
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise RuntimeError("unsafe file")
        return path.read_bytes() if path.exists() else None

    @classmethod
    def file_mode(cls, path):
        path = Path(path)
        if cls.use_virtual_modes:
            if path not in cls.mode_ledger:
                return None
            observed = stat.S_IMODE(path.stat().st_mode)
            if observed != cls.mode_stat_baselines.get(path):
                return None
            return cls.mode_ledger[path]
        return stat.S_IMODE(path.stat().st_mode)

    @classmethod
    def set_mode(cls, path, mode):
        path = Path(path)
        path.chmod(mode)
        cls.mode_ledger[path] = stat.S_IMODE(mode)
        cls.mode_stat_baselines[path] = stat.S_IMODE(path.stat().st_mode)

    @staticmethod
    def pstack_coexistence(codex_home, skills_dir=None):
        return REAL_INSTALLER.pstack_coexistence(codex_home, skills_dir)

    @classmethod
    def build_plan(cls, source, home, skills):
        cls.verified_roots.append(source)
        # A schema-1 ownership record like the real installer's, so coexistence
        # diagnosis recognizes this target as a Kit installation.
        manifest = {
            "schema": 1,
            "project": "agent-orchestration-kit",
            "targets": {"agents/worker.toml": str(home / "agents/worker.toml"),
                        "skill": str(skills / "astra-orchestrator/SKILL.md")},
            "files": {"agents/worker.toml": "fixture", "skill": "fixture"},
        }
        desired = {home / "config.toml": b'model = "test-root"\n',
                   home / "AGENTS.md": b"test instructions\n",
                   home / "agent-orchestration-kit/state.json": json.dumps(manifest, sort_keys=True).encode() + b"\n",
                   home / "agents/worker.toml": b'model = "test-model"\n',
                   skills / "astra-orchestrator/SKILL.md": b"test skill\n"}
        watched = {p: cls.regular_bytes(p) for p in desired}
        return {"changes": {p: raw for p, raw in desired.items() if watched[p] != raw},
                "watched": watched, "config_text": desired[home / "config.toml"].decode("utf-8"),
                "roles": {"worker": desired[home / "agents/worker.toml"]},
                "skill_path": skills / "astra-orchestrator/SKILL.md"}

    @classmethod
    def apply_plan(cls, plan, verify):
        originals = {}
        for path in plan["changes"]:
            before = cls.regular_bytes(path)
            mode = cls.file_mode(path) if before is not None else 0o600
            if before is not None and mode is None:
                # An unregistered virtual mode carries no test evidence; keep
                # the actual stat value instead of inventing a private mode.
                mode = stat.S_IMODE(path.stat().st_mode)
            originals[path] = (before, mode)
        try:
            for path, data in plan["changes"].items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                cls.set_mode(path, originals[path][1])
            verify()
        except BaseException:
            for path, (raw, mode) in originals.items():
                if raw is None:
                    path.unlink(missing_ok=True)
                    cls.mode_ledger.pop(path, None)
                    cls.mode_stat_baselines.pop(path, None)
                else:
                    path.write_bytes(raw)
                    cls.set_mode(path, mode)
            raise
        return len(plan["changes"])

    @classmethod
    def restore(cls, journal, transaction):
        for item in journal["files"]:
            raw = cls.regular_bytes(Path(item["path"]))
            before = base64.b64decode(item["before"]) if item["before"] is not None else None
            if raw != before and (raw is None or hashlib.sha256(raw).hexdigest() != item["after_sha256"]):
                raise RuntimeError("concurrent edit prevents native rollback")
        for item in reversed(journal["files"]):
            path = Path(item["path"])
            if item["before"] is None:
                path.unlink(missing_ok=True)
                cls.mode_ledger.pop(path, None)
                cls.mode_stat_baselines.pop(path, None)
            else:
                path.write_bytes(base64.b64decode(item["before"]))
                cls.set_mode(path, item["mode"])
        shutil.rmtree(transaction)


def patch_fake_installer_mode_fingerprints(test_case):
    """Use test-owned modes only on Windows; always keep real target checks."""
    fingerprint = adapter._fingerprint

    def observe(path, installer):
        current = fingerprint(path, installer)
        if (installer is FakeInstaller and current["sha256"] is not None
                and FakeInstaller.use_virtual_modes and Path(path) in FakeInstaller.mode_ledger):
            virtual_mode = FakeInstaller.file_mode(path)
            if virtual_mode is not None:
                current["mode"] = virtual_mode
        return current

    patcher = patch.object(adapter, "_fingerprint", side_effect=observe)
    patcher.start()
    test_case.addCleanup(patcher.stop)


class FakeNative:
    fail = False
    discovery_cwds = []

    @staticmethod
    def select_runtime(path):
        return {"path": path, "version": "synthetic-runtime"}

    @staticmethod
    def preflight_runtime(runtime):
        pass

    @staticmethod
    def validate_config(runtime, config, roles):
        pass

    @classmethod
    def verify_native(cls, *args):
        cls.discovery_cwds.append(args[2])
        if cls.fail:
            raise RuntimeError("synthetic native discovery failure")
        return {"inference_requests": 0, "fixture": True}


class ModelRouterBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.hub = self.base / "hub"
        self.source = configure_package(self.hub, "model-router", [
            "scripts/install_codex.py", "scripts/codex_native.py", "profiles/azhou-balanced",
        ])
        for name in ("install_codex.py", "codex_native.py"):
            path = self.source / "scripts" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# source fixture\n", encoding="utf-8")
        profile = self.source / "profiles/azhou-balanced/AGENTS.md"
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text("# fixture profile\n", encoding="utf-8")
        self.workspace = self.base / "workspace"
        self.home = self.base / "personal/codex"
        self.skills = self.home / "skills"
        self.runtime = self.base / "codex"
        self.runtime.write_text("synthetic executable", encoding="utf-8")
        self.runtime.chmod(0o700)
        self.targets = (self.workspace, self.home, self.skills)
        FakeNative.fail = False
        FakeNative.discovery_cwds = []
        FakeInstaller.verified_roots = []
        FakeInstaller.mode_ledger = {}
        FakeInstaller.mode_stat_baselines = {}
        FakeInstaller.use_virtual_modes = os.name == "nt"
        patch_fake_installer_mode_fingerprints(self)
        patcher = patch.object(adapter, "_module", side_effect=lambda _, f, **kw: FakeInstaller if f == "install_codex.py" else FakeNative)
        patcher.start()
        self.addCleanup(patcher.stop)

    def plan(self):
        return adapter.make_plan(None, *self.targets, self.runtime, hub_root=self.hub)[0]

    def install(self):
        return adapter.apply(None, *self.targets, self.runtime, self.plan()["plan_id"], hub_root=self.hub)

    def put(self, relative, raw):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        FakeInstaller.set_mode(path, 0o640)
        return path

    def disk(self):
        return {str(p.relative_to(self.home)): (p.read_bytes(), p.stat().st_mtime_ns, stat.S_IMODE(p.stat().st_mode))
                for p in self.home.rglob("*") if p.is_file()}

    def test_plan_is_read_only_and_binds_explicit_targets(self):
        config = self.put("config.toml", b'model = "existing"\n')
        before = self.disk()
        plan = self.plan()
        self.assertEqual(before, self.disk())
        self.assertFalse(self.workspace.exists())
        self.assertEqual(plan["codex_home"], str(self.home))
        self.assertIn(str(config), plan["changes"])

    def test_cli_defaults_to_canonical_package_without_source_flag(self):
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            result = adapter.main(["plan", "--workspace", str(self.workspace), "--codex-home", str(self.home),
                                   "--skills-dir", str(self.skills), "--codex-bin", str(self.runtime), "--json"],
                                  hub_root=self.hub)
        self.assertEqual(0, result)
        plan = json.loads(output.getvalue())
        self.assertEqual(str(self.source), plan["source"])
        self.assertFalse(self.workspace.exists())

    def test_stale_plan_does_not_write_any_target(self):
        plan = self.plan()
        self.put("config.toml", b'model = "new concurrent choice"\n')
        before = self.disk()
        with self.assertRaisesRegex(common.IntegrationError, "stale"):
            adapter.apply(self.source, *self.targets, self.runtime, plan["plan_id"], hub_root=self.hub)
        self.assertEqual(before, self.disk())
        self.assertFalse(self.workspace.exists())

    def test_missing_runtime_and_package_change_stale_the_reviewed_plan_before_install(self):
        self.runtime.unlink()
        with self.assertRaisesRegex(common.IntegrationError, "executable"):
            self.plan()
        self.runtime.write_bytes(b"runtime")
        self.runtime.chmod(0o700)

        old_plan = self.plan()
        (self.source / "scripts/install_codex.py").write_bytes(b"wrong version")
        fresh_plan = self.plan()
        self.assertNotEqual(old_plan["source_lock_sha256"], fresh_plan["source_lock_sha256"])
        before = self.disk()
        with self.assertRaisesRegex(common.IntegrationError, "stale|changed"):
            adapter.apply(None, *self.targets, self.runtime, old_plan["plan_id"], hub_root=self.hub)
        self.assertEqual(before, self.disk())
        self.assertFalse(self.home.exists())
        self.assertFalse(self.workspace.exists())

    def test_package_change_after_plan_check_is_rejected_before_router_target_writes(self):
        plan = self.plan()
        before = self.disk()
        snapshot = common.snapshot_source
        mutated = []

        def mutate_then_snapshot(component, source, workspace, *, hub_root, expected_digest=None):
            (self.source / "scripts/install_codex.py").write_bytes(b"unreviewed install code")
            mutated.append(True)
            return snapshot(component, source, workspace, hub_root=hub_root, expected_digest=expected_digest)

        with patch.object(common, "snapshot_source", side_effect=mutate_then_snapshot):
            with self.assertRaisesRegex(common.IntegrationError, "changed after the reviewed plan"):
                adapter.apply(None, *self.targets, self.runtime, plan["plan_id"], hub_root=self.hub)

        self.assertEqual([True], mutated)
        self.assertEqual(before, self.disk())
        self.assertFalse(self.home.exists())
        self.assertFalse(self.workspace.exists())

    def test_armed_pstack_registration_blocks_but_sheet_or_skills_alone_do_not(self):
        config = self.put("config.toml", b'[plugins."pstack@pstack-claude"]\nenabled = true\n')
        with self.assertRaisesRegex(common.IntegrationError, "auto-routing is armed"):
            self.plan()
        config.write_bytes(b'personal = true\n')
        self.put("pstack-models.md", b"# sheet with no registration anywhere\n")
        plan = self.plan()
        self.assertEqual(plan["coexistence"]["auto_routing"], "not-armed")
        self.assertTrue(plan["coexistence"]["compatible"])
        self.put("skills/poteto-mode/SKILL.md", b"visible shared skill\n")
        plan = self.plan()
        self.assertTrue(plan["coexistence"]["shared_skills_visible"])
        self.assertEqual(plan["coexistence"]["auto_routing"], "not-armed")
        self.assertFalse(self.workspace.exists())

    def test_pstack_cached_plugin_blocks_without_off_sheet_and_passes_with_it(self):
        self.put("plugins/cache/pstack/.codex-plugin/plugin.json", b'{"name":"pstack"}')
        with self.assertRaisesRegex(common.IntegrationError, "auto-routing is armed"):
            self.plan()
        self.put("pstack-models.md", b"# pstack model configuration\nsession hook: off\n")
        plan = self.plan()
        self.assertEqual(plan["coexistence"]["auto_routing"], "off")
        self.assertIn("unknown", plan["coexistence"]["hook_trust"])

    def test_native_installs_snapshot_and_identical_repeat_preserves_files(self):
        first = self.install()
        self.assertEqual(first["actual_invocation"], "not performed")
        self.assertEqual(FakeNative.discovery_cwds, [self.workspace])
        self.assertTrue(any(".azhou" in p.parts for p in FakeInstaller.verified_roots))
        before = self.disk()
        receipt_bytes = Path(first["receipt"]).read_bytes()
        repeat = self.install()
        self.assertEqual(repeat["changed_files_count"], 0)
        self.assertEqual(before, self.disk())
        self.assertEqual(receipt_bytes, Path(first["receipt"]).read_bytes())

    def test_uninstall_restores_before_and_preserves_unrelated_or_adopted_files(self):
        original = b'model = "before"\n'
        config = self.put("config.toml", original)
        custom = self.put("agents/custom.toml", b"custom = true\n")
        adopted = self.put("skills/astra-orchestrator/SKILL.md", b"test skill\n")
        self.install()
        plan = adapter.uninstall_plan(*self.targets, hub_root=self.hub)
        result = adapter.uninstall(*self.targets, plan["plan_id"], hub_root=self.hub)
        self.assertEqual(result["status"], "restored")
        self.assertEqual(config.read_bytes(), original)
        self.assertEqual(FakeInstaller.file_mode(config), 0o640)
        self.assertEqual(custom.read_bytes(), b"custom = true\n")
        self.assertEqual(adopted.read_bytes(), b"test skill\n")
        self.assertFalse((self.home / "agents/worker.toml").exists())

    def test_changed_target_blocks_uninstall_without_touching_other_files(self):
        self.install()
        self.put("config.toml", b"personal = true\n")
        before = self.disk()
        with self.assertRaisesRegex(common.IntegrationError, "changed"):
            adapter.uninstall_plan(*self.targets, hub_root=self.hub)
        self.assertEqual(before, self.disk())

    def test_changed_mode_blocks_uninstall(self):
        self.install()
        FakeInstaller.set_mode(self.home / "agents/worker.toml", 0o644)
        with self.assertRaisesRegex(common.IntegrationError, "changed"):
            adapter.uninstall_plan(*self.targets, hub_root=self.hub)

    def test_virtual_mode_ledger_drift_blocks_uninstall(self):
        self.install()
        worker = self.home / "agents/worker.toml"
        # Simulate Windows, where stat's POSIX mode bits do not report the
        # intended private mode. The fake installer still owns explicit mode
        # evidence, so a recorded-mode change must remain a hard refusal.
        self.assertEqual(FakeInstaller.mode_ledger[worker], 0o600)
        with patch.object(FakeInstaller, "use_virtual_modes", True, create=True):
            FakeInstaller.set_mode(worker, 0o644)
            with self.assertRaisesRegex(common.IntegrationError, "changed"):
                adapter.uninstall_plan(*self.targets, hub_root=self.hub)

    def test_direct_chmod_drift_blocks_uninstall_with_virtual_mode_ledger(self):
        self.install()
        worker = self.home / "agents/worker.toml"
        with patch.object(FakeInstaller, "use_virtual_modes", True):
            before_mode = stat.S_IMODE(worker.stat().st_mode)
            worker.chmod(0o444)
            self.assertNotEqual(stat.S_IMODE(worker.stat().st_mode), before_mode)
            with self.assertRaisesRegex(common.IntegrationError, "changed"):
                adapter.uninstall_plan(*self.targets, hub_root=self.hub)

    def test_unregistered_virtual_mode_keeps_the_observed_stat_mode(self):
        path = self.home / "config.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"unregistered mode fixture\n")
        path.chmod(0o644)
        FakeInstaller.mode_ledger.clear()
        with patch.object(FakeInstaller, "use_virtual_modes", True):
            observed_mode = stat.S_IMODE(path.stat().st_mode)
            self.assertNotIn(path, FakeInstaller.mode_ledger)
            self.assertEqual(adapter._fingerprint(path, FakeInstaller)["mode"], observed_mode)

    def test_deleted_target_blocks_uninstall_with_readable_difference(self):
        self.install()
        (self.home / "config.toml").unlink()
        before = self.disk()
        with self.assertRaisesRegex(common.IntegrationError, r"mode \d+ found absent"):
            adapter.uninstall_plan(*self.targets, hub_root=self.hub)
        self.assertEqual(before, self.disk())

    def test_preexisting_unowned_restore_directory_is_preserved(self):
        result = self.install()
        receipt_path = Path(result["receipt"])
        transaction = receipt_path.parent / "restore-transaction"
        transaction.mkdir()
        unowned = transaction / "unowned.txt"
        unowned.write_bytes(b"other actor's work")
        before = self.disk()
        plan = adapter.uninstall_plan(*self.targets, hub_root=self.hub)
        with self.assertRaisesRegex(common.IntegrationError, "already exists"):
            adapter.uninstall(*self.targets, plan["plan_id"], hub_root=self.hub)
        self.assertEqual(common.read_receipt(receipt_path)["status"], "installed")
        with self.assertRaisesRegex(common.IntegrationError, "unowned"):
            adapter.recover(*self.targets, hub_root=self.hub)
        self.assertEqual(unowned.read_bytes(), b"other actor's work")
        self.assertEqual(before, self.disk())

    def test_restore_directory_symlink_is_not_followed(self):
        result = self.install()
        receipt_path = Path(result["receipt"])
        outside = self.base / "other-transaction"
        outside.mkdir()
        (outside / "unowned.txt").write_bytes(b"untouched")
        (receipt_path.parent / "restore-transaction").symlink_to(outside, target_is_directory=True)
        plan = adapter.uninstall_plan(*self.targets, hub_root=self.hub)
        with self.assertRaisesRegex(common.IntegrationError, "already exists"):
            adapter.uninstall(*self.targets, plan["plan_id"], hub_root=self.hub)
        with self.assertRaisesRegex(common.IntegrationError, "symlink"):
            adapter.recover(*self.targets, hub_root=self.hub)
        self.assertEqual((outside / "unowned.txt").read_bytes(), b"untouched")

    def interrupted_restore(self):
        result = self.install()
        plan = adapter.uninstall_plan(*self.targets, hub_root=self.hub)
        with patch.object(FakeInstaller, "restore", side_effect=RuntimeError("simulated interruption")):
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                adapter.uninstall(*self.targets, plan["plan_id"], hub_root=self.hub)
        path = Path(result["receipt"])
        self.assertEqual(common.read_receipt(path)["status"], "uninstalling")
        return path, path.parent / "restore-transaction"

    def test_recovery_rejects_extra_file_in_owned_restore_transaction(self):
        _, transaction = self.interrupted_restore()
        unowned = transaction / "unowned.txt"
        unowned.write_bytes(b"preserve")
        before = self.disk()
        with self.assertRaisesRegex(common.IntegrationError, "unowned"):
            adapter.recover(*self.targets, hub_root=self.hub)
        self.assertEqual(unowned.read_bytes(), b"preserve")
        self.assertEqual(before, self.disk())

    def test_recovery_rejects_mismatched_restore_owner(self):
        _, transaction = self.interrupted_restore()
        marker = transaction / "owner.json"
        owner = common.read_receipt(marker)
        owner["restore_plan_id"] = "0" * 64
        common.write_receipt(marker, owner)
        before = self.disk()
        with self.assertRaisesRegex(common.IntegrationError, "ownership"):
            adapter.recover(*self.targets, hub_root=self.hub)
        self.assertTrue(marker.is_file())
        self.assertEqual(before, self.disk())

    def test_verified_owned_restore_transaction_can_resume(self):
        _, transaction = self.interrupted_restore()
        result = adapter.recover(*self.targets, hub_root=self.hub)
        self.assertEqual(result["status"], "restored")
        self.assertFalse(transaction.exists())
        self.assertFalse((self.home / "agents/worker.toml").exists())

    def test_recovery_finalizes_completed_restore_without_recreating_directory(self):
        result = self.install()
        plan = adapter.uninstall_plan(*self.targets, hub_root=self.hub)
        write = common.write_receipt
        def interrupted_final_receipt(path, payload):
            if payload.get("status") == "restored":
                raise RuntimeError("simulated final receipt interruption")
            return write(path, payload)
        with patch.object(common, "write_receipt", side_effect=interrupted_final_receipt):
            with self.assertRaisesRegex(RuntimeError, "final receipt interruption"):
                adapter.uninstall(*self.targets, plan["plan_id"], hub_root=self.hub)
        transaction = Path(result["receipt"]).parent / "restore-transaction"
        self.assertFalse(transaction.exists())
        recovered = adapter.recover(*self.targets, hub_root=self.hub)
        self.assertEqual(recovered["status"], "restored")
        self.assertFalse(transaction.exists())

    def test_even_rehashed_receipt_cannot_authorize_unknown_target(self):
        result = self.install()
        path = Path(result["receipt"])
        receipt = common.read_receipt(path)
        receipt["rollback"]["files"].append({"path": str(self.base / "unowned"), "before": None})
        common.write_receipt(path, receipt)
        with self.assertRaisesRegex(common.IntegrationError, "unowned"):
            adapter.uninstall_plan(*self.targets, hub_root=self.hub)

    def test_rehashed_receipt_cannot_omit_changed_target_or_change_mode(self):
        result = self.install()
        path = Path(result["receipt"])
        original = common.read_receipt(path)
        for corruption in ("omitted", "permissions"):
            with self.subTest(corruption=corruption):
                receipt = json.loads(json.dumps(original))
                if corruption == "omitted":
                    receipt["rollback"]["files"].pop()
                else:
                    receipt["rollback"]["files"][0]["mode"] = 0o777
                common.write_receipt(path, receipt)
                before = self.disk()
                with self.assertRaises(common.IntegrationError):
                    adapter.uninstall_plan(*self.targets, hub_root=self.hub)
                self.assertEqual(before, self.disk())

    def test_native_failure_restores_existing_files_and_records_rollback(self):
        config = self.put("config.toml", b"original = true\n")
        before = config.read_bytes()
        FakeNative.fail = True
        with self.assertRaisesRegex(RuntimeError, "discovery failure"):
            self.install()
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse((self.home / "agents/worker.toml").exists())
        path = adapter._receipt_path(*self.targets)
        self.assertEqual(common.read_receipt(path)["status"], "rolled_back")

    def test_verify_does_not_claim_model_execution(self):
        self.install()
        result = adapter.verify(*self.targets, hub_root=self.hub)
        self.assertEqual(result["status"], "discovered")
        self.assertEqual(result["actual_invocation"], "not performed")
        self.assertEqual(result["native_discovery"]["inference_requests"], 0)
        self.assertEqual(FakeNative.discovery_cwds[-1], self.workspace)

    def test_recover_pending_after_success_requires_exact_native_state(self):
        result = self.install()
        path = Path(result["receipt"])
        receipt = common.read_receipt(path)
        receipt["status"] = "pending"
        common.write_receipt(path, receipt)
        recovered = adapter.recover(*self.targets, hub_root=self.hub)
        self.assertEqual(recovered["status"], "installed")
        self.assertEqual(FakeNative.discovery_cwds[-1], self.workspace)


if __name__ == "__main__":
    unittest.main()
