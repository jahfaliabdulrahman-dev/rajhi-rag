#!/usr/bin/env python3
"""اختبار الشاهد الموضعي على صفحة **معطوبة عمداً** — وقياس ما يفعله العطب.

الشاهد الموضعي (الموضع + الحبر) كان يُجرَّب على صفحات سليمة فقط، وشهادةٌ على
صفحة سليمة لا تقول شيئاً عن الظرف الصعب (ميل · حبر باهت · ضبابية). فهذا الاختبار
يُعطِب صفحةً حقيقية بمعاملين معلنين (ميل بالدرجات + ضبابية بالسِجما) ويشغّل الشاهد
عليها، **ويمرّر رصيد الصفحة السابقة** حتى يدخل أوّل صفّ في مقابلة السلسلة (بدونه
يُستثنى أوّل صفّ من كل صفحة — ٦٢٩ صفّاً — وهو ما كشفه مدقّق خارجي).

    python3 tools/damaged_page_test.py --page 281 --skew 2.0 --blur 1.2

**الخصوصية**: الكشف الحقيقي يُحفظ في مجلد البيانات (غير الملتزم)، ويُكتب في
`docs/evidence/` **ملخّص قياس فقط**: لا مبالغ ولا تواريخ ولا أوصاف.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", type=int, default=281)
    ap.add_argument("--skew", type=float, default=2.0, help="ميل بالدرجات")
    ap.add_argument("--blur", type=float, default=1.2, help="ضبابية غاوسية بالسِجما")
    ap.add_argument("--run", default="data/local_sample/slice_629p_v2")
    ap.add_argument("--prev-balance", type=float, default=None,
                    help="رصيد آخر صفّ في الصفحة السابقة (من الملف المُسلَّم)")
    ap.add_argument("--max-cost", type=float, default=0.05)
    args = ap.parse_args()

    sys.path.insert(0, str(PROJ))
    from PIL import Image, ImageFilter  # noqa: PLC0415

    src = PROJ / args.run / "pages" / f"pg-{args.page}.png"
    if not src.exists():
        print(f"الصفحة غير موجودة: {src}")
        return 1
    out_dir = Path(tempfile.mkdtemp(prefix="damaged-"))
    im = Image.open(src).convert("L")
    im.rotate(args.skew, resample=Image.BICUBIC, fillcolor=255) \
        .filter(ImageFilter.GaussianBlur(args.blur)).save(out_dir / src.name)
    print(f"أُعطبت الصفحة: ميل {args.skew}° · ضبابية {args.blur} ⇒ {out_dir / src.name}")

    raw_out = PROJ / "data" / "local_sample" / "damaged_witness.json"
    cmd = [sys.executable, str(PROJ / "tools/pos_witness.py"), "--pages-dir", str(out_dir),
           "--pages", str(args.page), "--out", str(raw_out), "--max-cost", str(args.max_cost)]
    if args.prev_balance is not None:
        cmd += ["--prev-balance", str(args.prev_balance)]
    print(subprocess.run(cmd, cwd=PROJ, text=True).stdout)
    data = json.loads(raw_out.read_text(encoding="utf-8"))[str(args.page)]
    summary = {"الصفحة (ملف)": data["page"],
               "الإعطاب": {"ميل_درجات": args.skew, "ضبابية_سِجما": args.blur},
               "القياس": {"صفوف": len(data["rows"]), "على_حبر": data["on_ink"],
                          "توافق_مع_السلسلة": data.get("agree"), "خلاف": data.get("clash"),
                          "غير_محسوم": data.get("unresolved"), "الكلفة_دولار": data.get("cost")},
               "رصيد_الصفحة_السابقة_الممرَّر": args.prev_balance,
               "الخصوصية": "ملخّص قياس فقط: لا مبالغ ولا تواريخ ولا أوصاف"}
    dest = PROJ / "docs" / "evidence" / f"damaged-page-{args.page}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("الملخّص:", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
