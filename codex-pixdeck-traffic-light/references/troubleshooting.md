# Troubleshooting

## Device never changes

Call `/getBase`. A timeout usually means the IP changed, subnets differ, guest Wi-Fi isolates clients, a VPN changed routing, or a firewall blocked access.

If logs show `Operation not permitted`, launch from Terminal/PowerShell and grant Local Network/firewall access.

## Manual colors work but automation does not

Manual success proves only bitmap rendering and HTTP. Confirm the watcher stays alive and `--sessions-dir` points to the active Codex home.

Do not depend on `hooks.json` or Ulanzi Studio unless the installed version explicitly guarantees the needed behavior.

## Red never appears

Use a real unresolved permission request. The watcher recognizes permission calls and holds red until their matching tool output arrives.

Scan rollout files directly; a thread database may discover a session only after a short approval has ended.

## Red remains forever

Check all sessions for an actual pending approval. Red intentionally overrides yellow. Stale incomplete logs expire after `--stale-seconds` (default 900).

## Yellow remains after completion

Look for another active turn. One completed test must not show green while other work continues. Crash-truncated logs expire through the stale timeout.

## Red/yellow flicker

Keep `--debounce` near 0.4 seconds. JSONL may be observed between a permission call and its next line.

## DONE enters standby despite new work

Cancel the idle deadline immediately when any active state appears, and recheck all live sessions after five seconds.

## Payload invariant

Every frame must be shaped as `{"duration":1,"draw":[{"db":[0,0,52,16,pixels]}]}` where `pixels` is an actual array of exactly 832 integers.
