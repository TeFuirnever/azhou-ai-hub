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
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = 'azhou-agent-skin'
PLUGIN_OUTPUT_DIR = '.build/azhou-dsh-plugin'
STAGE_PARENT = '.build/azhou-stage.dsh-plugin'
MAX_PLUGIN_ICON_BYTES = 256 * 1024
ICON_EDGE_PX = 256
PATCH_YAML = "- insert:\n    - id: azhou-agent-skin\n      name: 'azhou-agent-skin'\n"
LOCALES = {
    'zh': {'meta': {'title': '阿舟 AI 实验室 for DeepSeek Harness',
                    'description': '为 DeepSeek Harness 带来阿舟启动动画、设置中的外观面板与主区壁纸皮肤。'}},
    'en': {'meta': {'title': 'Azhou AI Lab for DeepSeek Harness',
                    'description': ('Brings the Azhou startup animation, the settings appearance panel, '
                                    'and the main-surface wallpaper skin to DeepSeek Harness.')}},
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
_CLIENT_SECTION_FACTORY = (
    "    // 「阿舟主题与外观」设置页组件（settings.section 插槽，对齐 dsh-pet 的 pet-config\n"
    "    // 形态）：容器 div 里由控制器的 mountSettings 挂面板 iframe。宿主设置弹窗拥有\n"
    "    // Esc 与遮罩，本组件只负责挂载/卸载时的装拆，不引入自己的关闭层。\n"
    "    const SECTION_STYLE = Object.freeze({\n"
    "      position: 'relative', boxSizing: 'border-box', width: '100%', maxWidth: '720px',\n"
    "      height: '100%', minHeight: '0', background: 'transparent',\n"
    "      color: 'var(--dsw-alias-label-primary)', fontFamily: 'inherit', fontSize: '13px', lineHeight: '20px',\n"
    "    });\n"
    "    function makeAzhouAppearanceSection({ h, useEffect, useRef }) {\n"
    "      return function AzhouAppearanceSection(props) {\n"
    "        const container = useRef(null);\n"
    "        const closeRef = useRef(null);\n"
    "        useEffect(() => { closeRef.current = typeof props?.close === 'function' ? props.close : null; });\n"
    "        useEffect(() => {\n"
    "          const node = container.current;\n"
    "          const startup = globalThis.__azhouStartup;\n"
    "          if (!node || !startup || typeof startup.mountSettings !== 'function') return undefined;\n"
    "          const dispose = startup.mountSettings(node, { onClose: () => closeRef.current?.() });\n"
    "          return () => { try { dispose?.(); } catch {} };\n"
    "        }, []);\n"
    "        return h('div', { ref: container, style: SECTION_STYLE, 'data-agent-skin-settings-mount': '' });\n"
    "      };\n"
    "    }\n"
)
_CLIENT_SETTINGS_REGISTER = (
    "      // 注册「阿舟主题与外观」设置页：settings.section 插槽一次注册；ctx.effect\n"
    "      // 立即执行回调，插件停用时随 cordis 一并回收。React 从模块加载器平台表取。\n"
    "      const zhLocale = () => /^zh/i.test(document.documentElement?.lang || host.navigator?.language || '');\n"
    "      try {\n"
    "      ctx.effect(() => {\n"
    "        const slots = ctx.slots;\n"
    "        if (!slots || typeof slots.inject !== 'function' || typeof slots.register !== 'function') {\n"
    "          return () => {};\n"
    "        }\n"
    "        let section = null;\n"
    "        try {\n"
    "          const react = require('react');\n"
    "          section = makeAzhouAppearanceSection({\n"
    "            h: require('react/jsx-runtime').jsx,\n"
    "            useEffect: react.useEffect, useRef: react.useRef,\n"
    "          });\n"
    "        } catch {\n"
    "          // 平台表缺 react 时退化为纯 overlay：启动动画不受设置页影响。\n"
    "          return () => {};\n"
    "        }\n"
    "        slots.inject('settings.section', function* () {\n"
    "          yield slots.register({\n"
    "            name: 'settings.section', id: 'azhou-appearance', order: 40,\n"
    "            label: () => (zhLocale() ? '阿舟主题与外观' : 'Azhou appearance'),\n"
    "          }, section);\n"
    "        });\n"
    "        return () => {};\n"
    "      }, 'azhou-agent-skin: settings-section');\n"
    "      } catch {\n"
    "        // 设置页注册失败时退化为纯 overlay：激活永不因它失败。\n"
    "      }\n"
)
_CLIENT_CLOSE = (
    "    };\n"
    # The settings-section registration reads ctx.slots, a cordis service;
    # an undeclared service access throws and fails activation, so declare it.
    "    const inject = ['slots'];\n"
    + _CLIENT_SECTION_FACTORY
    + "    function apply(ctx) {\n"
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
    + _CLIENT_SETTINGS_REGISTER
    + "      const adapterCleanup = (resource) => {\n"
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
            or 'createCodexPageAdapter(' in payload):
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


def _compose_package(destination: Path, *, body: str, host_entry: str, icon: bytes, theme: dict,
                     inputs: dict, artifacts) -> dict:
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
        'index.js': host_entry.encode('utf-8'),
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


def verified_startup_stage(stage_root: Path, artifacts, created):
    receipt = artifacts.tree_receipt(stage_root)
    if receipt[:2] != created:
        raise RuntimeError(f'DSH 暂存根已替换，保留：{stage_root}')
    files = {'azhou-payload/Contents/Resources/' + name for name in artifacts.DSH_STARTUP_OUTPUTS}
    files.add('azhou-payload/Contents/Resources/startup/manifest.json')
    directories = {parent.as_posix() for name in files for parent in Path(name).parents if parent != Path('.')}
    expected = {**{name: 'file' for name in files}, **{name: 'directory' for name in directories}}
    if {entry[0]: entry[1] for entry in receipt[3]} != expected:
        raise RuntimeError(f'DSH 暂存含未知或缺失对象，保留：{stage_root}')
    return receipt


def verified_compose_work(work, initial, artifacts):
    receipt = artifacts.tree_receipt(work)
    if receipt[:2] != initial:
        raise RuntimeError(f'DSH 组合暂存根已替换，保留：{work}')
    files = {f'{side}/{PLUGIN_NAME}/{name}' for side in ('first', 'second')
             for name in artifacts.DSH_PLUGIN_PACKAGE_ENTRIES}
    directories = {parent.as_posix() for name in files for parent in Path(name).parents if parent != Path('.')}
    expected = {**{name: 'file' for name in files}, **{name: 'directory' for name in directories}}
    if {entry[0]: entry[1] for entry in receipt[3]} != expected:
        raise RuntimeError(f'DSH 组合暂存含未知或缺失对象，保留：{work}')
    return receipt


def dsh_receipt_path(root, destination, tree):
    identity = json.dumps({'destination': str(destination), 'tree': tree}, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()
    return root / '.build' / f'.azhou-dsh-{digest}.json'


def verify_dsh_receipt(root, destination, tree):
    path = dsh_receipt_path(root, destination, tree)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'DSH 旧输出缺少本项目回执，保留：{destination}')
    with path.open('r', encoding='utf-8') as stream:
        data = json.load(stream)
    expected = {'projectRoot': str(root), 'destination': str(destination), 'tree': tree}
    if json.dumps(data, ensure_ascii=False, sort_keys=True) != json.dumps(expected, ensure_ascii=False, sort_keys=True):
        raise RuntimeError(f'DSH 输出回执不匹配，保留：{destination}')


def create_dsh_receipt(root, destination, tree):
    path = dsh_receipt_path(root, destination, tree)
    data = {'projectRoot': str(root), 'destination': str(destination), 'tree': tree}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        verify_dsh_receipt(root, destination, tree)


def dsh_tree_content(tree):
    return (tree[2], [(item[0], item[1], item[4], item[5] if len(item) > 5 else None)
                      for item in tree[3]])


def publish_dsh_candidate(first, second, destination, work, initial, work_receipt, root, artifacts, lock, lock_fd):
    def require_work():
        current = work.lstat()
        if (current.st_dev, current.st_ino) != initial:
            raise RuntimeError(f'DSH 组合暂存已替换，保留：{work}')
        lock.checked_lock_file(lock_fd)

    require_work()
    new_tree, second_tree = artifacts.tree_receipt(first), artifacts.tree_receipt(second)
    artifacts.verify_dsh_plugin(first)
    if destination.is_symlink():
        raise RuntimeError(f'拒绝覆写符号链接 DSH 插件目录：{destination}')
    old_tree = artifacts.tree_receipt(destination) if destination.exists() else None
    reused = False
    if old_tree is not None:
        try:
            verify_dsh_receipt(root, destination, old_tree)
        except RuntimeError:
            if dsh_tree_content(old_tree) != dsh_tree_content(new_tree):
                raise
            artifacts.verify_dsh_plugin(destination)
            reused = True
    artifacts.require_tree(work, work_receipt)
    marker = work / '.dsh-transaction.json'
    marker_info = None
    if not reused:
        create_dsh_receipt(root, destination, new_tree)
        with marker.open('x', encoding='utf-8') as stream:
            json.dump({'projectRoot': str(root), 'destination': str(destination),
                       'new': new_tree, 'old': old_tree}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        marker_info = marker.lstat()
        require_work()
        artifacts.require_tree(first, new_tree)
        if old_tree is None:
            artifacts.rename_exclusive(first, destination)
        else:
            artifacts.require_tree(destination, old_tree)
            artifacts.swap(first, destination)
    try:
        artifacts.require_tree(destination, old_tree if reused else new_tree)
        if old_tree is not None and not reused:
            artifacts.require_tree(first, old_tree)
        artifacts.verify_dsh_plugin(destination)
        require_work()
    except BaseException as error:
        if not reused:
            try:
                require_work()
                artifacts.require_tree(destination, new_tree)
                if old_tree is None:
                    artifacts.rename_exclusive(destination, first)
                else:
                    artifacts.require_tree(first, old_tree)
                    artifacts.swap(first, destination)
                    artifacts.require_tree(destination, old_tree)
                artifacts.require_tree(first, new_tree)
            except BaseException as rollback_error:
                raise RuntimeError(f'DSH 输出回滚未确认，保留待核对：{work}、{destination}') from rollback_error
        raise error
    if old_tree is not None:
        artifacts.require_tree(first, new_tree if reused else old_tree)
        require_work()
        shutil.rmtree(first)
    artifacts.require_tree(second, second_tree)
    require_work()
    shutil.rmtree(second)
    first.parent.rmdir()
    second.parent.rmdir()
    if marker_info is not None:
        current = marker.lstat()
        if (current.st_dev, current.st_ino) != (marker_info.st_dev, marker_info.st_ino):
            raise RuntimeError(f'DSH 恢复标记已变化，保留：{work}')
        marker.unlink()
    require_work()
    work.rmdir()


def build_plugin(destination: Path | None = None, *, root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    spec = importlib.util.spec_from_file_location('agent_skin_build_lock', root / 'tools/build-lock.py')
    if spec is None or spec.loader is None:
        raise RuntimeError('Missing build lock module.')
    lock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lock)
    with lock.acquired() as lock_fd:
        return _build_plugin_locked(destination, root=root, lock=lock, lock_fd=lock_fd)


def _build_plugin_locked(destination: Path | None, *, root: Path, lock, lock_fd: int) -> dict:
    destination = Path(destination).expanduser().absolute() if destination is not None else root / PLUGIN_OUTPUT_DIR / PLUGIN_NAME
    builder = load_builder(root)
    artifacts = builder.load_artifacts(root)
    theme = artifacts.load_theme_config(root, require_inputs=True)

    build_dir = root / '.build'
    if build_dir.is_symlink():
        raise RuntimeError('拒绝通过符号链接 .build 目录构建 DSH 插件。')
    build_dir.mkdir(parents=True, exist_ok=True)

    legacy_stage = root / STAGE_PARENT / 'azhou-payload'
    if legacy_stage.is_symlink():
        raise RuntimeError('拒绝通过符号链接 staging 目录构建 DSH 插件。')
    stage_root = Path(tempfile.mkdtemp(prefix='azhou-stage.dsh-', dir=build_dir))
    initial = stage_root.lstat()
    stage = stage_root / 'azhou-payload'
    completed = False
    try:
        builder.build_startup(stage, root=root, host='dsh', lock_fd=lock_fd)
        stage_receipt = verified_startup_stage(stage_root, artifacts, (initial.st_dev, initial.st_ino))
        payload = (stage / 'Contents/Resources/startup/install.js').read_text(encoding='utf-8')
        body = _payload_body(payload)
        icon = _render_icon(root, artifacts, theme)
        inputs = artifacts.source_inputs()
        host_entry = artifacts.dsh_host_entry_source(root)
        work = Path(tempfile.mkdtemp(prefix='azhou-dsh-compose-', dir=build_dir))
        initial_work = work.lstat()
        try:
            first, second = work / 'first' / PLUGIN_NAME, work / 'second' / PLUGIN_NAME
            manifest = _compose_package(first, body=body, host_entry=host_entry, icon=icon, theme=theme,
                                        inputs=inputs, artifacts=artifacts)
            _compose_package(second, body=body, host_entry=host_entry, icon=icon, theme=theme,
                             inputs=inputs, artifacts=artifacts)
            _assert_identical(first, second)
            _assert_no_path_leak(first, root)
            work_identity = (initial_work.st_dev, initial_work.st_ino)
            work_receipt = verified_compose_work(work, work_identity, artifacts)
            artifacts.require_tree(stage_root, stage_receipt)
            lock.checked_lock_file(lock_fd)
            if (destination.parent.resolve() != destination.parent or destination in (stage_root, work)
                    or stage_root in destination.parents or work in destination.parents):
                raise RuntimeError(f'DSH 输出路径含别名或嵌入暂存，保留未处理：{destination}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            publish_dsh_candidate(first, second, destination, work,
                                  work_identity, work_receipt, root, artifacts, lock, lock_fd)
        except BaseException:
            print(f'DSH 组合暂存保留待核对：{work}', file=sys.stderr)
            raise
        completed = True
    finally:
        if completed:
            try:
                lock.checked_lock_file(lock_fd)
                artifacts.require_tree(stage_root, stage_receipt)
                shutil.rmtree(stage_root)
            except BaseException:
                print(f'DSH 构建暂存保留待核对：{stage_root}', file=sys.stderr)
                raise
        else:
            print(f'DSH 构建未完成，暂存保留待核对：{stage_root}', file=sys.stderr)
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
