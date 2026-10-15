"""**R117-7 — تقديرُ ما قبل الجولة يُقرأ من أحدث جولةٍ لا من آخر اسم، ويُسمّي حقله.**

**العطبُ المقيس (مراجعة ١١٧ · ملاحظةٌ ٩):** `last_billed_run` كان يمرّ على
`sorted(glob("answers-r*.json"))` ويحتفظ بـ**آخر ملفٍّ في القائمة الأبجديّة**، وقِيس أنّ
`answers-r108.json` يأتي **بعد** `answers-r108-03.json` ترتيبًا **وإن كان أقدمَ منه بالساعات**
⇒ فالتقديرُ يُبنى على جولةٍ ليست السابقة. و`st_mtime` كان **يُحفظ ولا يُقارَن** (يُكتَب في كلّ
تكرار ثمّ تُقرأ العناصر `[1:]` وحدَها). **والحقلُ كان يُفترض:** `cost_billed_usd` **لا تحمله أيُّ
جولةٍ محفوظة اليوم** (قِيس: ٠ من ٤٣٦ سجلًّا في خمسة ملفّات) ⇒ فلا تقديرَ يُطبع أصلًا.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools import eval_questions as ev  # noqa: E402
from tools import pack_io  # noqa: E402


def _write(root: pathlib.Path, name: str, *, mtime: float, rows: list[dict]) -> pathlib.Path:
    d = root / "data" / "eval_pack"
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(json.dumps({"results": rows}), encoding="utf-8")
    os.utime(f, (mtime, mtime))
    return f


def _rows_spent(n: int, spent_after: float) -> list[dict]:
    """سجلاتٌ بشكل جولةٍ حقيقيّة: `spent_after_usd` تراكميٌّ + ردودٌ مشهودة."""
    out = []
    for i in range(n):
        out.append({"id": f"q{i}", "spent_after_usd": round(spent_after * (i + 1) / n, 6),
                    "replies_observed": 2, "cost_billed_usd": None})
    return out


@pytest.fixture
def pack(tmp_path, monkeypatch):
    monkeypatch.setenv("RAJHI_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(ev, "pack_io", ev.pack_io)          # الجذرُ يُقرأ من البيئة عند كلّ نداء
    return tmp_path


def test_the_newest_run_wins_even_when_its_name_sorts_first(pack):
    """**الاختيارُ بأحدث تعديل:** أحدثُ ملفٍّ يحمل الاسمَ الأقدم ترتيبًا (‏`answers-r108.json`)."""
    _write(pack, "answers-r108-03.json", mtime=1_000_000, rows=_rows_spent(50, 0.067499))
    _write(pack, "answers-r108.json", mtime=2_000_000, rows=_rows_spent(10, 0.010000))
    got = ev.last_billed_run()
    assert got is not None and got["file"] == "answers-r108.json", got
    assert got["questions"] == 10


def test_the_older_mtime_does_not_win_by_name_order(pack):
    """**النقيض:** الاسمُ المتأخّر ترتيبًا (‏`-03`) أقدمُ تعديلًا ⇒ لا يُختار."""
    _write(pack, "answers-r108-03.json", mtime=1_000_000, rows=_rows_spent(50, 0.067499))
    _write(pack, "answers-r108.json", mtime=2_000_000, rows=_rows_spent(10, 0.010000))
    assert ev.last_billed_run()["file"] != "answers-r108-03.json"


def test_the_field_read_is_named_and_falls_back_declared(pack):
    """**الحقلُ يُسمّى:** `cost_billed_usd` إن وُجد، وإلّا **أقصى `spent_after_usd`** (تراكميٌّ
    مُحاسَب) — والاسمُ يُعاد مع الرقم ليُقرأ مصدرُه في سطر التقدير."""
    rows = [{"id": "q1", "cost_billed_usd": 0.004, "replies_observed": 2},
            {"id": "q2", "cost_billed_usd": 0.006, "replies_observed": 3}]
    _write(pack, "answers-r108.json", mtime=1_000_000, rows=rows)
    got = ev.last_billed_run()
    assert got["field"] == "cost_billed_usd" and got["spent"] == pytest.approx(0.010), got

    _write(pack, "answers-r108.json", mtime=1_000_000,
           rows=[{"id": "q1", "spent_after_usd": 0.02, "replies_observed": 2},
                 {"id": "q2", "spent_after_usd": 0.067499, "replies_observed": 3}])
    got2 = ev.last_billed_run()
    assert got2["field"] == "spent_after_usd", got2
    assert got2["spent"] == pytest.approx(0.067499), "المجموعُ التراكميُّ لا يُقصّ إلى آخر سؤال"
    assert got2["replies"] == 5


def test_the_estimate_scales_and_vanishes_without_a_file(pack):
    _write(pack, "answers-r108.json", mtime=1_000_000, rows=_rows_spent(50, 0.067499))
    est = ev.simple_estimate(50)
    assert est == pytest.approx(0.067499, rel=1e-6), est
    assert ev.simple_estimate(25) == pytest.approx(0.067499 / 2, rel=1e-6)
    for f in (pack / "data" / "eval_pack").glob("*.json"):
        f.unlink()
    assert ev.last_billed_run() is None and ev.simple_estimate(50) is None, \
        "تقديرٌ بلا ملفّ ⇒ لا سطرَ يُطبع (لا رقمَ يُخترع)"


def test_the_real_run_on_this_machine_yields_an_estimate():
    """**وعلى بيانات المالك:** أحدثُ جولةٍ حقيقيّة تُنتج تقديرًا **مُسمّى الحقل** — وهذا هو العطبُ
    الذي كان يقول «لا تقدير» قبل الإصلاح. تُتخطّى في بيئةٍ بلا بيانات (الـCI) بحدٍّ مُعلَن."""
    # **والتخطّي بجذر الدالّة نفسِه (R126-1 · مراجعة ١٢٦):** كان الشرطُ ينظر في
    # `Path.home()/Projects/rajhi-rag` — **مسارُ نسخةٍ واحدةٍ بعينها** — والدالّةُ تقرأ
    # `pack_io.data_root()` (شجرةُ العمل → الشجرةُ الأمّ بحكم `git-common-dir`) ⇒ ففي نسخةٍ أخرى
    # على الجهاز نفسه **يوجد** المسارُ المخمَّن ولا توجد الجولاتُ في الجذر المقروء
    # ⇒ **يسقط بدل أن يتخطّى** (قِيس: `1 failed` على الرأس وعلى `main`). والشرطُ الآن على
    # الجذر الذي تقرؤه الدالّة ⇒ فيتخطّى حيث لا جولات، ويسقط حيث الجولاتُ ناقصة (وهو ما يحرسه).
    if not (pack_io.data_root() / "data" / "eval_pack").is_dir():
        pytest.skip("لا بياناتُ جولاتٍ في جذر الأدلّة المقروء (لا تصل الـCI) — تُقاس حيث تكون الجولات")
    got = ev.last_billed_run()
    assert got is not None, "لا جولةَ محفوظةً تُقرأ ⇒ التقديرُ لا يُطبع (عطبُ R117-7)"
    assert got["field"] in ("cost_billed_usd", "spent_after_usd") and got["questions"] > 0
