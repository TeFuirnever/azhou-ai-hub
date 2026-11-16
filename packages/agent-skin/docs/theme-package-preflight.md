# P08 read-only theme ZIP preflight subset

This developer tool does not implement the P08 theme library. P07 currently supplies only the bundled theme and workspace readability foundation. No import, installation, application, preview, settings change or last-known-good write is performed.

## Interface and ownership

Run `python3 -B packages/agent-skin/tools/theme-package-preflight.py /path/to/theme.zip`.
The tool prints one JSON object. Exit 2 means blocked, not safe to import. The report always has `structure`, `resources`, `reference_css` and `hub_mapping` layers. Each layer has `status` and stable `reasons`. `passed` applies only to that named layer. The aggregate remains `blocked` until all four can be verified. Input bytes are bound by SHA-256. Input errors do not echo private paths or archive content.

The Python interface is `preflight(path) -> dict`. The ZIP is read once with a finite ceiling into memory and never extracted. There is no output directory or host adapter parameter. This keeps the developer inspection path separate from production settings and saved-theme ownership.

Two shapes were considered. A general validator with injected decoder, CSS policy and host adapters would expose future capabilities that have no evidence yet. A narrow report-only function leaves those layers explicitly blocked. This subset chooses the latter and adds no dependencies.

## Accepted subset

Only flat, single-root ordinary ZIPs containing exactly `theme.json`, `theme.css` and one PNG/JPEG/WebP named by `theme.json.image` are inspected. Only the minimal theme object with exactly `schemaVersion`, `id`, `name` and `image` is supported. Schema version is 1. Studio manifests, signatures, optional theme fields, directories, wrapper roots, transport metadata, encryption, ZIP64, extra fields and unsupported ZIP methods are blocked rather than guessed. These are subset limitations, not claims that the reference rejects all such formats.

Structure checks enforce canonical ASCII file names, no duplicate or case-colliding paths, no traversal or links, no unknown entries, coherent local records, finite entry and byte budgets, bounded decompression, CRC and exact lengths. Files must be nonempty. Theme JSON rejects duplicate keys, non-finite values and unsupported fields. CSS is checked only for nonempty UTF-8 bytes here, not Safe CSS acceptance. Background extension and media magic must agree. Magic alone is not decoding.

## Reference and limits

The inspected reference is `Codex-Dream-Skin` commit `6fc42df48a6a5365011f55cc349e20c038e56d1d`. Its root LICENSE is MIT, copyright 2026 Codex Dream Skin Studio contributors. This tool is independently written from the contract, not a vendored implementation. Any future source reuse must retain its notice and immutable provenance.

Reference `macos/scripts/extract-theme-zip-macos.sh` declares 32 MiB archive bytes, 64 MiB expanded bytes and 32 entries. `runtime/theme-package-validator.mjs` declares 1 MiB simple theme JSON, 256 KiB CSS and 10 MiB images. `runtime/image-metadata.mjs` declares 16384 pixels per side and 50000000 total pixels. No numeric compression-ratio limit was found in that extractor. This tool uses bounded actual expansion and per-file ceilings, not an invented ratio threshold.

## Deliberately blocked layers

Image dimensions, pixel budget and actual decode remain unverified. Even a matching magic signature leaves `resources` blocked. Reference CSS policy requires the exact shared Safe CSS parser and whitelist; arbitrary CSS or a selector match cannot establish acceptance. Hub mapping remains blocked because only `workspaceReadability` is currently admitted, not Dream Skin public parts. Dream Skin `minClientVersion` cannot be compared to the Hub version. A `manifest.sig` or reference `signatureIgnored` result is not publisher trust. No signature, provenance or license authorization for a user's theme is inferred.

Tests use synthetic archive bytes in temporary directories. They do not launch a real host or establish full importer security, actual rendering or reference-format parity.

## Remaining resource limitation

The ZIP central directory is parsed by `zipfile` before the entry-count limit is checked. The 32 MiB archive limit bounds input bytes, not peak parser memory. This subset does not establish a complete import resource-safety verdict.
