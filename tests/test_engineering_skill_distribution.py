"""Check shipped instruction routes and attribution, not model effectiveness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/pstack-agent-harness"
INVENTORY = json.loads((ROOT / "docs/research/2026-11-09-zcode-dsh-skills.json").read_text(encoding="utf-8"))
HOSTS = ("claude-code", "codex", "zcode", "skills-root")
LEGAL = ("LICENSE-ZCode", "NOTICE-ZCode.md", "LICENSE-DeepSeek", "ENGINEERING-SOURCES.md")


def inspect_bundle(tree: Path) -> list[str]:
    """Observe the installed layout, including links outside a single skill."""
    errors = []
    for name in LEGAL:
        file = tree / name
        if not file.is_file() or file.read_bytes() != (PACKAGE / name).read_bytes():
            errors.append(f"missing or changed attribution: {name}")
    for skill, relative in INVENTORY["routes"].items():
        entry = tree / "skills" / skill / "SKILL.md"
        if not entry.is_file() or relative not in re.findall(r"\]\(([^)]+)\)", entry.read_text(encoding="utf-8")):
            errors.append(f"unreachable reference: {skill}")
            continue
        reference = (entry.parent / relative).resolve()
        if not reference.is_relative_to((tree / "skills").resolve()):
            errors.append(f"reference escapes skills: {skill}")
            continue
        source = PACKAGE / "hub-skills" / reference.relative_to((tree / "skills").resolve())
        if not reference.is_file() or reference.read_bytes() != source.read_bytes():
            errors.append(f"missing or changed reference: {skill}")
    return errors


class EngineeringSkillDistributionTest(unittest.TestCase):
    def test_complete_pinned_inventory_has_a_decision_and_existing_owner(self):
        self.assertEqual(INVENTORY["schema"], "azhou-hub.skill-comparison.v1")
        self.assertEqual({s["name"]: s["count"] for s in INVENTORY["sources"]},
                         {"ZCode": 54, "deepseek-harness": 38})
        self.assertEqual(len(INVENTORY["routes"]), 11)
        entries = INVENTORY["entries"]
        self.assertEqual(len({r["id"] for r in entries}), 92)
        for source in INVENTORY["sources"]:
            self.assertRegex(source["commit"], r"^[0-9a-f]{40}$")
            paths = sorted(row["path"] for row in entries if row["source"] == source["name"])
            self.assertEqual(len(paths), source["count"])
            self.assertEqual(len(set(paths)), len(paths))
            digest = hashlib.sha256(("\n".join(paths) + "\n").encode()).hexdigest()
            self.assertEqual(digest, source["paths_sha256"])
        for row in entries:
            with self.subTest(entry=row["id"]):
                self.assertIn(row["decision"], {"adapt", "reuse", "host-specific", "out-of-scope", "fixture"})
                self.assertTrue((ROOT / row["target"]).is_file())
                self.assertTrue(row["reason"])
                self.assertTrue(row["review_depth"])
                self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")

    def test_every_host_ships_reachable_references_and_original_notices(self):
        for host in HOSTS:
            with self.subTest(host=host):
                tree = PACKAGE / "harness/pstack" / host
                self.assertEqual(inspect_bundle(tree), [])
                self.assertEqual(json.loads((tree / "plugin.json").read_text(encoding="utf-8"))["license"],
                                 "MIT AND Apache-2.0")
        manifest = json.loads((PACKAGE / "hub-package.json").read_text(encoding="utf-8"))
        self.assertTrue(set(LEGAL) <= set(manifest["runtime_paths"]))

    def test_missing_reference_or_notice_cannot_pass_distribution_check(self):
        # Copy only the observable bundle surface, not the upstream source tree.
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            real = PACKAGE / "harness/pstack/codex"
            for name in LEGAL:
                shutil.copyfile(real / name, tree / name)
            for skill, relative in INVENTORY["routes"].items():
                entry = tree / "skills" / skill / "SKILL.md"
                entry.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(real / "skills" / skill / "SKILL.md", entry)
                target = entry.parent / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(real / "skills" / skill / relative, target)
            self.assertEqual(inspect_bundle(tree), [])
            missing = tree / "skills/blast-radius/references/semantic-impact.md"
            saved = missing.read_bytes()
            missing.unlink()
            self.assertIn("missing or changed reference: blast-radius", inspect_bundle(tree))
            missing.write_bytes(saved)
            (tree / "LICENSE-ZCode").unlink()
            self.assertIn("missing or changed attribution: LICENSE-ZCode", inspect_bundle(tree))


if __name__ == "__main__":
    unittest.main()
