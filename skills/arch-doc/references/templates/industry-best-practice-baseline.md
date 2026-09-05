# MCC 文档模板业界基线

> **用途**：MCC PRD、产品软件实现架构设计说明书、功能详细设计说明书与 Test/Eval Report/Receipt 的精简、可维护参考。来源核对：2026-09-01。
>
> **边界**：本文件映射公开信息职责和实践，**不**是任何标准的逐条实现，也不表示 MCC、其文档或使用者取得 ISO、IEC、IEEE 或任何公司的合规/认证；亦不声称下列公司提供 MCC 的官方模板。

## 1. 证据层级与用语

| 层级 | 在 MCC 的含义 | 使用方式 |
|---|---|---|
| **规范性标准** | ISO/IEC/IEEE、IETF 的公开标准或 BCP | 用于确定信息职责和规范性用语；不自动决定模板章节或产品设计。 |
| **厂商一手实践** | Google、Microsoft、OpenAI、Anthropic、Apple 的公开开发者材料 | 可操作参考；按产品、平台和工作负载适用，不视为通用标准。 |
| **MCC 仓库约定** | 本仓库的 Markdown、PlantUML、文档层级、ID 与证据状态 | 本仓库的实际要求；不是外部标准要求。 |

若文档需要使用 RFC 2119/8174 的规范性大写词，必须在文首声明其解释遵循 [BCP 14（RFC 2119，经 RFC 8174 更新）](https://www.rfc-editor.org/info/rfc2119/)；[RFC 8174](https://datatracker.ietf.org/doc/rfc8174/) 明确只有全大写词具有该特殊含义。未作声明时，中文“必须/应/可”仅是 MCC 编辑语言，不借用 BCP 14 法律式语义。

## 2. 规范性基线

- [ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html) 是已发布的需求工程基线：覆盖需求过程、必需信息项及其内容和格式指引。ISO 页面显示该版于 2024-05-10 确认，并于 2026-02-16 进入“to be revised”；在新版本发布前，MCC 仍以已发布的 2018 版为参照，并在更新模板前复核 DIS/新版变化。
- [ISO/IEC/IEEE 42010:2022](https://www.iso.org/standard/74393.html) 是已发布的架构描述基线：规定架构描述的结构与表达，以及架构框架、观点和模型种类的相关要求；它不规定创建描述的方法、记法、工具或载体。因此 MCC 选择 Markdown 与 PlantUML 是仓库约定，不是该标准指定格式。
- [IEEE 1016-2009](https://standards.ieee.org/ieee/1016/4502/) 描述软件设计说明的信息内容与组织，且可适用于高层和详细设计；但 IEEE 将其列为 **Inactive-Reserved**（2020-03-05 失效）。MCC 只把它作为历史的信息组织参考，不作为现行符合性依据。

## 3. 各文档的最小实践映射

| MCC 文档 | 最少应回答/保留的信息 | 主要依据 | MCC 落实边界 |
|---|---|---|---|
| **PRD** | 读者/利益相关方；问题、目标、范围与非范围；可验证需求、约束、优先级、验收标准、来源与追溯。 | 29148 的需求信息项基线；Google 要求先声明文档范围、非范围和目标读者，并按读者需求组织内容（[Documents](https://developers.google.com/tech-writing/one/documents)、[Audience](https://developers.google.com/tech-writing/one/audience)）。 | PRD 定义 `why/who/what/success`，不替代架构、函数级设计或运行结论。每个 Must 需求应有验收方式和下游设计/验证链接。 |
| **产品软件实现架构设计说明书** | 架构范围；利益相关方与关注点；所选观点、视图和模型；系统边界、模块、接口、数据责任、质量属性、关键取舍、运行/部署、可观测性、发布与回滚。 | 42010 的架构描述概念；Microsoft 将技术规格定位为工程的实施计划，列出 API/数据契约、兼容、回滚、测试计划、监控信号和备选设计（[Architecture design specification](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-design-specification)）。 | 设计选择必须能回指业务或质量需求。架构决定另记 ADR；Microsoft 建议 ADR 记录上下文、备选、结果、权衡和状态（[ADR guidance](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)），但 MCC 不采用其官方模板。 |
| **功能详细设计说明书** | 单特性范围；上游需求/架构链接；设计实体、接口契约、数据/状态、流程、配置与依赖、错误/失败路径、兼容与迁移、实现拆分、验证计划。 | 1016 的历史性 SDD 信息组织参考；Apple 对平台 UI 要求清晰层级和遵循平台惯例（[Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines?lang=en)）。 | 仅在涉及 Apple 平台界面时采用 HIG；它不为 MCC 的通用后端/CLI 建立要求。详细设计不得重定系统级架构，也不得把计划写成结果。 |
| **Test/Eval Report / Receipt** | 目标与通过阈值；待验收需求；代码/配置/模型或 Prompt 版本；环境、数据集及其版本/抽样；方法、评分规则、运行 ID/时间；结果、失败分类、限制、复现位置与结论。 | Microsoft 说明测试策略/计划应与业务目标对齐并明确报告结果（[testing strategy](https://learn.microsoft.com/en-us/azure/well-architected/operational-excellence/testing)）；Apple 把单元、UI、测试套件与全量测试计划区分，并建议持续收集测试/性能数据（[Testing and performance](https://developer.apple.com/documentation/technologyoverviews/testing-and-performance)）。 | 报告只陈述实际运行；Receipt 固定输入、版本与证据位置。`Planned`、`Implemented`、`Verified`、`Production` 分开记账，不可互相替代。 |

## 4. AI 功能的 Eval 补充

AI 功能的 PRD 应把“好”改写为与用户任务相关、可度量的成功准则；Anthropic 要求准则具体、可测且与应用目的相关，并提示多数用例需要多维评估（[Define success and build evaluations](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests)）。功能详细设计应写清输入分布、边界/拒绝行为、评分器及人工复核点。

Test/Eval Report 应保留真实任务分布的样本、边界案例和已知失败，并区分自动评分与人工校准。OpenAI 建议早期且持续地做任务特定 Eval、记录开发日志、尽可能自动化评分，并用人工反馈校准自动评分（[Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)）；Apple 也警示仅覆盖 happy path 的数据会造成虚假信心，并列出 golden、edge、adversarial、known-failure 分类（[Designing evaluation datasets](https://developer.apple.com/documentation/Evaluations/designing-evaluation-datasets?changes=_3_7)）。这些是厂商实践，不是 MCC 对任何模型、评分器或平台的强制选型。

## 5. MCC 仓库约定（非外部标准）

- 权威源文件使用 UTF-8 Markdown；图使用 PlantUML fenced code block。每图有标题、目的、范围、版本/日期与文字结论，且可渲染。
- 文档控制信息至少包含 ID、状态、Owner、日期、范围、关联 PRD/ARCH/DETAIL/ADR/Report；不适用项写原因，不留伪占位符。
- 链接建立双向追溯：需求 → 设计 → 实现/配置 → 测试或 Eval Receipt。实际结果只进入 Report/Receipt；设计文档只写方法、阈值、失败动作和证据位置。
- 正式模板选择、命名、状态门与层级分工以 [design-doc.md](design-doc.md) 为准；本文件提供来源和原则，不复制模板正文。

## 6. 维护规则与来源覆盖

更新本文件时，只增补能直接支持具体实践的一手标准或厂商页面，并在相邻主张处链接；版本、状态或厂商页面发生变化时先更新版本注记，再调整映射。不要以博客、培训转述、非官方模板或单一公司产品说明替代上述规范性边界。

来源覆盖：**规范性**—ISO/IEC/IEEE 29148:2018、42010:2022、IEEE 1016-2009、RFC 2119/8174；**厂商一手实践**—Google（范围/读者）、Microsoft（架构/ADR/测试）、OpenAI（Eval）、Anthropic（成功准则/Eval）、Apple（HIG/测试/Eval 数据集）。
