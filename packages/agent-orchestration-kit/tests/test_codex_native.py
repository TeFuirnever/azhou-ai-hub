import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from codex_native import role_evidence, select_runtime


class NativeEvidenceTests(unittest.TestCase):
    expected = {"worker": ("gpt-6-luna", "max")}
    definition = "Available roles:\nworker: {\n- This role's model is set to `gpt-6-luna` and its reasoning effort is set to `max`.\n}\n"

    def prompt(self, description=None):
        return [{"type": "additional_tools", "role": "developer", "tools": [
            {"parameters": {"properties": {"agent_type": {"description": description or self.definition}}}}
        ]}]

    def test_role_evidence_uses_host_tool_schema(self):
        result = role_evidence(self.prompt(), self.expected)
        self.assertEqual(result[0]["model"], "gpt-6-luna")
        self.assertIn("tool schema", result[0]["evidence"])

    def test_model_or_user_prose_is_not_discovery_evidence(self):
        for role in ("user", "assistant", "developer"):
            with self.subTest(role=role), self.assertRaises(RuntimeError):
                role_evidence([{"type": "message", "role": role,
                                "content": [{"text": self.definition}]}], self.expected)

    def test_wrong_model_in_host_role_is_rejected(self):
        with self.assertRaises(RuntimeError):
            role_evidence(self.prompt(self.definition.replace("gpt-6-luna", "gpt-6-astra")), self.expected)

    def test_duplicate_or_missing_host_schema_is_rejected(self):
        for prompt in ([], self.prompt() + self.prompt()):
            with self.subTest(prompt=prompt), self.assertRaises(RuntimeError):
                role_evidence(prompt, self.expected)

    def test_duplicate_role_identity_is_rejected(self):
        with self.assertRaises(RuntimeError):
            role_evidence(self.prompt(self.definition + self.definition), self.expected)

    def test_missing_explicit_runtime_is_rejected(self):
        with patch("codex_native.shutil.which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "missing or not executable"):
                select_runtime("/definitely/missing/aok-codex-runtime")


if __name__ == "__main__":
    unittest.main()
