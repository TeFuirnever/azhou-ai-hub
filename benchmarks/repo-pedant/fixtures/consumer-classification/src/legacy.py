"""Pre-2.0 URL slug helper. Kept while the migration docs still quote the old link format."""


def legacy_slugify(text: str) -> str:
    """Render a legacy-style slug: lowercase, non-alphanumerics collapsed to dashes."""
    pieces = []
    for char in text.lower().strip():
        if char.isalnum():
            pieces.append(char)
        else:
            pieces.append("-")
    return "".join(pieces).strip("-")
