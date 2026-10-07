"""**وفاءُ التطبيق بعقد الدفتر — على مسار التطبيق نفسه (R96-1 · وSPEC-96-1: البوّابةُ المُعلَنة نقلةً).**

قرارُ المالك على `147a0de` أمر بنقل ثلاثةٍ من الفرع القديم: الترقيمَ · وإزالةَ الأداة الخاطئة ·
**والبوّابةَ المُعلَنة**. وكانت هناك `xfail` صارمةً لأنّ الزرَّ **لا يُنتج ملفًّا**. وفي هذا الفرع
**هبط الإصلاحُ نفسُه** ⇒ فالبوّابةُ الصادقةُ اليوم **إيجابيّة**: تُقاد بحالة التطبيق (المُهيّئ المعتمد:
نداءاتُ النموذج مكتوبة، والشبكةُ مقطوعة ⇒ بلا كلفة) وتسأل: هل بنى التطبيقُ **صفوفَ العقد** كاملةً؟

**وبوّابةُ القبول (الزرّ + الأوراقُ السبع) للمدقّق بقرار المالك** — هذه تحرس **سطحَ العقد** لا الواجهة،
فلا تُغني عنها ولا تُزاحمها.

**والعضُّ مقيسٌ على ما قبل الإصلاح:** على `147a0de` كان مسارُ التطبيق يرفع
`sqlite3.IntegrityError: NOT NULL constraint failed: rows_verified.row_no` (٩ حقولٍ من ٢٢ بلا رقمِ صفّ)،
و`rows_contract` لم يكن موجودًا أصلًا ⇒ فالبوّابةُ تسقط هناك بالمعنى لا بالمفتاح.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from statement_qa.ledger import COLUMNS  # noqa: E402

from test_intake import app_run  # noqa: E402,F401 — المُهيّئ المعتمد نفسه (بلا كلفة ولا شبكة)


def test_the_app_builds_the_ledger_contract_for_every_row(app_run):  # noqa: F811
    """**الصفوفُ التي تُبنى في التطبيق تحمل عقدَ الدفتر كاملًا** — والترقيمُ داخل الصفحة 1..n."""
    _out, _calls, _pages, state = app_run([("10", "0"), ("20", "0"), ("30", "0")])

    rows = state.get("rows_contract") or []
    assert rows, ("التطبيق لم يبنِ صفوفَ العقد (`STATE[\"rows_contract\"]` فارغة) — وهو الموضعُ الذي كان "
                  "يقف عند ٩ حقولٍ فيرفع الزرُّ قبل أن يُنتج ملفًّا")

    # **والاسمُ يُترجَم كما يُترجَم في الإدراج** (`_row_values`: `page`→`pg` · `source`→`proof_source`)
    # فلا يُقاس الشكلُ بالاسم قبل الترجمة — وهو ما يقرؤه حارسُ الأعمدة في `tests/test_ledger.py`.
    keys = set().union(*(r.keys() for r in rows))
    as_ledger = {("pg" if k == "page" else "proof_source" if k == "source" else k) for k in keys}
    missing = sorted(set(COLUMNS) - as_ledger)
    assert not missing, f"أعمدةٌ من عقد الدفتر لم يبنها التطبيق: {missing}"

    # **والترقيمُ داخل الصفحة 1..n** كما يُرقّم مسارُ التشغيل (`chunking.py:77`) ويفرضه
    # `UNIQUE (pg, row_no)` في المخطَّط — وغيابُه هو العطبُ الأوّل المقيس.
    by_page: dict[int, list[int]] = {}
    for r in rows:
        assert isinstance(r.get("row_no"), int), f"صفٌّ بلا رقمِ صفّ: {r}"
        by_page.setdefault(r["page"], []).append(r["row_no"])
    for pg, nums in by_page.items():
        assert nums == list(range(1, len(nums) + 1)), f"ترقيمُ الصفحة {pg} ليس 1..n: {nums}"

    # **والسطحان لا يختلطان:** سطحُ العرض/الأسئلة يبقى بلغته (`kind`/`ok`/`type`) ولا يحمل عقدَ الدفتر
    # (فلو حمل لصار للعقد موضعان — وهو ما يمنعه القرار).
    view = state.get("rows") or []
    assert view, "سطحُ العرض (`STATE[\"rows\"]`) فارغ — والصفحاتُ المقروءة لها صفوف"
    assert "row_no" not in view[0], "تسرّب عقدُ الدفتر إلى سطح العرض: للعقد موضعٌ واحد"


@pytest.mark.parametrize("column", ["counted"])
def test_the_counted_column_is_computed_in_the_builder(app_run, column):  # noqa: F811
    """**وخليّةُ `counted` تُحسب في الباني (F1 · مقعدُ البنية):** كانت تُمرَّر من المنادي فحملت
    كمّيتين باسمٍ واحد (`len(rows)` عند التطبيق · `len(rows with balance)` في سطر الأوامر)."""
    _out, _calls, _pages, state = app_run([("10", "0"), ("20", "0")])
    rows = state.get("rows_contract") or []
    assert rows and column in rows[0], f"العمودُ {column} غائبٌ عن صفوف العقد"
    by_page: dict[int, int] = {}
    for r in rows:
        by_page[r["page"]] = by_page.get(r["page"], 0) + (1 if r.get("balance") is not None else 0)
    for r in rows:
        assert r["counted"] == by_page[r["page"]], (
            f"`counted` في الصفحة {r['page']} = {r['counted']} والمتوقَّع {by_page[r['page']]} "
            "(عددُ صفوف الصفحة ذات الرصيد المطبوع — المعنى الواحد في الطريقين)")
