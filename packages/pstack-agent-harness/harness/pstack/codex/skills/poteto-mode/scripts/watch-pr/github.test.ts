import { describe, expect, it } from "bun:test";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  ChecksUnavailable,
  WatcherQueryError,
  buildReviewThreads,
  discoverStack,
  mapRollupNode,
  orderStack,
  parseCheckRollupPage,
  parseFastCheck,
  parsePullRequest,
  parseReviewThreadPage,
  resolveChecks,
  resolveContext,
  resolveReviewThreads,
  runCommand,
} from "./github.ts";
import {
  fakeReader,
  failedCheck,
  passingCheck,
  pendingCheck,
} from "./fakes.test-helper.ts";
import { parsePrNumber } from "./types.ts";

const context = {
  owner: "owner",
  repo: "repo",
  number: parsePrNumber(42),
};

describe("checks fallback chain", () => {
  it("uses a non-empty fast-path result without a rollup query", async () => {
    const reader = fakeReader({
      fastPath: { kind: "checks", checks: [passingCheck("fast")] },
    });
    const read = await resolveChecks(reader, context);
    if (read.kind !== "reported") throw new Error("expected resolved checks");
    expect(read.source).toBe("gh-pr-checks");
    expect(read.checks.map((check) => check.name)).toEqual(["fast"]);
    expect(reader.calls).toEqual(["checksFastPath"]);
  });

  it("paginates GraphQL when the fast path is unusable", async () => {
    const reader = fakeReader({
      fastPath: { kind: "unusable", exitCode: 8, stderr: "" },
      rollupPages: [
        { kind: "contexts", checks: [passingCheck("first")], endCursor: "next" },
        {
          kind: "contexts",
          checks: [failedCheck("second")],
          endCursor: null,
        },
      ],
    });
    const read = await resolveChecks(reader, context);
    if (read.kind !== "reported") throw new Error("expected resolved checks");
    expect(read.source).toBe("graphql-rollup");
    expect(read.checks.map((check) => check.name)).toEqual(["first", "second"]);
    expect(reader.calls).toEqual([
      "checksFastPath",
      "checkRollupPage:null",
      "checkRollupPage:next",
    ]);
  });

  it("falls back when valid fast-path JSON represented an empty list", async () => {
    const reader = fakeReader({
      fastPath: { kind: "checks", checks: [] },
      rollupPages: [
        {
          kind: "contexts",
          checks: [pendingCheck("fallback")],
          endCursor: null,
        },
      ],
    });
    const read = await resolveChecks(reader, context);
    if (read.kind !== "reported") throw new Error("expected resolved checks");
    expect(read.checks[0].name).toBe("fallback");
    expect(reader.calls).toEqual(["checksFastPath", "checkRollupPage:null"]);
  });

  it("fails closed when both paths are empty", async () => {
    const reader = fakeReader({
      fastPath: {
        kind: "unusable",
        exitCode: 8,
        stderr: "credential cannot read checks",
      },
    });
    await expect(resolveChecks(reader, context)).rejects.toBeInstanceOf(
      ChecksUnavailable
    );
    expect(reader.calls).toEqual(["checksFastPath", "checkRollupPage:null"]);
  });

  it("reports no checks only when the fast path and the rollup both say so", async () => {
    const reader = fakeReader({
      fastPath: { kind: "none-reported" },
      rollupPages: [{ kind: "no-rollup" }],
    });
    expect(await resolveChecks(reader, context)).toEqual({ kind: "no-checks" });

    const rollupExists = fakeReader({
      fastPath: { kind: "none-reported" },
      rollupPages: [{ kind: "contexts", checks: [], endCursor: null }],
    });
    await expect(resolveChecks(rollupExists, context)).rejects.toBeInstanceOf(
      ChecksUnavailable
    );
  });

  it("refuses a check rollup cursor that repeats instead of walking for ever", async () => {
    const reader = fakeReader({
      fastPath: { kind: "unusable", exitCode: 8, stderr: "unreadable" },
      rollupPages: [
        {
          kind: "contexts",
          checks: [passingCheck("first")],
          endCursor: "same",
        },
        {
          kind: "contexts",
          checks: [passingCheck("second")],
          endCursor: "same",
        },
      ],
    });
    await expect(resolveChecks(reader, context)).rejects.toBeInstanceOf(
      WatcherQueryError
    );
    expect(reader.calls).toEqual([
      "checksFastPath",
      "checkRollupPage:null",
      "checkRollupPage:same",
    ]);
  });
});

describe("rollup node mapping", () => {
  it("maps terminal and non-terminal CheckRun states fail closed", () => {
    const cases = [
      ["IN_PROGRESS", null, "pending", "PENDING"],
      ["COMPLETED", "SUCCESS", "passed", "SUCCESS"],
      ["COMPLETED", "NEUTRAL", "skipped", "NEUTRAL"],
      ["COMPLETED", "SKIPPED", "skipped", "SKIPPED"],
      ["COMPLETED", "ACTION_REQUIRED", "failed", "ACTION_REQUIRED"],
      ["COMPLETED", "TIMED_OUT", "failed", "FAILURE"],
      ["COMPLETED", "FUTURE_VALUE", "failed", "FAILURE"],
    ] as const;
    for (const [status, conclusion, kind, reportedState] of cases) {
      expect(
        mapRollupNode({
          __typename: "CheckRun",
          name: "ci",
          status,
          conclusion,
        })
      ).toMatchObject({ kind, reportedState });
    }
  });

  it("classifies an in-progress Code Review Gate from the rollup as the gate", () => {
    expect(
      mapRollupNode({
        __typename: "CheckRun",
        name: "Code Review Gate",
        status: "IN_PROGRESS",
        conclusion: null,
      })
    ).toMatchObject({ kind: "code-review-gate" });
    expect(
      mapRollupNode({
        __typename: "StatusContext",
        context: "Code Review Gate",
        state: "PENDING",
      })
    ).toMatchObject({ kind: "code-review-gate" });
  });

  it("classifies a Code Review Gate waiting on an owner approval as the gate", () => {
    expect(
      mapRollupNode({
        __typename: "CheckRun",
        name: "Code Review Gate",
        status: "COMPLETED",
        conclusion: "ACTION_REQUIRED",
        description: "1 of 2 policies",
      })
    ).toMatchObject({
      kind: "code-review-gate",
      reportedState: "ACTION_REQUIRED",
    });
  });

  it("classifies a fast-path Code Review Gate waiting on an owner approval as the gate", () => {
    expect(
      parseFastCheck({
        name: "Code Review Gate",
        state: "ACTION_REQUIRED",
        bucket: "fail",
      })
    ).toMatchObject({
      kind: "code-review-gate",
      reportedState: "ACTION_REQUIRED",
    });
    expect(
      parseFastCheck({ name: "ci", state: "ACTION_REQUIRED", bucket: "fail" })
    ).toMatchObject({ kind: "failed", reportedState: "ACTION_REQUIRED" });
  });

  it("maps StatusContext states and drops unknown typenames", () => {
    expect(
      mapRollupNode({
        __typename: "StatusContext",
        context: "ci",
        state: "EXPECTED",
      })
    ).toMatchObject({ kind: "pending", reportedState: "PENDING" });
    expect(
      mapRollupNode({
        __typename: "StatusContext",
        context: "ci",
        state: "FUTURE_VALUE",
      })
    ).toMatchObject({ kind: "failed", reportedState: "FUTURE_VALUE" });
    expect(mapRollupNode({ __typename: "FutureNode" })).toBeNull();
  });
});

describe("fast-path check bucket", () => {
  it("treats a finished state as a failure even when gh buckets it pending", () => {
    for (const state of ["STALE", "STARTUP_FAILURE", "CANCELLED"]) {
      expect(parseFastCheck({ name: "ci", state, bucket: "pending" })).toMatchObject(
        { kind: "failed", reportedState: state }
      );
    }
  });

  it("keeps a check that is genuinely in flight as pending", () => {
    for (const state of [
      "EXPECTED",
      "REQUESTED",
      "WAITING",
      "QUEUED",
      "PENDING",
      "IN_PROGRESS",
    ]) {
      expect(parseFastCheck({ name: "ci", state, bucket: "pending" })).toMatchObject(
        { kind: "pending" }
      );
    }
  });
});

describe("check rollup page parsing", () => {
  const response = (pageInfo: Record<string, unknown>) => ({
    data: {
      repository: {
        pullRequest: {
          commits: {
            nodes: [
              {
                commit: {
                  statusCheckRollup: {
                    contexts: {
                      pageInfo,
                      nodes: [
                        {
                          __typename: "CheckRun",
                          name: "ci",
                          status: "COMPLETED",
                          conclusion: "SUCCESS",
                        },
                      ],
                    },
                  },
                },
              },
            ],
          },
        },
      },
    },
  });

  it("keeps the cursor when the page reports more rows", () => {
    expect(
      parseCheckRollupPage(response({ hasNextPage: true, endCursor: "next" }))
    ).toMatchObject({ kind: "contexts", endCursor: "next" });
  });

  it("refuses a page that claims more rows without a cursor", () => {
    expect(() =>
      parseCheckRollupPage(response({ hasNextPage: true, endCursor: null }))
    ).toThrow(WatcherQueryError);
    expect(() =>
      parseCheckRollupPage(response({ hasNextPage: true, endCursor: "" }))
    ).toThrow(WatcherQueryError);
  });
});

describe("closed enum parsing", () => {
  const rawPullRequest = {
    mergeable: "MERGEABLE",
    mergeStateStatus: "CLEAN",
    reviewDecision: "APPROVED",
    headRefOid: "head",
    headRefName: "feature",
    baseRefName: "main",
    state: "OPEN",
    mergedAt: null,
    isDraft: false,
  };

  it("accepts mergeStateStatus CONFLICTING", () => {
    expect(
      parsePullRequest(
        { ...rawPullRequest, mergeStateStatus: "CONFLICTING" },
        context
      ).mergeStateStatus
    ).toBe("CONFLICTING");
  });

  it("reads gh's empty reviewDecision as no decision rather than a parse failure", () => {
    expect(
      parsePullRequest({ ...rawPullRequest, reviewDecision: "" }, context)
        .reviewDecision
    ).toBeNull();
  });

  it("reads an uncomputed mergeability as UNKNOWN rather than a query error", () => {
    for (const uncomputed of ["", null]) {
      const facts = parsePullRequest(
        { ...rawPullRequest, mergeable: uncomputed, mergeStateStatus: uncomputed },
        context
      );
      expect(facts.mergeable).toBe("UNKNOWN");
      expect(facts.mergeStateStatus).toBe("UNKNOWN");
    }
  });

  it("still rejects a mergeability value it does not know", () => {
    expect(() =>
      parsePullRequest({ ...rawPullRequest, mergeable: "MAYBE" }, context)
    ).toThrow(WatcherQueryError);
  });

  it("still rejects an unknown reviewDecision", () => {
    expect(() =>
      parsePullRequest({ ...rawPullRequest, reviewDecision: "MAYBE" }, context)
    ).toThrow(WatcherQueryError);
  });

  it("rejects unknown enum values as retryable errors carrying the raw value", () => {
    try {
      parsePullRequest(
        { ...rawPullRequest, mergeStateStatus: "FUTURE_STATE" },
        context
      );
      throw new Error("expected parser to throw");
    } catch (error) {
      expect(error).toBeInstanceOf(WatcherQueryError);
      if (!(error instanceof WatcherQueryError)) throw error;
      expect(error.failure).toMatchObject({
        kind: "missing-key",
        retryable: true,
        rawValue: '"FUTURE_STATE"',
      });
    }
  });
});

it("annotates Bugbot threads with distinct review-pass counts", () => {
  const response = {
    data: {
      repository: {
        pullRequest: {
          reviewThreads: {
            pageInfo: { hasNextPage: false, endCursor: null },
            nodes: [
              {
                id: "one",
                isResolved: false,
                comments: {
                  nodes: [
                    {
                      body: "RUN_ID: run-1",
                      createdAt: "now",
                      path: "a.ts",
                      line: 1,
                      author: { login: "bugbot" },
                    },
                  ],
                },
              },
              {
                id: "two",
                isResolved: false,
                comments: {
                  nodes: [
                    {
                      body: "CURSOR_AUTOMATION_ID: run-2 severity high",
                      createdAt: "now",
                      path: null,
                      line: null,
                      author: { login: "cursor" },
                    },
                  ],
                },
              },
              {
                id: "resolved",
                isResolved: true,
                comments: {
                  nodes: [
                    {
                      body: "RUN_ID: run-3",
                      createdAt: "now",
                      path: null,
                      line: null,
                      author: { login: "bugbot" },
                    },
                  ],
                },
              },
            ],
          },
        },
      },
    },
  };
  const threads = buildReviewThreads(parseReviewThreadPage(response).threads);
  expect(threads).toHaveLength(2);
  expect(threads.map((thread) => thread.isBugbot)).toEqual([true, true]);
  expect(threads.map((thread) => thread.bugbotReviewPasses)).toEqual([3, 3]);
});

describe("review thread pagination", () => {
  const thread = (id: string, resolved = false) => ({
    id,
    firstComment: {
      authorLogin: "someone",
      body: "please fix",
      path: "a.ts",
      line: 1,
      createdAt: "now",
    },
    resolved,
  });

  it("keeps walking pages until the cursor is exhausted", async () => {
    const reader = fakeReader({
      threadPages: [
        { threads: [thread("one")], endCursor: "next" },
        { threads: [thread("two")], endCursor: "last" },
        { threads: [thread("three")], endCursor: null },
      ],
    });
    const threads = await resolveReviewThreads(reader, context);
    expect(threads.map((item) => item.id)).toEqual(["one", "two", "three"]);
    expect(reader.calls).toEqual([
      "reviewThreadPage:null",
      "reviewThreadPage:next",
      "reviewThreadPage:last",
    ]);
  });

  it("sees an unresolved thread that sits past the first page", async () => {
    const reader = fakeReader({
      threadPages: [
        { threads: [thread("early", true)], endCursor: "next" },
        { threads: [thread("late")], endCursor: null },
      ],
    });
    const threads = await resolveReviewThreads(reader, context);
    expect(threads.map((item) => item.id)).toEqual(["late"]);
  });

  it("stops after a single page when the cursor is exhausted", async () => {
    const reader = fakeReader({
      threadPages: [{ threads: [thread("only")], endCursor: null }],
    });
    expect((await resolveReviewThreads(reader, context)).length).toBe(1);
    expect(reader.calls).toEqual(["reviewThreadPage:null"]);
  });

  it("counts Bugbot review passes across every page", async () => {
    const bugbot = (id: string, runId: string) => ({
      id,
      firstComment: {
        authorLogin: "bugbot",
        body: `RUN_ID: ${runId}`,
        path: "a.ts",
        line: 1,
        createdAt: "now",
      },
      resolved: false,
    });
    const reader = fakeReader({
      threadPages: [
        { threads: [bugbot("one", "run-1")], endCursor: "next" },
        { threads: [bugbot("two", "run-2")], endCursor: null },
      ],
    });
    const threads = await resolveReviewThreads(reader, context);
    expect(threads.map((item) => item.bugbotReviewPasses)).toEqual([2, 2]);
  });

  it("drops resolved threads from later pages too", async () => {
    const reader = fakeReader({
      threadPages: [
        { threads: [thread("one")], endCursor: "next" },
        { threads: [thread("two", true)], endCursor: null },
      ],
    });
    expect(
      (await resolveReviewThreads(reader, context)).map((item) => item.id)
    ).toEqual(["one"]);
  });

  it("refuses a cursor that repeats instead of walking for ever", async () => {
    const reader = fakeReader({
      threadPages: [
        { threads: [thread("one")], endCursor: "same" },
        { threads: [thread("two")], endCursor: "same" },
      ],
    });
    await expect(resolveReviewThreads(reader, context)).rejects.toBeInstanceOf(
      WatcherQueryError
    );
    expect(reader.calls).toEqual([
      "reviewThreadPage:null",
      "reviewThreadPage:same",
    ]);
  });

  it("refuses a page that claims more threads without a cursor", () => {
    const response = (pageInfo: Record<string, unknown>) => ({
      data: {
        repository: {
          pullRequest: {
            reviewThreads: {
              pageInfo,
              nodes: [
                {
                  id: "one",
                  isResolved: false,
                  comments: {
                    nodes: [
                      {
                        body: "please fix",
                        createdAt: "now",
                        path: "a.ts",
                        line: 1,
                        author: { login: "someone" },
                      },
                    ],
                  },
                },
              ],
            },
          },
        },
      },
    });
    expect(() =>
      parseReviewThreadPage(response({ hasNextPage: true, endCursor: null }))
    ).toThrow(WatcherQueryError);
    expect(
      parseReviewThreadPage(response({ hasNextPage: true, endCursor: "next" }))
        .endCursor
    ).toBe("next");
    expect(
      parseReviewThreadPage(response({ hasNextPage: false, endCursor: null }))
        .endCursor
    ).toBeNull();
  });

  it("rejects a page that omits pageInfo instead of assuming one page", async () => {
    const response = {
      data: {
        repository: {
          pullRequest: { reviewThreads: { nodes: [] } },
        },
      },
    };
    expect(() => parseReviewThreadPage(response)).toThrow(WatcherQueryError);
  });
});

describe("context and stack discovery", () => {
  it("returns a fully explicit context without any reader call", async () => {
    const reader = fakeReader();
    expect(
      await resolveContext({
        reader,
        owner: "explicit",
        repo: "repo",
        pr: context.number,
      })
    ).toEqual({ owner: "explicit", repo: "repo", number: context.number });
    expect(reader.calls).toEqual([]);
  });

  it("uses the local origin before currentPr for an explicit number", async () => {
    const reader = fakeReader({ origin: { owner: "local", repo: "checkout" } });
    expect(
      await resolveContext({
        reader,
        owner: null,
        repo: null,
        pr: context.number,
      })
    ).toEqual({ owner: "local", repo: "checkout", number: context.number });
    expect(reader.calls).toEqual(["originRepo"]);
  });

  const local = { owner: "owner", repo: "repo" };
  const fork = { owner: "contributor", repo: "repo" };

  it("orders the connected stack bottom-to-top", () => {
    const ordered = orderStack(context, [
      {
        number: parsePrNumber(41),
        headRepository: local,
        headRefName: "base-feature",
        baseRefName: "main",
      },
      {
        number: context.number,
        headRepository: local,
        headRefName: "feature",
        baseRefName: "base-feature",
      },
      {
        number: parsePrNumber(43),
        headRepository: local,
        headRefName: "upstack",
        baseRefName: "feature",
      },
    ]);
    expect(ordered.map((item) => Number(item.number))).toEqual([41, 42, 43]);
  });
  it("does not use a fork's same-named head as a stack parent", () => {
    const ordered = orderStack(context, [
      {
        number: parsePrNumber(41),
        headRepository: fork,
        headRefName: "base-feature",
        baseRefName: "main",
      },
      {
        number: context.number,
        headRepository: local,
        headRefName: "feature",
        baseRefName: "base-feature",
      },
    ]);
    expect(ordered.map((item) => Number(item.number))).toEqual([42]);
  });

  it("does not attach upstream branch children to a fork head", () => {
    const ordered = orderStack(context, [
      {
        number: context.number,
        headRepository: fork,
        headRefName: "feature",
        baseRefName: "main",
      },
      {
        number: parsePrNumber(43),
        headRepository: local,
        headRefName: "upstack",
        baseRefName: "feature",
      },
    ]);
    expect(ordered.map((item) => Number(item.number))).toEqual([42]);
  });

  it("keeps a fork pull request out of the stack when its branch name collides", () => {
    const ordered = orderStack(context, [
      {
        number: parsePrNumber(41),
        headRepository: local,
        headRefName: "base-feature",
        baseRefName: "main",
      },
      {
        number: context.number,
        headRepository: local,
        headRefName: "feature",
        baseRefName: "base-feature",
      },
      {
        number: parsePrNumber(43),
        headRepository: local,
        headRefName: "upstack",
        baseRefName: "feature",
      },
      {
        number: parsePrNumber(44),
        headRepository: fork,
        headRefName: "upstack",
        baseRefName: "feature",
      },
    ]);
    expect(ordered.map((item) => Number(item.number))).toEqual([41, 42, 43]);
  });

  it("refuses a full open PR page instead of assuming it is the whole stack", async () => {
    const open = (count: number) =>
      Array.from({ length: count }, (_, index) => ({
        number: parsePrNumber(index + 1),
        headRepository: local,
        headRefName: `branch-${index + 1}`,
        baseRefName: "main",
      }));
    await expect(
      discoverStack(fakeReader({ openPullRequests: open(300) }), context)
    ).rejects.toMatchObject({ failure: { kind: "invalid-stack" } });
    const short = await discoverStack(
      fakeReader({ openPullRequests: open(299) }),
      context
    );
    expect(short.map((pr) => Number(pr.number))).toEqual([42]);
  });

  it("terminates when an unrelated fork opens main against main", () => {
    // Bound the subprocess so this regression reports a failure instead of hanging the suite.
    const program = `import { orderStack } from ${JSON.stringify(import.meta.dir + "/github.ts")};
      console.log(JSON.stringify(orderStack(${JSON.stringify(context)}, [
        { number: 41, headRefName: "main", baseRefName: "main", headRepository: { owner: "contributor", repo: "repo" } },
        { number: 42, headRefName: "feature", baseRefName: "main", headRepository: { owner: "owner", repo: "repo" } }
      ])));`;
    const child = spawnSync(process.execPath, ["-e", program], { encoding: "utf8", timeout: 2000 });
    expect(child.error).toBeUndefined();
    expect(child.status).toBe(0);
    expect(JSON.parse(child.stdout).map((item: { number: number }) => item.number)).toEqual([42]);
  });

  it("requests and parses fork identity from gh before stack discovery", () => {
    const directory = mkdtempSync(join(tmpdir(), "watch-pr-fork-"));
    try {
      writeFileSync(join(directory, "gh"), `#!/bin/sh
case "$*" in
  *number,headRefName,baseRefName,headRepository,headRepositoryOwner*) ;;
  *) exit 2 ;;
esac
printf '%s\\n' '[{"number":42,"headRefName":"feature","baseRefName":"main","headRepository":{"name":"repo"},"headRepositoryOwner":{"login":"contributor"}}]'
`, { mode: 0o755 });
      const program = `import { GhGitHubReader } from ${JSON.stringify(import.meta.dir + "/github.ts")};
        console.log(JSON.stringify(await new GhGitHubReader().openPullRequests({ owner: "owner", repo: "repo" })));`;
      const child = spawnSync(process.execPath, ["-e", program], {
        encoding: "utf8", timeout: 2000,
        env: { ...process.env, PATH: directory + ":" + process.env.PATH },
      });
      expect(child.error).toBeUndefined();
      expect(child.status).toBe(0);
      expect(JSON.parse(child.stdout)).toEqual([
        {
          number: 42,
          headRepository: { owner: "contributor", repo: "repo" },
          headRefName: "feature",
          baseRefName: "main",
        },
      ]);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it("reports a missing gh as a failure the watcher must not retry", () => {
    const directory = mkdtempSync(join(tmpdir(), "watch-pr-nogh-"));
    try {
      const program = `import { GhGitHubReader } from ${JSON.stringify(import.meta.dir + "/github.ts")};
        try {
          await new GhGitHubReader().openPullRequests({ owner: "owner", repo: "repo" });
          console.log(JSON.stringify({ ok: true }));
        } catch (error) {
          console.log(JSON.stringify({ kind: error.failure?.kind, retryable: error.failure?.retryable }));
        }`;
      const child = spawnSync(process.execPath, ["-e", program], {
        encoding: "utf8",
        timeout: 5000,
        env: { ...process.env, PATH: directory },
      });
      expect(child.error).toBeUndefined();
      expect(child.status).toBe(0);
      expect(JSON.parse(child.stdout)).toEqual({
        kind: "spawn-failed",
        retryable: false,
      });
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });

  it("asks gh for more open pull requests than its 30-row default", () => {
    const directory = mkdtempSync(join(tmpdir(), "watch-pr-limit-"));
    try {
      // Model `gh pr list`: it returns 30 rows unless --limit asks for more.
      writeFileSync(join(directory, "gh"), `#!/bin/sh
limit=30
prev=
for arg in "$@"; do
  if [ "$prev" = "--limit" ]; then limit=$arg; fi
  prev=$arg
done
if [ "$limit" -gt 31 ]; then limit=31; fi
i=1
printf '['
while [ "$i" -le "$limit" ]; do
  if [ "$i" -gt 1 ]; then printf ','; fi
  printf '{"number":%s,"headRefName":"branch-%s","baseRefName":"main","headRepository":{"name":"repo"},"headRepositoryOwner":{"login":"owner"}}' "$i" "$i"
  i=$((i + 1))
done
printf ']\\n'
`, { mode: 0o755 });
      const program = `import { GhGitHubReader } from ${JSON.stringify(import.meta.dir + "/github.ts")};
        console.log(JSON.stringify((await new GhGitHubReader().openPullRequests({ owner: "owner", repo: "repo" })).map((pr) => pr.number)));`;
      const child = spawnSync(process.execPath, ["-e", program], {
        encoding: "utf8", timeout: 2000,
        env: { ...process.env, PATH: directory + ":" + process.env.PATH },
      });
      expect(child.error).toBeUndefined();
      expect(child.status).toBe(0);
      expect(JSON.parse(child.stdout)).toHaveLength(31);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });

});

describe("command timeout", () => {
  it("gives up on a hung gh or git call instead of blocking the watch", async () => {
    await expect(
      runCommand([process.execPath, "-e", "setTimeout(() => {}, 10000)"], 0.05)
    ).rejects.toMatchObject({
      failure: { kind: "command-timeout", retryable: true },
    });
  });

  it("returns normally for a command that finished in time", async () => {
    const result = await runCommand([
      process.execPath,
      "-e",
      "console.log('ok')",
    ]);
    expect(result.code).toBe(0);
    expect(result.stdout.trim()).toBe("ok");
  });
});
