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
        if spec.get("missing_sheets"):
            cache["missing_sheets"] = spec["missing_sheets"]
        (run / "results" / f"pg-{pg:03d}.json").write_text(
            json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    report = {
        "slice": {"first": 1, "count": 4, "pages_done": 4},
        "totals": {"rows": 5, "clean": 5, "clean_ratio": 1.0},
        "usage": {"cost": 0.0, "calls": 4},
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

def _run_gate(run: Path, xlsx: Path) -> tuple[int, list[str], list[str]]:
    """يشغّل البوابة في العملية نفسها: رمز الخروج + أسماء الناجحة + أسماء الساقطة."""
    verify_close.FAILS.clear()
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["verify_close.py", "--run", str(run), "--xlsx", str(xlsx),
                "--profile", str(PROFILE)]
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
    ("النطاق الزمني داخل", "تاريخ خارج المدى", p_date_out_of_range),
    ("الملخص يذكر «الإقفال الحسابي", "تغيير وسم الإقفال", p_summary_identity_label),
    ("الملخص يذكر «قيود الفجوة»", "تغيير وسم قيود الفجوة", p_summary_gap_label),
    ("الملخص يذكر «حكم الهوية»", "تغيير وسم حكم الهوية", p_summary_verdict_label),
    ("الملخص يعلن حكم الهوية", "قلب قيمة الحكم", p_summary_verdict_value),
    ("ورقة «ما لم يُثبت» قائمة", "حذف سطور الورقة", p_unproven_rows_cleared),
]


def _rules_for(name: str) -> list[tuple[str, str, Callable]]:
    return [r for r in POISONS if name.startswith(r[0])]


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
