from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class HookResilienceContractTest(unittest.TestCase):
    def test_repo_fragment_is_advisory_timeout_five_and_has_no_retry_controls(self) -> None:
        fragment = json.loads((ROOT / "skills/repo-pedant/assets/hooks/codex-hooks.fragment.json").read_text())
        for event in ("PreCompact", "Stop"):
            hook = fragment["hooks"][event][0]["hooks"][0]
            self.assertEqual(5, hook["timeout"])
            self.assertIn("--mode advisory", hook["command"])
            self.assertNotIn("additionalContextLimit", hook)
            self.assertNotIn("retry", hook)
            self.assertNotIn("max-attempt", hook["command"])
            self.assertNotIn("backoff", hook["command"])

    def test_standard_binds_raw_bootstrap_and_honest_receipts(self) -> None:
        text = (ROOT / "docs/skill-standard.md").read_text()
        required = (
            "Phase0P raw pre-write binding",
            "trusted bootstrap/Python",
            "root `.gitignore` source",
            "root/skill\nowner split",
            "detector/decision/audit-chain separation",
            "embedded integrity and internal consistency",
            "origin/authenticity/immutable history",
            "complete-with-holds",
            "visual gate",
            "deterministic read-only Super classification/freeze",
            "Markdown-to-machine executable validation",
        )
        for phrase in required:
            self.assertIn(phrase, text)

    def test_trigger_contract_distinguishes_codex_reentry_from_retry(self) -> None:
        text = (ROOT / "skills/repo-pedant/references/trigger-hooks.md").read_text()
        self.assertIn("Codex dispatches once per event", text)
        self.assertIn("Stop continuation is event re-entry, not retry", text)
        self.assertIn("64KiB", text)

    def test_owned_surface_boundary_is_explicit(self) -> None:
        text = (ROOT / "docs/skill-standard.md").read_text()
        self.assertIn("repo-pedant", text)
        self.assertIn("skills/<canonical-name>/", text)
        self.assertIn("neutral core", text)


if __name__ == "__main__":
    unittest.main()
