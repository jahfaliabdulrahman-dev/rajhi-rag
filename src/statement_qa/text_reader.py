"""قارئ الكشوف الرقمية (PDF نصّ صادر عن نظام المصرف) — حتميّ، بلا نموذج، بكلفة صفر.

**العقد:** يُخرج **نفس `RawRow`** الذي يُخرجه قارئ الصور
(`movement · balance · desc · date · raw_movement · raw_balance`) — فالقراءة تختلف
والمنظومة بعدها لا تعرف الفرق، وكل الشهود (السلسلة · الإجماليات · الهوية) تُقاس
بالأدوات نفسها. ووسم القارئ (`model` · `prompt_version`) يُكتب مع كل نقطة فحص كما
يُكتب لقارئ الصور (FMEA FM-1).

**والقراءة بالمواضع لا بترتيب الأسطر:** طبقة النصّ في هذه الملفات تُخرج العربية
بصور العرض مُرتَّبة بصرياً، وترتيب الأسطر لا يحفظ الصفوف. فالصفّ يُبنى من **مواضع
الكلمات**: عمود التاريخ يساراً، والمبالغ يميناً (Debit · Credit · Balance)، والوصف
بينهما. وهذا هو شاهد الموضع في ملفٍ رقمي: أدقّ من الصورة لأنه بلا قراءة.

**حدود مُعلنة:**
  · التطبيع العربي يصلح ترتيب الحروف والأرقام العربية، ولا يدّعي إصلاح كل
    الحالات النادرة (أرقام داخل نصّ عربي متداخل تُحفظ بترتيبها البصري).
    والوصف **سياق لا حساب**: لا رقم يُشتقّ منه.
  · الصفوف المقطوعة بين صفحتين لم تُقَس بعد في هذا القارئ.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber

# ⚠ترتيب الحروف: `NFKC` يفكّ الحرف المركّب (لام-ألف) إلى حرفين **بالترتيب البصري**،
# فيصير بعد عكس المقطع «اإل/اآل» بدل «الإ/الآ». والإصلاح **ثلاثة محارف** — وقد
# أخطأتُ أولاً بخانتين فأنتج «الإلقفال»: #قياسٌ يكشف خطأ القياس#. والأمثلة من
# الكشف نفسه (الإقفال · الآيبان) ومحروسةٌ باختبار.

NUM = re.compile(r"-?[\d,]+\.\d{2}")
DATE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
# إصلاح ترتيب اللام-ألف: **ثلاثة محارف** (اشتُقّ من أمثلة الكشف، ومحروسٌ باختبار)
ARABIC_ORDER_FIXES = {"اإل": "الإ", "اآل": "الآ"}
# عناوين الترويسة والملخّص: **ليست وصفاً لصفّ**. تُرشَّح بالاسم لا بالموقع، لأن
# «لا نصَّ قبل أوّل مبلغ» يُسقط وصفَ الصفّ الأول (وهو ما وقع أول مرة).
HEADER_LABELS = {
    "الرقم التسلسلي", "التاريخ", "الوقت", "تفاصيل الكشف", "اسم العميل", "رقم الحساب",
    "رقم الآيبان", "رصيد الافتتاح", "الرصيد الختامي", "عدد الإيداعات", "عدد السحوبات",
    "إجمالي الإيداعات", "إجمالي السحوبات", "خلال الفترة", "العنوان الوطني", "المدينة",
    "الشارع", "الحي", "الرمز البريدي", "رقم المبنى", "الرقم الفرعي",
}
HEADER_PREFIXES = ("Date", "Transaction Details", "Debit", "Credit", "Balance",
                   "Ref.", "Statement Details", "Account", "Opening", "Closing",
                   "Number Of", "Total ", "On The Period", "National Address",
                   "Customer Name", "IBAN", "City", "Street", "District", "Postal",
                   "Building", "Secondary", "Time ", "SAR")

LINE_TOL = 3.0            # دقّة تجميع السطور (نقاط)
AMOUNT_X = 300            # ما بعد هذا العمود مبالغ: Debit · Credit · Balance
DESC_MAX = 600


def _dec(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def _fix_order(run: str) -> str:
    """عكسُ المقطع العربي ثم إصلاح ترتيب اللام-ألف وحدهما (لا استبدال عام).

    الإصلاح **ثلاثة محارف**: «اإل» ← «الإ» و«اآل» ← «الآ». وأخطأتُ فيه أول مرة
    بخانتين فأنتج «الإلقفال» بدل «الإقفال» — والقياس على أمثلة الكشف هو الذي
    كشف خطأ القياس. (والقاعدة: تطبيعٌ يُنتج كلمةً غير موجودة عطلٌ لا تجميل.)
    """
    fixed = run[::-1]
    for wrong, right in ARABIC_ORDER_FIXES.items():
        fixed = fixed.replace(wrong, right)
    return fixed


def _is_rtl(ch: str) -> bool:
    """عربيٌّ أو فراغٌ بين عربيّين: الفراغ جزءٌ من المقطع، وإلا بقي ترتيب الكلمات مقلوباً."""
    return unicodedata.bidirectional(ch) in ("R", "AL") or ch.isspace()


def normalize_arabic_visual(text: str) -> str:
    """يُصلح نصّاً عربياً مُستخرَجاً بصور العرض: حروفٌ لا صورٌ، وترتيبٌ منطقي.

    لا يمسّ الأرقام ولا اللاتيني في مواضعها، ولا يُخفي ما لم يُصلحه: ما بقي
    بترتيبه البصري يبقى — والوصف سياقٌ لا يُشتقّ منه رقم.
    """
    if not text:
        return ""
    flat = unicodedata.normalize("NFKC", text)
    out, run = [], []
    for ch in flat:
        if _is_rtl(ch):
            run.append(ch)
        else:
            if run:
                out.append(_fix_order("".join(run)))
                run = []
            out.append(ch)
    if run:
        out.append(_fix_order("".join(run)))
    return "".join(out)


def _lines(page) -> list[list[dict]]:
    """كلمات الصفحة في سطور — تجميعٌ بعنقودٍ متصل لا بتقريب خانة."""
    words = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = []
    for w in words:
        if lines and w["top"] - lines[-1][0]["top"] <= LINE_TOL:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def read_rows(pdf_path: str | Path, *, page_number: int | None = None) -> list[dict]:
    """الصفحة (أو الملف) → صفوف بشكل `RawRow` نفسه الذي يعرفه المشروع.

    والقاعدة الحاكمة: ما يُنقل هو **ما على الورق** — المبلغ المطبوع والرصيد
    المطبوع. والاتجاه (مدين/دائن) **لا يُستنتج هنا**: تثبته السلسلة بعده.
    """
    rows: list[dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = [(page_number, pdf.pages[page_number - 1])] if page_number else \
            enumerate(pdf.pages, start=1)
        for _pg, page in pages:
            pending: list[str] = []
            for line in _lines(page):
                amounts = [w for w in line
                           if w["x0"] > AMOUNT_X and NUM.fullmatch(w["text"])]
                date_tok = next((w["text"] for w in line
                                 if w["x0"] < 100 and DATE.match(w["text"])), None)
                desc_toks = [w for w in line
                             if 100 <= w["x0"] <= AMOUNT_X
                             or (w["x0"] < 100 and not DATE.match(w["text"]))]
                if len(amounts) >= 3:
                    values = [_dec(w["text"]) for w in amounts[:3]]
                    if any(v is None for v in values):
                        continue
                    debit, credit, balance = values
                    movement = credit if credit else debit
                    desc = " ".join(pending + [w["text"] for w in desc_toks])
                    pending = []
                    rows.append({
                        "movement": movement,
                        "balance": balance,
                        "desc": normalize_arabic_visual(desc)[:DESC_MAX] or None,
                        "date": date_tok,
                        "raw_movement": (amounts[1] if credit else amounts[0])["text"],
                        "raw_balance": amounts[2]["text"],
                    })
                    continue
                text = " ".join(w["text"] for w in line).strip()
                if not text or text.startswith(("Ref.", "Date", "Statement")):
                    continue
                # ⚠️ سطر `Time:/Notes:` **يتبع صفّه** (يأتي بعد سطر المبالغ)، فإلحاقه
                # بـ`pending` يجعله وصفاً للصفّ **التالي** — وهو ما وقع أول مرة.
                if normalize_arabic_visual(text).strip().strip("· ") in HEADER_LABELS:
                    continue
                if text.startswith(HEADER_PREFIXES) and not text.startswith(("Time:", "Notes:")):
                    continue
                if text.startswith(("Time:", "Notes:")) and rows:
                    rows[-1]["desc"] = ((rows[-1]["desc"] or "") + " " +
                                        normalize_arabic_visual(text))[:DESC_MAX].strip()
                    continue
                pending.append(text)
    return rows


PERIOD_LABELS = {"opening": "Opening Balance", "closing": "Closing Balance",
                 "printed_debits": "Total Withdrawals",
                 "printed_credits": "Total Deposits",
                 "n_deposits": "Number Of Deposits",
                 "n_withdrawals": "Number Of Withdrawals"}


def read_period_summary(pdf_path: str | Path) -> dict:
    """مجاميع الفترة من صفحة الملخّص — **شاهدٌ مستقلّ** عن السلسلة، لا يُشتقّ."""
    found: dict[str, str] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for line in _lines(pdf.pages[0]):
            text = " ".join(w["text"] for w in line)
            for key, label in PERIOD_LABELS.items():
                if label in text and key not in found:
                    m = (re.search(r"\b(\d{1,5})\b", text.split(label, 1)[1])
                         if key.startswith("n_") else NUM.search(text))
                    if m:
                        found[key] = m.group(1) if m.re.groups else m.group(0)
    return found


def emit_run(pdf_path: str | Path, out_dir: Path, *, doc_id: str | None = None,
             label: str = "app_digital") -> dict:
    """يكتب نقاط فحص بشكل التشغيلة نفسه (+ وسم القارئ) — فيقرؤها ما بعدها كما هي."""
    import hashlib
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from scale_slice import row_to_json  # noqa: PLC0415
    from statement_qa.vlm_reader import reader_stamp  # noqa: PLC0415

    period_summary = read_period_summary(pdf_path)
    out_dir = Path(out_dir)
    results = out_dir / "results"
    results.mkdir(parents=True, exist_ok=True)
    pages_done = rows_total = 0
    with pdfplumber.open(str(pdf_path)) as pdf:
        n_pages = len(pdf.pages)
    opening = _dec(period_summary.get("opening", "")) if period_summary else None
    # ⚠️ الافتتاح يُلحَق بأوّل صفحةٍ **فيها صفوف**، لا بالصفحة ١: صفحة الملخّص لا
    # حركات فيها، فشرطُ `pg == 1` لم يُنفَّذ قطّ — واتجاهُ أول حركة بقي بلا شاهد
    # (وهو ما أنتج Σدائن ناقصاً 1000 بالضبط). القاعدة: الشاهد يُلحَق بمكانه لا
    # برقمٍ افترضتُه.
    opening_done = False
    for pg in range(1, n_pages + 1):
        rows = read_rows(pdf_path, page_number=pg)
        if rows and not opening_done and opening is not None:
            # **صفّ الافتتاح**: يُشتقّ اتجاهُ أول حركة من فرق رصيدين، وبلا رصيدٍ
            # سابق يفقد الشاهدُ أساسه فيُقلب الاتجاه (وقع: 1000 دائن صارت مديناً
            # فصار Σدائن ناقصاً 1000). والافتتاح **مطبوع** في ملخّص الفترة ⇒
            # يُقرأ ولا يُخمَّن، كما يقرؤه قارئ الصور من رأس الكشف.
            rows = [{"movement": None, "balance": opening, "desc": "الرصيد الافتتاحي",
                     "date": None, "raw_movement": None,
                     "raw_balance": period_summary.get("opening")}] + rows
            opening_done = True
        if not rows:
            continue
        pages_done += 1
        rows_total += len(rows)
        (results / f"pg-{pg:03d}.json").write_text(json.dumps(
            {**reader_stamp(reader="text"), "pg": pg, "raw_rows": [row_to_json(r) for r in rows],
             "cost_usd": "0", "reader": "text"}, ensure_ascii=False), encoding="utf-8")
    per_page = [{"page": pg, "rows": len(read_rows(pdf_path, page_number=pg)),
                 "footer": "absent", "suspects": 0, "page_no": pg,
                 "origin": "text", "ms_read": 0}
                for pg in range(1, n_pages + 1)
                if (results / f"pg-{pg:03d}.json").exists()]
    stamp = reader_stamp(reader="text")
    report = {
        "slice": {"first": 1, "count": n_pages, "pages_done": pages_done},
        "totals": {"rows": rows_total, "clean": rows_total, "suspects": 0,
                   "clean_ratio": 1.0},
        # الدور المُعلن للتذييل: **ملخّص فترة** لا تراكميٌّ لكل صفحة ⇒ فوتر كل
        # صفحة «غائب» بصدق، والمجاميع المطبوعة تُسجَّل تشهّداً مستقلاً يُفحص
        # بفحصه هو (ولا يُقحَم في شاهد الأعمدة التراكمي).
        "footer_role": "period_summary",
        "period_summary": period_summary,
        "footer": {"ok": 0, "mismatch": 0, "unchecked": 0,
                   "absent": pages_done, "gap": 0},
        "page_numbers": {"gaps": [], "duplicates": {}, "backwards": {}},
        "reader_stamp": stamp,
        "corpus_provenance": {"reader": stamp, "legacy_unstamped_pages": 0,
                              "stamp_conflict_pages": 0,
                              "declaration": "كوربوسٌ بنسبٍ واحد (قارئٌ حتميّ)"},
        "usage": {"cost": 0.0, "calls": 0},
        "per_page": per_page,
    }
    (out_dir / "slice_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = Path(pdf_path)
    return {"doc_id": doc_id or hashlib.sha256(doc.read_bytes()).hexdigest()[:16],
            "label": label, "pages": n_pages, "pages_with_rows": pages_done,
            "rows": rows_total, "written_to": str(out_dir), "stamp": stamp,
            "period_summary": period_summary}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True, type=Path)
    ap.add_argument("--emit-run", type=Path, default=None,
                    help="مجلد تشغيلة تُكتب فيه results/pg-NNN.json بشكل المشروع")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if args.emit_run:
        report = emit_run(args.pdf, args.emit_run)
        report["measured_on"] = _date.today().isoformat()
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return

    rows = read_rows(args.pdf)
    if args.limit:
        rows = rows[:args.limit]
    print(json.dumps({"rows": len(rows),
                      "rows_without_date": sum(1 for r in rows if not r["date"]),
                      "sample": rows[0] if rows else None},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
