# Agent Skin V3 file installation — 2026-11-18

## Scope and identity

Local maintainer-Mac installation of candidate `9824937080eb512657fe851866af93500baeb15a`, version `0.9.0`, build `43`. This is the restricted literal-main Dream profile, not full Dream compatibility. Existing private Azhou artwork was reused; private sources and generated media are not distributed by this receipt.

Builds were bound to the candidate and private inputs. The persistent-source build passed twelve build, artifact, signature, source-parity and before/after-input gates with no compiler warnings. Full repository verification was inherited through exact source parity with the candidate verification, not represented as a new full-suite run in the installation phase.

| Artifact | Identity |
| --- | --- |
| Codex input SHA-256 | `1f3e01a66b90a02af3c0caa9013b1d9f58ff890acbf3875a84156bfb10cd0b24` |
| Codex installed tree fingerprint | `d30f68c8da89e85cc8a2e45025c37dfffd3a89d1cc5635cc93080ac6c6829bea` |
| Previous Codex tree fingerprint | `ad73042f97aa26eb6d1ed983b5a5195c2452f8ffcf28f2f6e826a824e45bb3e1` |
| DSH input SHA-256 | `205f974cc9cc033733c655c2a304ddd252858cbfb56a1d0df35541236ab0f22f` |
| DSH installed tree fingerprint | `bbd42b9819fa3cbb15985b85fca826230a90d1b8605c0ae341210ad475c0cddb` |

Tree fingerprints above use the package verifier fingerprint algorithm, not the separate JSON content-map digest used by some build records. DSH intentionally excludes the private Codex startup-cover input; the host input digests were recomputed separately.

## DSH file update

The existing shared entity was owned by the maintainer. Three profile links resolved to it. A complete current build-43 snapshot was verified by content, permissions and ownership. Same-volume isolated copies passed `renamex_np(RENAME_SWAP)` update and swap-back with the simulated profile link identity preserved.

For the actual update, both existing maintenance locks were acquired nonblocking. Repeated process and open-file checks found no DSH host/backend using the entity. Old package, candidate, backup and the three links were rechecked before the atomic exchange. The installed entity passed artifact verification and the complete tree check; the three real profile links retained their identities. The displaced package and independent snapshot were retained. This round did not swap production back after successful installation; its rollback rehearsal used isolated copies.

## Codex file update

The old installation receipt, source payload and installed bundle agreed. New and old signatures passed, the launcher was not running, and the migration-specific registry inventory contained no extra retirement targets. The formal native installer migrated ownership from the maintainer checkout to a version-fixed persistent source outside disposable caches, using its global/new-source/old-source locks and identity-protected replacement. No `--open` was used.

Migration and the subsequent `--check` both passed: one installed entry, one registration and a matching new payload. The previous source, receipt and independent signed payload snapshot were retained. The persistent source is now an active installation owner and must not be removed until a later verified handoff. The active ChatGPT process remained running.

## Acceptance boundary and evidence custody

**Installed files verified; current running payload not verified.** Neither host was launched or restarted in this update. Cold/hot startup, exact loaded-payload identity, settings persistence/restore, navigation, focus/IME and visual acceptance remain pending for this precise candidate. Historical build-42/build-43 observations and user feedback do not transfer to these bytes. No general desktop-isolation, crash-proof transaction or full Dream-compatibility claim is made.

Raw build receipts, before/after manifests, the DSH transaction, native migration/check logs, private artwork and recovery packages remain in ignored maintainer-local evidence. No public push was performed in the installation steps. The support matrix and source provenance were reviewed and updated to distinguish installation from runtime acceptance.
