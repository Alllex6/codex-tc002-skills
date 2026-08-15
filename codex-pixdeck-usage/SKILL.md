---
name: codex-pixdeck-usage
description: Read a local Codex user's current Weekly limit from session rate-limit events and display the remaining percentage on a Ulanzi TC002/PixDeck-compatible pixel clock over direct HTTP. Use for one-off pushes, persistent change-triggered monitoring, device connectivity troubleshooting, or creating the same setup on Windows or macOS. Do not use MQTT unless the user explicitly requests it.
---

# Codex weekly usage → PixDeck clock

Use this skill to show the current Codex **Weekly limit remaining** on a 52×16 Ulanzi TC002-compatible clock. The bundled script is dependency-free and works on macOS and Windows with Python 3.9+.

The normal path is direct HTTP to the device's PixDeck-compatible DIY endpoint. This deliberately avoids MQTT and a local broker.

## Required inputs

- Clock IP address, for example `192.168.10.214`.
- The computer running Codex and the clock must be on the same LAN.
- PixDeck/DIY custom components must be enabled on the clock.

Use the local Codex directory by default:

- macOS: `~/.codex`
- Windows: `%USERPROFILE%\.codex`

The script selects the newest `token_count` session event with the weekly, 10,080-minute (`window_minutes=10080`) rate-limit window. It displays remaining, not used, percent.

## Run it

Copy or run `scripts/codex_pixdeck_usage.py`.

macOS/Linux:

```sh
python3 scripts/codex_pixdeck_usage.py --device 192.168.10.214 --once
python3 scripts/codex_pixdeck_usage.py --device 192.168.10.214 --watch --interval 60
```

Windows PowerShell:

```powershell
py .\scripts\codex_pixdeck_usage.py --device 192.168.10.214 --once
py .\scripts\codex_pixdeck_usage.py --device 192.168.10.214 --watch --interval 60
```

`--once` always pushes the current value. `--watch` scans periodically and pushes only when the value has changed, or when a prior push failed. It persists the last successful value in the user's cache directory, so restarting the process does not cause unnecessary redraws.

Use `--codex-dir PATH` when Codex state lives elsewhere, and `--app NAME` to choose a different DIY component name.

## Verify before diagnosing

1. Read the script output. It must say `pushed weekly remaining: ...`.
2. Confirm `http://<clock-ip>/getBase` responds from the same computer. If it does not, treat the device as offline or on a different network.
3. Check PixDeck's target is the same IP and its transport is **HTTP**, not MQTT.
4. Confirm the clock is currently showing the selected DIY component. A successful HTTP request registers the component but does not override a different app selected on the device.

Do not claim a push succeeded from a local script exit alone: verify the HTTP response and, when available, query `/api/customList` to confirm the configured app appears.

## Failure handling

- `No Codex weekly rate-limit data found`: run any Codex task once, then retry; do not guess a value from old screenshots.
- `Weekly window not found`: keep the raw `rate_limits` field for inspection; do not substitute a 5-hour window.
- Connection timeout/refused: leave the last-success state unchanged so `--watch` retries when the clock is back online.
- `403`/`404`: verify firmware, local network, and that the target implements the TC002/PixDeck HTTP DIY API.
- Do not start, configure, or depend on an MQTT broker for this skill.

## Automation guidance

For Codex desktop heartbeats or scheduled tasks, run this skill every minute. The task should invoke `--watch` continuously only when a long-lived local process is appropriate; otherwise invoke `--once` after detecting a changed value and retain the success state file. On device recovery, force one `--once` push so the display catches up.
