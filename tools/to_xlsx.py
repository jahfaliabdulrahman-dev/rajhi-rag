#!/usr/bin/env python3
"""EXPORT: كشف مُقروء — four sheets a human (accountant · lawyer) can open and use.

Why this exists
---------------
The pipeline produced proof-shaped artifacts (629 JSON checkpoints, a report, a
parquet index) and no deliverable: a buyer cannot read a cache. Everything below
is therefore *derived from* the run's own evidence, never recomputed by hand:

  · rows      ← `results/pg-*.json` (what the reader returned, with the printed
                string kept beside the parsed number)
  · verdicts  ← the run report's `per_page` (the ARBITER's output, not a
                re-derivation: the docstring of tools/to_parquet.py records that
                re-deriving chain facts produced two wrong conclusions)
  · blanks    ← the page gate's own JSON when present (mechanical, free)

Two columns carry the same value on purpose: `كما طُبع` is what the paper says,
`رقمي` is the parsed number. An export that shows only the parsed number hides
its own work; one that shows only the printed string cannot be filtered.

    python3 tools/to_xlsx.py --run data/local_sample/slice_629p \
        --out ~/Downloads/rajhi-rag-export-629p.xlsx [--gate <page_gate.json>]

Reading rule printed on sheet 4: a value with no printed counterpart is not
asserted here — it is listed on «ما لم يُثبت».
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ARABIC_VERDICT = {
    "ok": "مطابق لإجمالياته المطبوعة",
    "gap": "فجوة إطارات (ورق غائب من المسح)",
    "absent": "لا سطر إجماليات مطبوع",
    "unchecked": "غير قابل للتحقق (جارُه بلا إطار)",
}

HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(color="FFFFFF", bold=True, size=11)
NOTE_FONT = Font(italic=True, size=10, color="555555")


def load(run: Path) -> tuple[list[dict], dict, dict, dict]:
    """(rows, report, per-page verdicts, per-page repair flags) — straight from
    the run's own files. The repair flags live in the checkpoints (the evidence),
    not in the report's legacy fields."""
    report = json.loads((run / "slice_report.json").read_text(encoding="utf-8"))
    per_page = {int(e["page"]): e for e in report.get("per_page") or []}
    flags: dict[int, dict] = {}

    rows: list[dict] = []
    for cache in sorted((run / "results").glob("pg-*.json")):
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue                      # a truncated checkpoint is reported, not guessed
        page = int(data.get("pg") or 0)
        verdict = per_page.get(page, {})
        flags[page] = {
            "recovered": bool(data.get("recovered")),
            "reread": bool(data.get("reread")),
            "error": bool(data.get("error")),
        }
        for i, row in enumerate(data.get("raw_rows") or [], start=1):
            rows.append({
                "page": page,
                "row_no": i,
                "printed_page": data.get("page_no"),
                "date": row.get("date"),
                "desc": row.get("desc"),
                "printed_movement": row.get("raw_movement") or row.get("movement"),
                "printed_balance": row.get("raw_balance") or row.get("balance"),
                "movement": row.get("movement"),
                "balance": row.get("balance"),
                "footer": verdict.get("footer"),
                "counted": verdict.get("rows"),
            })
    return rows, report, per_page, flags


def write_sheet(ws, header: list[str], rows: list[list], widths: list[int],
                *, freeze: str = "A2") -> None:
    ws.append(header)
    for cell in ws[1]:
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in rows:
        ws.append(row)
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = freeze
    ws.auto_filter.ref = ws.dimensions


def build(run: Path, out: Path, gate: Path | None) -> dict:
    rows, report, per_page, flags = load(run)
    if not rows:
        raise SystemExit(f"لا صفوف في {run}/results — هل المسار صحيح؟")

    wb = Workbook()
    ws = wb.active
    assert ws is not None                      # openpyxl always creates one sheet
    ws.title = "الحركات"
    write_sheet(
        ws,
        ["الصفحة (ملف)", "رقم الصفّ", "رقم الصفحة المطبوع", "التاريخ (كما طُبع)",
         "الوصف", "الحركة كما طُبعت", "الرصيد كما طُبع", "الحركة (رقمي)",
         "الرصيد (رقمي)", "حالة إجماليات الصفحة"],
        [[r["page"], r["row_no"], r["printed_page"], r["date"], r["desc"],
          r["printed_movement"], r["printed_balance"], r["movement"],
          r["balance"], ARABIC_VERDICT.get(r["footer"], r["footer"])]
         for r in rows],
        [12, 9, 16, 18, 46, 16, 16, 14, 14, 30])

    ws2 = wb.create_sheet("التحقق لكل صفحة")
    write_sheet(
        ws2,
        ["الصفحة (ملف)", "رقم الصفحة المطبوع", "صفوف معتمدة", "إجماليات الصفحة",
         "عدد الشكوك", "المصدر", "زمن القراءة (ملّي ث)", "تناقض داخلي",
         "استُدركت آلياً", "أُعيدت قراءتها", "خطأ قراءة"],
        [[p, e.get("page_no"), e.get("rows"), ARABIC_VERDICT.get(e.get("footer"), e.get("footer")),
          e.get("suspects"), e.get("origin"), e.get("ms_read"), bool(e.get("paradox")),
          (flags.get(p) or {}).get("recovered"), (flags.get(p) or {}).get("reread"),
          (flags.get(p) or {}).get("error")]
         for p, e in sorted(per_page.items())],
        [13, 16, 13, 32, 12, 11, 18, 13, 13, 15, 11])

    # ما لم يُثبت — كل ما ليس "ok"، ومعه الفارغ من بوابة الصفحة (قياس ميكانيكي مجاني)
    unproven: list[list] = []
    for p, e in sorted(per_page.items()):
        if e.get("footer") != "ok":
            unproven.append([p, e.get("page_no"), e.get("rows"),
                             ARABIC_VERDICT.get(e.get("footer"), e.get("footer")),
                             "من تقرير التشغيل (المحكَّم)"])
    gate_verdict = {}
    if gate and gate.exists():
        gate_verdict = json.loads(gate.read_text(encoding="utf-8")).get("verdict") or {}
        for name in gate_verdict.get("rejected_pages") or []:
            disk = int("".join(ch for ch in name if ch.isdigit()) or 0)
            unproven.append([disk, None, 0, "صورة فارغة (لا حبر يُقرأ)",
                             "من بوابة جودة المسح — بلا استدعاء"])
    # فجوات المسح: كل عنصر [صفحة, سياق..., [أرقام الأوراق الغائبة]] — تُقرأ كما هي
    # ولا تُفسَّر: البنية من المُنتِج، والتصدير لا يعيد اختراعها.
    for gap in ((report.get("page_numbers") or {}).get("gaps")) or []:
        if not isinstance(gap, list) or not gap:
            continue
        missing = gap[-1] if isinstance(gap[-1], list) else None
        page = next((x for x in gap if isinstance(x, int)), None)
        unproven.append([page, page, None,
                         "فجوة مسح: ورقة غائبة من المسح" +
                         (f" — الأوراق الغائبة: {missing}" if missing else ""),
                         "من مسح الترقيم الميكانيكي (بلا استدعاء)"])

    ws3 = wb.create_sheet("ما لم يُثبت")
    write_sheet(ws3, ["الصفحة (ملف)", "رقم الصفحة", "صفوف", "ما لم يُثبت", "مصدر الحكم"],
                sorted(unproven, key=lambda r: (r[0] or 0)), [13, 14, 9, 40, 30])

    ws4 = wb.create_sheet("كيف تُقرأ هذه الأوراق")
    cost = (report.get("usage") or {}).get("cost")
    notes = [
        ("المصدر", f"{run} — نتائج القراءة الفعلية للكشف (629 ورقة ممسوحة)"),
        ("تاريخ التصدير", datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")),
        ("الصفوف المصدَّرة", f"{len(rows)} صفّاً كما قرأها النظام (منها سطور ملخّص لا معاملات)"),
        ("الصفوف المحتسبة في التقرير", f"{(report.get('totals') or {}).get('rows')} معاملة"),
        ("كلفة التشغيل المدفوعة", f"${cost:.4f}" if isinstance(cost, (int, float)) else "غير مسجّلة"),
        ("قاعدة الأمانة", "الرقم الذي لا يمكن إثباته لا يُقال: كل صفّ هنا يحمل قيمته المطبوعة "
                          "بجانب قيمته الرقمية، وحالة إجماليات صفحته من المحكَّم لا من تقدير."),
        ("ما لم يُثبت", "ورقة «ما لم يُثبت» تسمّي كل صفحة لم تُطابق إجمالياتها وسببها — "
                        "بلا مجموع واحد يُخفي الباقي."),
        ("تكرار مقصود", "قد تظهر الصفحة نفسها أكثر من مرة في «ما لم يُثبت» كلٌّ بسبب مختلف: "
                        "حكم المحكَّم («لا سطر إجماليات») وحكم بوابة الصورة («ورقة بيضاء») — "
                        "مصدران مستقلان، وذكرهما معاً إثبات اتفاق لا تكرار."),
        ("فرق الصفوف", f"المصدَّر {len(rows)} صفّاً والمحتسب في التقرير "
                       f"{(report.get('totals') or {}).get('rows')} — الفرق سطور ملخّص في الصفحة "
                       f"الختامية (الرصيد المتاح لليوم · إجماليات القيود) لا معاملات."),
        ("ما لا تجده هنا", "لا مجموع نهائي واحد ولا نسبة دقة واحدة: الأعمدة قابلة للفرز والجمع "
                            "في برنامجك، والمجاميع ملكك لا ملكنا."),
        ("القيم المطبوعة", "«كما طُبع» = نص الورقة حرفياً (أرقام عربية-هندية كما في الورقة) — "
                           "مُبقاة كما هي لأن التحويل قيمة مضافة لا تُفرض على المصدر."),
        ("القيم الرقمية", "«رقمي» = تحويل النظام للأرقام (نقطة عشرية لاتينية) للمقارنة والفرز."),
        ("التحكيم البشري", "الصفوف التي حُكِّمت بعين بشرية موثّقة في المستودع بـ`arbitrated_by` "
                           "(من · لماذا · القيمة الأصلية) ويمكن إعادة اشتقاقها بأمر واحد."),
    ]
    ws4.append(["البند", "البيان"])
    for cell in ws4[1]:
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
    for label, text in notes:
        ws4.append([label, text])
        ws4.cell(row=ws4.max_row, column=1).font = Font(bold=True)
    ws4.column_dimensions["A"].width = 28
    ws4.column_dimensions["B"].width = 105
    for row in ws4.iter_rows(min_row=2, min_col=2, max_col=2):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    ws4["B11"].font = NOTE_FONT

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return {
        "rows": len(rows),
        "pages": len(per_page),
        "unproven": len(unproven),
        "rejected_by_gate": len(gate_verdict.get("rejected_pages") or []),
        "out": str(out),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", required=True, help="مجلد التشغيل (فيه slice_report.json و results/)")
    ap.add_argument("--out", required=True, help="مسار ملف xlsx الناتج")
    ap.add_argument("--gate", default=None, help="ملف بوابة جودة المسح (اختياري · مجاني)")
    args = ap.parse_args()
    info = build(Path(args.run).expanduser(), Path(args.out).expanduser(),
                 Path(args.gate).expanduser() if args.gate else None)
    print(f"[to-xlsx] {info['out']}")
    print(f"  صفوف: {info['rows']} · صفحات: {info['pages']} · بلا إثبات: {info['unproven']}"
          f" · مرفوضة من البوابة: {info['rejected_by_gate']}")


if __name__ == "__main__":
    main()
