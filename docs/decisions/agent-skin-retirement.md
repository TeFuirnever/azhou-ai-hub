# Agent Skin retirement · 2026-11-24

The Hub retires the desktop launcher, wallpaper renderer, DSH plugin, build pipelines and integration commands. This includes the previously retired ZCode adapter. Azhou artwork now lives in [assets/azhou](../../assets/azhou/NOTICE.md). The session monitor uses host extension points and has no dependency on the skin.

## Installed users

- **Codex on macOS.** Open the official ChatGPT/Codex app directly. Unpin the Azhou launcher from the Dock. To remove it, identify the separate Azhou app bundle from its installation receipt first. Keep receipt-bound sources, private assets and backups until recovery is complete. The official host app and its profile remain independently owned.
- **DeepSeek Harness.** Disable the skin in each affected profile. Remove a plugin-manager installation through its original manager. For a linked installation, check all profiles sharing its target before removing any individual link. Preserve the shared target and saved settings while another profile uses them.
- **ZCode.** Existing frozen installations use their original launcher or their version-specific recovery procedure.

The [last source snapshot](https://github.com/TeFuirnever/azhou-ai-hub/tree/1eeb03c6005ac08b2c852d6f61823181bcee4fe4/packages/agent-skin) retains licenses, source, installer and recovery guidance. For an installed candidate from another revision, use the exact source identified by its receipt. Repository retirement performs no host-side uninstall.
