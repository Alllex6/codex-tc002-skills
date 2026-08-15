# Platform setup

## Prerequisites

- Python 3.9 or newer
- TC002 and computer on a mutually reachable LAN
- Pixdeck service enabled
- No third-party Python packages

Replace `DEVICE_IP` in all commands.

## Windows 10 and 11

Test in PowerShell:

```powershell
Invoke-WebRequest http://DEVICE_IP/getBase -UseBasicParsing
Invoke-WebRequest http://DEVICE_IP/api/customList -UseBasicParsing
py -3 .\codex_pixdeck_watcher.py --device DEVICE_IP
```

If `py` is unavailable, use the full `python.exe` path. Approve Windows Defender Firewall access for Private networks if prompted.

For automatic login startup, create a Task Scheduler task:

- Trigger: At log on
- Program: full path to `pythonw.exe` (quiet) or `python.exe` (diagnostic console)
- Arguments: full quoted watcher path plus `--device DEVICE_IP`
- Start in: directory containing both scripts

Use `python.exe` while validating so logs remain visible.

## macOS 12 and newer

Test and run from Terminal:

```bash
curl --max-time 5 http://DEVICE_IP/getBase
curl --max-time 5 http://DEVICE_IP/api/customList
python3 codex_pixdeck_watcher.py --device DEVICE_IP
```

Allow Local Network access if prompted. An AI sandbox may block LAN access even when Terminal works.

For login startup, create a user LaunchAgent with absolute paths to Python and the watcher. Set `RunAtLoad` and `KeepAlive` true, and write stdout/stderr under `~/Library/Logs`. Load it with `launchctl bootstrap gui/$(id -u) PLIST_PATH`.

## Portable directory

Keep both scripts together because the watcher imports the sender:

```text
pixdeck-codex/
  codex_task_traffic_light.py
  codex_pixdeck_watcher.py
```
