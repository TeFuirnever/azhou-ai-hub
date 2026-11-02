# Restored offline browser fixture

`harness.patch.b64` stores the exact patch without Git whitespace ambiguity and restores four test-tool files onto the public anchor source `b689702097be8bd3e2a4b6f2a10afb348cf5cb37` (obtainable in a fresh clone). It does not change production sources.
The decoded patch SHA-256 is `9f98ade764e5f0f6d66a1808976a39dfe306748e834bc16ba2f12bd7ee9bc396`. The runner decodes and verifies it only inside a new private root.
The historical baseline commit `8eec664611c2f679be6714bd888a07d764459c8a` (build 31) was never published to this repository, so restored bytes are pinned to what the public anchor plus the tracked patch deterministically produces:

- `fixture-browser-lifecycle.mjs`: `559ef05ea3f71ffaf3b64c65157476feeb9aa54c24c97b40c64777b00bafab77` (still its independently recorded historical digest)
- `test-startup-browser.mjs`: `aeab9fd4f364733430884944d0244c2600f35acbdc7236161ee6f3317c8bde16` (reproducible composite; the historical build-31-derived bytes `0ffb327cf7071965504512c668bead84725b91972c2d70360dd6775484ac7355` are not reproducible from the public anchor)

The `packages/codex-startup-animation/wallpaper` resources are restored from the same anchor; their copies were recorded as identical to the historical baseline files, and each run re-verifies the pinned digests (`wallpaper.css` `e2974673a1c92d2d1f4c8b36cfc695d5806bb975e4c7c27f70b430fc4dbfc16a`, `renderer.js` `38226c5f4d31ba773def9eca1f69e44048c5e7d9a6206fd9bdc1dae43149a933`).

The patch includes immediate observation and cancellation of navigation errors,
owned-child binary capture with short-write handling, accumulated cleanup errors,
profile retention when ownership is uncertain, and the Mac headless mock-keychain
flag. All UI assertions, the 10-second navigation budget, and the 900-second full
browser budget remain unchanged.

`run_browser.py` requires a new private root, an already verified resource root,
and this rescue package's command-evidence modules. It copies the exact newly
built default payload and manifest, checks every production input, applies the
test-only patch, runs all 13 formal Node files, compiles the fake-host Swift helper
and emits its expressions, then runs the full 70 checks once. It does not run the
native main suite or launch/attach to official Codex or ZCode.

```text
python3 -B browser/run_browser.py --root NEW_PRIVATE_ROOT \
  --resource-root VERIFIED_RESOURCE_ROOT --tools RESCUE_MODULE_DIRECTORY
```

Each current run has its own immutable command receipts and raw binary streams.
Historical passing counts are reference information and never establish a new
candidate's result. Raw receipts, private images and payloads, profiles, inventory,
personal paths, and material provenance stay outside Git. A successful run does
not establish real host, signing, login, keychain, or system isolation behavior.
