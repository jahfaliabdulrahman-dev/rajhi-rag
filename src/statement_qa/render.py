"""Pure rendering logic, extracted from app.py so it can be tested.

`app.py` is 800+ lines of Gradio layout with zero tests, and the audit found
that the untested functions inside it were exactly the ones shaping what a
reader sees: the row's verification column, the citation parser that decides
which rows the evidence panel shows, and the text of the answer. Those are
pure functions — they live here now, covered by tests, while app.py keeps the
wiring (audit P3-4).
"""
from __future__ import annotations

import re

from statement_qa.verification import caution, verdict_label

_ARG_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_REF_RE = re.compile(
    r"صفحة\s*([٠-٩0-9]+)[^\d٠-٩]{0,14}?صف(?:وف)?\s*([٠-٩0-9]+)"
    r"(?:\s*[–\-—]\s*([٠-٩0-9]+))?")
_BARE_REF_RE = re.compile(
    r"(?:^|[^\d٠-٩])صف(?:وف)?\s*([٠-٩0-9]+)(?:\s*[–\-—]\s*([٠-٩0-9]+))?")


def count_ar(n: int, one: str, two: str, few: str, many: str) -> str:
    """العددُ ومعدودُه بالعربيّة — **موضعٌ واحد** لصيغه الأربع: واحدٌ · اثنان · ٣–١٠ (جمعٌ) · ١١ فأكثر وصفرٌ (تمييزٌ مفرد).
    `few` و`many` يحملان `{n}`. (البروفةُ الحيّة 2026-10-31: «1 سؤالًا» و«1 ملفًّا» — كلُّ موضعٍ كتب صيغةَ الكثرة وحدها.)"""
    if n == 1:
        return one
    if n == 2:
        return two
    return (few if 3 <= n <= 10 else many).format(n=n)


def money(v) -> str:
    """تُفوَّض إلى الموضع الواحد (`statement_qa.money`) — فلا نسختان تفترقان."""
    from statement_qa.money import money as _m                                   # noqa: PLC0415
    return _m(v)


def date_cell(row: dict) -> str:
    """Gregorian `YYYY/MM/DD` for the table and the export; `*` = inherited.

    The printed cell may carry both calendars (hijri first) or separators —
    `contract_rows.normalize_date`, the one date reader, reads either — and an
    unparseable cell is shown as printed, never dropped.
    """
    from statement_qa.contract_rows import normalize_date

    d = str(row.get("date") or "").strip()
    if not d:
        return "—"
    iso = normalize_date(d)[0]
    shown = iso.replace("-", "/") if iso else d
    return shown + ("*" if row.get("date_source") == "inherited" else "")


# **أعمدةُ جدول الصفوف بترتيبها** (ما يُعيده `row_record`؛ يحرس تطابقَهما `tests/test_table_fits.py`).
ROW_COLUMNS = ("#", "الصفحة", "التاريخ", "الوصف", "النوع", "مدين", "دائن", "الرصيد", "الحالة", "التحقق")

# **حصّةُ كلّ عمودٍ من عرض الجدول — موضعٌ واحدٌ للجدولين** (جدولُ الكشف ولوحةُ الأدلّة، وفيها عمودُ الاستشهاد حين يكون).
# **العِلّة (صورُ حزمة التسليم 2026-11-01 · مقيس):** بلا عرضٍ مُعلَن تتّسع Gradio الأعمدةَ بقدر محتواها، فكان الجدولُ ١٥٧٣ في
# صندوقٍ ١٤٧٢ حتى على أقصى عرضٍ للصفحة ⇒ الرصيدُ مقطوع، و«الحالة»/«التحقق» خلف تمريرٍ جانبيّ. والبيانُ يلتفّ داخل حصّته (`wrap=True`).
_COLUMN_SHARE = {"#": 4, "استشهد به الجواب": 6, "الصفحة": 5, "التاريخ": 8, "الوصف": 33, "النوع": 12,
                 "مدين": 8, "دائن": 8, "الرصيد": 9, "الحالة": 7, "التحقق": 6}


def column_widths(columns) -> list[str]:
    """عروضُ الأعمدة نِسَبًا مئويّةً مجموعُها ١٠٠ — لأيّ ترتيبٍ أو عددٍ من الأعمدة (عمودٌ غيرُ معروفٍ يأخذ حصّةً وسطى)."""
    shares = [_COLUMN_SHARE.get(str(c), 8) for c in columns]
    total = sum(shares) or 1
    return [f"{100 * s / total:.2f}%" for s in shares]


def row_record(no: int, row: dict, verdicts: dict | None = None) -> dict:
    """Excel-style display record: real النوع + مدين/دائن split + verification.

    Global row numbers stay stable across filtering — the same numbers the
    tools cite («صف 94»). Direction lives ONLY in which of the two amount
    columns carries the value; it is not a type claim.

    The «التحقق» column is the page's oracle verdict. The export is the artefact
    that leaves the system and gets decided upon, and until now it carried no
    sign at all that a row came from a scan gap or a frameless page (P1-5).
    """
    verdicts = verdicts or {}
    mv = money(row["movement"])
    status = "✓" if row["ok"] else "⚠ مشبوه"
    if (row["ok"] and row.get("kind") == "txn" and mv
            and not (row.get("side") or "")):
        # the amount is real but its DIRECTION could not be derived (a page-start
        # edge where the opening row was missed) — never guess a side column
        status = "◌ اتجاه غير محسوم"
    return {"#": no,
            "الصفحة": row["page"],
            "التاريخ": date_cell(row),
            "الوصف": (row.get("desc") or "—"),
            "النوع": row.get("type") or
                    ("رصيد افتتاحي" if row.get("kind") == "opening" else "حركة"),
            "مدين": mv if row["side"] == "debit" else "",
            "دائن": mv if row["side"] == "credit" else "",
            "الرصيد": money(row["balance"]),
            "الحالة": status,
            "التحقق": verdict_label(verdicts.get(row["page"]))}


def answer_refs(answer: str) -> list[tuple[int | None, int, int]]:
    """Citations inside the answer text: (page|None, first_row, last_row)."""
    refs: list[tuple[int | None, int, int]] = []
    for m in _REF_RE.finditer(answer or ""):
        try:
            pg = int(m.group(1).translate(_ARG_DIGITS))
            a = int(m.group(2).translate(_ARG_DIGITS))
            b = int(m.group(3).translate(_ARG_DIGITS)) if m.group(3) else a
        except ValueError:
            continue
        if b < a:
            a, b = b, a
        refs.append((pg, a, b))
    if not refs:
        for m in _BARE_REF_RE.finditer(answer or ""):
            try:
                a = int(m.group(1).translate(_ARG_DIGITS))
                b = int(m.group(2).translate(_ARG_DIGITS)) if m.group(2) else a
            except ValueError:
                continue
            if b < a:
                a, b = b, a
            refs.append((None, a, b))
    return refs


def rows_for_refs(rows: list[dict], refs, cap: int = 60,
                  verdicts: dict | None = None) -> list[dict]:
    """Rows matching the citations, capped, as display records."""
    picked: list[tuple[int, dict]] = []
    for i, r in enumerate(rows, start=1):
        for pg, a, b in refs:
            if (pg is None or r["page"] == pg) and a <= i <= b:
                picked.append((i, r))
                break
    return [row_record(i, r, verdicts) for i, r in picked[:cap]]


def answer_text(res, page_of: dict, verdicts: dict) -> str:
    """The text a reader receives, with the two disclosures that must not be silent.

    1. A tool failure: the answer was NOT computed from the statement, and
       saying so is the difference between a caveat and a false number
       (audit P2-10 — the fallback used to happen invisibly).
    2. A page whose verdict is not «documented», named by page and reason
       (audit P1-4 — the verification layer never reached the answer).
    """
    text = str(getattr(res, "answer", "") or "")
    if getattr(res, "truncated", False):
        # **حالةٌ مُسمّاةٌ تُقرأ قبل العامّ (R124-1 · مراجعة ١٢٤):** الردُّ قُطع عند حدّ الرموز قبل
        # أن يُكمل الجواب ⇒ فما حسبته الأدواتُ **محفوظٌ في لوحة الأدلّة**، ونصُّ الجواب ناقصٌ لا
        # يُعتمد رقمًا. واللافتةُ تقول الحالتين معًا (حسابٌ وقع · جوابٌ ناقص) فلا تُقرأ قطعًا محضًا.
        return ("⚠ **قُطع ردُّ النموذج عند حدّ الرموز** قبل أن يُكمل الجواب: "
                "الأثرُ أدناه مما حسبته الأدوات فعلًا، **ونصُّ الجواب ناقصٌ لا يُعتمد رقمًا** — "
                "أعد صياغة السؤال أو جزّئه.\n\n" + text)
    if getattr(res, "limit_hit", False):
        # **لافتةٌ خاصّةٌ بالحالة المُسمّاة (R111-1 · مراجعة ١١١):** كان بلوغُ حدّ الخطوات يُعرض
        # تحت اللافتة العامّة («تعذّرت الأدوات — جوابٌ وصفي») وهي **ليست** وصفَ حاله: الجوابُ لم
        # يُكمَل لأنّ السؤال تجاوز حدَّ خطواته، لا لأنّ أداةً تعذّرت. واللافتةُ الأخصُّ تُقرأ أوّلًا.
        return ("⚠ بلغ السؤالُ **حدَّ الخطوات المسموح** فلم يُكمَل حسابًا من الكشف، "
                "فلا تعتمد أي رقم فيه — أعد صياغة السؤال أو جزّئه.\n\n" + text)
    if getattr(res, "tools_failed", False):
        return ("⚠ تعذّرت الأدوات — هذا الجواب وصفي ولم يُحسَب من الكشف، "
                "فلا تعتمد أي رقم فيه.\n\n" + text)
    if getattr(res, "ungrounded", False):
        # **والنصُّ يوصف حالَه لا صيغةَ سؤاله (قاسه مقعدُ المواصفة في R104):** البوّابةُ صارت تُطلَق
        # على **الجواب** أيضًا (مبلغٌ بلا نداءِ أداة) ⇒ فسؤالُ سلسلةٍ غيرُ رقميّ يُرفض بالحكم نفسه،
        # وكان النصُّ يقول «سؤال رقمي» ⇒ يصف نابضًا غيرَ نابضه.
        return ("⚠ جوابٌ يحمل أرقامًا بلا أي استدعاء أداة — الرقمُ أدناه من نص القطع "
                "لا من حساب على الكشف، فلا تعتمدها.\n\n" + text)
    pages = [page_of.get(n) for n in (getattr(res, "used_row_nos", None) or [])]
    warn = caution([p for p in pages if p is not None], verdicts)
    return text + (("\n\n" + warn) if warn else "")


def evidence_mode(res) -> str:
    """Which evidence the panel may honestly show.

    'none'     — the tools failed: the panel is emptied on purpose, because
                 evidence assembled from the model's own citations is evidence
                 for a claim that was never computed (audit P2-10);
    'typed'    — **الاستشهادُ من النوع (أ-٤)**: أرقامُ الصفوف جاءت في كائنٍ مُقيَّد لا من نثرٍ
                 يُقتطع بتعبيرٍ نمطيّ ⇒ فهي **تُعلَّم** في لوحة ما بنى الجواب (الأثر — `app._typed_evidence`،
                 بروفةُ CP1 2026-10-31)، وكلُّ استشهادٍ بلا شاهدِ أثرٍ يُعلَن؛
    'tools'    — rows a tool actually touched (the strong case);
    'fallback' — a descriptive answer: citations, else retrieval pages.
    """
    if getattr(res, "tools_failed", False) or getattr(res, "ungrounded", False):
        return "none"      # no computed evidence exists to show
    if getattr(res, "citation_mode", "prose") == "typed" and getattr(res, "cited_row_ids", None):
        return "typed"     # النوعُ مقدَّمٌ على القصّ: هو الذي يُصرّح، والأثرُ هو الذي يشهد
    if getattr(res, "used_row_nos", None):
        return "tools"
    return "fallback"
