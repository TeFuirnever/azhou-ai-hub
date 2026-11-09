# Make information available when it is needed

Read this when changing tool names, descriptions, parameter schemas, skill triggers, contextual output or multi-step workflows. Start with purpose, available actions and critical constraints. Each deferred resource needs a useful description, a working retrieval path and a trigger that tells the agent when to read it.

Place permission boundaries, destructive effects and required validation before the action. Put defaults, ranges and parameter pairing rules on the parameter. State each fact once at its owner; do not repeat the entire schema in a system prompt or describe private implementation details as user choices.

Return a bounded useful result with identifiers or artifact paths for details. Include nearby context only when it helps the next decision. Mark omitted or truncated content and expose how to continue; a rendering limit is not a bound on upstream reads or total cost. Missing or inaccessible context remains unknown.

Compare the actual model-visible prompt and tool definitions before and after the change. Measure first-turn tokens when the host exposes them; otherwise name that measurement gap. Evaluate total searches, repeated reads, errors and completion as well as prompt size. Do not claim an improvement from fewer bytes alone or infer hidden host context from a source file.

Respect the active host's tools and delegation rules. A source example of subagents, browser control or durable resume does not establish those capabilities in this session. Use the available owner or report the missing capability without inventing a fallback scheduler or another task store.

## Source and local changes

Adapted by Azhou AI Hub; read `ENGINEERING-SOURCES.md` at the installed distribution root for immutable sources, licenses, local substitutions and update steps. These are workflow instructions, not an automatic safety or approval gate.
