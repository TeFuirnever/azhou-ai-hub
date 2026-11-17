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
