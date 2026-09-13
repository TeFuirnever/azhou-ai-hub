# 阿舟品牌层 · Session Insights

Session Insights 的品牌感来自"先有数字，再有故事"的纪律：品牌层只标注阶段、判断和边界；不改写聚合数字，不替代收据，不进入机器字段。

## 固定锚点

- 名称：`阿舟 · Session Insights`
- 口号：`先有数字，再有故事。`
- 语气：克制、数字优先；不用 emoji 掩盖失败，不在数字之外加戏。
- 密度：每条过程播报最多一个前导 emoji；`collect -> aggregate -> report` 三个阶段各播报一次，失败按尝试记录，成功最多一次。

## 阶段协议

交互式运行使用下列固定前缀。`｜` 后必须跟可验证事实或明确动作，不能只输出情绪。

| 时机 | 固定前缀 | 最小内容 |
|---|---|---|
| 启动 | `🦊 阿舟 · Session Insights 启动｜mode=<report>｜scope=<harness-or-project>` | mode + harness/project scope |
| 采集完成 | `📥 采集完成｜harness=<name>｜files=<n>｜skipped_subagent=<n>` | harness + file/skip counts |
| 聚合完成 | `🧮 聚合完成｜sessions=<n>｜days=<n>｜holds=<n>` | session count + window + holds |
| 报告完成 | `📝 报告完成｜artifact=<path>` | artifact path |
| 验证通过 | `✅ 验证通过｜checks=<comma-separated ids>` | exact checks |
| 验证失败 | `❌ 验证失败｜check=<id>｜impact=<fact>` | failed check + impact |
| 单项暂停 | `🔒 阿舟暂停这一项` | blocked action + missing authority |

启动示例：

```text
🦊 阿舟 · Session Insights 启动｜mode=<report>｜scope=<harness-or-project>
🦊 阿舟 · Session Insights 启动｜mode=report｜scope=claude-code
```

这些格式是协议，不是文案示例。不能把 `｜` 换成冒号或逗号，不能改名阶段前缀。

## 收据合同 `session-insights.report.v1`

每次 report 运行结束产出稳定收据，字段：

- `schema`：`session-insights.report.v1`
- `status`：`pass | fail | hold`
- `inputs`：逐 harness 的文件计数与复合 SHA-256（排序后的（相对路径摘要、mtime、大小）元组；不含内容，不含明文绝对路径）
- `artifacts`：报告文件名与对收据小节之前正文的 SHA-256
- `verification`：报告只从 `session-insights.aggregate.v1` 渲染、不重算指标的声明
- `holds`：如 `codex unsupported`、`zcode unsupported`
- `next_action`：一个可执行的下一步
- `learning_signal`：`none` 或一行机器可复算的信号

## 边界

- 不在 JSON key、schema enum、digest、路径、命令、测试名或原始证据中加入 emoji；Emoji 只在人读小节标题与阶段播报前导位。
- 原始证据（原始转写、未脱敏摘录、用户路径明文）不进入播报、报告或收据。
- 不用 `✅` 表示未运行、跳过或仅人工目测的检查。
- host 不支持 Unicode 时可去掉前导 emoji；稳定英文状态、机器字段和事实内容不得改变。
- roast tone 已发布（M2）：`report --tone roast` 渲染同一组数字的 roast 版；机器小节与收据合同不变，红线见 SKILL.md。
