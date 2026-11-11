# Source and local boundary

Source: https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/.agents/skills/dsh-ci-test-reliability/SKILL.md

Source SHA-256: `6ed04407132759698e5e5e9684178f826b4c659e15e90e8e996141e5ad7edb4c`. License: MIT; retained notice/license files are in this folder.

This is a task-scoped adaptation for Azhou AI Hub, not a copy or claim of full upstream parity. It preserves the trigger and general engineering method while substituting the current project rules, actual tools, evidence and authorization. Source-project paths, commands, product-specific runtime contracts, automatic deletion, mandatory publication and approvals do not transfer. Consult the immutable source for omitted source-specific details.

## Capability adaptation

- 保留与补齐：四层并发拓扑、原子端口/目录、记录值与活资源分离、精确全局恢复、平台mtime/env/handle/signal差异、lane及hook预算、确定性同步、静止清理、既有flake分类与复现阶梯、负对照和独立进程。
- 本地替代：使用当前测试配置和CI；诊断不授权修改或远端重跑，平台不可用如实停止该复现路径。
- 未迁入：DSH Vitest固定配置、专用snapshot目录与外部API测试规则的默认继承。

本地升级方法：从上面的不可变 commit 获取原 Skill 与用到的配套资源，核对内容摘要和许可证，再逐项复核本节能力及本项目替代；保留既有 notices。先形成可审查差异，完成格式、引用和实际场景验证后再按用户授权更新本项目目录，不自动覆盖全局安装。

既有 flake 诊断亦适配自同一 commit 的 `references/ci-flake-diagnosis.md`。
