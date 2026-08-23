# 受控演化契约

Excalidraw Diagram 可以从真实执行中学习，但历史数据、observer、hook 和后台模型都没有修改 live skill 的权限。

## 候选生命周期

```text
observed -> corroborated -> regression_ready -> isolated_candidate
         -> paired_reviewed -> human_approved -> promoted
         -> rejected | expired
```

- 一个候选只改变一个可证伪机制；混合问题拆成独立轮次。
- 项目范围是默认值。跨项目通用规则需要至少两个项目的可比证据。
- Candidate 写入隔离分支或副本；不能直接修改当前安装入口，也不能通过 symlink/path traversal 逃逸。
- 先增加回归，再修改 instruction、reference、template 或 deterministic script。

## 评测与 promotion

Promotion 必须同时通过：

1. baseline 与 candidate 使用相同 prompt、skill tree 边界、时限和工具权限；
2. 相关语义、style、scene hygiene、overlap、render/export 和 artifact receipt 检查通过；
3. 具名视觉 reviewer 检查冻结产物，不把 `pending` 或 `skipped` 当 pass；
4. 至少 3 个独立 paired judges，以奇数多数偏好 candidate，并反转 A/B 顺序；
5. 没有新的安全、权限、隐私、来源或损坏交付回归；
6. 人类明确批准 exact diff。

绝对分数、成功率、健康趋势、出现次数和“用户没有反对”只用于排查优先级，不能单独 promotion。

## 运行控制

- 采集有样本上限、冷却、重入保护和明确覆盖范围；解析失败保留源证据，不静默丢弃。
- 原始运行保留在本地受控位置；公开结果只含允许的 digest、聚合、脱敏片段和 reproducible fixtures。
- Promotion 和 rollback 都通过显式仓库变更完成，并保留 decision receipt；不在 skill 内复制整份版本快照。
- 依赖升级与 instruction 变更使用同一 gate。结构检查通过不代表渲染、字体或视觉行为通过。

## 必须回归

1. 单个普通失败不能 promotion；一个严重损坏交付或安全失败可形成候选但仍需完整 gate。
2. 缺少具名视觉复核、三轮审核或 deterministic gate 时不能标记 `complete`。
3. Reference fixture 不能进入模型效果统计。
4. History/observer 不能写 live `SKILL.md`、references、templates、项目规则、全局规则或 memory。
5. Candidate 多数通过但出现安全、权限、隐私或来源回归时必须拒绝。
6. Exact diff 未获人类批准时不得 promotion。
