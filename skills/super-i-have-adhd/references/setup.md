# Dependencies and setup

Read this before first use, or whenever you need to confirm what this package requires and what it must never do on a machine.

## Zero external runtime dependency

| Requirement | Source | Purpose |
|---|---|---|
| None | the host harness's own skill loader | Load `SKILL.md` and its `references/`; the contract applies through ordinary responses |

This package is **instruction-only**: it carries no scripts, no assets, no templates, and no external runtime dependency — no language runtime, no CLI, no network access, and no model call is required or performed by the package itself. Verification equals loading: if `skills/super-i-have-adhd/SKILL.md` and its `references/` files are readable, the package is fully operational. There is no install step, nothing to download, and nothing to configure.

## Boundaries

- The contract shapes output in the host harness's own response channel. It never installs, downloads, reconfigures, or writes anything by itself; file writes belong to the underlying task, not to this contract.
- No runtime state namespace is required: the contract keeps no `.azhou/` store. Receipts live in the response channel; artifacts belong to the underlying task.
- Shaped output uses paths relative to the current working directory (or repository-relative) when it references a packet, file, or artifact; machine-local absolute paths are never part of the output (Azhou delta rule 5).
- The frozen contract governs presentation only. When the underlying task needs tools, runtimes, or another skill, that skill keeps its own setup contract; the capability carve in the entry description routes the request, and this package adds no dependency of its own.

## Related packages

Zero-background explanations belong to `super-eli5`, architecture documents to `super-arch-doc`, and raster images to `super-imagegen`; each of those packages documents its own runtime dependencies. Once this contract is engaged, its shaping applies to how their outputs are delivered without taking over their workflows.
