# Source and local boundary

Source: https://github.com/zai-org/ZCode/blob/a9fe401eede6e6e5e01be9048679c206fe6f02d9/.agents/skills/architecture-governance/SKILL.md

Source SHA-256: `33fb5462d6d8b0d5b61897b75842c5233e245b1cc5c2dffb02689733acce51bc`. License: Apache-2.0; retained notice/license files are in this folder.

This is a task-scoped adaptation for Azhou AI Hub, not a copy or claim of full upstream parity. It preserves the trigger and general engineering method while substituting the current project rules, actual tools, evidence and authorization. Source-project paths, commands, product-specific runtime contracts, automatic deletion, mandatory publication and approvals do not transfer. Consult the immutable source for omitted source-specific details.

## Capability adaptation

- 保留与补齐：编码前基线与有界上下文、单一状态所有者、公开依赖边、异步顺序/幂等/过期结果/重放、基线违规与新违规分离、检查器实际覆盖边界。
- 本地替代：按 Hub 当前架构和模块归属检查，新增模块沿已有登记机制；人工检查与可执行门禁分别报告。
- 未迁入：ZCode architecture-policy.yaml、固定 contract/domain/app/adapters/ui 层级、adopt/context/check 工具、四文件模块模板和停用 app unit test 的产品规则。

本地升级方法：从上面的不可变 commit 获取原 Skill 与用到的配套资源，核对内容摘要和许可证，再逐项复核本节能力及本项目替代；保留既有 notices。先形成可审查差异，完成格式、引用和实际场景验证后再按用户授权更新本项目目录，不自动覆盖全局安装。

`NOTICE-ZCode.md` 是逐字保留的上游法律声明；其中相对路径以[来源仓库的固定版本](https://github.com/zai-org/ZCode/tree/a9fe401eede6e6e5e01be9048679c206fe6f02d9)为上下文，不是本项目可执行入口。
