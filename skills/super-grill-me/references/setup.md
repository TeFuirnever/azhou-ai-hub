# Dependencies and setup

Read this before first use, or whenever you need to confirm what this package requires and what it must never do on a machine.

## Runtime dependency

| Requirement | Source | Purpose |
|---|---|---|
| None | the host harness's own skill loader | Load `SKILL.md` and its `references/` |
| The sibling `super-grilling` package | installed beside this one in the same skill root | The interview protocol this package hands off to |

This package is **instruction-only**: it carries no scripts, no assets, no templates, and no runtime dependency of its own. Verification equals loading: if `skills/super-grill-me/SKILL.md` and its `references/` files are readable, the package is complete.

## Dependency boundary

- This package does not contain the interview; `super-grilling` does. Installed without `super-grilling`, it fails closed: it says `super-grilling` is required and stops, and it never simulates the interview.
- Check that the sibling is present before first use: `skills/super-grilling/SKILL.md` must be readable in the same skill root.
- Nothing is installed, downloaded, written, or configured by this package. It makes no external request and keeps no state.

## Related packages

Exploring requirements before a design exists belongs to `super-brainstorming`. Stress-testing a plan or design that already exists belongs to `super-grilling`, which this package hands off to.
