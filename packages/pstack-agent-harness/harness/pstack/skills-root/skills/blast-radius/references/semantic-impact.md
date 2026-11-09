# Trace the behavior affected by a change

Read this before changing a public interface, a shared UI, persistent state, a generated artifact, or an installation path. An impact-only request produces findings, not edits or a new design.

1. Freeze the explicit base and head and inspect committed, staged, unstaged and untracked work separately. A path report is a discovery aid, not proof of a stable snapshot or complete impact. On drift, refresh the affected evidence.
2. Classify what changes: presentation, options/discovery, defaults, validation, committed effects, persistence, or recovery. Start with the actual entry and a small set of concrete callers. If an available code index has incomplete coverage, read source and search unindexed configuration, generated files, manifest entries and string-based loading.
3. For each distinct consumer, trace **input/display → default → validation → command → authoritative owner → persisted or derived result**. Record why the relationship changes behavior. Shared labels or components do not imply shared state. Follow re-exports through their public consumers; zero static references do not prove safe deletion.
4. Include source → generator → distributed package → installed entry, aliases, wire readers, configuration precedence, failure reports and cleanup. Tests support an edge but do not establish a product consumer. Mark dynamic callers you cannot resolve as unknown; do not turn a failed search or parse into an empty set.
5. Name one writer for mutable state, the public boundary between modules, and the event order for asynchronous work. Record ownership, admission, idempotency, stale-result handling and replay before implementing a state change. Preserve existing local architecture instead of importing another project's layer names.
6. Classify relationships as must inspect, conditional, invariant only, or evidence only. Expand when an owner or effect is unresolved. Do not report every reachable node as an affected feature.

Use the repository's current checker for allowed dependencies and package boundaries. Determine its configured coverage before citing a pass. If a legacy baseline exists, distinguish old from new violations, keep unrelated baseline entries, and require an owner, reason and expiry condition for an exception. Never refresh a baseline in CI to erase new failures. Do not create a baseline where no legacy problem exists.

Turn only behavior-changing dimensions into cases. Prefer meaningful pairs and risky combinations to a full Cartesian product. Each case has setup, action, observable assertions and an evidence location; mark it accepted, undefined, pruned with a reason, or a suspected implementation defect. Ask only for missing decisions that materially change behavior. Existing authorization and known contracts remain valid.

Return a compact record:

| Consumer / entry | Changed behavior | Owner / commit point | Dependency and evidence | Must preserve | Case / unresolved question |
| --- | --- | --- | --- | --- | --- |
| Actual entry | Concrete difference | Single writer | Source or runtime observation | Isolation, compatibility, failure | Setup, action, assertion |

A diagram or a caller list alone does not complete this record. Record unknowns and the cheapest observation that can settle them. Run the real entry for the critical safety claim when authorized; do not manufacture a test result for an impact-only investigation.

## Source and local changes

Adapted by Azhou AI Hub; read `ENGINEERING-SOURCES.md` at the installed distribution root for immutable sources, licenses, local substitutions and update steps. These are workflow instructions, not an automatic safety or approval gate.
