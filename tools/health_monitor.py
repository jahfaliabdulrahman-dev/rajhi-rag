#!/usr/bin/env python3
"""Light periodic monitor (what-if H3) — records the truth, changes NOTHING.

Runs from launchd every 10 minutes and appends ONE line to
~/Library/Logs/rajhi-health.log:

    2026-09-14 10:30:00 OK app=up redirect=up source=ok

It NEVER restarts anything: a kickstart can kill the owner's in-flight
processing run (a hard ops rule). Its job is fast diagnosis — open the log
and you immediately see since when the surface has been down.
Log is kept bounded (last ~400 lines).

**والمصدرُ يُقاس أيضًا (R107-2 · المرّةُ الثالثة R89-2 · R94-2):** كان المراقبُ يكتب «OK» بينما
مجلّدُ التطبيق على فرعٍ غيرِ مفحوص — لأنّه لا يقرأ **حكمَ المصدر**. والعمليةُ تُقلع من كود المجلّد
عند أيّ توقّف (`KeepAlive` + `RunAtLoad`) ⇒ فالمخاطرةُ حقيقيّةٌ ولا يراها أحد.
**فالحالةُ الثالثةُ `STALE`:** التطبيقُ يعمل، **ولا** يعمل على كود هذه الشجرة. وبلا حكمٍ لا يُقال
«سليم»: تعذُّرُ قراءةِ الحكم **رفضٌ مسمًّى** لا تمرير. **ولا يُعاد تشغيلُ شيء** — ينبّه فقط، كتصميمه.
"""
from __future__ import annotations

import http.client
import subprocess
import sys
import time
from pathlib import Path

LOG = Path.home() / "Library" / "Logs" / "rajhi-health.log"
#: أحوالُ السطر: `OK` (ثلاثةُ شروط) · `STALE` (يعملُ على كودٍ غيرِ كودِ الشجرة) · `DOWN`.
STATES = ("OK", "STALE", "DOWN")


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
    """The state recorded by the previous run ('OK' / 'STALE' / 'DOWN'), or None."""
    for line in reversed((log_text or "").splitlines()):
        parts = line.split()
        if len(parts) >= 3 and parts[2] in STATES:
            return parts[2]
    return None


def state_of(app_up: bool, redirect_up: bool, prov_ok: bool) -> str:
    """**قاعدةُ الحالة (R107-2):** لا `OK` إلّا بثلاثةٍ — التطبيقُ يجيب · القالبُ يحوّل ·
    **والتطبيقُ الجاري على كود هذه الشجرة**. ونجاحُ الأولَين مع مخالفةِ الكود ليس «سليماً»:
    هو `STALE`، لأنّ أيَّ توقّفٍ للعملية يُقلعها من كود المجلّد (كودٌ لم يُقَس).
    """
    if not (app_up and redirect_up):
        return "DOWN"
    return "OK" if prov_ok else "STALE"


def provenance_state() -> tuple[bool, str]:
    """(مطابق؟ · سببُ الرفض) — **بحكم المصدر القائم** (`tools/qa_gate._provenance_verdict`) ولا آليّةَ
    جديدة: الدوالُّ موجودةٌ ومقيسة، والمراقبُ يقرؤها وحدَها.

    **وتعذُّرُ القراءةِ رفضٌ مسمًّى لا تمرير:** غيابُ القياس ليس نظافة.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from qa_gate import (_app_code_stamp, _listener_pid, _provenance_verdict,
                             _tree_code_hash, _tree_head)
        refusal = _provenance_verdict(_app_code_stamp(), _tree_head(),
                                      _tree_code_hash(), _listener_pid())
    except Exception as e:                       # noqa: BLE001
        return False, f"تعذّر قراءةُ حكم المصدر ({type(e).__name__})"
    return (refusal is None), (refusal or "")


def transition(prev: str | None, now: str) -> str:
    """'' | 'down' | 'stale' | 'up' — speak ONLY when something changed.

    A monitor that notifies on every tick is a monitor whose notifications get
    muted, so the notification is tied to a state CHANGE (audit P3-8). The
    first line ever written is not a change: there is nothing to compare with.
    **و`STALE` حالةٌ ثالثة** (يعملُ على كودٍ غيرِ كودِ الشجرة) — تُنبّه كالتوقّف، **ولا تُقرأ «عاد»**.
    """
    if prev is None or prev == now:
        return ""
    return {"DOWN": "down", "STALE": "stale"}.get(now, "up")


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
    prov_ok, why = provenance_state()
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    state = state_of(app_up, redirect_up, prov_ok)
    try:
        prev = last_state(LOG.read_text(encoding="utf-8"))
    except OSError:
        prev = None
    line = (f"{stamp} {state} app={'up' if app_up else 'down'} "
            f"redirect={'up' if redirect_up else 'down'} "
            f"source={'ok' if prov_ok else 'stale'}\n")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line)
    change = transition(prev, state)
    if change == "down":
        notify("rajhi-rag توقف",
               "سطح التطبيق لا يستجيب — افتح tools/health_check.py للتشخيص")
        print(f"{stamp} NOTIFY down (كان {prev})")
    elif change == "stale":
        # **ولا إعادةَ تشغيل:** المالكُ يقرّر. والسببُ يُذكر مختصرًا في الإشعار.
        notify("rajhi-rag على كودٍ غيرِ المجلّد", (why or "")[:180]
               or "التطبيقُ الجاري ليس على كود هذه الشجرة")
        print(f"{stamp} NOTIFY stale: {why}")
    elif change == "up":
        notify("rajhi-rag عاد", "سطح التطبيق يعمل من جديد")
        print(f"{stamp} NOTIFY recovered")
    lines = LOG.read_text(encoding="utf-8").splitlines()
    if len(lines) > 500:
        LOG.write_text("\n".join(lines[-400:]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
