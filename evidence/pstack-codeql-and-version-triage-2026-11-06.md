# pstack statechart CodeQL triage and Hub version separation — 2026-11-06

**PR #372 original source-review head:** 58b676af10896403d038d7a5a123c6e17cf98ec5.

This is an independent read-only source assessment and reproducible
test-oracle evaluation. It is not formal human security approval and
does not dismiss any outstanding GitHub code-scanning alert.

## 18 PR review threads, three unique patterns

| Source pattern | Threads | Verified behavior | Proposed security disposition |
| --- | ---: | --- | --- |
| statechart/scripts/test/labels.ts:369 | 4 generated copies | fromSvg extracts Pele SVG text for equality comparisons and diagnostic messages | No observed production HTML sink; never use as HTML sanitization |
| statechart/scripts/test/cli.test.ts:896,910 | 8 generated copies | Bounded literals and JSON.stringify are written into temporary JS view fixtures intentionally executed by the test CLI | Test-only fixture generation in inspected path |
| statechart/scripts/test/differential.test.ts:253 | 4 generated copies | fast-check generates bounded synthetic models; JSON.stringify serializes data into test-only JS views | Test-only property harness in inspected path |
| Pinned upstream test/cli.test.ts:896,910 | 2 outdated PR locations | Same original test-source pattern as generated copies | Record with underlying pattern, not separately fixed production code |

**Total 18.** The original two test/cli.test.ts threads are outdated
in the PR; the generated copies remain active. The 3 implicated source
files are byte-for-byte identical across all four generated host trees.
Production statechart TypeScript files outside the test directory have
no static imports of these test helpers. The added distribution
test guards these exact source-byte and import separation properties.

## Unsafe as HTML sanitization; test-only call graph

The fromSvg helper removes markup using /<[^>]*>/g before entity
decoding. This is NOT a safe HTML sanitizer. Running the same helper
on the literal encoded text

    &#60;script&#62;alert(1)&#60;/script&#62;

returns this markup-looking string after decoding:

    <script>alert(1)</script>

If this string were inserted into an active HTML DOM, it would be
unsafe. In the inspected source, fromSvg output flows only to
readPele's comparisons or JSON-quoted failure diagnostics, which
are asserted by the test harness; no production HTML/DOM sink receives
that output. A separate template.innerHTML call in
statechart/scripts/test/render.test.ts:46–49 parses Mermaid label
markup in a detached JSDOM test template and is NOT fed fromSvg output.

This analysis does not cover the safety of arbitrary untrusted SVG,
renderer internals or downstream consumers of diagnostics. The
renderer comparison helper is a test-quality concern if reused.

## Dynamic test code, and separate CLI trust boundary

cli.test.ts serializes committed literal test cases into temporary
.mjs view modules. differential.test.ts uses bounded fast-check
generators with JSON.stringify for interpolated values. Both
intentionally exercise the CLI's --view execution path from test
directories. The production CLI can execute an arbitrary explicitly
supplied JS view module; this separate trust boundary is not proven
safe by these test findings and must be sandboxed appropriately.

## Review and disposition status

A separate native Codex read-only source review completed with
process exit 0 and turn.completed on 2026-11-06, classifying all
three patterns as test-only alerts within its examined call graphs.
The call chains and sink boundaries were independently checked.
One hypothetical nested-tag demonstration from the review did not
reproduce and is not used here; the entity-decoding demonstration
above is the verified counterexample.

The repository security maintainer should disposition one instance
of each unique source pattern and the duplicate generated copies.
Do not blanket-disable CodeQL, hand-edit pinned upstream or auto-close
all 18 threads. Until a reviewer signs off, the PR remains pending
security review despite green CodeQL CI.

## Versioned distribution, pinned upstream retained

The pinned upstream pstack remains version 0.15.36 at commit
c742dd61706fbacc1b95f1a20b7b988cf096ce6c, byte-immutable.
The revised Hub plugin changed runtime and adapter bytes while
still using the installed 0.15.36 cache identity. To prevent a
different native distribution reusing the same version, downstream-only
quilt patch 0021-hub-distribution-version-0.15.37.patch sets generated
Claude/Codex/ZCode manifests to 0.15.37. Hub metadata and Claude
marketplace version are also 0.15.37. A distribution test enforces
this, while verifying that pristine source still says 0.15.36.

**0.15.37 is only a new candidate, not installed or published.**
Default user plugin homes have not been modified. A versioned native
upgrade, real Hook trust, two-agent review completion, ZCode GUI
invocation and long-running restart acceptance remain separate gates.
