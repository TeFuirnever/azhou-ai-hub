# Upstream compatibility

This map records the imported `eli5` baseline at commit `794af9e63d07fad17087dcab61f21f44cb48effd`. Preserve every non-conflicting capability during updates.

| Upstream capability | Local status | Evidence / difference |
|---|---|---|
| `eli5` package name and skill identity | preserved | frontmatter `name: eli5` and package folder |
| `/eli5 <topic>` typed trigger and dead-simple explainer request | preserved | `SKILL.md` description and workflow step 1 |
| Zero-background audience framing | preserved verbatim | `SKILL.md` capability baseline sentence |
| One HTML artifact with big pictures and few words | preserved | `SKILL.md` artifact contract |
| `$ARGUMENTS` slash-command argument slot | adapted | harness-neutral topic argument in workflow step 1; no behavior removed |
| Topic boundary, artifact read-back, brand protocol, receipt, provenance | Azhou addition | no upstream counterpart; additive contract layers |

A future removal or replacement needs a documented safety conflict or implementation disadvantage plus regression evidence.
