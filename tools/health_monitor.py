#!/usr/bin/env python3
"""Light periodic monitor (what-if H3) — records the truth, changes NOTHING.

Runs from launchd every 10 minutes and appends ONE line to
~/Library/Logs/rajhi-health.log:

    2026-09-14 10:30:00 OK app=up redirect=up

It NEVER restarts anything: a kickstart can kill the owner's in-flight
processing run (a hard ops rule). Its job is fast diagnosis — open the log
and you immediately see since when the surface has been down.
Log is kept bounded (last ~400 lines).
"""
from __future__ import annotations

import http.client
import subprocess
import time
from pathlib import Path

LOG = Path.home() / "Library" / "Logs" / "rajhi-health.log"


def _probe(port: int, want_location: str | None = None) -> bool:
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
        conn.request("GET", "/")
        resp = conn.getresponse()
        status, location = resp.status, resp.getheader("Location")
        conn.close()
        if want_location:
            return status == 302 and bool(location) and want_location in location
        return status == 200
    except Exception:  # noqa: BLE001
        return False


def last_state(log_text: str) -> str | None:
    """The state recorded by the previous run ('OK' / 'DOWN'), or None."""
    for line in reversed((log_text or "").splitlines()):
        parts = line.split()
        if len(parts) >= 3 and parts[2] in ("OK", "DOWN"):
            return parts[2]
    return None


def transition(prev: str | None, now: str) -> str:
    """'' | 'down' | 'up' — speak ONLY when something changed.

    A monitor that notifies on every tick is a monitor whose notifications get
    muted, so the notification is tied to a state CHANGE (audit P3-8). The
    first line ever written is not a change: there is nothing to compare with.
    """
    if prev is None or prev == now:
        return ""
    return "down" if now == "DOWN" else "up"


def notify(title: str, message: str) -> bool:
    """A macOS notification: the monitor still RESTARTS nothing (a kickstart
    can kill the owner's in-flight run) — but «records the truth» was never
    enough when nobody watches the file."""
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{message}" '
                        f'with title "{title}"'],
                       capture_output=True, timeout=5, check=False)
        return True
    except Exception:  # noqa: BLE001
        return False


def main() -> None:
    app_up = _probe(7860)
    redirect_up = _probe(7867, want_location="7860")
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    state = "OK" if app_up and redirect_up else "DOWN"
    try:
        prev = last_state(LOG.read_text(encoding="utf-8"))
    except OSError:
        prev = None
    line = (f"{stamp} {state} app={'up' if app_up else 'down'} "
            f"redirect={'up' if redirect_up else 'down'}\n")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line)
    change = transition(prev, state)
    if change == "down":
        notify("rajhi-rag توقف",
               "سطح التطبيق لا يستجيب — افتح tools/health_check.py للتشخيص")
        print(f"{stamp} NOTIFY down (كان {prev})")
    elif change == "up":
        notify("rajhi-rag عاد", "سطح التطبيق يعمل من جديد")
        print(f"{stamp} NOTIFY recovered")
    lines = LOG.read_text(encoding="utf-8").splitlines()
    if len(lines) > 500:
        LOG.write_text("\n".join(lines[-400:]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
