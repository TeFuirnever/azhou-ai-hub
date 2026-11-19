# Local appearance presets

This P07 slice adds named, device-local appearance drafts. P07 is not complete. P08 package mapping and general theme rendering remain blocked.

`image-settings.js` owns the catalog in the existing IndexedDB settings store. The default key is `appearancePresets`; an injected images key derives `<settingsKey>:appearancePresets`. No database upgrade or separate settings service is added.

The catalog has schemaVersion 1, an integer revision, and entries. Each entry has a unique opaque local id, a trimmed plain-text name of 1 to 40 UTF-16 code units without control characters, recipeId `azhou-q-v3`, appearance containing artwork, contours and wallpaperStrength, and validated surfaceTransparency. It has no CSS, selector, startup text, startup avatar or active preset pointer. The images and themeState records remain the only active truth. Images schema and imagesBinding are unchanged.

The local subset allows at most eight entries and at most 20 MiB of UTF-8 JSON for the complete catalog. These are local limits, not the reference package contract. Every entry reuses image structure, contour, strength and real image decode validation. Unknown keys, unknown recipes, duplicate ids, invalid names, corrupt assets and excess limits fail closed.

Add preset and Load into draft do not persist or apply. Add requires the Azhou recipe. Loading replaces only appearance and theme selection. Startup fields stay unchanged. Save validates candidates before opening one readwrite transaction, compares the images, themeState and catalog baselines inside that transaction, and commits changed records atomically. An older images-only writer therefore invalidates the snapshot. Public save calls that omit the catalog preserve it and still check its baseline.

A missing catalog is an empty draft. An invalid catalog is retained unchanged and disabled, with visible feedback. Valid current appearance remains editable and saveable. Restore all defaults resets the current appearance, theme preference and startup draft, but retains the catalog draft. Cancel, close or dispose discard uncommitted directory changes. Embedded Cancel restores the last committed directory and appearance. Once Save commits, apply failure does not undo persistence and follows the existing retry contract.

Active runtime snapshots validate only the active images and theme state. They neither decode inactive preset images nor enable an unvalidated catalog. Normal settings loading and catalog writes still validate every preset image. A slow or corrupt inactive image therefore cannot delay an otherwise valid active snapshot.

Baseline comparisons preserve structured-clone types and graph identity, including BigInt and cyclic objects. Unchanged invalid catalogs remain read-only while current appearance can save. Concurrent type, value or graph changes prevent every write. Opaque structured-clone objects without a synchronous content comparison, such as Blob or File, conservatively conflict rather than risk overwriting a changed catalog.

The adjacent embedded cancellation boundary retains the transaction-normalized currentSettings rather than copying callback-only themeState metadata back into an images candidate.

Tests cover distinct A/B images, transparency 0 and 100, literal markup names, draft cancellation, catalog preservation, all three baseline conflicts, quota, abort, timeout, dispose, corruption, schema and size limits. No host adapter, renderer, Native protocol, installation or arbitrary theme ID is expanded. Deletion, ZIP import, CSS, synchronization and a general theme library are deferred.


## Single-preset file exchange

The settings panel imports and exports one Azhou JSON preset file. This is not Dream ZIP compatibility. P08 mapping and overall completion remain blocked.

The wire object has exactly `schema`, `name`, `recipeId`, `appearance` and `surfaceTransparency`. `schema` is `azhou-appearance-preset.v1`. The other fields use the catalog entry validation above. There is no external id, catalog revision, active pointer, startup text, avatar, CSS, host selector, link or file path. Artwork must be a normalized inline PNG that decodes at 1536 by 1024. Import checks the declared byte size before reading and the actual byte size afterward, with a 20 MiB limit. UTF-8 decoding is strict. The complete catalog still has its separate eight-entry and 20 MiB limits.

Import assigns a fresh opaque local id and adds only a catalog draft. It does not select or load the preset, change the current appearance, save, or apply. Cancel, close, dispose, timeout and late decode cannot commit it. Save retains the existing three-record baseline checks and atomic transaction. When only the catalog draft changed, Save writes only the catalog. It preserves the exact active images and theme records, including missing records and revisions, and skips `onApply`. The normal once-per-commit `onSaved` notification remains intact. A catalog-only save does not require a new theme revision, even at the maximum valid active revision. Public load and save return detached settings copies so caller edits cannot alter the internal comparison state. Saves that edit active settings retain the existing apply and retry contract.

Export includes only the selected catalog entry, including an unsaved entry. It does not implicitly save. It uses the fixed safe download name `azhou-preset.json` and releases the temporary anchor and object URL on both success and failure. File controls have visible associated labels and remain in the existing keyboard navigation.

Unit regressions cover the file boundary, draft-only round trip, active-record preservation, notifications, cancel and late file/decode completion, invalid schema and images, strict UTF-8, both file limits, catalog limits, three baseline conflicts, quota, abort, timeout and dispose. The isolated Chrome harness exercises the real file-input/Blob path, single-item export, imported literal markup names, IDB save and reopen, unchanged active records, cancellation, label/focus behavior and URL cleanup. These checks are not a real Codex host acceptance or a Dream ZIP test.
