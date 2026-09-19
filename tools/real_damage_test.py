#!/usr/bin/env python3
"""الشاهد الموضعي على صفحة أُعطبت **بيد بشر** — بصورة يلتقطها المالك.

الفرق عن `damaged_page_test.py`: ذاك **يُصنع** العطب (ميل + ضبابية) على رسم
الكوربوس، فيقيس متانة الشاهد على عطبٍ رياضي. وهذا يقيس على **ورقٍ حقيقي معطوب**:
صورة يلتقطها المالك (تجاعيد · ظلّ · ميل عدسة · حبر باهت · تصوير بجوال)، **ومحتواها
معروف** لأنها تقابل صفحةً في الكوربوس المعتمد ⇒ فالمقابلة ممكنة: ما قرأه الشاهد من
الصورة مقابل ما هو مثبت في الكوربوس.

    python3 tools/real_damage_test.py --page 281
    python3 tools/real_damage_test.py --page 281 --photo ~/Downloads/IMG_1234.jpeg

**أين تُوضع الصورة:** `data/local_sample/real_damage/pg-<رقم>.{png,jpg,jpeg,pdf}`
(المجلد غير مُلتزم — بيانات حقيقية لا تدخل git أبداً)، أو مرّر `--photo` مباشرة.

**الخصوصية:** الصورة تُقرأ عبر قارئ السحابة المقبول وحده؛ وملخّص القياس في
`docs/evidence/` **بلا مبالغ ولا تواريخ ولا أوصاف** — عددٌ ونِسَب وكلفة.

**الكلفة:** استدعاء واحد ≈ $0.013 للصفحة (تُطبع في المخرَج).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.legacy.arabic_digit_parser import norm_num  # noqa: E402

EXTS = (".png", ".jpg", ".jpeg", ".pdf")
LONG_SIDE = 2338          # مقاس رسم الكوربوس (200 dpi) — تُقاس عليه الصورة


def find_photo(page: int, given: str | None) -> Path | None:
    if given:
        p = Path(given).expanduser()
        return p if p.exists() else None
    base = PROJ / "data" / "local_sample" / "real_damage"
    for ext in EXTS:
        p = base / f"pg-{page:03d}{ext}"
        if p.exists():
            return p
    return None


def normalize(photo: Path, dest: Path) -> None:
    """صورةٌ ما ⇒ رمادي بمقاس الكوربوس (تُفكّ PDF، تُقلب إن كانت أفقية)."""
    from PIL import Image

    if photo.suffix.lower() == ".pdf":
        import tempfile as _tf

        with _tf.TemporaryDirectory() as tmp:
            subprocess.run(["pdftoppm", "-r", "200", "-png", "-f", "1", "-l", "1",
                            str(photo), str(Path(tmp) / "p")], check=True)
            first = sorted(Path(tmp).glob("p*.png"))[0]
            im = Image.open(first)
            im = im.convert("L")
    else:
        im = Image.open(photo).convert("L")
    if im.width > im.height:                        # صورة أفقية ⇒ الصفحة نائمة
        im = im.rotate(-90, expand=True)
    scale = LONG_SIDE / max(im.size)
    if abs(scale - 1) > 0.02:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, optimize=True)


def prev_balance(page: int, cache_dir: Path, lookback: int = 5) -> float | None:
    """آخر رصيد مقروء في الصفحة السابقة (وننزل للخلف عند صفحة بلا رصيد)."""
    for candidate in range(page - 1, max(1, page - lookback) - 1, -1):
        f = cache_dir / f"pg-{candidate:03d}.json"
        if not f.exists():
            continue
        for row in reversed(json.loads(f.read_text(encoding="utf-8")).get("raw_rows") or []):
            raw = row.get("raw_balance") or row.get("balance")
            if raw in (None, ""):
                continue
            try:
                value = norm_num(str(raw))
            except (InvalidOperation, ValueError, TypeError):
                continue
            if value is None:
                continue
            return float(value)
    return None


def certified_rows(page: int, cache_dir: Path) -> list[tuple[str, str]]:
    """(الحركة, الرصيد) لكل صفّ **مثبت** في الكوربوس المعتمد لهذه الصفحة."""
    f = cache_dir / f"pg-{page:03d}.json"
    if not f.exists():
        return []
    out = []
    for row in json.loads(f.read_text(encoding="utf-8")).get("raw_rows") or []:
        mv = row.get("raw_movement") or row.get("movement")
        bal = row.get("raw_balance") or row.get("balance")
        if mv not in (None, "") and bal not in (None, ""):
            out.append((str(mv), str(bal)))
    return out


def as_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(str(norm_num(str(raw))))
    except (InvalidOperation, ValueError, TypeError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", type=int, required=True, help="رقم الصفحة في الكوربوس")
    ap.add_argument("--photo", default=None, help="مسار الصورة/الـPDF (افتراضياً مجلد الاستلام)")
    ap.add_argument("--run", default="data/local_sample/slice_629p")
    ap.add_argument("--max-cost", type=float, default=0.05)
    ap.add_argument("--evidence-dir", default="docs/evidence")
    ap.add_argument("--damage-note", default=None,
                    help="وصف العطب بلفظ من شغّل القياس: «طيّة بيد بشر» · «مبرمج: ظلّ+ضبابية»")
    args = ap.parse_args()

    photo = find_photo(args.page, args.photo)
    if photo is None:
        print(f"لا صورة للصفحة {args.page}. ضعها في "
              f"data/local_sample/real_damage/pg-{args.page:03d}.jpg أو مرّر --photo.")
        return 2
    run = PROJ / args.run
    cache_dir = run / "results"

    with tempfile.TemporaryDirectory(prefix="real-damage-") as tmp:
        pages_dir = Path(tmp) / "pages"
        target = pages_dir / f"pg-{args.page}.png"
        normalize(photo, target)
        prev = prev_balance(args.page, cache_dir)
        raw_out = Path(tmp) / "witness.json"
        cmd = [sys.executable, str(PROJ / "tools/pos_witness.py"),
               "--pages-dir", str(pages_dir), "--pages", str(args.page),
               "--out", str(raw_out), "--max-cost", str(args.max_cost)]
        if prev is not None:
            cmd += ["--prev-balance", str(prev)]
        proc = subprocess.run(cmd, cwd=PROJ, text=True, capture_output=True)
        if proc.returncode != 0 or not raw_out.exists():
            print("فشل الشاهد:", (proc.stdout + proc.stderr)[-600:])
            return 1
        data = json.loads(raw_out.read_text(encoding="utf-8"))[str(args.page)]

    read_pairs = {p for p in ((as_decimal(r.get("amount", "")), as_decimal(r.get("balance", "")))
                              for r in data.get("rows") or [])
                  if p[0] is not None and p[1] is not None}
    truth_pairs = {p for p in ((as_decimal(mv), as_decimal(bal))
                               for mv, bal in certified_rows(args.page, cache_dir))
                   if p[0] is not None and p[1] is not None}
    matched = len(read_pairs & truth_pairs)
    summary = {
        "الصفحة (ملف)": args.page,
        "وصف_الإعطاب": args.damage_note or "غير معلن — يجب وصف العطب بلفظ من شغّل القياس",
        "بيد_بشر": bool(args.damage_note and "مبرمج" not in args.damage_note),
        "المصدر": {"نوع_الصورة": photo.suffix.lower().lstrip("."),
                   "مقاس_الكوربوس_المقيس": LONG_SIDE},
        "القياس": {
            "صفوف_قرأها_الشاهد": len(data.get("rows") or []),
            "صفوف_معتمدة_في_الكوربوس": len(truth_pairs),
            "تطابق_الزوج_(حركة,رصيد)": matched,
            "استرجاع": (f"{matched}/{len(truth_pairs)}" if truth_pairs else "لا سند"),
            "على_حبر": data.get("on_ink"),
            "توافق_مع_السلسلة": data.get("agree"),
            "خلاف": data.get("clash"),
            "غير_محسوم": data.get("undetermined"),
            "الكلفة_دولار": data.get("cost"),
        },
        "رصيد_الصفحة_السابقة_الممرَّر": prev,
        "الخصوصية": "ملخّص قياس فقط: لا مبالغ ولا تواريخ ولا أوصاف",
    }
    dest = PROJ / args.evidence_dir / f"real-damage-page-{args.page}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\nالملخّص:", dest.relative_to(PROJ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
