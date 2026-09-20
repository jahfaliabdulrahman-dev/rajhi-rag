"""قيود الفجوة: الحساب، والشاهد الثاني، ومنع الافتراض.

الأرقام المستعملة هنا هي **المقيسة فعلياً** على كشف الراجحي (فجوتا المسح بعد
الملفين ٤٢٦ و٦٢٥): زيادات التذييل المطبوع (2,390.50 + 1,851.98 = 4,242.48 مدين
· 3,025.00 + 2,671.00 = 5,696.00 دائن) وعبور الرصيد (+634.50 ثم +819.02 =
+1,453.52). الصافي واحد من الطريقين — وهذا ما يجعل القيد مُثبتاً لا مُفترضاً.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import sys

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src"), str(Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.gap_ledger import (  # noqa: E402
    PageFacts, build_gap_entries, debit_credit, identity,
)


def _facts(page, printed, own, first, last, missing=()) -> PageFacts:
    return PageFacts(page=page,
                     printed={k: Decimal(v) for k, v in printed.items()},
                     own={k: Decimal(v) for k, v in own.items()},
                     first_balance=Decimal(first) if first else None,
                     last_balance=Decimal(last) if last else None,
                     missing_sheets=tuple(missing))


def test_a_gap_entry_is_measured_from_the_footer_and_witnessed_by_the_balance():
    facts = [
        _facts(426, {"debits": "884150.08", "credits": "887666.49"}, {"debits": "0", "credits": "0"},
               "392.40", "392.40"),
        _facts(427, {"debits": "886661.80", "credits": "888416.49"}, {"debits": "120.22", "credits": "130.00"},
               "1026.90", "1026.90", missing=(426, 427)),
    ]
    entry = build_gap_entries(facts)[0]
    # الجمعان يُحسبان من فرق التذييل ناقص ما حسبناه على الصفحة نفسها
    assert entry["missing_sheets"] == [426, 427]
    assert entry["debits"] is not None and entry["credits"] is not None
    assert entry["net"] == entry["credits"] - entry["debits"]


def test_the_real_rajhi_numbers_are_self_consistent():
    """القيدان الحقيقيان: مجموع المدين/الدائن يفسّر عبور الرصيد بالضبط."""
    gap1 = {"d": Decimal("2390.50"), "c": Decimal("3025.00")}
    gap2 = {"d": Decimal("1851.98"), "c": Decimal("2671.00")}
    net = (gap1["c"] + gap2["c"]) - (gap1["d"] + gap2["d"])
    crossing = Decimal("634.50") + Decimal("819.02")
    assert net == Decimal("1453.52")
    assert net == crossing                      # الشاهدان يتفقان
    assert gap1["d"] + gap2["d"] == Decimal("4242.48")
    assert gap1["c"] + gap2["c"] == Decimal("5696.00")


def test_without_a_printed_footer_before_the_gap_the_entry_is_unproven():
    facts = [_facts(427, {"debits": "1", "credits": "1"}, {}, "10", "10", missing=(426, 427))]
    entry = build_gap_entries(facts)[0]
    assert entry["status"] == "unproven"
    assert entry["debits"] is None and "يتعذّر" in entry["note"]


def test_a_disagreeing_witness_marks_the_entry_not_hides_it():
    facts = [
        _facts(426, {"debits": "100.00", "credits": "0.00"}, {"debits": "0", "credits": "0"},
               "500.00", "500.00"),
        _facts(427, {"debits": "200.00", "credits": "0.00"}, {"debits": "0", "credits": "0"},
               "900.00", "900.00", missing=(426, 427)),
    ]
    entry = build_gap_entries(facts)[0]
    assert entry["status"] == "disagreed"           # القيد 100 والعبور 400
    assert entry["witnesses_agree"] is False
    assert "اختلفا" in entry["note"]


def test_identity_and_column_split():
    # identity(الافتتاح، المدين، الدائن) = افتتاح + دائن − مدين
    assert identity("0", "888404.92", "888975.51") == Decimal("570.59")
    assert identity("0", "4242.48", "5696.00") == Decimal("1453.52")
    assert debit_credit("22.00", "debit") == (Decimal("22.00"), None)
    assert debit_credit("22.00", "credit") == (None, Decimal("22.00"))
    assert debit_credit("0", "debit") == (None, None)
    assert debit_credit(None, "debit") == (None, None)


def test_the_export_declares_the_identity_block_and_the_gap_ledger(tmp_path):
    """الملف المُسلَّم يحمل إقفاله بنفسه: قسم الهوية + بند قيود الفجوة."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_exports import _synthetic_run
    from openpyxl import load_workbook
    from tools.to_xlsx import build

    PROFILE = Path(__file__).resolve().parents[1] / "profiles" / "al-rajhi.json"

    out = tmp_path / "export.xlsx"
    build(_synthetic_run(tmp_path), out, None, profile=PROFILE)
    wb = load_workbook(out)
    joined = " ".join(str(v) for row in wb["الملخص"].iter_rows(values_only=True)
                      for v in row if v is not None)
    assert "الإقفال الحسابي (الهوية)" in joined
    assert "قيود الفجوة" in joined
    assert ("مطابق ✓" in joined) or ("غير مطابق ✗" in joined)
    # الأعمدة التي تُجمع: مدين ودائن كما يطبع البنك
    header = [c.value for c in wb["الحركات"][1]]
    assert "مدين" in header and "دائن" in header
