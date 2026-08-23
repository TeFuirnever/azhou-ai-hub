# Repo Pedant benchmark

Development-only evaluation layer. Nothing here ships inside the installed skill.

## Layout

- `manifest.json` and `cases/*.case.json`: public prompts, expected behavior, protected paths, and gates.
- `fixtures/`: isolated synthetic repositories. `content-research/` remains an unregistered future case.
- `benchmark.py`: deterministic package, protected-path, review, and first-pass checks.
- `history/`: aggregate snapshots only. Raw or excerpt-bearing reports stay outside Git.
- `results.tsv` and `results/`: baseline, paired decisions, and human-checkpoint artifacts.
- `neat-freak-parity.json` and `regression-map.json`: all 28 baseline capabilities, documented replacements, and deterministic/model-regression evidence routes.
- `protocol/`: one valid execution record and the captured freeform-anchor drift that deterministic validation must reject.
- `trigger-cases.json`: positive, negative, and reminder-only trigger boundaries for cross-model evaluation.
- `workspace/`: generated local runs; ignored by Git.

## Run

```bash
python3 benchmarks/repo-pedant/benchmark.py check
python3 benchmarks/repo-pedant/benchmark.py verify \
  --case code-spec-conflict \
  --candidate benchmarks/repo-pedant/workspace/code-spec-conflict \
  --run benchmarks/repo-pedant/workspace/code-spec-conflict.run.json
```

Each candidate starts as a fresh fixture copy and receives only the case prompt. Keep case assertions and expected behavior outside the candidate directory.

`verify` accepts attempt `1` only. A usable first pass requires:

1. fixture `verify_command` passes;
2. protected code/input paths match the pristine fixture;
3. declared output files and a complete branded `repo-pedant.receipt.v2` exist;
4. human and safety reviewers both mark the run `passed` with reviewer identity.

Use identical fixtures and permissions for baseline/candidate. Run at least three independent paired judges, reverse A/B order, reject safety regressions, then stop for human promotion confirmation. Absolute scores remain triage signals only.
