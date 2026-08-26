# Exact statistics

Statistics are evidence, not style.

## Source priority

1. Use exact counters exposed by the active host for the current conversation.
2. If the user explicitly supplies or authorizes a compatible session log, use a documented parser for that host and state its scope.
3. Otherwise return `unavailable: host exposes no audited current-session counters.`

Never infer savings from writing style, word count, model intuition, or an undocumented log shape. Never scan home directories to locate private logs. Never claim lifetime totals from one session.

Separate measured fields from derived fields:

- measured: input tokens, output tokens, cache creation/read tokens, model, request count;
- derived: cost or savings computed from a named formula and versioned pricing table.

If pricing or attribution is missing, omit cost and savings. Exact token counts do not prove the counterfactual tokens a different writing style would have used.

Host-specific auto-interception, status-line updates, and persistent mode hooks are optional adapters. They are not part of this neutral package and must never be installed automatically.
