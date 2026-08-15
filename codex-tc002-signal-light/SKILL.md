---
name: codex-tc002-signal-light
description: Build, diagnose, install, and verify a reliable Codex task-status traffic light on an Ulanzi U-Clock TC002/PixDeck device using its HTTP Custom App API. Use when an AI must implement RUN/approval/DONE lights, parse Codex rollout JSONL logs, prevent one-second red flashes, support multiple Codex sessions, or install an auto-start watcher on Windows or macOS.
---

# Codex TC002 Signal Light

Implement the complete integration; do not stop after generating a bitmap demo. Detect Codex state, aggregate all recent sessions, push persistent frames, install an OS-native background process, and verify a real approval cycle.

Read [references/protocol-and-state.md](references/protocol-and-state.md) before writing the Python programs. Read exactly one platform guide before installing: [references/macos.md](references/macos.md) or [references/windows.md](references/windows.md).

## Required outcome

Implement this state machine:

| Agent condition | Internal state | Display |
|---|---|---|
| At least one approval dialog is unanswered | `permission` | Bright red lamp, `ASK` |
| No approval; at least one turn is active | `running` | Bright yellow lamp, `RUN` |
| Last active turn finishes | `done` | Bright green lamp, `DONE` for 5 seconds |
| Five seconds after done | `idle` | Three dim lamps or black standby |

Aggregate multiple sessions with strict priority: `permission > running > done > idle`. Never let activity in one task hide an unanswered approval in another.

An approval must remain red for exactly as long as it is unresolved. Do not use a fixed three-second approximation. Switch back to yellow only after the matching approval tool call has actually returned. A denial also resolves the dialog and may return to yellow while the agent processes it.

## Build two dependency-free Python programs

Create `codex_task_traffic_light.py` and `codex_pixdeck_watcher.py`. Use Python 3.9+ standard library only.

In the renderer:

- Draw a 52×16 integer bitmap using `0xRRGGBB` values.
- POST JSON to `http://DEVICE/api/custom?name=APP` with `Content-Type: application/json`.
- Use `{"duration":3600,"draw":[{"db":[0,0,52,16,...832 pixels...]}]}`.
- Never use `duration: 1`; it causes ASK to flash for one second and fall back to stale RUN content.
- Expose `--device`, `--app`, `--state`, `--state-file`, `--once`, `--timeout`, and `--done-off-delay`.
- Bypass environment HTTP proxies for LAN requests with `urllib.request.ProxyHandler({})`.

In the watcher:

- Discover recent `rollout-*.jsonl` files recursively below the Codex sessions directory.
- Default sessions directory to `%USERPROFILE%\.codex\sessions` on Windows and `~/.codex/sessions` on macOS. Allow `--sessions-dir` and `CODEX_HOME` overrides.
- Poll every 0.2 seconds and debounce transitions for about 0.4 seconds.
- Ignore stale rollout files, but use a configurable timeout such as 900 seconds.
- Re-push the current non-idle state every 2 seconds. This repairs display takeover by another PixDeck app or integration.
- On transition to no active sessions, push `done`, wait 5 seconds, recheck for activity, then push `idle` only if still inactive.
- Catch network and malformed-log errors, log them, and retry without exiting.

## Parse approvals correctly

Treat a new `event_msg/user_message` as an active turn. Treat `event_msg/task_complete` as complete.

Codex Desktop may encode permission requests in several forms. Recognize all of these:

1. A `response_item` whose `type` is `custom_tool_call` or `function_call` and whose `name` is exactly `request_permissions`.
2. A wrapped outer `exec` call whose `input` contains the executable expression `tools.request_permissions(`. Match with a narrow regex such as `\btools\.request_permissions\s*\(`; do not match ordinary prose containing the word `request_permissions`.
3. A wrapped command whose arguments contain `sandbox_permissions` with `require_escalated`.

Add its `call_id` to a pending-approval set.

Do not clear a pending approval merely because a `custom_tool_call_output` appeared. Approval-gated execution often first returns:

```text
Script running with cell ID 22
```

That is a continuation handle, not completion. Map the cell ID to the original approval call. Track later `wait` or `write_stdin` calls by `cell_id`/`session_id`; clear the original pending approval only when the matching continuation output no longer says `Script running with cell ID`. Clear all per-turn tracking on `task_complete`.

Outputs may be plain strings or arrays of content blocks. Flatten both before inspecting them.

## Install reliably

Do not run the watcher only inside an interactive Codex tool session. Such a child process can disappear when the task or host ends.

- On macOS, install a LaunchAgent with `RunAtLoad` and `KeepAlive`. Put runtime copies under `~/Library/Application Support/CodexPixdeck/`; macOS privacy controls can prevent a background LaunchAgent from reading scripts stored under `Documents`. Log to `~/Library/Logs/codex-pixdeck-watcher.log`.
- On Windows, install a Task Scheduler task that starts at user logon, restarts on failure, runs hidden, and uses absolute paths. Store runtime files under `%LOCALAPPDATA%\CodexPixdeck` and logs there. Do not depend on the current working directory.

Always preserve an editable source copy separately from the installed runtime copy. When updating, copy both Python files together and restart the service.

## Validate before declaring success

Perform all checks:

1. Query `http://DEVICE/getBase` and confirm the TC002 is reachable.
2. Manually push `running`, `permission`, `done`, and `idle` frames.
3. Unit-test approval parsing with synthetic JSONL for:
   - wrapped `tools.request_permissions(` detection;
   - ordinary prose not causing a false approval;
   - asynchronous `Script running with cell ID` remaining red;
   - matching continuation completion clearing red;
   - multiple sessions where permission outranks running.
4. Start the installed service and confirm its process/service status plus log output.
5. Trigger a harmless real permission request. Leave the dialog unanswered for at least ten seconds and verify red remains visible continuously. Approve or deny and verify yellow returns promptly.
6. Finish the turn and verify green appears for five seconds, then standby.
7. Wait through at least one two-second refresh and confirm another display update cannot permanently overwrite the signal light.

Do not claim success from parser logs alone; verify that the HTTP push succeeded and ask the user to confirm the physical display.

## Diagnose failures

Use this order:

1. Background service absent or stopped.
2. Service cannot read the script/session directory because of OS privacy or account context.
3. Incorrect TC002 IP, Custom App name, proxy routing, or device offline.
4. Another process repeatedly overwriting the Custom App.
5. A new rollout event shape not recognized by the parser.
6. Frame `duration` too short.

Inspect raw JSONL records around the failed approval before expanding match rules. Prefer exact structural or executable-pattern matches over broad substring searches to avoid false red lights.

## Handoff

Report the installed service name, runtime paths, log path, TC002 address/App name, refresh interval, and results of the real approval and completion tests. State clearly whether Codex itself must restart; normally only the watcher service needs restarting unless hook configuration changed.
