"""العددُ والمعدودُ بالعربيّة — موضعٌ واحد (`statement_qa.render.count_ar`).

**البروفةُ الحيّة (2026-10-31) — مقيس:** ملاحظتان كتبتا «1 سؤالًا وجوابًا» و«1 ملفًّا»، لأنّ كلَّ موضعٍ كتب صيغةَ
الكثرة وحدَها، والصفوفُ وحدَها كان لها مُصرِّف (`app._n_rows_ar`). فالمُصرِّفُ صار واحدًا، والمواضعُ الثلاثة تقرؤه.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa.render import count_ar  # noqa: E402


def test_the_four_forms_of_the_counted_noun() -> None:
    forms = ("ملفٌّ واحد", "ملفّان", "{n} ملفّات", "{n} ملفًّا")
    assert [count_ar(n, *forms) for n in (1, 2, 3, 10, 11, 99)] == [
        "ملفٌّ واحد", "ملفّان", "3 ملفّات", "10 ملفّات", "11 ملفًّا", "99 ملفًّا"]
    assert count_ar(0, *forms) == "0 ملفًّا"


def test_the_two_notes_the_rehearsal_caught_read_the_one_helper() -> None:
    src = (ROOT / "src" / "statement_qa" / "ledger_ui.py").read_text(encoding="utf-8")
    assert "ملفًّا: " not in src and "count_ar(" in src, "ملاحظةُ الحذف تكتب صيغتَها بنفسها"
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "سؤالًا وجوابًا ·" not in app and app.count("count_ar(") >= 2, "ملاحظةُ المحادثة تكتب صيغتَها بنفسها"
