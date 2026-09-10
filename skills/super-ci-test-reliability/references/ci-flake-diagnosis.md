# CI flake diagnosis workflow

A Python-stack re-expression of the pinned upstream's diagnosis reference (see [provenance.md](provenance.md) for the source pin). Use it when a CI test fails probabilistically; a diagnosis-only request stays read-only.

## 1. Freeze the evidence first

Before rerunning anything, capture what the failure already produced: the failing job's log (assertion text, stderr, timestamps), the concurrency layout at failure time (which modules, workers, jobs shared the run and the host), and any artifacts the test wrote. Reruns overwrite state; the first failure is often the only sample that shows the original contention.

## 2. Classify the failure

Place the failure in one class before reproducing; the class picks the ladder rung to start from:

| Class | Signature | Likely owner |
|---|---|---|
| Port or address in use | `EADDRINUSE`, bind errors | non-atomic allocation |
| Path or namespace collision | file exists / not found flips | predictable shared paths |
| State bleed | pass/fail depends on test order | process-global state not restored |
| Platform split | green on POSIX, red on Windows (or vice versa) | OS-owned semantics |
| Timeout mismatch | deadline fires but work was fine | lane-budget violation |
| Late completion | cleanup-side failures, corrupted next test | incomplete teardown |
| Resource exhaustion | too many open files, workers | disposal never awaited |
| Genuine product race | reproduces in the product entry path | the code under test |

If the class is not determinable from the frozen evidence, say so and treat reproduction as the next evidence-gathering step, not as confirmation of a guess.

## 3. Climb the reproduction ladder

Reproduce the contention, not just the test. Each rung is cheap before the next:

1. Rerun the single failing case alone — if it still fails, it is deterministic; stop, this is not a flake.
2. Rerun the owning module with its real neighbors in the same process pool.
3. Run the owning module concurrently with the modules that shared the failed job.
4. Run independent processes concurrently when the suspect resource is host-owned (port, path, subprocess).
5. Reproduce on the failing platform when the failure is platform-split.

Stop at the lowest rung that reproduces and record the rung in the report.

## 4. Fix at the owner

Map the reproduced class onto the owning section of the skill's methodology (allocation, global state, platform semantics, budgets, synchronization, quiescence) and fix the test design there. A fix that does not change what the test waits for, allocates, or restores is usually masking.

## 5. Close out

Prove the fix with the ladder rung that reproduced the failure now green, plus the regression negative control where one applies. Report the failure class, the reproduction rung, the exact commands, and the observed results; keep raw logs out of receipts unless the user supplied them.
