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
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from statement_qa.row_audit import DEBIT_ONLY_DESCRIPTIONS  # noqa: E402
from statement_qa.gap_ledger import (  # noqa: E402
    PageFacts, build_gap_entries, debit_credit, identity,
)
from statement_qa.vlm_reader import chain_derive  # noqa: E402

# الأوصاف التي لا تكون **دائنة** أبداً في هذا الكشف: مدفوعات نقاط البيع وسحوب
# الصراف تخرج من الحساب لا تدخله. فصفّ يجمع وصفاً منها بمبلغ دائن = الوصف أُزيح
# عن مبلغه (أو قراءة خاطئة) — كاشف حتمي بلا رؤية وبلا كلفة. القائمة في نواة
# المشروع (`row_audit`) لا هنا: مصدر واحد للحقيقة.
DEBIT_ONLY = DEBIT_ONLY_DESCRIPTIONS
SIDE_AR = {"credit": "دائن", "debit": "مدين", "": "غير محدّد"}

ARABIC_VERDICT = {
    "ok": "مطابق لإجمالياته المطبوعة",
    "gap": "فجوة إطارات (ورق غائب من المسح)",
    "absent": "لا سطر إجماليات مطبوع",
    "unchecked": "غير قابل للتحقق (جارُه بلا إطار)",
    "gate_rejected": "لم تُقرأ (رفضتها بوابة جودة المسح)",
}


def _row_date_source(row: dict) -> str:
    """مصدر تاريخ الصفّ بحكم القانون — لا بالتخمين."""
    from statement_qa.row_dates import resolve
    try:
        return str(resolve(row)["date_source"])
    except Exception:                                    # noqa: BLE001
        return "unknown"


def page_verdict(entry: dict, last_page: int) -> str:
    """حكم الصفحة بلفظه — ولا يُوهم بعيبٍ حيث الورق سليم.

    صفحةٌ **بلا حركات** ليست صفحة عمليات ناقصة الإجماليات: هي ملخّص الحساب
    (الصفحة الختامية بعد آخر حركة) أو ورقة بيضاء في الأصل. وتسميتها «لا سطر
    إجماليات مطبوع» تُقرأ عيباً في الورق أو في قراءتنا، وكلاهما غير صحيح.
    """
    if not (entry.get("rows") or 0):
        if entry.get("footer") == "gap":
            return ARABIC_VERDICT["gap"]
        if entry.get("page") == last_page:
            return "ملخص الحساب — صفحة ختامية بلا حركات"
        return "صفحة بلا حركات (ليست صفحة عمليات)"
    val = str(entry.get("footer") or "")
    return ARABIC_VERDICT.get(val, val)

# ————— التواريخ: ثلاثة أصناف لا واحد —————
# The reader returned the printed date as it found it, and the paper (and the
# model) mixed digit sets: Arabic-Indic ٠-٩ (U+0660), **Extended** Arabic-Indic
# ۰-۹ (U+06F0 — a different block, not a variant of the first), Latin, and even
# both inside one value (`۲۰۱۳۱۲۰٥`). Measured across the 629 pages: 2949 / 1368
# / 492 / 425 rows plus 504 with no usable date. An export that leaves that
# column alone hands the defect to the buyer, so it is normalised here — with
# the original kept beside it and the failures counted, never silently dropped.
_DIGIT_MAP = {chr(0x0660 + i): str(i) for i in range(10)}
_DIGIT_MAP.update({chr(0x06F0 + i): str(i) for i in range(10)})
_DATE_SOURCE_AR = {
    "cell": "من خانة التاريخ في الورق",
    "text": "من نصّ السطر نفسه (الخانة كانت فارغة)",
    "not_a_movement": "ليس حركة — لا تاريخ عليه",
    "missing": "بلا تاريخ (لا في الخانة ولا في النصّ)",
}
_DATE_STATUS_AR = {
    # سطرٌ ليس حركة (ملخّص حساب أو رصيد افتتاحي): لا تاريخ عليه ولا سلسلة — ووسمه
    # يمنعه أن يُقرأ «تاريخاً ناقصاً» أو بنداً «لم يُثبت»، وهو بريء من الاثنين.
    "not_a_movement": "ليس حركة (سطر ملخّص/افتتاحي)",
    "ok": "تاريخ كامل",
    "incomplete": "تاريخ غير مكتمل (أقل من ٨ خانات)",
    "implausible": "تاريخ غير معقول (خارج 1900–2100)",
    "missing": "بلا تاريخ مطبوع",
}


def to_ascii_digits(raw: str) -> str:
    """كل مجموعات الأرقام → لاتينية. الصيغة المختلطة تُطبَّع بلا استثناء."""
    return "".join(_DIGIT_MAP.get(ch, ch) for ch in raw)


def normalize_date(raw: str | None) -> tuple[str, str, int | None]:
    """(ISO date | '', status, year) — YYYYMMDD كما طُبع، بمجموعة أرقام أيّاً كانت.

    Returns `iso=''` when the value cannot honestly be called a date; the status
    says which kind of failure it is, so the summary can count them instead of
    hiding them behind an empty cell.
    """
    if raw is None or not str(raw).strip():
        return "", "missing", None
    digits = "".join(ch for ch in to_ascii_digits(str(raw)) if ch.isdigit())
    if len(digits) != 8:
        return "", "incomplete", None
    year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
    if not (1900 <= year <= 2100) or not (1 <= month <= 12) or not (1 <= day <= 31):
        return "", "implausible", None
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}", "ok", year

HEAD_FILL = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(color="FFFFFF", bold=True, size=11)
NOTE_FONT = Font(italic=True, size=10, color="555555")


def _dec(value) -> Decimal | None:
    """الرقم كـDecimal — السلسلة تعمل بـDecimal لا بنصوص."""
    if value is None:
        return None
    try:
        return Decimal(str(to_ascii_digits(str(value)).replace(",", "")))
    except (ArithmeticError, ValueError):
        return None


def _row_state(der: dict) -> str:
    """حكم السلسلة على الصفّ — بصياغة يقرؤها محاسب لا مبرمج."""
    if der.get("balance") is None:
        return "بلا رصيد مقروء — خارج السلسلة"
    mv = der.get("derived_movement")
    if mv is None:
        return "بلا حركة مقروءة"
    if der.get("opening"):
        return "رصيد مرحّل/افتتاحي (ليس حركة)"
    if Decimal(str(mv)) == 0:
        # سطر إجماليات قرأه القارئ صفّاً: لا فرق رصيد فيه، ومبلغه المطبوع
        # (الإجمالي التراكمي) لا يساوي صفراً ⇒ يُسمّى بما هو لا بما ظهر به.
        note = (" — ومبلغه المطبوع لا يطابق فرق الرصيد (إجماليات مُقروءة حركة)"
                if der.get("ok") is False else "")
        return f"لا حركة فيه: سطر إجماليات أو صفّ مكرّر{note}"
    if der.get("ok") is False:
        return "مشكوك: المبلغ المطبوع لا يطابق فرق الرصيد"
    return "حركة مثبتة بالسلسلة"


def _shift_suspect(row: dict, der: dict) -> str:
    """وصف لا يمكن أن يكون دائناً + مبلغ دائن ⇒ الوصف أُزيح عن مبلغه."""
    if der.get("side") != "credit":
        return ""
    desc = str(row.get("desc") or "")
    hit = next((d for d in DEBIT_ONLY if d in desc), None)
    return (f"الوصف «{hit}» لا يكون دائناً في هذا الكشف — الوصف أُزيح عن مبلغه"
            if hit else "")


def derive_pages(raw_by_page: list[tuple[int, list[dict]]]) -> list[list[dict]]:
    """يشتقّ كل صفحة بالسلسلة **بنفس دالة المحكَّم**، بالترتيب مع ترحيل الرصيد.

    الحاجة: المحكَّم يحكم على الصفوف المشتقّة، والتصدير كان ينشر الخام ⇒ كان
    يُسلّم ما لم يُثبت. الاشتقاق هنا ليس اجتهاداً جديداً: نفس الدالة، ونفس
    الترتيب، والتحقق أسفل البناء يقارن نتيجته بأحكام التقرير صفحةً صفحة.
    """
    out: list[list[dict]] = []
    prev: Decimal | None = None
    for _page, raw in raw_by_page:
        converted = [{**r, "movement": _dec(r.get("movement")),
                      "balance": _dec(r.get("balance"))} for r in raw]
        try:
            derived = chain_derive(converted, prev_balance=prev)
        except Exception:                       # noqa: BLE001 — لا نخمّن عند الفشل
            derived = [{**r, "derived_movement": None, "side": "", "ok": None,
                        "opening": False} for r in converted]
        out.append(derived)
        last = next((r["balance"] for r in reversed(derived)
                     if r.get("balance") is not None), None)
        # **الاستمرارية**: صفحة بلا رصيد مقروء (بيضاء/فارغة) لا تُصفّر الرصيد
        # العابر — وإلا صار أول صفّ في الصفحة التالية "مرساة" وسقط مبلغه من
        # الحساب. خط الأنابيب يحمله (`prev_closing` يبقى)، وهذا يطابقه.
        if last is not None:
            prev = last
    return out


def load(run: Path) -> tuple[list[dict], dict, dict, dict]:
    """(rows, report, per-page verdicts, per-page repair flags) — straight from
    the run's own files. The repair flags live in the checkpoints (the evidence),
    not in the report's legacy fields."""
    report = json.loads((run / "slice_report.json").read_text(encoding="utf-8"))
    per_page = {int(e["page"]): e for e in report.get("per_page") or []}
    flags: dict[int, dict] = {}

    caches = sorted((run / "results").glob("pg-*.json"))
    loaded: list[tuple[int, dict, list[dict], dict]] = []
    for cache in caches:
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue                      # a truncated checkpoint is reported, not guessed
        page = int(data.get("pg") or 0)
        loaded.append((page, data, data.get("raw_rows") or [],
                       per_page.get(page, {})))

    derived_pages = derive_pages([(p, raw) for p, _d, raw, _v in loaded])
    rows: list[dict] = []
    for (page, data, raw, verdict), derived in zip(loaded, derived_pages):
        flags[page] = {
            "recovered": bool(data.get("recovered")),
            "reread": bool(data.get("reread")),
            "error": bool(data.get("error")),
            "arbitrated": bool(data.get("arbitrated_by")),
            # القيم **المطبوعة التراكمية** كما قرأها القارئ من الورقة (لا
            # الفروق الحسابية في تفصيل التقرير): هي وحدها إجمالي الكشف.
            "printed": data.get("footer") or {},
        }
        for i, (row, der) in enumerate(zip(raw, derived), start=1):
            iso, status, year = normalize_date(row.get("date"))
            # **سطرٌ بلا رصيد مطبوع ليس حركة**: كل حركة في هذا الكشف تحمل رصيداً
            # جارياً؛ والذي لا يحمله هو سطر ملخّص الحساب (اجمالي الايداعات ·
            # اجمالي السحوبات · رصيد الاقفال …) أو الرصيد الافتتاحي. ووسمه هنا
            # يُخرجه من «الحركات» ومن «بلا تاريخ» ومن «ما لم يُثبت» معاً —
            # وهو بريء من الثلاثة: لا سلسلة تُقاس عليه ولا تاريخ يُطلب منه.
            is_movement = row.get("balance") is not None
            if not is_movement and status == "missing":
                status = "not_a_movement"
            rows.append({
                "page": page,
                "row_no": i,
                "printed_page": data.get("page_no"),
                "date": row.get("date"),
                "date_iso": iso,
                "date_status": status,
                # مصدر التاريخ: من خانة الورق أو من نصّ السطر نفسه (تعميم لاحق على
                # صفحات قُرئت قبل وجود القانون) — يُعرض بلفظه في ورقة الحركات.
                # لا يُختلق مصدر: إن لم يُعلن الكاش مصدراً نسأل قانون
                # التواريخ عن الصفّ نفسه (قد يكون missing أو ليس حركة)
                # — وإلا كُتب «من خانة الورق» على صفّ لا تاريخ له (كشفه مدقّق خارجي).
                "date_source": str(row.get("date_source")
                                   or _row_date_source(row)),
                "year": year,
                "desc": row.get("desc"),
                "printed_movement": row.get("raw_movement") or row.get("movement"),
                "printed_balance": row.get("raw_balance") or row.get("balance"),
                "movement": row.get("movement"),
                "balance": row.get("balance"),
                "derived_movement": der.get("derived_movement"),
                "side": der.get("side") or "",
                "opening": bool(der.get("opening")),
                "chain_ok": der.get("ok"),
                "row_state": (
                    # **مرساةُ فجوة**: مبلغٌ مطبوع ورصيدٌ مطبوع ⇒ حركة فعليّة،
                    # لكن فرق الرصيد يبتلع ورقةً غائبة فلا تُقفله السلسلة. ووسمُها
                    # «ليس حركة» كان خطأً يُنكر حركةً مبصوطة على الورق.
                    "حركة — مرساة بعد ورقة غائبة (المبلغ مطبوع ولا تُقفله السلسلة)"
                    if (is_movement and der.get("opening")
                        and _num0(row.get("movement")))
                    else (_row_state(der) if is_movement
                          else "سطر ملخّص/افتتاحي — ليست حركة")),
                "shift": _shift_suspect(row, der),
                "footer": verdict.get("footer"),
                "counted": verdict.get("rows"),
            })
    return rows, report, per_page, flags


def _num0(value) -> Decimal | None:
    """القيمة كـDecimal للجمع والمقارنة (لا للعرض)."""
    if value is None:
        return None
    try:
        return Decimal(str(to_ascii_digits(str(value)).replace(",", "")))
    except (ArithmeticError, ValueError):
        return None


def _num(value) -> float | None:
    """القيمة كما فُهمت رقماً — أو None. تُستعمل للفرز والجمع فقط."""
    if value is None:
        return None
    text = to_ascii_digits(str(value)).replace(",", "").replace("٫", ".").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def summary_facts(rows: list[dict], report: dict, per_page: dict,
                  flags: dict | None = None) -> dict:
    """كل أرقام الملخص، محسوبة مرة واحدة ومُعلَنة الطريقة في الورقة نفسها."""
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["date_status"]] = by_status.get(r["date_status"], 0) + 1
    dates = sorted(r["date_iso"] for r in rows if r["date_iso"])
    years = sorted({r["year"] for r in rows if r["year"]})
    ok_pages = [e for e in per_page.values() if e.get("footer") == "ok"]
    last_ok = max(ok_pages, key=lambda e: e["page"]) if ok_pages else None

    # الإجماليات المطبوعة **تراكمية من بداية الكشف** (قِيست على الصفحات: ص190
    # مدين 433794.02 وفرقه عن الدائن = الرصيد 24.39؛ ص628 892646.90/893217.49
    # وفرقه 570.59 = الرصيد) ⇒ **جمعها عبر الصفحات بلا معنى**، وهو خطأ وقع في
    # نسخة سابقة من هذا الملف. الرقم الصحيح: قيم آخر صفحة مطابقة (إجمالي الكشف).
    printed_debits = printed_credits = last_balance = None
    if last_ok:
        for item in (last_ok.get("footer_detail") or []):
            if item.get("field") == "balance":
                last_balance = item.get("footer")
    if last_ok and flags:
        last_printed = (flags.get(last_ok["page"]) or {}).get("printed") or {}
        printed_debits = last_printed.get("debits") or printed_debits
        printed_credits = last_printed.get("credits") or printed_credits
        last_balance = last_printed.get("balance") or last_balance

    # الترتيب على **الحركات المثبتة بالسلسلة** فقط: الصفوف التي لا حركة فيها
    # (سطر إجماليات قرأه القارئ صفّاً — وقع فعلاً في ص190) كانت تتصدّر الترتيب
    # بـ433,794.02 وهو رقم ليس حركة.
    ranked = [(abs(Decimal(str(r["derived_movement"]))), r) for r in rows
              if r["row_state"] == "حركة مثبتة بالسلسلة"
              and _num(r["derived_movement"]) not in (None, 0)]
    biggest = max(ranked, key=lambda p: p[0]) if ranked else None
    smallest = min(ranked, key=lambda p: p[0]) if ranked else None
    txn_rows = [r for r in rows if str(r["row_state"]).startswith("حركة")]
    shift_rows = [r for r in rows if r["shift"]]
    # سطور الملخّص/الافتتاح ليست حركات: سلسلة الرصيد لا تُقاس عليها، فسقوطها من
    # فحص السلسلة ليس عيباً يُعلن — والملخص يعدّها في «سطور ليست حركة».
    chain_suspect = [r for r in rows if r["chain_ok"] is False
                     and r["row_state"] != "سطر ملخّص/افتتاحي — ليست حركة"]
    read_ms = [e["ms_read"] for e in per_page.values() if e.get("ms_read")]
    return {
        "rows": len(rows),
        "txn_rows": len(txn_rows),
        "nontxn_rows": len(rows) - len(txn_rows),
        "shift_rows": shift_rows,
        "chain_suspect": chain_suspect,
        "counted": sum(int(e.get("rows") or 0) for e in per_page.values()),
        "pages": len(per_page),
        "date_status": by_status,
        "dates_ok": by_status.get("ok", 0),
        "first_date": dates[0] if dates else "",
        "last_date": dates[-1] if dates else "",
        "years": years,
        "ok_pages": len(ok_pages),
        "last_ok_page": (last_ok or {}).get("page"),
        "printed_debits": printed_debits,
        "printed_credits": printed_credits,
        "printed_balance": last_balance,
        "biggest": biggest,
        "smallest": smallest,
        "median_page_s": round(_median(read_ms) / 1000, 2) if read_ms else None,
        "verdicts": report.get("footer") or {},
        "cost": (report.get("usage") or {}).get("cost"),
    }


def summary_sheet(facts: dict, rows: list[dict], report: dict) -> list[list]:
    ds = facts["date_status"]
    return [
        ["نظرة عامة", "", ""],
        ["الصفوف المقروءة من الكشوف", facts["rows"], "كل سطر عاد به القارئ من الورق"],
        ["منها حركات (مثبتة بالسلسلة أو مرساة فجوة)", facts["txn_rows"],
         "أثبتها فرق الرصيد — هذا هو العدد الذي يقوم عليه التقرير"],
        ["منها سطور ليست حركة", facts["nontxn_rows"],
         "رصيد مرحّل/افتتاحي أو سطر إجماليات أو صفّ بلا حركة — لا تُعدّ ولا تدخل الترتيب"],
        ["صفوف مشكوك في إزاحة وصفها", len(facts["shift_rows"]),
         "وصف لا يكون دائناً في هذا الكشف جاء بمبلغ دائن — التفصيل في «ما لم يُثبت»"],
        ["صفوف خالفت السلسلة", len(facts["chain_suspect"]),
         "المبلغ المطبوع لا يطابق فرق الرصيد — أعاد التشغيل قراءتها"],
        ["الصفوف المحتسبة في تقرير التشغيل", facts["counted"],
         "عدّاد التشغيل نفسه — قد يختلف عن عدد الصفوف أعلاه"],
        ["الصفحات", facts["pages"], "صفحة ممسوحة"],
        ["الصفحات المطابقة لإجمالياتها المطبوعة", facts["ok_pages"],
         "حكم المحكَّم: مجموع الصفوف == الإجمالي المطبوع أسفل الصفحة"],
        ["", "", ""],
        ["التواريخ", "", ""],
        ["تاريخ كامل (٨ خانات)", ds.get("ok", 0), "شمل كل مجموعات الأرقام المطبوعة"],
        ["تاريخ غير مكتمل", ds.get("incomplete", 0),
         "أقل من ٨ خانات كما طُبع — لم يُخمَّن ولم يُصحَّح"],
        ["تاريخ غير معقول", ds.get("implausible", 0), "خارج 1900–2100"],
        ["بلا تاريخ مطبوع", ds.get("missing", 0), "سطور افتتاحية/ترحيل بلا تاريخ على الورق"],
        ["أول تاريخ", facts["first_date"], "من التواريخ المكتملة فقط"],
        ["آخر تاريخ", facts["last_date"], "من التواريخ المكتملة فقط"],
        ["السنوات المشمولة", " · ".join(str(y) for y in facts["years"]),
         f"عددها {len(facts['years'])}"],
        ["", "", ""],
        ["الإجماليات المطبوعة (تراكمية من بداية الكشف — لا تُجمع)", "", ""],
        ["إجمالي المدين حتى آخر صفحة مطابقة", facts["printed_debits"],
         f"من سطر الإجماليات في الصفحة {facts['last_ok_page']} — رقم الورق لا حسابنا. "
         f"وهو **تراكمي** (فرقه عن الدائن = الرصيد) فلا يُجمع مع صفحة أخرى"],
        ["إجمالي الدائن حتى آخر صفحة مطابقة", facts["printed_credits"],
         "نفس المصدر ونفس القيد: تراكمي"],
        ["الرصيد الختامي المطبوع", facts["printed_balance"],
         f"من نفس السطر في الصفحة {facts['last_ok_page']} — وفرق المدين عن الدائن يساويه"],
        ["", "", ""],
        ["الحركات", "", ""],
        ["أكبر حركة", f"{facts['biggest'][0]:,.2f}" if facts["biggest"] else "",
         f"صفحة {facts['biggest'][1]['page']} · صفّ {facts['biggest'][1]['row_no']}"
         if facts["biggest"] else ""],
        ["أصغر حركة (غير صفرية)", f"{facts['smallest'][0]:,.2f}" if facts["smallest"] else "",
         f"صفحة {facts['smallest'][1]['page']} · صفّ {facts['smallest'][1]['row_no']}"
         if facts["smallest"] else ""],
        ["", "", ""],
        ["حالة الإثبات", "", ""],
        ["صفحات بلا حركات أو بلا سطر إجماليات", facts["verdicts"].get("absent", 0),
         "منها ملخّص الحساب (الصفحة الختامية) وأوراق بيضاء فعلاً — ليست صفحات عمليات"],
        ["صفحات غير قابلة للتحقق", facts["verdicts"].get("unchecked", 0), "جوارها بلا إطار"],
        ["فجوات إطارات", facts["verdicts"].get("gap", 0), "أوراق غائبة من المسح نفسه"],
        ["", "", ""],
        ["التشغيل", "", ""],
        ["الكلفة المدفوعة", f"${facts['cost']:.4f}" if isinstance(facts["cost"], (int, float)) else "",
         "مجموع usage.cost في الكاش"],
        ["وسيط زمن الصفحة (ث)", facts["median_page_s"], "المقيس، لا المقدَّر"],
        ["طريقة كل رقم أعلاه", "من أدلة التشغيل أو من الإجماليات المطبوعة",
         "لا رقم في هذه الورقة أُعيد اشتقاقه يدوياً"],
    ]


def question_set(rows: list[dict], facts: dict, per_page: dict,
                 flags: dict) -> tuple[list[list], list[list]]:
    """(الأسئلة, الصفوف الداعمة) — حساب حتمي بلا نموذج لغوي.

    Every answer here is a filter or a sum over the run's own evidence, so the
    same command returns the same number tomorrow. Questions that need a model
    (interpretation, legal meaning) are deliberately absent — an export that
    answers those would be guessing with a confident tone.
    """
    questions: list[list] = []
    evidence: list[list] = []
    ds = facts["date_status"]

    def add(qid: int, question: str, answer, method: str, basis: str) -> None:
        questions.append([qid, question, answer, method, basis])

    add(1, "كم عدد الحركات المقروءة؟", facts["rows"],
        "عدّ كل سطر عاد به القارئ من الورق",
        f"منها {facts['txn_rows']} حركة أثبتها فرق الرصيد · "
        f"و{facts['nontxn_rows']} سطراً ليس حركة")
    add(2, "كم عدد الصفحات ولم تُقبل منها كم صفحة؟",
        f"{facts['pages']} صفحة · {facts['ok_pages']} مطابقة · "
        f"{facts['verdicts'].get('absent', 0)} بلا حركات أو بلا إجماليات · "
        f"{facts['verdicts'].get('unchecked', 0)} غير قابلة للتحقق",
        "حكم المحكَّم لكل صفحة", "ورقة «التحقق لكل صفحة»")
    add(3, "ما إجمالي المدين في الكشوف؟", facts["printed_debits"] or "-",
        f"سطر الإجماليات المطبوع في الصفحة {facts['last_ok_page']} — **تراكمي** "
        f"من بداية الكشف، ففرقه عن الدائن = الرصيد ولا يُجمع مع صفحة أخرى",
        "من الورق مباشرة · رقم مطبوع لا محسوب")
    add(4, "ما إجمالي الدائن في الكشوف؟", facts["printed_credits"] or "-",
        "نفس السطر ونفس القيد: تراكمي", "وفرقه عن المدين يساوي الرصيد الختامي")
    add(5, "ما الرصيد الختامي المطبوع؟", facts["printed_balance"] or "-",
        "من سطر الإجماليات في آخر صفحة مطابقة", f"الصفحة {facts['last_ok_page']}")
    add(6, "ما مدى التواريخ؟",
        f"{facts['first_date']} → {facts['last_date']} "
        f"({len(facts['years'])} سنة)",
        "تصنيف ٨ خانات بعد توحيد مجموعات الأرقام الثلاث",
        f"مكتملة: {ds.get('ok', 0)} · غير مكتملة: {ds.get('incomplete', 0)} "
        f"· بلا تاريخ: {ds.get('missing', 0)}")
    if facts["biggest"]:
        amount, rec = facts["biggest"]
        add(7, "ما أكبر حركة؟", f"{amount:,.2f}",
            "فرز القيم المطلقة للحركات **المثبتة بالسلسلة** فقط — "
            "سطور الإجماليات والأرصدة المرحّلة مستثناة",
            f"صفحة {rec['page']} · صفّ {rec['row_no']}")
        evidence.append([7, rec["page"], rec["row_no"], rec["date_iso"], rec["desc"],
                         rec["derived_movement"], rec["balance"],
                         f"أكبر حركة (اتجاه: {SIDE_AR.get(rec['side'], '')})"])
    if facts["smallest"]:
        amount, rec = facts["smallest"]
        add(8, "ما أصغر حركة غير صفرية؟", f"{amount:,.2f}",
            "فرز القيم المطلقة للحركات المثبتة بالسلسلة",
            f"صفحة {rec['page']} · صفّ {rec['row_no']}")
        evidence.append([8, rec["page"], rec["row_no"], rec["date_iso"], rec["desc"],
                         rec["derived_movement"], rec["balance"],
                         f"أصغر حركة (اتجاه: {SIDE_AR.get(rec['side'], '')})"])
    odd = [r for r in rows if r["date_status"] != "ok"]
    add(9, "كم حركة بلا تاريخ صالح؟", len(odd),
        "تصنيف كل صفّ: مكتمل/غير مكتمل/بلا تاريخ",
        f"غير مكتملة {ds.get('incomplete', 0)} · بلا تاريخ {ds.get('missing', 0)} "
        f"· غير معقولة {ds.get('implausible', 0)}")
    for r in odd:
        evidence.append([9, r["page"], r["row_no"], r["date_iso"], r["desc"],
                         r["movement"], r["balance"], _DATE_STATUS_AR[r["date_status"]]])
    arb = sorted(p for p, f in flags.items() if f.get("arbitrated"))
    add(10, "كم صفحة احتاجت تحكيماً بشرياً؟", len(arb),
        "وسم arbitrated_by في كاش التشغيل", " · ".join(str(p) for p in arb) or "-")
    for r in rows:
        if r["page"] in arb:
            evidence.append([10, r["page"], r["row_no"], r["date_iso"], r["desc"],
                             r["movement"], r["balance"], "صفّ في صفحة محكَّمة"])
    repaired = sorted(p for p, f in flags.items() if f.get("recovered") or f.get("reread"))
    add(11, "كم صفحة أُصلحت آلياً (استدراك/إعادة قراءة)؟", len(repaired),
        "وسوم recovered/reread في كاش التشغيل",
        " · ".join(str(p) for p in repaired) or "-")
    add(12, "ما الكلفة المدفوعة ووسيط زمن الصفحة؟",
        f"${facts['cost']:.4f} · {facts['median_page_s']} ث" if isinstance(
            facts["cost"], (int, float)) else "-",
        "مجموع usage.cost ووسيط ms_read", "كاش التشغيل")
    add(13, "كم سطراً قرأه القارئ وليس حركة؟", facts["nontxn_rows"],
        "حكم السلسلة على كل صفّ: رصيد مرحّل/افتتاحي، أو لا فرق رصيد فيه "
        "(سطر إجماليات أو صفّ مكرّر)، أو بلا رصيد مقروء",
        "لا يُحتسب في أي مجموع ولا يدخل ترتيب الحركات")
    for r in rows:
        if r["row_state"] != "حركة مثبتة بالسلسلة":
            evidence.append([13, r["page"], r["row_no"], r["date_iso"], r["desc"],
                             r["printed_movement"], r["balance"], r["row_state"]])
    add(14, "كم صفّاً وصفه لا يطابق مبلغه (إزاحة وصف)؟", len(facts["shift_rows"]),
        "وصف مدين لا يكون دائناً في هذا الكشف (نقاط بيع/صراف) جاء بمبلغ دائن — "
        "دليل حسابي على أن الوصف أُزيح عن مبلغه، لا حكم بصري",
        " · ".join(f"ص{r['page']} صفّ{r['row_no']}" for r in facts["shift_rows"]) or "-")
    for r in facts["shift_rows"]:
        evidence.append([14, r["page"], r["row_no"], r["date_iso"], r["desc"],
                         r["derived_movement"], r["balance"], r["shift"]])
    add(15, "كم صفّاً خالف السلسلة (مبلغ مطبوع ≠ فرق الرصيد)؟",
        len(facts["chain_suspect"]),
        "مقارنة المبلغ المطبوع بفرق الرصيد لكل صفّ",
        " · ".join(f"ص{r['page']} صفّ{r['row_no']}" for r in facts["chain_suspect"]) or "-")
    for r in facts["chain_suspect"]:
        evidence.append([15, r["page"], r["row_no"], r["date_iso"], r["desc"],
                         r["printed_movement"], r["balance"], r["row_state"]])
    return questions, evidence



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


def gap_facts(rows: list[dict], per_page: dict, flags: dict) -> list:
    """يجمع ما يحتاجه محرّك الفجوات من الأدلة الموجودة أصلاً — بلا حساب جديد."""
    by_page: dict[int, list[dict]] = {}
    for r in rows:
        by_page.setdefault(r["page"], []).append(r)
    facts = []
    for page in sorted(by_page):
        entries = by_page[page]
        own = {"debits": Decimal("0"), "credits": Decimal("0")}
        for r in entries:
            field = {"debit": "debits", "credit": "credits"}.get(r["side"])
            mv = r["derived_movement"]
            if field and mv is not None and not r["opening"]:
                own[field] += Decimal(str(mv))
        balances = [r["balance"] for r in entries if r.get("balance") is not None]
        facts.append(PageFacts(
            page=page,
            printed={k: Decimal(str(v).replace(",", ""))/1
                     for k, v in (flags.get(page, {}).get("printed") or {}).items()
                     if k in ("debits", "credits") and v not in (None, "")},
            own=own,
            first_balance=Decimal(str(balances[0])) if balances else None,
            last_balance=Decimal(str(balances[-1])) if balances else None,
            missing_sheets=tuple(per_page.get(page, {}).get("missing_sheets") or ()),
        ))
    return facts


def verify_derivation(rows: list[dict], per_page: dict) -> tuple[list[str], int]:
    """يقارن اشتقاقَنا بأرقام المحكَّم المسجَّلة في تقريره — صفحةً صفحة.

    هذا ما يجعل نشر الصفوف المشتقّة أميناً: نفس دالة المحكَّم، ونفس الترتيب،
    والنتيجة تُقابَل بـ`app` الذي كتبه المحكَّم نفسه (مجموع الصفحة من جانبه).
    أي اختلاف ⇒ التصدير يمتنع ولا يُسلَّم ملف يحمل أرقاماً غير محكَّمة.
    """
    by_page: dict[int, list[dict]] = {}
    for r in rows:
        by_page.setdefault(r["page"], []).append(r)
    problems: list[str] = []
    checked = 0
    for page, entries in sorted(by_page.items()):
        detail = {i.get("field"): i
                  for i in (per_page.get(page, {}).get("footer_detail") or [])}
        if not detail:
            continue
        mine = {"debits": Decimal("0"), "credits": Decimal("0")}
        for r in entries:
            mv, side = r["derived_movement"], r["side"]
            field = {"debit": "debits", "credit": "credits"}.get(side)
            if mv is None or r["opening"] or field is None:
                continue
            mine[field] += Decimal(str(mv))
        for field in ("debits", "credits"):
            item = detail.get(field) or {}
            # نقارن حيث قارن المحكَّم نفسه فقط: على صفحات «غير قابلة للتحقق»
            # (سلسلة مكسورة) يسجّل أرقاماً تراكمية بلا `ok` — وهي ليست مجموع
            # الصفحة، فمقابلتها بها قياس خاطئ لا فحص.
            if item.get("ok") is not True:
                continue
            want = _dec(item.get("app"))
            if want is None:
                continue
            checked += 1
            if mine[field] != want:
                problems.append(
                    f"ص{page}: {field} عندنا {mine[field]} وعند المحكَّم {want}")
    return problems, checked


def build(run: Path, out: Path, gate: Path | None) -> dict:
    rows, report, per_page, flags = load(run)
    if not rows:
        raise SystemExit(f"لا صفوف في {run}/results — هل المسار صحيح؟")

    # بوّابة الأمانة: ما ننشره مشتقّ هنا، فيجب أن يطابق ما أثبته المحكَّم حرفياً.
    problems, checked = verify_derivation(rows, per_page)
    if problems:
        raise SystemExit("اشتقاق التصدير لا يطابق المحكَّم — لا يُسلَّم ملف: "
                         + " | ".join(problems[:5])
                         + (f" (+{len(problems) - 5})" if len(problems) > 5 else ""))

    facts = summary_facts(rows, report, per_page, flags)
    # قيود الفجوة: الأوراق الغائبة تُحسَب بمقدارها المقيس (زيادة التذييل المطبوع)
    # ويُثبتها شاهد مستقل (عبور الرصيد). تُدرج صفوفاً في «الحركات» ليقفل مجموع
    # الملف على ملخص البنك المطبوع — وعلى الهوية الحسابية.
    gaps = build_gap_entries(gap_facts(rows, per_page, flags))
    sum_debits = sum((Decimal(str(r["derived_movement"])) for r in rows
                      if r["derived_movement"] is not None and not r["opening"]
                      and r["side"] == "debit"), Decimal("0"))
    sum_credits = sum((Decimal(str(r["derived_movement"])) for r in rows
                       if r["derived_movement"] is not None and not r["opening"]
                       and r["side"] == "credit"), Decimal("0"))
    gap_debits = sum((g["debits"] or Decimal("0") for g in gaps), Decimal("0"))
    gap_credits = sum((g["credits"] or Decimal("0") for g in gaps), Decimal("0"))
    totals = {"debits": sum_debits + gap_debits, "credits": sum_credits + gap_credits}
    first_open = next((r["balance"] for r in rows if r.get("opening")
                       and r.get("balance") is not None), None)
    opening = Decimal(str(first_open)) if first_open is not None else Decimal("0")
    walk = identity(opening, totals["debits"], totals["credits"])
    closing = _num0(facts["printed_balance"])
    identity_ok = closing is not None and abs(walk - closing) <= Decimal("0.005")
    _fmt = lambda v: f"{v:,.2f}"  # noqa: E731 — صيغة عرض واحدة في هذا القسم
    gap_rows = [
        # ملاحظة: عمود «مصدر التاريخ» أُضيف بعد «حالة التاريخ»، فصفوف الفجوة تُدرج
        # فراغاً ثامناً قبله ليبقى العمودان (مدين/دائن) في موضعهما — وإلا أُزيحت
        # قيمُها فاختلّت المجاميع (وقد رصدته البوابة فوراً).
        [g["before_page"], None, None, None, None, None, None, None,
         (f"قيد فجوة مسح — الأوراق الغائبة {g['missing_sheets']} "
          f"(بين الصفحتين {g['after_page']} و{g['before_page']}): "
          f"مقداراه من زيادة التذييل المطبوع، وعبور الرصيد "
          f"{g['crossing']} يثبت صافيه"
          if g["status"] == "proven" else
          f"قيد فجوة مسح غير مُثبت — {g['note']}"),
         None, None, g["debits"], g["credits"], None, None,
         "قيد فجوة مسح — موثّق لا اتهام صفحة (ورق غائب من المسح)"
         + (" — الشاهدان متفقان" if g["witnesses_agree"] else " — غير مُثبت"),
         "", ""]
        for g in gaps]
    wb = Workbook()

    ws0 = wb.active
    assert ws0 is not None                     # openpyxl always creates one sheet
    ws0.title = "الملخص"
    ws0.append(["البند", "القيمة", "الطريقة / الملاحظة"])
    for cell in ws0[1]:
        cell.fill, cell.font = HEAD_FILL, HEAD_FONT
    section_font = Font(bold=True, color="1F3864", size=11)
    for label, value, note in summary_sheet(facts, rows, report):
        ws0.append([label, value, note])
        if label and not value and not note:
            ws0.cell(row=ws0.max_row, column=1).font = section_font

    # الإقفال الحسابي: الهوية التي تجعل الملف غير قابل للطعن. تُحسب **بعد** قيود
    # الفجوة، ويُقارن ناتجها بالرصيد الختامي المطبوع على الورق.
    for label, value, note in (
        ["", "", ""],
        ["الإقفال الحسابي (الهوية)", "", ""],
        ["رصيد الافتتاح", _fmt(opening), "من الورق: أول رصيد مطبوع في الكشف"],
        ["Σ المدين (بعد قيود الفجوة)", _fmt(totals["debits"]),
         f"حركات مثبتة بالسلسلة {_fmt(sum_debits)}"
         + (f" + قيود فجوة {_fmt(gap_debits)}" if gap_debits else "")],
        ["Σ الدائن (بعد قيود الفجوة)", _fmt(totals["credits"]),
         f"حركات مثبتة بالسلسلة {_fmt(sum_credits)}"
         + (f" + قيود فجوة {_fmt(gap_credits)}" if gap_credits else "")],
        ["الافتتاح + Σ دائن − Σ مدين", _fmt(walk),
         "هذه هي الهوية: يجب أن تساوي الرصيد الختامي المطبوع"],
        ["الرصيد الختامي المطبوع", facts["printed_balance"],
         f"من سطر الإجماليات في الصفحة {facts['last_ok_page']} — رقم الورق"],
        ["حكم الهوية", "مطابق ✓" if identity_ok else "غير مطابق ✗",
         f"بتسامح ≤ 0.005 — الفرق {_fmt(walk - closing) if closing is not None else '?'}"],
        ["قيود الفجوة", f"{len(gaps)} قيداً · صافيها "
         f"{_fmt(gap_credits - gap_debits)}",
         "أوراق غائبة من المسح: مقداراها من زيادة التذييل المطبوع، وعبور الرصيد شاهد ثانٍ"],
    ):
        ws0.append([label, value, note])
        if label and not value and not note:
            ws0.cell(row=ws0.max_row, column=1).font = section_font
    ws0.column_dimensions["A"].width = 40
    ws0.column_dimensions["B"].width = 26
    ws0.column_dimensions["C"].width = 70
    for row in ws0.iter_rows(min_row=2, min_col=3, max_col=3):
        row[0].alignment = Alignment(wrap_text=True, vertical="top")

    ws = wb.create_sheet("الحركات")
    write_sheet(
        ws,
        ["الصفحة (ملف)", "رقم الصفّ", "رقم الصفحة المطبوع", "التاريخ (كما طُبع)",
         "التاريخ (ميلادي)", "حالة التاريخ", "مصدر التاريخ", "السنة", "الوصف",
         "الحركة كما طُبعت", "الحركة المثبتة بالسلسلة", "مدين", "دائن",
         "الرصيد كما طُبع", "الرصيد (رقمي)", "حكم السلسلة على الصفّ",
         "تنبيه", "حالة إجماليات الصفحة"],
        [[r["page"], r["row_no"], r["printed_page"], r["date"], r["date_iso"],
          _DATE_STATUS_AR[r["date_status"]], _DATE_SOURCE_AR[r["date_source"]],
          r["year"], r["desc"],
          r["printed_movement"], r["derived_movement"],
          (debit_credit(r["derived_movement"], r["side"])[0]
           if not r["opening"] else None),
          (debit_credit(r["derived_movement"], r["side"])[1]
           if not r["opening"] else None),
          r["printed_balance"], r["balance"],
          r["row_state"], r["shift"],
          ARABIC_VERDICT.get(r["footer"], r["footer"])]
         for r in rows]
        + gap_rows,
        [12, 9, 16, 18, 14, 26, 8, 46, 16, 18, 12, 12, 16, 14, 34, 40, 30])

    # الأسئلة: حساب حتمي على أدلة التشغيل — بلا نموذج لغوي وبلا كلفة، فالجواب
    # نفسه يُعاد إنتاجه بنفس الأمر غداً. ما يحتاج تفسيراً لا يُخمَّن هنا.
    questions, evidence = question_set(rows, facts, per_page, flags)
    ws_q = wb.create_sheet("الأسئلة")
    write_sheet(ws_q, ["#", "السؤال", "الجواب", "الطريقة (كيف حُسب)", "الأساس / الدليل"],
                questions, [5, 44, 40, 44, 38])
    ws_e = wb.create_sheet("صفوف الأسئلة")
    write_sheet(ws_e, ["# السؤال", "الصفحة", "رقم الصفّ", "التاريخ (ميلادي)", "الوصف",
                       "الحركة", "الرصيد", "سبب الدعم"],
                evidence, [10, 10, 10, 14, 46, 14, 14, 30])

    ws2 = wb.create_sheet("التحقق لكل صفحة")
    write_sheet(
        ws2,
        ["الصفحة (ملف)", "رقم الصفحة المطبوع", "صفوف معتمدة", "إجماليات الصفحة",
         "عدد الشكوك", "المصدر", "زمن القراءة (ملّي ث)", "تناقض داخلي",
         "استُدركت آلياً", "أُعيدت قراءتها", "خطأ قراءة"],
        [[p, e.get("page_no"), e.get("rows"),
          page_verdict(e, max(per_page) if per_page else 0),
          e.get("suspects"), e.get("origin"), e.get("ms_read"), bool(e.get("paradox")),
          (flags.get(p) or {}).get("recovered"), (flags.get(p) or {}).get("reread"),
          (flags.get(p) or {}).get("error")]
         for p, e in sorted(per_page.items())],
        [13, 16, 13, 32, 12, 11, 18, 13, 13, 15, 11])

    # ما لم يُثبت — كل ما ليس "ok"، ومعه الفارغ من بوابة الصفحة (قياس ميكانيكي مجاني)
    #
    # وشهادات الشاهد الموضعي (عند الطلب) تُنسخ هنا بلفظها: «أثبته شاهد الموضع» لا
    # «أثبته الورق المطبوع» — الشاهد يُثبت أن المبلغ في موضعه وأن الإطار على حبر
    # فعلاً، ولا يُثبت إجماليات الصفحة؛ فالورق يبقى الحاكم والموضع شاهدٌ ثالث.
    witness: dict = {}
    try:
        base = Path(run)
        files = sorted(base.glob("pos_witness*.json")) or \
            sorted(base.parent.glob("pos_witness*.json"))
        for wf in files:
            witness.update(json.loads(wf.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        witness = {}

    def _cert(page: int) -> str:
        """شهادة الشاهد بلفظها — أو نصٌّ فارغ حيث لا شهادة (لا يُخترع شاهد)."""
        c = witness.get(str(page))
        if not c:
            return ""
        rows_n = len(c.get("rows") or [])
        if not rows_n:
            return " · شاهد الموضع: صفر صفوف (بلا حركات فعلاً)"
        ok = c.get("on_ink") or 0
        return (f" · شاهد الموضع: {rows_n} صفّاً · {ok}/{rows_n} إطاراً على حبر · "
                f"توافق مع السلسلة {c.get('agree', 0)} · خلاف {c.get('clash', 0)}")

    unproven: list[list] = []
    for p, e in sorted(per_page.items()):
        if e.get("footer") != "ok":
            cert = _cert(p)
            reason = str(ARABIC_VERDICT.get(str(e.get("footer") or ""))
                         or e.get("footer") or "")
            unproven.append([p, e.get("page_no"), e.get("rows"), reason + cert,
                             "من تقرير التشغيل (المحكَّم)"
                             + (" + شاهد الموضع" if cert else "")])
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

    # مشاكل على مستوى **الصفّ** لا الصفحة: تُدرج في هذه الورقة لأنها عقد الأمانة
    # في الملف — كل ما لم يُثبت يُسمّى باسمه، لا يُخفى في عمود جانبي.
    for r in facts["shift_rows"]:
        unproven.append([r["page"], r["printed_page"], None,
                         f"صفّ {r['row_no']}: إزاحة وصف محتملة — «{str(r['desc'])[:38]}» "
                         f"بمبلغ {r['derived_movement']} ({SIDE_AR.get(r['side'], '')})",
                         "كاشف حسابي: وصف لا يكون دائناً جاء دائناً"])
    for r in facts["chain_suspect"]:
        unproven.append([r["page"], r["printed_page"], None,
                         f"صفّ {r['row_no']}: المبلغ المطبوع {r['printed_movement']} "
                         f"لا يطابق فرق الرصيد {r['derived_movement']}",
                         "سلسلة الرصيد (المحكَّم)"])

    # ——— تفكيك البنك لمجاميعه (الصفحة الختامية): شاهد مستقل على المجموعين ———
    # البنك يطبع في الصفحة الختامية تفكيك مجاميعه: مكوّنات الإيداعات ثم إجماليها،
    # ومكوّنات السحوبات ثم إجماليها. فإذا جمعت المكوّنات فطابقت الإجمالي المطبوع،
    # فهذا **برهانٌ من داخل الورق** على Σدائن وΣمدين — لا حسابٌ من عندنا.
    # (كشفه مدقّق خارجي: كان في الملف ونحن نطرحه بوصفه «ليس حركة».)
    parts_c: list = []
    parts_d: list = []
    printed_totals: dict = {}
    bucket = parts_c
    for r in rows:
        if not str(r["row_state"]).startswith("سطر ملخّص"):
            continue
        label = str(r.get("desc") or "").strip()
        amount = _num(r.get("movement"))
        if "اجمالي الايداعات" in label:
            printed_totals["credits"] = amount
            bucket = parts_d
        elif "اجمالي السحوبات" in label:
            printed_totals["debits"] = amount
            bucket = None
        elif amount is not None and bucket is not None:
            bucket.append(amount)
    sum_c = round(sum(parts_c), 2) if parts_c else None
    sum_d = round(sum(parts_d), 2) if parts_d else None
    decomp = []
    if printed_totals.get("credits") is not None:
        decomp.append(["تفكيك البنك — الإيداعات (شاهد مستقل)", f"{sum_c:,.2f}",
                       f"مكوّنات مطبوعة مجموعها = إجمالي الإيداعات المطبوع "
                       f"{_fmt(Decimal(str(printed_totals['credits'])))}"
                       + (" ✓ يقفل" if abs(Decimal(str(sum_c)) -
                                           Decimal(str(printed_totals["credits"])))
                          <= Decimal("0.005") else " ✗ لا يقفل")])
    if printed_totals.get("debits") is not None:
        decomp.append(["تفكيك البنك — السحوبات (شاهد مستقل)", f"{sum_d:,.2f}",
                       f"مكوّنات مطبوعة مجموعها = إجمالي السحوبات المطبوع "
                       f"{_fmt(Decimal(str(printed_totals['debits'])))}"
                       + (" ✓ يقفل" if abs(Decimal(str(sum_d)) -
                                           Decimal(str(printed_totals["debits"])))
                          <= Decimal("0.005") else " ✗ لا يقفل")])
    for label_row in decomp:
        ws0.append(label_row)

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
        ("التواريخ", "الورق والقارئ خلطا ثلاث مجموعات أرقام: عربية-هندية (٠-٩) وفارسية (۰-۹) "
                     "ولاتينية — وبعض القيم تخلط مجموعتين داخلها. عمود «التاريخ (ميلادي)» "
                     "يُنتج صيغة YYYY-MM-DD موحّدة، وعمود «حالة التاريخ» يسمّي كل ما لم يكتمل "
                     "بدل تركه فارغاً."),
        ("ورقة الأسئلة", "الأسئلة في ورقة «الأسئلة» تُجاب بحساب حتمي من أدلة التشغيل نفسها "
                         "(عدّ · فرز · قراءة الإجماليات المطبوعة) — **بلا نموذج لغوي وبلا كلفة**، "
                         "فالجواب نفسه يُعاد إنتاجه بنفس الأمر. وورقة «صفوف الأسئلة» تحمل الصفوف "
                         "الداعمة لكل جواب (أكبر حركة · أصغر حركة · الصفوف بلا تاريخ · صفوف "
                         "الصفحات المحكَّمة) مع سبب الدعم."),
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

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return {
        "rows": len(rows),
        "pages": len(per_page),
        "unproven": len(unproven),
        "questions": len(questions),
        "evidence": len(evidence),
        "dates_ok": facts["dates_ok"],
        "date_status": facts["date_status"],
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
    print(f"  أسئلة: {info['questions']} · صفوف داعمة: {info['evidence']}"
          f" · تواريخ مكتملة: {info['dates_ok']} (الحالة: {info['date_status']})")


if __name__ == "__main__":
    main()
