# Repository impact matrix

Use this reference when a changed code fact's consumers are unclear. Select relevant rows only.

| Changed code fact | Material consumers |
|---|---|
| API, route, command, or public interface | implementation/config, contract tests, integration guide, examples, downstream clients |
| Environment variable or deployment parameter | config template, runtime validation, runbook, setup guide, dependent service docs |
| Data model, schema, or file format | schema/implementation, readers and writers, migration notes, examples, validation tests |
| Project rule or safety boundary | nearest agent instruction, contributor guide, deterministic verifier when justified |
| Product or workflow status | maintained status surface, handoff, release manifest, next-action owner |
| Naming or terminology | implementation identifiers, indexes, active guidance; preserve historical quotations |
| Source, rights, or verification state | evidence ledger, asset manifest, release gate; provenance and permission remain separate |
| Operational procedure | executable automation, runbook, escalation path, handoff, validation steps |
| Completed or cancelled work | current task/status and dependencies; history only in the designated history surface |

## Required propagation detail

Use both columns: forward propagation finds consumers to update; reverse propagation removes stale duplication from active surfaces.

| Change type | Project rules | User/operator docs | Machine surfaces | Cross-project checks |
|---|---|---|---|---|
| API, route, CLI, SDK | only durable boundary/command/index changes | integration examples, errors, architecture routes, handoff | schema/OpenAPI, contract tests, generated reference inputs | every client, gateway, example app, compatibility statement |
| Environment variable, secret name, feature flag | required name/default/red-line behavior | setup, runbook, deployment, troubleshooting | `.env.example`, config parser, deployment manifest, validation | every deployer and downstream configuration guide |
| Database table, column, migration | access boundary and migration command | architecture data model, migration/runbook, handoff | schema, migration, fixtures, serializers | readers, writers, analytics, export/import contracts |
| User or agent workflow | durable sequence and prohibited shortcuts | README usage, integration guide, architecture state flow, runbook | workflow config, scripts, acceptance tests | upstream trigger and downstream result consumers |
| Deployment/infrastructure | destructive/privileged boundaries and canonical commands | operator runbook, rollback, observability, handoff | IaC, service manifests, health checks, config examples | shared domains, queues, storage, auth, service dependencies |
| Naming/terminology | canonical identifier and migration boundary | glossary, README, API reference, current status | code/config/schema names, redirects, aliases | old-name search in every affected consumer; preserve historical quotes |
| Security/authorization/privacy | non-negotiable rule and checkpoint | threat/operation guidance where reader-relevant | policy, validator, audit event, negative test | trust boundaries, data owners, credential consumers |
| Source/rights/verification | release boundary and evidence requirement | attribution/usage statement where appropriate | evidence ledger, asset manifest, release gate | source owner, derivative consumer, publication package |

For a material feature, explicitly classify four document roles even when filenames differ:

1. integration/setup — how an external reader uses it;
2. architecture — how it works and what it depends on;
3. runbook — how to operate, verify, and recover it;
4. handoff/changelog/current status — what exists now.

An absent role is not an automatic creation request. Record `verified`/not applicable, create it when runnable-stage evidence and reader need justify it, or `hold` with reason.

## Spec conflict

| Observation | Current-state action | Reminder action |
|---|---|---|
| spec names behavior absent from code | keep active docs aligned to code | record unimplemented target and ask whether to start implementation |
| code changed but spec still describes old behavior | update current-state sections to code | preserve historical decision rationale where it still matters |
| code and runtime disagree | investigate build, deploy, flags, or environment | `hold` until the executed artifact is identified |
| two docs disagree | resolve both against code | preserve unresolved intent as one explicit reminder |

## Reverse reconciliation

Look for material that should leave an active surface:

- superseded facts competing with code;
- completed tasks presented as next actions;
- duplicated rules copied from a maintained source;
- paths or commands whose targets no longer exist;
- historical narrative occupying an instruction or current-status surface.

Merge or move only when destination and authorization are clear. Make deletion a proposal until the exact target is authorized.

## Repository audiences

| Surface | Primary reader | Keep here |
|---|---|---|
| agent memory, when supported | a future agent across sessions | durable preferences and non-obvious facts with evidence |
| `AGENTS.md`, `CLAUDE.md`, equivalents | agents changing this repository | rules, hard boundaries, commands, pointers, recurring traps |
| `README`, `docs/`, runbooks | users, operators, downstream teams | setup, behavior, contracts, architecture, operations |
| spec, ADR, plan | implementers and decision makers | target behavior, rationale, unresolved decisions |

One fact can have several readers without becoming several authorities. Code remains the current behavior source; each surface translates it for its reader.

An explicit `reconcile` or `handoff` request covers all three project audiences by default. This includes project-bound agent memory stored outside the repository. Only user-wide/global configuration, memory whose project binding is unclear, unrelated repositories, and whole-file or directory deletion require a separate checkpoint.
