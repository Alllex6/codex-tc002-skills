---
name: codex-pixdeck-traffic-light
description: Build, install, test, or troubleshoot an automatic Codex task-status traffic light on a Pixdeck/TC002 pixel display over HTTP. Use for RUN (yellow), permission ASK (red), DONE (green), five-second dim-icon standby, multi-session aggregation, or portable Windows/macOS deployment using only Python standard-library code.
---

# Codex Pixdeck Traffic Light

Implement two independent layers: a deterministic bitmap sender and a long-running Codex state watcher. Never treat a manually played color sequence as proof that automatic monitoring works.

## Required state machine

Apply this aggregate priority across all live Codex turns:

1. If any turn has an unresolved permission request, display red `ASK`.
2. Otherwise, if any turn is executing, display yellow `RUN`.
3. When the last executing turn completes, display green `DONE`.
4. After five seconds, recheck. If still empty, retain three dim red/yellow/green lamp icons.
5. If work starts during the five-second grace period, cancel standby and display `RUN` immediately.

An approval resolution is not completion: return to yellow if that turn continues. Do not show green while another turn remains active.

## Workflow

### Verify the device

Require the computer and TC002 to share a reachable LAN. Verify:

```text
GET http://DEVICE_IP/getBase
GET http://DEVICE_IP/api/customList
```

Treat a timeout as a network/IP/subnet/firewall issue before changing bitmap code.

### Test bitmap delivery separately

Copy `scripts/codex_task_traffic_light.py` to the target computer and run:

```bash
python codex_task_traffic_light.py --device DEVICE_IP --state running --once
python codex_task_traffic_light.py --device DEVICE_IP --state permission --once
python codex_task_traffic_light.py --device DEVICE_IP --state done --once
```

Confirm yellow, red, green, then dim icons. This proves HTTP and rendering only.

### Install automatic monitoring

Copy both bundled scripts into the same directory. Start the watcher outside a restricted AI-command sandbox:

```bash
python codex_pixdeck_watcher.py --device DEVICE_IP
```

The watcher uses `${CODEX_HOME}/sessions` when set, otherwise `~/.codex/sessions`. This resolves naturally on Windows and macOS.

Read [references/platform-setup.md](references/platform-setup.md) for OS startup configuration. Read [references/troubleshooting.md](references/troubleshooting.md) when behavior differs from the state machine.

### Validate automatically

Create one harmless Codex turn that works, requests read-only permission, resumes, and finishes. Observe watcher logs and the physical display. Expected transitions:

```text
running -> permission
permission -> running
running -> None
done -> idle
```

Use two overlapping turns to validate aggregation: red while any approval is pending; otherwise yellow while any work remains.

## Guardrails learned from implementation

- Use only the Python standard library.
- POST to `http://DEVICE_IP/api/custom?name=codex_task` with JSON content type.
- Render 52×16 as exactly 832 `0xRRGGBB` integers; draw glyphs instead of device fonts.
- Discover rollout JSONL files directly. A thread database can lag beyond a short approval window.
- Keep the watcher independent of Ulanzi Studio and Codex hooks; either may be closed, cached, unsupported, delayed, or sandboxed.
- Run the networked watcher from Terminal, PowerShell, Task Scheduler, or launchd. An AI sandbox may deny LAN requests with `Operation not permitted`.
- Debounce status for about 400 ms to prevent red/yellow flicker during partial log writes.
- Retry failed pushes without marking the target state delivered.
- Ignore stale incomplete rollout files after a bounded interval; default to 15 minutes.
- Recheck live state before entering standby; never use an unconditional DONE sleep in the watcher.

## Bundled scripts

- `scripts/codex_task_traffic_light.py`: bitmap renderer and one-shot/state-file sender.
- `scripts/codex_pixdeck_watcher.py`: cross-platform rollout monitor and multi-session aggregator.
