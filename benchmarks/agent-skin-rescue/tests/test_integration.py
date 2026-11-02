"""Public offline admission seam: host scope and unsafe roots must have zero writes."""
from pathlib import Path
import os
import sys
import tempfile
import shutil
import unittest

SOURCE = Path(__file__).resolve().parents[1]
WORKTREE = SOURCE.parents[1]
sys.path.insert(0, str(SOURCE))
import integration


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        scratch = WORKTREE / ".scratch"
        scratch.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="integration-admission-", dir=scratch))
        os.chmod(self.root, 0o700)

    def tearDown(self):
        if not (self.root / "invalid-proof-output").exists():
            shutil.rmtree(self.root)
        else:
            print("retained controlled rejection evidence:", self.root)

    def test_invalid_resource_proof_keeps_real_completion_failure(self):
        (self.root / "binding.json").write_text("{}\n")
        (self.root / "producer.json").write_text("{}\n")
        output = self.root / "invalid-proof-output"
        with self.assertRaises(ValueError):
            integration.run(self.root, "binding.json", "producer.json", output)
        result = __import__("json").loads((output / "result.json").read_bytes())
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["hostLaunchAllowed"])
        self.assertEqual(result["commands"][0]["kind"], "C")
        self.assertEqual(result["commands"][0]["exit_code"], 1)
        self.assertFalse(result["commands"][0]["successful"])

    def test_host_scope_has_no_output_side_effects(self):
        output = self.root / "refused-output"
        with self.assertRaises(ValueError):
            integration.run(self.root, "binding.json", "producer.json", output, scope="host")
        self.assertFalse(output.exists())

    def test_external_root_is_refused_before_any_output(self):
        with tempfile.TemporaryDirectory(prefix="external-offline-root-", dir="/tmp") as temporary:
            root = Path(temporary)
            output = root / "refused-output"
            with self.assertRaises(ValueError):
                integration.run(root, "binding.json", "producer.json", output)
            self.assertFalse(output.exists())

    def test_symlink_root_is_refused_before_any_output(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        output = alias / "refused-output"
        with self.assertRaises(ValueError):
            integration.run(alias, "binding.json", "producer.json", output)
        self.assertFalse((self.root / "refused-output").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
