# Spec Relay: 60-second demo

This demo shows the relay contract: one HTML file that carries the source spec, an embedded state block and its exact visible feedback ledger. The checked-in deterministic checks prove the contract wiring; they are not a claim that an arbitrary model run produced a correct packet.

## 1. Ask the agent

```text
Use spec-relay to package this spec and its review comments into one transferable HTML.
```

Point the agent at the real source spec and review goal. The packet keeps the source's own branding: the skill never injects Azhou identity, emoji or colors into the HTML.

## 2. Expect these outputs

The agent must return:

1. one portable HTML packet where every substantive item carries a stable `data-review-id`;
2. an embedded `spec-relay.html-state.v1` state block whose visible feedback ledger is its exact projection;
3. complete comments, selected-text annotations, targets, dispositions (`accepted`, `rejected`, `deferred`, `needs_clarification`), rationale and owner per item;
4. optimistic revision guards that reject stale copies and duplicate feedback IDs without overwriting;
5. a `spec-relay.receipt.v1` receipt.

## 3. Verify the development contract

From the repository root, run the deterministic suite:

```bash
python3 -m unittest tests.test_spec_relay -v
```

Real run at revision `9d491ea`, Python 3.14.7 (trimmed):

```text
test_comment_and_selection_round_trip_inside_html ... ok
test_deferred_feedback_is_carried_as_unresolved ... ok
test_duplicate_feedback_id_is_rejected_without_overwrite ... ok
test_feedback_can_be_resolved_without_losing_history ... ok
test_handoff_metadata_can_move_with_packet ... ok
test_init_embeds_portable_state_and_visible_ledger ... ok
test_stale_revision_is_rejected_without_overwrite ... ok
test_unresolved_target_without_selection_is_rejected ... ok
test_visible_ledger_tampering_is_rejected ... ok
----------------------------------------------------------------------
Ran 9 tests in 1.141s

OK
```

Then drive the CLI once end to end on a disposable fixture packet:

```bash
SKILL_DIR=/absolute/path/to/skills/spec-relay
PACKET="$(mktemp -d)/packet.html"
printf '%s' '<!doctype html><html><body><main data-review-id="REQ-001">Requirement</main></body></html>' > "$PACKET"
python3 "$SKILL_DIR/scripts/relay_state.py" init "$PACKET" \
  --source-spec docs/spec.md --source-revision abc123 \
  --review-goal "approve scope" --review-status in_review
python3 "$SKILL_DIR/scripts/relay_state.py" show "$PACKET"
python3 "$SKILL_DIR/scripts/relay_state.py" add-feedback "$PACKET" \
  --feedback-id FB-001 --expected-revision 0 --target REQ-001 \
  --comment "Explain why this requirement exists" --selection "Requirement" \
  --disposition accepted --rationale "clarifies scope" --owner product
python3 "$SKILL_DIR/scripts/relay_state.py" validate "$PACKET"
```

Real output (trimmed):

```text
initialized spec-relay.html-state.v1: /tmp/spec-relay-demo.ZVJXc3/packet.html
persisted FB-001: /tmp/spec-relay-demo.ZVJXc3/packet.html
valid spec-relay.html-state.v1: packet=f7d5308a-c06d-4188-a06c-65bc51782ed2 revision=1 feedback=1 unresolved=0
```

The stale-copy guard fails closed on a replayed revision:

```bash
python3 "$SKILL_DIR/scripts/relay_state.py" add-feedback "$PACKET" \
  --feedback-id FB-002 --expected-revision 0 --target REQ-001 \
  --comment "replayed write" --disposition deferred --rationale x
```

```text
spec-relay: stale state revision: expected 0, current 1
(exit 1, packet unchanged)
```

Passing proves embedded-state, round-trip, optimistic-concurrency, target-resolution, tamper-detection and responsive-ledger wiring. It does not prove that a real reviewer session returned meaningful feedback, that the browser session connected, that `export` or `share` succeeded (both hold separate authorization and share transfers the embedded comments), or that an openable HTML equals a completed review. A packet with no reviewer feedback must still be recorded as `review_feedback: none_received`, not as human approval.

## 4. Evidence receipts

Recorded per the [skill standard evidence stage](../skill-standard.md) for the run quoted above:

| Stage field | Value |
|---|---|
| runtime | Python 3.14.7, macOS (Darwin 25.6.0), repository `9d491ea` |
| harness / model | deterministic `unittest` + stdlib CLI; no model in the loop |
| skill package digest | `SKILL.md` `08fd0d195d32ad6f`, `relay_state.py` `0bf07a5b314885ee` (sha256, 16-hex prefix) |
| input / case digest | fixture `packet.html` `c818268160674886`; `tests/test_spec_relay.py` `0c4ed73067a661a6` |
| tool permissions | local filesystem and Python only; no network access |
| attempt | one deterministic attempt; byte-reproducible commands above |
| artifact digest | final packet `f7d5308a…` (packet id), `state_revision` 1 |
| automated checks | 9/9 tests OK in 1.141s; CLI `validate` pass; stale-revision rejection exit 1 |
| named human review | not performed for this demo run; recorded as an explicit hold |
