# Azhou AI Hub · Ponytail 审计与分阶段执行计划（2026-11-19）

- 快照：`main` `3dfff39fc289d958d90d66c75121e8f64072d7ed`。本页是该版本的只读审计与近程执行记录，不是已修复或已部署的声明。
- 范围：Hub 入口、目录和分发、CI/发布、Agent Skin、维护的 pstack 集成；按本地工作站、同一 checkout 可能有并发任务、GitHub Actions 远端门禁的实际使用形态判断。按 [Ponytail Audit](https://github.com/DietrichGebert/ponytail/blob/main/skills/ponytail-audit/SKILL.md) 先查活跃入口和调用方，再判定删减，不按文件大小判断。
- 目标：先修会产生错误结果或误导证据的问题，再删明确无人使用的路径；复用已验证、可维护且有来源的实现，不把对标理解成补齐所有功能。

## 发现与最小调整

基线行号以开头提交为准；代码路径是审计依据。运行时风险未在真实用户宿主或真实发布中触发。

| ID | 结论与依据 | 处理与验收 |
| --- | --- | --- |
| 1 | **保留；原“CI 漏跑 retired scan”假设被否定。** [.github/workflows/ci.yml:63–90](../../.github/workflows/ci.yml) 总会执行 Hub 单测；[tests/test_check_retired_surfaces.py:29–30](../../tests/test_check_retired_surfaces.py) 直接扫描实际 checkout；命令行的 [scripts/verify.py:31](../../scripts/verify.py) 也执行该扫描。 | 不另造 CI 步骤，不放宽现有检查。仅在未来实测维护或运行成本明显时评估重复调用，不能只看 workflow 的步骤名就判定漏洞。 |
| 2 | **修；发布校验和候选标识可能分离。** [.github/workflows/release.yml:19–30,43–71](../../.github/workflows/release.yml) 测 checkout 和传 `--target`，但已存在且没有 release 的同名 tag 不是必然指向该 checkout；创建 draft 前只查了 release。 | 复用现有发布流程，在写入前明确核对 tag 至已验 SHA。至少测无 tag、tag 指向已验 SHA、tag 指向另一 SHA、查询异常；不移动已有 tag，不触发真实发布。 |
| 3 | **修；pstack 集成终态写得过早。** [scripts/integration_pstack.py:555–556,1284–1297](../../scripts/integration_pstack.py) 在 doctor/native 回读前写 `installed` / `removed`，只捕获声明的集成失败；若此时中断，磁盘凭证可看似完成。 | 成功回读后再发布终态，继续保留操作中的可恢复状态。分别用隔离 fixture 检查 install/remove 成功、回读失败、在回读边界中断不留下假终态。 |
| 4 | **修；pstack 审核摘要受易变运行文件影响。** [scripts/integration_pstack.py:59–75,209–222,592,1182–1186](../../scripts/integration_pstack.py) 的计划承诺记录受控输入，但目录遍历哈希会纳入 SQLite/WAL/tmp 等运行产物；Azhou 未改授权输入，也可能因宿主运行而拒绝应用。 | 只对确定性自有输入计算审批绑定；真实目录越界、未知数据和所有权审查仍失败。测日志/WAL 改变不误失效，受控文件改动仍拒绝。 |
| 5 | **缩；#519 下线后还有 Dream 渲染契约的候选尾巴。** [wallpaper/apply.js:174–218](https://github.com/TeFuirnever/azhou-ai-hub/blob/1eeb03c6005ac08b2c852d6f61823181bcee4fe4/packages/agent-skin/wallpaper/apply.js)、[wallpaper/renderer.js:174–193,588–589,677–733](https://github.com/TeFuirnever/azhou-ai-hub/blob/1eeb03c6005ac08b2c852d6f61823181bcee4fe4/packages/agent-skin/wallpaper/renderer.js) 和 [extension/renderer.mjs:24](https://github.com/TeFuirnever/azhou-ai-hub/blob/1eeb03c6005ac08b2c852d6f61823181bcee4fe4/packages/agent-skin/extension/renderer.mjs) 仍有 `mainPaint` 分支或字段；独立的 [theme-source-library](https://github.com/TeFuirnever/azhou-ai-hub/blob/1eeb03c6005ac08b2c852d6f61823181bcee4fe4/packages/agent-skin/docs/theme-source-library.md) 明示开发用途，不能据此把它判作运行时功能。 | 先全树查运行、构建、生成测试及动态调用，证实无当前消费者再删专属字段、分支和只护退役能力的 fixture；开发者解析器仅在确证无独立用途时移除。保留 #517 Dot/连续性、阿舟预设和图片、host 防腐、回退及 #519 无读取/无写回的拒绝门禁。 |
| 6 | **先删；一次性的 super 前缀改名脚本仍在交付树。** [scripts/migrate_canonical_super_prefix.py](https://github.com/TeFuirnever/azhou-ai-hub/blob/3dfff39fc289d958d90d66c75121e8f64072d7ed/scripts/migrate_canonical_super_prefix.py) 383 行；当前全树名称引用只在 [历史 CHANGELOG:82](../../CHANGELOG.md) 和 [scripts/check_repository.py:961](../../scripts/check_repository.py) 的旧清单。它不同于在线安装凭证迁移和旧入口兼容。 | 删脚本和相应登记，留历史。验收不存在运行/CI/文档入口，保留 canonical discovery、已退役能力反向扫描、接续已有安装的命令及测试，全仓验证通过。 |
| 7 | **缩；目录把只读回答扩成额外行为。** Info 的 [触发词和执行约束:3,29–34](../../skills/super-azhou-info/SKILL.md) 接受“现在装了哪些 skill”，实际 [info_payload:324–346](../../scripts/azhou_hub.py) 返回 checkout 可安装清单；[Ask 路由:58–68](../../skills/super-ask-azhou/SKILL.md) 把没匹配变成必须写入逐请求哈希，未找到用它识别意图的活跃消费者，[记录器:110–124](../../skills/super-ask-azhou/scripts/record_unrouted.py) 还可能丢并发计数；[Lavish:3,42–50](../../skills/super-lavish/SKILL.md) 会把普通比较升级为浏览器长轮询，和 [Archify:19–24](../../skills/super-archify/SKILL.md) 默认不主动开页面不同。 | 分别删误导触发、默认遥测写入和普通文本的隐式浏览器升级。重新生成索引，成对验证正例、负例；确认手工摘要用途再考虑删记录器，不删旧记录，不合并四个独立的保有者/生命周期入口，不新增扫描器或通用 HTML 路由。 |
| 8 | **修；pstack 生成暂存区可被不同输出构建共用。** [packages/pstack-agent-harness/tools/build-harness.mjs:4,33–37,61–63,164–166,399–404](../../packages/pstack-agent-harness/tools/build-harness.mjs) 即使分别传 `--out` 仍共用 scratch，且清理旧输出早于所有新树完成，帮助文案还列出未实现的 `--target`。 | 修源码/补丁队列，不直接改已生成分发树。每次构建隔离暂存，完整校验后再替换；并发不同输出及中断都不污染或丢失旧产物，校对帮助文案，用生成树逐字节对照验证。 |

低优先：两种语言的 README（[EN:15,51](../../README.md)、[ZH:15,51](../../README.zh-CN.md)）、支持矩阵与路由正文重复维护动态数量。英文 banner 已见在 17 项基线仍写 16（#518 下架后恰好相符）。下一次更图时保留阿舟插画，去掉图片/alt 的精确数量；只在生成目录保留计数。历史 Dream 回执可标历史，包 README 同步 Pet 已退役，绝不据合并声称宿主已安装。

## 顺序与阶段门槛

1. **A · 先落本审计，再做单独脚本退役变更（#6）。** #1 仅记录复核，不新增门禁。确认 #6 无活跃调用方后用最小变更删除；全仓验证、反向扫描、Git diff 范围都通过再交付。
2. **B · 发布候选绑定（#2）。** 独立修复和 mock/fixture，无 release 操作；正负路径绿、现有 draft/权限守卫不变。
3. **C · Agent Skin 剩余运行契约（#5）。** 先追踪代码和生成载荷可达性，再独立小步去掉无主分支；必要时更新当前支持措辞。Codex/DSH 构建、原生、生成浏览器、覆盖率和像素负对照保留，不改变断言门槛，也不替代实机验收。
4. **D · pstack/目录分开维护。** #3、#4、#8 用独立 pstack 维护任务、补丁队列和分发生成验证，不混入 Hub Skill 升级；#7 单独改目录，先取真正诱发错误动作的提示行为进行配对验证。

各阶段从最新主线重核证据，风险变动就停止受影响动作；只读审计不代表可删除任意保留证据、可发布/装机或可绕过审批。保留许可证、原始出处、回退/断电恢复、用户数据边界、单所有者租约、无障碍和真实问题的正负对照。未触发真实发布、安装、宿主异常或并发故障注入；未逐行审查所有上游及生成文件。目录和证据中的工程结论遵循现有 [产品原则](../principles.md) 和 [集成约定](../integrations.md)。
