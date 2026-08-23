# Repo Pedant: 60-second demo

This demo shows the invocation and return contract. Its synthetic fixture proves that the benchmark and knowledge-surface contract are wired; it is not a claim about a model's success rate.

## 1. Ask the agent

```text
This phase is done. Run repo-pedant reconcile.
```

Use an explicit closeout request. An inferred milestone only permits one reminder and does not authorize repository edits.

## 2. Expect these outputs

The agent must return:

1. scope and current truth;
2. an inventory of affected docs, project rules, state/handoff files and project-bound memory;
3. minimal reconciliations plus named verification commands;
4. explicit holds for unresolved or unauthorized work;
5. a `repo-pedant.receipt.v2` receipt.

The [multi-surface handoff case](../../benchmarks/repo-pedant/cases/multi-surface-handoff.case.json) freezes a representative repository with stale docs, rules, handoff state and project memory.

## 3. Verify the development contract

From the repository root:

```bash
python3 benchmarks/repo-pedant/benchmark.py check
python3 -m unittest tests.test_repo_pedant_benchmark tests.test_repo_pedant_parity
```

Passing these commands proves case registration, fixtures, assertions and compatibility mapping. It does not prove that an arbitrary agent run reconciled a real repository correctly; that requires the run's own diff, checks and receipt.
