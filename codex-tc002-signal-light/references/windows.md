# Windows installation

1. Find Python with `py -3` or `where python`; resolve the absolute executable path.
2. Copy both Python files to `%LOCALAPPDATA%\CodexPixdeck`.
3. Create a wrapper command or PowerShell script using absolute paths, `--sessions-dir "%USERPROFILE%\.codex\sessions"`, the device IP, App name, and `--refresh-seconds 2`.
4. Register a Task Scheduler task for the current user:
   - trigger at logon;
   - run whether the window is visible or hidden;
   - restart on failure;
   - working directory `%LOCALAPPDATA%\CodexPixdeck`;
   - redirect stdout/stderr to a log in the same directory.
5. Start the task and verify with `Get-ScheduledTask`, `Get-ScheduledTaskInfo`, and the log.

Prefer Task Scheduler over a Startup-folder console window. Quote every path because user and AppData paths may contain spaces. Do not use drive-relative paths. Allow outbound private-network access to TCP port 80 on the TC002; add a narrowly scoped Windows Firewall rule only when connection tests demonstrate it is needed.

If the task works interactively but not at logon, compare the task account, Python path, working directory, environment variables, and access to `%USERPROFILE%\.codex\sessions`.
