#!/usr/bin/env python3
"""Health check — the FIRST step before any «التطبيق خرب» diagnosis.

What-if H3: a dead page was once read as a broken app, wasting a long
diagnosis session. The rule now: run this BEFORE touching any logic — it
separates «الخدمة ميتة» from «منطق خاطئ» in five seconds.

Checks (service-level only; exit 1 if any fails):
  1. app :7860 → HTTP 200
  2. template surface :7867 → 302 → :7860
  3. launchd jobs loaded (app + redirect + healthcheck when present)
  4. log scan: report recent Tracebacks (informational — old lines are fine)

Usage:
    python3 tools/health_check.py
"""
from __future__ import annotations

import http.client
import subprocess
import sys
from pathlib import Path

WANTED_JOBS = ("com.jahfali.rajhi-rag", "com.jahfali.rajhi-redirect",
               "com.jahfali.rajhi-healthcheck")
LOG = Path.home() / "Library" / "Logs" / "rajhi-rag.log"


def _http(port: int):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/")
    resp = conn.getresponse()
    status, location = resp.status, resp.getheader("Location")
    conn.close()
    return status, location


def _jobs() -> dict[str, str]:
    out = subprocess.run(["launchctl", "list"], capture_output=True,
                         text=True).stdout
    jobs: dict[str, str] = {}
    for line in out.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) == 3 and "jahfali.rajhi" in parts[2]:
            jobs[parts[2]] = parts[0]
    return jobs


def main() -> None:
    failures = 0
    print("— فحص صحة مُدقّق كشوف الراجحي —\n")

    try:
        status, _ = _http(7860)
        if status == 200:
            print("[✅] التطبيق :7860 — يعمل (HTTP 200)")
        else:
            print(f"[❌] التطبيق :7860 — يرد HTTP {status} بدل 200")
            failures += 1
    except Exception as e:  # noqa: BLE001
        print(f"[❌] التطبيق :7860 — لا يستجيب ({type(e).__name__})")
        failures += 1

    try:
        status, loc = _http(7867)
        if status == 302 and loc and "7860" in loc:
            print(f"[✅] سطح القالب :7867 — يحوّل ({loc})")
        else:
            print(f"[❌] سطح القالب :7867 — {status} {loc} (المتوقع 302 → :7860)")
            failures += 1
    except Exception as e:  # noqa: BLE001
        print(f"[❌] سطح القالب :7867 — لا يستجيب ({type(e).__name__})")
        failures += 1

    jobs = _jobs()
    for label in WANTED_JOBS:
        if label in jobs:
            pid = jobs[label]
            state = f"pid {pid}" if pid != "-" else "خامل (ينتظر)"
            print(f"[✅] {label} — محمّل، {state}")
        else:
            optional = "healthcheck" in label
            mark = "⚠ " if optional else "❌"
            print(f"[{mark}] {label} — غير محمّل"
                  + (" (اختياري)" if optional else ""))
            failures += 0 if optional else 1

    if LOG.exists():
        lines = LOG.read_text(errors="replace").splitlines()
        tbs = [i for i, l in enumerate(lines) if "Traceback" in l]
        if tbs:
            tail = "\n      ".join(lines[tbs[-1]:tbs[-1] + 3])
            print(f"[⚠ ] السجل — وُجد Traceback (قديم؟ تحقق من الطابع الزمني):\n      {tail}")
        else:
            print("[✅] السجل — لا Tracebacks")
    else:
        print("[⚠ ] السجل — غير موجود بعد (يُنشأ مع أول تشغيل للخدمة)")

    print()
    if failures == 0:
        print("الخلاصة: الخدمات سليمة. إذا بدا «التطبيق خرباً» فالمشكلة ليست "
              "هنا — حدّث المتصفح (⌘⇧R) أو راجع منطق القراءة.")
        sys.exit(0)
    print("الخلاصة: عطل خدمة مؤكَّد. الإصلاح:")
    print("  tools/install_services.sh                 # تثبيت/إعادة تحميل سليم")
    print("  # وعند الضرورة فقط (لا تفعله أثناء تشغيل جارٍ — يقتله):")
    print("  launchctl kickstart -k gui/$(id -u)/com.jahfali.rajhi-rag")
    sys.exit(1)


if __name__ == "__main__":
    main()
