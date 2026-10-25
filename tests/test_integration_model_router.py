"""Adapter ownership/rollback tests with a synthetic native API, never inference.

The fixed source's independent tests and on-device discovery validate its native
installer; these tests exercise the Hub boundary and deliberately wrong inputs.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import integration_common as common
from scripts import integration_model_router as adapter


class FakeInstaller:
    PROFILE = "test-profile"
    ROLE_MODELS = {"worker": ("test-model", "high")}
    SETTINGS = {"model": "test-root"}
    verified_roots = []

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
    def build_plan(cls, source, home, skills):
        cls.verified_roots.append(source)
        desired = {home / "config.toml": b'model = "test-root"\n',
                   home / "AGENTS.md": b"test instructions\n",
                   home / "agent-orchestration-kit/state.json": b'{"owner":"native"}\n',
                   home / "agents/worker.toml": b'model = "test-model"\n',
                   skills / "astra-orchestrator/SKILL.md": b"test skill\n"}
        watched = {p: cls.regular_bytes(p) for p in desired}
        return {"changes": {p: raw for p, raw in desired.items() if watched[p] != raw},
                "watched": watched, "config_text": desired[home / "config.toml"].decode("utf-8"),
                "roles": {"worker": desired[home / "agents/worker.toml"]},
                "skill_path": skills / "astra-orchestrator/SKILL.md"}

    @classmethod
    def apply_plan(cls, plan, verify):
        originals = {p: (cls.regular_bytes(p), stat.S_IMODE(p.stat().st_mode) if p.exists() else 0o600)
                     for p in plan["changes"]}
        try:
            for path, data in plan["changes"].items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                path.chmod(originals[path][1])
            verify()
        except BaseException:
            for path, (raw, mode) in originals.items():
                if raw is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(raw)
                    path.chmod(mode)
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
            else:
                path.write_bytes(base64.b64decode(item["before"]))
                path.chmod(item["mode"])
        shutil.rmtree(transaction)


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
        self.source = self.base / "source"
        self.source.mkdir()
        (self.source / "scripts").mkdir()
        for name in ("install_codex.py", "codex_native.py"):
            (self.source / "scripts" / name).write_text("# source fixture\n", encoding="utf-8")
        def git(*args):
            return subprocess.run(["git", "-C", str(self.source), *args], check=True,
                                  capture_output=True, text=True, encoding="utf-8").stdout.strip()
        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")
        self.hub = self.base / "hub"
        folder = self.hub / "integrations/model-router"
        folder.mkdir(parents=True)
        lock = {"schema": common.LOCK_SCHEMA, "component": "model-router", "commit": git("rev-parse", "HEAD"),
                "source_kind": "commit", "files": {
                    p.relative_to(self.source).as_posix(): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                                         "executable": False}
                    for p in (self.source / "scripts").iterdir()}}
        (folder / "source-lock.json").write_text(json.dumps(lock), encoding="utf-8")
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
        patcher = patch.object(adapter, "_module", side_effect=lambda _, f, **kw: FakeInstaller if f == "install_codex.py" else FakeNative)
        patcher.start()
        self.addCleanup(patcher.stop)

    def plan(self):
        return adapter.make_plan(self.source, *self.targets, self.runtime, hub_root=self.hub)[0]

    def install(self):
        return adapter.apply(self.source, *self.targets, self.runtime, self.plan()["plan_id"], hub_root=self.hub)

    def put(self, relative, raw):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(0o640)
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

    def test_stale_plan_does_not_write_any_target(self):
        plan = self.plan()
        self.put("config.toml", b'model = "new concurrent choice"\n')
        before = self.disk()
        with self.assertRaisesRegex(common.IntegrationError, "stale"):
            adapter.apply(self.source, *self.targets, self.runtime, plan["plan_id"], hub_root=self.hub)
        self.assertEqual(before, self.disk())
        self.assertFalse(self.workspace.exists())

    def test_missing_runtime_and_source_drift_fail_before_install(self):
        self.runtime.unlink()
        with self.assertRaisesRegex(common.IntegrationError, "executable"):
            self.plan()
        self.runtime.write_bytes(b"runtime")
        self.runtime.chmod(0o700)
        (self.source / "scripts/install_codex.py").write_bytes(b"wrong version")
        with self.assertRaisesRegex(common.IntegrationError, "drift"):
            self.plan()
        self.assertFalse(self.home.exists())

    def test_pstack_registration_or_model_policy_blocks_router(self):
        config = self.put("config.toml", b'[plugins."pstack@pstack-claude"]\nenabled = true\n')
        with self.assertRaisesRegex(common.IntegrationError, "cannot be chained"):
            self.plan()
        config.write_bytes(b'personal = true\n')
        self.put("pstack-models.md", b"unreviewed model policy")
        with self.assertRaisesRegex(common.IntegrationError, "pstack model policy"):
            self.plan()
        self.assertFalse(self.workspace.exists())

    def test_pstack_cached_plugin_blocks_even_without_config(self):
        self.put("plugins/cache/pstack/.codex-plugin/plugin.json", b'{"name":"pstack"}')
        with self.assertRaisesRegex(common.IntegrationError, "pstack plugin"):
            self.plan()

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
        self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o640)
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
        (self.home / "agents/worker.toml").chmod(0o644)
        with self.assertRaisesRegex(common.IntegrationError, "changed"):
            adapter.uninstall_plan(*self.targets, hub_root=self.hub)

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
