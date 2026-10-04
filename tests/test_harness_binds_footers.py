"""**كلُّ مقياسٍ يُمرِّر مُدخَلاتِه** — لا يقيس المقياسُ نفسَه.

**العِلّة (قِيست، لا استُنتجت):** حزمةُ الأسئلة المدفوعة أعطت `footer` **0/8**، والوكيلُ كان **صادقًا** في كلّ
حالة: قال «لا تذييلَ مطبوعًا لهذه الصفحة» ولم يُخمّن. والسببُ أنّ `tools/eval_questions.py` نادى
`answer_question(...)` **بلا `footers=`** بينما التطبيقُ (`app.py:1052`) يُمرّرها ⇒ فأداةُ `page_footer` قرأت
`footers=None` ⇒ «لا يوجد». **ولكلّ صفحةٍ من الثماني تذييلٌ مطبوعٌ في البيانات** (قِيس في `pg-*.json`).

فالبوّابةُ ثلاثةُ أضلاع:
① **الأصلُ (AST):** نداءُ `answer_question` في المقياس يربط `footers=` — والضابطُ **يسقط** لو نُزع.
② **المنتجُ (AST):** نداءُ التطبيق يربطه كذلك (فلا يُصلَح المقياسُ ويُنسى المنتج).
③ **السلوك (يُتخطّى بلا بيانات المالك):** للصفحة التي لها تذييلٌ مطبوع، **الأداةُ تفرق** بين وجود المُدخَل
وغيابه — فالفرقُ هو ما كان يُقاس خطأً، لا القدرة.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _calls(path: pathlib.Path, func: str) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func:
            out.append(node)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
              and node.func.attr == func):
            out.append(node)
    return out


def _binds(call: ast.Call, name: str) -> bool:
    return any(k.arg == name for k in call.keywords)


@pytest.mark.parametrize("rel,label", [
    ("tools/eval_questions.py", "المقياس"),
    ("app.py", "التطبيق"),
])
def test_every_harness_binds_the_printed_footers(rel: str, label: str) -> None:
    """**الضابطُ يقيس النداءَ نفسَه:** من ينادي `answer_question` يُمرّر التذييلاتِ المطبوعة.

    الثمنُ إن سقط: يقع في **صامتٍ** — الأداةُ تجيب «لا يوجد» بصدق، والدرجةُ تنزل، **والسببُ يُنسب إلى
    النموذج لا إلى المقياس**. (وهو عينُ ما وقع: 0/8 في الحزمة المدفوعة.)
    """
    calls = _calls(ROOT / rel, "answer_question")
    assert calls, f"{label}: لا نداءَ لـ`answer_question` في {rel} — العنوانُ تغيّر ⇒ حدِّث الضابطَ"
    missing = [c for c in calls if not _binds(c, "footers")]
    assert not missing, (
        f"{label} ({rel}): {len(missing)} نداءً بلا `footers=` من {len(calls)} — "
        f"والمُدخَلُ هو ما كان يُقاس خطأً (R77: أداةُ `page_footer`)")


def test_the_tool_answers_where_the_data_has_a_printed_footer() -> None:
    """**والسلوك:** الفرقُ قائمٌ فعلًا — لا دعوى في تعليق. (يُتخطّى بلا بيانات المالك.)

    يُقاس على **صفحةٍ لها تذييلٌ مطبوع** في `slice_629p_v2`: الأداةُ تُعيد رقمًا حين تُمرَّر التذييلات،
    وتقول «لا يوجد» بلا تمريرها. فيصحّ ما قيل: **0/8 كان عطبَ مُدخَلٍ لا عطبَ قدرة.**
    """
    run = ROOT / "data" / "local_sample" / "slice_629p_v2"
    if not (run / "results").exists():
        pytest.skip("بلا بيانات المالك المحلّيّة (بيئة CI) — الضابطان أعلاه يكفيان هنا")
    from tools.refusal_test import build_footers, build_rows   # noqa: PLC0415
    from statement_qa.qa_tools import make_qa_tools            # noqa: PLC0415

    rows, _n = build_rows(run)
    footers = build_footers(run)
    assert footers, "لا تذييلات مطبوعة ⇒ إمّا تغيّر شكل البيانات أو الدالّة"
    page = sorted(p for p in footers if isinstance(footers[p], dict) and footers[p])[0]

    def _ask(pg: int, with_f: bool) -> str:
        f = {pg: footers[pg]} if with_f else None
        tools = {t.name: t for t in make_qa_tools(rows, footers=f)}
        return tools["page_footer"].invoke({"page": int(pg)})

    rich, bare = _ask(page, True), _ask(page, False)
    # **يُقاس الرقمُ لا الصياغة:** الرقمُ المطبوع يظهر مع المُدخَل ولا يظهر بدونه (والأرقامُ بلا فواصل).
    import re
    raw = (footers[page] or {})
    val = str(raw.get("debits") or raw.get("credits") or "").replace(",", "")
    assert val and "." in val, f"الصفحة {page}: التذييلُ بلا رقمٍ مطبوع — اختر صفحةً أخرى"

    def _nums(t) -> set[str]:
        return {x.replace(",", "") for x in re.findall(r"[\d,]+\.\d+", str(t))}

    assert val in _nums(rich), (
        f"الصفحة {page}: بتمرير التذييل يجب أن يظهر الرقم {val} — got rich={rich!r}")
    assert val not in _nums(bare), (
        f"الصفحة {page}: وبلا تمرير يجب ألّا يظهر — got bare={bare!r}")
    assert rich != bare, f"الصفحة {page}: لا فرقَ بين وجود التذييل وغيابه ⇒ الفرضيّةُ باطلة"
