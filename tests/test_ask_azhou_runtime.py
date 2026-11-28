"""Protect routing text and private telemetry across failure/input boundaries."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "super-ask-azhou" / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"ask_azhou_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TELEMETRY = load_script("record_unrouted")
GENERATOR = load_script("generate_routing_index")


class AskAzhouTelemetryBoundaryTest(unittest.TestCase):
    def test_failed_atomic_publication_preserves_old_counts_and_cleans_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, _, _ = TELEMETRY.record(root, "first private request")
            before = store.read_bytes()
            with mock.patch.object(TELEMETRY.os, "replace", side_effect=OSError("injected publish failure")):
                with self.assertRaisesRegex(OSError, "injected publish failure"):
                    TELEMETRY.record(root, "second private request")
            self.assertEqual(before, store.read_bytes())
            self.assertEqual([store], list(store.parent.iterdir()))

    def test_invalid_event_values_fail_closed_without_rewriting_the_store(self):
        valid = {
            "schema": TELEMETRY.SCHEMA,
            "events": {"a" * 64: {"count": 1, "first_seen": "2026-11-27", "last_seen": "2026-11-27"}},
        }
        invalid = []
        for count in (True, False, 0, -1, "1", 1.5, None):
            payload = copy.deepcopy(valid)
            payload["events"]["a" * 64]["count"] = count
            invalid.append((f"count={count!r}", payload))
        for digest in ("A" * 64, "g" * 64, "a" * 63):
            payload = copy.deepcopy(valid)
            payload["events"] = {digest: payload["events"]["a" * 64]}
            invalid.append((f"digest={digest[:3]}/{len(digest)}", payload))
        for key, value in (("first_seen", None), ("last_seen", "2026"), ("request", "unapproved raw text")):
            payload = copy.deepcopy(valid)
            payload["events"]["a" * 64][key] = value
            invalid.append((key, payload))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = TELEMETRY.store_path(root)
            store.parent.mkdir(parents=True)
            for name, payload in invalid:
                with self.subTest(name=name):
                    before = json.dumps(payload).encode("utf-8")
                    store.write_bytes(before)
                    with self.assertRaises(TELEMETRY.TelemetryError):
                        TELEMETRY.record(root, "a request that must not be persisted")
                    self.assertEqual(before, store.read_bytes())

    def test_repeat_across_days_preserves_first_seen_and_other_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with mock.patch.object(TELEMETRY, "datetime") as clock:
                clock.now.return_value = datetime(2026, 11, 27, 23, 0, tzinfo=timezone.utc)
                store, digest, _ = TELEMETRY.record(root, "需要路由的请求")
                _, other_digest, _ = TELEMETRY.record(root, "another request")
                other = json.loads(store.read_text(encoding="utf-8"))["events"][other_digest]
                clock.now.return_value = datetime(2026, 11, 28, 1, 0, tzinfo=timezone.utc)
                _, repeated, count = TELEMETRY.record(root, "  需要路由的请求\n")
            self.assertEqual(digest, repeated)
            self.assertEqual(2, count)
            payload = json.loads(store.read_text(encoding="utf-8"))
            self.assertEqual({"count": 2, "first_seen": "2026-11-27", "last_seen": "2026-11-28"}, payload["events"][digest])
            self.assertEqual(other, payload["events"][other_digest])
            self.assertNotIn("需要路由", store.read_text(encoding="utf-8"))

    def test_summary_of_an_unused_root_does_not_create_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, payload = TELEMETRY.summarize(root)
            self.assertEqual({"schema": TELEMETRY.SCHEMA, "events": {}}, payload)
            self.assertEqual([], list(root.iterdir()))

    @unittest.skipIf(os.name == "nt", "POSIX private permission modes")
    def test_record_restores_private_store_and_parent_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, _, _ = TELEMETRY.record(root, "first")
            store.chmod(0o666)
            store.parent.chmod(0o777)
            TELEMETRY.record(root, "second")
            self.assertEqual(0o600, store.stat().st_mode & 0o777)
            self.assertEqual(0o700, store.parent.stat().st_mode & 0o777)


class AskAzhouRoutingBoundaryTest(unittest.TestCase):
    def test_quoted_descriptions_retain_apostrophes_colons_and_escapes(self):
        cases = [
            ("'Use Azhou''s skill: route a task.'", "Use Azhou's skill: route a task."),
            ('"Use \\"quoted\\" paths: C:\\\\tools\\tthen continue."', 'Use "quoted" paths: C:\\tools\tthen continue.'),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            for encoded, description in cases:
                with self.subTest(encoded=encoded):
                    path.write_text(f"---\nname: super-example\ndescription: {encoded}\n---\n", encoding="utf-8")
                    self.assertEqual(("super-example", description), GENERATOR.parse_frontmatter(path))

    def test_unsupported_escape_and_unquoted_mapping_text_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SKILL.md"
            for description in ('"Unsupported \\q escape"', "Unquoted: nested mapping"):
                with self.subTest(description=description):
                    text = f"---\nname: super-example\ndescription: {description}\n---\n"
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(GENERATOR.GenerationError):
                        GENERATOR.parse_frontmatter(path)
                    self.assertEqual(text, path.read_text(encoding="utf-8"))

    def test_regeneration_preserves_authored_sections_and_is_idempotent(self):
        prefix = "# 阿舟路由\n\nKeep this authored instruction.\n" + GENERATOR.BEGIN_MARKER
        suffix = GENERATOR.END_MARKER + "\n\n## Exceptions\nKeep this exception too.\n"
        original = prefix + "\n- stale generated entry\n" + suffix
        block = "- `super-example` — Example description.\n"
        updated = GENERATOR.splice(original, block, Path("router.md"))
        self.assertEqual(prefix + "\n" + block + suffix, updated)
        self.assertEqual(updated, GENERATOR.splice(updated, block, Path("router.md")))

    def test_reversed_generated_markers_are_rejected(self):
        original = GENERATOR.END_MARKER + "\nUser-authored text\n" + GENERATOR.BEGIN_MARKER
        with self.assertRaisesRegex(GENERATOR.GenerationError, "out of order"):
            GENERATOR.splice(original, "- generated\n", Path("router.md"))


if __name__ == "__main__":
    unittest.main()
