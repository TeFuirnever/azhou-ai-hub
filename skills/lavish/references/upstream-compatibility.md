# Upstream compatibility

This map records the imported `lavish` baseline at commit `232972beba9e0e4e75682c98f2aeb2cf01532122`. Preserve every non-conflicting capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| Explicit `/lavish` request and conversation inference | preserved | `SKILL.md` Request section |
| Default `.lavish/<name>.html` artifact path | preserved | Workflow step 1 |
| Open or resume browser review | preserved | Workflow step 2; CLI pinned to `0.1.47` |
| Repair `self_paint_warning` before polling | preserved | Workflow step 2 |
| Foreground long-poll and verified callback rule | preserved | Workflow step 3 |
| Passive layout inbox; repair only queued warnings | preserved | Workflow steps 3–4 |
| Apply feedback and reply in the same session | preserved | Workflow step 5 |
| End and `Send & End` semantics | preserved | Workflow steps 6–7 |
| Never reopen browser-ended sessions uninvited | preserved and strengthened | Explicit authorization boundary |
| Visual hierarchy and overflow guidance | preserved | Visual guidance |
| Real UI screenshots over prose | preserved | Visual guidance |
| Diagram/table/comparison/plan/code/input/slides playbooks | preserved | Playbooks |
| Mermaid-to-editable-Excalidraw review | preserved | Commands and rules |
| Portable standalone export | preserved | Commands and rules |
| `ht-ml.app` sharing | preserved with safety checkpoint | Explicit publication authorization required |
| User/project/fallback design-source priority | preserved | Commands and rules |
| No required global install | preserved | Setup documents locked `npx` path |
| Local/global installed-copy fallback | preserved | Entry and setup |
| Hermes categorization metadata | intentionally omitted | Neutral runtime packages expose only `name` and `description`; no behavior removed |

A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence.
