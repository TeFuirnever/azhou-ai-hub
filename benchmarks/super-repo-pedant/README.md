# Super Repo Pedant benchmark

Development-only evaluation layer. Nothing here ships inside the installed skill.

## Layout

- `manifest.json` and `cases/*.case.json`: public prompts, expected behavior, protected paths, and gates.
- `fixtures/`: isolated synthetic repositories. `content-research/` remains an unregistered future case.
- `benchmark.py`: deterministic package, protected-path, review, and first-pass checks.
- `history/`: aggregate snapshots only. Raw or excerpt-bearing reports stay outside Git.
- `results.tsv` and `results/`: baseline, paired decisions, and human-checkpoint artifacts.
- `neat-freak-parity.json` and `regression-map.json`: all 28 baseline capabilities, documented replacements, and deterministic/model-regression evidence routes.
- `protocol/`: one valid v2 execution record, the historical v1 freeform-anchor drift (rejected at the schema-version gate), and a v2 freeform-anchor drift that deterministic validation must reject at the anchor level.
- `trigger-cases.json`: positive, negative, and reminder-only trigger boundaries for cross-model evaluation.
- `workspace/`: generated local runs; ignored by Git.

## Run

```bash
python3 benchmarks/super-repo-pedant/benchmark.py check
python3 benchmarks/super-repo-pedant/benchmark.py verify \
  --case code-spec-conflict \
  --candidate benchmarks/super-repo-pedant/workspace/code-spec-conflict \
  --run benchmarks/super-repo-pedant/workspace/code-spec-conflict.run.json
```

Each candidate starts as a fresh fixture copy and receives only the case prompt. Keep case assertions and expected behavior outside the candidate directory.

`verify` accepts attempt `1` only. A usable first pass requires:

1. fixture `verify_command` passes;
2. protected code/input paths match the pristine fixture;
3. declared output files and a complete branded `super-repo-pedant.receipt.v2` exist;
4. human and safety reviewers both mark the run `passed` with reviewer identity.

Use identical fixtures and permissions for baseline/candidate. Run at least three independent paired judges, reverse A/B order, reject safety regressions, then stop for human promotion confirmation. Absolute scores remain triage signals only.

## Isolated replay of the 2026-11-10 evaluator

`replay_isolated.py` is a development adapter for the exact previously reviewed project-scope evaluator, not a general evaluator sandbox. It reads the original registration by an external SHA-256 anchor, verifies the pinned evaluator and frozen inputs, then creates a new output tree and synthetic Git identities. Only ownership paths are remapped; evaluator bytes, cases and answers remain unchanged. The derived registration is recorded separately.

~~~bash
python3 benchmarks/super-repo-pedant/replay_isolated.py \
  --source /absolute/frozen-project-scope-corpus \
  --runtime /absolute/skill/scripts \
  --output /absolute/new-replay-directory \
  --expected-registration-sha256 '<frozen-registration-sha256>'
~~~

The output directory must be new and disjoint from corpus/runtime; existing output is never reused. Before/after inventories cover original corpus and runtime plus copied protocol, frozen inputs and runtime, including bytes, links, directories and modes. `status=complete` and `isolation_status=passed` mean the replay completed without observed input drift. `effect_status` reports case outcomes separately: a correctly isolated baseline can still fail cases. Any observed input drift invalidates the effect result. Original evidence remains intact; failures and partial timeout output stay in the new directory. This is a path-mapped synthetic replay, not the original exact protocol, a natural task trial or an OS sandbox.
