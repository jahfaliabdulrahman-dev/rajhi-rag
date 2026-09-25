#!/usr/bin/env python3
"""حَيّازُ الانكشاف — قياسٌ واحد لحالة المراجع المحذوفة (يُعاد بعد كل ردٍّ من GitHub).

يقيس أربعةَ أشياء بلا نداءِ نموذج ($0):
  ١) عددُ `refs/pull/*` على الريموت.
  ٢) التزاماتُ مرآةٍ كاملةٍ مقابل التزامات `main` المعاد كتابتِه.
  ٣) **صيغُ المبالغ الحقيقيّة المرئيّة عبر المرآة** بحارس المبالغ نفسِه (`history_forms`).
  ٤) هل التزاماتُ ما قبل التنقية لا تزال «cached views» (رمزُ HTTP لكل رابط).

الحكم: `PURGED` (صفرُ انكشاف) · `STILL EXPOSED` (بقي شيء) · `UNMEASURED` (تعذّر الجلب ⇒ **فشلٌ مُغلَق**).
والقيمُ لا تُطبع أصلاً (القاعدة ١٣) — أعدادٌ وحالاتٌ فقط.

    python3 tools/refs_exposure_probe.py [--json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/jahfaliabdulrahman-dev/rajhi-rag"
# **معرّفاتُ ما قبل التنقية تُقرأ من ملفٍّ غيرِ مُتتبَّع** (مراجعة ٥٣ — إسقاطٌ أمنيّ):
# كتابتُها هنا كانت تنشر **رابطاً موسوماً** إلى ما لم يُطهَّر («أوّلُ من أدخل قائمة المبالغ») في مستودعٍ
# عامّ ⇒ من قرأ الملفَّ عرف **أيّ التزامٍ** يفتح البيانات. والوصفُ يبقى في `data/security/` المُهمَل.
SHA_FILE = Path(os.environ.get("REFS_CACHED_SHAS") or (ROOT / "data" / "security" / "refs-cached-shas.json"))


def cached_shas() -> list[str]:
    """قائمةُ الالتزامات من **غير المُتتبَّع**. وغيابُها ⇒ لا قياسَ (يُعلَن، والحكمُ يفشل مُغلَقاً)."""
    try:
        data = json.loads(SHA_FILE.read_text(encoding="utf-8"))
        out = [str((x or {}).get("sha") or "") for x in (data.get("cached_views") or [])]
        return [s for s in out if s]
    except Exception:                            # غيابٌ أو عطبٌ ⇒ ليست أدلّةً صامتة
        return []


def _guard():
    spec = importlib.util.spec_from_file_location("amount_guard", ROOT / "tools" / "amount_guard.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ الحارس ⇒ لا قياس"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(cmd: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    """**سبيلٌ واحد لنداءات git** — وعليه يقوم اختبارُ رمز الخروج بلا شبكة.

    (العطبُ الذي أُمسك 2026-09-24: `--json` كان يُرجع **0** والحكمُ `STILL EXPOSED`، لأنّ `return 1`
    سكن فرعَ المخرَج النصّيّ ⇒ مستهلكٌ آليّ يقرأ صفرًا فيمرّ على سطحٍ مكشوف = **فشلٌ مفتوح**.)
    """
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _http_code(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "rajhi-refs-probe"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="مخرَجٌ آليّ لا يُقصّ")
    args = ap.parse_args()

    ag = _guard()
    deny = ag.load_deny()
    if deny is None:
        print("⚠ UNMEASURED — لا أدلّةَ (مانيفست/مفتاح) ⇒ لا أستطيع مسحَ المرآة ⇒ **فشلٌ مُغلَق**")
        return 2

    shas = cached_shas()
    if not shas:
        print(f"⚠ UNMEASURED — لا قائمةَ لالتزامات ما قبل التنقية (تُقرأ من {SHA_FILE} · غيرِ مُتتبَّع) "
              "⇒ **فشلٌ مُغلَق** (لا أُعلن نظافةً لم أرها)")
        return 2

    out: dict[str, object] = {"repo": URL}
    ls = _run(["git", "ls-remote", "origin", "refs/pull/*"], cwd=str(ROOT))
    if ls.returncode != 0:
        print("⚠ UNMEASURED — تعذّر سؤالُ الريموت ⇒ **فشلٌ مُغلَق** (لا أُعلن تنظيفاً لم أره)")
        return 2
    out["pull_refs"] = len([l for l in ls.stdout.splitlines() if l.strip()])

    tmp = Path(tempfile.mkdtemp(prefix="refs-probe-"))
    try:
        mirror = tmp / "mirror.git"
        cl = _run(["git", "clone", "-q", "--mirror", URL, str(mirror)])
        if cl.returncode != 0:
            print(f"⚠ UNMEASURED — تعذّر جلبُ المرآة ⇒ **فشلٌ مُغلَق** ({cl.stderr.strip()[:80]})")
            return 2
        rv = _run(["git", "-C", str(mirror), "rev-list", "--all", "--count"])
        out["mirror_commits"] = int(rv.stdout.strip() or 0)
        mb = _run(["git", "-C", str(mirror), "rev-list", "main", "--count"])
        out["main_commits"] = int(mb.stdout.strip() or 0)
        try:
            nblobs, forms = ag.history_forms(deny, repo=mirror)
            out["mirror_blobs"], out["amount_formats"] = nblobs, forms
        except Exception as e:                       # UnresolvedRange وغيرُه ⇒ لا أمرّ
            print(f"⚠ UNMEASURED — مسحُ المرآة لم يقع ({type(e).__name__}) ⇒ **فشلٌ مُغلَق**")
            return 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    cached = {s[:10]: _http_code(f"{URL}/commit/{s}") for s in shas}
    out["cached_views"] = cached

    exposed = bool(out["amount_formats"]) or any(c == 200 for c in cached.values())
    verdict = "STILL EXPOSED" if exposed else "PURGED"
    out["verdict"] = verdict

    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(f"· refs/pull/* على الريموت        : {out['pull_refs']}")
        print(f"· التزاماتُ المرآة                : {out['mirror_commits']} (و main المعاد كتابتُه {out['main_commits']})")
        print(f"· صيغُ مبالغَ حقيقيّة عبر المرآة   : {out['amount_formats']} داخل {out['mirror_blobs']} blobاً")
        print("· cached views للتزامات ما قبل التنقية: " +
              " · ".join(f"{k} ⇒ HTTP {v}" for k, v in cached.items()))
        print("⛔ STILL EXPOSED — المراجعُ تُرجع ما طلبنا إزالته ⇒ يُعاد الفتحُ بنصٍّ واحد: "
              "«the refs still resolve — please expire them»" if exposed else
              "✓ PURGED — لا شكلَ مبلغٍ مرئيّ ولا cached view يردّ 200 ⇒ يُغلق البند **بقياس** لا بوعد.")
    # **والحكمُ هو الحكم** في الوضعين: `PURGED=0` · `STILL EXPOSED=1` (ولا يتبدّل بشكل المخرَج).
    return 1 if exposed else 0


if __name__ == "__main__":
    raise SystemExit(main())
