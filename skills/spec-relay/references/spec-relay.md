# Spec Relay

Read this file for any PRD, RFC, design spec, technical spec, implementation plan, or team-transfer request. The relay packet is complete only when another teammate or agent can open one HTML file, identify the source revision, inspect every material requirement, recover comments and annotations, and continue unresolved work without reconstructing prior context.

## Source contract

Capture these fields before generating HTML:

| Field | Required value |
|---|---|
| `source_spec` | local path, URL supplied by the user, or `conversation:<scope>` |
| `source_revision` | Git SHA, content hash, document version, or `unknown` |
| `review_goal` | decision or feedback expected from reviewers |
| `review_status` | `draft`, `in_review`, `approved`, or `held` |
| `handoff_to` | named team, role, person, agent, or `unassigned` |

An unknown revision is a visible hold on traceability, not permission to invent one.

## Addressable HTML

The review artifact contains:

1. Source metadata, review goal, status, and reviewer instructions.
2. Scope and non-goals.
3. Requirements and acceptance criteria.
4. Decisions, dependencies, risks, and open questions.
5. Feedback ledger and next-owner relay state.

Give each material item a stable `data-review-id` and visible label:

| Prefix | Meaning |
|---|---|
| `SCOPE-###` | scope or non-goal |
| `REQ-###` | requirement |
| `AC-###` | acceptance criterion |
| `DEC-###` | decision |
| `DEP-###` | dependency |
| `RISK-###` | risk |
| `OPEN-###` | unresolved question |

Preserve an ID across revisions while its meaning remains the same. Allocate a new ID when meaning changes materially. This keeps element comments and selected-text annotations traceable across team relays.

## Brand-neutral packet

Spec Relay mechanics do not add Azhou identity, emoji, character assets or colors to HTML. Preserve branding already present in the source spec or subject project; otherwise follow the Lavish design-source fallback. The embedded state, visible ledger, IDs and commands remain neutral across every design source. Azhou stage anchors belong to the agent conversation and receipt only.

## Embedded review state

The HTML carries one canonical machine-readable block:

```html
<script type="application/json" id="spec-relay-state">
{
  "schema": "spec-relay.html-state.v1",
  "packet_id": "<uuid>",
  "state_revision": 0,
  "updated_at": "<ISO-8601 UTC timestamp>",
  "source": {
    "spec": "docs/example-spec.md",
    "revision": "<revision>",
    "review_goal": "<goal>",
    "review_status": "in_review"
  },
  "feedback": [],
  "unresolved": [],
  "handoff_to": "unassigned"
}
</script>
```

This JSON block is the feedback source of truth. The visible feedback ledger is rendered or regenerated from it. Persist every feedback item before declaring the file ready to relay; feedback that remains only in Lavish session storage does not travel with the HTML.

Encode the block as valid JSON and escape `<`, `>`, and `&` in user-supplied strings as `\u003c`, `\u003e`, and `\u0026`. This prevents comment text such as `</script>` from terminating the state block. Preserve unknown fields when revising a packet from a newer schema producer.

`packet_id` identifies the relay packet across filenames. `state_revision` starts at `0` and increments on every accepted state mutation. Mutation commands require the caller's current revision, so an older copy cannot silently overwrite newer feedback. Use one writer per packet revision; after a stale-revision rejection, inspect the current packet and reconcile before retrying.

## State commands

Resolve `<skill-dir>` to the installed `skills/spec-relay/` directory.

Initialize a generated HTML packet:

```bash
python3 <skill-dir>/scripts/relay_state.py init .lavish/spec.html \
  --source-spec docs/spec.md \
  --source-revision <revision> \
  --review-goal "approve scope" \
  --review-status in_review \
  --handoff-to product
```

Persist one comment returned by polling:

```bash
python3 <skill-dir>/scripts/relay_state.py add-feedback .lavish/spec.html \
  --feedback-id FB-001 \
  --expected-revision 0 \
  --target REQ-001 \
  --comment "<complete comment text>" \
  --selection "<selected text or none>" \
  --disposition needs_clarification \
  --rationale "<reason>" \
  --owner platform
```

Resolve a comment after its owner responds:

```bash
python3 <skill-dir>/scripts/relay_state.py update-feedback .lavish/spec.html \
  --feedback-id FB-001 \
  --expected-revision 1 \
  --disposition accepted \
  --rationale "latency benchmark passed" \
  --source-change "docs/spec.md#latency" \
  --owner platform
```

Move the packet to its next reviewer or source revision:

```bash
python3 <skill-dir>/scripts/relay_state.py update-metadata .lavish/spec.html \
  --expected-revision 2 \
  --source-revision <revision> \
  --review-status approved \
  --handoff-to engineering
```

Regenerate a stale or altered visible ledger from canonical embedded state:

```bash
python3 <skill-dir>/scripts/relay_state.py refresh-ledger .lavish/spec.html \
  --expected-revision 3
```

Inspect or validate the state before relay:

```bash
python3 <skill-dir>/scripts/relay_state.py show .lavish/spec.html
python3 <skill-dir>/scripts/relay_state.py validate .lavish/spec.html
```

The standard-library tool preserves the HTML file mode, updates the embedded JSON through a unique temporary file, and atomically replaces the packet only after validation. A rejected or stale update leaves the HTML unchanged. `validate` requires the complete visible ledger—not only its IDs or counts—to be the exact escaped projection of the embedded feedback. `refresh-ledger` is the explicit repair and renderer-upgrade path: it validates canonical state, checks the expected revision, regenerates the view, and advances the packet revision.

## Feedback ledger

For every returned comment, annotation, or prompt, record:

| Field | Values |
|---|---|
| `feedback_id` | stable `FB-###` |
| `target` | `data-review-id` or selected quote |
| `comment` | complete reviewer comment or annotation text |
| `selection` | selected text, element label, or `none` |
| `disposition` | `accepted`, `rejected`, `deferred`, `needs_clarification` |
| `rationale` | one concrete reason |
| `source_change` | applied revision, proposed change, or `none` |
| `owner` | responsible role/person/agent or `unassigned` |
| `created_at` | supplied timestamp or generated UTC timestamp |
| `updated_at` | supplied timestamp or generated UTC timestamp |

Accepted feedback updates the review artifact. It updates the source spec only when the task authorizes that file change. The complete comment remains inside the HTML packet so the next reviewer can recover context. Treat that file as potentially sensitive review data; a selected, sanitized packet may be committed when requested.

## Relay gate

The packet is ready when:

- every material source item has an addressable section;
- every received feedback item has a disposition;
- the HTML contains `spec-relay.html-state.v1`, a packet ID, and a non-negative state revision;
- the complete visible feedback ledger is the exact escaped projection of embedded feedback;
- each embedded feedback target resolves to a `data-review-id` or retains its selected quote;
- accepted changes name the resulting artifact or source revision;
- deferred and unclear items name an owner or remain visibly `unassigned`;
- the receipt from [brand-layer.md](brand-layer.md) names the next owner and transport.
