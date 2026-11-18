# Appearance information hierarchy

## Decision

Keep the existing workspace/startup/about navigation and transaction boundaries.
The default workspace view prioritizes previews, labeled controls and current
values. Put local preset management and technical file/opacity explanations in
native, initially closed `details` sections rather than deleting instructions.
Keep the disabled-control reason and conditional background-strength relationship
visible. Shorten theme action labels in both supported locales.

Import, Apply and Save are distinct: importing a Dream source stores it locally;
it neither applies the theme nor saves other drafts. This effect stays beside the
import button and in its accessible description. Existing success, unsaved-draft,
conflict and failure announcements stay unchanged. Expanding help performs no
storage or application work. The two sliders remain separate.

## Verification

- Added bilingual disclosure behavior tests red before implementation, then green.
- Existing settings/localization suite: 208 passed, 1 pre-existing skip.
- Isolated Chromium: real Enter key opens all three disclosures in both locales,
  focus stays on the summary, and closing help does not apply/save. Expanded and
  collapsed layouts fit 390/640/800 CSS-pixel widths. Existing image/preset import,
  export, draft, cancel, conflict and save regression checks remain covered.
- Generated DSH client: embedded iframe tested in both locales at 390/640 pixels,
  collapsed/expanded screenshots, plus import/apply/restore/reopen/navigation and
  reload-persistence regression. Synthetic carrier uses explicit UTF-8 headers.
- Full repository `python3 scripts/verify.py` gate passed during implementation.

These are isolated browser and generated-consumer checks, not native DSH or Codex
acceptance. No installation, remote push, or merge is part of this change. The
unresolved earlier native Dream Apply failure is not explained by this UI work.
