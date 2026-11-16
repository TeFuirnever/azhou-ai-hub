#!/usr/bin/env python3
"""End-to-end tests for the DeepSeek Harness plugin package emitter."""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PACKAGE = Path(__file__).resolve().parents[1]
TOOLS = PACKAGE / "tools"
EMITTER_PATH = TOOLS / "build-dsh-plugin.py"
APP_PACKAGE = json.loads((PACKAGE / "hub-package.json").read_text(encoding="utf-8"))
APP_VERSION = APP_PACKAGE["runtime_version"]
APP_BUILD = str(APP_PACKAGE["runtime_build"])


def load_module(path: Path, name: str):
    path = Path(path)
    if path.name in {"verify-artifacts.py", "build-wallpaper.py", "build-preflight.py", "build-dsh-plugin.py"}:
        canonical = TOOLS / path.name
        if path.resolve() != canonical.resolve() and path.read_bytes() != canonical.read_bytes():
            raise AssertionError(f"coverage-mapped source differs from canonical source: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vision_runner(helpers, real_run):
    """Mock the Swift Vision pipeline while letting sips reach the real tool."""

    def run(command, **kwargs):
        if command[0] == "xcrun" or Path(command[0]).name == "sips":
            return real_run(command, **kwargs)
        helpers.synthetic_png(Path(command[3]), 512, 512, lambda x, y: (240, 80, 30, 255))
        helpers.synthetic_png(Path(command[4]), 1536, 1024, lambda x, y: (30, 70, 110, 255))
        Path(command[5]).write_text(json.dumps([[[10, 20], [30, 40]]]), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    return run


class DshPluginBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin" or shutil.which("xcrun") is None or shutil.which("sips") is None:
            raise unittest.SkipTest("DSH plugin assembly requires macOS Vision and sips")
        cls.temporary = tempfile.TemporaryDirectory(prefix="agent-skin-dsh-plugin-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = (Path(cls.temporary.name) / "source").resolve()
        cls.helpers = load_module(TOOLS / "test-startup-build.py", "agent_skin_dsh_fixture_helpers")
        cls.helpers.clone_source_tree(cls.root)
        cls.emitter = load_module(EMITTER_PATH, "agent_skin_dsh_plugin_emitter")
        cls.artifacts = load_module(cls.root / "tools/verify-artifacts.py", "agent_skin_dsh_artifacts")
        cls.destination = cls.root / ".build/azhou-dsh-plugin/azhou-agent-skin"
        real_run = subprocess.run
        # staticmethod: a bare function on the class would bind as a method when
        # tests read self.vision for mock side_effect, doubling its first argument.
        cls.vision = staticmethod(vision_runner(cls.helpers, real_run))
        cls.manifest = cls.build_plugin(cls.destination)

    @classmethod
    def build_plugin(cls, destination):
        with mock.patch.object(subprocess, "check_output", return_value="arm64\n"), \
                mock.patch.object(subprocess, "run", side_effect=cls.vision):
            return cls.emitter.build_plugin(destination, root=cls.root)

    def snapshot(self, base: Path) -> dict:
        return {item.relative_to(base).as_posix(): item.read_bytes()
                for item in sorted(base.rglob("*")) if item.is_file()}

    def test_package_tree_loader_binding_and_owner_strings(self):
        self.assertEqual(sorted(self.snapshot(self.destination)),
                         sorted(self.artifacts.DSH_PLUGIN_PACKAGE_ENTRIES))
        client = (self.destination / "client.js").read_text(encoding="utf-8")
        for needle, count in (
            ("window.__ModuleLoader__.load({", 1),
            ("id: 'azhou-agent-skin',", 1),
            ("factory(require) {", 1),
            ("const runStartup = (registerCleanup) => {", 1),
            ("function createDSHPageAdapter(", 1),
            ("const pageAdapter = createDSHPageAdapter(globalThis, { build: { version: APP_VERSION, buildNumber: "
             + json.dumps(APP_BUILD) + " }, sidebarEntry: false }, {", 1),
            ("    installRenderer,\n    createWallpaperApplicator,\n    registerCleanup,\n  });", 1),
            ("controllerOwner: 'azhou-dsh-startup'", 1),
            ("owner: 'azhou.dsh-startup-animation'", 1),
            ("playbackOwner: 'dsh-gated'", 1),
            ("const DEFAULT_ASSETS = Object.freeze(", 1),
            ("function apply(ctx) {", 1),
            ("const inject = ['slots'];", 1),
            ("slots.inject('settings.section', function* () {", 1),
            ("name: 'settings.section', id: 'azhou-appearance', order: 40,", 1),
            ("startup.mountSettings(node, { onClose: () => closeRef.current?.() })", 1),
            ("module.exports = { apply, inject };", 1),
        ):
            with self.subTest(needle=needle):
                self.assertEqual(client.count(needle), count)
        self.assertNotIn("createCodexPageAdapter(", client)
        self.assertNotIn("((controllerMetadata) => {", client)
        self.assertNotIn("playbackOwner: 'native'", client,
                         "DSH never adopts the Codex native owner")
        self.assertLess(len(client.encode("utf-8")), 24 * 1024 * 1024)

        package_json = json.loads((self.destination / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package_json["name"], "azhou-agent-skin")
        self.assertIs(package_json["private"], True)
        self.assertEqual(package_json["dsh"]["client"], {"platform": "web", "immediately": True, "inject": []})
        for forbidden in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            self.assertNotIn(forbidden, package_json)
        icon = (self.destination / "icon.png").read_bytes()
        self.assertTrue(icon.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertLessEqual(len(icon), 256 * 1024)
        zh = json.loads((self.destination / "locale/zh.json").read_text(encoding="utf-8"))
        self.assertEqual(zh["meta"]["title"], "阿舟 AI 实验室 for DeepSeek Harness")
        en = json.loads((self.destination / "locale/en.json").read_text(encoding="utf-8"))
        self.assertEqual(en["meta"]["title"], "Azhou AI Lab for DeepSeek Harness")
        self.assertTrue(en["meta"]["description"].strip())
        self.assertTrue(zh["meta"]["description"].strip())

        node = shutil.which("node")
        if node is not None:
            syntax = subprocess.run([node, "--check", str(self.destination / "client.js")],
                                    check=False, capture_output=True, text=True)
            self.assertEqual(syntax.returncode, 0, syntax.stderr)
            host_entry_check = subprocess.run([
                node, "--input-type=module", "-e", """
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const entry = await import(pathToFileURL(process.argv.at(-1)));
let listener;
entry.apply({ on(name, callback) { assert.equal(name, 'webserver/index-inject'); listener = callback; } });
assert.equal(typeof listener, 'function');
const rows = [];
listener(rows);
assert.equal(rows.length, 1);
assert.deepEqual(rows[0], { kind: 'script', placement: 'head', text: rows[0].text });
assert.match(rows[0].text, /__azhouDshStartupGateDocumentLatch/);
assert.match(rows[0].text, /getComputedStyle/);
listener(rows);
assert.equal(rows.length, 1, 'duplicate host injection registers one bridge per index');
""", str(self.destination / "index.js")], check=False, capture_output=True, text=True)
            self.assertEqual(host_entry_check.returncode, 0, host_entry_check.stderr)
        self.artifacts.verify_dsh_plugin(self.destination)

    def test_manifest_binds_current_inputs_and_package_digests(self):
        manifest = json.loads((self.destination / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["schema"], manifest["protocolVersion"], manifest["targetHost"]), (1, 1, "dsh"))
        self.assertEqual((manifest["appVersion"], manifest["appBuild"]), (APP_VERSION, APP_BUILD))
        self.assertIn("no install or host writes", manifest["scope"])
        inputs = self.artifacts.source_inputs()
        self.assertEqual(manifest["inputSHA256"], self.artifacts.aggregate_inputs(inputs))
        self.assertEqual(set(manifest["sourceInputs"]), set(self.artifacts.DSH_PLUGIN_REQUIRED_INPUTS))
        for name, digest in manifest["sourceInputs"].items():
            self.assertEqual(digest, inputs[name])
        self.assertEqual(set(manifest["outputs"]), set(self.artifacts.DSH_PLUGIN_OUTPUTS))
        self.assertNotIn("manifest.json", manifest["outputs"])
        for relative, digest in manifest["outputs"].items():
            self.assertEqual(hashlib.sha256((self.destination / relative).read_bytes()).hexdigest(), digest)

    def test_second_full_build_is_byte_identical(self):
        second = self.root / ".build/azhou-dsh-plugin-second/azhou-agent-skin"
        self.build_plugin(second)
        self.assertEqual(self.snapshot(self.destination), self.snapshot(second),
                         "a second full assembly must reproduce every package byte")

    def test_assembly_rejects_different_outputs_and_replaced_stages(self):
        with tempfile.TemporaryDirectory(prefix="agent-skin-dsh-safety-") as temporary:
            root = Path(temporary)
            first, second = root / "first", root / "second"
            first.mkdir()
            second.mkdir()
            (first / "index.js").write_text("one", encoding="utf-8")
            (second / "index.js").write_text("two", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "not deterministic"):
                self.emitter._assert_identical(first, second)
            (second / "index.js").unlink()
            with self.assertRaisesRegex(RuntimeError, "not deterministic"):
                self.emitter._assert_identical(first, second)

            artifacts = mock.Mock()
            artifacts.tree_receipt.return_value = (1, 2, None, [])
            with self.assertRaisesRegex(RuntimeError, "暂存根已替换"):
                self.emitter.verified_startup_stage(root, artifacts, (3, 4))
            artifacts.DSH_STARTUP_OUTPUTS = ("startup/install.js",)
            with self.assertRaisesRegex(RuntimeError, "未知或缺失对象"):
                self.emitter.verified_startup_stage(root, artifacts, (1, 2))
            with self.assertRaisesRegex(RuntimeError, "暂存根已替换"):
                self.emitter.verified_compose_work(root, (3, 4), artifacts)

    def test_verify_dsh_plugin_rejects_tampering(self):
        def mutate_client(replacement):
            def mutate(path):
                client = path / "client.js"
                client.write_text(replacement(client.read_text(encoding="utf-8")), encoding="utf-8")
            return mutate

        cases = (
            (mutate_client(lambda text: text.replace("createDSHPageAdapter", "createRetitledPageAdapter")),
             "恰好绑定一次|外来适配器"),
            (mutate_client(lambda text: text + "\nexport function leak() {}\n"), "模块导入|external"),
            (mutate_client(lambda text: text + "\nfetch('https://example.invalid/x');\n"), "外部资源|external"),
            (mutate_client(lambda text: text.replace(
                "const inject = ['slots'];", "const inject = ['slots'];\n    const inject = ['slots'];")), "恰好绑定一次|exactly once"),
            (lambda path: (path / "manifest.json").write_text(json.dumps({
                **json.loads((path / "manifest.json").read_text(encoding="utf-8")), "appVersion": "99.0.0"}),
                encoding="utf-8"), "manifest"),
            (lambda path: (path / "package.json").write_text(json.dumps({
                **json.loads((path / "package.json").read_text(encoding="utf-8")), "dependencies": {"x": "1.0.0"}}),
                encoding="utf-8"), "package.json"),
            (lambda path: (path / "cordis.patch.yml").write_text(
                "- insert:\n    - id: other\n      name: 'other'\n"), "patch"),
            (lambda path: (path / "locale/en.json").write_text(
                json.dumps({"meta": {"title": "", "description": "x"}}), encoding="utf-8"), "locale"),
            (lambda path: (path / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\nbroken"), "PNG"),
            (lambda path: (path / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 257 * 1024), "256 KiB"),
            (lambda path: (path / "extra.txt").write_text("x", encoding="utf-8"), "文件清单|file set"),
            (lambda path: (path / "index.js").unlink(), "文件清单|缺失"),
            (lambda path: (path / "client.js").write_bytes(
                (path / "client.js").read_text(encoding="utf-8").encode("utf-8") + b"tampered"), "manifest|摘要"),
        )
        for index, (mutate, message) in enumerate(cases):
            with self.subTest(case=index):
                clone = Path(self.temporary.name) / f"dsh-tamper-{index}"
                if clone.exists():
                    shutil.rmtree(clone)
                shutil.copytree(self.destination, clone)
                mutate(clone)
                with self.assertRaisesRegex(RuntimeError, message):
                    self.artifacts.verify_dsh_plugin(clone)

    def test_client_module_guard_rejects_non_dsh_pages_without_effects(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("client guard probe requires Node.js")
        probe = (
            "const fs = require('node:fs');\n"
            "const vm = require('node:vm');\n"
            "const effects = [];\n"
            "const sandbox = {\n"
            "  window: {}, console,\n"
            "  document: { readyState: 'complete', body: {}, addEventListener() {}, removeEventListener() {} },\n"
            "};\n"
            "sandbox.window.__ModuleLoader__ = { load(spec) { sandbox.__spec = spec; } };\n"
            "sandbox.globalThis = sandbox;\n"
            "vm.createContext(sandbox);\n"
            "vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);\n"
            "if (sandbox.__spec.id !== 'azhou-agent-skin') throw new Error('loader id');\n"
            "const exported = sandbox.__spec.factory((name) => { throw new Error('unexpected require ' + name); });\n"
            "if (typeof exported.apply !== 'function' || !Array.isArray(exported.inject)) throw new Error('module shape');\n"
            "const ctx = { effect(fn, label) { effects.push(label); fn(); return () => {}; } };\n"
            "const result = exported.apply(ctx);\n"
            "if (result.installed !== false || result.reason !== 'page-unsupported') throw new Error('guard ' + JSON.stringify(result));\n"
            "if (effects.length !== 0) throw new Error('guard must not touch ctx.effect');\n"
            "console.log('dsh-client-guard:ok');\n"
        )
        result = subprocess.run([node, "-e", probe, str(self.destination / "client.js")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("dsh-client-guard:ok", result.stdout)

    def test_client_registers_the_settings_section_once_with_react_degrade(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("settings-section probe requires Node.js")
        probe = (
            "const fs = require('node:fs');\n"
            "const vm = require('node:vm');\n"
            "const effects = [];\n"
            "const injections = [];\n"
            "const registrations = [];\n"
            "const requires = [];\n"
            "const withReact = process.argv[2] === 'with-react';\n"
            "const modules = withReact ? {\n"
            "  react: { useState() {}, useEffect() {}, useRef() {} },\n"
            "  'react/jsx-runtime': { jsx() {} },\n"
            "} : {};\n"
            "const loader = { load(spec) { sandbox.__spec = spec; } };\n"
            "const sandbox = {\n"
            "  window: {}, console,\n"
            "  document: { readyState: 'loading', body: {}, documentElement: { lang: 'zh-CN' },\n"
            "    addEventListener() {}, removeEventListener() {} },\n"
            "  __DSH_BOOT__: { carrier: 'probe' },\n"
            "  __ModuleLoader__: loader,\n"
            "  effect(fn, label) { effects.push(label); fn(); return () => {}; },\n"
            "};\n"
            "sandbox.window.__ModuleLoader__ = loader;\n"
            "sandbox.globalThis = sandbox;\n"
            "sandbox.__spec = null;\n"
            "vm.createContext(sandbox);\n"
            "vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), sandbox);\n"
            "if (sandbox.__spec.id !== 'azhou-agent-skin') throw new Error('loader id');\n"
            "const exported = sandbox.__spec.factory((name) => {\n"
            "  if (!(name in modules)) throw new Error('unexpected require ' + name);\n"
            "  requires.push(name);\n"
            "  return modules[name];\n"
            "});\n"
            "const ctx = { effect: sandbox.effect,\n"
            "  slots: { inject(name, factory) { injections.push({ name, factory }); },\n"
            "    register(def, component) { registrations.push({ def, component }); } } };\n"
            "const result = exported.apply(ctx);\n"
            "if (result.installed !== false || result.reason !== 'dom-loading') {\n"
            "  throw new Error('dom-loading result ' + JSON.stringify(result));\n"
            "}\n"
            "if (!effects.includes('azhou-agent-skin: settings-section')) throw new Error('effect label');\n"
            "if (withReact) {\n"
            "  if (injections.length !== 1 || injections[0].name !== 'settings.section') {\n"
            "    throw new Error('slot inject ' + JSON.stringify(injections));\n"
            "  }\n"
            "  if (injections[0].factory?.constructor?.name !== 'GeneratorFunction') {\n"
            "    throw new Error('inject takes a registration generator');\n"
            "  }\n"
            "  let yields = 0;\n"
            "  for (const yielded of injections[0].factory()) { yields += 1; }\n"
            "  if (yields !== 1 || registrations.length !== 1) throw new Error('register exactly once');\n"
            "  const def = registrations[0].def;\n"
            "  if (def.name !== 'settings.section' || def.id !== 'azhou-appearance' || def.order !== 40) {\n"
            "    throw new Error('slot definition ' + JSON.stringify(def));\n"
            "  }\n"
            "  if (def.label() !== '阿舟主题与外观') throw new Error('zh label ' + def.label());\n"
            "  sandbox.document.documentElement.lang = 'en-US';\n"
            "  if (def.label() !== 'Azhou appearance') throw new Error('en label ' + def.label());\n"
            "  if (typeof registrations[0].component !== 'function') throw new Error('section component');\n"
            "  if (JSON.stringify(requires) !== JSON.stringify(['react', 'react/jsx-runtime'])) {\n"
            "    throw new Error('platform requires ' + JSON.stringify(requires));\n"
            "  }\n"
            "  console.log('dsh-client-settings-section:ok');\n"
            "} else {\n"
            "  if (requires.length !== 0) throw new Error('degraded require ' + JSON.stringify(requires));\n"
            "  if (injections.length !== 0 || registrations.length !== 0) throw new Error('degrade kept the slot quiet');\n"
            "  if (!effects.includes('azhou-agent-skin: document-ready')) throw new Error('bootstrap still armed');\n"
            "  console.log('dsh-client-settings-section-degrade:ok');\n"
            "}\n"
        )
        for variant, marker in (("with-react", "dsh-client-settings-section:ok"),
                                ("without-react", "dsh-client-settings-section-degrade:ok")):
            result = subprocess.run([node, "-e", probe, str(self.destination / "client.js"), variant],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(marker, result.stdout)

    def test_local_build_path_leak_refuses_before_any_destination_write(self):
        destination = self.root / ".build/azhou-dsh-plugin-leak/azhou-agent-skin"
        poisoned = "  const leak = '" + str(self.root) + "';\n"
        with mock.patch.object(self.emitter, "_payload_body", return_value=poisoned):
            with self.assertRaisesRegex(RuntimeError, "leaks the local build path"):
                self.build_plugin(destination)
        self.assertFalse(destination.exists())

    def test_oversize_icon_refuses_to_assemble(self):
        destination = self.root / ".build/azhou-dsh-plugin-oversize/azhou-agent-skin"
        with mock.patch.object(self.emitter, "MAX_PLUGIN_ICON_BYTES", 1024):
            with self.assertRaisesRegex(RuntimeError, "icon"):
                self.build_plugin(destination)
        self.assertFalse(destination.exists())

    def test_missing_private_inputs_fail_closed(self):
        root = (Path(self.temporary.name) / "missing-private-source").resolve()
        self.helpers.clone_source_tree(root, private=False)
        emitter = load_module(root / "tools/build-dsh-plugin.py", "agent_skin_dsh_missing_inputs_emitter")
        destination = root / ".build/azhou-dsh-plugin/azhou-agent-skin"
        with self.assertRaisesRegex(RuntimeError, "assets/private|私有素材"):
            emitter.build_plugin(destination, root=root)
        self.assertFalse(destination.exists())

    def test_payload_body_refuses_foreign_and_tail_less_payloads(self):
        with self.assertRaisesRegex(RuntimeError, "codex-style single-adapter expression"):
            self.emitter._payload_body("((controllerMetadata) => { createDSHPageAdapter(globalThis); })()\n")
        tail_less = ("(() => {\nfunction createDSHPageAdapter(host) { return host; }\n"
                     "const pageAdapter = createDSHPageAdapter(globalThis);\n})()\n")
        with self.assertRaisesRegex(RuntimeError, "fixed adapter wiring tail"):
            self.emitter._payload_body(tail_less)

    def test_load_builder_refuses_when_no_module_loader_can_be_created(self):
        with mock.patch.object(importlib.util, "spec_from_file_location", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Missing startup builder module"):
                self.emitter.load_builder(self.root)

    def test_render_icon_refuses_without_the_macos_sips_tool(self):
        theme = self.artifacts.load_theme_config(self.root, require_inputs=True)
        with mock.patch.object(shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "requires the macOS sips tool"):
                self.emitter._render_icon(self.root, self.artifacts, theme)

    def test_compose_package_refuses_existing_destination(self):
        theme = self.artifacts.load_theme_config(self.root, require_inputs=True)
        destination = Path(self.temporary.name) / "compose-existing"
        destination.mkdir()
        with self.assertRaisesRegex(RuntimeError, "Refusing to compose over an existing directory"):
            self.emitter._compose_package(destination, body="const placeholder = 1;\n",
                                          host_entry=self.artifacts.dsh_host_entry_source(self.root),
                                          icon=b"\x89PNG\r\n\x1a\n", theme=theme,
                                          inputs=self.artifacts.source_inputs(), artifacts=self.artifacts)
        self.assertTrue(destination.is_dir())

    def test_build_refuses_symlinked_build_and_stage_directories(self):
        build_dir = self.root / ".build"
        relocated = self.root / ".build-relocated"
        build_dir.rename(relocated)
        (self.root / ".build").symlink_to(relocated, target_is_directory=True)
        try:
            with self.assertRaisesRegex(RuntimeError, "符号链接 \\.build 目录"):
                self.emitter.build_plugin(self.root / ".build/azhou-dsh-plugin-x/azhou-agent-skin",
                                          root=self.root)
        finally:
            (self.root / ".build").unlink()
            relocated.rename(build_dir)

        stage_parent = self.root / self.emitter.STAGE_PARENT
        stage_parent.mkdir(parents=True)
        (stage_parent / "azhou-payload").symlink_to(relocated / "azhou-dsh-plugin", target_is_directory=True)
        try:
            with self.assertRaisesRegex(RuntimeError, "符号链接 staging 目录"):
                self.emitter.build_plugin(self.root / ".build/azhou-dsh-plugin-y/azhou-agent-skin",
                                          root=self.root)
        finally:
            (stage_parent / "azhou-payload").unlink()
            stage_parent.rmdir()

    def test_build_refuses_to_replace_a_symlinked_destination(self):
        target = Path(self.temporary.name) / "symlink-target"
        target.mkdir()
        (target / "keep.txt").write_text("keep", encoding="utf-8")
        destination = self.root / ".build/azhou-dsh-plugin-symlink/azhou-agent-skin"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "拒绝覆写符号链接"):
            self.build_plugin(destination)
        self.assertTrue(destination.is_symlink())
        self.assertEqual([item.name for item in sorted(target.iterdir())], ["keep.txt"])

    def test_rebuild_replaces_existing_destination_and_tolerates_stage_leftovers(self):
        destination = self.root / ".build/azhou-dsh-plugin-rebuild/azhou-agent-skin"
        stage_parent = self.root / self.emitter.STAGE_PARENT
        stage_parent.mkdir(parents=True)
        (stage_parent / "azhou-payload").mkdir()
        (stage_parent / "azhou-payload" / "stale.txt").write_text("stale", encoding="utf-8")
        leftover = stage_parent / "leftover.txt"
        leftover.write_text("leftover", encoding="utf-8")
        stages_before = set((self.root / ".build").glob("azhou-stage.dsh-*"))
        manifest = self.build_plugin(destination)
        self.assertEqual(sorted(self.snapshot(destination)),
                         sorted(self.artifacts.DSH_PLUGIN_PACKAGE_ENTRIES))
        self.assertTrue(leftover.is_file(), "unrelated staging leftovers must survive cleanup")
        self.assertEqual((stage_parent / "azhou-payload/stale.txt").read_text(encoding="utf-8"), "stale")
        self.assertEqual(set((self.root / ".build").glob("azhou-stage.dsh-*")), stages_before)

        argv = ["build-dsh-plugin.py", "--output", str(destination)]
        with mock.patch.object(subprocess, "check_output", return_value="arm64\n"), \
                mock.patch.object(subprocess, "run", side_effect=self.vision), \
                mock.patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(io.StringIO()) as captured:
            with self.assertRaises(SystemExit) as caught:
                load_module(self.root / "tools/build-dsh-plugin.py", "__main__")
        self.assertEqual(caught.exception.code, 0)
        summary = json.loads(captured.getvalue())
        self.assertEqual((summary["kind"], summary["plugin"]), ("dshPlugin", self.emitter.PLUGIN_NAME))
        self.assertEqual(summary["appVersion"], manifest["appVersion"])
        self.assertEqual(summary["outputs"], len(manifest["outputs"]))
        self.assertEqual(self.snapshot(destination), self.snapshot(self.destination),
                         "a CLI rebuild over an existing destination must stay byte-identical")

    def test_dsh_build_respects_shared_build_lock(self):
        lock_path = self.root / ".build/.agent-skin-build.lock"
        fd = os.open(lock_path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            destination = self.root / ".build/azhou-dsh-plugin-locked/azhou-agent-skin"
            with self.assertRaisesRegex(RuntimeError, "另一个构建"):
                self.build_plugin(destination)
            self.assertFalse(destination.exists())
            self.assertTrue(lock_path.is_file())
        finally:
            os.close(fd)

    def test_unknown_content_added_to_new_stage_is_preserved_before_publish(self):
        destination = self.root / ".build/azhou-dsh-plugin-stage-race/azhou-agent-skin"
        observed = []
        stages_before = set((self.root / ".build").glob("azhou-stage.dsh-*"))

        def inject_unknown(_tree, _root):
            stages = set((self.root / ".build").glob("azhou-stage.dsh-*")) - stages_before
            self.assertEqual(len(stages), 1)
            foreign = next(iter(stages)) / "foreign.txt"
            foreign.write_bytes(b"unknown synthetic file")
            observed.append(foreign)

        with mock.patch.object(self.emitter, "_assert_no_path_leak", side_effect=inject_unknown):
            with self.assertRaisesRegex(RuntimeError, "保留"):
                self.build_plugin(destination)
        self.assertFalse(destination.exists())
        self.assertEqual(observed[0].read_bytes(), b"unknown synthetic file")
        # This fixture owns the test-only stage; production does not remove it.
        shutil.rmtree(observed[0].parent)

    def test_unknown_existing_output_is_preserved(self):
        destination = self.root / ".build/azhou-dsh-unknown/azhou-agent-skin"
        destination.mkdir(parents=True)
        foreign = destination / "foreign.txt"
        foreign.write_bytes(b"unknown synthetic output")
        with self.assertRaisesRegex(RuntimeError, "回执"):
            self.build_plugin(destination)
        self.assertEqual(foreign.read_bytes(), b"unknown synthetic output")
        self.assertEqual([p.name for p in destination.iterdir()], ["foreign.txt"])

    def test_identical_unproven_output_is_reused_without_claiming_it(self):
        destination = self.root / ".build/azhou-dsh-identical/azhou-agent-skin"
        destination.parent.mkdir(parents=True)
        shutil.copytree(self.destination, destination)
        before = destination.stat().st_ino
        before_bytes = self.snapshot(destination)
        self.build_plugin(destination)
        self.assertEqual(destination.stat().st_ino, before)
        self.assertEqual(self.snapshot(destination), before_bytes)

    def test_unknown_compose_file_stops_before_publishing(self):
        destination = self.root / ".build/azhou-dsh-compose-race/azhou-agent-skin"
        captured = []

        def inject(first, _root):
            foreign = first.parent.parent / "foreign.txt"
            foreign.write_bytes(b"unknown compose data")
            captured.append(foreign)

        with mock.patch.object(self.emitter, "_assert_no_path_leak", side_effect=inject):
            with self.assertRaisesRegex(RuntimeError, "保留"):
                self.build_plugin(destination)
        self.assertFalse(destination.exists())
        self.assertEqual(captured[0].read_bytes(), b"unknown compose data")

    def test_verified_output_is_restored_when_post_publish_verification_fails(self):
        destination = self.root / ".build/azhou-dsh-rollback/azhou-agent-skin"
        self.build_plugin(destination)
        before_inode, before_bytes = destination.stat().st_ino, self.snapshot(destination)
        publish = self.emitter.publish_dsh_candidate

        def fail_verification(first, second, dest, work, initial, work_receipt, root, artifacts, lock, lock_fd):
            verify = artifacts.verify_dsh_plugin
            def checked(path):
                if Path(path) == dest:
                    raise RuntimeError("injected verification failure")
                return verify(path)
            with mock.patch.object(artifacts, "verify_dsh_plugin", side_effect=checked):
                return publish(first, second, dest, work, initial, work_receipt, root, artifacts, lock, lock_fd)

        with mock.patch.object(self.emitter, "publish_dsh_candidate", side_effect=fail_verification):
            with self.assertRaisesRegex(RuntimeError, "injected verification failure"):
                self.build_plugin(destination)
        self.assertEqual(destination.stat().st_ino, before_inode)
        self.assertEqual(self.snapshot(destination), before_bytes)

    def test_failed_output_rollback_preserves_both_candidates(self):
        destination = self.root / ".build/azhou-dsh-failed-rollback/azhou-agent-skin"
        self.build_plugin(destination)
        previous = self.snapshot(destination)
        publish = self.emitter.publish_dsh_candidate
        captured = []

        def fail(first, second, dest, work, initial, work_receipt, root, artifacts, lock, lock_fd):
            swap, verify = artifacts.swap, artifacts.verify_dsh_plugin
            calls = 0
            def failing_swap(left, right):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected rollback failure")
                return swap(left, right)
            def failing_verify(path):
                if Path(path) == dest:
                    raise RuntimeError("injected verification failure")
                return verify(path)
            captured.append((first, work))
            with mock.patch.object(artifacts, "swap", side_effect=failing_swap),                  mock.patch.object(artifacts, "verify_dsh_plugin", side_effect=failing_verify):
                return publish(first, second, dest, work, initial, work_receipt, root, artifacts, lock, lock_fd)

        with mock.patch.object(self.emitter, "publish_dsh_candidate", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "回滚未确认"):
                self.build_plugin(destination)
        self.assertEqual(self.snapshot(captured[0][0]), previous)
        self.assertTrue(destination.is_dir())
        self.assertTrue((captured[0][1] / ".dsh-transaction.json").is_file())

    def test_first_output_created_during_publish_is_not_overwritten(self):
        destination = self.root / ".build/azhou-dsh-first-race/azhou-agent-skin"
        publish = self.emitter.publish_dsh_candidate

        def race(first, second, dest, work, initial, work_receipt, root, artifacts, lock, lock_fd):
            exclusive = artifacts.rename_exclusive
            def create_then_publish(source, target):
                target.mkdir()
                (target / "foreign.txt").write_bytes(b"unknown first target")
                exclusive(source, target)
            with mock.patch.object(artifacts, "rename_exclusive", side_effect=create_then_publish):
                return publish(first, second, dest, work, initial, work_receipt, root, artifacts, lock, lock_fd)

        with mock.patch.object(self.emitter, "publish_dsh_candidate", side_effect=race):
            with self.assertRaises(OSError):
                self.build_plugin(destination)
        self.assertEqual((destination / "foreign.txt").read_bytes(), b"unknown first target")

    def test_output_replaced_during_swap_is_preserved(self):
        destination = self.root / ".build/azhou-dsh-swap-race/azhou-agent-skin"
        self.build_plugin(destination)
        before_bytes = self.snapshot(destination)
        moved = destination.parent / "original-moved"
        captured = []
        publish = self.emitter.publish_dsh_candidate

        def race(first, second, dest, work, initial, work_receipt, root, artifacts, lock, lock_fd):
            swap = artifacts.swap
            def replace_then_swap(left, right):
                right.rename(moved)
                right.mkdir()
                (right / "foreign.txt").write_bytes(b"unknown replacement")
                swap(left, right)
                captured.append(left)
            with mock.patch.object(artifacts, "swap", side_effect=replace_then_swap):
                return publish(first, second, dest, work, initial, work_receipt, root, artifacts, lock, lock_fd)

        with mock.patch.object(self.emitter, "publish_dsh_candidate", side_effect=race):
            with self.assertRaisesRegex(RuntimeError, "保留"):
                self.build_plugin(destination)
        self.assertEqual(self.snapshot(moved), before_bytes)
        self.assertEqual((captured[0] / "foreign.txt").read_bytes(), b"unknown replacement")
        self.assertTrue(destination.is_dir())

    def test_main_reports_build_failures_and_exits_nonzero(self):
        with mock.patch.object(sys, "argv", ["build-dsh-plugin.py"]), \
                mock.patch.object(self.emitter, "build_plugin", side_effect=RuntimeError("boom")), \
                contextlib.redirect_stderr(io.StringIO()) as captured:
            with self.assertRaises(SystemExit) as caught:
                self.emitter.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("DSH 插件包构建失败：boom", captured.getvalue())

    def test_verify_cli_entry_verifies_the_assembled_package(self):
        with mock.patch.object(sys, "argv",
                               ["verify-artifacts.py", "--verify-dsh-plugin", str(self.destination)]):
            load_module(self.root / "tools/verify-artifacts.py", "__main__")

        tampered = Path(self.temporary.name) / "dsh-verify-cli-tampered"
        if tampered.exists():
            shutil.rmtree(tampered)
        shutil.copytree(self.destination, tampered)
        (tampered / "index.js").unlink()
        with mock.patch.object(sys, "argv",
                               ["verify-artifacts.py", "--verify-dsh-plugin", str(tampered)]), \
                contextlib.redirect_stderr(io.StringIO()) as captured:
            with self.assertRaises(SystemExit) as caught:
                load_module(self.root / "tools/verify-artifacts.py", "__main__")
        self.assertEqual(caught.exception.code, 1)
        self.assertIn("文件清单", captured.getvalue())

    def test_check_reports_the_verified_dsh_plugin_payload(self):
        staged, _ = self.helpers.build_staged_product(self.root, "dsh-check")
        with mock.patch.object(self.artifacts.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0)), \
                mock.patch.object(self.artifacts, "PAYLOAD", staged), \
                contextlib.redirect_stdout(io.StringIO()) as captured:
            self.artifacts.check()
        report = json.loads(captured.getvalue())
        self.assertEqual(report["kind"], "buildPayload")
        self.assertEqual(report["dshPlugin"], str(self.destination))
        self.assertEqual(report["version"], self.manifest["appVersion"])

    def test_frozen_codex_fixture_builds_still_verify(self):
        codex, artifacts = self.helpers.build_staged_product(self.root, "dsh-round-codex")
        info = {"CFBundleShortVersionString": APP_VERSION, "CFBundleVersion": APP_BUILD}
        inputs = artifacts.source_inputs()
        marker = {"version": APP_VERSION, "build": APP_BUILD,
                  "inputSHA256": artifacts.aggregate_inputs(inputs), "inputs": inputs}
        artifacts.verify_startup(codex, info, marker)
        artifacts.verify_wallpaper(codex, info, marker)

if __name__ == "__main__":
    unittest.main(verbosity=2)
