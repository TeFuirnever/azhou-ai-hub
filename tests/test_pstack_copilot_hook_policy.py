"""Synthetic model-sheet and PreToolUse tests for the Hub-owned pstack hooks.

Does not access real COPILOT_HOME, HOME model sheets, tokens or account state.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "packages/pstack-agent-harness/harness/pstack/claude-code"
SCRIPTS = PLUGIN / "skills/setup-pstack/scripts"
HOOK = PLUGIN / "hooks/pre-tool-use.sh"


@unittest.skipUnless(os.name == "posix" and Path("/bin/sh").is_file() and shutil.which("awk"),
                     "requires a POSIX host with /bin/sh and awk; Windows Hook validation is separate")
class PstackCopilotHookPolicyTest(unittest.TestCase):
    def test_registered_models_are_enforced_only_for_pstack_agent_types(self) -> None:
        parser = SCRIPTS / "sheet.awk"
        checker = SCRIPTS / "check-sheet.sh"
        self.assertTrue(parser.is_file(), "the hook cannot parse a missing model sheet")
        self.assertTrue(checker.is_file(), "setup-pstack requires the same validator")
        roles = re.findall(r'roles\[\+\+n\] = "([^"]+)"', parser.read_text())
        self.assertEqual(len(roles), 17)

        with tempfile.TemporaryDirectory(prefix="pstack-hook-policy-") as work:
            home = Path(work)
            models = home / "pstack-models.md"
            models.write_text(
                "\n".join(
                    [
                        "# isolated synthetic model choices",
                        "default effort: session",
                        "panel vendors: any",
                        *[
                            f"{name}: " + (
                                "gpt-6-sol"
                                if name == "feature, refactoring"
                                else "inherit-parent"
                            )
                            for name in roles
                        ],
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            env = {
                **os.environ,
                "COPILOT_PLUGIN_ROOT": str(PLUGIN),
                "COPILOT_HOME": work,
                "HOME": work,
                "LC_ALL": "C",
            }
            validation = subprocess.run(
                ["/bin/sh", str(checker), str(models)],
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=12,
                check=False,
            )
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertEqual(validation.stdout.strip(), "sheet ok")

            def decision(agent_type: str, model: str | None) -> dict | None:
                args = {"agent_type": agent_type}
                if model is not None:
                    args["model"] = model
                payload = {"tool_name": "Task", "tool_input": args, "cwd": work}
                execution = subprocess.run(
                    ["/bin/sh", str(HOOK)],
                    input=json.dumps(payload) + "\n",
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=12,
                    check=False,
                )
                self.assertEqual(execution.returncode, 0, execution.stderr)
                self.assertEqual(execution.stderr.strip(), "")
                return json.loads(execution.stdout) if execution.stdout.strip() else None

            self.assertIsNone(decision("pstack-azhouzhou:poteto-agent", "gpt-6-sol"))
            denial = decision("pstack-azhouzhou:poteto-agent", "foreign-model")
            self.assertIsNotNone(denial)
            self.assertEqual(denial["permissionDecision"], "deny")
            self.assertIn("foreign-model", denial["permissionDecisionReason"])
            for inherited_alias in ("inherit-parent", "auto"):
                alias_denial = decision(
                    "pstack-azhouzhou:poteto-agent", inherited_alias
                )
                self.assertIsNotNone(
                    alias_denial, "an inheritance alias must not be an explicit model"
                )
                self.assertEqual(alias_denial["permissionDecision"], "deny")
            self.assertIsNone(decision("pstack-azhouzhou:poteto-agent", None))
            self.assertIsNone(decision("foreign:agent", "foreign-model"))
            self.assertIsNone(decision("pstack:poteto-agent", "foreign-model"))

            copilot_start = subprocess.run(
                ["/bin/sh", str(PLUGIN / "hooks/session-start.sh"), "copilot"],
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=12,
                check=False,
            )
            self.assertEqual(copilot_start.returncode, 0, copilot_start.stderr)
            context = json.loads(copilot_start.stdout)["additionalContext"]
            self.assertIn("You have pstack-azhouzhou", context)
            self.assertIn("feature, refactoring: gpt-6-sol", context)

            muse = home / "muse"
            muse.mkdir()
            (muse / "pstack-models.md").write_bytes(models.read_bytes())
            muse_env = {**env, "MUSE_PLUGIN_ROOT": str(PLUGIN),
                        "XDG_CONFIG_HOME": work}
            muse_start = subprocess.run(
                ["/bin/sh", str(PLUGIN / "hooks/session-start.sh"), "muse"],
                env=muse_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=12,
                check=False,
            )
            self.assertEqual(muse_start.returncode, 0, muse_start.stderr)
            self.assertIn("You have pstack-azhouzhou", muse_start.stdout)
            self.assertIn("feature, refactoring: gpt-6-sol", muse_start.stdout)


if __name__ == "__main__":
    unittest.main()
