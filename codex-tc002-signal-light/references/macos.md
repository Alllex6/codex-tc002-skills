# macOS installation

1. Locate Python 3.9+ with `command -v python3` and use that absolute path.
2. Copy both Python files to `~/Library/Application Support/CodexPixdeck/`.
3. Create `~/Library/LaunchAgents/com.<user>.codex-pixdeck-watcher.plist` with absolute arguments.
4. Include `RunAtLoad=true`, `KeepAlive=true`, `ProcessType=Background`, and stdout/stderr paths under `~/Library/Logs/`.
5. Load with `launchctl bootstrap gui/$(id -u) <plist>` and restart with `launchctl kickstart -k gui/$(id -u)/<label>`.
6. Verify with `launchctl print gui/$(id -u)/<label>` and inspect the log.

Do not point the LaunchAgent at a script under Desktop, Documents, or Downloads. macOS privacy/TCC may return `Operation not permitted` even when interactive execution succeeds.

When replacing an existing definition, `bootout` it before `bootstrap`. Use a per-user LaunchAgent, not a system daemon, so it can access the user's Codex session directory.
