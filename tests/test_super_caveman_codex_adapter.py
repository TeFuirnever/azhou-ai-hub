from __future__ import annotations

import ast
import json
from pathlib import Path
import shlex
import shutil
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

    def test_setup_replaces_relocated_adapter_and_uninstall_removes_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hooks_path, options = self.hooks_for(root, "project")
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            payload["hooks"]["SessionStart"].insert(
                0,
                {
                    "matcher": OWN_MATCHER,
                    "hooks": [
                        {
                            "type": "command",
                            "command": "/old/python /old/cache/super-caveman/scripts/codex_adapter.py render",
                            "timeout": 5,
                            "additionalContextLimit": 1024,
                            "statusMessage": "Loading Super Caveman",
                        }
                    ],
                },
            )
            hooks_path.write_text(json.dumps(payload), encoding="utf-8")

            installed = self.invoke("setup", "project", options)
            after_install = json.loads(hooks_path.read_text(encoding="utf-8"))
            removed = self.invoke("uninstall", "project", options)
            after_remove = json.loads(hooks_path.read_text(encoding="utf-8"))

        self.assertEqual(0, installed.returncode, installed.stderr)
        owned = [
            handler
            for registration in after_install["hooks"]["SessionStart"]
            for handler in registration.get("hooks", [])
            if "codex_adapter.py" in handler.get("command", "")
        ]
        self.assertEqual(1, len(owned))
        self.assertIn(str(ADAPTER.resolve()), owned[0]["command"])
        self.assertEqual(0, removed.returncode, removed.stderr)
        self.assertNotIn("codex_adapter.py", json.dumps(after_remove))

    def test_single_stable_field_mismatch_and_malformed_commands_are_unowned(self) -> None:
        current = f"{shlex.quote(sys.executable)} {shlex.quote(str(ADAPTER.resolve()))} render"
        variants = []
        for field, value in (
            ("matcher", "startup"),
            ("type", "prompt"),
            ("timeout", 4),
            ("additionalContextLimit", 1023),
            ("statusMessage", "different"),
            ("command", current + " extra"),
        ):
            registration = {"matcher": OWN_MATCHER, "hooks": [{
                "type": "command", "command": current, "timeout": 5,
                "additionalContextLimit": 1024, "statusMessage": "Loading Super Caveman",
            }]}
            if field == "matcher":
                registration[field] = value
            else:
                registration["hooks"][0][field] = value
            variants.append(registration)
        malformed = {"matcher": OWN_MATCHER, "hooks": [{
            "type": "command", "command": 'python3 "unterminated', "timeout": 5,
            "additionalContextLimit": 1024, "statusMessage": "Loading Super Caveman",
        }]}

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hooks_path, options = self.hooks_for(root, "project")
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            payload["hooks"]["SessionStart"] = variants + [malformed]
            hooks_path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.invoke("setup", "project", options)
            updated = json.loads(hooks_path.read_text(encoding="utf-8"))

        self.assertEqual(0, result.returncode, result.stderr)
        session_start = updated["hooks"]["SessionStart"]
        self.assertEqual(8, len(session_start))
        self.assertEqual(7, sum("codex_adapter.py" in json.dumps(entry) for entry in session_start))
        canonical = [
            registration for registration in session_start
            if registration.get("matcher") == OWN_MATCHER
            and registration.get("hooks", [{}])[0].get("command") == current
            and registration["hooks"][0].get("type") == "command"
            and registration["hooks"][0].get("timeout") == 5
            and registration["hooks"][0].get("additionalContextLimit") == 1024
            and registration["hooks"][0].get("statusMessage") == "Loading Super Caveman"
        ]
        self.assertEqual(1, len(canonical))

    def test_arbitrary_harness_root_adapter_path_is_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hooks_path, options = self.hooks_for(root, "project")
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            payload["hooks"]["SessionStart"] = [{
                "matcher": OWN_MATCHER,
                "hooks": [{
                    "type": "command",
                    "command": "/usr/bin/python3 /any/harness/root/super-caveman/scripts/codex_adapter.py render",
                    "timeout": 5,
                    "additionalContextLimit": 1024,
                    "statusMessage": "Loading Super Caveman",
                }],
            }]
            hooks_path.write_text(json.dumps(payload), encoding="utf-8")
            result = self.invoke("uninstall", "project", options)
            updated = json.loads(hooks_path.read_text(encoding="utf-8"))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("SessionStart", updated.get("hooks", {}))

    def test_setup_and_uninstall_preserve_unowned_registrations_deeply(self) -> None:
        old_command = "/old/python '/old/cache/super-caveman/scripts/codex_adapter.py' render"
        owned_handler = {
            "type": "command",
            "command": old_command,
            "timeout": 5,
            "additionalContextLimit": 1024,
            "statusMessage": "Loading Super Caveman",
        }
        unrelated = {
            "matcher": "startup",
            "registrationUnknown": {"nested": [1, "keep", False]},
            "hooks": [{"type": "command", "command": "echo unrelated", "handlerUnknown": {"x": 1}}],
        }
        lookalike_timeout = {
            "matcher": OWN_MATCHER,
            "registrationUnknown": "lookalike-one",
            "hooks": [{
                "type": "command", "command": old_command, "timeout": 4,
                "additionalContextLimit": 1024, "statusMessage": "Loading Super Caveman",
                "handlerUnknown": ["preserve", 2],
            }],
        }
        owned_one = {"matcher": OWN_MATCHER, "ownedRegistration": 1, "hooks": [owned_handler]}
        empty_owned_matcher = {
            "matcher": OWN_MATCHER,
            "registrationUnknown": {"empty": True},
            "hooks": [],
        }
        scalar = {"arrayEntryUnknown": "keep-me", "hooks": "not-a-list"}
        lookalike_status = {
            "matcher": OWN_MATCHER,
            "registrationUnknown": "lookalike-two",
            "hooks": [{
                "type": "command", "command": old_command, "timeout": 5,
                "additionalContextLimit": 1024, "statusMessage": "Different",
                "handlerUnknown": {"preserve": True},
            }],
        }
        owned_two = {"matcher": OWN_MATCHER, "ownedRegistration": 2, "hooks": [dict(owned_handler)]}
        original_session_start = [
            unrelated,
            lookalike_timeout,
            owned_one,
            empty_owned_matcher,
            scalar,
            lookalike_status,
            owned_two,
        ]

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            hooks_path, options = self.hooks_for(root, "project")
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            payload["hooks"]["SessionStart"] = original_session_start
            hooks_path.write_text(json.dumps(payload), encoding="utf-8")

            installed = self.invoke("setup", "project", options)
            after_install = json.loads(hooks_path.read_text(encoding="utf-8"))
            removed = self.invoke("uninstall", "project", options)
            after_uninstall = json.loads(hooks_path.read_text(encoding="utf-8"))

        self.assertEqual(0, installed.returncode, installed.stderr)
        current = after_install["hooks"]["SessionStart"][2]
        self.assertEqual(OWN_MATCHER, current["matcher"])
        self.assertEqual("command", current["hooks"][0]["type"])
        self.assertEqual(5, current["hooks"][0]["timeout"])
        expected_unowned = [unrelated, lookalike_timeout, empty_owned_matcher, scalar, lookalike_status]
        expected_after_install = [
            unrelated,
            lookalike_timeout,
            current,
            empty_owned_matcher,
            scalar,
            lookalike_status,
        ]
        self.assertEqual(expected_after_install, after_install["hooks"]["SessionStart"])
        self.assertEqual(0, removed.returncode, removed.stderr)
        self.assertEqual(expected_unowned, after_uninstall["hooks"]["SessionStart"])

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
        project = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, project, ignore_errors=True)
        enabled = self.run_adapter(
            "enable", "--scope", "project", "--mode", "full", "--project-dir", str(project)
        )
        self.assertEqual(0, enabled.returncode, enabled.stderr)
        for source in ("startup", "resume", "clear", "compact"):
            with self.subTest(source=source):
                result = self.run_adapter(
                    "render", stdin=json.dumps({"source": source, "cwd": str(project), "transcript": "private-secret"})
                )

                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("", result.stderr)
                self.assertLessEqual(len(result.stdout), 10_000)
                payload = json.loads(result.stdout)
                output = payload["hookSpecificOutput"]
                self.assertEqual("SessionStart", output["hookEventName"])
                self.assertIn("active_mode=full", output["additionalContext"])
                self.assertIn(f"event={source}", output["additionalContext"])
                self.assertIn("schema_version=super-caveman.claude-capsule.v1", output["additionalContext"])
                self.assertRegex(output["additionalContext"], r"rules_digest=[0-9a-f]{64}")
                self.assertNotIn("private-secret", result.stdout)

    def test_neutral_capsule_when_no_default_is_enabled(self) -> None:
        result = self.run_adapter("render", stdin=json.dumps({"source": "startup"}))
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]["additionalContext"]
        self.assertIn("response shaping is off", context)
        self.assertNotIn("active_mode=", context)

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
        # The delegated canonical handler reports its own module prefix; the
        # adapter contract only requires a fail-open exit and no crash.
        self.assertIn("super-caveman", result.stderr)
        self.assertFalse({"requests", "urllib", "httpx", "socket"} & imports)
        self.assertNotRegex(source, r"https?://")


if __name__ == "__main__":
    unittest.main()
