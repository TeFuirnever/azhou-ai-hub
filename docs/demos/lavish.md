# Lavish: 60-second demo

This demo shows the review-loop contract: one local HTML artifact, one locked CLI baseline and one stable receipt. The relay-mode half shows the Spec Relay packet contract: one HTML file that carries the source spec, an embedded state block and its exact visible feedback ledger. The checked-in deterministic checks prove the contract wiring; they are not a claim that an arbitrary model run produced a correct artifact or packet, or that a human completed a review.

## 1. Ask the agent

```text
Use lavish to turn this comparison into a rich HTML artifact I can review.
```

Point the agent at real material. The skill builds the artifact locally, opens the browser review surface and stays in the loop until the user's feedback lands.

## 2. Expect these outputs

The agent must return:

1. one local HTML artifact, by default under `.lavish/`, written in a chosen design source and matching Lavish playbooks;
2. a review session opened with the locked baseline `npx -y lavish-axi@0.1.47 <html-file>`;
3. a foreground long-poll (or a verified harness wake callback) so user annotations and queued prompts reach the agent;
4. user feedback applied to the artifact before polling again;
5. session end (`end` / `Send & End`) honored: no uninvited reopening;
6. a `lavish.receipt.v1` receipt with `complete` / `complete_with_holds` / `hold` / `failed` kept distinct — a local artifact or open session never proves publication.

## 3. Verify the development contract

From the repository root, run the deterministic suite:

```bash
python3 -m unittest tests.test_skill_package.SkillPackageTest.test_lavish_package_keeps_the_locked_upstream_baseline tests.test_check_repository.RepositoryPolicyTest.test_all_canonical_skills_follow_the_shared_brand_contract -v
```

Real run at revision `78c0b78`, Python 3.14.7 (trimmed):

```text
test_lavish_package_keeps_the_locked_upstream_baseline ... ok
test_all_canonical_skills_follow_the_shared_brand_contract ... ok
----------------------------------------------------------------------
Ran 2 tests in 0.001s

OK
```

Then inspect the locked npm baseline before first execution:

```bash
node --version
npm view lavish-axi@0.1.47 version dist.integrity license --json
```

Real output:

```text
v24.15.0
{
  "version": "0.1.47",
  "dist.integrity": "sha512-zB1kEUSgyvi6sC3I/nBPCGZwO8Z5pt8I2/ltFcovC8R+PuzRwJUb5V4BWMWnaPdXVBPH07B7XoBKKBf28733kg==",
  "license": "MIT"
}
```

The registry integrity matches the `sha512-…` value recorded in [provenance](../../skills/lavish/references/provenance.md) byte-for-byte. Passing proves the locked-baseline, provenance, brand-layer and receipt wiring. It does not prove that a real browser session connected, that a user returned meaningful feedback, that `export` produced a portable file, or that a share succeeded. A share is a third-party publication action on `ht-ml.app`; without an explicit authorization and its own receipt, the demo records `publication: not_requested`.

## 4. Evidence receipts

Recorded per the [skill standard evidence stage](../skill-standard.md) for the runs quoted above:

| Stage field | Value |
|---|---|
| runtime | Python 3.14.7, Node.js v24.15.0, macOS (Darwin 25.6.0), repository `78c0b78` |
| harness / model | deterministic `unittest` + npm registry metadata; no model in the loop |
| skill package digest | `SKILL.md` `6986aa9966580669`, `setup.md` `c75fa6b3d07602e4`, `provenance.md` `b257a120fdb8b2b8`, `upstream-compatibility.md` `33ad40c0f1556c22`, `brand-layer.md` `b82f00f84150bf9d` (sha256, 16-hex prefix) |
| input / case digest | `tests/test_skill_package.py` `088f160b9c65328d`; `scripts/check_repository.py` `1a3fb011f750443b` |
| tool permissions | local filesystem, Python and npm registry read only; no artifact opened, no share performed |
| attempt | one deterministic attempt; byte-reproducible commands above |
| artifact digest | package files above; no runtime artifact produced (no model run claimed) |
| automated checks | 2/2 tests OK in 0.001s; registry integrity equals the provenance `sha512-…` record |
| named human review | not performed for this demo run; recorded as an explicit hold |

## 5. Relay mode: package a spec in one HTML

Ask the agent:

```text
Use lavish in relay mode to package this spec and its review comments into one transferable HTML.
```

Point the agent at the real source spec and review goal. The packet keeps the source's own branding: the skill never injects Azhou identity, emoji or colors into the HTML.

The agent must return: a source-linked HTML with addressable `data-review-id` sections, the embedded `spec-relay.html-state.v1` block and its exact visible feedback ledger, dispositioned feedback, unresolved owners, explicit transport/publication status, and a `spec-relay.receipt.v1` receipt. A packet with no reviewer feedback must be recorded as `review_feedback: none_received`, not as human approval.

### Verify the relay contract

From the repository root, run the deterministic suite:

```bash
python3 -m unittest tests.test_lavish_relay_state -v
```

Real run at revision `9d491ea`, Python 3.14.7 (trimmed; recorded when the parser lived at `skills/spec-relay/` — it moved byte-identical to `skills/lavish/scripts/relay_state.py` in the merge):

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
SKILL_DIR=/absolute/path/to/skills/lavish
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

Real output (trimmed, revision `9d491ea`):

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

Passing proves embedded-state, round-trip, optimistic-concurrency, target-resolution, tamper-detection and responsive-ledger wiring. It does not prove that a real reviewer session returned meaningful feedback, that the browser session connected, that `export` or `share` succeeded (both hold separate authorization and share transfers the embedded comments), or that an openable HTML equals a completed review.

### Relay evidence receipts

Recorded for the relay runs quoted above at their pinned revision `9d491ea`:

| Stage field | Value |
|---|---|
| runtime | Python 3.14.7, macOS (Darwin 25.6.0), repository `9d491ea` |
| harness / model | deterministic `unittest` + stdlib CLI; no model in the loop |
| skill package digest | `SKILL.md` `08fd0d195d32ad6f`, `relay_state.py` `0bf07a5b314885ee` (sha256, 16-hex prefix) |
| input / case digest | fixture `packet.html` `c818268160674886`; `tests/test_spec_relay.py` `0c4ed73067a661a6` (now `tests/test_lavish_relay_state.py`) |
| tool permissions | local filesystem and Python only; no network access |
| attempt | one deterministic attempt; byte-reproducible commands above |
| artifact digest | final packet `f7d5308a…` (packet id), `state_revision` 1 |
| automated checks | 9/9 tests OK in 1.141s; CLI `validate` pass; stale-revision rejection exit 1 |
| named human review | not performed for this demo run; recorded as an explicit hold |
