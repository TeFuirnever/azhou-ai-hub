# Azhou Skill Standard

本准则是 Azhou AI Hub 所有 skill 的项目级权威。它约束新 skill、上游改造、依赖、交互、证据、评测、演化和收尾；各 skill 只在自己的 `SKILL.md` 与 references 中补充领域行为，不复制第二份项目准则。

## 1. 当前事实与授权

- 代码、锁文件、机器配置和真实运行结果是当前行为；spec、计划和历史对话表达目标或证据，不能伪装成已实现能力。
- 用户要求实现时修改最小必要范围。删除、发布、部署、全局 agent 配置、归属不明 memory 和无关跨仓写入保持 checkpoint。
- 上游改造必须保留来源、许可证和能力基线。非冲突能力默认保留；替代或移除能力必须有兼容清单、回归和理由。
- 工作树已有修改先判定归属。模糊重叠暂停该项，独立工作继续。

## 2. 包结构与运行边界

每个 skill 独立安装在 `skills/<canonical-name>/`，只带运行时需要的内容。

“独立安装”表示完整复制单个 canonical package 后，harness 能单独发现并加载它；不表示 package 必须内置所有外部运行时。Package 不得依赖兄弟 skill 目录，但可以声明 Python、Node、浏览器或显式 repository checkout 等外部依赖。此类依赖必须在 package-local setup 中写明最低版本、定位方式、失败边界和验证命令；缺失时 fail closed，不能扫描无关目录或静默复制第二份权威实现。

| Surface | 何时需要 | 约束 |
|---|---|---|
| `SKILL.md` | 必须 | 入口、触发、顺序、边界；保持可扫描 |
| `references/` | 复杂规则、setup、provenance、schema 或深度说明 | 按需读取，不把全部细节塞回入口 |
| `scripts/` | 可机械验证、转换或重复执行的动作 | 优先标准库、确定性、`--help`、明确退出码 |
| `assets/` / `templates/` | 运行时 schema、素材或可复用起点 | 保留来源、版本和许可证；不放评测答案 |
| `references/setup.md` | 有外部依赖 | 写最低版本、锁定来源、dry-run、安装、验证、系统修改边界 |
| `references/brand-layer.md` | 有交互式多阶段流程 | 固定品牌锚点、状态映射、收据与 Unicode 降级 |
| `references/history-evolution.md` | 从历史运行持续改进 | 定义采集、隐私、失败分类和 promotion gate |

开发期 prompts、expected outputs、fixtures、judge records、真实运行聚合和 benchmark runner 统一放在仓库级 `benchmarks/<skill>/`。运行时包不包含 `benchmarks/`、`agents/openai.yaml` 或其他模型专用身份；Codex、Claude、zcode 和其他 harness 共享同一个 neutral core。

## 3. 阿舟交互层

品牌属于仓库，能力属于 skill。每个交互式 skill 使用自己的英文 canonical name，并通过克制的阿舟锚点形成同族体验：

1. 启动时输出一次 `🦊 阿舟 · <Skill> 启动`，携带 mode 与 scope。
2. 多阶段 skill 将顺序、固定前缀、字段和分隔符写成协议；脆弱流程提供标准库 validator 与正反回归，不让 agent 自由改写阶段名。
3. 成功、失败、跳过和 hold 分开表达；成功锚点只能在全部声明检查完成后发送，并且是最后阶段事件。
4. checkpoint 只暂停缺少授权的动作，其他独立步骤继续。
5. 结束时输出稳定收据：schema、status、current truth、artifacts/changes、verification、holds、next action、learning signal。

Emoji 只存在于展示层。JSON key、schema enum、digest、路径、命令、测试名和原始证据保持稳定纯文本；不支持 Unicode 的 host 可移除 emoji，不能改机器字段和值。

## 4. 证据与评测

- 真实运行优先于自评。记录 runtime、harness/model、skill tree digest、输入或 case digest、工具权限、attempt、产物 digest、自动检查和具名人工检查。
- 比较不同模型、harness 或 skill revision 时冻结 prompt、runtime package、时限和工具权限；reference fixture 只证明 verifier 接线，不算模型效果。
- 原始对话、用户路径、身份、URL、token、私有素材和未脱敏产物留在 Git 外。仓库只提交合成 case、聚合统计、失败机制、脱敏 receipt、paired 决策和覆盖限制。
- 自动 gate 负责能机械证明的事实；语义、视觉、权限或产品判断由具名 reviewer 负责。收据不能把 `skipped`、`pending` 或缺失证据升级成 pass。

## 5. 受控演化

历史数据没有修改 live skill 的权限。每次演化只处理一个可证伪机制：

```text
observed -> corroborated -> regression_ready -> isolated_candidate
         -> paired_reviewed -> human_approved -> promoted | rejected
```

- 普通失败至少在两个独立运行中重复；权限、删除、安全、隐私或损坏交付类严重失败可由一次证据形成候选。
- 修改前增加回归 case。baseline 与 candidate 使用同一输入和权限，candidate 保持隔离。
- promotion 需要确定性检查通过、无安全回归、至少 3 个独立 paired judges 的奇数多数、反转 A/B 顺序，以及人类对 exact diff 的明确批准。
- 后台 observer、hook、历史采集器和健康趋势都不能静默修改 live skill。失败批次保留；成功只归档已验证批次。

## 6. 收尾与完成定义

Skill 变更完成前必须：

1. 读回修改后的入口、references、setup、provenance、项目文档和 agent 规则，消除第二权威。
2. 运行相关脚本测试、benchmark integrity、链接/JSON 解析、skill validator 和 `git diff --check`。
3. 对新增或变化行为记录 current truth、验证命令、限制和一个具体 next action。
4. 明确任务结束时运行 `repo-pedant`，同步 docs、项目规则和已证明绑定当前项目的 memory；推测结束只提醒，不写入。
5. `repo-pedant` closeout 为每个受影响项目记录 memory inventory：绑定路径、已检查但未发现的具体 surface，或带原因的 hold；`unresolved` 不能完成。

未通过的外部或既存限制可以成为具名 hold；本次修改制造的失败不能包装成完成。
