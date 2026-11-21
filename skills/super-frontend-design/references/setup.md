# Setup and capabilities

Copy this complete package into a harness's skill directory. The package is instruction-only guidance: it carries no scripts, no external runtime dependency, and no network requirement of its own. Verification equals loading — if `SKILL.md` and its `references/` files are readable, the package is fully operational.

## Conditional capabilities

Two upstream capabilities are conditional and keep the upstream wording, "if your environment supports it":

| Capability | When the host has it | When it is missing |
|---|---|---|
| Screenshot self-review ("Critique your own work as you build, taking screenshots to review") | Capture real screenshots of the built UI and critique them against the plan. | Name the limitation, continue with the prose critique, and never report a screenshot critique that did not run. This is a degradation, not a fail-closed stop: the design work continues. |
| Design memory ("a space to quickly jot down notes about what you've tried") | Keep per-project notes under the host's authorized state root, following the hub runtime-state contract. | Continue in chat; say that persistence is unavailable instead of silently dropping the practice. |

Neither capability is a dependency. A missing capability is named in the receipt's `verification` line; a critique that never ran can never back `✅ 验证通过`.

## Boundaries

- The package writes nothing by itself; file writes belong to the underlying design or build task.
- No `.azhou/` state is required for an ordinary design run. If a host offers persistent design notes, store them only under an explicitly authorized `.azhou/super-frontend-design/` root, and never include private conversation in them.
- The design guidance is advisory input; the user's brief and repository rules outrank it.
