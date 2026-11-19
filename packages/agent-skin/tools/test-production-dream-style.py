#!/usr/bin/env python3
"""Registered source-capsule, AST derivation and total-mapping contract tests."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DreamStyleTests(unittest.TestCase):
    def test_source_bound_generator_rejects_drift(self):
        spec = importlib.util.spec_from_file_location('dream_ast_generator', ROOT / 'tools/derive-dream-safe-css-ast.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = (ROOT / 'vendor/dream-safe-css-validator.mjs').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), module.SOURCE_SHA256)
        self.assertEqual(module.derive(source), (ROOT / 'vendor/dream-safe-css-ast.mjs').read_bytes())
        with self.assertRaises(ValueError):
            module.derive(source + b'\n')

    def test_classic_factory_is_reproducible_and_preview_wired(self):
        spec = importlib.util.spec_from_file_location('dream_startup_builder', ROOT / 'tools/build-startup.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        expected = builder.dream_theme_style_source(ROOT)
        self.assertEqual((ROOT / 'dream-theme-style.js').read_text(), expected)
        self.assertNotIn('\nimport ', expected)
        self.assertNotIn('\nexport ', expected)
        index = (ROOT / 'index.html').read_text()
        self.assertLess(index.index('src="dream-theme-style.js"'), index.index('src="image-settings.js"'))
        result = subprocess.run(['node', '--input-type=module', '-e',
            "import vm from 'node:vm'; import fs from 'node:fs'; import assert from 'node:assert/strict';"
            "const context=vm.createContext({TextEncoder});"
            "vm.runInContext(fs.readFileSync('dream-theme-style.js','utf8'),context);"
            "const api=context.createDreamThemeStyle();assert.deepEqual(Object.keys(api),['validateThemeSnapshot']);"
            "const preference={mode:'override',value:20};"
            "const result=api.validateThemeSnapshot({schemaVersion:1,revision:4,imagesBinding:'a'.repeat(64),"
            "activeThemeId:'azhou-q-v3',preferencesByTheme:{'azhou-q-v3':preference}});"
            "assert.equal(result.schemaVersion,2);assert.equal(result.selection.surfaceTransparency.value,20);"
            "assert.throws(()=>api.validateThemeSnapshot({...result,selection:{...result.selection,kind:'imported'}}));"],
            cwd=ROOT, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode())

    def test_shipping_payloads_do_not_include_the_offline_dream_parsers(self):
        spec = importlib.util.spec_from_file_location('agent_skin_startup_builder', ROOT / 'tools/build-startup.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        artifacts = builder.load_artifacts(ROOT)
        css = (ROOT / 'wallpaper/wallpaper.css').read_text(encoding='utf-8')
        shipping = {
            f'{host}/{owner}': builder._build_script(ROOT, {}, css, artifacts, host=host, playback_owner=owner)
            for host, owner in [('codex', 'page'), ('codex', 'native'), ('dsh', 'dsh-gated')]
        }
        preview = next(name for name in builder.PREVIEW_SOURCES if 'theme-style.js' in name)
        shipping['preview'] = (ROOT / preview).read_text(encoding='utf-8')
        for target, payload in shipping.items():
            with self.subTest(target=target):
                retired = ('parseSafeCssAst', 'validateOfficialTheme', 'mapDreamTheme')
                self.assertEqual([name for name in retired if name in payload], [])
                self.assertIn('validateThemeSnapshot', payload)
        for notice in ('vendor/dream-safe-css.LICENSE', 'vendor/dream-theme-validator.LICENSE'):
            self.assertNotIn(notice, builder.PREVIEW_SOURCES)

    def test_javascript_source_contracts_and_pristine_corpus(self):
        for arguments in [
            ['tools/dream-theme-style.test.mjs'],
            ['tools/dream-theme-snapshot.test.mjs'],
            ['tools/dream-safe-css.test.mjs', (ROOT / 'vendor/dream-safe-css-ast.mjs').as_uri()],
        ]:
            with self.subTest(arguments=arguments):
                result = subprocess.run(['node', *arguments], cwd=ROOT, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode())


if __name__ == '__main__':
    unittest.main()
