# Provenance

## Upstream lineage

- Upstream skill: `neat-freak` from [KKKKhazix/Khazix-Skills](https://github.com/KKKKhazix/Khazix-Skills), immutable commit `bab178311a65f93ffd073e4fdebc9911eae35791`, MIT (repository-level copy at [Khazix-Skills-MIT.txt](../../../LICENSES/Khazix-Skills-MIT.txt)).
- Exact regression snapshot: `benchmarks/super-repo-pedant/upstream/neat-freak/` (entry stored as `SKILL.snapshot.md` so package discovery cannot install the legacy baseline); the snapshot is hash-locked by `scripts/check_repository.py`.
- Upstream v3 observation (2026-10-07 audit, read-only): upstream HEAD `322346ded8129436b3f64707789a73e732ae24d9` self-declares `metadata.version: "3.0.0"`. The pin→v3 delta was re-audited per capability and judged an equivalent evolution (20 kept / 8 changed-mappable / 0 removed across the 28 baseline rows); see [neat-freak-compatibility.md](neat-freak-compatibility.md) v2 and [`docs/research/2026-10-07-neat-freak-v3-capability-audit.md`](../../../docs/research/2026-10-07-neat-freak-v3-capability-audit.md). The implementation baseline stays at the pin above; no vendored bytes changed.
- Capability contract: [neat-freak-compatibility.md](neat-freak-compatibility.md) records every original capability as `preserved`, `restored`, `conflict_replaced`, `disadvantage_replaced` or `additive`, with the safety or implementation reason for each replacement.

## Fidelity classification

Classification: `adapted` — this package declares itself the strict enhancement of neat-freak (entry: "super-repo-pedant 是 neat-freak 的严格增强版"): every original capability remains mandatory, and the local layer adds authorization checkpoints, inventory/impact/execution protocols, receipts and the runtime-state contract on top of the original's flow — a behavior superset, which skill-standard §2.3 classifies as `adapted`. The canonical name is `super-repo-pedant` (renamed from `repo-pedant` in #182 under the audit's promotion-coupled rename milestone #176 M3, coordinated with the super-caveman promotion record's reviewed blobs); the old name survives only as a compatibility trigger. Skill-standard §2.3.
