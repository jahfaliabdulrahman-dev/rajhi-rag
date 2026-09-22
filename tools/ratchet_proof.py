#!/usr/bin/env python3
"""برهانُ السقاطة: أربعُ حالاتٍ حقيقيّة داخل نسخةٍ مؤقّتة، تُقاس بالأمر لا بالقول.

تُنسخ المستودعُ إلى مجلّدٍ مؤقّت (نسخةٌ مثبَّتةٌ من `origin/main`)، ثم:

  ١) تسريبٌ مباشر            → يجب أن يُسقط الدفع.
  ٢) تسريبٌ + رفعُ خطّ الأساس في الدفعة نفسِها → يجب أن يُسقط.
  ٣) تبديلُ قيمةٍ بأخرى في ملفٍّ مُعلَن (العدّ نفسُه) → يجب أن يُسقط (بصمةُ المجموعة).
  ٤) الخطّافُ من نسخةٍ بلا `.venv` → **لا** يُسقط على `static_gate`، وحرّاسُ الأمن تعمل.

المفتاحُ والمانيفست يُنسخان إلى النسخة المؤقّتة، ثم تُحذف النسخةُ كاملةً في `finally`.
**ولا يُدفع شيء:** كلُّ التشغيل محليٌّ في مجلّدٍ مؤقّت (`--dry-run` في حالة الخطّاف).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run(*a: str, cwd: Path, env: dict | None = None, inp: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(list(a), cwd=str(cwd), capture_output=True, text=True,
                          input=inp, env={**os.environ, **(env or {})})


def _real_values(deny: set[str], surface: str, need: int = 2) -> list[str]:
    """قيمٌ حقيقيّة **من ملفٍّ مُعلَنٍ سلفاً في خطّ الأساس** — لا نُكتب قيمةً في ملفّ متتبَّع هنا."""
    sys.path.insert(0, str(ROOT))
    import tools.amount_guard as ag                                   # noqa: PLC0415
    txt = (ROOT / surface).read_text(encoding="utf-8")
    found = [t for t, _ in ag.find_in_text(txt, deny)]
    if len(found) < need:
        raise SystemExit(f"⛔ السطحُ {surface} لا يحمل {need} قيمتين ⇒ لا برهان (يُعلن ولا يُدَّعى)")
    return found[:need]


def main() -> int:
    sys.path.insert(0, str(ROOT))
    import tools.amount_guard as ag                                   # noqa: PLC0415
    deny = ag.load_deny()
    if deny is None:
        print("⚠ لا مانيفست ⇒ البرهانُ غيرُ قابلٍ للتنفيذ هنا (يُعلن ولا يُدَّعى)")
        return 5
    vals = _real_values(deny, "tests/test_parser.py")
    tmp = Path(tempfile.mkdtemp(prefix="ratchet-proof-"))
    results: list[tuple[str, bool, str]] = []
    try:
        clone = tmp / "clone"
        r = _run("git", "clone", "-q", "--no-hardlinks", str(ROOT), str(clone), cwd=tmp)
        if r.returncode != 0:
            print(f"⛔ تعذّر النسخ: {r.stderr.strip()[:120]}")
            return 5
        _run("git", "checkout", "-q", "origin/main", cwd=clone)
        (clone / ".githooks").mkdir(exist_ok=True)
        shutil.copy2(ROOT / ".githooks/pre-push", clone / ".githooks/pre-push")
        os.chmod(clone / ".githooks/pre-push", 0o755)
        (clone / "docs/security").mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "docs/security/amount-baseline.json", clone / "docs/security/")
        # الأدلّةُ (المفتاحُ والمانيفست): تُنسخ ليعمل الحارس، وتُحذف مع النسخة
        (clone / "data/eval_pack").mkdir(parents=True, exist_ok=True)
        for rel in ("data/.amount-guard-key", "data/eval_pack/amount-manifest.json"):
            if (ROOT / rel).exists():
                shutil.copy2(ROOT / rel, clone / rel)
        # الأداةُ قيدَ الاختبار تُنسَخ من الشجرة العاملة (والنسخةُ فيها نسخةُ HEAD)
        shutil.copy2(ROOT / "tools/amount_guard.py", clone / "tools/amount_guard.py")
        _run("git", "config", "core.hooksPath", ".githooks", cwd=clone)
        target = clone / "tests/test_parser.py"
        base = target.read_text(encoding="utf-8")
        head = _run("git", "rev-parse", "HEAD", cwd=clone).stdout.strip()
        name = "refs/heads/proof"

        def push_refs(new_head: str) -> str:
            return f"{name} {new_head} {name} {head}\n"

        # ١) تسريبٌ مباشر
        target.write_text(base + f"\n# {vals[0]}\n", encoding="utf-8")
        _run("git", "add", "-A", cwd=clone)
        _run("git", "commit", "-q", "-m", "proof: leak", cwd=clone)
        new = _run("git", "rev-parse", "HEAD", cwd=clone).stdout.strip()
        r = _run(PY, "tools/amount_guard.py", "--pre-push", cwd=clone, inp=push_refs(new))
        results.append(("١) تسريبٌ مباشر", r.returncode != 0, f"rc={r.returncode}"))

        # ٢) تسريبٌ + رفعُ خطّ الأساس في الدفعة نفسِها
        _run(PY, "tools/amount_guard.py", "--baseline-write", "--accept-increase", "برهان",
             cwd=clone, env={"AMOUNT_GUARD_ROOT": str(clone)})
        _run("git", "add", "-A", cwd=clone)
        _run("git", "commit", "-q", "-m", "proof: leak + raised baseline", cwd=clone)
        new2 = _run("git", "rev-parse", "HEAD", cwd=clone).stdout.strip()
        r = _run(PY, "tools/amount_guard.py", "--pre-push", cwd=clone, inp=push_refs(new2))
        results.append(("٢) تسريبٌ + رفعُ الأساس معه", r.returncode != 0, f"rc={r.returncode}"))

        # ٣) تبديلُ قيمةٍ بأخرى في ملفٍّ مُعلَن (العدّ نفسُه)
        _run("git", "checkout", "-q", head, "--", "tests/test_parser.py", cwd=clone)
        swapped = base.replace(vals[0], vals[1], 1) if vals[0] in base else base
        if swapped == base:
            results.append(("٣) تبديلُ قيمةٍ بأخرى", False, "تعذّر التبديل (القيمةُ ليست في الملفّ)"))
        else:
            target.write_text(swapped, encoding="utf-8")
            _run("git", "add", "-A", cwd=clone)
            _run("git", "commit", "-q", "-m", "proof: swap", cwd=clone)
            new3 = _run("git", "rev-parse", "HEAD", cwd=clone).stdout.strip()
            r = _run(PY, "tools/amount_guard.py", "--pre-push", cwd=clone, inp=push_refs(new3))
            results.append(("٣) تبديلُ قيمةٍ بأخرى (العدّ ثابت)", r.returncode != 0, f"rc={r.returncode}"))

        # ٤) الخطّافُ من نسخةٍ بلا `.venv` (pyflakes غائبٌ بالمحاكاة) — على شجرةٍ **نظيفة**
        _run("git", "reset", "--hard", "-q", head, cwd=clone)   # تُطرَح التزاماتُ البرهان: المدى = النظيفُ وحده
        (clone / "PROOF-OK.md").write_text("التزامٌ نظيف: لا مبلغَ فيه\n", encoding="utf-8")
        _run("git", "add", "-A", cwd=clone)
        _run("git", "commit", "-q", "-m", "proof: clean", cwd=clone)
        stub = tmp / "bin/python3"
        stub.parent.mkdir(exist_ok=True)
        stub.write_text(f'#!/bin/sh\ncase "$*" in *"import pyflakes"*) exit 1;; esac\nexec "{PY}" "$@"\n',
                        encoding="utf-8")
        os.chmod(stub, 0o755)
        r = _run("git", "push", "--dry-run", "origin", "HEAD:refs/heads/main", cwd=clone,
                 env={"PATH": f"{stub.parent}:{os.environ.get('PATH','')}", "AMOUNT_GUARD_ROOT": str(clone)})
        out4 = r.stdout + r.stderr
        tail = (out4.strip().splitlines() or ["—"])[-1]
        # المقياسُ: **لا يُحجب الدفعُ** لغياب أداةٍ تطويريّة (وما دون ذلك يُقاس يدويًّا بنصّ التخطّي).
        results.append(("٤) الخطّافُ من نسخةٍ بلا `.venv`: لا يُحجب على static_gate",
                        r.returncode == 0, f"rc={r.returncode} · {tail[:60]}"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    width = max(len(n) for n, _, _ in results)
    ok = True
    for name, passed, note in results:
        ok &= passed
        print(f"   {'✓' if passed else '✗'} {name.ljust(width)}  {note}")
    print(f"\n{'PASS' if ok else 'FAIL'} — برهانُ السقاطة على نسخةٍ مؤقّتة ({len(results)} حالات)"
          f" · وleak_sha داخل النسخة المؤقّتة فقط، ولا وُجِد بقيّة")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
