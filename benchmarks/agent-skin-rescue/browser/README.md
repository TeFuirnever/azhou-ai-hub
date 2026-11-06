# Restored offline browser fixture

`harness.patch.b64` stores the exact patch without Git whitespace ambiguity and applies onto the restored historical build-31 source. It does not change production sources.
The decoded patch SHA-256 is `9f98ade764e5f0f6d66a1808976a39dfe306748e834bc16ba2f12bd7ee9bc396`. The runner decodes and verifies it only inside a new private root.
The offline source is the exact historical build 31 tree `3060b7e3587b37a0486c54423f76bb3d792c7b6d`: the `packages/agent-skin` archive of the public anchor commit `b689702097be8bd3e2a4b6f2a10afb348cf5cb37` (subtree `93de39312c4a7aadaa2800ff2d60d52de3e4aac7`) plus the tracked restoration patch (decoded SHA-256 `5b5382b8b4dcfd4dfe1894ff4140fec1ac6c5dbc7146d320de92e429e5a045fb`), verified by Git tree id on every run; the unpublished historical commit object is not required.
The restored final files match the independently recorded historical SHA-256:

- `test-startup-browser.mjs`: `0ffb327cf7071965504512c668bead84725b91972c2d70360dd6775484ac7355`
- `fixture-browser-lifecycle.mjs`: `559ef05ea3f71ffaf3b64c65157476feeb9aa54c24c97b40c64777b00bafab77`

The `packages/codex-startup-animation/wallpaper` subtree (`92cfa938ad3f342c9d3111e4a6114cd3f37c7a8b`) is identical at the public anchor and the historical baseline; each run re-verifies the anchor subtree id and the restored file digests (`wallpaper.css` `e2974673a1c92d2d1f4c8b36cfc695d5806bb975e4c7c27f70b430fc4dbfc16a`, `renderer.js` `38226c5f4d31ba773def9eca1f69e44048c5e7d9a6206fd9bdc1dae43149a933`).

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
