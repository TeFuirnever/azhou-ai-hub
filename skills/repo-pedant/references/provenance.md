# Provenance

## Upstream lineage

- Upstream skill: `neat-freak` from [KKKKhazix/Khazix-Skills](https://github.com/KKKKhazix/Khazix-Skills), immutable commit `bab178311a65f93ffd073e4fdebc9911eae35791`, MIT (repository-level copy at [Khazix-Skills-MIT.txt](../../../LICENSES/Khazix-Skills-MIT.txt)).
- Exact regression snapshot: `benchmarks/repo-pedant/upstream/neat-freak/` (entry stored as `SKILL.snapshot.md` so package discovery cannot install the legacy baseline); the snapshot is hash-locked by `scripts/check_repository.py`.
- Capability contract: [neat-freak-compatibility.md](neat-freak-compatibility.md) records every original capability as `preserved`, `restored`, `conflict_replaced`, `disadvantage_replaced` or `additive`, with the safety or implementation reason for each replacement.

## Fidelity classification

Classification: `adapted` — this package declares itself the strict enhancement of neat-freak (entry: "repo-pedant 是 neat-freak 的严格增强版"): every original capability remains mandatory, and the local layer adds authorization checkpoints, inventory/impact/execution protocols, receipts and the runtime-state contract on top of the original's flow — a behavior superset, which skill-standard §2.3 classifies as `adapted`. The `super-` prefix rename rides the audit's promotion-coupled rename milestone (#176 M3), coordinated with the super-caveman promotion record's reviewed blobs. Skill-standard §2.3.
