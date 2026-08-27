"""Behavior matrix for the Phase0A evidence owner."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/skill_resilience_evidence.py"
MANIFEST = ROOT / "tests/fixtures/owned-hook-surfaces.json"
PHASE1 = [
    "docs/skill-standard.md", "tests/test_hook_resilience_contract.py",
    "skills/repo-pedant/assets/hooks/codex-hooks.fragment.json",
    "skills/repo-pedant/references/trigger-hooks.md", "skills/repo-pedant/scripts/closeout_hook.py",
    "tests/test_closeout_hook.py", "skills/excalidraw-diagram/assets/overlap-audit.schema.json",
    "skills/excalidraw-diagram/assets/overlap-receipt.schema.json", "skills/excalidraw-diagram/scripts/overlap_contract.py",
    "skills/excalidraw-diagram/scripts/audit-overlaps.py", "skills/excalidraw-diagram/scripts/overlap_repair_decision.py",
    "skills/excalidraw-diagram/scripts/overlap_receipt.py", "skills/excalidraw-diagram/SKILL.md",
    "skills/excalidraw-diagram/references/design-system.md", "skills/excalidraw-diagram/references/brand-layer.md",
    "tests/test_excalidraw_overlap_contract.py", "tests/test_excalidraw_overlap_audit.py", "tests/test_excalidraw_overlap_receipt.py",
]


class EvidenceMatrix(unittest.TestCase):
    def run_helper(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(HELPER), *arguments], cwd=ROOT, text=True, capture_output=True)

    def raw_copy(self, directory: Path) -> Path:
        target = directory / "pre-bootstrap.raw.json"
        status = directory / "status.raw"
        status.write_bytes(b"")
        entries = [{"path": path, "record": {"kind": "missing"}} for path in sorted([".gitignore", "scripts/skill_resilience_evidence.py", "tests/fixtures/owned-hook-surfaces.json", "tests/test_skill_resilience_evidence.py", "docs/skill-standard.md", "skills/repo-pedant/assets/hooks/codex-hooks.fragment.json", "skills/super-caveman", "skills/super-caveman/scripts/codex_adapter.py", "/tmp/hooks.json", "/tmp/alias.py"])]
        source = {
            "schema_version": "skill-resilience.pre-bootstrap-raw.v1",
            "capture_commands": ["synthetic-test"],
            "capture_root": str(directory),
            "dirty_path_bytes_sha256": hashlib.sha256(b"").hexdigest(),
            "dirty_paths": [], "entries": entries,
            "entry_list_sha256": hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "git_base": "base", "git_head": "head", "hooks_path": "/tmp/hooks.json",
            "hooks_representation": {"kind": "missing"}, "installed_alias": "/tmp/alias.py",
            "installed_alias_representation": {"hops": [], "terminal": {"kind": "missing"}},
            "managed_intersection": [], "phase0a_paths": [".gitignore", "scripts/skill_resilience_evidence.py", "tests/fixtures/owned-hook-surfaces.json", "tests/test_skill_resilience_evidence.py"],
            "phase1_paths": PHASE1, "raw_status_sha256": hashlib.sha256(b"").hexdigest(),
            "repository_realpath": str(ROOT.resolve()), "tool_identities": {"test": "synthetic"},
        }
        payload = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        target.write_bytes(payload)
        (directory / "pre-bootstrap.raw.sha256").write_text(hashlib.sha256(payload).hexdigest() + "\n", encoding="ascii")
        return target

    def focused(self, directory: Path) -> Path:
        path = directory / "focused.json"
        output = directory / "focused.out"; output.write_text("Ran 24 tests in 1s\n", encoding="utf-8")
        path.write_text(json.dumps({"command": "python3 -m unittest -v tests.test_skill_resilience_evidence", "status": "PASS", "tests_run": 24, "output_path": str(output), "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "helper_sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest(), "test_sha256": hashlib.sha256((ROOT / "tests/test_skill_resilience_evidence.py").read_bytes()).hexdigest()}), encoding="utf-8")
        return path

    def binding(self, directory: Path) -> list[str]:
        path = directory / "bootstrap.json"
        helper_sha = hashlib.sha256(HELPER.read_bytes()).hexdigest()
        focused_out = directory / "focused.out"; focused_out.write_text("Ran 24 tests in 1s\n", encoding="utf-8")
        value = {"schema_version": "skill-resilience.evidence-record.v1", "record_type": "bootstrap", "repository_realpath": str(ROOT.resolve()), "pre_bootstrap_snapshot_digest": "a" * 64, "helper_realpath": str(HELPER.resolve()), "helper_sha256": helper_sha, "trusted_python_realpath": str(Path(sys.executable).resolve()), "owned_surface_manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), "ownership_digest": "b" * 64, "focused_test_evidence": {"command": "python3 -m unittest -v tests.test_skill_resilience_evidence", "status": "PASS", "tests_run": 24, "output_path": str(focused_out), "output_sha256": hashlib.sha256(focused_out.read_bytes()).hexdigest(), "helper_sha256": helper_sha, "test_sha256": hashlib.sha256((ROOT / "tests/test_skill_resilience_evidence.py").read_bytes()).hexdigest()}, "ignore_proof": {"path": " .omx/evidence/skill-resilience-fix".strip(), "source": ".gitignore:1", "match": ".gitignore:1 .omx/evidence/skill-resilience-fix"}, "raw_status_sha256": "d" * 64, "dirty_path_bytes_sha256": "e" * 64, "entry_list_sha256": "f" * 64, "hooks_representation": {"kind": "missing"}, "installed_alias_representation": {"hops": [], "terminal": {"kind": "missing"}}, "manifest": json.loads(MANIFEST.read_text(encoding="utf-8")), "installed_alias": "/tmp/alias.py", "hooks_path": "/tmp/hooks.json"}
        payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        path.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        (Path(str(path) + ".sha256")).write_text(digest + "\n", encoding="ascii")
        return ["--bootstrap", str(path), "--helper", str(HELPER), "--snapshot-digest", "a" * 64, "--bootstrap-digest", digest]

    def test_raw_and_sidecar_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp, tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            raw = self.raw_copy(Path(raw_temp))
            sidecar = raw.with_name("pre-bootstrap.raw.sha256")
            sidecar.write_text("0" * 64 + "\n", encoding="ascii")
            result = self.run_helper("bootstrap", "--raw-snapshot", str(raw), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), "--manifest", str(MANIFEST), "--focused-test-evidence", str(self.focused(Path(temp))), "--output", str(ROOT / ".omx/evidence/skill-resilience-fix/test-raw.json"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("E_SIDECAR_MISMATCH", result.stderr)

    def test_bootstrap_requires_real_focused_evidence_and_containment(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp)
            raw = self.raw_copy(directory)
            outside = directory / "outside.json"
            result = self.run_helper("bootstrap", "--raw-snapshot", str(raw), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), "--manifest", str(MANIFEST), "--output", str(outside))
            self.assertEqual(result.returncode, 2)

    def test_manifest_rejects_extra_duplicate_parent_absolute_glob(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp)
            raw = self.raw_copy(directory)
            for mutation in (
                lambda value: value["surfaces"].append({"id": "extra", "path": "x", "mode": "managed"}),
                lambda value: value["surfaces"].__setitem__(1, value["surfaces"][0].copy()),
                lambda value: value["surfaces"][0].__setitem__("path", "../x"),
                lambda value: value["surfaces"][0].__setitem__("path", "/tmp/x"),
                lambda value: value["surfaces"][0].__setitem__("path", "x*")
            ):
                value = json.loads(MANIFEST.read_text(encoding="utf-8"))
                mutation(value)
                manifest = directory / "manifest.json"
                manifest.write_text(json.dumps(value), encoding="utf-8")
                result = self.run_helper("bootstrap", "--raw-snapshot", str(raw), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), "--manifest", str(manifest), "--focused-test-evidence", str(self.focused(directory)), "--output", str(ROOT / ".omx/evidence/skill-resilience-fix/test-manifest.json"))
                self.assertEqual(result.returncode, 2)

    def test_normalizers_have_stable_tuple_keys(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp)
            source = Path(temp) / "input.json"
            source.write_text(json.dumps({"checks": [{"stage": "b", "code": "z", "reason": "2"}, {"stage": "a", "code": "z", "reason": "1"}]}), encoding="utf-8")
            result = self.run_helper("normalize-verifier", "--input", str(source), "--output", str(directory / "v1.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *self.binding(directory))
            self.assertEqual(json.loads(result.stdout)["payload"][0]["stage"], "a")
            source.write_text(json.dumps({"checks": [{"check": "a", "status": "bad", "summary": "volatile /tmp/x 9ms", "cause": "z"}, {"check": "a", "status": "bad", "summary": "stable", "cause": "a"}]}), encoding="utf-8")
            result = self.run_helper("normalize-doctor", "--input", str(source), "--output", str(directory / "d1.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *self.binding(directory))
            self.assertEqual(json.loads(result.stdout)["payload"][0]["cause"], "a")

    def test_classifier_required_classes_and_bounds(self) -> None:
        canonical = str(ROOT / "skills/super-caveman/scripts/codex_adapter.py")
        alias = "/Users/guanxueliang/.agents/skills/super-caveman/scripts/codex_adapter.py"
        def classify(command: str) -> str:
            return self.run_helper("classify-super", "--command", command, "--canonical", canonical, "--alias", alias, "--repository", str(ROOT)).stdout.strip()
        self.assertEqual(classify(f"python3 {canonical} render"), "parsed_target")
        expected = {
            f"python3 {alias} render": "raw_ambiguous",
            f"sh -c 'python3 {canonical} render'": "raw_ambiguous",
            f"env X=1 python3 {canonical} render": "raw_ambiguous",
            f"python3 {canonical} render extra": "raw_ambiguous",
            "caveman": "none",
            "ordinary-caveman-word": "none",
        }
        for command, classification in expected.items():
            self.assertEqual(classify(command), classification)
        self.assertEqual(classify("caveman"), "none")
        self.assertEqual(classify(" ".join(["x"] * 65)), "raw_ambiguous")

    def test_binding_detects_helper_python_snapshot_and_bootstrap_drift(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            bootstrap = Path(temp) / "bootstrap.json"
            bootstrap.write_text(json.dumps({"helper_realpath": str(HELPER.resolve()), "helper_sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest(), "trusted_python_realpath": str(Path(sys.executable).resolve()), "pre_bootstrap_snapshot_digest": "a" * 64}), encoding="utf-8")
            (Path(str(bootstrap) + ".sha256")).write_text(hashlib.sha256(bootstrap.read_bytes()).hexdigest() + "\n", encoding="ascii")
            result = self.run_helper("assert-binding", "--bootstrap", str(bootstrap), "--helper", str(HELPER), "--snapshot-digest", "b" * 64)
            self.assertEqual(result.returncode, 2)

    def test_hook_warning_startup_value_is_separate(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp)
            source = Path(temp) / "doctor.json"
            source.write_text(json.dumps({"startup_warning_hooks": "1", "warnings": ["new"]}), encoding="utf-8")
            result = self.run_helper("assert-hook-warnings", "--input", str(source), "--output", str(directory / "w1.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *self.binding(directory))
            self.assertEqual(result.returncode, 2)
            source.write_text(json.dumps({"startup_warning_hooks": "0", "warnings": ["new"]}), encoding="utf-8")
            result = self.run_helper("assert-hook-warnings", "--input", str(source), "--output", str(directory / "w2.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *self.binding(directory))
            self.assertEqual(result.returncode, 0)

    def test_every_binding_consumer_rejects_missing_or_wrong_binding(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp)
            input_path = directory / "input.json"
            input_path.write_text(json.dumps({"checks": []}), encoding="utf-8")
            consumers = [
                ["normalize-verifier"], ["normalize-doctor"], ["assert-hook-warnings"],
                ["record-baseline"], ["record-postflight"], ["ownership"], ["freeze-super"],
            ]
            for command in consumers:
                with self.subTest(command=command[0]):
                    args = command + ["--input", str(input_path)] if command[0].startswith("normalize") or command[0] == "assert-hook-warnings" else command + ["--output", str(directory / (command[0] + ".json")), "--input", str(input_path)]
                    if command[0] == "ownership":
                        args = command + ["--raw-snapshot", str(directory / "missing.raw"), "--output", str(directory / "o.json")]
                    if command[0] == "freeze-super":
                        args = command + ["--hooks", str(input_path), "--alias", str(input_path), "--adapter", str(input_path), "--output", str(directory / "f.json")]
                    result = self.run_helper(*args)
                    self.assertEqual(result.returncode, 2)

    def test_classifier_exact_legacy_and_boundary_matrix(self) -> None:
        canonical = str(ROOT / "skills/super-caveman/scripts/codex_adapter.py")
        alias = "/tmp/installed/super-caveman/scripts/codex_adapter.py"
        def classify(command: str) -> str:
            return self.run_helper("classify-super", "--command", command, "--canonical", canonical, "--alias", alias, "--repository", str(ROOT)).stdout.strip()
        self.assertEqual(classify("echo 'CAVEMAN MODE ACTIVE. Rules: x'"), "parsed_legacy")
        self.assertEqual(classify("/x/i-have-adhd/hooks/always-on.sh"), "parsed_legacy")
        self.assertEqual(classify("echo caveman"), "none")
        self.assertEqual(classify("echo super-cavemanish"), "none")
        self.assertEqual(classify("env X=1 python3 " + canonical + " render"), "raw_ambiguous")
        self.assertEqual(classify("sh -c 'python3 " + canonical + " render'"), "raw_ambiguous")
        self.assertEqual(classify("python3 " + alias + " render"), "raw_ambiguous")
        self.assertEqual(classify("python3 skills/super-caveman/scripts/codex_adapter.py render"), "raw_ambiguous")

    def test_classifier_rejects_path_glued_to_path_punctuation(self) -> None:
        canonical = str(ROOT / "skills/super-caveman/scripts/codex_adapter.py")
        alias = "/tmp/installed/super-caveman/scripts/codex_adapter.py"
        def classify(command: str) -> str:
            return self.run_helper("classify-super", "--command", command, "--canonical", canonical, "--alias", alias, "--repository", str(ROOT)).stdout.strip()
        self.assertEqual(classify("echo x." + canonical), "none")
        self.assertEqual(classify("echo x/" + canonical), "none")
        self.assertEqual(classify("echo " + canonical + ".bak"), "none")
        self.assertEqual(classify("echo x$HOME/.agents/skills/super-caveman/scripts/codex_adapter.py"), "none")

    def test_nested_adhd_is_ambiguous_but_top_level_exact_is_legacy(self) -> None:
        canonical = str(ROOT / "skills/super-caveman/scripts/codex_adapter.py")
        alias = "/tmp/alias.py"
        def classify(command: str) -> str:
            return self.run_helper("classify-super", "--command", command, "--canonical", canonical, "--alias", alias, "--repository", str(ROOT)).stdout.strip()
        self.assertEqual(classify("sh -c 'python3 /x/i-have-adhd/hooks/always-on.sh'"), "raw_ambiguous")
        self.assertEqual(classify("/x/i-have-adhd/hooks/always-on.sh"), "parsed_legacy")

    def test_evil_adapter_suffix_is_not_a_target(self) -> None:
        canonical = str(ROOT / "skills/super-caveman/scripts/codex_adapter.py")
        result = self.run_helper("classify-super", "--command", "python3 /evil/super-caveman/scripts/codex_adapter.py render", "--canonical", canonical, "--alias", "/tmp/alias.py", "--repository", str(ROOT))
        self.assertEqual(result.stdout.strip(), "none")

    def test_freeze_adapter_path_is_canonical_only(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            canonical = ROOT / "skills/super-caveman/scripts/codex_adapter.py"
            entries = [{"path": "skills/super-caveman/scripts/codex_adapter.py", "record": module.record_path(canonical)}]
            with self.assertRaises(module.EvidenceError) as error:
                module.validate_canonical_adapter(Path(temp) / "evil.py", ROOT, entries)
            self.assertEqual(str(error.exception), "E_ADAPTER_PATH")
            module.validate_canonical_adapter(canonical, ROOT, entries)

    def test_volatile_only_normalizer_inputs_are_equal(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp)
            first = directory / "one.json"
            second = directory / "two.json"
            first.write_text(json.dumps({"checks": [{"stage": "verify", "code": "PASS", "reason": "3 checks in 4ms at /tmp/a"}]}), encoding="utf-8")
            second.write_text(json.dumps({"checks": [{"stage": "verify", "code": "PASS", "reason": "99 checks in 800ms at /tmp/b"}]}), encoding="utf-8")
            one = self.run_helper("normalize-verifier", "--input", str(first), "--output", str(directory / "o1.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *self.binding(directory))
            two = self.run_helper("normalize-verifier", "--input", str(second), "--output", str(directory / "o2.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *self.binding(directory))
            self.assertEqual(json.loads(one.stdout)["payload"], json.loads(two.stdout)["payload"])

    def test_classifier_wrong_interpreter_and_home_alias_are_ambiguous(self) -> None:
        canonical = str(ROOT / "skills/super-caveman/scripts/codex_adapter.py")
        alias = "/Users/test/.agents/skills/super-caveman/scripts/codex_adapter.py"
        def classify(command: str) -> str:
            return self.run_helper("classify-super", "--command", command, "--canonical", canonical, "--alias", alias, "--repository", str(ROOT)).stdout.strip()
        self.assertEqual(classify("sh " + canonical + " render"), "raw_ambiguous")
        self.assertEqual(classify("python3 $HOME/.agents/skills/super-caveman/scripts/codex_adapter.py render"), "raw_ambiguous")

    def test_component_cli_baseline_and_postflight_are_sealed(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp)
            binding = self.binding(directory)
            projection = {"helper_realpath": str(HELPER.resolve()), "helper_sha256": hashlib.sha256(HELPER.read_bytes()).hexdigest(), "trusted_python_realpath": str(Path(sys.executable).resolve()), "pre_bootstrap_snapshot_digest": "a" * 64, "bootstrap_digest": binding[-1]}
            names = {"verifier": "skill-resilience.full-verify-signatures.v1", "doctor": "skill-resilience.doctor-signatures.v1", "hook_warnings": "skill-resilience.hook-warnings.v1", "ownership": "skill-resilience.ownership.v1", "super_freeze": "skill-resilience.super-freeze.v1"}
            paths = {}
            for key, record_type in names.items():
                path = directory / (key + ".json")
                path.write_text(json.dumps({"schema_version": "skill-resilience.evidence-record.v1", "record_type": record_type, "binding": projection, "payload": {}}, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                (Path(str(path) + ".sha256")).write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "\n", encoding="ascii")
                paths[key] = str(path)
            payload = directory / "components.json"
            payload.write_text(json.dumps(paths), encoding="utf-8")
            result = self.run_helper("record-baseline", "--input", str(payload), "--output", str(directory / "baseline.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *binding)
            self.assertEqual(result.returncode, 0, result.stderr)
            baseline_digest = hashlib.sha256((directory / "baseline.json").read_bytes()).hexdigest()
            paths["baseline"] = str(directory / "baseline.json")
            for key in names:
                source = Path(paths[key]); fresh = directory / (key + "-fresh.json")
                shutil.copy2(source, fresh); shutil.copy2(Path(str(source) + ".sha256"), Path(str(fresh) + ".sha256"))
                paths[key] = str(fresh)
            payload.write_text(json.dumps(paths), encoding="utf-8")
            result = self.run_helper("record-postflight", "--input", str(payload), "--output", str(directory / "postflight.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), "--baseline-digest", baseline_digest, *binding)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_registration_rejects_non_string_target_material(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        malformed = {"hooks": {"SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [{"type": "command", "command": 7}]}]}}
        with self.assertRaises(module.EvidenceError):
            module.registrations(malformed, str(ROOT / "skills/super-caveman/scripts/codex_adapter.py"), str(ROOT), "/tmp/alias.py")

    def test_symlink_chain_records_resolved_regular_terminal(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp); target = directory / "target"; link = directory / "link"
            target.write_text("x", encoding="utf-8"); link.symlink_to(target)
            identity = module.symlink_chain(link)
            self.assertEqual(identity["terminal"]["kind"], "file")
            self.assertGreaterEqual(len(identity["hops"]), 1)

    def test_shared_lexical_budget_rejects_depth_three(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        self.assertTrue(module.lexical_tokens('sh -c "sh -c \'sh -c \\\"echo x\\\"\'"')[1])

    def test_shared_lexical_budget_rejects_token_sixty_five(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        tokens, exhausted = module.lexical_tokens(" ".join(["x"] * 65))
        self.assertTrue(exhausted); self.assertEqual(len(tokens), 64)

    def test_status_parser_distinguishes_untracked(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        self.assertEqual(module.status_entries(b" M tracked\0?? new\0"), [(" M", b"tracked"), ("??", b"new")])

    def test_atomic_writer_rejects_self_digest(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            with self.assertRaises(module.EvidenceError):
                module.atomic_write(Path(temp) / "x.json", {"record_sha256": "x"})

    def test_registration_rejects_extra_group_hook(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        canonical = str(ROOT / "skills/super-caveman/scripts/codex_adapter.py")
        hooks = {"hooks": {"SessionStart": [{"matcher": "startup|resume|clear|compact", "hooks": [{"type": "command", "command": "python3 " + canonical + " render"}, {"type": "command", "command": "echo x"}]}]}}
        found = module.registrations(hooks, canonical, str(ROOT), "/tmp/alias")
        self.assertEqual(found[0]["group_hooks_count"], 2)

    def test_alias_retarget_changes_representation(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp); first = directory / "first"; second = directory / "second"; alias = directory / "alias"
            first.write_text("a", encoding="utf-8"); second.write_text("b", encoding="utf-8"); alias.symlink_to(first)
            before = module.protected_identity(alias); alias.unlink(); alias.symlink_to(second)
            self.assertNotEqual(before, module.protected_identity(alias))

    def test_component_sidecar_format_is_closed(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); value = directory / "component.json"; value.write_text("{}", encoding="utf-8")
            (Path(str(value) + ".sha256")).write_text("bad\n", encoding="ascii")
            with self.assertRaises(module.EvidenceError):
                module.read_sidecar(value)

    def test_generic_rejects_external_component_and_unknown_key(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".omx/evidence/skill-resilience-fix") as temp:
            directory = Path(temp)
            binding = self.binding(directory)
            payload = directory / "components.json"
            payload.write_text(json.dumps({"verifier": "/tmp/external.json", "doctor": "/tmp/external.json", "hook_warnings": "/tmp/external.json", "ownership": "/tmp/external.json", "super_freeze": "/tmp/external.json"}), encoding="utf-8")
            result = self.run_helper("record-baseline", "--input", str(payload), "--output", str(directory / "baseline.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *binding)
            self.assertEqual(result.returncode, 2)
            payload.write_text(json.dumps({"unknown": 1}), encoding="utf-8")
            result = self.run_helper("record-baseline", "--input", str(payload), "--output", str(directory / "baseline2.json"), "--evidence-root", str(ROOT / ".omx/evidence/skill-resilience-fix"), *binding)
            self.assertEqual(result.returncode, 2)

    def test_doctor_none_and_empty_causes_emit_one_no_cause(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        self.assertEqual(module.scrub(None) or "<no-cause>", "<no-cause>")
        self.assertEqual(module.scrub("") or "<no-cause>", "<no-cause>")

    def test_ownership_projection_is_stable_without_widening_phase0b_gate(self) -> None:
        spec = importlib.util.spec_from_file_location("evidence", HELPER)
        module = importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
        phase1_path = PHASE1[0]
        protected_path = "unrelated/protected.txt"
        raw = {
            "raw_status_sha256": "a" * 64,
            "hooks_representation": {"kind": "missing"},
            "installed_alias_representation": {"hops": [], "terminal": {"kind": "missing"}},
            "phase1_paths": PHASE1,
            "entries": [
                {"path": ".gitignore", "record": {"kind": "file", "sha256": "b" * 64}},
                {"path": phase1_path, "record": {"kind": "file", "sha256": "c" * 64}},
                {"path": protected_path, "record": {"kind": "file", "sha256": "d" * 64}},
            ],
        }
        expected_status = {".gitignore": " M", phase1_path: " M", protected_path: "??"}
        exclusions = module.ownership_projection_exclusions(raw)
        phase0b_managed = module.ownership_managed_paths(raw, "phase0b")
        postflight_managed = module.ownership_managed_paths(raw, "postflight")

        self.assertNotIn(phase1_path, phase0b_managed)
        self.assertIn(phase1_path, postflight_managed)
        phase0b_projection = module.protected_projection(raw, expected_status, exclusions)
        postflight_projection = module.protected_projection(raw, expected_status, exclusions)
        self.assertEqual(phase0b_projection, postflight_projection)
        projection = phase0b_projection
        self.assertEqual(set(projection["protected_entries"]), {protected_path})
        self.assertEqual(set(projection["protected_status"]), {protected_path})

        protected, out_of_allowlist, status_differences = module.ownership_enforcement(
            changed=[phase1_path],
            names=set(),
            dirty_paths=[],
            expected_xy=expected_status,
            current_xy=expected_status,
            managed=phase0b_managed,
        )
        self.assertEqual(protected, [phase1_path])
        self.assertEqual(out_of_allowlist, [])
        self.assertEqual(status_differences, [])


if __name__ == "__main__":
    unittest.main()
