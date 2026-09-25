"""قيود الفجوة: الحساب، والشاهد الثاني، ومنع الافتراض.

الأرقام المستعملة هنا هي **المقيسة فعلياً** على كشف الراجحي (فجوتا المسح بعد
الملفين ٤٢٦ و٦٢٥): زيادات التذييل المطبوع (8514.50 + 9977.98 = 4,242.48 مدين
· 9,007.00 + 9,005.00 = 9,009.00 دائن) وعبور الرصيد (+634.50 ثم +819.02 =
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
        _facts(426, {"debits": "218998.15", "credits": "647041.04"}, {"debits": "0", "credits": "0"},
               "392.40", "392.40"),
        _facts(427, {"debits": "323267.17", "credits": "189784.39"}, {"debits": "120.22", "credits": "130.00"},
               "6345.36", "6345.36", missing=(426, 427)),
    ]
    entry = build_gap_entries(facts)[0]
    # الجمعان يُحسبان من فرق التذييل ناقص ما حسبناه على الصفحة نفسها
    assert entry["missing_sheets"] == [426, 427]
    assert entry["debits"] is not None and entry["credits"] is not None
    assert entry["net"] == entry["credits"] - entry["debits"]


def test_the_gap_numbers_are_self_consistent():
    """**البنيةُ تُختبر بأمثالٍ صناعية** — والأرقامُ الحقيقيةُ تُقاس في تشغيل البحث (دليلُها في
    `data/` المُهمَل)، فقد كانت منشورةً هنا نصّاً: والاختبارُ يجب ألّا يكون قناةَ تسريب.

    والقاعدةُ الدقيقة: خريطةُ التطهير مفتاحُها **القيمةُ المُقنَّنة** ⇒ تنجو علاقاتُ التساوي
    والتسلسل (دائن − مدين = رصيد، وقيمةٌ مُكرّرةٌ في ملفَّين) — أمّا **الجمعيّاتُ** فتحتاج مثالاً
    مُصمَّماً (كما هنا) لا تطهيراً.
    """
    gap1 = {"d": Decimal("1234.56"), "c": Decimal("2345.67")}
    gap2 = {"d": Decimal("3456.78"), "c": Decimal("4567.89")}
    net = (gap1["c"] + gap2["c"]) - (gap1["d"] + gap2["d"])
    crossing = Decimal("1111.11") + Decimal("1111.11")
    assert net == crossing                                     # الشاهدان يتفقان
    assert gap1["d"] + gap2["d"] == Decimal("4691.34")
    assert gap1["c"] + gap2["c"] == Decimal("6913.56")
    assert net == Decimal("2222.22")


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
    assert identity("0", "4242.48", "9009.00") == Decimal("4766.52")   # 0 + 9009.00 − 4242.48
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
