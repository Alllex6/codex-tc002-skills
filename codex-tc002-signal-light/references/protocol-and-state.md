# TC002 protocol and state reference

## HTTP API

Use `POST http://<device>/api/custom?name=<url-encoded-app>` with JSON content. A bitmap draw command is:

```json
{"duration":3600,"draw":[{"db":[0,0,52,16,0,0,0]}]}
```

Append exactly 832 color integers after the first four `db` values. Each color is `0xRRGGBB`. Use a persistent duration and replace the frame explicitly on every state change.

Useful read-only checks:

- `GET /getBase`
- `GET /api/customList`
- `GET /getMqttConfig` when MQTT is involved

The HTTP Custom App update may compete with MQTT, a usage monitor, Home Assistant, or another process. Periodic re-push is therefore part of correctness, not merely cosmetic.

## Suggested colors

- black: `0x000000`
- dim red/yellow/green: `0x240000`, `0x242000`, `0x002400`
- bright red/yellow/green: `0xFF2020`, `0xFFD800`, `0x20E850`
- label: `0xE8E8E8`

## Rollout records

Each line is standalone JSON with top-level `type` and `payload`. Only process valid dictionaries and tolerate partial writes/malformed lines.

Approval correlation needs three maps/sets:

- `pending_approvals: set[call_id]`
- `approval_cells: dict[cell_id, approval_call_id]`
- `wait_cells: dict[wait_call_id, cell_id]`

The latest active turn state is `permission` if `pending_approvals` is nonempty, otherwise `running`. A completed turn is `None`. Aggregate files after computing each file independently.

## Lessons from the reference implementation

- A one-second frame caused a visible one-second red flash even when parsing was correct.
- Clearing approval on the first tool output was wrong because that output often only yielded a cell handle.
- Matching the bare word `request_permissions` produced false positives when an AI discussed or edited the watcher itself.
- A watcher launched inside a Codex session was not a durable service.
- macOS LaunchAgents could not execute a script stored under `Documents`; moving the runtime copy to Application Support fixed it.
- A second TC002 integration could overwrite the screen; refreshing the current state every two seconds made the display self-healing.
