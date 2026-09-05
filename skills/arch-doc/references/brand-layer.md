# Arch Doc 品牌层（多阶段事件协议）

固定阶段、前缀与收据格式；Emoji 只属于展示层，机器字段保持纯文本。Host 不支持 Unicode 时按「Unicode 降级」小节退化，不改变语义。

## 模式与阶段

| 模式 | 阶段顺序 |
|---|---|
| draft | 研读 → 骨架 → 成文 → 图纪律 → 回源 → 入账 |
| calibrate | 增量研读 → 回源勘误 → 入账 |
| review | 对标评审 → 报告落盘 |
| sequence | 图纪律自查 → 入账 |

## 状态前缀

- 阶段进行中：`🦊 阿舟 · Arch Doc 启动｜mode=<draft|calibrate|review|sequence>｜scope=<repo-or-document>` 之后按步骤陈述进度。
- 阶段完成：陈述该步完成判据的满足事实（引用校验输出），不单发完成事件。
- 收尾锚点：全部声明检查完成后发 `✅ 验证通过`；任何 gate 失败发 `❌ 验证失败` 并列 gate；单项阻塞发 `🔒 阿舟暂停这一项`，其余步骤继续。

## 收据（稳定 schema）

```text
mode=<mode>
source=<上游真源路径>
artifact=<产出文档路径>
checks=<已跑确定性校验清单，逐项 pass/fail>
review=<对标分数与 Top 发现，或 n/a>
holds=<具名阻塞项，无则 none>
next_action=<一个具体下一步>
learning_signal=<本次可沉淀的一条经验，或 n/a>
```

`skipped`、`pending` 或缺失证据不得升级为 pass；成功锚点必须是最后一个事件。

## Unicode 降级

不支持 Unicode 的 host：`🦊 阿舟` 可省略，`✅ 验证通过` → `验证通过`，`❌ 验证失败` → `验证失败`，`🔒 阿舟暂停这一项` → `暂停`；模式行、收据字段与校验名不变。
