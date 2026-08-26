from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
ADAPTER = ROOT / "skills" / "super-caveman" / "scripts" / "codex_adapter.py"
OWN_MATCHER = "startup|resume|clear|compact"


class CodexAdapterContractTest(unittest.TestCase):
    def run_adapter(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ADAPTER), *args],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            timeout=6,
        )

    def hooks_for(self, root: Path, scope: str) -> tuple[Path, list[str]]:
        scope_root = root / scope
        hooks_path = scope_root / ".codex" / "hooks.json"
        hooks_path.parent.mkdir(parents=True)
        hooks_path.write_text(
            json.dumps(
                {
                    "description": "keep this metadata",
                    "hooks": {
                        "Stop": [{"hooks": [{"type": "command", "command": "echo external"}]}],
                        "SessionStart": [
                            {
                                "matcher": OWN_MATCHER,
                                "hooks": [{"type": "command", "command": "echo external", "timeout": 4}],
                            }
                        ],
                    },
                }
            ),
            encoding="utf-8",
        )
        option = "--project-dir" if scope == "project" else "--home-dir"
        return hooks_path, [option, str(scope_root)]

    def invoke(self, command: str, scope: str, options: list[str]) -> subprocess.CompletedProcess[str]:
        return self.run_adapter(command, "--scope", scope, *options)

    def test_setup_requires_explicit_scope(self) -> None:
        result = self.run_adapter("setup")

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual("", result.stdout)

    def test_setup_preserves_unrelated_entries_and_registers_one_owned_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for scope in ("project", "user"):
                with self.subTest(scope=scope):
                    hooks_path, options = self.hooks_for(root, scope)
                    result = self.invoke("setup", scope, options)

                    self.assertEqual(0, result.returncode, result.stderr)
                    payload = json.loads(hooks_path.read_text(encoding="utf-8"))
                    self.assertEqual("keep this metadata", payload["description"])
                    self.assertEqual([{"hooks": [{"type": "command", "command": "echo external"}]}], payload["hooks"]["Stop"])
                    registrations = payload["hooks"]["SessionStart"]
                    owned = [entry for entry in registrations if "codex_adapter.py" in json.dumps(entry)]
                    self.assertEqual(1, len(owned))
                    self.assertEqual(1, len(owned[0]["hooks"]))
                    handler = owned[0]["hooks"][0]
                    self.assertEqual(OWN_MATCHER, owned[0]["matcher"])
                    self.assertEqual("command", handler["type"])
                    self.assertEqual(5, handler["timeout"])
                    self.assertEqual(1024, handler["additionalContextLimit"])
                    self.assertIn(" render", handler["command"])

    def test_setup_is_idempotent_and_uninstall_removes_only_owned_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hooks_path, options = self.hooks_for(Path(temporary), "project")
            first = self.invoke("setup", "project", options)
            after_first = json.loads(hooks_path.read_text(encoding="utf-8"))
            second = self.invoke("setup", "project", options)
            after_second = json.loads(hooks_path.read_text(encoding="utf-8"))
            removed = self.invoke("uninstall", "project", options)
            after_remove = json.loads(hooks_path.read_text(encoding="utf-8"))

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(after_first, after_second)
        self.assertEqual(0, removed.returncode, removed.stderr)
        self.assertEqual(
            [{"matcher": OWN_MATCHER, "hooks": [{"type": "command", "command": "echo external", "timeout": 4}]}],
            after_remove["hooks"]["SessionStart"],
        )

    def test_reconcile_legacy_removes_only_the_two_superseded_global_injections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hooks_path, options = self.hooks_for(Path(temporary), "user")
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            payload["hooks"]["SessionStart"].append(
                {
                    "matcher": OWN_MATCHER,
                    "hooks": [
                        {"type": "command", "command": "echo 'CAVEMAN MODE ACTIVE. Rules: old contract'"},
                        {"type": "command", "command": "sh \"/cache/i-have-adhd/hooks/always-on.sh\""},
                        {"type": "command", "command": "echo diagnostic: CAVEMAN MODE ACTIVE"},
                        {"type": "command", "command": "echo external-two"},
                    ],
                }
            )
            hooks_path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.invoke("reconcile-legacy", "user", options)
            updated = json.loads(hooks_path.read_text(encoding="utf-8"))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(2, json.loads(result.stdout)["removed_legacy_session_start_handlers"])
        commands = json.dumps(updated["hooks"]["SessionStart"])
        self.assertNotIn("Rules: old contract", commands)
        self.assertNotIn("always-on.sh", commands)
        self.assertIn("diagnostic: CAVEMAN MODE ACTIVE", commands)
        self.assertIn("echo external", commands)
        self.assertIn("echo external-two", commands)

    def test_scope_rejects_nonstandard_and_symlinked_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hooks_path, options = self.hooks_for(root, "project")
            outside = root / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            rejected = self.run_adapter("setup", "--scope", "project", *options, "--hooks-path", str(outside))

            target = root / "target.json"
            target.write_bytes(hooks_path.read_bytes())
            hooks_path.unlink()
            hooks_path.symlink_to(target)
            symlinked = self.invoke("setup", "project", options)

            self.assertNotEqual(0, rejected.returncode)
            self.assertEqual("{}", outside.read_text(encoding="utf-8"))
            self.assertNotEqual(0, symlinked.returncode)
            self.assertTrue(hooks_path.is_symlink())

    def test_all_session_start_sources_emit_a_bounded_machine_clean_capsule(self) -> None:
        for source in ("startup", "resume", "clear", "compact"):
            with self.subTest(source=source):
                result = self.run_adapter("render", stdin=json.dumps({"source": source, "transcript": "private-secret"}))

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("", result.stderr)
                self.assertLessEqual(len(result.stdout), 4_000)
                payload = json.loads(result.stdout)
                output = payload["hookSpecificOutput"]
                self.assertEqual("SessionStart", output["hookEventName"])
                self.assertIn("active_mode=full", output["additionalContext"])
                self.assertIn(f"event={source}", output["additionalContext"])
                self.assertRegex(output["additionalContext"], r"rules_digest=[0-9a-f]{64}")
                self.assertNotIn("private-secret", result.stdout)

    def test_invalid_event_fails_open_and_adapter_has_no_network_client(self) -> None:
        result = self.run_adapter("render", stdin="not-json")
        source = ADAPTER.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }

        self.assertEqual(0, result.returncode)
        self.assertEqual({}, json.loads(result.stdout))
        self.assertIn("super-caveman Codex adapter:", result.stderr)
        self.assertFalse({"requests", "urllib", "httpx", "socket"} & imports)
        self.assertNotRegex(source, r"https?://")


if __name__ == "__main__":
    unittest.main()
