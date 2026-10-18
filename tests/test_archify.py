"""Integrity suite for the archify canonical skill.

Pins the vendored upstream baseline (tt-a1i/archify v3.1.0), the hub wrapper
layer (frontmatter contract, carved coexistence boundary, brand protocol,
receipt) and the deterministic CLI surfaces the receipt depends on.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from scripts.check_repository import INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "archify"
SKILL = SKILL_DIR / "SKILL.md"

UPSTREAM_TAG = "v3.1.0"
UPSTREAM_COMMIT = "1c2b42d660e4a7571813fb43839c79e3e9ca7720"
UPSTREAM_URL = "https://github.com/tt-a1i/archify"
UPSTREAM_SKILL_SHA256 = "55c126d68c1fbef114ccdef8dd0e7f046419dc9203ac7f6dab1728f6bab3ca71"
VENDORED_FILE_COUNT = 144
VENDOR_MANIFEST = ROOT / "tests" / "archify-vendor-manifest.json"


def run_cli(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["node", str(SKILL_DIR / "bin" / "archify.mjs"), *args],
        cwd=SKILL_DIR, capture_output=True, check=False,
    )


class ArchifyPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match)
        self.frontmatter = match.group("frontmatter")

    def test_frontmatter_matches_the_hub_contract(self) -> None:
        keys = {line.split(":", 1)[0] for line in self.frontmatter.splitlines()}
        self.assertEqual({"name", "description"}, keys - {"invocation"})
        name = re.search(r"^name:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertEqual("archify", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), INVOCATION_CLASSES)
        description = re.search(r"^description:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1).strip()), 1024)

    def test_upstream_description_baseline_and_carve_are_retained(self) -> None:
        self.assertIn(
            "Create validated architecture, workflow, sequence, data-flow, lifecycle/state",
            self.text,
        )
        self.assertIn("Not for numeric charts or dashboards", self.text)
        self.assertIn("belong to excalidraw-diagram", self.text)

    def test_excalidraw_diagram_records_the_other_side_of_the_carve(self) -> None:
        excalidraw = (ROOT / "skills" / "excalidraw-diagram" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("belong to archify", excalidraw)

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/archify/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.text)
        self.assertIn("raw evidence", self.text)
        self.assertIn("archify.receipt.v1", self.text)

    def test_provenance_pins_the_locked_upstream(self) -> None:
        provenance = (SKILL_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_TAG, provenance)
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertIn(UPSTREAM_URL, provenance)
        self.assertIsNotNone(re.search(r"^Classification: `faithful`", provenance, re.MULTILINE))
        self.assertIn("Skill-standard §2.3", provenance)

    def test_compatibility_map_records_the_trim_and_the_carve(self) -> None:
        compat = (SKILL_DIR / "references" / "upstream-compatibility.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, compat)
        self.assertIn("intentionally omitted", compat)
        self.assertIn("preserved verbatim, plus one carve sentence", compat)
        self.assertIn("A future removal or replacement needs", compat)

    def test_setup_documents_the_node_runtime(self) -> None:
        setup = (SKILL_DIR / "references" / "setup.md").read_text(encoding="utf-8")
        self.assertIn("Node.js 18", setup)
        self.assertIn("fail closed", setup.lower())
        self.assertIn("doctor", setup)

    def test_vendored_tree_matches_the_complete_manifest(self) -> None:
        manifest = json.loads(VENDOR_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual("azhou-hub.archify-vendor-manifest.v1", manifest["schema"])
        self.assertEqual(UPSTREAM_TAG, manifest["tag"])
        self.assertEqual(UPSTREAM_COMMIT, manifest["commit"])
        actual = {
            path.relative_to(SKILL_DIR).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(SKILL_DIR.rglob("*")) if path.is_file()
        }
        self.assertEqual(VENDORED_FILE_COUNT, len(manifest["files"]))
        self.assertEqual(set(manifest["files"]), set(actual))
        for relative, expected in manifest["files"].items():
            self.assertEqual(expected, actual[relative], relative)

    def test_vendored_tree_size_is_stable(self) -> None:
        files = [path for path in SKILL_DIR.rglob("*") if path.is_file()]
        self.assertEqual(VENDORED_FILE_COUNT, len(files))

    def test_license_copy_and_notices_are_retained(self) -> None:
        license_text = (ROOT / "LICENSES" / "archify-MIT.txt").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 tt-a1i (Archify)", license_text)
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("tt-a1i (Archify)", notices)
        self.assertIn("archify-MIT.txt", notices)
        self.assertIn("JetBrains Mono", notices)
        package_notices = (SKILL_DIR / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("JetBrains Mono", package_notices)


@unittest.skipIf(shutil.which("node") is None, "node is not available")
class ArchifyCliSmokeTest(unittest.TestCase):
    def test_doctor_passes_on_the_trimmed_package(self) -> None:
        result = run_cli("doctor")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(b"Archify is ready", result.stdout)

    def test_guide_router_loads(self) -> None:
        result = run_cli("guide", "user requests an order status timeline", "--json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertTrue(payload["ok"])

    def test_validate_passes_on_a_shipped_example(self) -> None:
        result = run_cli(
            "validate", "workflow", "examples/agent-tool-call.workflow.json",
            "--quality", "showcase", "--json",
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
