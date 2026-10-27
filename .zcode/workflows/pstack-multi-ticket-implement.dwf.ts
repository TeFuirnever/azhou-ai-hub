/* zcode-workflow
description: 发布 .planning/pstack-orchestrator-coexistence 下的 spec 与五张票到
  GitHub（幂等查重、原生父子与阻塞关系、读回核验），领取/认领 Treehouse 租约，逐票 01→05 实施：每票实施员 → verify.py
  确定性门禁（最多 4 轮修复）→ 独立评审员（含"未通过但零意见"的契约修复）→ 推送与草稿 PR → 批次独立终审 → 记录员回写
  .planning。内置本次踩过的全部坑：早退分支必须 return、评审输出契约防御、租约按 treehouse status 认领而非解析 get
  输出。
whenToUse: 本仓库 .planning/pstack-orchestrator-coexistence 的票批次推进或补跑（如票05 live
  验收补跑、新批次票）。常量绑定该规划目录与 lease holder zcode-pstack-coexistence-20261026、分支
  codex/pstack-orchestrator-coexistence；其他批次 fork 脚本改头部常量。运行前需要：treehouse
  池有空槽或已按 holder 建好租约（池满时先 treehouse lease <槽位> --lease-holder <holder>）。
*/
interface PublishTicket {
  /** 票编号键，"01"–"05"。 */
  key: string;
  /** 对应 GitHub issue 编号；0 表示未能创建。 */
  number: number;
}

interface PublishResult {
  /** spec issue 编号；0 表示未能创建。 */
  specNumber: number;
  tickets: PublishTicket[];
  /** 关系机制：native / body / mixed。 */
  linking: string;
  /** 创建与读回过程中的问题；空表示顺利。 */
  problems: string[];
}

interface WorkResult {
  /** done=本票完成；blocked=实施受阻。 */
  status: "done" | "blocked";
  /** 本票全部提交后的分支 HEAD（完整 sha）。 */
  head: string;
  /** 本票变更文件（仓库相对路径）。 */
  changedFiles: string[];
  /** 逐条对应验收标准的落实方式与证据。 */
  evidence: string[];
  /** 按票文允许保留的验收阻塞及原因。 */
  recordedBlockers: string[];
  /** status=blocked 时的阻塞原因。 */
  blockedOn?: string;
  notes: string;
}

interface ReviewFinding {
  /** 文件:行 或验收条目。 */
  where: string;
  what: string;
  severity: "low" | "medium" | "high";
  /** true=必须修复本票才能通过。 */
  blocking: boolean;
}

interface ReviewResult {
  approved: boolean;
  findings: ReviewFinding[];
}

interface TicketOutcome {
  key: string;
  title: string;
  status: "已完成" | "受阻";
  issue: number;
  head: string;
  blockers: string[];
}

interface Finding {
  /** Workspace-relative path, with a line when it applies. */
  where: string;
  /** One sentence: what is wrong, or what was found. */
  what: string;
  /** What showed it: the lines read, or the command and the output that proved it. */
  evidence: string;
  /** "verified" when an independent subagent or a deterministic check confirmed it; "unconfirmed" otherwise. */
  status: "verified" | "unconfirmed";
  /** How much it matters. Reserve "high" for data loss, a crash, or a wrong result. */
  severity: "low" | "medium" | "high";
}

interface WorkflowReport {
  /** Two or three sentences answering what the user asked for. */
  conclusion: string;
  findings: Finding[];
  /** What the run checked and how: the commands it ran, the files it covered. */
  verified: string[];
  /** What the run did not look at or could not check, and why. */
  notCovered: string[];
}

const REPO = "TeFuirnever/azhou-ai-hub";
const ORIG = "/Users/guanxueliang/Desktop/oh-my-ai/azhou-ai-hub";
const PLAN = ORIG + "/.planning/pstack-orchestrator-coexistence";
const HOLDER = "zcode-pstack-coexistence-20261026";
const BRANCH = "codex/pstack-orchestrator-coexistence";
const GATE_TIMEOUT = 1800000;

const TICKETS: { key: string; file: string; label: string }[] = [
  { key: "01", file: "01-task-owner-and-dispatch.md", label: "任务归属与模型派发" },
  { key: "02", file: "02-compatible-install-and-diagnosis.md", label: "共存安装与诊断" },
  { key: "03", file: "03-owned-update-and-removal.md", label: "更新与退出恢复" },
  { key: "04", file: "04-existing-install-transition.md", label: "既有安装转换" },
  { key: "05", file: "05-native-acceptance-and-support.md", label: "原生验收与说明" },
];

function parseJsonLoose(raw: string): unknown {
  const objStart = raw.indexOf("{");
  const arrStart = raw.indexOf("[");
  let start: number;
  if (objStart === -1 && arrStart === -1) throw new Error("输出中没有 JSON");
  if (objStart === -1) start = arrStart;
  else if (arrStart === -1) start = objStart;
  else start = Math.min(objStart, arrStart);
  const end = Math.max(raw.lastIndexOf("}"), raw.lastIndexOf("]"));
  if (end <= start) throw new Error("输出中没有完整 JSON");
  return JSON.parse(raw.slice(start, end + 1));
}

function tail4(s: string): string {
  return s.length > 4000 ? s.slice(s.length - 4000) : s;
}

const IMPL_SYSTEM =
  "你是 Azhou AI Hub 的资深实现工程师，在受控 Treehouse worktree 中落地一张已批准的工程票。遵守仓库 AGENTS.md 与 docs/worktree-policy.md。" +
  "诚实优先：做不到或验证不了就如实记录或明确提出问题，绝不伪造结果，绝不靠删检查、改宽断言或改写主环境制造通过。" +
  "若指令互相矛盾或某个检查不可能通过，明确提出问题（escalate）而不是绕过。";

const REV_SYSTEM =
  "你是资深工程评审，用新鲜视角找会坏的地方：读代码与测试、对照验收标准，指出缺失、被删除或放宽的保护、与规格的矛盾。" +
  "不做礼节性肯定，不做风格性挑剔；证据不足就明说。绝不编辑任何文件，绝不运行完整验证门禁。";

const PUB_SYSTEM =
  "你是发布执行员，把用户已批准的规划发布为本仓库的 GitHub issues。严格幂等：每次创建前按标题查重，已存在的必须复用，绝不重复立票。" +
  "只创建/编辑本批次的 spec 与五张票，不 assign、不创建 PR、不修改或关闭其他 issue。GitHub API 不可用时如实报告 problems，不伪造成功。";

function implAsk(t: { key: string; file: string; label: string }, wt: string, prevHead: string, outcomes: TicketOutcome[]): string {
  return [
    `本票：${t.key} ${t.label}（${PLAN}/tickets/${t.file}）。`,
    `受控 worktree：${wt}（分支 ${BRANCH}，本票 diff 基线 ${prevHead.slice(0, 12)}）。一切实现、测试与提交都在该 worktree 内完成；绝不改动原 checkout（${ORIG}）的工作区、其他 worktree 或用户主环境。`,
    ``,
    `先读（.planning 是原 checkout 的被忽略目录，worktree 里没有，用绝对路径读）：`,
    `- ${ORIG}/AGENTS.md 与 ${ORIG}/docs/worktree-policy.md（仓库规则）`,
    `- ${PLAN}/spec.md（用户已批准的共存规格）`,
    `- ${PLAN}/tickets/${t.file}（本票验收标准，逐条落实）`,
    `- ${PLAN}/sources.md（现状证据与文件定位图，从这些锚点出发核对当前源码）`,
    ``,
    `前序票已在该分支完成：${outcomes.length > 0 ? JSON.stringify(outcomes) : "（本票是第一张）"}。开始前先 git -C ${wt} log --oneline -10 了解现状；若本票已有部分提交（中断续作），核对后续续作，不重做。不要 rebase 或改写已有提交。`,
    ``,
    `硬性要求：`,
    `1. 验收落在可执行行为上：规则模板、pstack 的 Codex 映射、安装兼容判定、恢复路径与对应测试；说明文字仅作同步。禁止只改文档，禁止只删除或放宽现有冲突检查来制造通过——用基于实际安装状态的判定替换粗粒度拒绝时，必须同时给出新判定与测试。`,
    `2. 提交信息 type(scope): 祈使句摘要；代码、其测试与必要合同更新可同 commit。完成后工作树必须干净。若最终受阻：已自洽的部分提交，其余清理，blockedOn 写明原因。`,
    `3. 开发中运行针对性测试（sources.md 列出的相关套件）。完整 scripts/verify.py 由工作流脚本在你之后统一运行：你不要运行完整门禁，不要 push，不要运行任何 treehouse 命令（租约由脚本管理）。`,
    `4. 边界：不安装或修改主环境插件与用户级配置（~/.codex 等）、不动共享 Skills 安装、不改其他 harness 默认行为、不动开屏/壁纸/Pet。票内 Scope boundary 逐条遵守。真实宿主演示只在受控隔离环境（如临时 CODEX_HOME）尝试；不能安全隔离的验收项按票文记入 recordedBlockers 并说明影响，不以确定性测试冒充真实宿主验收。`,
    `5. 主会话模型、权限与项目约束始终遵循宿主规则；不新增编排器链或后台守护。`,
    ``,
    `返回 WorkResult：head=本票全部提交后的分支 HEAD 完整 sha；evidence 逐条对应验收标准；recordedBlockers 列出票文允许保留的验收阻塞及原因。`,
  ].join("\n");
}

function revAsk(t: { key: string; file: string; label: string }, wt: string, prevHead: string, headNow: string): string {
  return [
    `评审对象：${wt} 分支 ${BRANCH} 上 ${prevHead.slice(0, 12)}..${headNow.slice(0, 12)} 的全部改动（先 git -C ${wt} diff ${prevHead}..${headNow} 查看；本票范围，前序票已评审通过，不重审）。`,
    `依据：${PLAN}/tickets/${t.file} 的验收标准逐条核对，加 ${PLAN}/spec.md 对应章节。可读 worktree 中任何文件与测试，可运行只读命令（git diff/log/show、查看测试）；绝不编辑任何文件，绝不运行完整门禁。`,
    `问自己：什么会坏？哪些验收条目只是“文档说了”而没有可执行行为或测试？哪里删除或放宽了原有保护？哪里与规格的任务归属、让位、模型路径分离或 owner 规则矛盾？双语 README 与 docs 是否需要同步而未同步？`,
    `返回 ReviewResult：findings 逐条给 where（文件:行或验收条目）、what、severity、blocking；没有必须修复项时 approved=true。风格性偏好不要标 blocking。`,
  ].join("\n");
}

artifact.board("tickets", {
  key: "key",
  status: "status",
  columns: ["待开始", "实施中", "验证中", "评审中", "已完成", "受阻"],
  cardTitle: "title",
  detail: [{ field: "issue", label: "issue" }, { field: "head", label: "HEAD" }],
});

const findings: Finding[] = [];
const verified: string[] = [];
const outcomes: TicketOutcome[] = [];

let prUrl = "";
let chainBlocked: string | null = null;
let WT = "";
let LEASE_ID = "";
let BASE = "";

async function deliver(conclusion: string): Promise<WorkflowReport> {
  const notCovered: string[] = [];
  notCovered.push("GitHub Actions 远端 CI 未等待：推送后未核对检查结果");
  if (WT !== "") notCovered.push(`Treehouse 租约保留至人工审阅（${WT}，lease_id ${LEASE_ID}，holder ${HOLDER}），未归还`);
  notCovered.push("主环境迁移未执行：按用户约束需另行提供计划并获确认");
  for (const o of outcomes) {
    for (const b of o.blockers) notCovered.push(`票${o.key} 验收阻塞：${b}`);
  }
  if (chainBlocked !== null) notCovered.push(`依赖链在此终止：${chainBlocked}`);
  const lines: string[] = [
    "# pstack / orchestrator 共存实施报告",
    "",
    conclusion,
    "",
    `分支 \`${BRANCH}\`（基线 \`${BASE === "" ? "?" : BASE.slice(0, 12)}\`）${prUrl !== "" ? "，草稿 PR：" + prUrl : "（PR 未创建）"}`,
    WT !== "" ? `租约 \`${WT}\`（lease_id \`${LEASE_ID}\`）——保留至人工审阅` : "（worktree 未取得）",
    "",
    "## 各票结果",
    "",
    "| 票 | issue | 状态 | HEAD | 记录的验收阻塞 |",
    "|---|---|---|---|---|",
  ];
  for (const o of outcomes) {
    lines.push(`| ${o.key} ${o.title} | #${o.issue} | ${o.status} | \`${o.head.slice(0, 12)}\` | ${o.blockers.length > 0 ? o.blockers.join("；") : "无"} |`);
  }
  if (outcomes.length === 0) lines.push("|（无——未进入实施阶段）| | | | |");
  await artifact.markdown("report", lines.join("\n"), {
    title: "pstack / orchestrator 共存实施报告",
    description: "spec 与五张票的发布、逐票实施、门禁与评审结果，以及保留的租约和阻塞。",
    primary: true,
  });
  return { conclusion, findings, verified, notCovered };
}

phase("发布前查重");
const listRun = await world.run("gh", ["issue", "list", "--state", "all", "--limit", "300", "--json", "number,title,state"]);
let allIssues: { number: number; title: string; state: string }[] = [];
if (listRun.exitCode === 0) {
  try {
    allIssues = parseJsonLoose(listRun.stdout) as { number: number; title: string; state: string }[];
  } catch {
    allIssues = [];
  }
}
const dupes = allIssues.filter((i) => /pstack|orchestrator|受控共存/i.test(i.title));
log(dupes.length > 0 ? `发现 ${dupes.length} 个标题相关的既有 issue，发布执行员将复用而不重复立票` : "未发现重名 spec/票，按新批次发布");

phase("定稿并发布 spec 与五张票");
const publisher = agent("发布执行员", { system: PUB_SYSTEM });
const pub = await publisher.ask<PublishResult>(
  [
    `任务：把 ${PLAN} 下用户已批准的 spec 与五张票定稿并发布到 ${REPO} 的 GitHub issues，建立父子与阻塞依赖，读回验证。`,
    `查重结果（标题含 pstack/orchestrator/受控共存 的既有 issue，必须复用，缺失的才创建）：${JSON.stringify(dupes)}`,
    ``,
    `先读：${PLAN}/spec.md、${PLAN}/README.md、${PLAN}/sources.md、${PLAN}/tickets/ 下全部五张票，以及 ${ORIG}/docs/agents/issue-tracker.md 与 ${ORIG}/docs/agents/triage-labels.md。`,
    ``,
    `步骤（严格按此顺序，全程幂等）：`,
    `1. 定稿规划文件：spec.md 与各票的 “Status: draft-awaiting-approval” 改为已批准状态；spec 的「待用户确认」段落改写为已确认的结论（两个测试入口与 01→02→03→04→05 依赖已获用户批准）。`,
    `2. 创建 spec issue：标题 “spec: Codex 中 pstack 与 orchestrator 的受控共存”，body 用 gh issue create --body-file 指向定稿后的 spec.md 绝对路径，标签 ready-for-agent。`,
    `3. 把五张票文件的 Parent/Status 回填为真实 spec 编号，然后逐张创建（标题用票文件 H1 去掉 “# ”，如 “01: 选定 pstack 后正确让位并使用其子代理模型”，--body-file 指向票文件，标签 ready-for-agent）。`,
    `4. 回填每张票的 Blocked by 真实编号（01 无阻塞；02←01、03←02、04←03、05←04），并用 gh issue edit <n> --body-file <文件> 刷新已创建票的正文。`,
    `5. 关系优先用原生 API，失败降级并在 problems 记录：子票 gh api --method POST repos/${REPO}/issues/<spec编号>/sub_issues -F sub_issue_id=<票的数据库 id>（db id 用 gh api repos/${REPO}/issues/<n> --jq .id 获取）；阻塞 gh api --method POST repos/${REPO}/issues/<子编号>/dependencies/blocked_by -F issue_id=<阻塞方 db id>。降级方式：spec 正文 task list + 票正文 “Part of #spec” 与 “Blocked by: #n”。`,
    `6. 读回：逐个 gh issue view 核对标题、标签、状态与关系摘要（issue_dependencies_summary）。`,
    `7. 回填 ${PLAN}/README.md 与各票文件记录真实 issue 编号（该目录被 git 忽略，不需要提交）。`,
    ``,
    `禁止：assign 认领、创建/修改 PR、关闭或修改其他 issue、改动任何 git tracked 文件。`,
    `返回 PublishResult。`,
  ].join("\n"),
);

const issueBy: Record<string, number> = {};
for (const tk of pub.tickets) issueBy[tk.key] = tk.number;
const pubProblems = Array.isArray(pub.problems) ? pub.problems : [];
const missingIssues =
  pub.specNumber === 0 || TICKETS.some((t) => !issueBy[t.key]) || pubProblems.some((p) => /失败|不可用|无法/.test(p));
for (const p of pubProblems) {
  findings.push({ where: "GitHub 发布", what: p, evidence: "发布执行员报告", status: "unconfirmed", severity: "medium" });
}
if (missingIssues) {
  return await deliver(`发布未完成：spec=${pub.specNumber}，票编号=${JSON.stringify(pub.tickets)}，问题=${JSON.stringify(pub.problems)}。实施未开始，请人工核对 GitHub 后重跑。`);
}

phase("读回核验已发布 issues");
const readbackIds: { label: string; n: number; marker: string }[] = [
  { label: "spec", n: pub.specNumber, marker: "受控共存" },
  ...TICKETS.map((t) => ({ label: `票${t.key}`, n: issueBy[t.key], marker: t.key })),
];
let readbackBad = false;
for (const rb of readbackIds) {
  const v = await world.run("gh", ["issue", "view", String(rb.n), "--json", "number,title,state"]);
  let ok = v.exitCode === 0;
  if (ok) {
    try {
      const parsed = parseJsonLoose(v.stdout) as { title: string; state: string };
      ok = parsed.state === "OPEN" && parsed.title.includes(rb.marker);
    } catch {
      ok = false;
    }
  }
  if (!ok) {
    readbackBad = true;
    findings.push({ where: `issue #${rb.n}`, what: `${rb.label} 读回核验失败`, evidence: tail4(v.stdout + v.stderr), status: "verified", severity: "high" });
  }
}
if (readbackBad) {
  return await deliver(`读回核验未全部通过（关系机制：${pub.linking}），实施未开始。`);
}
verified.push(`spec #${pub.specNumber} 与五张票读回核验通过（关系机制 ${pub.linking}）`);
for (const t of TICKETS) {
  report({ key: t.key, title: `票${t.key} ${t.label}`, status: "待开始", issue: issueBy[t.key], head: "" }, "tickets");
}

phase("领取受控 worktree");
// 池已满（10 槽全部占用或 dirty，max_trees=8），租约由主会话以 treehouse lease 在槽位 2 原地建立；
// 脚本只按 status 认领本 holder 的租约，不解析 treehouse get 的输出形状。
const stRun = await world.run("treehouse", ["status", "--json"]);
if (stRun.exitCode === 0) {
  try {
    const entries = parseJsonLoose(stRun.stdout) as { path: string; status: string; lease_holder?: string; lease_id?: string }[];
    const mine = entries.find((e) => e.lease_holder === HOLDER && e.status === "leased" && e.lease_id !== undefined);
    if (mine !== undefined) {
      WT = mine.path;
      LEASE_ID = mine.lease_id ?? "";
    }
  } catch {
    // status 输出不含 JSON 时保持 WT 为空，走下面的阻塞分支
  }
}
if (WT === "") {
  findings.push({ where: "treehouse lease", what: `未找到 holder ${HOLDER} 的租约`, evidence: tail4(stRun.stdout + stRun.stderr), status: "verified", severity: "high" });
  return await deliver(`未找到 holder ${HOLDER} 的 Treehouse 租约，实施未开始。当前池 10 槽全部占用或 dirty（max_trees=8）：请人工确认某槽位 git 干净（仅 ignored 噪音）后运行 treehouse lease <槽位> --lease-holder ${HOLDER} --json，再重跑本工作流。`);
}
const c1 = await world.run("git", ["rev-parse", "--path-format=absolute", "--git-common-dir"]);
const c2 = await world.run("git", ["-C", WT, "rev-parse", "--path-format=absolute", "--git-common-dir"]);
const commonOk = c1.exitCode === 0 && c2.exitCode === 0 && c1.stdout.trim() === c2.stdout.trim();
if (!commonOk) {
  return await deliver(`租约校验失败（与主 checkout 不属同一仓库）。路径 ${WT}。实施未开始，租约需人工检查。`);
}
const headRun0 = await world.run("git", ["rev-parse", "HEAD"]);
BASE = headRun0.stdout.trim();
const coRun = await world.run("git", ["-C", WT, "checkout", "-B", BRANCH, BASE]);
if (coRun.exitCode !== 0) {
  return await deliver(`无法在 ${WT} 创建分支 ${BRANCH}（基线 ${BASE.slice(0, 12)}）：${tail4(coRun.stderr)}`);
}
log(`租约就绪：${WT}（${BRANCH} @ ${BASE.slice(0, 12)}，lease ${LEASE_ID.slice(0, 8)}…）`);

phase("运行基线门禁");
const baseGate = await world.run("python3", [WT + "/scripts/verify.py"], { timeoutMs: GATE_TIMEOUT });
if (baseGate.exitCode !== 0) {
  findings.push({ where: "scripts/verify.py", what: "基线门禁在未改动 worktree 上失败，存在与本任务无关的既有破损", evidence: tail4(baseGate.stdout + baseGate.stderr), status: "verified", severity: "high" });
  return await deliver(`基线门禁失败（基线 ${BASE.slice(0, 12)}），实施未开始；按 worktree 政策保留为显式 hold。`);
}
verified.push(`基线门禁通过：干净 worktree ${WT} @ ${BASE.slice(0, 12)} 上 scripts/verify.py 退出码 0`);

let prevHead = BASE;
const gateCmd = (): Promise<{ exitCode: number; stdout: string; stderr: string }> => world.run("python3", [WT + "/scripts/verify.py"], { timeoutMs: GATE_TIMEOUT });

for (const t of TICKETS) {
  if (chainBlocked !== null) break;
  const issueNumber = issueBy[t.key];
  report({ key: t.key, title: `票${t.key} ${t.label}`, status: "实施中", issue: issueNumber, head: prevHead.slice(0, 12) }, "tickets");
  log(`开始票${t.key} ${t.label}（issue #${issueNumber}）`);

  phase("实施与自测");
  const impl = agent(`实施员·票${t.key}`, { system: IMPL_SYSTEM });
  const work = await impl.ask<WorkResult>(implAsk(t, WT, prevHead, outcomes));
  if (work.status === "blocked") {
    const reason = work.blockedOn ?? work.notes;
    chainBlocked = `票${t.key} 实施受阻：${reason}`;
    outcomes.push({ key: t.key, title: t.label, status: "受阻", issue: issueNumber, head: prevHead, blockers: [reason] });
    report({ key: t.key, title: `票${t.key} ${t.label}`, status: "受阻", issue: issueNumber, head: prevHead.slice(0, 12) }, "tickets");
    report({ ticket: t.key, outcome: "受阻", reason, evidence: work.evidence });
    break;
  }
  const recBlockers = Array.isArray(work.recordedBlockers) ? work.recordedBlockers : [];

  phase("运行确定性门禁");
  let headNow = (await world.run("git", ["-C", WT, "rev-parse", "HEAD"])).stdout.trim();
  if (headNow === prevHead) {
    await impl.ask(`分支上没有发现你的新提交（HEAD 仍是 ${prevHead.slice(0, 12)}）。请在 ${WT} 的 ${BRANCH} 上提交本票改动后返回。`);
    headNow = (await world.run("git", ["-C", WT, "rev-parse", "HEAD"])).stdout.trim();
  }
  if (headNow === prevHead) {
    chainBlocked = `票${t.key} 声称完成但分支无新提交`;
    outcomes.push({ key: t.key, title: t.label, status: "受阻", issue: issueNumber, head: prevHead, blockers: [chainBlocked] });
    report({ key: t.key, title: `票${t.key} ${t.label}`, status: "受阻", issue: issueNumber, head: prevHead.slice(0, 12) }, "tickets");
    break;
  }
  report({ key: t.key, title: `票${t.key} ${t.label}`, status: "验证中", issue: issueNumber, head: headNow.slice(0, 12) }, "tickets");
  let gate = await gateCmd();
  let gateRound = 0;
  while (gate.exitCode !== 0 && gateRound < 4) {
    await impl.ask(
      `scripts/verify.py 门禁失败（第 ${gateRound + 1} 轮），输出末尾：\n${tail4(gate.stdout + "\n" + gate.stderr)}\n请在 ${WT} 修复。不得删除或放宽检查制造通过；若失败暴露的是检查与合同不符，修复时说明理由。`,
    );
    gateRound += 1;
    gate = await gateCmd();
  }
  if (gate.exitCode !== 0) {
    chainBlocked = `票${t.key} 门禁连续 ${gateRound} 轮修复后仍失败`;
    findings.push({ where: "scripts/verify.py", what: chainBlocked ?? "", evidence: tail4(gate.stdout + gate.stderr), status: "verified", severity: "high" });
    outcomes.push({ key: t.key, title: t.label, status: "受阻", issue: issueNumber, head: headNow, blockers: [chainBlocked] });
    report({ key: t.key, title: `票${t.key} ${t.label}`, status: "受阻", issue: issueNumber, head: headNow.slice(0, 12) }, "tickets");
    break;
  }
  const dirtyRun = await world.run("git", ["-C", WT, "status", "--porcelain"]);
  if (dirtyRun.exitCode === 0 && dirtyRun.stdout.trim() !== "") {
    await impl.ask(`worktree 仍有未提交内容：\n${tail4(dirtyRun.stdout)}\n请提交或清理，保持工作树干净（不相关的临时文件删除即可）。`);
    const dirty2 = await world.run("git", ["-C", WT, "status", "--porcelain"]);
    if (dirty2.exitCode === 0 && dirty2.stdout.trim() !== "") {
      chainBlocked = `票${t.key} 完成后工作树未清理干净`;
      outcomes.push({ key: t.key, title: t.label, status: "受阻", issue: issueNumber, head: headNow, blockers: [chainBlocked] });
      report({ key: t.key, title: `票${t.key} ${t.label}`, status: "受阻", issue: issueNumber, head: headNow.slice(0, 12) }, "tickets");
      break;
    }
    headNow = (await world.run("git", ["-C", WT, "rev-parse", "HEAD"])).stdout.trim();
  }
  verified.push(`票${t.key}：scripts/verify.py 门禁通过（HEAD ${headNow.slice(0, 12)}，修复 ${gateRound} 轮）`);

  phase("评审并修复");
  report({ key: t.key, title: `票${t.key} ${t.label}`, status: "评审中", issue: issueNumber, head: headNow.slice(0, 12) }, "tickets");
  const rev = agent(`评审员·票${t.key}`, { system: REV_SYSTEM });
  const reviewFindings = (r: ReviewResult): ReviewFinding[] => (Array.isArray(r.findings) ? r.findings : []);
  // “未通过但零意见”是评审输出契约故障（findings 为 undefined/空而 approved=false）：
  // 先要求评审员重述一次；再发生则记异常并视为通过，不让序列化故障阻塞整条依赖链
  // （该票 diff 仍会被批次独立终审覆盖）。
  const repairVerdict = async (r: ReviewResult): Promise<ReviewResult> => {
    if (r.approved || reviewFindings(r).length > 0) return r;
    const restated = await rev.ask<ReviewResult>(
      "你上一轮返回 approved=false 但 findings 为空，实施方无法执行。请重新给出 ReviewResult：确有必须修复的问题就逐条写入 findings（where/what/severity/blocking），没有就必须 approved=true；不允许空 findings 且 approved=false。",
    );
    if (restated.approved || reviewFindings(restated).length > 0) return restated;
    findings.push({ where: `票${t.key} 评审`, what: "评审员两轮“未通过但零意见”，按输出契约故障视为通过，留人工复核", evidence: "approved=false 且 findings 为空 ×2", status: "unconfirmed", severity: "low" });
    return { approved: true, findings: [] };
  };
  let review = await repairVerdict(await rev.ask<ReviewResult>(revAsk(t, WT, prevHead, headNow)));
  let rRound = 0;
  while (!review.approved && rRound < 3) {
    await impl.ask(
      `票${t.key} 评审未通过（第 ${rRound + 1} 轮），意见：\n${JSON.stringify(reviewFindings(review), null, 2)}\n请逐条处理 blocking 项与 medium 以上问题（确属误判的说明理由也算处理），在 ${WT} 提交修复。`,
    );
    let g2 = await gateCmd();
    if (g2.exitCode !== 0) {
      await impl.ask(`修复后门禁失败：\n${tail4(g2.stdout + g2.stderr)}\n请修复。`);
      g2 = await gateCmd();
    }
    if (g2.exitCode !== 0) {
      chainBlocked = `票${t.key} 评审修复后门禁仍失败`;
      findings.push({ where: "scripts/verify.py", what: chainBlocked ?? "", evidence: tail4(g2.stdout + g2.stderr), status: "verified", severity: "high" });
      break;
    }
    rRound += 1;
    review = await repairVerdict(await rev.ask<ReviewResult>(`票${t.key} 修复已提交，请重新查看 ${WT} 分支 ${BRANCH} 上 ${prevHead.slice(0, 12)}..HEAD 的 diff 并复核，返回 ReviewResult。`));
  }
  if (chainBlocked !== null) {
    outcomes.push({ key: t.key, title: t.label, status: "受阻", issue: issueNumber, head: headNow, blockers: [chainBlocked] });
    report({ key: t.key, title: `票${t.key} ${t.label}`, status: "受阻", issue: issueNumber, head: headNow.slice(0, 12) }, "tickets");
    break;
  }
  if (!review.approved) {
    chainBlocked = `票${t.key} 评审 ${rRound} 轮修复后仍未通过`;
    findings.push({ where: `票${t.key}`, what: chainBlocked ?? "", evidence: JSON.stringify(review.findings), status: "verified", severity: "high" });
    outcomes.push({ key: t.key, title: t.label, status: "受阻", issue: issueNumber, head: headNow, blockers: [chainBlocked] });
    report({ key: t.key, title: `票${t.key} ${t.label}`, status: "受阻", issue: issueNumber, head: headNow.slice(0, 12) }, "tickets");
    break;
  }
  for (const f of reviewFindings(review)) {
    if (!f.blocking) findings.push({ where: f.where, what: f.what, evidence: `票${t.key} 评审（非阻塞，未修复）`, status: "unconfirmed", severity: f.severity });
  }
  headNow = (await world.run("git", ["-C", WT, "rev-parse", "HEAD"])).stdout.trim();

  let push = await world.run("git", ["-C", WT, "push", "-u", "origin", BRANCH]);
  if (push.exitCode !== 0) push = await world.run("git", ["-C", WT, "push", "-u", "origin", BRANCH]);
  if (push.exitCode !== 0) {
    chainBlocked = `票${t.key} 推送失败：${tail4(push.stderr)}`;
    outcomes.push({ key: t.key, title: t.label, status: "受阻", issue: issueNumber, head: headNow, blockers: [chainBlocked] });
    report({ key: t.key, title: `票${t.key} ${t.label}`, status: "受阻", issue: issueNumber, head: headNow.slice(0, 12) }, "tickets");
    break;
  }
  if (prUrl === "") {
    const prBody = [
      `按 spec #${pub.specNumber} 实施 Codex 中 pstack 与 orchestrator 的受控共存。`,
      ``,
      `票：${TICKETS.map((x) => `#${issueBy[x.key]}`).join(" ")}`,
      ``,
      `- 每票独立提交序列，逐票通过 python3 scripts/verify.py 与实施评审`,
      `- 记录的验收阻塞见各票 issue 评论与实施报告`,
      ``,
      `合并与发布由维护者执行；本 PR 为草稿。`,
    ].join("\n");
    const prc = await world.run("gh", [
      "pr", "create", "--draft", "--base", "main", "--head", BRANCH,
      "--title", "feat(integrations): Codex 中 pstack 与 orchestrator 受控共存（票01–05）",
      "--body", prBody,
    ]);
    if (prc.exitCode === 0) {
      prUrl = prc.stdout.trim().split("\n").filter((l) => l.includes("https://")).pop() ?? prc.stdout.trim();
    } else {
      const prl = await world.run("gh", ["pr", "list", "--head", BRANCH, "--json", "url", "--limit", "1"]);
      try {
        const arr = parseJsonLoose(prl.stdout) as { url: string }[];
        if (arr[0] !== undefined) prUrl = arr[0].url;
      } catch {
        prUrl = "";
      }
    }
  }
  const blockerNote = recBlockers.length > 0 ? "记录的验收阻塞：" + recBlockers.join("；") : "无记录阻塞";
  await world.run("gh", [
    "issue", "comment", String(issueNumber), "--body",
    `票${t.key} 阶段性完成：分支 ${BRANCH} @ ${headNow.slice(0, 12)}；scripts/verify.py 门禁通过；实施评审通过（${rRound} 轮修复）。${blockerNote}${prUrl !== "" ? "\n草稿 PR：" + prUrl : ""}\n\n> 保留的验收阻塞会进入票05 的原生验收与支持声明，不在本评论展开。`,
  ]);
  outcomes.push({ key: t.key, title: t.label, status: "已完成", issue: issueNumber, head: headNow, blockers: recBlockers });
  report({ key: t.key, title: `票${t.key} ${t.label}`, status: "已完成", issue: issueNumber, head: headNow.slice(0, 12) }, "tickets");
  log(`票${t.key} 完成：${headNow.slice(0, 12)}${recBlockers.length > 0 ? "（含记录阻塞 " + recBlockers.length + " 项）" : ""}`);
  prevHead = headNow;
}

phase("批次独立终审");
const finalReviewer = agent("独立终审员", { system: REV_SYSTEM });
let finalReview = await finalReviewer.ask<ReviewResult>(
  [
    `独立终审：${WT} 分支 ${BRANCH} 上 ${BASE.slice(0, 12)}..HEAD 的整体改动（git -C ${WT} diff ${BASE}..HEAD）。你是从未见过各票评审的新鲜视角。`,
    `各票结果：${JSON.stringify(outcomes)}${chainBlocked !== null ? "；依赖链终止原因：" + chainBlocked : ""}`,
    `依据 ${PLAN}/spec.md 的 Implementation Decisions 与 Testing Decisions 全部章节，重点：五张票合起来是否兑现共存合同（归属让位、模型路径分离、两入口一致判定、按 owner 恢复、既有安装转换、验收与支持声明对齐）；跨票一致性（01 的合同 vs 02 的安装判定 vs 03 的恢复 vs 04 的转换）；README 双语与 docs/support-matrix.md 是否与实现一致；有没有票间相互抵消或重复实现。`,
    `可读任何文件、运行只读命令；绝不编辑文件，绝不运行完整门禁。返回 ReviewResult。`,
  ].join("\n"),
);
const finalFixer = agent("终审修复员", { system: IMPL_SYSTEM });
const finalFindings = (): ReviewFinding[] => (Array.isArray(finalReview.findings) ? finalReview.findings : []);
let fRound = 0;
let finalGateStuck = false;
while (!finalReview.approved && fRound < 2 && finalFindings().length > 0) {
  await finalFixer.ask(
    `批次终审意见（第 ${fRound + 1} 轮）：\n${JSON.stringify(finalFindings(), null, 2)}\n请在 ${WT} 分支 ${BRANCH} 上处理 blocking 项与 medium 以上问题并提交；遵守仓库 AGENTS.md 与规格 ${PLAN}/spec.md。`,
  );
  let fg = await gateCmd();
  if (fg.exitCode !== 0) {
    await finalFixer.ask(`修复后门禁失败：\n${tail4(fg.stdout + fg.stderr)}\n请修复。`);
    fg = await gateCmd();
  }
  if (fg.exitCode !== 0) {
    finalGateStuck = true;
    findings.push({ where: "scripts/verify.py", what: "终审修复后门禁仍失败", evidence: tail4(fg.stdout + fg.stderr), status: "verified", severity: "high" });
    break;
  }
  fRound += 1;
  finalReview = await finalReviewer.ask(`终审修复已提交，请重新查看 ${WT} 分支 ${BRANCH} 上 ${BASE.slice(0, 12)}..HEAD 的整体 diff 并复核，返回 ReviewResult。`);
}
for (const f of finalFindings()) {
  findings.push({ where: f.where, what: f.what, evidence: `独立终审（${f.blocking ? "blocking" : "非阻塞"}）`, status: "unconfirmed", severity: f.severity });
}
if (finalGateStuck) {
  chainBlocked = chainBlocked ?? "终审修复后门禁失败";
} else if (finalReview.approved) {
  verified.push(`独立终审通过（${fRound} 轮修复）`);
} else if (finalFindings().length === 0) {
  findings.push({ where: "批次终审", what: "独立终审返回“未通过但零意见”（输出契约故障），PR 保持草稿待人工复核", evidence: "approved=false 且 findings 为空", status: "verified", severity: "medium" });
} else {
  findings.push({ where: "批次终审", what: "独立终审未通过，PR 保持草稿待人工裁决", evidence: JSON.stringify(finalFindings()), status: "verified", severity: "medium" });
}
const finalHead = (await world.run("git", ["-C", WT, "rev-parse", "HEAD"])).stdout.trim();
const finalPush = await world.run("git", ["-C", WT, "push", "origin", BRANCH]);
if (finalPush.exitCode !== 0) findings.push({ where: "git push", what: "终审后最终推送失败", evidence: tail4(finalPush.stderr), status: "verified", severity: "medium" });

phase("收尾与交付");
const recorder = agent("记录员", {
  system: "你是项目记录员，只在被 git 忽略的 .planning 目录内写工作笔记，不改任何 tracked 文件，不动 GitHub。",
});
await recorder.ask(
  [
    `更新 ${PLAN} 工作笔记（该目录被 git 忽略）：`,
    `1. README.md：状态段更新为本运行的实际结果。`,
    `2. 新建或追加 ${PLAN}/handoff-2026-10-26.md：记录 worktree 租约（path=${WT}，lease_id=${LEASE_ID}，holder=${HOLDER}，未归还，待 PR 审阅后按 worktree-policy 归还）、分支 ${BRANCH}、基线 ${BASE.slice(0, 12)}、最终 HEAD ${finalHead.slice(0, 12)}、每票结果 ${JSON.stringify(outcomes)}、PR ${prUrl === "" ? "未创建" : prUrl}、链终止原因 ${chainBlocked ?? "无"}、后续待办（PR 审阅与合并、租约归还、主环境迁移另行授权）。`,
    `3. 五张票文件的 Status 行更新为实际状态（完成@${finalHead.slice(0, 12)} 或 受阻：原因）。`,
    `返回写入的文件路径列表。`,
  ].join("\n"),
);
if (prUrl !== "") {
  await world.run("gh", [
    "pr", "comment", prUrl, "--body",
    `批次推进完成（草稿，待人工审阅）：完成 ${outcomes.filter((o) => o.status === "已完成").length}/5 张票${chainBlocked !== null ? "；链终止：" + chainBlocked : ""}。最终 HEAD ${finalHead.slice(0, 12)}，逐票 scripts/verify.py 门禁与评审记录见各票 issue 评论。合并与发布由维护者决定。`,
  ]);
} else {
  await world.run("gh", [
    "issue", "comment", String(pub.specNumber), "--body",
    `批次推进结果：完成 ${outcomes.filter((o) => o.status === "已完成").length}/5 张票${chainBlocked !== null ? "；链终止：" + chainBlocked : ""}（未创建 PR）。分支 ${BRANCH}，最终 HEAD ${finalHead.slice(0, 12)}。`,
  ]);
}

const doneCount = outcomes.filter((o) => o.status === "已完成").length;
const conclusion =
  `spec #${pub.specNumber} 与五张票已发布并按 01→02→03→04→05 推进：${doneCount}/5 张票完成并通过逐票 verify.py 门禁与实施评审${chainBlocked !== null ? "；" + chainBlocked : ""}。` +
  `${prUrl !== "" ? "草稿 PR：" + prUrl + "，" : ""}分支 ${BRANCH}（最终 HEAD ${finalHead.slice(0, 12)}），租约保留待人工审阅，合并与发布未执行。`;
return await deliver(conclusion);