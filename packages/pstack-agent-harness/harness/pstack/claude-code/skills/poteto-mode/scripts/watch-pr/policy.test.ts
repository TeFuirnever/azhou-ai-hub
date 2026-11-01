import { describe, expect, it } from "bun:test";
import { WatcherQueryError } from "./github.ts";
import {
  applyQueueSnapshot,
  assessGitHubMerge,
  classifyPr,
  createQueueState,
  evaluateQueue,
  planQueue,
  queryBackoffSeconds,
  readSnapshot,
  runQueued,
  runSimple,
  selectTierMajorStackDecision,
} from "./policy.ts";
import {
  fakeReader,
  failedCheck,
  passingCheck,
  pendingCheck,
} from "./fakes.test-helper.ts";
import type {
  GitHubReader,
  NonEmpty,
  PollingOptions,
  PrContext,
  ProgressVerdict,
  PullRequestFacts,
  RollupState,
} from "./types.ts";
import { parsePrNumber } from "./types.ts";

const context = (number: number): PrContext => ({
  owner: "owner",
  repo: "repo",
  number: parsePrNumber(number),
});
const options = {
  interval: 10,
  sweepInterval: 300,
  timeout: 0,
  maxQueryErrors: 5,
  allowDraft: false,
} satisfies PollingOptions;

describe("readiness truth table", () => {
  it("covers every specified row and every UNKNOWN rollup value", () => {
    const cases: readonly [
      PullRequestFacts["mergeStateStatus"],
      RollupState,
      "allowed" | "refused",
    ][] = [
      ["BLOCKED", "FAILURE", "refused"],
      ["BLOCKED", "ERROR", "refused"],
      ["BLOCKED", "PENDING", "allowed"],
      ["UNSTABLE", "FAILURE", "allowed"],
      ["UNKNOWN", "ERROR", "allowed"],
      ["UNKNOWN", "EXPECTED", "allowed"],
      ["UNKNOWN", "FAILURE", "allowed"],
      ["UNKNOWN", "PENDING", "allowed"],
      ["UNKNOWN", "SUCCESS", "allowed"],
      ["UNKNOWN", null, "allowed"],
      ["CLEAN", "SUCCESS", "allowed"],
    ];
    for (const [mergeStateStatus, headRollupState, expected] of cases) {
      expect(
        assessGitHubMerge({ mergeStateStatus, headRollupState }).kind
      ).toBe(expected);
    }
  });

  it("turns a clean visible list plus GitHub refusal into an explicit CI blocker", async () => {
    const reader = fakeReader({
      facts: { mergeStateStatus: "BLOCKED" },
      fastPath: { kind: "checks", checks: [passingCheck()] },
      commitRollups: [{ oid: "head", state: "FAILURE" }],
    });
    const snapshot = await readSnapshot({
      reader,
      context: context(1),
      pendingHistory: "include",
      allowDraft: false,
    });
    expect(snapshot.kind).toBe("open");
    if (snapshot.kind !== "open") throw new Error("expected open snapshot");
    expect(snapshot.ci.kind).toBe("ci-github-rejected");
    expect(classifyPr(snapshot)).toMatchObject({
      kind: "blocker",
      blocker: { kind: "failing-checks" },
    });
  });
});

describe("snapshot query planning", () => {
  it("does not query commit rollups while queued checks are pending", async () => {
    const reader = fakeReader({
      fastPath: { kind: "checks", checks: [pendingCheck()] },
    });
    const snapshot = await readSnapshot({
      reader,
      context: context(2),
      pendingHistory: "omit",
      allowDraft: false,
    });
    expect(snapshot.kind).toBe("open");
    if (snapshot.kind !== "open") throw new Error("expected open snapshot");
    expect(snapshot.ci.kind).toBe("ci-pending");
    expect(reader.calls).toEqual([
      "pullRequest",
      "reviewThreadPage:null",
      "checksFastPath",
      "pullRequest",
    ]);
  });

  it("queries rollups for settled and failed lists", async () => {
    const settled = fakeReader();
    await readSnapshot({
      reader: settled,
      context: context(3),
      pendingHistory: "omit",
      allowDraft: false,
    });
    expect(settled.calls).toContain("commitRollups");

    const failed = fakeReader({
      fastPath: { kind: "checks", checks: [failedCheck()] },
    });
    await readSnapshot({
      reader: failed,
      context: context(4),
      pendingHistory: "omit",
      allowDraft: false,
    });
    expect(failed.calls).toContain("commitRollups");
  });

  it("short-circuits merged rows before threads and checks", async () => {
    const reader = fakeReader({
      facts: { state: "MERGED", mergedAt: "2026-07-26T00:00:00Z" },
    });
    expect(
      (
        await readSnapshot({
          reader,
          context: context(5),
          pendingHistory: "include",
          allowDraft: false,
        })
      ).kind
    ).toBe("merged");
    expect(reader.calls).toEqual(["pullRequest"]);
  });
});

it("scans stacks tier-major so an upstack conflict outranks frontier CI", async () => {
  const frontier = await readSnapshot({
    reader: fakeReader({
      fastPath: { kind: "checks", checks: [failedCheck()] },
      commitRollups: [{ oid: "head", state: "FAILURE" }],
    }),
    context: context(10),
    pendingHistory: "omit",
    allowDraft: false,
  });
  const upstack = await readSnapshot({
    reader: fakeReader({ facts: { mergeable: "CONFLICTING" } }),
    context: context(11),
    pendingHistory: "omit",
    allowDraft: false,
  });
  const decision = selectTierMajorStackDecision([frontier, upstack]);
  expect(decision).toMatchObject({
    kind: "blocker",
    blocker: { kind: "merge-conflicts", pr: { number: 11 } },
  });
});

it("attributes a stack wait to the PR whose checks are pending, not the bottom", async () => {
  const readyBottom = await readSnapshot({
    reader: fakeReader(),
    context: context(20),
    pendingHistory: "omit",
    allowDraft: false,
  });
  const pendingUpstack = await readSnapshot({
    reader: fakeReader({
      fastPath: { kind: "checks", checks: [pendingCheck("upstack-build")] },
    }),
    context: context(21),
    pendingHistory: "omit",
    allowDraft: false,
  });
  const decision = selectTierMajorStackDecision([readyBottom, pendingUpstack]);
  expect(decision).toMatchObject({
    kind: "waiting",
    frontier: { number: 21 },
    reason: { kind: "pending-checks", pending: [{ name: "upstack-build" }] },
  });
});

it("waits on a draft while checks are pending, then reports the draft gate", async () => {
  const pending = await readSnapshot({
    reader: fakeReader({
      facts: { isDraft: true },
      fastPath: { kind: "checks", checks: [pendingCheck()] },
    }),
    context: context(12),
    pendingHistory: "omit",
    allowDraft: false,
  });
  expect(classifyPr(pending).kind).toBe("waiting");

  const settled = await readSnapshot({
    reader: fakeReader({ facts: { isDraft: true } }),
    context: context(12),
    pendingHistory: "omit",
    allowDraft: false,
  });
  expect(classifyPr(settled)).toMatchObject({
    kind: "blocker",
    blocker: { kind: "merge-gate", reason: "draft-pr" },
  });
});

describe("queued-stack cadence", () => {
  async function openSnapshot(pr: PrContext) {
    return readSnapshot({
      reader: fakeReader(),
      context: pr,
      pendingHistory: "omit",
      allowDraft: false,
    });
  }

  it("drops a sweep head only after its snapshot succeeds", async () => {
    const queue = [
      context(20),
      context(21),
      context(22),
    ] satisfies NonEmpty<PrContext>;
    let state = createQueueState(queue, 0);
    const first = await openSnapshot(queue[0]);
    state = applyQueueSnapshot(state, first, 0, options).state;
    expect(state.work).toMatchObject({
      kind: "whole-stack-sweep",
      remaining: [{ number: 21 }, { number: 22 }],
    });
    const second = await openSnapshot(queue[1]);
    state = applyQueueSnapshot(state, second, 60, options).state;
    expect(state.work).toMatchObject({
      kind: "whole-stack-sweep",
      remaining: [{ number: 22 }],
    });
  });

  it("resumes the sweep at the PR whose read failed", async () => {
    const middle = context(21);
    const base = fakeReader();
    let failNext = true;
    const timeline: string[] = [];
    const reader = {
      ...base,
      async pullRequest(pr: PrContext) {
        if (pr.number === middle.number && failNext) {
          failNext = false;
          timeline.push(`fail:${pr.number}`);
          throw new WatcherQueryError({
            kind: "command-exit",
            retryable: true,
            detail: "rate limited",
            code: 1,
          });
        }
        timeline.push(`read:${pr.number}`);
        return base.pullRequest(pr);
      },
    } satisfies GitHubReader;
    let now = 0;
    let sleeps = 0;
    const running = runQueued({
      dependencies: {
        reader,
        clock: {
          now: () => now,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep(seconds) {
            timeline.push("sleep");
            now += seconds;
            sleeps += 1;
            if (sleeps === 2) throw new Error("stop after resume proof");
          },
        },
        emit(verdict) {
          timeline.push(`emit:${verdict.kind}`);
        },
      },
      contexts: [context(20), middle, context(22)],
      options,
    });
    await expect(running).rejects.toThrow("stop after resume proof");
    // An open snapshot reads the facts twice: once to start the verdict and once
    // to confirm nothing it depends on moved while the checks were collected.
    expect(timeline).toEqual([
      "emit:QUEUE",
      "read:20",
      "read:20",
      "fail:21",
      "emit:RETRY",
      "sleep",
      "read:21",
      "read:21",
      "read:22",
      "read:22",
      "emit:STATUS",
      "emit:WAITING",
      "sleep",
    ]);
  });

  it("emits a completed sweep only after its final successful snapshot", async () => {
    const queue = [context(30), context(31)] satisfies NonEmpty<PrContext>;
    let state = createQueueState(queue, 0);
    const first = applyQueueSnapshot(
      state,
      await openSnapshot(queue[0]),
      0,
      options
    );
    expect(first.completedSweepRows).toBeNull();
    state = first.state;
    const second = applyQueueSnapshot(
      state,
      await openSnapshot(queue[1]),
      5,
      options
    );
    expect(
      second.completedSweepRows?.map((row) => Number(row.context.number))
    ).toEqual([30, 31]);
    expect(second.state.nextSweepAt).toBe(305);
  });

  it("ADVANCE continues directly to the new frontier without sleeping", async () => {
    const one = context(40);
    const two = context(41);
    const base = fakeReader();
    let merged = false;
    const timeline: string[] = [];
    const reader = {
      ...base,
      async pullRequest(pr: PrContext) {
        timeline.push(`read:${pr.number}`);
        const facts = await base.pullRequest(pr);
        return pr.number === one.number && merged
          ? {
              ...facts,
              state: "MERGED" as const,
              mergedAt: "2026-07-26T00:00:00Z",
            }
          : facts;
      },
    } satisfies GitHubReader;
    let now = 0;
    let sleeps = 0;
    const emitted: ProgressVerdict[] = [];
    const running = runQueued({
      dependencies: {
        reader,
        clock: {
          now: () => now,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep(seconds) {
            merged = true;
            timeline.push("sleep");
            now += seconds;
            sleeps += 1;
            if (sleeps === 2) throw new Error("stop after advance proof");
          },
        },
        emit(verdict) {
          emitted.push(verdict);
          timeline.push(`emit:${verdict.kind}`);
        },
      },
      contexts: [one, two],
      options,
    });
    await expect(running).rejects.toThrow("stop after advance proof");
    expect(emitted.some((event) => event.kind === "ADVANCE")).toBe(true);
    const firstSleep = timeline.indexOf("sleep");
    const secondSleep = timeline.indexOf("sleep", firstSleep + 1);
    expect(timeline.slice(firstSleep, secondSleep)).toEqual([
      "sleep",
      "read:40",
      "emit:ADVANCE",
      "read:41",
      "read:41",
      "emit:WAITING",
    ]);
  });

  it("deduplicates identical waits and schedules the next due sweep", async () => {
    const queue = [context(50)] satisfies NonEmpty<PrContext>;
    let state = createQueueState(queue, 0);
    state = applyQueueSnapshot(
      state,
      await openSnapshot(queue[0]),
      0,
      options
    ).state;
    const first = evaluateQueue(state, 0, options);
    expect(first.kind).toBe("waiting");
    if (first.kind !== "waiting") throw new Error("expected waiting");
    expect(first.emit).toBe(true);
    const second = evaluateQueue(first.state, 10, options);
    expect(second.kind).toBe("waiting");
    if (second.kind !== "waiting") throw new Error("expected waiting");
    expect(second.emit).toBe(false);
    expect(planQueue(second.state, 300).work?.kind).toBe("whole-stack-sweep");
  });
});

it("uses the specified retry floor and cap", () => {
  expect(queryBackoffSeconds(1, 1)).toBe(60);
  expect(queryBackoffSeconds(1, 2)).toBe(120);
  expect(queryBackoffSeconds(60, 4)).toBe(300);
});


describe("polling deadline sleeps", () => {
  for (const mode of ["single", "queued-stack", "query-retry"] as const) {
    it(`caps ${mode} sleeps at the configured deadline`, async () => {
      let now = 0;
      const sleeps: number[] = [];
      const pending = fakeReader({ fastPath: { kind: "checks", checks: [pendingCheck()] } });
      const reader = mode === "query-retry"
        ? { ...pending, async pullRequest(): Promise<PullRequestFacts> {
          throw new WatcherQueryError({ kind: "command-exit", retryable: true, code: 1, detail: "temporary failure" });
        } }
        : pending;
      const dependencies = {
        reader,
        clock: {
          now: () => now,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep(seconds: number) { sleeps.push(seconds); now += seconds; },
        },
        emit() {},
      };
      const polling = { ...options, interval: 60, timeout: 5 };
      const result = mode === "queued-stack"
        ? await runQueued({ dependencies, contexts: [context(1)], options: polling })
        : await runSimple({ dependencies, contexts: [context(1)], mode: "single", statusOnly: false, options: polling });
      expect(result.kind).toBe("TIMEOUT");
      expect(sleeps).toEqual([5]);
      expect(now).toBe(5);
    });
  }
  it("preserves the polling interval when the deadline is disabled", async () => {
    let now = 0;
    let reads = 0;
    const sleeps: number[] = [];
    const pending = fakeReader({ fastPath: { kind: "checks", checks: [pendingCheck()] } });
    const passed = fakeReader({ fastPath: { kind: "checks", checks: [passingCheck()] } });
    const result = await runSimple({
      dependencies: {
        reader: {
          ...pending,
          async checksFastPath(pr) {
            reads += 1;
            return reads === 1 ? pending.checksFastPath(pr) : passed.checksFastPath(pr);
          },
        },
        clock: {
          now: () => now,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep(seconds) { sleeps.push(seconds); now += seconds; },
        },
        emit() {},
      },
      contexts: [context(1)], mode: "single", statusOnly: false,
      options: { ...options, interval: 60, timeout: 0 },
    });
    expect(result.kind).toBe("READY");
    expect(sleeps).toEqual([60]);
  });

});

describe("no-checks confirmation", () => {
  const noChecks = (): GitHubReader => {
    const base = fakeReader({
      fastPath: { kind: "none-reported" },
      commitRollups: [{ oid: "head", state: null }],
    });
    return {
      ...base,
      async checkRollupPage() {
        return { kind: "no-rollup" };
      },
    };
  };

  it("waits instead of reporting a head with no checks ready", async () => {
    const row = await readSnapshot({
      reader: noChecks(),
      context: context(1),
      pendingHistory: "include",
      allowDraft: false,
      confirmNoChecks: () => false,
    });
    expect(classifyPr(row)).toMatchObject({
      kind: "waiting",
      reason: { kind: "checks-unreported" },
    });
    const confirmed = await readSnapshot({
      reader: noChecks(),
      context: context(1),
      pendingHistory: "include",
      allowDraft: false,
      confirmNoChecks: () => true,
    });
    expect(classifyPr(confirmed)).toMatchObject({ kind: "ready" });
  });

  it("reports ready only after the same head has shown no checks for 60 seconds", async () => {
    let now = 0;
    const sleeps: number[] = [];
    const waits: string[] = [];
    const result = await runSimple({
      dependencies: {
        reader: noChecks(),
        clock: {
          now: () => now,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep(seconds) {
            sleeps.push(seconds);
            now += seconds;
          },
        },
        emit(verdict) {
          if (verdict.kind === "WAITING") waits.push(verdict.reason.kind);
        },
      },
      contexts: [context(1)],
      mode: "single",
      statusOnly: false,
      options: { ...options, interval: 30, timeout: 0 },
    });
    expect(waits).toEqual(["checks-unreported", "checks-unreported"]);
    expect(sleeps).toEqual([30, 30]);
    expect(result.kind).toBe("READY");
  });

  it("restarts the confirmation window when the head moves", async () => {
    const base = noChecks();
    let now = 0;
    const sleeps: number[] = [];
    const reader: GitHubReader = {
      ...base,
      async pullRequest(pr) {
        const facts = await base.pullRequest(pr);
        return {
          ...facts,
          headRefOid: now < 30 ? "before-push" : "after-push",
        };
      },
    };
    const result = await runSimple({
      dependencies: {
        reader,
        clock: {
          now: () => now,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep(seconds) {
            sleeps.push(seconds);
            now += seconds;
          },
        },
        emit() {},
      },
      contexts: [context(1)],
      mode: "single",
      statusOnly: false,
      options: { ...options, interval: 30, timeout: 0 },
    });
    expect(result.kind).toBe("READY");
    expect(sleeps).toEqual([30, 30, 30]);
  });
});

describe("ready proof rests on GitHub's mergeability reading", () => {
  const snapshot = (mergeable: PullRequestFacts["mergeable"], number = 1) =>
    readSnapshot({
      reader: fakeReader({ facts: { mergeable } }),
      context: context(number),
      pendingHistory: "include",
      allowDraft: false,
    });

  it("does not report ready on passing checks alone", async () => {
    const decision = classifyPr(await snapshot("UNKNOWN"));
    expect(decision).toMatchObject({
      kind: "waiting",
      reason: { kind: "mergeability-unknown" },
    });
  });

  it("carries the reading GitHub gave once it reports the PR mergeable", async () => {
    const decision = classifyPr(await snapshot("MERGEABLE"));
    if (decision.kind !== "ready")
      throw new Error(`expected ready, got ${decision.kind}`);
    expect(decision.pr.proof.mergeability).toBe("clear");
  });

  it("holds the whole stack back on the same unproven reading", async () => {
    const rows = [await snapshot("MERGEABLE", 1), await snapshot("UNKNOWN", 2)];
    expect(selectTierMajorStackDecision(rows)).toMatchObject({
      kind: "waiting",
      frontier: { number: 2 },
      reason: { kind: "mergeability-unknown" },
    });
  });

  it("holds on the polling interval while GitHub has not computed mergeability", async () => {
    for (const facts of [
      { mergeable: "UNKNOWN" as const },
      {
        mergeable: "MERGEABLE" as const,
        mergeStateStatus: "UNKNOWN" as const,
      },
    ]) {
      const sleeps: number[] = [];
      const seen: string[] = [];
      let now = 0;
      const running = runSimple({
        dependencies: {
          reader: fakeReader({ facts }),
          clock: {
            now: () => now,
            observedAt: () => "2026-07-26T00:00:00.000Z",
            async sleep(seconds) {
              sleeps.push(seconds);
              now += seconds;
              throw new Error("stop after wait proof");
            },
          },
          emit(verdict) {
            seen.push(
              verdict.kind === "WAITING" ? verdict.reason.kind : verdict.kind
            );
          },
        },
        contexts: [context(1)],
        mode: "single",
        statusOnly: false,
        options: { ...options, interval: 45, timeout: 0 },
      });
      await expect(running).rejects.toThrow("stop after wait proof");
      expect(seen).toEqual(["mergeability-unknown"]);
      expect(sleeps).toEqual([45]);
    }
  });
});

describe("merge gates after the checks pass", () => {
  const decided = (facts: Partial<PullRequestFacts>) =>
    readSnapshot({
      reader: fakeReader({ facts }),
      context: context(1),
      pendingHistory: "include",
      allowDraft: false,
    }).then(classifyPr);

  it("blocks a pull request that is behind its base", async () => {
    expect(await decided({ mergeStateStatus: "BEHIND" })).toMatchObject({
      kind: "blocker",
      blocker: { kind: "merge-gate", reason: "behind-base" },
    });
  });

  it("blocks a pull request that still owes its required review", async () => {
    expect(await decided({ reviewDecision: "REVIEW_REQUIRED" })).toMatchObject({
      kind: "blocker",
      blocker: { kind: "merge-gate", reason: "review-required" },
    });
  });

  it("blocks the branch protection rule GitHub leaves the PR under", async () => {
    expect(await decided({ mergeStateStatus: "BLOCKED" })).toMatchObject({
      kind: "blocker",
      blocker: { kind: "merge-gate", reason: "branch-protection" },
    });
  });

  it("reports behind-base ahead of a required review", async () => {
    expect(
      await decided({
        mergeStateStatus: "BEHIND",
        reviewDecision: "REVIEW_REQUIRED",
      })
    ).toMatchObject({
      kind: "blocker",
      blocker: { kind: "merge-gate", reason: "behind-base" },
    });
  });

  it("keeps reporting the wait while checks are still running", async () => {
    const row = await readSnapshot({
      reader: fakeReader({
        facts: { reviewDecision: "REVIEW_REQUIRED" },
        fastPath: { kind: "checks", checks: [pendingCheck("build")] },
      }),
      context: context(1),
      pendingHistory: "include",
      allowDraft: false,
    });
    expect(classifyPr(row)).toMatchObject({
      kind: "waiting",
      reason: { kind: "pending-checks" },
    });
  });
});

describe("unrecoverable query failures", () => {
  it("ends the watch on the first failure rather than retrying it", async () => {
    const base = fakeReader();
    let reads = 0;
    const reader: GitHubReader = {
      ...base,
      async pullRequest() {
        reads += 1;
        throw new WatcherQueryError({
          kind: "spawn-failed",
          retryable: false,
          detail: "could not run gh: ENOENT",
        });
      },
    };
    const result = await runSimple({
      dependencies: {
        reader,
        clock: {
          now: () => 0,
          observedAt: () => "2026-07-26T00:00:00.000Z",
          async sleep() {
            throw new Error("an unrecoverable failure must not reach a sleep");
          },
        },
        emit() {},
      },
      contexts: [context(1)],
      mode: "single",
      statusOnly: false,
      options,
    });
    expect(reads).toBe(1);
    expect(result).toMatchObject({
      kind: "BLOCKER",
      exitCode: 7,
      blocker: { kind: "status-query", failures: 1 },
    });
  });
});

describe("snapshot consistency between the two reads", () => {
  const changing = (
    options: Parameters<typeof fakeReader>[0],
    change: Partial<PullRequestFacts>
  ): GitHubReader => {
    const base = fakeReader(options);
    let reads = 0;
    return {
      ...base,
      async pullRequest(pr) {
        reads += 1;
        const facts = await base.pullRequest(pr);
        return reads === 1 ? facts : { ...facts, ...change };
      },
    };
  };
  const collect = (reader: GitHubReader) =>
    readSnapshot({
      reader,
      context: context(1),
      pendingHistory: "include",
      allowDraft: false,
    });

  it("refuses a verdict when the head moved while checks were collected", async () => {
    await expect(collect(changing({}, { headRefOid: "moved" }))).rejects.toMatchObject(
      {
        name: "WatcherQueryError",
        failure: { kind: "snapshot-changed", retryable: true },
      }
    );
  });

  it("refuses a verdict when the base or the review moved", async () => {
    await expect(
      collect(
        changing(
          {},
          { baseRefName: "release", reviewDecision: "CHANGES_REQUESTED" }
        )
      )
    ).rejects.toMatchObject({ failure: { kind: "snapshot-changed" } });
    await expect(
      collect(changing({}, { isDraft: true }))
    ).rejects.toMatchObject({ failure: { kind: "snapshot-changed" } });
  });

  it("keeps the reading when GitHub merely computes mergeability", async () => {
    const row = await collect(
      changing(
        {
          facts: {
            mergeable: "UNKNOWN",
            mergeStateStatus: "UNKNOWN",
          },
        },
        { mergeable: "MERGEABLE", mergeStateStatus: "CLEAN" }
      )
    );
    expect(row.kind).toBe("open");
  });
});
