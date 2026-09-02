# Provenance and local boundary

## Referenced upstream

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/karpathy/autoresearch` |
| Pinned commit | `228791fb499afffb54b46200aca536f79142f117` (master head at absorption, 2026-09-02) |
| Shape | Python uv project: `prepare.py`, `train.py`, `program.md`, `uv.lock` |
| License | none published; see below |

## License status and consequence

The upstream repository publishes no `LICENSE` file; GitHub license detection reports none, and the upstream README contains a single-word MIT line without license text or a copyright line. This repository treats it as unlicensed source: public visibility without a license is not permission to copy, modify, or redistribute.

Consequences for this package:

- zero upstream bytes are vendored, and every file here is Azhou-authored wrapper text;
- the experiment protocol stays in the upstream `program.md` and is read at runtime from the user's own pinned checkout; this package does not reproduce or paraphrase its content;
- the pinned commit keeps the documented setup reproducible even if upstream advances.

If upstream later publishes a formal license, vendoring or deeper adaptation may be re-evaluated only through the repository's controlled evolution path.

## Reproducible source check

```bash
git ls-remote https://github.com/karpathy/autoresearch refs/heads/master
```

At absorption time this returned `228791fb499afffb54b46200aca536f79142f117`; later heads are expected and do not change the recorded baseline.
