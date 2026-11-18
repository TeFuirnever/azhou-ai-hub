# Dream main literal-paint profile

## Scope and implementation stages

The target product is original source library → capsule → independent Dream settings directory → explicit, reversible application. The current source candidate implements this loop for the first literal-paint profile, including independent directory import, explicit Apply, fresh startup and Restore saved Azhou appearance. The settings store owns the atomic selection; PageController owns the live renderer. No installation, real Codex acceptance or general Dream compatibility is claimed. P08 overall mapping remains blocked outside this narrow profile.

`codex-main-literal-paint/v1` accepts only a manifest with `schemaVersion`, `id`, `name` and `image`. Identity fields name a directory item; they never replace Azhou application, bot or startup identity. Every optional official-theme field blocks this profile rather than disappearing silently. The source library can still retain packages with those fields.

The profile maps every pristine SafeCSS AST rule and declaration in source order. Only `main`, no state, and `background-color` are supported. Values must be validated hex, rgb, rgba or case-insensitive transparent literals. Variables, currentColor, other parts/states and all other declarations block the whole package. Output contains bounded numeric RGBA steps, not author selectors or compiled CSS. Each color step derives `background-image:none` for main itself, following the upstream compiler. It must not clear the body scene or any pseudo-element.

The owned-main implementation replaces the previous legacy wash/P07 mask with a transparent wash, preserves the original source image on the body, and covers transparent/rgba/opaque composition with actual computed styles and screenshot pixels. This promises the mapped declaration semantics, not full Dream base-engine visual parity.

## Source capsule

The CLI command is:

```sh
python3 -B tools/theme-library.py --library /physical/path/to/library export-capsule ARCHIVE_SHA256 > theme.dream.json
```

The command performs the same stored-archive hash and full source revalidation as `read`, then writes deterministic JSON to stdout. It does not write settings, LKG or host state. The exact envelope is `{schema:"azhou-agent-skin.dream-capsule.v1",archiveSha256,files}`. Files are exactly original `theme.json`, `theme.css`, and the registered `background.png`, `background.jpg` or `background.webp`; each record has exact `bytes`, `sha256`, `base64` keys. Export does not map the CSS or grant application permission. No `safe`, mapped token, active pointer, file path, raw archive copy or publisher-trust field is present.

The UI boundary accepts at most 20 MiB of capsule bytes, strictly decodes UTF-8, rejects duplicate keys including escaped aliases, and bounds JSON depth/value counts. It checks exact envelope and file shapes, canonical base64, actual byte counts and SHA-256. Per-source limits remain 1 MiB JSON, 256 KiB CSS and 10 MiB image. It reapplies official JSON validation, the total profile mapping, static image/container and dimension limits, then requires a real decoder to agree on dimensions. Cancellation before or after asynchronous decoding discards the result. The archive digest is retained as provenance only: the UI did not re-unzip those ZIP bytes and does not treat the digest as a signature or a ZIP validation receipt.

## Durable source and tagged snapshot contracts

The independent `dreamThemes` directory uses the existing settings store and namespace. Import immediately stores the original capsule string once, not an Azhou preset or an active selection. It does not save other panel drafts or apply a wallpaper. The directory has eight-entry and 20 MiB serialized-record limits. Its exact shape is `{schemaVersion:1,revision,entries:[{capsuleSha256,capsule}]}`. Catalog names are verified manifest text, never HTML or Azhou identity overrides. Identical source is idempotent but still checks the current baseline. Directory writes CAS the raw images, theme, Azhou-preset and Dream records in one transaction, preserving changed or unknown records rather than repairing them. Cancel, dispose and timeout abort pending transactions; late get/put callbacks cannot publish a directory.

The known imported selection stored at `themeState` is an internal thin record, not the snapshot wire: exact `{schemaVersion:2,revision,imagesBinding,selection:{kind:"imported",capsuleSha256},preferencesByTheme:{"azhou-q-v3":preference},commitId}`. The existing bundled v1 storage remains readable. The UI does not write an imported active pointer in this stage. Normal Save currently refuses an imported active selection until the reversible application stage supplies its startup-only-save semantics. Unknown versioned image/theme records are read-only and cannot be rewritten from fallback defaults. Unknown inactive directories remain preserved during unrelated known appearance saves.

Each host snapshot reads the selected source again, verifies every active file, reruns the pristine AST and total mapper, and projects the original image into `settings.artwork` exactly once. It never trusts stored paint. Broken inactive entries are not decoded by active snapshot loading. Missing or changed active source blocks the snapshot without clearing its selection. Stored legacy artwork, avatar and text preferences stay intact. The transient startup contour analysis reuses the existing cover/edge pipeline without encoding a replacement PNG. An image without usable internal edges gets a frame outline for the Azhou startup transition; its original image bytes remain unchanged. This is not Dream animation parity.

The self-contained wire has exact theme keys `{schemaVersion:2,revision,imagesBinding,selection}`. Bundled selection is `{kind:"bundled",id:"azhou-q-v3",surfaceTransparency}`. Imported selection is `{kind:"imported",profile:"codex-main-literal-paint/v1",capsuleSha256,archiveSha256,image:{name,mime,bytes,sha256,width,height},paint:{rgba:[r,g,b,a],backgroundImage:"none",sourceDeclarationCount}}`. RGB channels are finite 0–255, alpha finite 0–1, and source count 1–128. Source mapping accounts for every declaration in order before converging to the final paint; source counts do not authorize otherwise unsupported input. No CSS, selectors, capsule, ZIP or second image is transported. `imagesBinding` remains an opaque storage/snapshot consistency value, not authorization; Native does not reserialize JSON to recompute it.

An imported runtime `settings` record uses schema 2 and the original PNG/JPEG/WebP artwork. Stored legacy images and bundled runtime settings stay schema 1 with their existing PNG limits. Avatar stays PNG at its old 2 MiB URL cap. Imported raw image bytes remain capped at 10,485,760; their canonical data URL is at most 13,981,039 ASCII bytes. The complete serialized wire remains capped at 24 MiB plus 4 KiB. Transport still uses 64 KiB page-to-Native and 192 KiB Native-to-player chunks, and the existing expression limits. Native uses typed bundled/imported cases, strict keys, numeric bounds and actual MIME/length/hash checks. JavaScript additionally checks container dimensions and decoding. Native and the player consume only the bounded finite plan, not author-CSS authorization. Host application must always revalidate/remap the catalog source. Unknown schema/kind/profile fails closed; a cancelled or stale asynchronous hash result cannot be delivered as a new snapshot.

The existing settings owner captures all four raw record baselines and a bounded digest token for the visible panel. A token that cannot represent an invalid/unserializable record blocks explicit application; it does not relax ordinary Save's structured-graph CAS or rewrite the invalid record. The host reconstructs the source plan, activates/probes a candidate while retaining the incumbent sheet, URL and workspace lease, commits images/theme with four-record CAS, then finalizes the renderer. A second explicit request cancels and awaits the first transaction's settlement before activation. The thin imported record additionally retains `previousThemeId` and the bundled preferences. Existing legacy image bytes remain untouched; a missing image record is initialized only from the captured defaults, never unsaved panel text or avatar.

Before-commit quota, conflict, cancellation or timeout aborts IDB before reporting failure and rolls the candidate back. The renderer retains and restores the existing mask without asynchronous regeneration when its geometry is still current. A lost main/document/foreign owner cannot be revived as an apparently successful old skin. Post-commit loss conditionally compensates only the exact images/theme commit; independent catalog writes survive and newer active selections cannot be overwritten. A compensating selection advances revision, except restoring genuinely absent initial records removes only this transaction's exact initial records. Operation identity and structural baseline equality prevent late compensation from acting on a newer writer. Disposal immediately rejects new public operations, but retains the already-open transaction connection until deferred commit/compensation settlement and then closes it. Compensation failure is reported ahead of cancellation rather than claimed restored.

Imported mode hides the obsolete legacy preview and disables legacy artwork/theme/default controls. Ordinary Save can change startup text/avatar and source-independent catalog drafts without calling the legacy appearance apply callback. Explicit Apply and Restore do not save unrelated drafts. Restore retains the saved legacy artwork, strength, active bundled/null choice and transparency preference. Restoring saved strength zero uses the incumbent owner’s reversible deactivation receipt: its imported paint, sheet and URL stay unchanged through CAS; only successful finalize disposes the owner and publishes an explicit disabled state. Quota, conflict or cancellation leaves imported visuals and active records unchanged. A zero-strength restore never installs another image or uses a transparent mask as a substitute for disabling wallpaper. Every subsequent host startup/retry remaps catalog CSS again. A child/Native numeric paint is never an authorization to skip the source boundary. Unknown active storage schema remains read-only and cannot silently fall back to a writable legacy record.

## Evidence boundaries

Fixtures use self-authored PNG/JPEG/WebP pixels and constructed official-contract JSON/CSS. The real CLI→settings producer→Swift receiver/sender→animation bridge covers bundled and all three source formats. A valid large private ancillary PNG chunk exercises an original data URL above the old 12 MiB cap while preserving the same 2×3 pixels; legacy still rejects that URL. No authorized complete external theme ZIP was available. Parser/capsule tests establish source and boundary behavior, not third-party media permission, real Codex acceptance, full compatibility or whole-package 95% unit coverage.

## Executable UI check

The generated parent/child scenario is selected with `node tools/test-startup-browser.mjs --generated-payload INSTALL_JS --out NEW_DIRECTORY --only 'generated Dream source UI applies literal main paint and restores the saved Azhou appearance'`. Build `INSTALL_JS` with the current startup builder. The scenario uses its own Chrome profile and self-authored uniform PNG/strict source packages. It calls the real CLI, imports through the actual file input, checks IDB and startup drafts, activates three source colors, checks body/main computed images and screenshot alpha composition, reloads the generated payload, and restores the saved Azhou appearance. Quota is fault-injected at a real IDB write after activation; another IDB connection writes a competing directory record; cancellation occurs after activation. These are real renderer/IDB rollback checks, not disk-exhaustion or real-host evidence.

## DSH explicit main-paint capability

DSH uses `dsh-owned-main-paint/v2`, not the Codex workspace or mask contract.
The source profile name remains the versioned source mapper identity; it does not
license arbitrary selectors on DSH. The adapter identifies exactly one connected `data-slot="main"` inside the
captured root. A normal boxed slot paints itself. For the observed DSH
`display:contents` slot, v2 nominates only its exclusive direct parent with a
`_mainPanel` CSS-module class token, a real layout box, and no additional element
children. The semantic slot and paint plane remain separately bound; unknown
ancestors or expanded scopes fail closed. Both the semantic slot and paint plane
reject hidden/aria-hidden/inert ancestry and computed hidden/collapsed visibility,
including at initial admission. Added-and-removed element siblings invalidate
the exclusive plane lease even when the final topology looks unchanged.
No host display/layout property is
rewritten to manufacture a box. A lease binds document/html, boot,
route, root and main; pending mutation records are drained before checking it.
Removal/reinsertion permanently invalidates the lease. Decode, transactional
activation, zero-strength Restore and rollback must not revive a stale main or
clobber a newer owner. The bounded owned stylesheet wins over DSH's existing
main transparency rule without changing host inline styles.

This capability supports imported literal main paint and Restore of the existing
DSH legacy/null-theme baseline, including strength zero. It does not add P07
Codex reading-mask geometry. An unsupported non-null mask baseline is rejected,
not silently discarded. Main replacement fails closed; full automatic navigation
recovery is not claimed. Reload revalidates the stored capsule before applying.
Generic Apply failures ask the user to reconfirm the appearance rather than
claiming that rollback or database compensation necessarily succeeded.

Run the synthetic DSH adapter/renderer transaction check in
`test-startup-browser.mjs` and the generated client/iframe check with
`AZHOU_TEST_PYTHON=PYTHON node tools/test-dsh-dream-browser.mjs --out NEW_DIRECTORY`
after `tools/build-dsh-plugin.py`. The latter invokes the real embedded `mountSettings` path inside a synthetic
host dialog with the observed boxless slot shape. It uses a mocked module loader/Cordis
carrier, not the actual React component, and an isolated owned Chrome profile. These are
regression checks, not installed-host payload identity or native IME evidence.
