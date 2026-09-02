# Provenance and local boundary

Repository-wide notice and the retained license copy live in [THIRD_PARTY_NOTICES.md](../../../THIRD_PARTY_NOTICES.md) and [Claude-Plugins-Community-Apache-2.0.txt](../../../LICENSES/Claude-Plugins-Community-Apache-2.0.txt).

## Imported source

| Field | Locked value |
|---|---|
| Upstream | `https://github.com/anthropics/claude-plugins-community` |
| Immutable commit | `794af9e63d07fad17087dcab61f21f44cb48effd` |
| Upstream path | `eli5/skills/eli5/SKILL.md` |
| Upstream SHA-256 | `3bb95cd13852051c5a1862e8b94da1de7cfba7415d418ab0ca4d762527d1b9a5` |
| License | Apache-2.0, the repository-level `LICENSE` file of the upstream project |

The upstream baseline at the locked commit is a single 321-byte `SKILL.md`. Its behavior sentence is retained verbatim in this package's `SKILL.md`; no other upstream bytes exist to import.

## Azhou-maintained adaptation

- keeps the upstream behavior sentence verbatim as the capability baseline;
- keeps the upstream two-key `name` and `description` frontmatter shape and documents a harness-neutral topic argument instead of the slash-command-only `$ARGUMENTS` slot;
- adds the topic boundary, the one self-contained artifact contract, the Azhou brand protocol, and a stable receipt;
- adds this provenance record and the upstream compatibility map.

## Reproducible source check

```bash
curl -fsSL https://raw.githubusercontent.com/anthropics/claude-plugins-community/794af9e63d07fad17087dcab61f21f44cb48effd/eli5/skills/eli5/SKILL.md \
  | shasum -a 256
```

Expected SHA-256: `3bb95cd13852051c5a1862e8b94da1de7cfba7415d418ab0ca4d762527d1b9a5`.
