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


# ── المقطعُ الخالص: الاستخراجُ من نصّ السؤال — يعمل في الـCI بلا بياناتٍ ولا نموذج ─────────────
def test_the_pages_named_in_the_questions_are_extracted_exactly():
    """**والأرقامُ تُقرأ من نصّ السؤال — عائلة `derive.page` هي المرجعُ (٣٩ سؤالًا)، والاستخراجُ
    يجب أن يوافقها كلَّها** (لا أن يقاربها) — ثمّ صورُ الكتابة الأخرى تُقاس صريحةً."""
    from statement_qa.scope import pages_in as named_pages

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
    # **والمدى يُفكّ (بوّابةُ المُنتِج · R105-4):** «١٠–١٢» كانت تُقرأ صفحتين **وتسقط ١١**
    assert named_pages("قارن صفحات ١٠–١٢.") == [10, 11, 12]
    assert named_pages("قارن صفحات 10-12.") == [10, 11, 12]
    assert named_pages("قارن الصفحات من ٥ إلى ٧.") == [5, 6, 7]
    # **وسقفُ الفكّ مُعلَن:** مدى شاذٌّ (خطأٌ مطبعيّ) لا يُفكّ إلى ألف صفحة
    assert named_pages("صفحات ١–١٠٠٠.") == [1, 1000]


# ── الفخُّ وقاعدتا الحصّة — بفهرسٍ مُقلَّد: بلا نموذجٍ وبلا بيانات (تعمل في الـCI) ───────────────
class _Doc:
    def __init__(self, page: int, row: int):
        self.metadata = {"chunk_id": f"p{page:03d}-r{row:02d}-{row:02d}",
                         "page": page, "row_start": row, "row_end": row}
        self.page_content = f"[صفحة {page}]"


class _Store:
    """فهرسٌ مُقلَّد يسجّل كلّ نداء: يُثبت **ماذا طُلب** لا **ما أُعيد** وحدَه."""

    def __init__(self, per_page: dict[int, int], ntotal: int | None = None):
        self.pages = {p: [_Doc(p, i + 1) for i in range(n)] for p, n in per_page.items()}
        if ntotal is not None:
            self.index = type("_Idx", (), {"ntotal": ntotal})()
        self.calls: list[dict] = []

    def similarity_search_with_score(self, query, k=4, filter=None, fetch_k=None):
        self.calls.append({"k": k, "filter": filter, "fetch_k": fetch_k})
        if filter is not None:
            return [(d, 0.1) for d in self.pages.get(filter["page"], [])][:k]
        flat = [d for p in sorted(self.pages) for d in self.pages[p]]
        return [(d, 0.9) for d in flat][:k]


def test_the_trap_reads_the_index_size_and_never_guesses():
    """**الفخُّ المقيس (مراجعة ١٠٥):** المرشِّحُ يعمل بعد البحث ⇒ `fetch_k` = حجمِ الفهرس،
    **والحجمُ يُقرأ من `index.ntotal`**. وإن كان الفهرسُ مُقلَّدًا (بلا `.index`) فلا انهيار —
    يُطلَب `fetch_k` = العددِ المطلوب، وهذا الفرعُ الاحتياطيُّ **مقيسٌ هنا** وإلّا بقي الفخُّ بلا حرس.
    """
    from statement_qa.retriever import retrieve

    real = _Store({242: 1, 1: 1}, ntotal=626)
    retrieve(real, "س", k=4, pages=[242])
    assert real.calls[0]["fetch_k"] == 626, real.calls
    assert real.calls[0]["filter"] == {"page": 242}

    fake = _Store({242: 1, 1: 1})                    # بلا `.index` ⇒ index_size ⇒ 0
    got = retrieve(fake, "س", k=4, pages=[242])
    assert fake.calls[0]["fetch_k"] == 4, fake.calls  # «لا أعرف» ⇒ العددُ المطلوب، لا صفر
    assert [h["page"] for h in got][0] == 242


def test_a_named_page_is_never_dropped():
    """**قاعدةُ الحصّة (بوّابةُ المُنتِج · R105-4):** كانت حلقةُ `k` تقطع عند `k` بصمت
    ⇒ سؤالٌ يسمّي خمسَ صفحاتٍ لا يبلغ الفهرسَ إلّا بأربعٍ منها. والآن لكلّ صفحةٍ حصّةٌ
    (`max(1, limit // len(pages))`) و`limit = max(k, len(pages))` ⇒ **لا صفحةَ مسمّاةٌ تُسقَط**.
    """
    from statement_qa.retriever import retrieve

    five = _Store({p: 1 for p in (10, 20, 30, 40, 50)}, ntotal=626)
    got = retrieve(five, "س", k=4, pages=[10, 20, 30, 40, 50])
    assert [h["page"] for h in got] == [10, 20, 30, 40, 50], got

    two = _Store({2: 3, 3: 3}, ntotal=626)           # صفحتان كبيرتان: الحصّةُ تقتسم المجموع
    got2 = retrieve(two, "س", k=4, pages=[2, 3])
    assert {h["page"] for h in got2} == {2, 3}, got2
    assert two.calls[0]["k"] == two.calls[1]["k"] == 2, two.calls


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
    from statement_qa.scope import pages_in as named_pages

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
# ── R107-1 (٢)+(٣): القارئُ واحدٌ — وضابطان يقيسانه ──────────────────────────────────────────────
def test_the_gate_and_the_retrieval_read_the_same_pages():
    """**R107-1 (٢): أربعُ صيغٍ كان القارئُ الأوّلُ لا يراها** (بلا «ال» · «الصفحه» بالهاء ·
    المثنّى «الصفحتين» · `page` إنجليزيّة) ⇒ فتمرّ إلى النموذج، والاسترجاعُ يعرف أنّ صفحتَها
    **خارج الكشف**. والقارئُ اليوم واحدٌ (`scope.pages_in`) فالحكمان لا يفترقان.
    **يُكتب أحمرَ على الرأس قبل التوحيد** (كان `page_in` يُعيد `None` للصيغ الأربع).
    """
    from statement_qa.scope import classify, pages_in

    for q in ("كم عدد الحركات في صفحة ٧٠٠؟",
              "ما مجموع الصفحتين ٢ و٧٠٠؟",
              "كم عدد الحركات في الصفحه ٧٠٠؟",
              "How many rows on page 700?"):
        assert pages_in(q), "القارئُ الواحد لا يرى الصفحةَ في: " + q
        assert classify(q, (), 629, frozenset()).kind == "no_such_data", q
    # **وحدُّه:** سؤالٌ داخل الكشف لا يُرفض — الحارسُ لا يرفض ما يمكن إثباتُه
    assert classify("ما مجموعُ مبالغ الحركة في الصفحة ٥٢؟", (), 629, frozenset()).kind == "in_scope"
    assert classify("قارن الصفحتين ٢ و٣.", (), 629, frozenset()).kind == "in_scope"


#: **جدولُ التكافؤ — مقيسٌ على الرأس `a60011f` قبل توحيد القارئين** (بوّابةُ المُنتِج · R105-4):
#: لكلّ سؤالٍ: `page_in` (القارئُ القديم) · `named_pages` (قارئ الاسترجاع) · حكمُ البوّابة بـ`max_page=629`.
#: **ولم يفترق القارئان على الأسئلة الخمسين** (قِيس: صفر اختلاف)؛ والفرقُ كان في صيغٍ لا تسألها
#: الحزمة. **وهذا الجدولُ هو شرطُ أن يجري التوحيدُ قبل الخمسين دون أن يغيّر ما تقيسه:** يُعاد
#: توليدُه بالقارئ الواحد ويُقابَل صفًّا صفًّا، **وأيُّ افتراقٍ يُسقط الضابط.**
#: والصيغةُ: `id:page_in:pages:gate` (و`-` تعني «لا صفحةَ مسمّاة»).
_PRE_CHANGE_TABLE = (
    "num-01:2:2:in_scope num-02:2:2:in_scope num-03:52:52:in_scope num-04:52:52:in_scope num-05:242:242:in_scope "
    "num-06:242:242:in_scope num-07:486:486:in_scope num-08:486:486:in_scope num-09:27:27:in_scope num-10:100:100:in_scope "
    "num-11:290:290:in_scope num-12:535:535:in_scope cnt-01:2:2:in_scope cnt-02:25:25:in_scope cnt-03:51:51:in_scope "
    "cnt-04:52:52:in_scope cnt-05:242:242:in_scope cnt-06:486:486:in_scope cnt-07:500:500:in_scope cnt-08:535:535:in_scope "
    "bal-01:2:2:in_scope bal-02:52:52:in_scope bal-03:242:242:in_scope bal-04:486:486:in_scope chn-01:52:52,53:in_scope "
    "chn-02:242:242,243:in_scope chn-03:486:486,487:in_scope chn-04:2:2,3:in_scope cit-01:-:-:in_scope cit-02:-:-:in_scope "
    "cit-03:52:52:in_scope cit-04:60:60:in_scope cit-05:100:100:in_scope cit-06:242:242:in_scope cit-07:486:486:in_scope "
    "cit-08:535:535:in_scope cit-09:25:25:in_scope cit-10:500:500:in_scope abs-01:700:700:no_such_data abs-02:629:629:in_scope "
    "abs-03:-:-:in_scope abs-04:-:-:in_scope abs-05:243:243:in_scope abs-06:244:244:in_scope abs-07:700:700:no_such_data "
    "abs-08:2:2:in_scope abs-09:800:800:no_such_data abs-10:900:900:no_such_data str-03:-:-:in_scope abs-11:1000:1000:no_such_data "
)


def test_the_single_reader_reproduces_the_pre_change_table():
    """**R107-1 (٣): قراراتُ البوّابة وصفحاتُ الاسترجاع للأسئلة الخمسين كما قِيست قبل التوحيد.**"""
    from statement_qa.scope import classify, pages_in

    bank = {x["id"]: x["q"] for x in _questions()}
    rows = _PRE_CHANGE_TABLE.split()      # الأسطرُ المتجاورةُ تتّصل ⇒ التقسيمُ على الفراغات
    drifted = []
    for row in rows:
        qid, page_in, pages, kind = row.split(":")
        q = bank[qid]
        now = pages_in(q)
        now_page_in = str(now[0]) if now else "-"
        now_pages = ",".join(str(p) for p in now) or "-"
        if (now_page_in, now_pages, classify(q, (), 629, frozenset()).kind) != (page_in, pages, kind):
            drifted.append((qid, (now_page_in, now_pages), (page_in, pages)))
    assert not drifted, "افتراقٌ بعد التوحيد عن جدول ما قبلَه: " + repr(drifted)
    assert len(rows) == 50
    # **وتُطبع شهادةُ التطابق** (شرطُ مراجعة ١٠٧ للخمسين: «وضابطُ R107-1 (٣) يطبع تطابقَ قرارات
    # البوّابة وصفحاتِ الاسترجاع للأسئلة الخمسين») — تُقرأ في مخرَج التشغيل لا تُدَّعى.
    print(f"تطابقُ الجدول: {len(rows)} سؤالًا — قراراتُ البوّابة وصفحاتُ الاسترجاع كما قِيست قبل "
          f"توحيد القارئين (`a60011f`) · افتراقٌ 0")
