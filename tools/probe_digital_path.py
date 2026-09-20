#!/usr/bin/env python3
"""مسبار قدرات على الكشف الرقمي (PDF من تطبيق المصرف) — بالكلفة صفر وبلا نموذج.

السؤال: هل تُغلق **الهوية** و**السلسلة** من نصّ الكشف وحده؟ فإن أُغلقتا فأربعة
أشياء تُثبت معاً: المسار الرقمي مقروء · الرصيد الجاري مطبوع · الإجماليات المطبوعة
تُطابق المحسوبة · والمستخرج النصّي يُخرِج الصفوف نفسها التي تفهمها بقية المنظومة.

والقراءة بالمواضع (`x`) لا بترتيب الأسطر — والنصّ العربي في هذه الملفات يُستخرج
بصور العرض مُقلوباً، فلا يُبنى عليه حكم.

**الخصوصية:** يقرأ ملفاً محليّاً ويطبع حقولاً مجمَّعةً فقط (أعداد وفروق)، ولا يكتب
اسماً ولا رقم حساب ولا إجمالياً مطلقاً في دليلٍ عام.

    python3 tools/probe_digital_path.py --pdf "$HOME/Downloads/Rajhi statment from app.pdf"
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber

NUM = re.compile(r"-?[\d,]+\.\d{2}")
DATE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
LINE_TOL = 3.0          # دقّة تجميع السطور (نقاط)
AMOUNT_X = 300          # ما بعد هذا العمود مبالغ (Debit/Credit/Balance)


def non_witnesses() -> tuple[str, ...]:
    """ما **لا** يشهد به ملفٌّ رقمي — تُطبَع مع كل قياس لا تُترك للقارئ.

    سببُ وجودها: كل فحوص المسبار تُحسب من **داخل الملف نفسه**، فملفٌّ عُدِّل ثم
    أُعيد حساب أرصدته يمرّ منها كلها. فـ«0 كسور» تُثبت **اتّساق المستند** لا
    **صدوره عن المصرف** — والدقّة والحجّيّة محوران لا محور. والمرجع المطبوع
    عنوانُ الجهة التي تُسأل، لا شهادةً منها.
    """
    return (
        "لا توقيع رقمي ولا تشفير: لا شيء يمنع تعديل الملف وإعادة حساب أرصدته.",
        "حقل /Author نصٌّ يكتبه أي محرِّر PDF — لا يشهد بالمصدر.",
        "كل فحوص هذا المسبار تُحسب من داخل الملف نفسه ⇒ «0 كسور» اتّساقٌ داخلي "
        "لا صدورٌ عن المصرف.",
        "المرجع المطبوع (Ref. No) عنوانُ الجهة التي تُسأل — لا شهادةٌ منها.",
    )


def signature_facts(path: Path) -> dict:
    """التوقيع والتشفير مقيسان لا مُفترضان (pypdf — بلا شبكة)."""
    try:
        from pypdf import PdfReader
        r = PdfReader(str(path))
        root = r.trailer.get("/Root") or {}
        return {"signed_acroform": "/AcroForm" in root,
                "encrypted": bool(r.is_encrypted),
                "author": str((r.metadata or {}).get("/Author") or "") or None}
    except Exception as exc:  # pragma: no cover - يعتمد على الملف
        return {"signed_acroform": "unreadable", "encrypted": "unreadable",
                "error": f"{type(exc).__name__}: {exc}"[:160]}


def _dec(s: str) -> Decimal | None:
    try:
        return Decimal(s.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def _lines(page) -> list[list[dict]]:
    """تجميع الكلمات في سطور بـ**عنقودٍ متصل** لا بتقريبِ خانة.

    كان التجميع `round(top / tol)`: كلمتان على السطر نفسه (`378.9` و`379.8`)
    تقعان في خانتين مختلفتين فينفصل سطرٌ واحد إلى سطرين — وهو الصنف نفسه:
    أداةٌ تُسأل عن سطر فتجيب عن خانتين.
    """
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = []
    for w in words:
        if lines and w["top"] - lines[-1][0]["top"] <= LINE_TOL:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def parse_document(path: Path) -> dict:
    """-> صفوف + ما يقوله الورق عن نفسه (الملخّص المطبوع)."""
    rows: list[dict] = []
    header: dict[str, str] = {}
    per_page: list[int] = []
    no_date = 0
    with pdfplumber.open(path) as pdf:
        for pi, page in enumerate(pdf.pages, start=1):
            lines = _lines(page)
            texts = [(round(ls[0]["top"], 1) if ls else 0.0,
                      " ".join(w["text"] for w in ls)) for ls in lines]
            n_before = len(rows)
            if pi == 1:
                for label, key in (("Opening Balance", "opening"),
                                   ("Closing Balance", "closing"),
                                   ("Total Deposits", "printed_credits"),
                                   ("Total Withdrawals", "printed_debits"),
                                   ("Number Of Deposits", "n_deposits"),
                                   ("Number Of Withdrawals", "n_withdrawals"),
                                   ("Ref. No", "ref")):
                    for i, (top, text) in enumerate(texts):
                        if label not in text or key in header:
                            continue
                        # في هذا التصميم قد يكون الرقم في السطر نفسه (المبالغ) أو **في
                        # سطرٍ تحته** (الأعداد الصحيحة) — والبحث يمتدّ سطرين لا أكثر.
                        window = [text] + [t for tp, t in texts[i + 1:i + 3]
                                           if tp - top < 45]
                        if key.startswith("n_"):
                            body = window[0].split(label, 1)[1]
                            m = re.search(r"\b(\d{1,5})\b", body) or next(
                                (re.search(r"^(\d{1,5})$", w.strip())
                                 for w in window[1:] if re.search(r"^(\d{1,5})$", w.strip())),
                                None)
                        elif key == "ref":
                            m = re.search(r"\b(\d{6,})\b", text)
                        else:
                            m = NUM.search(text)
                        if m:
                            header[key] = m.group(1) if m.re.groups else m.group(0)
            for line in lines:
                amounts = [w for w in line if w["x0"] > AMOUNT_X and NUM.fullmatch(w["text"])]
                if len(amounts) < 3:
                    continue
                vals = [_dec(w["text"]) for w in amounts[:3]]
                if any(v is None for v in vals):
                    continue
                d = next((w["text"] for w in line
                          if w["x0"] < 100 and DATE.match(w["text"])), None)
                if d is None:
                    no_date += 1
                rows.append({"page": pi, "date_printed": d,
                             "debit": vals[0], "credit": vals[1], "balance": vals[2]})
            per_page.append(len(rows) - n_before)
    return {"rows": rows, "header": header, "per_page": per_page, "rows_without_date": no_date}


def measure(parsed: dict) -> dict:
    rows, hdr = parsed["rows"], parsed["header"]
    opening = _dec(hdr.get("opening", "0"))
    closing = _dec(hdr.get("closing", "0"))
    sd = sum((r["debit"] for r in rows), Decimal("0"))
    sc = sum((r["credit"] for r in rows), Decimal("0"))
    # السلسلة: balance[i] = balance[i-1] + credit - debit
    breaks, prev = [], opening
    for i, r in enumerate(rows):
        want = prev + r["credit"] - r["debit"]
        if r["balance"] != want:
            breaks.append({"row": i + 1, "page": r["page"],
                           "diff": str(r["balance"] - want)})
        prev = r["balance"]
    pd_ = _dec(hdr.get("printed_debits", "0"))
    pc = _dec(hdr.get("printed_credits", "0"))
    counts = None
    if "n_deposits" in hdr and "n_withdrawals" in hdr:
        counts = int(hdr["n_deposits"]) + int(hdr["n_withdrawals"])
    return {
        "صفوف": len(rows),
        "صفوف_بلا_تاريخ": parsed["rows_without_date"],
        "عدد_مطبوع_للإيداعات+السحوبات": counts if counts is not None else "غير مقروء من الورق",
        "عدد_الصفوف_يساوي_المطبوع": counts == len(rows) if counts is not None else None,
        "فرق_مجموع_المدين_عن_المطبوع": str(sd - (pd_ or Decimal("0"))),
        "فرق_مجموع_الدائن_عن_المطبوع": str(sc - (pc or Decimal("0"))),
        "الهوية_افتتاح+دائن−مدين−إقفال": str(opening + sc - sd - closing),
        "كسور_في_السلسلة": len(breaks),
        "أمثلة_الكسور": breaks[:3],
        "الرصيد_الختامي_المحسوب_يساوي_المطبوع": prev == closing,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("docs/evidence"))
    args = ap.parse_args()

    parsed = parse_document(args.pdf)
    result = measure(parsed)
    report = {
        "measured_at": date.today().isoformat(),
        "kind": "كشف رقمي (نصّ) — قياس مجمَّع فقط، بلا اسم ولا حساب ولا إجمالي مطلق",
        "ref_present": bool(parsed["header"].get("ref")),
        "pages_with_rows": len([n for n in parsed["per_page"] if n]),
        **result,
        "signature": signature_facts(args.pdf),
        "ما_لا_يشهد_به_هذا_الملف": list(non_witnesses()),
        "cost_usd": "0 — لا نموذج ولا شاهد موضعي: النصّ هو الدليل",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "20260920-digital-path-probe.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\nالملف: {out}")


if __name__ == "__main__":
    main()
