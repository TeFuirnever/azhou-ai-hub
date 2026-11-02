# Restored offline browser fixture

`harness.patch.b64` stores the exact patch without Git whitespace ambiguity and restores four test-tool files from the fixed project baseline
`8eec664611c2f679be6714bd888a07d764459c8a`. It does not change production sources.
The decoded patch SHA-256 is `9f98ade764e5f0f6d66a1808976a39dfe306748e834bc16ba2f12bd7ee9bc396`. The runner decodes and verifies it only inside a new private root.
The restored final files match the independently recorded historical SHA-256:

- `test-startup-browser.mjs`: `0ffb327cf7071965504512c668bead84725b91972c2d70360dd6775484ac7355`
- `fixture-browser-lifecycle.mjs`: `559ef05ea3f71ffaf3b64c65157476feeb9aa54c24c97b40c64777b00bafab77`

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
