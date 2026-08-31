# Lavish: 60-second demo

This demo shows the review-loop contract: one local HTML artifact, one locked CLI baseline and one stable receipt. The checked-in deterministic checks prove the contract wiring; they are not a claim that an arbitrary model run produced a correct artifact or that a human completed a review.

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
6. a `lavish.receipt.v1` receipt with `complete` / `hold` / `failed` kept distinct — a local artifact or open session never proves publication.

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
