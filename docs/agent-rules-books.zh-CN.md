# Agent Rules Books

从下面 14 套书籍工程规则中，选一套来处理眼前的工程问题。

- `a-philosophy-of-software-design` 用来简化模块边界和 API。
- `clean-architecture` 用来让业务规则独立于框架、数据库和界面。
- `clean-code` 用来改进命名、函数和代码可读性。
- `code-complete` 用来检查控制流、防御性代码和测试。
- `designing-data-intensive-applications` 用来分析数据一致性、复制和可靠性。
- `domain-driven-design` 用来为复杂业务建模、划分限界上下文。
- `domain-driven-design-distilled` 用来梳理子域和上下文之间的关系。
- `implementing-domain-driven-design` 用来实现聚合、领域事件和仓储。
- `patterns-of-enterprise-application-architecture` 用来选择服务层、事务脚本和数据映射器等模式。
- `refactoring` 用来改进现有代码结构，同时保留可观察的行为。
- `refactoring-guru` 用来识别代码坏味道、选择重构手法。
- `release-it` 用来评审超时、重试、熔断和故障恢复。
- `the-pragmatic-programmer` 用来缩短反馈周期、判断哪些工作值得自动化。
- `working-effectively-with-legacy-code` 用来通过接缝和刻画测试安全修改难以测试的代码。

### 在 Azhou AI Hub 开发时使用

Hub 维护的版本在 `.agents/skills/`。开发 Hub 时，直接使用当前 checkout 自带的规则。在这个 checkout 打开的 Codex 会话里，可以输入 `$refactoring 检查这次改动，建议一项能保持行为的最小重构。` Ask Azhou 核实当前工作区已启用对应规则后，也可以推荐它。

### 在其他项目安装

准备好 Node.js 和 npm 后，在自己的项目目录运行下面的命令，为 Codex 安装 Hub 维护的版本。把 `refactoring` 换成上面任意一个规则名即可。如果安装器询问安装范围，请选当前项目。

~~~bash
npx skills add TeFuirnever/azhou-ai-hub --skill refactoring --agent codex
~~~

在同一项目里打开新会话，确认能找到该技能后再调用。安装器默认从 Hub 的默认分支取规则。要与某个 Hub checkout 的版本完全一致，在仓库名后加 `@<commit>`。[安装和更新说明](https://github.com/TeFuirnever/azhou-ai-hub/blob/main/docs/installation.md#install-agent-rules-books)
