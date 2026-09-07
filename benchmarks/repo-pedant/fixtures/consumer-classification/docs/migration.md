# Link migration (1.x to 2.0)

Permanent links changed shape in 2.0. Old bookmarks used the slug format
produced by `legacy_slugify` (for example `/accounts-42-statements`); the 2.0
router resolves them by unquoting and re-splitting on dashes. Keep quoting the
old format in support replies until the 1.x deprecation window closes.
