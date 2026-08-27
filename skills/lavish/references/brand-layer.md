# Azhou interaction layer

Keep brand in status output, never in file paths, commands, schema keys, or raw evidence.

## Start

Emit once when the skill starts:

```text
🦊 阿舟 · Lavish 启动 | mode=<artifact|review|export|share> | scope=<short scope>
```

## Material stages

Use at most one anchor per material stage:

| State | Anchor |
|---|---|
| design source and playbooks selected | `🧭 方向锁定` |
| artifact written and local checks complete | `🧱 产物就绪` |
| browser review is open and polling is attached | `🔎 审阅进行` |
| explicit hold | `🔒 阿舟暂停这一项` |
| all declared checks passed | `✅ 验证通过` |
| current attempt failed | `❌ 验证失败` |

Do not emit `🔎 审阅进行` unless a foreground poll or verified wake callback is live. Do not emit success when review, export, or publication remains pending.

## Stable receipt

End the completed workflow with these fields in this order:

```text
schema: lavish.receipt.v1
status: complete | hold | failed
mode: artifact | review | export | share
scope: <short scope>
current_truth: <what exists now>
artifacts: <local paths or none>
session_status: not_started | open | agent_ended | user_ended
verification: <named checks and results>
publication: not_requested | held | published_with_receipt
holds: <named holds or none>
next_action: <one concrete action or none>
learning_signal: <repeated failure mechanism or none>
```

`complete` means the requested scope is done. A local HTML file does not prove human review, a portable export, or publication. A returned URL is publication evidence only when the share command succeeded and the receipt records it.
