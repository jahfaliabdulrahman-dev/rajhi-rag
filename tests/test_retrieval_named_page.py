"""**R105-4 — الصفحةُ المسمّاةُ تصل إلى السياق (بلا نموذجٍ لغويّ · بلا كلفة).**

**العطبُ المقيس في مراجعة ١٠٥ على `main`:** الحزمةُ تسمّي صفحاتٍ في أسئلتها، والقطعُ التي تُرسَل
مع السؤال **صفحاتٌ أخرى** — فالصفحةُ المسمّاةُ في السياق **واحدٌ من ٣٩**. والقاعدتان ٣ و٤ توجّهان
النموذجَ إلى القطع نفسِها («ألزم كلّ رقمٍ بمصدره: صفحة N، صفوف X–Y» · «إن لم تكفِ القطع قل غير
موجود في الكشف») ⇒ فالسؤال عن صفحةٍ بعينها يقرأ صفحاتٍ لا تخصّه.

**والعلاجُ مكوّنٌ من المكتبة لا من عندنا (قاعدةُ المالك):** `FAISS.similarity_search_with_score(…,
filter={"page": N}, fetch_k=…)` في `langchain_community` — **وفخُّه مقيس:** المرشِّحُ يعمل **بعد**
البحث ⇒ بـ`fetch_k` الافتراضيّ (20) تعود القائمةُ **فارغة**، وبـ`fetch_k` = حجم الفهرس تعود الصفحة.
فـ`retriever.retrieve(pages=…)` يقرأ الحجمَ من `index.ntotal`، **و`boost_last_page` طُويت فيه**
(كانت حالةً يدويّةً خاصّةً من الشيء نفسه).

**والضابطُ هنا يقيس الذراعين معًا** — بالمرشِّح وبلا مرشِّح — فيُثبت أنّ الفرقَ فعلُ الكود لا فعلُ
الصياغة:
  · **مع المرشِّح:** الصفحةُ المسمّاةُ في السياق لكلّ سؤالٍ يسمّي صفحةً داخل الكشف (**‏٣٩ من ٣٩**
    في عائلة `derive.page` وحدَها، وهي التي قاسها المراجع).
  · **وبلا مرشِّح:** العددُ نفسُه **أدنى أدنى** — وهذا هو قياسُ ما كان على `main`.

وتخطّيها في نسخةٍ نقيّة **مُعلَنٌ بالاسم** (`require_local_evidence` · `require_run`) لأنّها تُقاس
على الكشف ونموذجِ التضمين المحلّيّين — لا على شيءٍ يُنزَّل في فحص.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

from tests._local_evidence import ROOT, require_local_evidence, require_run

#: العيّنةُ التي تبنيها أداةُ القياس بالافتراض (`tools/eval_questions.py --run`).
RUN = ROOT / "data/local_sample/slice_629p"
QUESTIONS = ROOT / "docs/eval_pack/questions.json"
#: نموذجُ التضمين المحلّيّ (`retriever.EMBED_MODEL`) — وجودُه شرطُ قياسٍ لا يُخترق بالتخطّي الصامت.
EMBED_CACHE = (pathlib.Path.home() / ".cache/huggingface/hub"
               / "models--intfloat--multilingual-e5-small")


def _questions() -> list[dict]:
    d = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    return d["questions"] if isinstance(d, dict) and "questions" in d else d


def _derive_page(q: dict):
    d = q.get("derive")
    return d.get("page") if isinstance(d, dict) else None


def _named_in(question: str, n_pages: int) -> list[int]:
    from statement_qa.qa import named_pages
    return [p for p in named_pages(question) if 1 <= p <= n_pages]


# ── المقطعُ الخالص: الاستخراجُ من نصّ السؤال — يعمل في الـCI بلا بياناتٍ ولا نموذج ─────────────
def test_the_pages_named_in_the_questions_are_extracted_exactly():
    """**والأرقامُ تُقرأ من نصّ السؤال — عائلة `derive.page` هي المرجعُ (٣٩ سؤالًا)، والاستخراجُ
    يجب أن يوافقها كلَّها** (لا أن يقاربها) — ثمّ صورُ الكتابة الأخرى تُقاس صريحةً."""
    from statement_qa.qa import named_pages

    qs = _questions()
    with_page = [q for q in qs if _derive_page(q)]
    wrong = [(q["id"], _derive_page(q), named_pages(q["q"]))
             for q in with_page if named_pages(q["q"]) != [_derive_page(q)]]
    assert not wrong, f"استخراجٌ لا يوافق `derive.page`: {wrong}"
    assert len(with_page) == 39, f"عائلةُ `derive.page` ليست ٣٩ بل {len(with_page)}"

    # **صورُ الكتابة الثلاثُ مقيسةٌ بالنصّ لا مُدَّعاة:**
    assert named_pages("ما مجموعُ مبالغ الحركات المطبوعة داخل الصفحة ٥٢؟") == [52]
    assert named_pages("ما الرقمُ المطبوعُ في تذييل الصفحة ٢؟") == [2]
    assert named_pages("قارن الصفحتين ٢ و٣.") == [2, 3]
    assert named_pages("ما الرصيدُ في الصفحة 4 من 5؟") == [4]
    assert named_pages("ما أكبرُ حركةٍ في الصفحة ۲۴۲؟") == [242]      # هنديّةٌ ممتدّة
    assert named_pages("كم عددُ الحركات في الكشف؟") == []


# ── المقطعُ الكامل: الفهرسُ الحقيقيّ — يُقاس حيث يوجد الكشف (بيئة المالك · نسخة المدقّق) ────────
def _index():
    require_local_evidence()
    require_run(RUN)
    if not EMBED_CACHE.exists():
        pytest.skip("نموذجُ التضمين المحلّيّ غيرُ موجود (ولا يُنزَّل في فحص) ⇒ الضابطُ لا يُقاس هنا")
    sys.path.insert(0, str(ROOT / "src"))
    from tools.refusal_test import build_rows
    from statement_qa.chunking import chunk_rows
    from statement_qa.retriever import build_index

    rows, n_pages = build_rows(RUN)
    chunks = chunk_rows([{**r, "row_no": i + 1} for i, r in enumerate(rows)])
    return build_index(chunks), n_pages, {c.page for c in chunks}


def test_the_named_page_reaches_the_context():
    """**الذراعان مقيسان معًا:** بالمرشِّح ⇒ ٣٩ من ٣٩ · وبدونه ⇒ ما كان على `main` (١ من ٣٩).

    **والسؤالُ يُقاس على صفحةٍ لها قطعٌ في الكشف** — وسؤالٌ يسمّي صفحةً **لا وجودَ لها** (فجوةٌ
    مسجّلة، أو صفحةٌ خارج الكشف) **لا يُقاس**: لا يُطالَب المرشِّحُ بصفحةٍ ليست في الفهرس. وهي
    **ستّةٌ مُسمّاةٌ** (عائلةُ الغياب: ٦٢٩ — وهي فجوةٌ مسجّلة — و٧٠٠ · ٨٠٠ · ٩٠٠ · ١٠٠٠)، والمراجعُ
    أخرجها كذلك حين قاس «٣٩ من ٣٩».
    """
    from statement_qa.retriever import retrieve

    store, _n_pages, chunk_pages = _index()
    qs = _questions()
    from statement_qa.qa import named_pages

    named = [(q["id"], named_pages(q["q"])) for q in qs]
    named = [(i, p) for i, p in named if p]
    inside = [(i, p) for i, p in named if all(x in chunk_pages for x in p)]
    outside = [(i, p) for i, p in named if not all(x in chunk_pages for x in p)]
    texts = {q["id"]: q["q"] for q in qs}
    derive39 = {q["id"] for q in qs if _derive_page(q)}

    def arm(with_filter: bool) -> tuple[int, list[str]]:
        ok, misses = 0, []
        for qid, pages in inside:
            got = {h["page"] for h in retrieve(store, texts[qid], k=4,
                                               pages=pages if with_filter else None)}
            if all(p in got for p in pages):
                ok += 1
            else:
                misses.append(qid)
        return ok, misses

    ok_filtered, missed = arm(True)
    ok_plain, _ = arm(False)
    print(f"\nأسئلةٌ تسمّي صفحةً: {len(named)} · لها قطعٌ في الكشف: {len(inside)} "
          f"· بمُرشِّح {ok_filtered}/{len(inside)} · بلا مُرشِّح {ok_plain}/{len(inside)}"
          f"\nوالمُستبعَدُ لأنّ صفحتَه ليست في الفهرس: {[(i, p) for i, p in outside]}")

    assert len(inside) == 39, f"عائلةُ «صفحةٌ لها قطع» ليست ٣٩ بل {len(inside)}"
    assert ok_filtered == 39, f"سقط مع المُرَشِّح: {missed}"
    assert ok_plain < ok_filtered, (
        "الذراعُ المرجعيّةُ يجب أن تكون أدنى — وما تساويا إلّا إن كان المُرَشِّحُ لا يفعل شيئًا "
        f"(بلا مُرشِّح {ok_plain}/{len(inside)})")
    # **وضابطُ الاسم لا العدد:** عائلةُ الغياب الستّةُ مُسمّاةٌ، فلا تُقرأ «٣٩» رقمًا مُرسَلًا.
    assert len(outside) == 6, outside
    assert len(derive39) == 39
