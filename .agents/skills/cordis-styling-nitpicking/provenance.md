# Source and local boundary

Source: https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/.agents/skills/cordis-styling-nitpicking/SKILL.md

Source SHA-256: `697bdf8aced2c680b74ceea93cb836d650c85f3f451618891d320327cd74d5b1`. License: MIT; retained notice/license files are in this folder.

This is a task-scoped adaptation for Azhou AI Hub, not a copy or claim of full upstream parity. It preserves the trigger and general engineering method while substituting the current project rules, actual tools, evidence and authorization. Source-project paths, commands, product-specific runtime contracts, automatic deletion, mandatory publication and approvals do not transfer. Consult the immutable source for omitted source-specific details.

## Capability adaptation

- 保留与补齐：真实插件根的可达审查、全局可变状态归属、副作用逆操作、清理最后依赖调用、并发disposer/监听器失效、真实disposer身份、根退出/替换/异常路径、屏障回归与终态/持久结果。
- 本地替代：Cordis语义仅在实际Cordis使用中核实；通用异步资源按真实owner判断，严重级别按实际影响。
- 未迁入：所有三类自动P0、固定vendored Cordis版本的generator workaround、DSH专属记录与审查schema。

本地升级方法：从上面的不可变 commit 获取原 Skill 与用到的配套资源，核对内容摘要和许可证，再逐项复核本节能力及本项目替代；保留既有 notices。先形成可审查差异，完成格式、引用和实际场景验证后再按用户授权更新本项目目录，不自动覆盖全局安装。
