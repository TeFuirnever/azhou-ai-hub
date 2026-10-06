"""Trigger and discovery surface gates from the u4 batch.

Covers four evidence-backed surfaces (docs/research/2026-10-06-cross-harness-
execution-evidence.md §3.3): the ask-azhou routing catalog is generated from
the canonical skills manifest and gate-checked for parity; eli5's frontmatter
carries a paired positive/negative trigger-phrase list (the repo-pedant C1
precedent); every canonical description declares its trigger surface; and
unrouted routing misses are recorded under `.azhou/ask-azhou/` as
count-plus-hash telemetry with negative controls.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from scripts.check_repository import (
    INSTALLABLE_SKILL_PATHS,
    REPOSITORY_EXTENSION_SKILL_PATHS,
    check_router_generated_index,
)

ROOT = Path(__file__).parents[1]
GENERATOR = ROOT / "skills" / "ask-azhou" / "scripts" / "generate_routing_index.py"
RECORDER = ROOT / "skills" / "ask-azhou" / "scripts" / "record_unrouted.py"
ROUTER = ROOT / "skills" / "ask-azhou" / "SKILL.md"
ELI5 = ROOT / "skills" / "eli5" / "SKILL.md"
BEGIN_MARKER = "<!-- generated-routing-index:begin -->"
END_MARKER = "<!-- generated-routing-index:end -->"
UPSTREAM_ELI5_SENTENCE = (
    "Explain like I'm someone who knows nothing about this topic, "
    "using a HTML artifact with big pictures and few words."
)


def run_script(script: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        input=None if stdin is None else stdin.encode("utf-8"),
        capture_output=True,
        timeout=120,
    )


def write_skill(package: Path, name: str, description: str) -> None:
    package.mkdir(parents=True, exist_ok=True)
    (package / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\ninvocation: user-invoked orchestrator\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def make_router(package: Path, body: str = "Router catalog:\n") -> None:
    package.mkdir(parents=True, exist_ok=True)
    (package / "SKILL.md").write_text(
        f"---\nname: ask-azhou\ndescription: Router probe\ninvocation: user-invoked orchestrator\n---\n\n# Ask Azhou\n\n{body}"
        f"{BEGIN_MARKER}\n{END_MARKER}\n",
        encoding="utf-8",
    )


def install_generator(root: Path) -> None:
    """Copy the generator into a fixture root so the gate wrapper can run it."""
    destination = root / "skills" / "ask-azhou" / "scripts" / "generate_routing_index.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(GENERATOR.read_text(encoding="utf-8"), encoding="utf-8")


class RoutingIndexGenerationTest(unittest.TestCase):
    def test_checked_in_block_matches_the_manifest(self) -> None:
        result = run_script(GENERATOR, "--root", str(ROOT), "--check")
        self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))

    def test_generated_index_gate_passes_on_the_repository(self) -> None:
        self.assertEqual([], check_router_generated_index(ROOT))

    def test_stale_block_fails_check_and_regeneration_repairs_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root / "skills" / "alpha", "alpha", "Alpha probe surface.")
            write_skill(root / "skills" / "beta", "beta", "Beta probe surface.")
            make_router(root / "skills" / "ask-azhou")
            self.assertEqual(0, run_script(GENERATOR, "--root", str(root)).returncode)
            self.assertEqual(0, run_script(GENERATOR, "--root", str(root), "--check").returncode)

            write_skill(root / "skills" / "beta", "beta", "Beta probe surface, re-described.")
            stale = run_script(GENERATOR, "--root", str(root), "--check")
            self.assertEqual(1, stale.returncode)
            self.assertIn("routing index is stale", stale.stderr.decode("utf-8"))
            install_generator(root)
            self.assertEqual(
                ["router generated index drift: routing index is stale; regenerate with "
                 "python skills/ask-azhou/scripts/generate_routing_index.py"],
                check_router_generated_index(root),
            )

            self.assertEqual(0, run_script(GENERATOR, "--root", str(root)).returncode)
            self.assertEqual(0, run_script(GENERATOR, "--root", str(root), "--check").returncode)
            text = (root / "skills" / "ask-azhou" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("`beta` — Beta probe surface, re-described.", text)

    def test_added_skill_without_regeneration_is_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root / "skills" / "alpha", "alpha", "Alpha probe surface.")
            make_router(root / "skills" / "ask-azhou")
            self.assertEqual(0, run_script(GENERATOR, "--root", str(root)).returncode)
            write_skill(root / "skills" / "gamma", "gamma", "Gamma probe surface.")
            self.assertEqual(1, run_script(GENERATOR, "--root", str(root), "--check").returncode)

    def test_name_folder_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root / "skills" / "alpha", "not-alpha", "Alpha probe surface.")
            make_router(root / "skills" / "ask-azhou")
            result = run_script(GENERATOR, "--root", str(root), "--check")
            self.assertEqual(1, result.returncode)
            self.assertIn("does not match the package folder", result.stderr.decode("utf-8"))

    def test_unsupported_frontmatter_line_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "skills" / "alpha"
            package.mkdir(parents=True)
            (package / "SKILL.md").write_text(
                "---\nname: alpha\ndescription: Alpha probe surface.\ntriggers: [x]\n---\n",
                encoding="utf-8",
            )
            make_router(root / "skills" / "ask-azhou")
            result = run_script(GENERATOR, "--root", str(root), "--check")
            self.assertEqual(1, result.returncode)
            self.assertIn("unsupported frontmatter line", result.stderr.decode("utf-8"))

    def test_missing_markers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root / "skills" / "alpha", "alpha", "Alpha probe surface.")
            package = root / "skills" / "ask-azhou"
            package.mkdir(parents=True)
            (package / "SKILL.md").write_text(
                "---\nname: ask-azhou\ndescription: Router probe\n---\n\n# Ask Azhou\n",
                encoding="utf-8",
            )
            result = run_script(GENERATOR, "--root", str(root))
            self.assertEqual(1, result.returncode)
            self.assertIn("markers missing", result.stderr.decode("utf-8"))

    def test_duplicated_markers_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root / "skills" / "alpha", "alpha", "Alpha probe surface.")
            package = root / "skills" / "ask-azhou"
            package.mkdir(parents=True)
            (package / "SKILL.md").write_text(
                f"---\nname: ask-azhou\ndescription: Router probe\n---\n\n{BEGIN_MARKER}\n{END_MARKER}\n{BEGIN_MARKER}\n{END_MARKER}\n",
                encoding="utf-8",
            )
            result = run_script(GENERATOR, "--root", str(root))
            self.assertEqual(1, result.returncode)
            self.assertIn("duplicated", result.stderr.decode("utf-8"))


class Eli5TriggerSurfaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = ELI5.read_text(encoding="utf-8")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match)
        self.frontmatter = match.group("frontmatter")
        description = re.search(r"^description:\s*(.+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.description = description.group(1).strip()

    def test_positive_and_negative_trigger_phrases_are_paired(self) -> None:
        # The repo-pedant C1 precedent: positive triggers always ship with an
        # anti-over-trigger negative example.
        for phrase in (
            "MUST trigger",
            "/eli5 <topic>",
            "explain like I'm 5",
            "ELI5",
            "dead-simple picture explainer",
            "给我讲明白",
            "用大白话讲",
            "讲给零基础",
            "通俗易懂",
        ):
            self.assertIn(phrase, self.description)
        for boundary in (
            "Precision-critical asks",
            "spec review",
            "security analysis",
            "migration plans",
            "numerical",
            "never degrade into eli5",
        ):
            self.assertIn(boundary, self.description)

    def test_frontmatter_shape_and_upstream_baseline_survive(self) -> None:
        keys = {line.split(":", 1)[0] for line in self.frontmatter.splitlines()}
        self.assertEqual({"name", "description"}, keys - {"invocation"})
        self.assertLessEqual(len(self.description), 1024)
        self.assertIn(UPSTREAM_ELI5_SENTENCE, self.text)


class DescriptionTriggerSurfaceTest(unittest.TestCase):
    def test_every_canonical_description_declares_a_trigger_surface(self) -> None:
        markers = ("MUST trigger", "Use when", "Use for", "Use before", "Also for")
        frontmatter_pattern = re.compile(r"^---\n(?P<frontmatter>.*?)\n---\n", re.DOTALL)
        for relative in sorted(INSTALLABLE_SKILL_PATHS | REPOSITORY_EXTENSION_SKILL_PATHS):
            text = (ROOT / relative).read_text(encoding="utf-8")
            match = frontmatter_pattern.match(text)
            self.assertIsNotNone(match, relative)
            description = re.search(r"^description:\s*(.+)$", match.group("frontmatter"), re.MULTILINE)
            self.assertIsNotNone(description, relative)
            self.assertTrue(
                any(marker in description.group(1) for marker in markers),
                f"trigger surface missing in {relative}",
            )


class UnroutedTelemetryTest(unittest.TestCase):
    STORE = Path(".azhou") / "ask-azhou" / "unrouted-telemetry.json"
    REQUEST = "how do I fold this into the quarterly report xf7qzunitmarker"

    def store_text(self, root: Path) -> str:
        return (root / self.STORE).read_text(encoding="utf-8")

    def test_record_stores_hash_and_count_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = run_script(RECORDER, "--root", str(root), "--prompt", self.REQUEST)
            self.assertEqual(0, first.returncode, first.stderr.decode("utf-8"))
            second = run_script(RECORDER, "--root", str(root), "--stdin", stdin=f"  {self.REQUEST}  \n")
            self.assertEqual(0, second.returncode, second.stderr.decode("utf-8"))

            payload = json.loads(self.store_text(root))
            self.assertEqual("ask-azhou.unrouted-telemetry.v1", payload["schema"])
            self.assertEqual(1, len(payload["events"]))
            event = next(iter(payload["events"].values()))
            self.assertEqual(2, event["count"])
            self.assertEqual(event["first_seen"], event["last_seen"])
            self.assertRegex(event["first_seen"], r"^\d{4}-\d{2}-\d{2}$")

            stored = self.store_text(root)
            self.assertNotIn("xf7qzunitmarker", stored)
            self.assertNotIn("quarterly report", stored)
            self.assertIn("recorded", second.stdout.decode("utf-8"))

    def test_summary_prints_aggregates_without_raw_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(0, run_script(RECORDER, "--root", str(root), "--prompt", self.REQUEST).returncode)
            result = run_script(RECORDER, "--root", str(root), "--summary")
            self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))
            output = result.stdout.decode("utf-8")
            self.assertIn("1 distinct, 1 total", output)
            self.assertRegex(output, r"sha256=[0-9a-f]{12}")
            self.assertNotIn("xf7qzunitmarker", output)
            self.assertNotIn("quarterly report", output)

    def test_empty_request_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_script(RECORDER, "--root", str(root), "--prompt", "   ")
            self.assertEqual(1, result.returncode)
            self.assertIn("empty", result.stderr.decode("utf-8"))
            self.assertFalse((root / self.STORE).exists())

    def test_prompt_or_stdin_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_script(RECORDER, "--root", directory)
            self.assertEqual(2, result.returncode)

    def test_corrupt_store_fails_closed_and_stays_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / self.STORE
            store.parent.mkdir(parents=True)
            store.write_text("{not json", encoding="utf-8")
            result = run_script(RECORDER, "--root", str(root), "--prompt", self.REQUEST)
            self.assertEqual(1, result.returncode)
            self.assertIn("unreadable", result.stderr.decode("utf-8"))
            self.assertEqual("{not json", store.read_text(encoding="utf-8"))

    def test_schema_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / self.STORE
            store.parent.mkdir(parents=True)
            store.write_text(json.dumps({"schema": "other.schema.v1", "events": {}}), encoding="utf-8")
            result = run_script(RECORDER, "--root", str(root), "--prompt", self.REQUEST)
            self.assertEqual(1, result.returncode)
            self.assertIn("schema mismatch", result.stderr.decode("utf-8"))

    def test_raw_shape_violation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / self.STORE
            store.parent.mkdir(parents=True)
            digest = "a" * 64
            store.write_text(
                json.dumps({"schema": "ask-azhou.unrouted-telemetry.v1", "events": {digest: {"count": 1}}}),
                encoding="utf-8",
            )
            result = run_script(RECORDER, "--root", str(root), "--prompt", self.REQUEST)
            self.assertEqual(1, result.returncode)
            self.assertIn("event shape is unsupported", result.stderr.decode("utf-8"))

    def test_symlink_ancestor_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = Path(directory) / "outside"
            outside.mkdir()
            (root / ".azhou").symlink_to(outside, target_is_directory=True)
            result = run_script(RECORDER, "--root", str(root), "--prompt", self.REQUEST)
            self.assertEqual(1, result.returncode)
            self.assertIn("symlink", result.stderr.decode("utf-8"))
            self.assertFalse((outside / "ask-azhou" / "unrouted-telemetry.json").exists())

    def test_missing_root_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = run_script(RECORDER, "--root", str(Path(directory) / "absent"), "--prompt", self.REQUEST)
            self.assertEqual(1, result.returncode)
            self.assertIn("not a directory", result.stderr.decode("utf-8"))

    def test_store_lives_in_the_ask_azhou_runtime_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(0, run_script(RECORDER, "--root", str(root), "--prompt", self.REQUEST).returncode)
            self.assertTrue((root / ".azhou" / "ask-azhou" / "unrouted-telemetry.json").is_file())
            self.assertTrue(os.path.islink(root / ".azhou") is False)


if __name__ == "__main__":
    unittest.main()
