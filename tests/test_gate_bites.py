"""حالات الحقن: **كل فحص في بوابة الإقفال يُثبَت بأنه يفشل على عيّنة مسمومة.**

الفكرة (رفعها المدقّق الخارجي في §٦·س٢ من جولته الثالثة، ونُفِّذت هنا):

- إعلانُ العدد يكشف الفحص الميت **بمفتاح خاطئ** (صفر من صفر)، ولا يكشف الميت
  **بشرطٍ مُعطَّل** (`or not required`) — ذاك يقول العدد ويُظهر النقص ويمرّ.
- فالحكم الوحيد على حياة فحص هو **أن يُسمَّم ما يحرسه فيسقط**؛ ولذلك يُشترط
  **اسم الفحص** في قائمة الإخفاقات لا مجرد فشل: التسميم الواحد قد يُسقط أربعة
  فحوص (رأيناه)، فلو اكتفينا بـ«فشل» لمرّ فحصٌ ميت تحت ستار جاره.

البنية: تشغيلة صناعية صغيرة + مصنّف مبنيّ منها بـ`to_xlsx.build` (بلا كلفة وبلا
شبكة)، ثم لكل فحص **سمٌّ واحد** على نسخة. وفحصٌ يُضاف إلى البوابة بلا حالة حقن
⇒ **يسقط `test_every_gate_check_has_a_poison`** — فالإضافة إلى الحُكم تُلزم
إضافة الدليل عليه.

الأرقام مقفلة في هذا الملف: الإقفال `190.00 = 0.00 + 355.00 − 165.00`، والمرساة
الصناعية تحمل مبلغاً مطبوعاً يبتلع فرقُ رصيدها ورقةً غائبة (نفس شكل الكشف الحقيقي).
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
from pathlib import Path
from typing import Callable

import pytest
from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.to_xlsx import build  # noqa: E402
import verify_close  # noqa: E402

PROFILE = ROOT / "profiles" / "al-rajhi.json"
APP_PROFILE = ROOT / "profiles" / "al-rajhi-app.json"
OPENS = "حركة مثبتة"


# ─────────────────────────── التشغيلة الصناعية ───────────────────────────

def _make_run(base: Path) -> Path:
    """أربع صفحات: ثلاث مقروءة بفوتر مطابق، ورقة غائبة واحدة، وصفحة بلا إطار.

    صفحة 3 تلي ورقةً غائبة، فصفّها الأول **مرساة**: مبلغه مطبوع وفرقُ رصيده
    يبتلع حركة الورقة الغائبة (20.00 دائن) — فلا تُقفله السلسلة، وهذا هو الصنف
    الذي وُلد منه عمود «مصدر إثبات الحركة».
    """
    run = base / "run"
    (run / "results").mkdir(parents=True, exist_ok=True)

    def row(mv, bal, desc, date):
        return {"movement": mv, "balance": bal, "desc": desc, "date": date,
                "raw_movement": mv, "raw_balance": bal}

    opening = {"movement": None, "balance": "0.00", "desc": "الرصيد الافتتاحي",
               "date": "20240101", "raw_movement": None, "raw_balance": "0.00"}
    pages = {
        1: {"page_no": 1,
            "rows": [opening,
                     row("300.00", "300.00", "إيداع راتب", "20240101"),
                     row("100.00", "200.00", "سحب نقدي", "20240101")],
            "footer": {"debits": "100.00", "credits": "300.00", "balance": "200.00"}},
        2: {"page_no": 2,
            "rows": [row("50.00", "150.00", "سحب نقدي", "20240102")],
            "footer": {"debits": "150.00", "credits": "300.00", "balance": "150.00"}},
        3: {"page_no": 4,                      # الورقة ٣ غائبة ⇒ المطبوعة تقفز إلى ٤
            "rows": [row("30.00", "200.00", "إيداع نقدي", "20240103"),   # مرساة
                     row("10.00", "190.00", "سحب نقدي", "20240104")],
            "footer": {"debits": "165.00", "credits": "355.00", "balance": "190.00"},
            "missing_sheets": [3]},
        4: {"page_no": 5, "rows": [], "footer": None},
    }
    for pg, spec in pages.items():
        cache = {"pg": pg, "page_no": spec["page_no"], "raw_rows": spec["rows"],
                 "footer": spec["footer"], "usage": {"cost": 0.0, "calls": 1}}
        if pg == 1:
            # **الخليط الأرجح**: نقطةٌ مختومة وثلاثٌ قديمة بلا ختم — وهو حال
            # الكوربوس القائم لحظةَ تُقرأ أول صفحة بعد `reader_stamp()`. وسمّاه
            # المدقّق: الحالة التي يمرّ فيها «ختمٌ واحد + صفحات بلا ختم» بلا فحص.
            cache |= {"model": "test-model", "prompt_version": "v2"}
        if spec.get("missing_sheets"):
            cache["missing_sheets"] = spec["missing_sheets"]
        (run / "results" / f"pg-{pg:03d}.json").write_text(
            json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    report = {
        "slice": {"first": 1, "count": 4, "pages_done": 4},
        "totals": {"rows": 5, "clean": 5, "clean_ratio": 1.0},
        "usage": {"cost": 0.0, "calls": 4},
        # هوية القارئ (FM-1): العيّنة تُولَد بما تُولَد به التشغيلة الحقيقية، وإلا
        # صار الفحص الجديد يسقط على ملفٍّ سليم — والفحص الذي يسقط على السليم
        # يُعطَّل، فيعود البابُ الذي أُغلق.
        "reader_stamp": {"model": "test-model", "prompt_version": "v2"},
        "corpus_provenance": {"reader": {"model": "test-model",
                                         "prompt_version": "v2"},
                              "legacy_unstamped_pages": 3,
                              "stamp_conflict_pages": 0,
                              "declaration": "نقطةٌ واحدة بلا ختم + نسبٌ واحد"},
        "footer": {"ok": 3, "mismatch": 0, "absent": 1, "unchecked": 0, "gap": 0},
        "page_numbers": {"gaps": [[2, 2, 3, 4, [3]]], "duplicates": {}, "backwards": {}},
        "per_page": [
            {"page": 1, "rows": 3, "footer": "ok", "suspects": 0, "page_no": 1,
             "origin": "live", "ms_read": 1000,
             "footer_detail": [{"field": "debits", "footer": "100.00", "ok": True},
                               {"field": "credits", "footer": "300.00", "ok": True},
                               {"field": "balance", "footer": "200.00", "ok": True}]},
            {"page": 2, "rows": 1, "footer": "ok", "suspects": 0, "page_no": 2,
             "origin": "live", "ms_read": 1000},
            {"page": 3, "rows": 2, "footer": "ok", "suspects": 0, "page_no": 4,
             "origin": "live", "ms_read": 1000, "missing_sheets": [3]},
            {"page": 4, "rows": 0, "footer": "absent", "suspects": 0, "page_no": 5,
             "origin": "live", "ms_read": 1000},
        ],
    }
    (run / "slice_report.json").write_text(json.dumps(report, ensure_ascii=False),
                                          encoding="utf-8")
    return run


@pytest.fixture(scope="module")
def gate_fixture(tmp_path_factory) -> tuple[Path, Path, list[str]]:
    """(مجلد التشغيلة · المصنّف السليم · أسماء الفحوص التي مرّت) — يُبنى مرة واحدة."""
    base = tmp_path_factory.mktemp("gate-bites")
    run = _make_run(base)
    clean = base / "export.xlsx"
    build(run, clean, None)
    code, passed, fails = _run_gate(run, clean)
    assert code == 0 and fails == [], f"العيّنة السليمة يجب أن تمرّ: {code} · {fails}"
    return run, clean, passed


# ─────────────────────────── تشغيل البوابة ───────────────────────────

def _run_gate(run: Path, xlsx: Path,
              profile: Path | None = None) -> tuple[int, list[str], list[str]]:
    """يشغّل البوابة في العملية نفسها: رمز الخروج + أسماء الناجحة + أسماء الساقطة."""
    verify_close.FAILS.clear()
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["verify_close.py", "--run", str(run), "--xlsx", str(xlsx),
                "--profile", str(profile or PROFILE)]
    try:
        with contextlib.redirect_stdout(buf):
            code = verify_close.main()
    finally:
        sys.argv = argv
    out = buf.getvalue()
    passed = [ln.split("] ", 1)[1].split(" — ")[0]
              for ln in out.splitlines() if ln.startswith("[PASS]")]
    return code, passed, list(verify_close.FAILS)


# ─────────────────────────── أدوات التسميم ───────────────────────────

def _col(ws, name: str) -> int:
    return [c.value for c in ws[1]].index(name) + 1


def _hit(ws, pred: Callable[[dict], bool]) -> tuple[int, dict]:
    header = [c.value for c in ws[1]]
    for i, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        d = dict(zip(header, values))
        if pred(d):
            return i, d
    raise AssertionError("لا صفّ يطابق الشرط — العيّنة تغيّرت؟")


def _first_movement(ws) -> tuple[int, dict]:
    return _hit(ws, lambda d: str(d.get("حكم السلسلة على الصفّ") or "").startswith(OPENS))


def _summary_row(wb, label: str, *, starts: bool = False) -> int:
    """رقم سطر في «الملخص» — يقبل مصنّفاً أو ورقة (الصياغة تُقرأ بالاسم)."""
    ws = wb["الملخص"] if isinstance(wb, Workbook) else wb
    rows = [i for i, d in _hit_all(ws, lambda d: (
        str(d.get("البند") or "").startswith(label) if starts
        else label in str(d.get("البند") or "")))]
    assert rows, f"لا سطر ملخص باسم {label}"
    return rows[-1] if starts else rows[0]


def _hit_all(ws, pred):
    header = [c.value for c in ws[1]]
    for i, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        d = dict(zip(header, values))
        if pred(d):
            yield i, d


def _gap_row(wb) -> tuple[int, dict]:
    ws = wb["الحركات"]
    return _hit(ws, lambda d: "قيد فجوة" in str(d.get("حكم السلسلة على الصفّ") or ""))


# ─────────────────────────── الأسمام ───────────────────────────
# (اسم الفحص أو بادئته · وصف · ما يُسمَّم) — البادئة تُستعمل حيث يتغيّر الاسم مع
# العيّنة (اسم قيد الفجوة يحمل أرقام الأوراق الغائبة).

def p_sheet_renamed(wb): wb["ما لم يُثبت"].title = "غير مُثبت"


def p_opening(wb): wb["الملخص"].cell(row=_summary_row(wb, "رصيد الافتتاح"), column=2).value = "50.00"


def p_closing_blank(wb):
    ws = wb["الملخص"]
    ws.cell(row=_summary_row(ws, "الرصيد الختامي المطبوع", starts=True), column=2).value = None


def p_credit_shift(wb):
    ws = wb["الحركات"]
    i, _ = _hit(ws, lambda d: d.get("دائن") is not None)
    ws.cell(row=i, column=_col(ws, "دائن")).value = float(ws.cell(row=i, column=_col(ws, "دائن")).value) + 1


def p_debit_plus_1000(wb):
    ws = wb["الحركات"]
    i, _ = _hit(ws, lambda d: d.get("مدين") is not None)
    ws.cell(row=i, column=_col(ws, "مدين")).value = float(ws.cell(row=i, column=_col(ws, "مدين")).value) + 1000


def p_closing_moved(wb):
    ws = wb["الملخص"]
    i = _summary_row(ws, "الرصيد الختامي المطبوع", starts=True)
    ws.cell(row=i, column=2).value = "191.00"


def p_gap_row_deleted(wb):
    ws = wb["الحركات"]
    i, _ = _gap_row(wb)
    ws.delete_rows(i)


def p_gap_debit_blanked(wb):
    ws = wb["الحركات"]
    i, _ = _gap_row(wb)
    ws.cell(row=i, column=_col(ws, "مدين")).value = None


def p_gap_witness_denied(wb):
    ws = wb["الحركات"]
    i, d = _gap_row(wb)
    ws.cell(row=i, column=_col(ws, "حكم السلسلة على الصفّ")).value = (
        str(d["حكم السلسلة على الصفّ"]).replace("الشاهدان متفقان", "غير مُثبت"))


def p_negative_debit(wb):
    ws = wb["الحركات"]
    i, _ = _hit(ws, lambda d: d.get("مدين") is not None)
    ws.cell(row=i, column=_col(ws, "مدين")).value = -5


def p_both_columns(wb):
    ws = wb["الحركات"]
    i, _ = _first_movement(ws)
    ws.cell(row=i, column=_col(ws, "مدين")).value = 1
    ws.cell(row=i, column=_col(ws, "دائن")).value = 1


def p_clash_note(wb):
    ws = wb["الحركات"]
    i, _ = _first_movement(ws)
    ws.cell(row=i, column=_col(ws, "تنبيه")).value = "تناقض وصف↔اتجاه"


def p_source_removed(wb):
    ws = wb["الحركات"]
    i, _ = _first_movement(ws)
    ws.cell(row=i, column=_col(ws, "مصدر إثبات الحركة")).value = None


def p_source_forged_on_anchor(wb):
    ws = wb["الحركات"]
    i, _ = _hit(ws, lambda d: str(d.get("حكم السلسلة على الصفّ") or "").startswith("حركة — مرساة"))
    ws.cell(row=i, column=_col(ws, "مصدر إثبات الحركة")).value = "السلسلة: فرق رصيدين متتاليين"


def p_printed_contradiction(wb):
    ws = wb["الحركات"]
    i, _ = _first_movement(ws)
    ws.cell(row=i, column=_col(ws, "الحركة كما طُبعت")).value = "٩٩٩٩٩.٩٩"


def p_date_removed(wb):
    ws = wb["الحركات"]
    i, _ = _first_movement(ws)
    ws.cell(row=i, column=_col(ws, "التاريخ (ميلادي)")).value = None


def p_identity_fabricated(wb):
    """هويةٌ مُختلقة: قارئٌ لا وجود له ⇒ يجب أن تسقط بمقابلتها بالكاش.

    سمُّ الحضور (`p_reader_identity_blank`) يحرس أن *يُقال شيء*؛ وهذا يحرس أن
    يكون ما قيل **صادقاً** — وهو غرض FM-1 بعينه.
    """
    ws = wb["الملخص"]
    for i, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if str(values[0] or "").startswith("هوية القارئ"):
            ws.cell(row=i, column=2).value = "قارئٌ واحد: acme/reader-v9 · تلقينة V7"
            return
    raise AssertionError("لا سطر «هوية القارئ» في العيّنة")


def p_identity_denies_the_stamp(wb):
    """إعلانُ «غير مختم» على كوربوسٍ فيه ختمٌ مسجَّل ⇒ يكذّب الكاش."""
    ws = wb["الملخص"]
    for i, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if str(values[0] or "").startswith("هوية القارئ"):
            ws.cell(row=i, column=2).value = "غير مختم — 3 صفحة قُرئت قبل تسجيل الهوية"
            return
    raise AssertionError("لا سطر «هوية القارئ» في العيّنة")


def p_unstamped_count_lies(wb):
    """عدّادٌ يكذب: 1 ⇐ 0 ⇒ الكاش يقول غير ذلك."""
    ws = wb["الملخص"]
    for i, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if str(values[0] or "").startswith("صفحات بلا ختم قارئ"):
            ws.cell(row=i, column=2).value = 0
            return
    raise AssertionError("لا سطر «صفحات بلا ختم قارئ» في العيّنة")


def p_scan_limits_row_renamed(wb):
    """**يُفرّغ ورقة الحدود** ⇒ الحدود الموعودة لم تُقل.

    وأولُ محاولةٍ كانت أضعف: غيّرتُ سطراً واحداً فمرّ الفحص، لأن النصّ المطلوب
    كان مذكوراً في سطور أخرى. فالسمّ يجب أن يُزيل **ما يُشترط** لا ما يظنّه
    المسمِّم. (وهذا فرقٌ بين سمٍّ يبدو وسمٍّ يقع.)
    """
    ws = wb["كيف تُقرأ هذه الأوراق"]
    for i in range(2, ws.max_row + 1):
        for col in (1, 2):
            ws.cell(row=i, column=col).value = None


def p_reader_identity_blank(wb):
    """إفراغ هوية القارئ ⇒ رقمٌ يُنشر بلا نسب (FM-1: كان هذا الباب مفتوحاً)."""
    ws = wb["الملخص"]
    for i, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if str(values[0] or "").startswith("هوية القارئ"):
            ws.cell(row=i, column=2).value = None
            return
    raise AssertionError("لا سطر «هوية القارئ» في العيّنة")


def p_unstamped_row_removed(wb):
    """حذف سطر «صفحات بلا ختم قارئ» ⇒ يُسكَت عن الصفحات التي قُرئت بلا ختم."""
    ws = wb["الملخص"]
    for i, values in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if str(values[0] or "").startswith("صفحات بلا ختم قارئ"):
            ws.delete_rows(i, 1)
            return
    raise AssertionError("لا سطر «صفحات بلا ختم قارئ» في العيّنة")


def p_anchor_date_removed(wb):
    """مرساةٌ تفقد تاريخها.

    والمَراسي كانت **خارج مجتمع الفحص** حتى هذه الجولة: البوابة كانت تفحص
    «المُثبَتة بالسلسلة» وحدها، وحكم المرساة يبدأ بـ«حركة — مرساة» ⇒ فحذفُ
    تاريخها كان يمرّ PASS. وهذا السمّ هو ما يُثبت أن الباب أُغلق.
    """
    ws = wb["الحركات"]
    i, _ = _hit(ws, lambda d: str(d.get("حكم السلسلة على الصفّ") or "").startswith("حركة — مرساة"))
    ws.cell(row=i, column=_col(ws, "التاريخ (ميلادي)")).value = None


def p_date_out_of_range(wb):
    ws = wb["الحركات"]
    i, _ = _first_movement(ws)
    ws.cell(row=i, column=_col(ws, "التاريخ (ميلادي)")).value = "1899-01-01"


def p_summary_identity_label(wb):
    ws = wb["الملخص"]
    i = _summary_row(ws, "الإقفال الحسابي (الهوية)")
    ws.cell(row=i, column=1).value = "الإقفال"


def p_summary_gap_label(wb):
    ws = wb["الملخص"]
    # السطر الذي **يبدأ** بالعنوان: «Σ المدين (بعد قيود الفجوة)» يذكره أيضاً،
    # وتسميمه لا يُسقط فحص الإعلان (وهذا بالضبط ما كشفه الحقن).
    i = _summary_row(ws, "قيود الفجوة", starts=True)
    ws.cell(row=i, column=1).value = "قيود الأوراق"


def p_summary_verdict_label(wb):
    ws = wb["الملخص"]
    i = _summary_row(ws, "حكم الهوية")
    ws.cell(row=i, column=1).value = "الحكم"


def p_summary_verdict_value(wb):
    ws = wb["الملخص"]
    ws.cell(row=_summary_row(ws, "حكم الهوية"), column=2).value = "غير مطابق"


def p_unproven_rows_cleared(wb):
    ws = wb["ما لم يُثبت"]
    for i in range(ws.max_row, 1, -1):
        ws.delete_rows(i)


POISONS: list[tuple[str, str, Callable[[Workbook], None]]] = [
    ("الأوراق المطلوبة", "إعادة تسمية ورقة", p_sheet_renamed),
    ("الافتتاح المقروء من الورق", "قيمة الافتتاح في الملخص", p_opening),
    ("رصيد الإقفال مقروء من الملخص", "تفريغ الإقفال في الملخص", p_closing_blank),
    ("الهوية: افتتاح", "+1 على دائن صفّ", p_credit_shift),
    ("Σ المدين == المطبوع", "+1000 على مدين صفّ", p_debit_plus_1000),
    ("Σ الدائن == المطبوع", "+1 على دائن صفّ", p_credit_shift),
    ("رصيد الإقفال == المطبوع", "تحريك قيمة الإقفال في الملخص", p_closing_moved),
    ("قيود الفجوة قائمة كصفوف", "حذف صفّ القيد", p_gap_row_deleted),
    ("قيد ص", "تفريغ مدين القيد", p_gap_debit_blanked),
    ("عدد قيود الفجوة", "حذف صفّ القيد", p_gap_row_deleted),
    ("كل قيد يُعلن اتفاق شاهديه", "نزع وسم اتفاق الشاهدين", p_gap_witness_denied),
    ("لا قيم سالبة", "مدين سالب", p_negative_debit),
    ("لا صفّ يحمل الرقمين معاً", "المبلغ في العمودين", p_both_columns),
    ("لا تناقض وصف↔اتجاه", "وسم تنبيه", p_clash_note),
    ("كل حركة تُعلن مصدر إثباتها", "مسح عمود المصدر", p_source_removed),
    ("إعلان المصدر يوافق حكم السلسلة", "تزوير مصدر مرساة", p_source_forged_on_anchor),
    ("لا تناقض بين «الحركة كما طُبعت»", "تناقض المكتوب بالمثبت", p_printed_contradiction),
    ("التواريخ: كل صفّ حركة له تاريخ", "حذف تاريخ حركة", p_date_removed),
    ("التواريخ: كل صفّ حركة له تاريخ", "حذف تاريخ مرساة (خارج المجتمع سابقاً)",
     p_anchor_date_removed),
    ("النطاق الزمني داخل", "تاريخ خارج المدى", p_date_out_of_range),
    ("الملخص يذكر «الإقفال الحسابي", "تغيير وسم الإقفال", p_summary_identity_label),
    ("الملخص يذكر «قيود الفجوة»", "تغيير وسم قيود الفجوة", p_summary_gap_label),
    ("الملخص يذكر «حكم الهوية»", "تغيير وسم حكم الهوية", p_summary_verdict_label),
    ("ورقة الحدود تُعلن حقيقة هذا التصميم", "تغيير حدٍّ في ورقة الحدود",
     p_scan_limits_row_renamed),
    ("الملخص يعلن هوية القارئ", "إفراغ هوية القارئ (نموذج · تلقينة)",
     p_reader_identity_blank),
    ("هوية القارئ المعلنة توافق الكاش", "اختلاق هوية قارئ", p_identity_fabricated),
    ("هوية القارئ المعلنة توافق الكاش", "إنكار ختمٍ مسجَّل",
     p_identity_denies_the_stamp),
    ("عدد الصفحات بلا ختم يطابق الكاش", "عدّاد بلا ختم يكذب",
     p_unstamped_count_lies),
    ("الملخص يعدّ الصفحات بلا ختم", "حذف سطر الصفحات بلا ختم قارئ",
     p_unstamped_row_removed),
    ("الملخص يعلن حكم الهوية", "قلب قيمة الحكم", p_summary_verdict_value),
    ("ورقة «ما لم يُثبت» قائمة", "حذف سطور الورقة", p_unproven_rows_cleared),
]


def _cache_second_reader(run: Path) -> None:
    """قارئٌ ثانٍ في نقطة فحص واحدة: الكوربوس المختلط الذي يمنعه الفحص الثالث."""
    f = run / "results" / "pg-004.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d |= {"model": "other-model", "prompt_version": "v2"}
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


# (اسم الفحص · وصف · ما يُسمَّم) — أسمامٌ تُوقَع على **الكاش** لا على الورقة:
# فحصُ صدق الإعلان لا يُسمَّم بتزوير الإعلان وحده، بل بتزوير مصدره.
def _cache_corrupt_checkpoint(run: Path) -> None:
    """نقطة فحص تالفة: كانت تختفي من كل تعداد فيُنسب الفرق إلى الإعلان."""
    (run / "results" / "pg-003.json").write_text("{ ليس JSON", encoding="utf-8")


def _cache_corrupt_last(run: Path) -> None:
    """آخر نقطةٍ مطابقة (footers == ok) يُقرأ فوترُها للمجاميع المطبوعة.

    وهي `pg-003` في العيّنة (footers: 1..3 = ok · 4 = absent) — وكانت تالفةً
    تُسقط الأداة بـ`JSONDecodeError` بدل حكمٍ مسمّى.
    """
    (run / "results" / "pg-003.json").write_text("{ ليس JSON", encoding="utf-8")


CACHE_POISONS: list[tuple[str, str, Callable[[Path], None]]] = [
    ("لا نسبتان مسجَّلتان في كوربوسٍ واحد", "قارئٌ ثانٍ في نقطة فحص واحدة",
     _cache_second_reader),
    ("كل نقاط الفحص مقروءة", "نقطة فحص تالفة", _cache_corrupt_checkpoint),
    ("نقطة الفحص الأخيرة المطابقة مقروءة", "نقطة الفحص الأخيرة تالفة",
     _cache_corrupt_last),
]


# ─────────────────── تشغيلةٌ تذييلها «ملخّص فترة» (التصميم الثاني) ───────────────────
def _make_period_run(base: Path) -> Path:
    """تشغيلةٌ بدور تذييلٍ ثانٍ: لا إجمالياتٍ لكل صفحة، بل ملخّص فترة واحد.

    سببُ وجودها: الفحوص التي لا تُطلَق إلا على تصميمٍ آخر **لا يسمّمها المصنّف
    الأول** ⇒ تبقى بلا سمّ. فالتصميم الثاني يُبنى هنا كما يُبنى الأول.
    """
    run = base / "period"
    (run / "results").mkdir(parents=True, exist_ok=True)
    pages = {
        1: [{"movement": None, "balance": "0.00", "desc": "الرصيد الافتتاحي",
             "date": None, "raw_movement": None, "raw_balance": "0.00"},
            {"movement": "100.00", "balance": "100.00", "desc": "إيداع نقدي",
             "date": "20250101", "raw_movement": "100.00", "raw_balance": "100.00"}],
        2: [{"movement": "40.00", "balance": "60.00", "desc": "سحب نقدي",
             "date": "20250102", "raw_movement": "40.00", "raw_balance": "60.00"}],
    }
    for pg, rows in pages.items():
        (run / "results" / f"pg-{pg:03d}.json").write_text(json.dumps(
            {"pg": pg, "page_no": pg, "raw_rows": rows, "footer": None,
             "model": "deterministic", "prompt_version": "text-v1",
             "usage": {"cost": 0.0, "calls": 0}}, ensure_ascii=False), encoding="utf-8")
    report = {
        "slice": {"first": 1, "count": 2, "pages_done": 2},
        "totals": {"rows": 3, "clean": 3, "clean_ratio": 1.0},
        "footer_role": "period_summary",
        "period_summary": {"opening": "0.00", "closing": "60.00",
                           "printed_debits": "40.00", "printed_credits": "100.00",
                           "n_deposits": "1", "n_withdrawals": "1"},
        "footer": {"ok": 0, "mismatch": 0, "absent": 2, "unchecked": 0, "gap": 0},
        "page_numbers": {"gaps": [], "duplicates": {}, "backwards": {}},
        "reader_stamp": {"model": "deterministic", "prompt_version": "text-v1"},
        "corpus_provenance": {"reader": {"model": "deterministic",
                                         "prompt_version": "text-v1"},
                              "legacy_unstamped_pages": 0,
                              "stamp_conflict_pages": 0,
                              "declaration": "كوربوسٌ بنسبٍ واحد (قارئٌ حتميّ)"},
        "usage": {"cost": 0.0, "calls": 0},
        "per_page": [{"page": pg, "rows": len(rows), "footer": "absent",
                      "suspects": 0, "page_no": pg, "origin": "text", "ms_read": 0}
                     for pg, rows in pages.items()],
    }
    (run / "slice_report.json").write_text(json.dumps(report, ensure_ascii=False),
                                           encoding="utf-8")
    return run


@pytest.fixture(scope="module")
def period_fixture(tmp_path_factory) -> tuple[Path, Path, list[str]]:
    base = tmp_path_factory.mktemp("gate-bites-period")
    run = _make_period_run(base)
    clean = base / "period.xlsx"
    build(run, clean, None)
    code, passed, fails = _run_gate(run, clean, APP_PROFILE)
    assert code == 0 and fails == [], f"عيّنة ملخّص الفترة يجب أن تمرّ: {fails}"
    return run, clean, passed


def _period_report_edit(run: Path, **fields) -> None:
    f = run / "slice_report.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["period_summary"] |= fields
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def _period_credits_lie(run: Path) -> None:
    _period_report_edit(run, printed_credits="999.00")


def _period_closing_lie(run: Path) -> None:
    _period_report_edit(run, closing="61.00")


def _period_count_lie(run: Path) -> None:
    _period_report_edit(run, n_withdrawals="7")


def _period_disclosure_blank(wb) -> None:
    """يُفرّغ ورقة الحدود في التصدير الرقمي ⇒ قارئُه لا يعرف ما لا يُشهد به."""
    ws = wb["كيف تُقرأ هذه الأوراق"]
    for i in range(2, ws.max_row + 1):
        for col in (1, 2):
            ws.cell(row=i, column=col).value = None


def _period_declares_gaps(run: Path) -> None:
    """يُعلن أوراقاً غائبة بلا قيدٍ يقابلها ⇒ يجب أن يسقط فحص القيود."""
    f = run / "slice_report.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["page_numbers"]["gaps"] = [[1, 1, 2, 3, [2]]]
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


# أسمامُ التصميم الثاني: تُوقَع على تشغيلة «ملخّص الفترة» لا على الأولى — فلكل
# تصميمٍ عيّنته، وسمُّ تصميمٍ لا يُجرَّب على آخر.
# أسمامُ **ورقةٍ** في التصميم الثاني: بعض الفحوص يقع على المصنّف لا على الكاش
PERIOD_WORKBOOK_POISONS: list[tuple[str, str, Callable]] = [
    ("ورقة الحدود تُعلن حقيقة هذا التصميم", "إفراغ حدّ الملف الرقمي",
     _period_disclosure_blank),
]


PERIOD_POISONS: list[tuple[str, str, Callable[[Path], None]]] = [
    ("Σ الدائن == ملخّص الفترة", "إجمالي الدائن في ملخّص الفترة يكذب",
     _period_credits_lie),
    ("رصيد الإقفال == ملخّص الفترة", "إقفال ملخّص الفترة يكذب", _period_closing_lie),
    ("عدد الصفوف == عدد الحركات المطبوع", "عدد الحركات المطبوع يكذب",
     _period_count_lie),
    ("قيود الفجوة قائمة كصفوف", "أوراقٌ غائبة مُعلنة بلا قيد", _period_declares_gaps),
]


def _rules_for(name: str) -> list[tuple[str, str, Callable]]:
    return ([r for r in POISONS if name.startswith(r[0])]
            + [r for r in CACHE_POISONS if name.startswith(r[0])]
            + [r for r in PERIOD_POISONS if name.startswith(r[0])]
            + [r for r in PERIOD_WORKBOOK_POISONS if name.startswith(r[0])])


# ─────────────────────────── الفحوص ───────────────────────────

def test_the_synthetic_fixture_passes_the_gate(gate_fixture):
    """العيّنة السليمة تمرّ — وإلا كان كل سمّ لاحقاً بلا معنى."""
    run, clean, passed = gate_fixture
    code, _passed, fails = _run_gate(run, clean)
    assert code == 0 and fails == [], (code, fails)
    assert len(passed) >= 20, f"البوابة على العيّنة طبعت {len(passed)} فحصاً فقط"


def test_every_gate_check_has_a_poison(gate_fixture):
    """فحصٌ في البوابة بلا حالة حقن = فحصٌ لا يُعرف أحيٌّ هو أم ميت ⇒ يسقط هنا."""
    _run, _clean, passed = gate_fixture
    uncovered = [name for name in passed if not _rules_for(name)]
    assert not uncovered, (
        "فحوص بلا حالة حقن (أضف سمّاً في POISONS): " + " · ".join(uncovered))


def test_no_check_name_carries_an_unresolved_placeholder(gate_fixture):
    """الأسمام تحرس **حياة** الفحص، ولا تحرس **صحّة اسمه** — فالاسم يُحرَس هنا.

    دفعَ إليها مدقّق خارجي: أفرغ «الصفحة (ملف)» لصفّ القيد، فطبع البديلُ الخاطئ
    (`g.get("رقم الصفحة")` — والعمود اسمه «رقم الصفحة المطبوع») اسماً هو
    `قيد ص?`. ولم يمسكه سمّ، لأن السمّ يطابق بالبادئة. فالحدّ البنيوي يبقى (لا
    اختبار يقرأ النية)، لكن **موضعَ علامةٍ لم تُستبدل** يُحرَس كصنف.
    """
    _run, _clean, passed = gate_fixture
    bad = [n for n in passed if "?" in n or "None" in n or "{" in n or "}" in n]
    assert not bad, f"أسماء فحوص فيها علامة لم تُستبدل: {bad}"


def test_the_gap_check_names_the_printed_sheets_not_the_file_position(tmp_path, gate_fixture):
    """القيد يُسمّى بورقه: «قيد ص3» — لا بموقع الملف ولا بعلامةٍ بديلة."""
    run, clean, passed = gate_fixture
    gap = next(n for n in passed if n.startswith("قيد ص"))
    assert gap == "قيد ص3 له مقدارا مدين ودائن", gap
    # ١) موقع الملف فارغ ⇒ الاسم يبقى على الورق.
    poisoned = tmp_path / "no-position.xlsx"
    shutil.copy(clean, poisoned)
    wb = load_workbook(poisoned)
    ws = wb["الحركات"]
    i, _ = _gap_row(wb)
    ws.cell(row=i, column=_col(ws, "الصفحة (ملف)")).value = None
    wb.save(poisoned)
    _code, _passed, fails = _run_gate(run, poisoned)
    assert all("?" not in f for f in fails), fails
    # ٢) **والعمودان فارغان معاً** (الحدّ الذي أعلنه المدقّق): لا علامة بديلة —
    #    يُسمّى القيد بترتيبه فيُقرأ الاسم ولا يمرّ `?` صامتاً.
    both = tmp_path / "no-both.xlsx"
    shutil.copy(clean, both)
    wb = load_workbook(both)
    ws = wb["الحركات"]
    j, _ = _gap_row(wb)
    ws.cell(row=j, column=_col(ws, "الصفحة (ملف)")).value = None
    ws.cell(row=j, column=_col(ws, "رقم الصفحة المطبوع")).value = None
    wb.save(both)
    _code, passed2, fails = _run_gate(run, both)
    assert all("?" not in f for f in fails + passed2), fails + passed2
    assert "قيد فجوة #1 له مقدارا مدين ودائن" in passed2, passed2


def _cache_poison_case(make_run, rule, tmp_path) -> None:
    name, desc, mutate = rule
    base = tmp_path / "cache-bite"
    run = make_run(base)
    clean = base / "export.xlsx"
    build(run, clean, None)
    mutate(run)
    code, _passed, fails = _run_gate(run, clean)
    assert code != 0, f"السمّ «{desc}» لم يُسقط البوابة"
    assert any(f.startswith(name) for f in fails), \
        f"سقط غير المسمّى: {fails} (المطلوب: {name})"


@pytest.mark.parametrize("rule", PERIOD_WORKBOOK_POISONS,
                         ids=[r[0] for r in PERIOD_WORKBOOK_POISONS])
def test_a_second_layout_sheet_poison_fails_the_gate(tmp_path, rule):
    """فحصٌ يقع على ورقة التصدير في التصميم الثاني: يُسمَّم على مصنّفه."""
    name, desc, mutate = rule
    base = tmp_path / "sheet-bite"
    run = _make_period_run(base)
    clean = base / "period.xlsx"
    build(run, clean, None)
    poisoned = base / "poisoned.xlsx"
    shutil.copy(clean, poisoned)
    wb = load_workbook(poisoned)
    mutate(wb)
    wb.save(poisoned)
    code, _passed, fails = _run_gate(run, poisoned, APP_PROFILE)
    assert code != 0, f"السمّ «{desc}» لم يُسقط البوابة"
    assert any(f.startswith(name) for f in fails), f"سقط غير المسمّى: {fails}"


@pytest.mark.parametrize("rule", PERIOD_POISONS,
                         ids=[r[0] for r in PERIOD_POISONS])
def test_a_second_layout_poison_fails_the_gate(tmp_path, rule):
    """فحوصٌ لا تُطلَق إلا على تصميمٍ آخر: تُسمَّم على عيّنة ذلك التصميم."""
    _cache_poison_case(_make_period_run, rule, tmp_path)


@pytest.mark.parametrize("rule", CACHE_POISONS, ids=[r[0] for r in CACHE_POISONS])
def test_a_cache_poison_fails_the_gate(tmp_path, rule):
    """سمٌّ على الكاش ⇒ البوابة تسقط بالاسم.

    وسببُ وجود هذا الصنف: بعض الفحوص لا يُسمَّم محتواها بورقة — فحصُ «كوربوسٌ
    واحد بنسبٍ واحد» لا معنى لتسميمه في الملخص، لأن **مصدر الحكم هو الكاش**.
    فتسميمه أن يُصنَع الكوربوس المختلط نفسه — وهو ما طلبه المدقّق: لا تنتظروا
    قارئاً ثانياً حقيقياً، اصنعوه في العيّنة.
    """
    name, desc, mutate = rule
    base = tmp_path / "cache-bite"
    run = _make_run(base)
    clean = base / "export.xlsx"
    build(run, clean, None)
    mutate(run)
    code, _passed, fails = _run_gate(run, clean)
    assert code != 0, f"السمّ «{desc}» لم يُسقط البوابة"
    assert any(f.startswith(name) for f in fails), \
        f"سقط غير المسمّى: {fails} (المطلوب: {name})"


@pytest.mark.parametrize("rule", POISONS, ids=[r[0] for r in POISONS])
def test_a_poison_trips_its_named_check(rule, gate_fixture, tmp_path):
    """الشرط على **اسم الفحص** لا على الفشل وحده: التسميم قد يُسقط جارَه أيضاً."""
    label, _desc, poison = rule
    run, clean, passed = gate_fixture
    target = next((n for n in passed if n.startswith(label)), None)
    assert target, f"لا فحص في البوابة يطابق «{label}»"
    poisoned = tmp_path / "poisoned.xlsx"
    shutil.copy(clean, poisoned)
    wb = load_workbook(poisoned)
    poison(wb)
    wb.save(poisoned)
    code, _passed, fails = _run_gate(run, poisoned)
    assert code != 0, f"البوابة مرّت على سمّ «{label}» (exit=0)"
    assert target in fails, f"السمّ أسقط {fails} ولم يُسقط «{target}»"

