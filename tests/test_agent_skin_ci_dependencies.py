"""Keep surviving Dream image suites runnable after companion retirement."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AgentSkinCiDependenciesTest(unittest.TestCase):
    def test_dream_jobs_install_the_pinned_image_decoder_before_testing(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        jobs = dict(re.findall(r'^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)',
                               workflow, re.M | re.S))
        for job, command in (
            ('agent-skin-macos', 'python -B tools/test-production-theme-package-preflight.py'),
            ('agent-skin-unit-coverage', 'python -B tools/test-unit-coverage.py'),
        ):
            with self.subTest(job=job):
                body = jobs[job]
                dependency = re.search(r'python -m pip install[^\n]*--only-binary=:all:[^\n]*Pillow==12\.3\.0', body)
                self.assertIsNotNone(dependency, 'Dream image decoding still requires pinned Pillow')
                self.assertLess(dependency.start(), body.index(command))


if __name__ == '__main__':
    unittest.main()
