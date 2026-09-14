"""Single-job lock — one read run at a time, everywhere.

What-if workshop delta #3: two open windows (or a browser run + the QA gate's
API call) produce two simultaneous jobs on the same service — interleaved
logs, mixed states, confusing results. The lock is a plain advisory file
lock (fcntl.flock) around the processing body:

- acquired → the run proceeds; PID + start time are written for diagnostics.
- held by another job → JobBusyError, which the app turns into a clear
  Arabic message («يوجد تشغيل جارٍ الآن…») instead of silent interference.

flock semantics: locks attach to the open file description, so a second
acquisition — another process OR another thread with its own fd — fails
immediately (LOCK_NB). Released automatically on process death.
"""
from __future__ import annotations

import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path


class JobBusyError(RuntimeError):
    """Another processing job currently holds the lock."""


@contextmanager
def job_lock(path: str | Path):
    """Acquire the single-job lock or raise JobBusyError."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        fh.close()
        raise JobBusyError(f"another job holds {path}") from e
    try:
        fh.write(f"pid={os.getpid()} started={time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.flush()
        yield
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        finally:
            fh.close()
