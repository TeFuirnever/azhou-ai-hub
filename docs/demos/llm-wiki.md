# LLM Wiki reference demo

This demo shows the branded interaction, machine receipt, and private storage boundary. It proves the shipped runtime contract, not the quality of unreviewed knowledge.

## 1. Ask the agent

```text
Use llm-wiki to store this verified architecture decision, query it back, and lint the wiki.
```

Provide the decision, its source, and an honest confidence level. Do not include secrets, raw transcripts, or unrelated personal data.

## 2. Expect these outputs

The interaction uses one restrained Azhou anchor per completed stage:

```text
🦊 阿舟 · LLM Wiki 启动｜operation=ingest｜scope=/absolute/project
🧭 知识范围锁定｜topic=architecture｜sources=1｜privacy=checked
🔎 Wiki 检索完成｜operation=query｜matches=0｜read_only=true
📝 Wiki 更新完成｜action=created｜page=auth-decision.md｜confidence=high
🧪 Wiki 健康检查｜errors=0｜warnings=0｜info=1
✅ 验证通过｜checks=readback,lint
```

The CLI JSON stays emoji-free and returns `llm-wiki.receipt.v2`, including `currentTruth`, exact changes and verification, holds, one next action, and `learningSignal`. A success anchor is invalid after `fail`, `hold`, or `skipped`.

## 3. Verify the runtime contract

Use an isolated project directory:

```bash
SKILL_DIR=/absolute/path/to/skills/llm-wiki
PROJECT_ROOT="$(mktemp -d)"

python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" init
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" ingest \
  --title "Auth decision" \
  --content "Use signed, short-lived sessions." \
  --tag auth --category decision --source review-42 --confidence high
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" query auth --no-log
python3 "$SKILL_DIR/scripts/llm_wiki.py" --root "$PROJECT_ROOT" lint --no-log
```

Every normal entrypoint must use only `$PROJECT_ROOT/.llm-wiki/`. The focused development checks are:

```bash
python3 -m unittest \
  tests.test_llm_wiki \
  tests.test_llm_wiki_full_parity \
  tests.test_llm_wiki_production
```

Passing proves CLI, MCP, lifecycle, migration, privacy, brand-machine separation, and negative product-surface gates. It does not make unsourced or low-confidence page content true.
