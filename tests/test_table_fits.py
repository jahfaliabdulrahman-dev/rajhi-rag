"""الجدولان في عرض صندوقيهما — حصصُ الأعمدة من موضعٍ واحد (`statement_qa.render.column_widths`).

**مقيسٌ في صور حزمة التسليم (2026-11-01):** جدولُ الكشف ١٥٧٣ في صندوقٍ ١٤٧٢ حتى على أقصى عرضٍ للصفحة، لأنّ Gradio تتّسع الأعمدةَ
بقدر محتواها بلا عرضٍ مُعلَن ⇒ الرصيدُ مقطوعٌ و«الحالة»/«التحقق» خلف تمريرٍ جانبيّ. بعد الحصص والالتفاف: ١٣٧٤ في ١٣٧٦ على عرض ١٤٤٠.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa.render import ROW_COLUMNS, column_widths, row_record  # noqa: E402


def test_the_declared_columns_are_the_rows_columns() -> None:
    rec = row_record(1, {"page": 1, "desc": "x", "type": "t", "movement": None, "side": "", "balance": None,
                         "ok": True, "kind": "txn", "date": None}, {})
    assert tuple(rec) == ROW_COLUMNS, tuple(rec)


def test_every_table_adds_up_to_its_box() -> None:
    for cols in (ROW_COLUMNS, ("#", "استشهد به الجواب", *ROW_COLUMNS[1:]), ("#", "عمودٌ جديد")):
        widths = column_widths(cols)
        assert len(widths) == len(cols), (cols, widths)
        assert abs(sum(float(w.rstrip("%")) for w in widths) - 100) < 0.05, widths
    # البيانُ أوسعُ الأعمدة — هو الذي يلتفّ
    w = dict(zip(ROW_COLUMNS, column_widths(ROW_COLUMNS)))
    assert max(w, key=lambda c: float(w[c].rstrip("%"))) == "الوصف", w


def test_both_tables_wrap_and_take_their_widths_from_the_one_place() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert app.count("wrap=True") >= 2, "جدولٌ بلا التفاف"
    assert "column_widths=render_column_widths(ROW_COLUMNS)" in app
    assert "column_widths=render_column_widths(list(df.columns))" in app
