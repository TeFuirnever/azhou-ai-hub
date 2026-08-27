# LLM Wiki brand layer

Use one restrained Azhou anchor per material stage. Machine output remains emoji-free.

| Stage | Anchor | Required content |
|---|---|---|
| start | `🦊 阿舟 · LLM Wiki 启动` | operation, project root, selected store |
| scope | `🧭 知识范围锁定` | topic, source boundary, privacy exclusions |
| read | `🔎 Wiki 检索完成` | query/list/read result count and read-only status |
| write | `📝 Wiki 更新完成` | created/updated page, source, confidence |
| lint | `🧪 Wiki 健康检查` | errors, warnings, informational findings |
| hold | `🔒 阿舟暂停这一项` | missing deletion authorization, invalid scope, or privacy hold |
| finish | `✅ LLM Wiki 验证通过` | only after the declared checks pass |
| failure | `❌ LLM Wiki 验证失败` | failed check and retained artifact state |

Finish with the script's `llm-wiki.receipt.v1` fields: `status`, `operation`, `store`, `result`, `changes`, `verification`, `holds`, and `nextAction`. Do not print a success anchor after a `fail`, `hold`, or `skipped` receipt.
