# Workbench 0.12.12 native follow-up

On 2026-11-26, the Codex and ZCode native plugin managers updated their existing Workbench registrations from 0.12.11 to 0.12.12 on macOS 27.2.1. The managed manifests and entry points matched [Hub revision `cd7dad43`](https://github.com/TeFuirnever/azhou-ai-hub/commit/cd7dad43146221bf9311d5a6ea26e886e72279d3). The private receipt retains the previous plugin payloads.

## ZCode Desktop 4.0.0

After restarting ZCode, the composer opened Workbench in a pane about 240 pixels wide in the capture. The same panel showed an empty draft and then showed the restored test conversation's own rate and turn duration. The disclosure remained open across the theme change and another live request. The request count increased from one to two, and the dashboard showed a completion time.

The composer still said it was waiting after the model response ended. That test exposed a gap between the final model event and usage reaching the database. The 0.12.13 regression exercises the final event before the completed row arrives, a final event without a rate, and a late final event for an older request.

## Codex Desktop 26.1120.50957

The 0.12.12 Codex cache matched the deployed panel and server. Codex App Server selected the right data across A → B → A. A separate live Codex session called the installed Workbench and received its last completed turn during the next turn. Desktop sidebar interactions still need a manual walkthrough.
