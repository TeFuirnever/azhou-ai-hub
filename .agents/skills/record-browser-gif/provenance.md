# Source and local boundary

Source: https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/.agents/skills/record-browser-gif/SKILL.md

Source SHA-256: `baacaf5ca4591280a8d3e67f256b8e9beb6a89fe2dd5c0636086621146643806`. License: MIT; retained notice/license files are in this folder.

This is a task-scoped adaptation for Azhou AI Hub, not a copy or claim of full upstream parity. It preserves the trigger and general engineering method while substituting the current project rules, actual tools, evidence and authorization. Source-project paths, commands, product-specific runtime contracts, automatic deletion, mandatory publication and approvals do not transfer. Consult the immutable source for omitted source-specific details.

## Capability adaptation

- 保留与补齐：真实版本/服务/transport证据链、隔离单次story、video/截图fallback、状态就绪、视频flush、随包encoder、trim/speed/hold/palette/size参数、编码后QA、分片、发布前后head/正文/附件复核。
- 本地替代：当前浏览器工具优先，依赖缺失不安装；附件检查实际CLI/connector能力，只有明确上传请求才发布。
- 未迁入：DSH固定build/profile/凭据位置、所有GUI PR强制GIF、仅凭gh版本号假设附件支持；媒体测试不放运行包。

本地升级方法：从上面的不可变 commit 获取原 Skill 与用到的配套资源，核对内容摘要和许可证，再逐项复核本节能力及本项目替代；保留既有 notices。先形成可审查差异，完成格式、引用和实际场景验证后再按用户授权更新本项目目录，不自动覆盖全局安装。

运行工具 `scripts/encode_gif.py` 为上述 commit 同路径的原始副本（MIT）。Git blob: `cfda42ccabd53b015e15de6e8a35306a6c0faa74`；SHA-256: `34aa805990361bc9838267a767160bd209f3e113d844913d4370b98af8441a47`。依赖与验证方式见 [references/setup.md](references/setup.md)。
