# 受控演化契约（Arch Doc）

Arch Doc 从执行证据中学习，但历史数据与后台 hook 对 live skill 没有修改权限。本契约遵循仓库 `docs/skill-standard.md` §5 的演化管线：`observed → corroborated → regression_ready → isolated_candidate → paired_reviewed → human_approved → promoted | rejected`。

## 证据单元

每条观察是一条原子、项目内记录，必含字段：

- `signal_id`、`schema_version`、`observed_at`、`project_id`；
- `runtime`（harness/model）、`session_digest`、`source`（上游文档/代码/用户反馈）、`provenance`；
- `category`（事实错误 / 图纪律 / 判据不可判定 / 路由误触发 / 措辞 / 流程缺失）、`mechanism`、`severity`、`outcome`；
- 脱敏证据引用或摘要（原文引用可含上游句，但用户路径、身份、token 不入 Git）；
- 用户反馈显式记录：`accepted` / `corrected` / `rejected` / `none`。

## 失败分类与升级

- 普通失败（措辞、顺序、覆盖缺口）：至少两个独立运行中重复才成候选。
- 严重失败（契约被篡改、模板被改、假 ✅、跨租户泄露式错误）：一次证据即可成候选。
- 同一问题跨 3+ 轮重复：升级为结构性议题，报告用户而非继续打补丁。

## 候选与晋升 gate

1. 修改前先加回归 case 进 `benchmarks/arch-doc/`（golden 输入 + verify_doc 断言 + 结构抽查）。
2. baseline 与 candidate 用同一输入与权限，candidate 在隔离分支/副本上做。
3. promotion 要求：确定性检查全过、零安全回归、≥3 个独立 paired judges 奇数多数、A/B 顺序反转重跑、人类对 exact diff 明确批准。
4. 后台 observer / hook / 历史采集器不得静默改 live skill；失败批次保留，成功只归档已验证批次。

## 收尾

每次演化在 `evidence/` 留 receipt（schema、status、current truth、验证命令、限制、next action），并在 ARCH 文档或本 skill 的变更记录入账。
