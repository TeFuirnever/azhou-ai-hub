"""Integrity suite for the super-archify canonical skill.

Pins the vendored upstream baseline (tt-a1i/archify v3.2.0), the hub wrapper
layer (frontmatter contract, carved coexistence boundary, brand protocol,
receipt) and the deterministic CLI surfaces the receipt depends on.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_repository import INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-archify"
SKILL = SKILL_DIR / "SKILL.md"

UPSTREAM_TAG = "v3.2.0"
UPSTREAM_COMMIT = "208acba8d412335185b2056fedf54b3405df43fb"
UPSTREAM_URL = "https://github.com/tt-a1i/archify"
UPSTREAM_SKILL_SHA256 = "93434ad579983f4cff639c2b7230c311e0785cc48a25b66b1498e1802be7de91"
VENDORED_FILE_COUNT = 190
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
        self.assertEqual("super-archify", name.group(1).strip())
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
        self.assertIn("Not for dashboards", self.text)
        self.assertIn("belong to super-excalidraw-diagram", self.text)

    def test_excalidraw_diagram_records_the_other_side_of_the_carve(self) -> None:
        excalidraw = (ROOT / "skills" / "super-excalidraw-diagram" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("belong to super-archify", excalidraw)

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-archify/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.text)
        self.assertIn("raw evidence", self.text)
        self.assertIn("super-archify.receipt.v1", self.text)

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
        self.assertEqual(UPSTREAM_SKILL_SHA256, manifest["source_files"]["SKILL.md"])
        self.assertEqual(203, len(manifest["source_files"]))
        self.assertEqual(16, sum(row["disposition"] == "retain_documented_exclusion" for row in manifest["migration"]))
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
        self.assertIn("Pele 1.3.0", package_notices)
        pele_license = (SKILL_DIR / "explainer/vendor/pele/LICENSE").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 kepano", pele_license)
        self.assertIn("ISC License", pele_license)


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


@unittest.skipIf(shutil.which("node") is None, "node is not available")
class ArchifyRuntimeRegressionTest(unittest.TestCase):
    def test_preview_delivers_through_the_actual_internal_cli(self) -> None:
        program = r'''
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root,input,output] = process.argv.slice(1);
const { startPreview } = await import(pathToFileURL(path.join(root,'bin/preview.mjs')));
const preview = await startPreview({type:'workflow',input,output,open:false,pollMs:100,debounceMs:20});
try {
  const deadline=Date.now()+15000;
  while (preview.state().status==='checking' && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,50));
  console.log(JSON.stringify(preview.state()));
} finally { await preview.stop(); await preview.closed; }
'''
        with tempfile.TemporaryDirectory(prefix="hub-archify-preview-") as directory:
            root = Path(directory)
            source = json.loads((SKILL_DIR / "examples/agent-tool-call.workflow.json").read_text())
            source["meta"]["output"] = "artifact.html"
            input_path, output_path = root / "input.json", root / "artifact.html"
            input_path.write_text(json.dumps(source))
            result = subprocess.run(
                ["node", "--input-type=module", "-e", program, str(SKILL_DIR), str(input_path), str(output_path)],
                cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=25,
                env={**os.environ, "ARCHIFY_UPDATE_CHECK_DISABLED": "1"},
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            state = json.loads(result.stdout)
            self.assertEqual("verified", state["status"], state)
            self.assertTrue(output_path.is_file(), state)
            self.assertEqual(hashlib.sha256(output_path.read_bytes()).hexdigest(), state["lastVerified"]["sha256"])
            self.assertEqual(state["lastVerified"]["checkCount"], state["lastVerified"]["checksPassed"])

    def test_official_update_identity_is_distinct_from_canonical_name(self) -> None:
        # Exact official v3.1.0 stable manifest archived at the v3.2.0 source tag.
        # This checks protocol compatibility, not whether that historical version is newer.
        manifest = {
            "schemaVersion": 1, "skillId": "archify", "channel": "stable", "version": "3.1.0",
            "publishedAt": "2026-10-13T17:01:11Z",
            "source": {"repository": UPSTREAM_URL, "ref": "v3.1.0", "treeSha": "7e1de2b2cf3a9a91823ee5dcc2089c1d96a7e4f1"},
            "artifact": {"sha256": "ffedc53390c9da6e859f41e432c5d2d0615a23cf00a503181f07efbba88a7ce8"},
            "summary": "Adds five diagram types for ten total, default Live motion, clearer layouts and verified delivery, with export and Windows portability fixes.",
            "releaseNotes": UPSTREAM_URL + "/releases/tag/v3.1.0", "severity": "normal",
        }
        program = r'''
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root,text]=process.argv.slice(1);
const {validateLocalRelease,validateStableUpdateManifest}=await import(pathToFileURL(path.join(root,'scripts/update-contract.mjs')));
const source=JSON.parse(text);
const local=validateLocalRelease(JSON.parse(fs.readFileSync(path.join(root,'skill-release.json'),'utf8')));
const official=validateStableUpdateManifest(source);
let renamedRejected=false;
try { validateStableUpdateManifest({...source,skillId:'super-archify'}); } catch { renamedRejected=true; }
console.log(JSON.stringify({local,official,renamedRejected}));
'''
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR), json.dumps(manifest)],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("archify", payload["local"]["skillId"])
        self.assertEqual("3.2.0", payload["local"]["version"])
        self.assertEqual(manifest, payload["official"])
        self.assertTrue(payload["renamedRejected"])

    def test_explainer_delivery_keeps_unrequested_browser_not_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hub-archify-explainer-") as directory:
            output = Path(directory) / "answer.html"
            result = subprocess.run(
                ["node", str(SKILL_DIR / "bin/archify.mjs"), "finalize", "explainer",
                 str(SKILL_DIR / "examples/delivery.explainer.json"), str(output), "--json"],
                cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=20,
                env={**os.environ, "ARCHIFY_UPDATE_CHECK_DISABLED": "1"},
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual({"validate":"pass", "deliver":"pass", "check":"pass", "browser-check":"not-run"}, receipt["gates"])
            self.assertFalse(receipt["browserCheck"]["requested"])
            self.assertFalse(receipt["browserCheck"]["ran"])
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), receipt["artifact"]["sha256"])


if __name__ == "__main__":
    unittest.main()
