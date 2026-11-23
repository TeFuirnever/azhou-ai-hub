# Dependencies and setup

Read this before first use, or whenever you need to confirm what this package requires and what it must never do on a machine.

## Runtime dependency

| Requirement | Source | Purpose |
|---|---|---|
| None | the host harness's own skill loader | Load `SKILL.md` and its `references/` |
| A sub-agent facility | optional, from the host harness | Look up facts for the frontier from a fresh context window |

This package is **instruction-only**: it carries no scripts, no assets, no templates, and no runtime dependency. Verification equals loading: if `skills/super-grilling/SKILL.md` and its `references/` files are readable, the package is complete.

## Boundaries

- A harness without sub-agents is supported. The skill then looks the fact up itself and says that the fact was not checked from an independent context window.
- The skill asks and recommends; it does not act. Nothing is carried out until the user confirms a shared understanding, and the skill installs, downloads, writes, and configures nothing by itself.
- The skill keeps no state and makes no external request of its own.

## Related packages

`super-grill-me` is the reader's explicit entry into this protocol and requires this package. Exploring requirements before a design exists belongs to `super-brainstorming`.
