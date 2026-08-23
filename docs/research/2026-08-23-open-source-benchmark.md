# Azhou AI Hub 开源项目基准研究

> 研究日期：2026-08-23
>
> 范围：`alchaincyf/alchaincyf`、`affaan-m/ECC`、`mattpocock/skills`，以及 GitHub 官方仓库治理文档。
> 说明：下文把“观察”与“建议”分开。观察只描述公开仓库中可直接核验的事实；建议是针对 Azhou AI Hub 的取舍，不把参考项目做法自动视为最佳实践。

## 结论

Azhou AI Hub 不应复制任一参考仓库，而应组合三种优势：

1. 用 `alchaincyf/alchaincyf` 的个人品牌叙事，让访客在首屏知道“阿舟是谁、相信什么、正在做什么”；其 README 依次呈现身份、可信成果、当前项目、理念和联系入口，是清晰的品牌首页结构。[来源：alchaincyf README](https://github.com/alchaincyf/alchaincyf/blob/main/README.md)
2. 用 ECC 的工程可信度，把安装边界、跨 harness 支持状态、贡献流程、安全政策、CI 和发布链做成可核验合同；ECC 公开列出官方分发渠道、单路径安装原则、能力清单和支持边界。[来源：ECC README](https://github.com/affaan-m/ECC/blob/main/README.md)
3. 用 Matt Pocock Skills 的产品克制：一句鲜明定位、小而可组合、模型中立、30 秒安装、可编辑与托管安装二选一；仓库结构聚焦 `skills/`、`docs/`、`scripts/`、发布元数据和少量根文件。[来源：mattpocock/skills README](https://github.com/mattpocock/skills/blob/main/README.md) [来源：仓库根目录](https://github.com/mattpocock/skills/tree/main)

“业界最强”应落成可验收标准，而不是宣传词：首次安装路径可复制；每个 skill 独立安装且有演示；PR 必过同一套本地/CI gate；社区健康文件齐全；漏洞有私密报告入口；版本、变更与 Release 对得上；默认分支受保护；每个重要主张能回到测试、benchmark 或来源。

## 一、观察：三个项目分别强在哪里

### 1. alchaincyf/alchaincyf：品牌锚点强，工程模式不宜整体照搬

**观察**

- README 开头用一句反差身份建立记忆点，紧接可量化成果；随后只讲“我在做的事”“我相信的事”“找到我”，没有先用技术目录消耗访客注意力。[来源：README](https://github.com/alchaincyf/alchaincyf/blob/main/README.md)
- 仓库本身极简，核心是 `README.md` 和一个定时更新统计的 workflow。[来源：仓库根目录](https://github.com/alchaincyf/alchaincyf) [来源：update-stats workflow](https://github.com/alchaincyf/alchaincyf/blob/main/.github/workflows/update-stats.yml)
- 该 workflow 每小时运行并拥有 `contents: write`，公开提交历史中因此出现大量重复的 `chore: refresh stats badges` 提交。[来源：workflow](https://github.com/alchaincyf/alchaincyf/blob/main/.github/workflows/update-stats.yml) [来源：commit history](https://github.com/alchaincyf/alchaincyf/commits/main/)

**给 Azhou 的建议**

- 采用其“人设 → 作品 → 信念 → 入口”叙事法，但 README 的主角应是 Azhou AI Hub 的用户价值，阿舟品牌是可信来源，不应压过安装与使用。
- 不复制写入默认分支的高频统计自动化。动态数据若必须保留，使用不改 Git 的 badge 服务，或低频生成 PR；主分支历史只记录有意义的产品变化。

### 2. affaan-m/ECC：治理、安全和交付链最完整

**观察**

- README 先给出完整工作循环，再说明为何一次安装能替代每次提示；同时明确不同 harness 的能力并不等价，避免“全平台完全支持”的模糊承诺。[来源：ECC README](https://github.com/affaan-m/ECC/blob/main/README.md)
- 仓库根目录同时提供 `CODE_OF_CONDUCT.md`、`CONTRIBUTING.md`、`SECURITY.md`、`CHANGELOG.md`、许可证、多语言 README 和大量开发/发布入口；`.github/` 包含 issue template、PR template、CODEOWNERS、Dependabot、release notes 配置和工作流。[来源：仓库根目录](https://github.com/affaan-m/ECC) [来源：.github 目录](https://github.com/affaan-m/ECC/tree/main/.github)
- CONTRIBUTING 不只写礼仪，还给出 fork、分支、测试、PR 标题、PR 内容和各类贡献的验收清单；提交示例采用 `feat(scope): ...`、`fix(scope): ...`、`docs: ...`。[来源：ECC CONTRIBUTING](https://github.com/affaan-m/ECC/blob/main/CONTRIBUTING.md)
- SECURITY 明确支持版本、私密报告入口、响应时限、范围、非官方分发面和供应链规则；这比一句“请发邮件”更可执行。[来源：ECC SECURITY](https://github.com/affaan-m/ECC/blob/main/SECURITY.md)
- CI 使用最小 `contents: read` 权限、跨操作系统/Node/包管理器矩阵、Python lint/type/test、安全审计，并把第三方 Action 固定到完整 commit SHA。[来源：ECC CI](https://github.com/affaan-m/ECC/blob/main/.github/workflows/ci.yml)
- Dependabot 同时覆盖 npm、GitHub Actions、pip 和 Cargo，分离安全更新与 minor/patch 分组。[来源：ECC dependabot.yml](https://github.com/affaan-m/ECC/blob/main/.github/dependabot.yml)
- commit history 中常见 `docs(scope)`、`fix(scope)`、`test(scope)`、`feat(scope)` 的连续小步和 PR merge 记录，能从文档合同跟到实现与测试。[来源：ECC commits](https://github.com/affaan-m/ECC/commits/main/)

**给 Azhou 的建议**

- 复用“公开合同”思想：支持矩阵、安装边界、贡献 gate、安全边界、官方分发渠道、版本状态都写实。
- 不复制 ECC 的超大运行面和 vendor-specific 副本。Azhou 的项目准则要求中立 core、skill 独立安装，且禁止 `agents/openai.yaml`；这一边界应继续以本仓库的 [AGENTS.md](../../AGENTS.md) 和 [skill standard](../skill-standard.md) 为权威。

### 3. mattpocock/skills：定位、组合性和变更管理最克制

**观察**

- README 用 “Skills For Real Engineers” 定位，立即说明不是接管流程的大框架，而是“小、易改、可组合、适用于任何模型”的技能集合。[来源：README](https://github.com/mattpocock/skills/blob/main/README.md)
- 安装部分明确两种不同哲学：托管只读 bundle 与复制到项目后自行修改，并警告不要重复安装；这是很好的安装决策界面。[来源：README 安装部分](https://github.com/mattpocock/skills/blob/main/README.md#installation-30-second-setup)
- 根目录把运行时能力放在 `skills/`，把说明放在 `docs/`，把自动化放在 `scripts/`，并使用 `.changeset/`、`CHANGELOG.md` 和单一 release workflow 管理版本。[来源：仓库根目录](https://github.com/mattpocock/skills/tree/main) [来源：Changesets 目录](https://github.com/mattpocock/skills/tree/main/.changeset) [来源：release workflow](https://github.com/mattpocock/skills/blob/main/.github/workflows/release.yml)
- 近期提交把行为修改、changeset 和 PR merge 分开记录；变更标题通常能直接定位 skill 或问题。[来源：commit history](https://github.com/mattpocock/skills/commits/main/)

**给 Azhou 的建议**

- README 采用“短定位 + 立即安装 + skill catalog + 为什么可信”的顺序；深层理念、benchmark 方法和演化合同链接到 docs。
- 可借鉴 changeset 的“每个用户可见变化都有机器可读变更记录”，但 Azhou 当前不是 npm monorepo，不必为了形式引入 Node 发布依赖。可以先用仓库内 `changes/` YAML/Markdown 或 Conventional Commit + 自动 Release Notes 达成同一目的。
- 不照抄其 workflow 中 `actions/checkout@v4`、`actions/setup-node@v4` 和 `changesets/action@v1` 的 tag 引用。GitHub 官方说明：完整 commit SHA 是第三方 Action 唯一不可变引用方式。[来源：GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions)

## 二、建议：Azhou AI Hub 的目标产品面

### README / 产品叙事

建议根 README 固定为以下信息顺序：

1. **品牌首屏**：Azhou AI Hub 名称、12—20 字价值主张、阿舟视觉锚点、CI/License/Release 三个可信 badge。
2. **30 秒开始**：只放一个推荐安装路径；其余方法折叠到安装文档，并明确不同安装方式不可叠加。该决策界面直接借鉴 Matt Pocock Skills 与 ECC 的单路径警告。[来源：Matt 安装说明](https://github.com/mattpocock/skills/blob/main/README.md#installation-30-second-setup) [来源：ECC 安装说明](https://github.com/affaan-m/ECC/blob/main/README.md#install-ecc)
3. **Skill catalog**：每行只展示名称、一个真实任务、支持 harness、版本、验证状态；点击进入 skill 自己的 README/SKILL。
4. **为什么可信**：用 3—5 个可点击证据回答“真实执行、确定性校验、跨 harness、受控演化、安全边界”。
5. **参与与路线**：贡献入口、Discussion、公开 roadmap、Security、License；不要把长贡献教程塞回主 README。

README 中所有数字应来自可复现脚本或 release snapshot；无法自动校验的宣传数字不进入 badge。GitHub 允许上传独立社交预览图，官方建议 1280×640 以获得最佳显示，适合固定阿舟品牌首图。[来源：GitHub social preview](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)

### 仓库结构

建议保持现有运行时/开发时分层，并补齐社区与发布层：

```text
azhou-ai-hub/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── workflows/
│   ├── CODEOWNERS
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml
│   └── release.yml
├── skills/<canonical-name>/    # 可独立安装的运行时包
├── benchmarks/<skill>/         # 开发评测，不进入运行时包
├── docs/                       # 标准、架构、支持矩阵、发布说明
├── evidence/                   # 脱敏证据合同与公开快照
├── tests/                      # 仓库级确定性验证
├── AGENTS.md                   # 项目权威规则
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
└── README.md
```

每个 skill 保持自己的 `SKILL.md`、`references/`、`scripts/`、`assets/` 和 setup；根仓库只提供共同标准、CI、社区和 release。该结构结合 Matt 的运行时聚焦布局与 ECC 的治理层，同时服从本项目 [skill standard](../skill-standard.md)。[来源：Matt 根目录](https://github.com/mattpocock/skills/tree/main) [来源：ECC 根目录](https://github.com/affaan-m/ECC)

### 治理与社区文件

首个公开 release 前补齐：

- `CODE_OF_CONDUCT.md`：采用 Contributor Covenant，并写明执行联系人。
- `CONTRIBUTING.md`：保留 fork/branch/test/PR 最短路径；增加“新增 skill”“修复 skill”“新增 benchmark”“修改项目标准”四类清单。
- `.github/ISSUE_TEMPLATE/bug.yml`：复现输入、harness/model、skill version/commit、实际结果、期望结果、脱敏日志。
- `.github/ISSUE_TEMPLATE/skill-request.yml`：真实任务、现有替代、成功证据、范围外边界。
- `.github/PULL_REQUEST_TEMPLATE.md`：summary、risk、tests、benchmark、docs、security、breaking change、evidence。
- `SECURITY.md`：支持版本、私密报告路径、响应目标、范围、供应链规则、官方安装面。
- `.github/CODEOWNERS`：先覆盖 `skills/`、`benchmarks/`、`.github/workflows/`、`docs/skill-standard.md`；人员不足时仍可从单一 maintainer 起步。

GitHub 的 Community Profile 会检查 README、CODE_OF_CONDUCT、LICENSE、CONTRIBUTING 等推荐文件；Issue Forms 必须放在 `.github/ISSUE_TEMPLATE` 且使用有效 frontmatter。[来源：GitHub community profiles](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories) ECC 提供了这些文件及 CODEOWNERS/PR template/Dependabot 的完整公开实例。[来源：ECC 根目录](https://github.com/affaan-m/ECC) [来源：ECC .github](https://github.com/affaan-m/ECC/tree/main/.github)

## 三、建议：CI、安全与发布自动化

### CI 最小强门

新增 `.github/workflows/ci.yml`，在 `pull_request` 和 `push main` 上运行本仓库权威验证：

```text
unit-tests
repo-pedant-benchmark
excalidraw-model-floor
skill-package-validation
json/yaml/link checks
git diff --check
```

具体策略：

- 默认 `permissions: contents: read`；只有发布 job 单独提升权限。GitHub 官方建议将 `GITHUB_TOKEN` 默认权限设为只读，再按 job 增加。[来源：GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use#use-secrets-for-sensitive-information)
- 第三方 Actions 固定到完整 SHA，并在注释中保留版本号；ECC CI 是可核验示例。[来源：GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use#using-third-party-actions) [来源：ECC CI](https://github.com/affaan-m/ECC/blob/main/.github/workflows/ci.yml)
- `actions/checkout` 使用 `persist-credentials: false`，除非该 job 必须写 Git。
- 为每个 job 设置 `timeout-minutes` 和 concurrency cancel，避免重复或悬挂运行；ECC CI 同时使用两者。[来源：ECC CI](https://github.com/affaan-m/ECC/blob/main/.github/workflows/ci.yml)
- 不使用 `pull_request_target` 运行不可信 PR 代码。GitHub 明确警告该触发器与不可信 checkout 组合会暴露写权限或 secrets。[来源：GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use#mitigating-the-risks-of-untrusted-code-checkout)

### 依赖与安全

- 配置 Dependabot 覆盖 `github-actions`、Python，以及 Excalidraw 实际依赖的 Node 包；安全更新单独处理，minor/patch 合并分组以降低 PR 噪声。[来源：GitHub repository security quickstart](https://docs.github.com/en/code-security/getting-started/quickstart-for-securing-your-repository) [来源：ECC dependabot.yml](https://github.com/affaan-m/ECC/blob/main/.github/dependabot.yml)
- 开启 dependency graph、Dependabot alerts/security updates、CodeQL default setup、secret scanning 与 push protection；GitHub 官方安全快速入门列出了这些仓库级开关及适用范围。[来源：GitHub repository security quickstart](https://docs.github.com/en/code-security/getting-started/quickstart-for-securing-your-repository)
- 开启 private vulnerability reporting，并确保维护者订阅 Security alerts；GitHub 提供结构化私密报告表单，避免漏洞进入公开 issue。[来源：GitHub private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository)
- `.github/workflows/` 由 CODEOWNERS 保护。GitHub 官方将 CODEOWNERS 列为监控 workflow 变更的防护手段。[来源：GitHub Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use#using-codeowners-to-monitor-changes)

### Release

建议采用仓库级 SemVer：`vMAJOR.MINOR.PATCH` 表示整个 hub 的可安装快照；每个 release notes 再列各 skill 的变更与兼容状态。只有 skill 内容或安装合同发生用户可见变化才发版本，不因 benchmark 结果重跑而发版。

发布流程：

1. 合并 release PR：同步 `CHANGELOG.md`、skill catalog、版本/支持矩阵和所有验证证据。
2. 创建签名 tag 与 draft GitHub Release；先附上安装说明、breaking changes、各 skill 状态和校验摘要。
3. CI 从 tag 重跑完整 gate；通过后发布 Release。
4. `.github/release.yml` 用 PR labels 分类生成 notes，再由 maintainer 人工检查。GitHub 自动 release notes 能生成 merged PR、贡献者和 full changelog，并支持按 label 分类/排除。[来源：GitHub automated release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes)
5. 稳定后启用 immutable releases；GitHub 建议先建 draft、附齐资产，再发布不可变 Release。[来源：GitHub release management](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)

## 四、建议：GitHub 远端设置清单

> 当前公开页面没有提供 Azhou AI Hub 管理后台状态，本研究不声称下列设置已经开启。实施者必须在 GitHub `Settings` 中逐项核验，并保存设置截图或 `gh api` 导出作为验收证据。

### Repository metadata

- Description：一句用户结果，不写内部实现。
- Website：有稳定文档站再填；没有就留空，不用临时页面。
- Topics：建议 `agent-skills`、`ai-agents`、`codex`、`claude-code`、`excalidraw`、`developer-tools`、`open-source`；GitHub 说明 topics 用于发现与分类，最多 20 个且只允许小写、数字和连字符。[来源：GitHub topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
- Social preview：上传 1280×640 的阿舟品牌图，并检查深浅背景。[来源：GitHub social preview](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)
- 开启 Issues；只有维护者能持续回应时再开启 Discussions。Docs 继续版本化放在仓库内，不用 Wiki 分叉出第二套权威文档。

### Pull requests and history

- 只启用 **Squash merge**，默认提交标题使用 PR title；删除已合并 head branch。
- 为 `main` 创建 active ruleset：禁止删除、禁止 force push、要求 PR、至少 1 个 approval、最新 push 需由其他人批准、所有对话解决、全部 required checks 通过、要求线性历史。
- 当稳定的 maintainer/bot 签名链验证完成后，再开启 required signed commits；GitHub 的 squash/rebase 与签名存在限制，应先在真实 fork PR 上演练。[来源：GitHub ruleset rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) [来源：GitHub merge methods](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github)
- Ruleset bypass 只给仓库管理员的紧急路径，不给普通 automation；GitHub rulesets 可同时控制分支、tag、签名、PR、status checks 和 force push。[来源：GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)

### Actions and security

- Actions workflow 权限默认只读；关闭 workflow 创建/批准 PR 的能力，除非未来 release bot 有明确需求。
- 只允许 GitHub 官方、已验证创建者或显式 allowlist 的 Actions；所有引用固定 SHA。
- 启用前述 dependency、code scanning、secret protection、private vulnerability reporting。
- tag ruleset 保护 `v*`：限制创建/更新/删除；release 只由受信 maintainer 或 release workflow 产生。

## 五、建议：commit history 合同

### 主分支格式

```text
feat(repo-pedant): add memory inventory proof
fix(excalidraw): preserve editable bindings
docs(readme): clarify one-path installation
test(repo-pedant): cover closeout trigger boundary
ci: pin actions and require benchmark gates
chore(release): prepare v0.1.0
```

规则：

- 一个 commit 只回答一个“为什么”；代码、对应测试和必要文档可以同 commit，多个无关 skill 不混在一起。
- 标题使用 `type(scope): imperative summary`；scope 优先用 canonical skill 名，仓库级变化用 `repo`、`docs`、`ci`、`release`。
- commit body 写动机、风险、证据；不复述 diff。
- PR 可保留探索性 commits，但进入 `main` 时 squash 成一个可回滚单位。GitHub 官方指出 squash 能把工作分支提交合成一个 commit，形成更清晰历史；同时也列出了作者与原始 SHA 信息丢失等代价。[来源：GitHub merge methods](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github)
- 发布后的默认分支不改写历史；规则集应阻止 force push。GitHub 说明 force push 可能移除他人依赖的 commits，导致冲突或损坏 PR。[来源：GitHub ruleset rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#block-force-pushes)
- 维护者签名 commits/tags。GitHub 支持 GPG、SSH、S/MIME commit 签名，并展示 Verified 状态。[来源：GitHub commit signing](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits)
- bot 不直接制造统计型主分支 commits；需要变更仓库内容的 automation 走可审查 PR。

### 当前开源化改造的建议提交序列

若这些变更尚未公开推送，按可审查边界组织为：

1. `docs(readme): establish Azhou AI Hub product story`
2. `docs(governance): add contribution and security contracts`
3. `ci: add deterministic skill and benchmark gates`
4. `chore(github): add issue forms, code owners, dependabot, and release notes`
5. `chore(release): prepare v0.1.0`

如果现有 commits 已经公开，不通过 rebase/force-push 美化历史；从下一 PR 开始执行新合同。

## 六、实施顺序与验收

### P0：公开前必须完成

1. README 首屏、一个推荐安装路径、skill catalog、真实验证 badge。
2. CODE_OF_CONDUCT、SECURITY、Issue Forms、PR Template、CODEOWNERS。
3. PR CI 运行本项目四条权威验证命令，并设为 required checks。
4. `main` ruleset、squash merge、force-push/delete 禁止。
5. v0.1.0 draft Release、CHANGELOG、release notes 分类和官方分发说明。

### P1：公开后第一个迭代

1. Dependabot、CodeQL、secret scanning/push protection、private vulnerability reporting。
2. 每个 skill 增加 60 秒 demo、输入/输出样例、支持矩阵和独立安装 smoke test。
3. 建立公开 roadmap 与 `good first issue`，记录维护响应预期。
4. 加入 release provenance/SBOM 仅在实际分发 artifact 出现后；不要为尚不存在的包制造供应链仪式。

### 验收定义

- GitHub Community Profile 推荐项全部通过。[来源：GitHub community profiles](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/about-community-profiles-for-public-repositories)
- fork PR 无写权限和 secrets，能跑完 required checks。
- failing unit/benchmark/link/diff 任一项都阻止 merge。
- 新用户从 README 到成功安装只需一个选择，不会重复安装同名 skill。
- SECURITY 的私密报告入口可用，维护者已订阅通知。
- Release tag、CHANGELOG、README catalog、skill 内容和验证证据指向同一 commit。
- 默认分支 history 无高频统计噪声；每个 squash commit 能独立解释、验证和回滚。

这套目标不是“文件最多”，而是“品牌可记忆、安装低摩擦、行为可证明、贡献可执行、发布可追溯、安全边界诚实”。

## 七、第二轮复查：从“文件齐全”转向“能力可见”

复查基线：Azhou AI Hub `main@7c6cbdb`。这一轮重新读取三个参考仓当前公开页面，并通过 GitHub API 核对本仓远端设置；不再把已经完成的 P0 重复列成待办。[来源：Azhou AI Hub](https://github.com/TeFuirnever/azhou-ai-hub) [来源：alchaincyf](https://github.com/alchaincyf/alchaincyf) [来源：ECC](https://github.com/affaan-m/ECC) [来源：Matt Pocock Skills](https://github.com/mattpocock/skills)

| 面向 | 当前结论 | 状态 |
|---|---|---|
| 首屏与品牌 | 中英文 README 已共用 1280×640 阿舟 hero；本轮不再重复新增装饰图。 | `complete` |
| 社区治理 | Community Profile 100%；README、License、Code of Conduct、Contributing、PR template 已被 GitHub 识别。 | `complete` |
| 合并与历史 | 只允许 squash merge，合并后自动删分支；`main` 与 `v*` 均有 active ruleset。 | `complete` |
| Actions 与安全 | Actions 默认只读、禁止 workflow 批准 PR、只允许选定 Actions、强制 SHA pinning；CodeQL、Dependabot security updates、secret scanning/push protection、private vulnerability reporting 已启用。 | `complete` |
| 能力展示 | 参考项目不只给安装，还让访客快速理解产品作用；本轮增加两个可复制的 60 秒输入/输出 demo，并明确 reference fixture 不是模型成绩。 | `complete` |
| 外部可信度 | OpenSSF Scorecard 当前为 6.9；依赖更新、权限、依赖 pinning、SAST、CI 等项通过，项目年龄、独立 code review 和尚未发布 Release 仍拉低分数。 | `partial` |
| 首次交付 | `v0.1.0` 仍是 draft，目标 commit 早于当前 `main`；公开安装 smoke receipt 与跨 harness 真实 receipt 尚未闭环。 | `hold` |
| Social Preview | Git 版本化 1280×640 资产与 README 展示已完成；GitHub 设置页媒体对象/CDN 的上传成功仍需独立平台回执，不能用 README HTTP 200 代替。 | `hold` |

远端核对命令：

```bash
gh api repos/TeFuirnever/azhou-ai-hub
gh api repos/TeFuirnever/azhou-ai-hub/rulesets
gh api repos/TeFuirnever/azhou-ai-hub/actions/permissions
gh api repos/TeFuirnever/azhou-ai-hub/actions/permissions/workflow
gh api repos/TeFuirnever/azhou-ai-hub/community/profile
gh api repos/TeFuirnever/azhou-ai-hub/private-vulnerability-reporting
gh release view v0.1.0 --json isDraft,targetCommitish,url
curl -fsSL https://api.securityscorecards.dev/projects/github.com/TeFuirnever/azhou-ai-hub
```

下一轮只保留三个真实缺口：从公开 GitHub 源做两个 skill 的独立安装 smoke；采集不夸大的跨 harness receipt；在发布授权后把 draft Release、tag、CHANGELOG 与同一 commit 对齐。继续不复制 alchaincyf 的统计型 commits、ECC 的 vendor-specific 运行副本或 Matt 的 npm-specific Changesets 基础设施。
