#!/usr/bin/env python3
"""اشتقاق أرقام الصفحات المطبوعة لكل صفحة — بلا نموذج وبلا كلفة.

الترقيم المطبوع **يتسلسل**: يزيد واحداً مع كل صفحة ملف، وتنقص أرقامٌ عند الأوراق
الغائبة. فمن مراسي مقروءة (أو مؤكدة بالعين) يُشتقّ الباقي حسابياً في كل مقطع.

**وفحص الجودة إلزامي**: المسح متّصل، فإزاحة الرقم المطبوع عن رقم الصفحة لا تتجاوز
٣ (الفجوتان وحدهما تصنعان الانزياح). ومرساةٌ خارج ذلك فاسدة تُلوّث الاشتقاق كله —
وقع فعلاً: مرساة «ص10 → 70» جعلت الصفحات ١–٩ تُعلن ٦١…٦٩. والمراسي الفاسدة تُرفض
وتُطبع أسماؤها، ولا تُهمَل بصمت.

    python3 tools/page_numbers_derive.py [--out data/local_sample/page_numbers_map.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.page_numbers import build_map, conflicts  # noqa: E402

MAX_SHIFT = 3          # أقصى إزاحة معقولة بين رقم الملف ورقم الورق
GAP_AFTER = {425, 624}  # نقص الترقيم يقع بعد هاتين الصفحتين (فُجوتا المسح)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="data/local_sample/slice_629p")
    ap.add_argument("--out", default="data/local_sample/page_numbers_map.json")
    ap.add_argument("--last-page", type=int, default=629)
    args = ap.parse_args()

    def load(name: str, key: str | None = None) -> dict[int, int]:
        # الملفّان المساعدان (المؤكَّد بالعين والمكبَّر) يقيمان في مجلد العيّنة،
        # لا داخل مجلد التشغيلة — ولو بحثنا في مكانٍ واحد لأنتجنا خريطةً كلّها
        # «ممتدة» بلا مراسٍ حقيقية (وقع فعلاً: ٤٤٠ ممتدة بدل ٥٢ مقروءة).
        for candidate in (PROJ / args.run / name, PROJ / args.run / ".." / name,
                          PROJ / "data" / "local_sample" / name):
            path = candidate.resolve()
            if path.exists():
                break
        else:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        data = data.get(key) if key else data
        return {int(k): int(v) for k, v in (data or {}).items() if v}

    anchors: dict[int, int] = {}
    anchors.update(load("page_numbers_verified.json", "map"))
    anchors.update(load("page_numbers_read_map.json", "zoom_verified"))
    anchors.update({int(e["page"]): int(e["page_no"])
                    for e in json.loads((PROJ / args.run / "slice_report.json")
                                        .read_text(encoding="utf-8"))["per_page"]
                    if e.get("page_no")})

    suspect = {p: v for p, v in anchors.items() if abs(v - p) > MAX_SHIFT}
    keep = {p: v for p, v in anchors.items() if abs(v - p) <= MAX_SHIFT}
    mapping = build_map(keep, args.last_page, GAP_AFTER)
    counts = Counter(v["source"] for v in mapping.values())
    bad = [p for p, v in mapping.items() if abs(v["printed"] - p) > MAX_SHIFT]

    print(f"مراسٍ مقبولة: {len(keep)} · مرفوضة (إزاحة > {MAX_SHIFT}): {len(suspect)} "
          f"{dict(list(suspect.items())[:4])}")
    print("المصادر:", dict(counts))
    print("تعارضات بين المراسي:", len(conflicts(mapping, keep)))
    print("صفحات بإزاحة شاذة بعد الاشتقاق:", len(bad), bad[:5])
    out = PROJ / args.out
    out.write_text(json.dumps({str(k): v for k, v in sorted(mapping.items())},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"كُتبت الخريطة: {out} ({len(mapping)} صفحة)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
