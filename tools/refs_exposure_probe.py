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
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/jahfaliabdulrahman-dev/rajhi-rag"
# الالتزاماتُ الثلاثة التي قِيست «مرئيّةً» يومَ الطلب (رقمُ الطلب عند GitHub قائمٌ عليها).
CACHED_SHAS = (
    "aa8b70cb2ea59aa9413e0ca15a31883f2ee6241a",   # آخرُ التزامٍ حمل المسارَين
    "17f5daca929e0d0e8af4ef8bdaaea49cd176b76d",
    "d3dbf2af2662e0becec0b9763a6b50a55da2e987",   # أوّلُ من أدخل قائمة المبالغ
)


def _guard():
    spec = importlib.util.spec_from_file_location("amount_guard", ROOT / "tools" / "amount_guard.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ الحارس ⇒ لا قياس"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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

    out: dict[str, object] = {"repo": URL}
    ls = subprocess.run(["git", "ls-remote", "origin", "refs/pull/*"],
                        cwd=str(ROOT), capture_output=True, text=True)
    if ls.returncode != 0:
        print("⚠ UNMEASURED — تعذّر سؤالُ الريموت ⇒ **فشلٌ مُغلَق** (لا أُعلن تنظيفاً لم أره)")
        return 2
    out["pull_refs"] = len([l for l in ls.stdout.splitlines() if l.strip()])

    tmp = Path(tempfile.mkdtemp(prefix="refs-probe-"))
    try:
        mirror = tmp / "mirror.git"
        cl = subprocess.run(["git", "clone", "-q", "--mirror", URL, str(mirror)],
                            capture_output=True, text=True)
        if cl.returncode != 0:
            print(f"⚠ UNMEASURED — تعذّر جلبُ المرآة ⇒ **فشلٌ مُغلَق** ({cl.stderr.strip()[:80]})")
            return 2
        rv = subprocess.run(["git", "-C", str(mirror), "rev-list", "--all", "--count"],
                            capture_output=True, text=True)
        out["mirror_commits"] = int(rv.stdout.strip() or 0)
        mb = subprocess.run(["git", "-C", str(mirror), "rev-list", "main", "--count"],
                            capture_output=True, text=True)
        out["main_commits"] = int(mb.stdout.strip() or 0)
        try:
            nblobs, forms = ag.history_forms(deny, repo=mirror)
            out["mirror_blobs"], out["amount_formats"] = nblobs, forms
        except Exception as e:                       # UnresolvedRange وغيرُه ⇒ لا أمرّ
            print(f"⚠ UNMEASURED — مسحُ المرآة لم يقع ({type(e).__name__}) ⇒ **فشلٌ مُغلَق**")
            return 2
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    cached = {s[:10]: _http_code(f"{URL}/commit/{s}") for s in CACHED_SHAS}
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
        if exposed:
            print("⛔ STILL EXPOSED — المراجعُ تُرجع ما طلبنا إزالته ⇒ يُعاد الفتحُ بنصٍّ واحد: "
                  "«the refs still resolve — please expire them»")
            return 1
        print("✓ PURGED — لا شكلَ مبلغٍ مرئيّ ولا cached view يردّ 200 ⇒ يُغلق البند **بقياس** لا بوعد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
