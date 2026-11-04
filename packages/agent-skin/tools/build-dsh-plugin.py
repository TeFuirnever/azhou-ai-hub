#!/usr/bin/env python3
"""Assemble the local DeepSeek Harness plugin package from the neutral core.

The package is emitted into the ignored .build tree only; installing it into a
DSH profile is a separate manual step and never happens here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = 'azhou-agent-skin'
PLUGIN_OUTPUT_DIR = '.build/azhou-dsh-plugin'
STAGE_PARENT = '.build/azhou-stage.dsh-plugin'
MAX_PLUGIN_ICON_BYTES = 256 * 1024
ICON_EDGE_PX = 256
INDEX_JS = (
    '/** Host half of the Agent Skin bundle; the Client module owns the rendering. */\n'
    'export function apply() {}\n'
)
PATCH_YAML = "- insert:\n    - id: azhou-agent-skin\n      name: 'azhou-agent-skin'\n"
LOCALES = {
    'zh': {'meta': {'title': '阿舟 AI 实验室 for DeepSeek Harness',
                    'description': '为 DeepSeek Harness 带来阿舟启动动画、侧栏外观入口与主区壁纸皮肤。'}},
    'en': {'meta': {'title': 'Azhou AI Lab for DeepSeek Harness',
                    'description': ('Brings the Azhou startup animation, sidebar appearance entry, '
                                    'and main-surface wallpaper skin to DeepSeek Harness.')}},
}
MANIFEST_SCOPE = ('local assembly only; installing into a DSH profile is a separate manual step; '
                  'no install or host writes')
_IIFE_OPEN = '(() => {\n'
_IIFE_CLOSE = '})()\n'
_DEPENDENCY_TAIL = 'createWallpaperApplicator,\n  });\n  return bootstrapStartup({'
_DEPENDENCY_TAIL_WITH_CLEANUP = 'createWallpaperApplicator,\n    registerCleanup,\n  });\n  return bootstrapStartup({'
_CLIENT_OPEN = (
    "window.__ModuleLoader__.load({\n"
    "  id: 'azhou-agent-skin',\n"
    "  factory(require) {\n"
    "    'use strict';\n"
    "    const module = { exports: {} };\n"
    "    const runStartup = (registerCleanup) => {\n"
)
_CLIENT_CLOSE = (
    "    };\n"
    "    const inject = [];\n"
    "    function apply(ctx) {\n"
    "      const host = globalThis;\n"
    "      const document = host.document;\n"
    "      const boot = Object.getOwnPropertyDescriptor(host, '__DSH_BOOT__');\n"
    "      if (!document || !document.body || !boot || !Object.hasOwn(boot, 'value')\n"
    "          || typeof host.__ModuleLoader__?.load !== 'function') {\n"
    "        return { installed: false, alreadyActive: false, reason: 'page-unsupported' };\n"
    "      }\n"
    "      // cordis ctx.effect runs its callback immediately and invokes the returned\n"
    "      // disposer at teardown, so every cleanup below returns its own disposer.\n"
    "      const dispose = (fn, label) => ctx.effect(() => () => {\n"
    "        try { fn(); } catch {}\n"
    "      }, 'azhou-agent-skin: ' + label);\n"
    "      dispose(() => {\n"
    "        const startup = host.__azhouStartup;\n"
    "        if (startup?.owner === 'azhou-dsh-startup') startup.dispose();\n"
    "      }, 'startup-controller');\n"
    "      const adapterCleanup = (resource) => {\n"
    "        if (!resource || typeof resource.key !== 'string' || typeof resource.dispose !== 'function') return;\n"
    "        dispose(resource.dispose, 'adapter-' + resource.key);\n"
    "      };\n"
    "      if (document.readyState !== 'loading') return runStartup(adapterCleanup);\n"
    "      ctx.effect(() => {\n"
    "        const start = () => {\n"
    "          try { runStartup(adapterCleanup); } catch {}\n"
    "        };\n"
    "        document.addEventListener('DOMContentLoaded', start, { once: true });\n"
    "        return () => document.removeEventListener('DOMContentLoaded', start);\n"
    "      }, 'azhou-agent-skin: document-ready');\n"
    "      return { installed: false, alreadyActive: false, reason: 'dom-loading' };\n"
    "    }\n"
    "    module.exports = { apply, inject };\n"
    "    return module.exports;\n"
    "  },\n"
    "});\n"
)


def load_builder(root: Path):
    path = Path(root) / 'tools/build-startup.py'
    spec = importlib.util.spec_from_file_location('agent_skin_dsh_startup_builder', path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Missing startup builder module: {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _payload_body(payload: str) -> str:
    """Defer the emitted startup expression and route adapter cleanup outward.

    build-startup emits a self-contained codex-style ``(() => { ... })()``
    expression; the plugin factory must stay side-effect free, so the wrapper
    turns it into ``runStartup(registerCleanup)`` and binds the adapter's
    optional registerCleanup dependency to the caller's disposal sink.
    """
    if (not payload.startswith(_IIFE_OPEN) or not payload.endswith(_IIFE_CLOSE)
            or payload.startswith('((controllerMetadata) => {')
            or payload.count('function createDSHPageAdapter(') != 1
            or 'createCodexPageAdapter(' in payload
            or 'createZCodePageAdapter(' in payload):
        raise RuntimeError('The DSH startup payload must be the codex-style single-adapter expression.')
    body = payload[len(_IIFE_OPEN):-len(_IIFE_CLOSE)]
    if body.count(_DEPENDENCY_TAIL) != 1:
        raise RuntimeError('The DSH startup payload must end with the fixed adapter wiring tail.')
    return body.replace(_DEPENDENCY_TAIL, _DEPENDENCY_TAIL_WITH_CLEANUP, 1)


def _render_icon(root: Path, artifacts, theme: dict) -> bytes:
    source = artifacts._private_input(root, theme['identity']['iconInput'], 'identity.iconInput', required=True)
    sips = shutil.which('sips')
    if sips is None:
        raise RuntimeError('DSH plugin icon generation requires the macOS sips tool.')
    build_dir = Path(root) / '.build'
    with tempfile.TemporaryDirectory(prefix='azhou-dsh-icon-', dir=build_dir) as temporary:
        target = Path(temporary) / 'icon.png'
        subprocess.run([sips, '-s', 'format', 'png', '--resampleWidth', str(ICON_EDGE_PX),
                        str(source), '--out', str(target)], check=True, capture_output=True, text=True)
        icon = target.read_bytes()
    artifacts.png_details(icon, 'icon.png')
    if len(icon) > MAX_PLUGIN_ICON_BYTES:
        raise RuntimeError(f'DSH plugin icon exceeds the 256 KiB host limit ({len(icon)} bytes); refusing to assemble.')
    return icon


def _json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


def _compose_package(destination: Path, *, body: str, icon: bytes, theme: dict, inputs: dict, artifacts) -> dict:
    destination = Path(destination)
    if destination.exists():
        raise RuntimeError(f'Refusing to compose over an existing directory: {destination}')
    destination.mkdir(parents=True)
    package_json = {
        'name': PLUGIN_NAME,
        'version': theme['identity']['version'],
        'private': True,
        'description': LOCALES['en']['meta']['description'],
        'type': 'module',
        'exports': {'.': './index.js', './client': './client.js',
                    './locale/*.json': './locale/*.json', './package.json': './package.json'},
        'files': ['client.js', 'cordis.patch.yml', 'icon.png', 'index.js', 'locale/*.json', 'manifest.json'],
        'icon': 'icon.png',
        'dsh': {'bundle': {'patch': './cordis.patch.yml'},
                'client': {'platform': 'web', 'immediately': True, 'inject': []}},
    }
    files = {
        'client.js': (_CLIENT_OPEN + body + _CLIENT_CLOSE).encode('utf-8'),
        'index.js': INDEX_JS.encode('utf-8'),
        'cordis.patch.yml': PATCH_YAML.encode('utf-8'),
        'package.json': _json_text(package_json).encode('utf-8'),
        'icon.png': icon,
        'locale/zh.json': _json_text(LOCALES['zh']).encode('utf-8'),
        'locale/en.json': _json_text(LOCALES['en']).encode('utf-8'),
    }
    for name, data in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = {
        'schema': 1,
        'protocolVersion': 1,
        'appVersion': theme['identity']['version'],
        'appBuild': theme['identity']['build'],
        'targetHost': 'dsh',
        'inputSHA256': artifacts.aggregate_inputs(inputs),
        'sourceInputs': {name: inputs[name] for name in artifacts.DSH_PLUGIN_REQUIRED_INPUTS},
        'outputs': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
        'scope': MANIFEST_SCOPE,
    }
    (destination / 'manifest.json').write_bytes(_json_text(manifest).encode('utf-8'))
    return manifest


def _assert_identical(first: Path, second: Path) -> None:
    def snapshot(base: Path) -> dict:
        return {item.relative_to(base).as_posix(): item.read_bytes()
                for item in sorted(base.rglob('*')) if item.is_file()}

    left, right = snapshot(Path(first)), snapshot(Path(second))
    if left != right:
        differing = sorted(set(left) ^ set(right)) or sorted(
            name for name in set(left) & set(right) if left[name] != right[name])
        raise RuntimeError('DSH plugin composition is not deterministic: ' + ', '.join(differing))


def _assert_no_path_leak(tree: Path, root: Path) -> None:
    marker = str(Path(root).resolve()).encode('utf-8')
    for item in sorted(Path(tree).rglob('*')):
        if item.is_file() and marker in item.read_bytes():
            raise RuntimeError(f'DSH plugin file leaks the local build path: {item.name}')


def build_plugin(destination: Path | None = None, *, root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    destination = Path(destination) if destination is not None else root / PLUGIN_OUTPUT_DIR / PLUGIN_NAME
    builder = load_builder(root)
    artifacts = builder.load_artifacts(root)
    theme = artifacts.load_theme_config(root, require_inputs=True)

    build_dir = root / '.build'
    if build_dir.is_symlink():
        raise RuntimeError('拒绝通过符号链接 .build 目录构建 DSH 插件。')
    build_dir.mkdir(parents=True, exist_ok=True)

    stage = root / STAGE_PARENT / 'azhou-payload'
    if stage.is_symlink():
        raise RuntimeError('拒绝通过符号链接 staging 目录构建 DSH 插件。')
    if stage.exists():
        shutil.rmtree(stage)
    try:
        builder.build_startup(stage, root=root, host='dsh')
        payload = (stage / 'Contents/Resources/startup/install.js').read_text(encoding='utf-8')
        body = _payload_body(payload)
        icon = _render_icon(root, artifacts, theme)
        inputs = artifacts.source_inputs()
        with tempfile.TemporaryDirectory(prefix='azhou-dsh-compose-', dir=build_dir) as temporary:
            work = Path(temporary)
            first, second = work / 'first' / PLUGIN_NAME, work / 'second' / PLUGIN_NAME
            manifest = _compose_package(first, body=body, icon=icon, theme=theme,
                                        inputs=inputs, artifacts=artifacts)
            _compose_package(second, body=body, icon=icon, theme=theme,
                             inputs=inputs, artifacts=artifacts)
            _assert_identical(first, second)
            _assert_no_path_leak(first, root)
            if destination.is_symlink():
                raise RuntimeError(f'拒绝覆写符号链接 DSH 插件目录：{destination}')
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(first), str(destination))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        try:
            stage.parent.rmdir()
        except OSError:
            pass
    artifacts.verify_dsh_plugin(destination)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=None,
                        help='destination package directory '
                             '(default .build/azhou-dsh-plugin/azhou-agent-skin)')
    args = parser.parse_args()
    try:
        manifest = build_plugin(args.output)
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        parser.exit(1, f'DSH 插件包构建失败：{exc}\n')
    print(json.dumps({
        'kind': 'dshPlugin', 'plugin': PLUGIN_NAME,
        'appVersion': manifest['appVersion'], 'appBuild': manifest['appBuild'],
        'protocolVersion': manifest['protocolVersion'], 'outputs': len(manifest['outputs']),
        'scope': MANIFEST_SCOPE,
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
