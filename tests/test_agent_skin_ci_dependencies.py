"""Keep Agent Skin CI jobs runnable and mandatory for code changes."""
from pathlib import Path
import os
import re
import subprocess
import textwrap
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


    @unittest.skipIf(os.name == "nt", "Required CI job runs on Ubuntu")
    def test_required_job_only_allows_platform_skips_for_docs(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        required_job = workflow.split('\n  required:\n', 1)[1]
        self.assertIn('DOCS_ONLY: ${{ needs.changes.outputs.docs_only }}', required_job)
        command = textwrap.dedent(re.search(r'^        run: \|\n((?:^          .*\n)+)', required_job, re.M)[1])
        platform = ('WINDOWS_RESULT', 'ANIMATION_RESULT', 'AGENT_SKIN_COVERAGE_RESULT',
                    'AGENT_SKIN_FRESH_CLONE_RESULT')
        normal = ('CHANGES_RESULT', 'TESTS_RESULT', 'BENCHMARKS_RESULT', 'POLICY_RESULT', 'PSTACK_RESULT')
        env = dict.fromkeys((*normal, *platform), 'success')

        def result(docs_only, **checks):
            return subprocess.run(
                ['sh', '-e', '-c', command], env={**env, 'DOCS_ONLY': docs_only, **checks},
                capture_output=True, text=True,
            ).returncode

        self.assertEqual(result('false'), 0)
        self.assertEqual(result('true', **dict.fromkeys(platform, 'skipped')), 0)
        for check in platform:
            with self.subTest(check=check):
                self.assertNotEqual(result('false', **{check: 'skipped'}), 0)
                self.assertNotEqual(result('', **{check: 'skipped'}), 0)
                self.assertNotEqual(result('true', **{check: 'failure'}), 0)
                self.assertNotEqual(result('true', **{check: 'cancelled'}), 0)
        self.assertNotEqual(result('true', CHANGES_RESULT='failure'), 0)


if __name__ == '__main__':
    unittest.main()
