from contextlib import redirect_stderr, redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock


RUNNER = Path(__file__).resolve().parents[1] / "benchmarks/super-arch-doc/run_case.py"


class ArchDocReceiptTests(unittest.TestCase):
    def run_benchmark(self, target: Path) -> tuple[int, str, str]:
        main = runpy.run_path(str(RUNNER))["main"]
        stdout, stderr = io.StringIO(), io.StringIO()
        with (mock.patch.object(sys, "argv", [str(RUNNER), "--receipt", str(target)]),
              redirect_stdout(stdout), redirect_stderr(stderr)):
            code = main()
        return code, stdout.getvalue(), stderr.getvalue()

    def test_receipt_records_run_date_and_matches_printed_result(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "receipt.json"
            target.write_bytes(b"previous receipt\r\n")
            before = date.today().isoformat()
            code, stdout, stderr = self.run_benchmark(target)
            after = date.today().isoformat()
            self.assertEqual(0, code, stderr)
            receipt = json.loads(target.read_bytes())
            self.assertEqual("passed", receipt["status"])
            self.assertIn(receipt["date"], {before, after})
            self.assertEqual(receipt, json.loads(stdout.splitlines()[-2]))
            self.assertEqual(f"receipt written: {target}", stdout.splitlines()[-1])
            self.assertEqual([target], list(target.parent.iterdir()))

    def test_failed_write_or_replace_preserves_previous_receipt(self):
        open_staging = tempfile.NamedTemporaryFile

        def partial_write(*args, **kwargs):
            stream = open_staging(*args, **kwargs)
            write = stream.write

            def fail(content):
                write(content[:12])
                raise OSError("injected partial write")

            stream.write = fail
            return stream

        for phase, fault in (
            ("write", mock.patch("tempfile.NamedTemporaryFile", side_effect=partial_write)),
            ("replace", mock.patch("os.replace", side_effect=OSError("injected replace failure"))),
        ):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "receipt.json"
                original = '{"date":"2026-01-01","note":"旧回执"}\r\n'.encode("utf-8")
                target.write_bytes(original)
                with fault:
                    code, stdout, stderr = self.run_benchmark(target)
                self.assertEqual(1, code)
                self.assertIn("receipt write failed: injected", stderr)
                self.assertNotIn("receipt written:", stdout)
                self.assertEqual(original, target.read_bytes())
                self.assertEqual([target], list(target.parent.iterdir()))
