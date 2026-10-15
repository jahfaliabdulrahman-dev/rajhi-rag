"""**R127-1 (P2 · مراجعة ١٢٧ · قرار المالك `20261015-211000` · الخيار ١): سؤالُ السلسلة يُحكم بمبلغ الفرق، لا بقائمة ألفاظ.**

**العطبُ المقيس (قديمٌ منذ 2026-09-23):** كانت `_polarity` تحكم `chn-01..04` بألفاظ، فأُسقط جوابٌ صحيحٌ
**٧ مرّات في ٦ من ١٢ ملفَّ جولة** (r100 · r102 ×٢ · r103 · r107 · r108 · r126): كلُّها **تنفي التساويَ
وتذكر الفرقَ الصحيح** ثمّ تشرح أنّ التسلسلَ متّصل — و«متّصل» عضوٌ في `_POS` ⇒ فسقطت بـ`neg and not pos`.
**وسطرُ سببِها المطبوع كان يقول «نفيٌ صريح · الفرقُ مذكور»** — أي إنّه يقرأ كنقصٍ وهو زيادةٌ مضادّة
(R126-3، ويزول بحذف القائمة).

**والثابتُ المنفَّذ:** الحكمُ بالدعوى التي يطلبها السؤال — **مبلغُ الفرق مقروءًا رقمًا** — ولا قائمةَ
ألفاظٍ في مسار السلسلة. **وما يُترك مُعلَنًا:** فحصُ «لم يدّعِ التساويَ بالكلام» (وقِيس أنّ صفرَ جوابٍ
في الملفّات الـ١٢ يذكر الفرقَ الصحيح ويدّعي التساوي).

**والقبولُ الثلاثيّ:** ① إعادةُ القراءة تُنتج السبعةَ المسمّاة ✗ ⇒ ✓ بالضبط وصفرًا عكسًا ·
② نقيضُه (فرقٌ خطأ) ⇒ ✗ · ③ والمساراتُ الأخرى لا تُمسّ (وفيها الضابطُ الآليّ).
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tests._local_evidence import require_pack, require_run  # noqa: E402
from tools import eval_questions as ev                       # noqa: E402
from tools import pack_io                                    # noqa: E402
from tools.refusal_test import build_rows                    # noqa: E402

#: **السبعةُ المسمّاة في المراجعة ١٢٧** (ملفٌّ · سؤال) — والخريطةُ مجمَّدةٌ عن قصد: هي نتيجةُ القرار،
#: فتغيُّرُها (زيادةً أو نقصًا) يُسقط هذا الضابطَ بدل أن يمرّ صامتًا.
NAMED_SEVEN = {
    ("answers_50_r100.json", "chn-01"),
    ("answers_50_r102.json", "chn-01"),
    ("answers_50_r102.json", "chn-04"),
    ("answers_50_r103.json", "chn-03"),
    ("answers-r107.json", "chn-01"),
    ("answers-r108.json", "chn-03"),
    ("answers-r126-01.json", "chn-03"),
}
#: **الملفّاتُ الـ١٢ المسمّاة في المراجعة ١٢٧** (الاثنا عشر التي تحمل أسئلةَ سلسلة).
SAVED_RUNS = [
    "answers-r105.json", "answers-r107.json", "answers-r108-03.json", "answers-r108.json",
    "answers-r123-01.json", "answers-r126-01.json", "answers.json", "answers_50.json",
    "answers_50_r100.json", "answers_50_r102.json", "answers_50_r103.json", "answers_50_r93.json",
]


def _run_dir() -> pathlib.Path:
    """مجلّدُ العيّنة **من جذر الأدلّة** (`pack_io.data_root()` — `git-common-dir`) لا من جذر الشجرة.

    (ونفسُ صنف R126-1: شجرةُ عملٍ مرتبطة لا تحمل `data/` ⇒ فمسارٌ مبنيٌّ من جذر الشجرة يُعلن تخطّيًا
    حيث البياناتُ مرئيّة، أو **يسقط** حيث الحاجةُ أضيقُ من الادّعاء.)
    """
    return pack_io.data_root() / "data" / "local_sample" / "slice_629p"


def _data_dir() -> pathlib.Path:
    return pack_io.data_root() / "data" / "eval_pack"


def _require_saved_runs() -> None:
    """**حضورُ ما يُقاس عليه بالسؤال الذي تسأله الفحوصُ نفسُها** — لا علامةً أعمّ منه."""
    missing = [n for n in SAVED_RUNS if not (_data_dir() / n).exists()]
    if missing:
        pytest.skip(f"ملفّاتُ جولاتٍ محفوظة غائبةٌ في هذه النسخة ({len(missing)} من {len(SAVED_RUNS)}: "
                    f"{', '.join(missing[:3])}…) ⇒ القياسُ على المحفوظ لا يُدَّعى هنا")


def _chain_q() -> dict:
    """سؤالُ السلسلة `chn-03` من الحزمة المُلتزمة (اسمُه من الحزمة، لا مكتوبًا بيد)."""
    spec = json.loads((ROOT / "docs/eval_pack/questions.json").read_text())
    return next(q for q in spec["questions"] if q["expect"] == "chain" and q["id"] == "chn-03")


def _truth_of(q: dict):
    """الحقيقةُ المشتقّةُ من الوعاء الحقيقيّ — **والضابطُ يُبنى منها لا من رقمٍ مكتوب** (القاعدة ١٣)."""
    pack = json.loads(pack_io.pack_path().read_text())
    pages = sorted(int(p) for p in (pack.get("page_seal") or {}).get("pages") or {})
    c = ev.Corpus(_run_dir(), pages)
    rows, _ = build_rows(_run_dir())
    return ev.truth(q, c, pack, rows)[0], rows


def test_a_correct_difference_beside_a_connectivity_word_is_right() -> None:
    """**شكلُ `chn-03` في r126 بعينه:** نفيٌ صريح + الفرقُ الصحيح + شرحٌ فيه «متّصل» ⇒ **صحيح.**

    (وهذا هو الضابطُ الأحمرُ قبل الإصلاح: القائمةُ كانت تُشعل الإيجابَ فتُسقطه.)
    """
    require_run(_run_dir())
    require_pack()
    q = _chain_q()
    tv, rows = _truth_of(q)
    diff = float(tv["diff"])
    ans = (f"لا يساويه. رصيدُ آخر صفٍّ في الصفحة السابقة يخالف أولَ صفٍّ في التالية بفرقٍ قدره {diff} ريال، "
           f"وهو حركةُ الصفّ نفسه، والرصيد متّصل صحيحًا.")
    ok, why = ev.score_answer(q, tv, ans, ev._Trace({"answer_kind": "figure"}), rows)
    assert ok, why
    assert "متّصل" in ans, "الضابطُ لم يعد يبني الجوابَ بالكلمة التي أسقطته (نصٌّ مختلف ⇒ ضابطٌ بلا معنى)"


def test_a_wrong_difference_is_wrong() -> None:
    """**النقيض:** النفيُ صريحٌ وكلمةُ الاتّصال حاضرة — **والفرقُ خطأ** ⇒ **خطأ** (فالحكمُ بالرقم لا بالكلمة)."""
    require_run(_run_dir())
    require_pack()
    q = _chain_q()
    tv, rows = _truth_of(q)
    # **والقياسُ لا يكتب مبلغًا في ملفٍّ مُتتبَّع** (القاعدة ١٤: «تُغيَّر القيمةُ ولا يُعفى الموضع»):
    # الإزاحةُ صغيرةٌ (تفوق التسامح ٠٫٠٥) ولا تُكتب بشكلِ مبلغ — والقيمةُ تُشتقّ من الحقيقة وقتَ التشغيل.
    wrong = float(tv["diff"]) + 1
    ans = (f"لا يساويه. الفرق {wrong} ريال، والرصيد متّصل صحيحًا.")
    ok, why = ev.score_answer(q, tv, ans, ev._Trace({"answer_kind": "figure"}), rows)
    assert not ok, why


def test_the_chain_path_does_not_read_the_word_list() -> None:
    """**وموضعٌ واحدٌ بالبناء:** فرعُ السلسلة في `_score_common` **لا يلمس** `_polarity` ولا `_POS`/`_NEG`.

    (فحصٌ بالـ`ast` على الشجرة: لا يكفي أن يكون الحكمُ صحيحًا اليوم — يُقاس ألّا تعود القائمةُ إليه.)
    """
    src = (ROOT / "tools" / "eval_questions.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body
              if isinstance(n, ast.FunctionDef) and n.name == "_score_common")
    chain_if = None
    for n in ast.walk(fn):
        if isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and n.test.comparators:
            comp = n.test.comparators[0]
            if isinstance(comp, ast.Constant) and comp.value == "chain":
                chain_if = n
                break
    assert chain_if is not None, "فرعُ السلسلة (`q[\"expect\"] == \"chain\"`) لم يُعرف ⇒ الفحصُ لا يقيس شيئًا"
    dumped = ast.dump(chain_if)
    for banned in ("_polarity", "_POS", "_NEG"):
        assert banned not in dumped, (
            f"{banned} ما زالت تُقرأ في فرع السلسلة — والقرار `20261015-211000` يطلب الحكمَ بمبلغ الفرق "
            f"وحده (وفرعُ `boolean` وحده يُسمح له بقراءتها، وهو مفصولٌ عن هذا الفرع)")


def test_the_pack_declares_no_boolean_chain_question() -> None:
    """**وحدُّ ما تُرك مُعلَنًا بقياس:** `_polarity` قارئُها الباقي فرعُ `expect == "boolean"`،
    **والحزمةُ خاليةٌ منه (٠)** ⇒ فالمسارُ غيرُ مُختبَرٍ **يُعلَن**، ولو دخل سؤالٌ من هذا الصنف ظهر هذا
    الحدُّ بدل أن يمرّ الحكمُ بقائمةٍ لا يقيسها ضابط."""
    spec = json.loads((ROOT / "docs/eval_pack/questions.json").read_text())
    kinds = {q["expect"] for q in spec["questions"]}
    assert "boolean" not in kinds, (
        f"دخل سؤالُ سلسلةٍ بـ`expect == \"boolean\"` ⇒ `_polarity` صارت تحكم في مسارٍ مُختبَرٍ بلا ضابطٍ "
        f"يقيس صحّتَها: الصيغةُ تُبتكر أو يُعلَن الحدّ. الأنماطُ الآن: {sorted(kinds)}")
    src = (ROOT / "tools" / "eval_questions.py").read_text(encoding="utf-8")
    assert "_polarity(" in src, "أُزيلت `_polarity` وبقي فرعُ `boolean` ⇒ مسارٌ بلا حُكم"


def test_the_saved_runs_flip_exactly_the_named_seven() -> None:
    """**القبولُ بالقياس على المحفوظ:** ١٢ ملفًّا · ٤٨ سجلَ سلسلة ⇒ **٧ ✗ ⇒ ✓ بالضبط وصفرٌ عكسًا.**

    **والعمودُ المقارِن هو المقيس:** هو الذي يحكم السجلّاتِ السابقةَ لحقل الإشارة (حكمُ التاريخ بمصحِّحه)،
    **والعمودُ المنشور** يحكم ما يحمل الإشارةَ وحدَه (وحدُّه مُعلَن في `score_answer`). والانقلابُ يُقاس بين
    ما **حُفظ** في السجلّ وبين حكمِ القاعدة المصحَّحة — لا بين حكمين مُشتقَّين بيدي.
    """
    _require_saved_runs()
    require_run(_run_dir())
    require_pack()
    spec = json.loads((ROOT / "docs/eval_pack/questions.json").read_text())
    qs = {q["id"]: q for q in spec["questions"]}
    pack = json.loads(pack_io.pack_path().read_text())
    pages = sorted(int(p) for p in (pack.get("page_seal") or {}).get("pages") or {})
    c = ev.Corpus(_run_dir(), pages)
    rows, _ = build_rows(_run_dir())

    up: set[tuple[str, str]] = set()
    down: set[tuple[str, str]] = set()
    judged = 0
    data_dir = _data_dir()
    for name in SAVED_RUNS:
        f = data_dir / name
        assert f.exists(), f"ملفُّ جولةٍ مسمًّى في المراجعة ١٢٧ غائبٌ عن القرص: {name}"
        for rec in json.loads(f.read_text()).get("results", []):
            q = qs.get(rec["id"])
            if q is None or q.get("expect") != "chain":
                continue
            judged += 1
            tv, _ = ev.truth(q, c, pack, rows)
            ok, _why = ev.score_answer_by_text(q, tv, rec.get("answer", ""), ev._Trace(rec), rows)
            was = bool(rec.get("ok"))
            if ok and not was:
                up.add((name, rec["id"]))
            elif was and not ok:
                down.add((name, rec["id"]))
    assert judged == 48, f"عددُ سجلات السلسلة تغيّر: {judged} (كان ٤٨ في المراجعة ١٢٧) ⇒ تُحدَّث القائمةُ بالاسم"
    assert up == NAMED_SEVEN, (
        f"الانقلاباتُ ✗ ⇒ ✓ ليست السبعةَ المسمّاة:\n  زائدٌ: {sorted(up - NAMED_SEVEN)}\n"
        f"  ناقصٌ: {sorted(NAMED_SEVEN - up)}")
    assert not down, f"وانقلابٌ في الاتجاه الآخر ⇒ لا يُقبل: {sorted(down)}"
    # **والنمطُ الذي وُلد منه العطب:** كلُّ واحدٍ من السبعة كان سببُه المطبوع «نفيٌ صريح · الفرقُ مذكور».
    for name, qid in sorted(NAMED_SEVEN):
        rec = next(r for r in json.loads((data_dir / name).read_text())["results"] if r["id"] == qid)
        assert re.search(r"نفيٌ صريح · الفرقُ مذكور", str(rec.get("why"))), \
            f"{name}/{qid}: سببُه المحفوظ ليس نمطَ العطب (القائمةُ المجمَّدة لم تعد تصف الواقع)"


def test_the_published_column_flips_the_same_question_where_the_record_carries_the_signal() -> None:
    """**والعمودُ المنشور:** على الملفّ الذي يحمل الإشارة (`r126`) يقلب السؤالُ نفسُه ⇒ **٤/٤ في السلاسل**.

    (وهو المقيسُ المتوقَّع لدرجة الجولة: ٤٧ ⇒ **٤٨**/٥٠ — ويُقاس بالسطر المقارِن للأداة لا بيدي.)
    """
    _require_saved_runs()
    require_run(_run_dir())
    require_pack()
    spec = json.loads((ROOT / "docs/eval_pack/questions.json").read_text())
    qs = {q["id"]: q for q in spec["questions"]}
    pack = json.loads(pack_io.pack_path().read_text())
    pages = sorted(int(p) for p in (pack.get("page_seal") or {}).get("pages") or {})
    c = ev.Corpus(_run_dir(), pages)
    rows, _ = build_rows(_run_dir())
    f = _data_dir() / "answers-r126-01.json"
    rec = next(r for r in json.loads(f.read_text())["results"] if r["id"] == "chn-03")
    q = qs["chn-03"]
    tv, _ = ev.truth(q, c, pack, rows)
    ok, why = ev.score_answer(q, tv, rec.get("answer", ""), ev._Trace(rec), rows)
    assert ok, why
