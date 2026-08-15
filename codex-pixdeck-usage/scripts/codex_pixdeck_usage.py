#!/usr/bin/env python3
"""Display a local Codex user's Weekly limit remaining on a 52x16 TC002.

Uses only Python's standard library and direct HTTP.  It does not use MQTT.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

WIDTH, HEIGHT, WEEKLY_MINUTES = 52, 16, 10_080
FONT = {
    " ": ("...", "...", "...", "...", "..."),
    "%": ("#.#", "..#", ".#.", "#..", "#.#"),
    "0": ("###", "#.#", "#.#", "#.#", "###"), "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("###", "..#", "###", "#..", "###"), "3": ("###", "..#", ".##", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"), "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"), "7": ("###", "..#", ".#.", ".#.", ".#."),
    "8": ("###", "#.#", "###", "#.#", "###"), "9": ("###", "#.#", "###", "..#", "###"),
    "C": ("###", "#..", "#..", "#..", "###"), "D": ("##.", "#.#", "#.#", "#.#", "##."),
    "E": ("###", "#..", "##.", "#..", "###"), "K": ("#.#", "##.", "#..", "##.", "#.#"),
    "O": ("###", "#.#", "#.#", "#.#", "###"), "W": ("#.#", "#.#", "###", "###", "#.#"),
    "X": ("#.#", "#.#", ".#.", "#.#", "#.#"),
}


def default_codex_dir() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def default_state_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "codex-pixdeck-usage" / "last-success.json"


def timestamp(event: dict[str, Any], fallback: float) -> float:
    raw = event.get("timestamp")
    if isinstance(raw, str):
        try:
            return __import__("datetime").datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return fallback


def find_weekly(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if value.get("window_minutes") == WEEKLY_MINUTES and "used_percent" in value:
            return value
        for child in value.values():
            found = find_weekly(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = find_weekly(child)
            if found:
                return found
    return None


def read_weekly_remaining(codex_dir: Path) -> int:
    newest: tuple[float, dict[str, Any]] | None = None
    for path in codex_dir.glob("sessions/**/*.jsonl"):
        try:
            with path.open("rb") as handle:
                for line in handle:
                    if b'"token_count"' not in line or b'"rate_limits"' not in line:
                        continue
                    try:
                        event = json.loads(line)
                        payload = event.get("payload", {})
                        if payload.get("type") != "token_count":
                            continue
                        limits = payload.get("rate_limits") or {}
                        weekly = find_weekly(limits)
                        if weekly is None:
                            continue
                        item = (timestamp(event, path.stat().st_mtime), weekly)
                        if newest is None or item[0] > newest[0]:
                            newest = item
                    except (json.JSONDecodeError, AttributeError, OSError, TypeError):
                        continue
        except OSError:
            continue
    if newest is None:
        raise RuntimeError(f"No Codex weekly rate-limit data found below {codex_dir}")
    used = max(0.0, min(100.0, float(newest[1]["used_percent"])))
    return round(100.0 - used)


def make_frame(remaining: int) -> dict[str, Any]:
    pixels = [0] * (WIDTH * HEIGHT)

    def draw(text: str, x: int, y: int, color: int) -> None:
        for char in text:
            glyph = FONT.get(char, FONT[" "])
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    px, py = x + gx, y + gy
                    if bit == "#" and 0 <= px < WIDTH and 0 <= py < HEIGHT:
                        pixels[py * WIDTH + px] = color
            x += 4

    color = 0x00FF99 if remaining >= 50 else 0xFFD166 if remaining >= 20 else 0xFF4050
    draw("CODEX", 1, 2, 0xFFFFFF)
    draw(f"WK {remaining}%", 1, 9, color)
    return {"duration": 31_536_000, "draw": [{"db": [0, 0, WIDTH, HEIGHT, pixels]}]}


def request_json(url: str, data: bytes | None = None) -> tuple[int, str]:
    request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    if data:
        request.add_header("Content-Type", "application/json")
    # Ignore developer-environment proxy settings for private-LAN devices.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=8) as response:
        return response.status, response.read().decode("utf-8", "replace")


def push(device: str, app: str, remaining: int, verify: bool) -> None:
    base = device if device.startswith(("http://", "https://")) else "http://" + device
    base = base.rstrip("/")
    if verify:
        request_json(base + "/getBase")
    frame = json.dumps(make_frame(remaining), separators=(",", ":")).encode()
    url = base + "/api/custom?name=" + urllib.parse.quote(app, safe="")
    status, body = request_json(url, frame)
    if not 200 <= status < 300:
        raise RuntimeError(f"clock returned HTTP {status}: {body[:200]}")
    if verify:
        try:
            request_json(base + "/api/customList")
        except urllib.error.URLError:
            # Older firmware may not expose this optional verification endpoint.
            pass


def load_state(path: Path) -> int | None:
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("remaining"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def save_state(path: Path, remaining: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"remaining": remaining, "updated_at": int(time.time())}), encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Clock IP or http://host:port")
    parser.add_argument("--app", default="codex_usage", help="DIY component name")
    parser.add_argument("--codex-dir", type=Path, default=default_codex_dir())
    parser.add_argument("--state-file", type=Path, default=default_state_path())
    parser.add_argument("--once", action="store_true", help="Push once even if unchanged")
    parser.add_argument("--watch", action="store_true", help="Monitor and push on changes")
    parser.add_argument("--interval", type=int, default=60, help="Watch interval in seconds")
    parser.add_argument("--no-verify", action="store_true", help="Skip getBase/customList checks")
    args = parser.parse_args()
    if args.watch and args.interval < 10:
        parser.error("--interval must be at least 10 seconds")
    if not args.once and not args.watch:
        args.once = True

    while True:
        try:
            remaining = read_weekly_remaining(args.codex_dir)
            prior = load_state(args.state_file)
            if args.once or prior != remaining:
                push(args.device, args.app, remaining, not args.no_verify)
                save_state(args.state_file, remaining)
                print(f"pushed weekly remaining: {remaining}%", flush=True)
            else:
                print(f"unchanged: {remaining}%", flush=True)
        except (OSError, RuntimeError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            print(f"push failed: {exc}", file=sys.stderr, flush=True)
            if not args.watch:
                return 1
        if not args.watch:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
