"""Config migration steps.

Enabled steps are listed in ``config/migration-steps.txt`` and dispatched by
name at runtime; the file is edited per deployment, so the enabled set is not
fixed in code.
"""


def migrate_config(raw: dict) -> dict:
    """Reshape a v1 config mapping into the v2 shape."""
    out = dict(raw)
    out.setdefault("version", 2)
    out["migrated_by"] = "migrate_config"
    return out


def migrate_schema(raw: dict) -> dict:
    """Stamp the current schema revision onto a config mapping."""
    out = dict(raw)
    out["schema_revision"] = 7
    return out


def run_enabled_steps(raw: dict, steps_file) -> dict:
    """Apply every enabled step in file order to the given mapping."""
    result = raw
    for name in steps_file.read_text(encoding="utf-8").split():
        handler = globals()[f"migrate_{name}"]
        result = handler(result)
    return result
