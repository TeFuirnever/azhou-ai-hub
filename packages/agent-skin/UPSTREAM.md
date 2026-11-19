# 上游来源与授权边界

本文件记录既有 Hub 源码的原始导入来源。2026-10-27 设定 `agent-skin` 为 canonical Hub package 时保留了既有 `packages/codex-startup-animation/` 源目录；本次没有改写原始仓库、commit 或本地安装/Pet 回执身份。

## 来源

- 上游仓库：<https://github.com/panding999/codex-startup-animation>（用户提供的来源地址）
- 本地源仓 `origin`：<https://github.com/TeFuirnever/codex-startup-animation.git>
- 检查时的源仓 `HEAD`：`c743c2b5eceaa7be9dc511d23a1a77f7c4ce6248`
- 工作树基线：上述 `HEAD` 加上 2026-10-26 检查到的未提交修改及未跟踪维护文件。`HEAD` 不代表完整迁移内容，完整输入来自当时的源工作树。

迁移修改包括包路径和失效历史证据链接说明、包级忽略规则与来源元数据，以及八个导入文本文件的 EOF 空行规范化。活动代码的语义保持原样；导入不是原始提交的逐字节镜像。

## 授权状态

源仓根目录没有 `LICENSE`、`NOTICE` 或 `COPYING` 文件，也没有发现授予本包再分发权的许可文本。源仓 `docs/references.md` 说明历史参考项目仅用于研究、未复制其源码；该说明不能替代本项目代码许可，也不覆盖素材权利。

用户已授权本地迁移。Hub 包中记录该上游归属，并保留源工作树当时维护的代码与文档。2026-10-26 导入时，用户联系上游维护者确认许可，并在得到明确许可前暂停对外发布。本文件不推定上游的开源许可，也不构成权利转让。

[#441](https://github.com/TeFuirnever/azhou-ai-hub/pull/441)（2026-11-11）按 [衍生面清点](../../evidence/agent-skin-derivative-surface-audit-2026-11-08.md) 独立重写了仍与迁入快照重合的代码段。自此本包代码按仓库根 [MIT 许可证](../../LICENSE) 发布。上游仓库及 Git 历史中已删除的 `packages/codex-startup-animation/` 字节仍未获许可，MIT 不覆盖它们，本包也不再分发它们。

2026-11-13 复核：上游只有 3 个提交，`c743c2b5` 为最新；其中 23 个代码文件共 951 行有效内容（去空白后不少于 25 个字符）中，只有 31 行在当前包内出现，均为通用 API 或样板写法，例如 `import UniformTypeIdentifiers`、`let app = NSApplication.shared`、`codesign --force --sign - "$bundle"`、`<link rel="stylesheet" href="style.css">`。Pet、壁纸、安装器、校验器及其测试从未出现在上游任何提交中，它们来自本地维护工作树。包内也没有上游文件头或版权行；`vendor/dream-image-metadata.mjs` 是另一个 MIT 依赖，许可证保留在旁。

MIT 只覆盖代码。阿舟图像是维护者自有 IP，自 2026-11-13 起放在 `assets/azhou/`，采用 [CC BY-NC-ND 4.0](assets/azhou/LICENSE)（见 [NOTICE](assets/azhou/NOTICE.md)）；阿舟名称、标识与角色见 [TRADEMARKS.md](../../TRADEMARKS.md)。本地覆盖层 `assets/private/` 不随源码发布。

2026-10-26 的源码导入排除了私有阿舟图像、生成素材和本地机器验收产物。同日的本地交接将构建所需私有输入放在 Hub 包内被 Git 忽略的 `assets/private/`；它们仍不属于跟踪源码或公开分发内容。参见 [迁移清单](MIGRATION-INVENTORY.md)和 [本地交接记录](../../evidence/optional-integrations-local-handoff-2026-10-26.md)。

## Hub 运行评估

Hub adapter 按已核验的 App 版本选择日志评估方式：0.7.1 继续走旧事件评估；0.8.0 及更高版本要求被消费事件符合 `azhou-startup.event.v1`。已知诊断事件可以没有 schema，但不会被当作启动成功证据。合成事件测试验证适配器判定，不证明原生启动器实际产生日志、不构成上游许可，也不扩大素材使用权。

## Safe CSS reference validator

The read-only theme ZIP preflight vendors the following MIT files from `Codex-Dream-Skin` commit `6fc42df48a6a5365011f55cc349e20c038e56d1d`. Copyright (c) 2026 Codex Dream Skin Studio contributors. The complete notice is retained as `vendor/dream-safe-css.LICENSE`.

| Upstream file | Local file | SHA-256 |
|---|---|---|
| `runtime/safe-css-validator.mjs` | `vendor/dream-safe-css-validator.mjs` | `98a626655a4167ba0bbbff5eab96e78de7a5a74371e4a4ff6d8ac15211e5b24e` |
| `runtime/safe-css-policy.json` | `vendor/dream-safe-css-policy.json` | `c784dd3a16d71395fca0b2695047395dc6f951f44df962284976faeb0b3ea551` |
| `LICENSE` | `vendor/dream-safe-css.LICENSE` | `18f8478d0f9efd45307e5f17790194593b116658145c758ced3166398eb05b21` |

All three files are byte-identical copies. The JSON is a contract snapshot, not runtime configuration. `tools/reference-safe-css.mjs` is the local anti-corruption boundary. It uses only `validateSafeCss`, never the compiler or reference-host selector mappings. `tools/reference-safe-css.mjs` remains a developer inspection boundary. The source-bound AST/classic adapter below now adds its pristine validator and retained notice to build/runtime inputs; the upstream compiler is never invoked by host application.

To update, inspect a new immutable upstream revision and its license first. Copy the three complete source files without rewriting them, update this table and the focused suite's hash locks, compare the policy export deeply, and run the same corpus against the vendored and original validator. Preserve RED/GREEN evidence and perform independent review on the exact frozen diff. Any future Hub mapping is a separate reviewed implementation, not an upstream compiler call.


## Official theme JSON contract

The isolated Dream source library derives `vendor/dream-theme-validator.mjs` from the same MIT `Codex-Dream-Skin` commit `6fc42df48a6a5365011f55cc349e20c038e56d1d`. The source is `runtime/theme-package-validator.mjs`, SHA-256 `8f249d726367c383d8c5894890e2b6d1c3b56a7282d7441a80cfb6470955b5f8`. Copyright (c) 2026 Codex Dream Skin Studio contributors. The complete unchanged root notice is `vendor/dream-theme-validator.LICENSE`, SHA-256 `18f8478d0f9efd45307e5f17790194593b116658145c758ced3166398eb05b21`.

The local extraction retains the exact source spans listed by `tools/extract-dream-theme-validator.py`. Only the official-theme constants and pure helpers are selected. Local additions are the attribution header and `export { validateOfficialTheme };`. There is no filesystem staging, version/platform comparison, signature handling, CSS compiler or reference-host selector mapping. The derived module SHA-256 is `63363d5830cd76c57483ce7bdad28b66bce5dfae596134a6c46350c3169ad3ff`.

Rebuild from a separately inspected checkout at that exact commit with `python3 -B tools/extract-dream-theme-validator.py --source /path/to/reference/runtime/theme-package-validator.mjs --license /path/to/reference/LICENSE --output /path/to/rebuilt.mjs`, then compare the complete output with the vendored derivative. The generator refuses either source or notice hash drift. Review any source update as a new contract and rerun the official-theme corpus, extraction check, ZIP and source-library suites. Do not replace it with the reference package entry point, whose filesystem and CSS-compiler authority is outside this boundary.

## Safe CSS AST derivative

`vendor/dream-safe-css-ast.mjs` derives from the exact pristine Safe CSS source above, under the adjacent `dream-safe-css.LICENSE`. The only patch is the UTF-8 suffix `\nexport { parseSafeCss as parseSafeCssAst };\n`. It exposes the existing bounded parser without changing validation or invoking the compiler.

- Source SHA-256: `98a626655a4167ba0bbbff5eab96e78de7a5a74371e4a4ff6d8ac15211e5b24e`
- Patch SHA-256: `3b649164964b5bfadad94468c1f08f3e384502006ad4ff0ca2d1ee9928cd3fad`
- Output SHA-256: `ed0657f061e7f500233b8723683b3e28b236721b8f6fe13af24f8ac796d8cc37`

Rebuild with `python3 -B tools/derive-dream-safe-css-ast.py`; `--check` verifies exact output and the retained MIT notice without writing. `dream-theme-style.mjs` consumes AST records and never compiles upstream selectors. The local, intentionally partial profile rejects unmapped source rules and manifest fields. Run `python3 -B tools/test-production-dream-style.py` to compare the pristine and derived validators on the same corpus and test the mapping boundary. These source-stage tests do not prove host application or full Dream engine compatibility.

The Safe CSS parser, official manifest validator and literal mapping above are offline development references. Current Codex and DSH startup payloads and browser preview do not ship or invoke them. Their pinned sources, attribution and notices remain in this repository.

The generated `dream-theme-style.js` retains its classic startup/preview entry name and is built by `tools/build-startup.py --update-dream-theme-style` only from `azhou-theme-snapshot.mjs`. It validates bundled Azhou v1/v2 snapshots and rejects retired imported selections. The independent image metadata reader and notice remain shipped: ordinary Appearance image selection uses them to check PNG, JPEG and WebP dimensions before decode.
