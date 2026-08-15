#!/usr/bin/env python3
"""Poll Codex rollout logs and push aggregate live status to Pixdeck."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from codex_task_traffic_light import push_frame


def default_sessions_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return Path(codex_home).expanduser() / "sessions" if codex_home else Path.home() / ".codex" / "sessions"


def recent_rollouts(sessions_dir: Path, since_seconds: float) -> list[Path]:
    """Discover rollout files directly; the thread database can lag behind."""
    paths = []
    for path in sessions_dir.glob("*/*/*/rollout-*.jsonl"):
        try:
            if path.stat().st_mtime >= since_seconds:
                paths.append(path)
        except OSError:
            pass
    return paths


def rollout_state(path: Path) -> str | None:
    """Return permission/running, or None when the latest turn is complete."""
    turn_active = False
    pending_approvals: set[str] = set()
    approval_cells: dict[str, str] = {}
    wait_cells: dict[str, str] = {}

    def output_text(value: object) -> str:
        """Flatten tool output, which may be a string or content-block list."""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(
                str(block.get("text", ""))
                for block in value
                if isinstance(block, dict)
            )
        return str(value or "")

    try:
        with path.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                kind, payload = item.get("type"), item.get("payload", {})
                if kind == "event_msg" and payload.get("type") == "user_message":
                    turn_active = True
                    pending_approvals.clear()
                    approval_cells.clear()
                    wait_cells.clear()
                elif kind == "response_item" and payload.get("type") in {
                    "custom_tool_call", "function_call"
                }:
                    call_id = payload.get("call_id", "")
                    raw = str(payload.get("input", payload.get("arguments", "")))
                    if (payload.get("name") == "request_permissions"
                            or "require_escalated" in raw
                            or re.search(
                                r"\btools\.request_permissions\s*\(", raw
                            )):
                        pending_approvals.add(call_id)
                    elif payload.get("name") in {"wait", "write_stdin"}:
                        try:
                            arguments = json.loads(raw)
                        except (TypeError, ValueError):
                            arguments = {}
                        cell_id = arguments.get("cell_id", arguments.get("session_id"))
                        if cell_id is not None:
                            wait_cells[call_id] = str(cell_id)
                elif kind == "response_item" and payload.get("type") in {
                    "custom_tool_call_output", "function_call_output"
                }:
                    call_id = payload.get("call_id", "")
                    text = output_text(payload.get("output"))
                    if call_id in pending_approvals:
                        # Approval-gated exec calls often yield before the user
                        # responds.  Their first output is only a cell handle, not
                        # completion, so keep ASK active and follow that cell.
                        match = re.search(r"Script running with cell ID\s+(\S+)", text)
                        if match:
                            approval_cells[match.group(1)] = call_id
                        else:
                            pending_approvals.discard(call_id)
                    cell_id = wait_cells.pop(call_id, None)
                    if cell_id and "Script running with cell ID" not in text:
                        approval_id = approval_cells.pop(cell_id, None)
                        if approval_id:
                            pending_approvals.discard(approval_id)
                elif kind == "event_msg" and payload.get("type") == "task_complete":
                    turn_active = False
                    pending_approvals.clear()
                    approval_cells.clear()
                    wait_cells.clear()
    except OSError:
        return None
    if not turn_active:
        return None
    return "permission" if pending_approvals else "running"


def aggregate(paths: list[Path]) -> str | None:
    states = {state for path in paths if (state := rollout_state(path))}
    if "permission" in states:
        return "permission"
    if "running" in states:
        return "running"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default=os.environ.get("PIXDECK_DEVICE", "10.10.20.95"))
    parser.add_argument("--app", default="codex_task")
    parser.add_argument("--sessions-dir", type=Path, default=default_sessions_dir())
    parser.add_argument("--poll", type=float, default=0.2)
    parser.add_argument("--debounce", type=float, default=0.4)
    parser.add_argument(
        "--permission-min-seconds", type=float, default=0.0,
        help="optional minimum ASK display time; default follows approval exactly",
    )
    parser.add_argument("--recent-hours", type=float, default=24)
    parser.add_argument("--stale-seconds", type=float, default=900)
    parser.add_argument(
        "--refresh-seconds", type=float, default=2.0,
        help="re-push the current frame periodically so other apps cannot overwrite it",
    )
    args = parser.parse_args()
    if args.permission_min_seconds < 0:
        parser.error("--permission-min-seconds must be non-negative")
    sentinel = object()
    last = sentinel
    candidate = sentinel
    candidate_since = time.monotonic()
    idle_deadline = None
    retry_at = 0.0
    refresh_at = 0.0
    permission_visible_until = 0.0
    while True:
        try:
            since = time.time() - args.recent_hours * 3600
            paths = recent_rollouts(args.sessions_dir, since)
            fresh_after = time.time() - args.stale_seconds
            paths = [path for path in paths if path.stat().st_mtime >= fresh_after]
            now = time.monotonic()
            raw_state = aggregate(paths)
            # Start the minimum interval only after the ASK frame was successfully
            # sent. Detection, debounce, HTTP latency and device refresh therefore
            # do not consume any of the user-visible hold time.
            state = (
                "permission"
                if last == "permission" and now < permission_visible_until
                else raw_state
            )
            if state != candidate:
                candidate = state
                candidate_since = now
                # A new task during the DONE grace period cancels standby now,
                # without waiting for debounce or another device request.
                if state is not None:
                    idle_deadline = None
            if (candidate != last
                    and now - candidate_since >= args.debounce
                    and now >= retry_at):
                print(f"state: {last!r} -> {candidate!r}", flush=True)
                try:
                    if candidate is None:
                        push_frame(args.device, args.app, "done", 3)
                        idle_deadline = time.monotonic() + 5
                    else:
                        push_frame(args.device, args.app, candidate, 3)
                        idle_deadline = None
                    last = candidate
                    refresh_at = time.monotonic() + args.refresh_seconds
                    if candidate == "permission":
                        permission_visible_until = (
                            time.monotonic() + args.permission_min_seconds
                        )
                    retry_at = 0.0
                except Exception as exc:
                    print(f"push failed; retrying in 3s: {exc}", flush=True)
                    retry_at = time.monotonic() + 3
            elif (last is not sentinel and last is not None
                    and now >= refresh_at and now >= retry_at):
                try:
                    push_frame(args.device, args.app, last, 3)
                    refresh_at = time.monotonic() + args.refresh_seconds
                except Exception as exc:
                    print(f"refresh failed; retrying in 3s: {exc}", flush=True)
                    retry_at = time.monotonic() + 3
            if idle_deadline is not None and time.monotonic() >= idle_deadline:
                since = time.time() - args.recent_hours * 3600
                paths = recent_rollouts(args.sessions_dir, since)
                fresh_after = time.time() - args.stale_seconds
                paths = [path for path in paths if path.stat().st_mtime >= fresh_after]
                if aggregate(paths) is None:
                    try:
                        push_frame(args.device, args.app, "idle", 3)
                        idle_deadline = None
                        print("state: done -> idle", flush=True)
                    except Exception as exc:
                        print(f"idle push failed; retrying in 3s: {exc}", flush=True)
                        idle_deadline = time.monotonic() + 3
                else:
                    idle_deadline = None
        except Exception as exc:
            print(f"watcher: {exc}", flush=True)
        time.sleep(args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
