# Dream main literal-paint profile

## Scope and implementation stages

The target product is original source library → capsule → independent Dream settings directory → explicit, reversible application. Source-stage code currently provides the capsule export and strict parser/mapping boundary. Settings, tagged Native/JavaScript snapshots, owned-main capability and transactional application remain unimplemented at this stage. No installed host support or visual compatibility is claimed.

`codex-main-literal-paint/v1` accepts only a manifest with `schemaVersion`, `id`, `name` and `image`. Identity fields name a directory item; they never replace Azhou application, bot or startup identity. Every optional official-theme field blocks this profile rather than disappearing silently. The source library can still retain packages with those fields.

The profile maps every pristine SafeCSS AST rule and declaration in source order. Only `main`, no state, and `background-color` are supported. Values must be validated hex, rgb, rgba or case-insensitive transparent literals. Variables, currentColor, other parts/states and all other declarations block the whole package. Output contains bounded numeric RGBA steps, not author selectors or compiled CSS. Each color step derives `background-image:none` for main itself, following the upstream compiler. It must not clear the body scene or any pseudo-element.

The intended owned-main implementation must replace the previous legacy wash/P07 mask, preserve the original source image on the body, and prove transparent/rgba/opaque composition with actual computed styles and pixels. This promises the mapped declaration semantics, not full Dream base-engine visual parity.

## Source capsule

The CLI command is:

```sh
python3 -B tools/theme-library.py --library /physical/path/to/library export-capsule ARCHIVE_SHA256 > theme.dream.json
```

The command performs the same stored-archive hash and full source revalidation as `read`, then writes deterministic JSON to stdout. It does not write settings, LKG or host state. The exact envelope is `{schema:"azhou-agent-skin.dream-capsule.v1",archiveSha256,files}`. Files are exactly original `theme.json`, `theme.css`, and the registered `background.png`, `background.jpg` or `background.webp`; each record has exact `bytes`, `sha256`, `base64` keys. Export does not map the CSS or grant application permission. No `safe`, mapped token, active pointer, file path, raw archive copy or publisher-trust field is present.

The UI boundary accepts at most 20 MiB of capsule bytes, strictly decodes UTF-8, rejects duplicate keys including escaped aliases, and bounds JSON depth/value counts. It checks exact envelope and file shapes, canonical base64, actual byte counts and SHA-256. Per-source limits remain 1 MiB JSON, 256 KiB CSS and 10 MiB image. It reapplies official JSON validation, the total profile mapping, static image/container and dimension limits, then requires a real decoder to agree on dimensions. Cancellation before or after asynchronous decoding discards the result. The archive digest is retained as provenance only: the UI did not re-unzip those ZIP bytes and does not treat the digest as a signature or a ZIP validation receipt.

## Planned durable and live contracts

The independent Dream directory will share the existing settings store, not the Azhou preset format or a second settings service. Imports store source only and do not activate. Persistent legacy image/startup preferences stay intact. A tagged active selection will project one verified original scene into a self-contained runtime snapshot. JavaScript and Native must enforce the same exact tagged shape and byte budgets; unknown schemas are read-only, never rewritten as defaults.

The existing settings owner must capture baselines, prepare/activate/probe while retaining the previous renderer owner, CAS the settings record, then finalize. Before-commit failure rolls back without a durable change. Post-commit loss requires conditional compensation against the exact operation identity, never a write over a newer selection. Exact main/document/workspace/owner epochs authorize each live phase. This is a planned contract until its tests and consumers are implemented.

## Evidence boundaries

Fixtures use a self-authored tiny PNG and constructed official-contract JSON/CSS. No authorized complete external theme ZIP was available. Parser/capsule tests establish source and boundary behavior, not third-party media permission, real Codex acceptance, full compatibility or whole-package 95% unit coverage.
