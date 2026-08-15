#!/usr/bin/env python3
"""Push Codex task status frames to a Pixdeck/TC002 device."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

WIDTH, HEIGHT = 52, 16
FRAME_DURATION = 3600  # Match Ulanzi's persistent Custom App state pattern.
BLACK = 0x000000
DIM_RED, DIM_YELLOW, DIM_GREEN = 0x240000, 0x242000, 0x002400
BRIGHT_RED, BRIGHT_YELLOW, BRIGHT_GREEN = 0xFF2020, 0xFFD800, 0x20E850
WHITE = 0xE8E8E8

ALIASES = {
    "running": "running", "working": "running", "run": "running",
    "permission": "permission", "approval": "permission", "ask": "permission",
    "done": "done", "finished": "done", "complete": "done",
    "idle": "idle", "standby": "idle", "off": "idle",
}

# Compact 3x5 bitmap font; 1 means a lit pixel.
FONT = {
    "A": ("010", "101", "111", "101", "101"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "K": ("101", "110", "100", "110", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "U": ("101", "101", "101", "101", "111"),
}


def normalize_state(text: str) -> str:
    """Find a supported state word in free-form text."""
    words = text.lower().replace("_", " ").replace("-", " ").split()
    # Prefer approval over other words when logs contain several state names.
    for canonical in ("permission", "done", "running", "idle"):
        for word in words:
            if ALIASES.get(word.strip(".,:;!?()[]{}\"'")) == canonical:
                return canonical
    raise ValueError("no supported state found (running/permission/done and aliases)")


def set_pixel(pixels: list[int], x: int, y: int, color: int) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        pixels[y * WIDTH + x] = color


def draw_lamp(pixels: list[int], cx: int, cy: int, color: int) -> None:
    """Draw a small round lamp with a dark housing."""
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            distance = dx * dx + dy * dy
            if distance <= 16:
                set_pixel(pixels, cx + dx, cy + dy, 0x101010)
            if distance <= 9:
                set_pixel(pixels, cx + dx, cy + dy, color)


def draw_text(pixels: list[int], text: str, x: int, y: int, color: int) -> None:
    for char in text:
        glyph = FONT[char]
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    set_pixel(pixels, x + gx, y + gy, color)
        x += 4


def make_pixels(state: str) -> list[int]:
    pixels = [BLACK] * (WIDTH * HEIGHT)
    colors = [DIM_RED, DIM_YELLOW, DIM_GREEN]
    label = ""
    if state == "permission":
        colors[0], label = BRIGHT_RED, "ASK"
    elif state == "running":
        colors[1], label = BRIGHT_YELLOW, "RUN"
    elif state == "done":
        colors[2], label = BRIGHT_GREEN, "DONE"

    for cx, color in zip((6, 16, 26), colors):
        draw_lamp(pixels, cx, 7, color)
    if label:
        text_width = len(label) * 4 - 1
        draw_text(pixels, label, 51 - text_width, 5, WHITE)
    return pixels


def push_frame(device: str, app: str, state: str, timeout: float) -> None:
    # A one-second frame falls through to the device's previous Custom App
    # content, which makes ASK appear as a brief red flash followed by stale RUN.
    # Keep the current state visible; the watcher explicitly replaces it on the
    # next state transition.
    payload = {
        "duration": FRAME_DURATION,
        "draw": [{"db": [0, 0, WIDTH, HEIGHT, make_pixels(state)]}],
    }
    url = f"http://{device}/api/custom?name={quote(app, safe='')}"
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        response.read()
        if not 200 <= response.status < 300:
            raise RuntimeError(f"device returned HTTP {response.status}")


def send_state(args: argparse.Namespace, state: str) -> None:
    push_frame(args.device, args.app, state, args.timeout)
    print(f"sent {state} to {args.device} ({args.app})", flush=True)
    if state == "done":
        time.sleep(args.done_off_delay)
        push_frame(args.device, args.app, "idle", args.timeout)
        print("sent idle (three dim lamps)", flush=True)


def read_state_file(path: Path) -> str:
    return normalize_state(path.read_text(encoding="utf-8", errors="replace"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default=os.environ.get("PIXDECK_DEVICE", "10.10.20.95"), help="TC002 host or IP")
    parser.add_argument("--app", default="codex_task", help="Pixdeck custom app name")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--state", help="running, permission, done, or a supported alias")
    group.add_argument("--state-file", type=Path, help="file containing state text")
    parser.add_argument("--once", action="store_true", help="push once; otherwise watch --state-file")
    parser.add_argument("--done-off-delay", type=float, default=5.0, help="seconds before dim standby")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="state-file polling interval")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    args = parser.parse_args()
    if args.done_off_delay < 0 or args.poll_interval <= 0 or args.timeout <= 0:
        parser.error("delays must be non-negative and intervals/timeouts must be positive")
    if args.state and not args.once:
        args.once = True  # A literal state has nothing to monitor.
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.state:
            send_state(args, normalize_state(args.state))
            return 0
        if args.once:
            send_state(args, read_state_file(args.state_file))
            return 0

        last_state = None
        print(f"watching {args.state_file}; press Ctrl+C to stop", flush=True)
        while True:
            try:
                state = read_state_file(args.state_file)
                if state != last_state:
                    send_state(args, state)
                    last_state = state
            except (OSError, ValueError) as exc:
                print(f"waiting for a valid state: {exc}", file=sys.stderr, flush=True)
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, HTTPError, URLError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
