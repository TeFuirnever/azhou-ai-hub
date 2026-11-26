# Workbench 0.12.13 verification

On 2026-11-26, the Codex and ZCode native managers updated their existing Workbench registrations to 0.12.13 on macOS 27.2.1. The installed manifests and checked entry points matched [Hub revision `81bb1538`](https://github.com/TeFuirnever/azhou-ai-hub/commit/81bb15384a257468356c2a18c71a2cffafceeca8). The previous payloads remain in the private install record. Both [PR #604](https://github.com/TeFuirnever/azhou-ai-hub/pull/604) and its [Pages deployment](https://github.com/TeFuirnever/azhou-ai-hub/actions/runs/45765703668) completed.

## ZCode Desktop 4.0.0

After a restart, the maintainer Mac reloaded Workbench and ran another short request in the conversation that reproduced the stale waiting notice. The composer showed the finished segment and total turn time. The dashboard request count increased from two to three with Performance details still open.

## Codex Desktop 26.1120.50957

The installed panel and server matched the release. Codex App Server verified A → B → A session binding. A live `session_performance` call reported a running turn and returned the last completed turn. The browser harness verified success and failure feedback, opening and closing details, and the open state surviving refresh.

Manual refresh and disclosure in the native 0.12.13 desktop sidebar remain unverified. The computer-use surface blocks interaction with the Codex window. To complete the check, finish a short turn in a fresh Codex Desktop chat, ask Workbench for the current session's performance, then open the result card. Expand Performance details and click Refresh. Confirm that the panel reports the result, the details remain open, and the disclosure still closes and reopens.
