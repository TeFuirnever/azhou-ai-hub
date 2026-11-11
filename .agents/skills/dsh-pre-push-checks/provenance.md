# Source and local boundary

Source: https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/.agents/skills/dsh-pre-push-checks/SKILL.md

Source SHA-256: `8a4b78f71444be44bc2fcfab25f6b1553230bdb61433f1bd586f53f8429d17d7`. License: MIT; retained notice/license files are in this folder.

This is a task-scoped adaptation for Azhou AI Hub, not a copy or claim of full upstream parity. It preserves the trigger and general engineering method while substituting the current project rules, actual tools, evidence and authorization. Source-project paths, commands, product-specific runtime contracts, automatic deletion, mandatory publication and approvals do not transfer. Consult the immutable source for omitted source-specific details.

## Capability adaptation

- 保留与补齐：实时基线/scope、实际消费者到检查映射、测试选择与源码覆盖分离、参数透传/数量核对、hook改变字节后复查、exact lease、同步后逐层验证、远端OID/CI/review/no-checks归因。
- 本地替代：Hub强制python3 scripts/verify.py优先；本地ignored Skill另做文件指纹；推送与历史操作需实际授权。
- 未迁入：DSH无统一本地基线、具体pnpm/hook/snapshot布局与覆盖率阈值，不自动授权stack sync。

本地升级方法：从上面的不可变 commit 获取原 Skill 与用到的配套资源，核对内容摘要和许可证，再逐项复核本节能力及本项目替代；保留既有 notices。先形成可审查差异，完成格式、引用和实际场景验证后再按用户授权更新本项目目录，不自动覆盖全局安装。
