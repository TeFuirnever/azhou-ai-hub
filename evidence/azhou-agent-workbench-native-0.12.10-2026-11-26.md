# Workbench 0.12.10 desktop verification

On 2026-11-26, the Codex and ZCode plugin managers updated the existing Hub registrations from 0.12.9 to 0.12.10 on an arm64 Mac running macOS 27.2.1 (26B131). The installed manifests and runtime entry points matched [Hub revision `8d8b7f19`](https://github.com/TeFuirnever/azhou-ai-hub/commit/8d8b7f19319720532aaa1166dc73d3b5ee5adc0f). The local install receipt retains the previous cache payloads.

## ZCode Desktop 4.0.0

| Check | Observed result |
| --- | --- |
| Narrow path | Two test chats used folders with the same final name and different parent directories. Both full working paths wrapped without clipping in a pane about 240 pixels wide in the window capture. The path remained legible in day and night themes. |
| Switch chats | Switched North → South → North. The dashboard showed the selected chat's full path and its own request count. |
| Refresh | Sent one more prompt with the North dashboard open. The request count rose from one to two, the plot gained a segment, and the expanded performance details stayed open. |
| Performance details | Clicked the disclosure to open it and again to close it. The measured rows appeared and disappeared. |

The completed walkthrough used the `azhou-agent-tools` registration.

## Codex Desktop 26.1120.50957

The plugin manager reported 0.12.10. Its panel and server matched the Hub source. A separate Codex App Server check verified A → B → A thread binding with disposable numeric fixtures. The browser tests exercised the panel's narrow layout, manual refresh and performance disclosure. The native desktop walkthrough is pending.
