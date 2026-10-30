#!/usr/bin/env python3
"""Compatibility checks for a Codex-specific label on an existing installation."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('agent_skin_artifacts', PACKAGE / 'tools/verify-artifacts.py')
artifacts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(artifacts)


class CodexEntryCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agent-skin-codex-label-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('hub-package.json', 'theme-config.json'):
            shutil.copy2(PACKAGE / name, self.root / name)
        self.config = json.loads((self.root / 'theme-config.json').read_text(encoding='utf-8'))
        self.config['identity']['appName'] = {
            'zh-CN': '阿舟 AI 实验室 for Codex',
            'en': 'Azhou AI Lab for Codex',
        }

    def write_config(self):
        (self.root / 'theme-config.json').write_text(
            json.dumps(self.config, ensure_ascii=False), encoding='utf-8')

    def test_codex_label_keeps_existing_install_path(self):
        self.write_config()
        identity = artifacts.load_theme_config(self.root)['identity']
        self.assertEqual(identity['installationName'], '阿舟 AI 实验室.app')
        self.assertEqual(identity['appName']['en'], 'Azhou AI Lab for Codex')
        self.assertEqual(identity['appName']['zh-CN'], '阿舟 AI 实验室 for Codex')
        self.assertEqual(artifacts.bundle_fallback_display_name(identity), '阿舟 AI 实验室')

    def test_rejects_unsafe_install_paths_with_codex_label(self):
        for name in ('../elsewhere.app', 'nested/other.app', '.app', 'other.txt'):
            with self.subTest(name=name):
                self.config['identity']['installationName'] = name
                self.write_config()
                with self.assertRaises(RuntimeError):
                    artifacts.load_theme_config(self.root)


if __name__ == '__main__':
    unittest.main()
