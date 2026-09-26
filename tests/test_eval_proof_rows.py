"""**لا سؤالَ بلا موضعِ إثبات** — ضوابطُ حاكمِ الإثبات (الخارطة · أ-١).

كان الناقصُ معلَنًا نصًّا: «لا يُطبع `--truth` صفوفَ الإثبات، ولا حارسَ «سؤالٌ بلا صفوفٍ ⇒ يسقط»».
فالآن: `truth()` تُعيد **موضعَ الإثبات** مع القيمة (من القيم نفسها لا من مصدرٍ ثانٍ)، و`classify_proof`
يحكم على كلّ سؤال، و`--validate` يُسقط الجولةَ على السؤال الذي لا موضعَ له — و**الاستثناءُ يُعلَن باسمه
وسببه ويُكشف متقادمًا**، فلا تصير القائمةُ غطاءً دائمًا.

الضوابطُ الأولى تعمل بلا كوربوس (تُشغَّل في CI)، والأخيران يحتاجان العيّنة ويتخطّيان **معلنين**.
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

from tests._local_evidence import require_pack, require_run, run_is_ready

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = ROOT / "data/local_sample/slice_629p"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tool():
    for p in (str(ROOT / "tools"), str(ROOT / "src"), str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return _load("evalq_proof_rows", "tools/eval_questions.py")


def _questions() -> list[dict]:
    return json.loads((ROOT / "docs/eval_pack/questions.json").read_text(encoding="utf-8"))["questions"]


# ————————————————————— ضوابطٌ بلا كوربوس (تعمل في CI) —————————————————————

def test_every_kind_has_a_proof_rule():
    """نوعٌ جديدٌ بلا قاعدةِ إثباتٍ = فتحةٌ صامتة ⇒ يسقط قبل أن يُكتب سؤال."""
    m = _tool()
    kinds = {q["derive"]["kind"] for q in _questions()}
    missing = sorted(k for k in kinds if k not in m.PROOF_RULE)
    assert not missing, f"أنواعٌ بلا قاعدةِ إثبات: {missing}"
    assert kinds, "لا أسئلة؟"


def test_every_exception_is_named_and_reasoned_and_known():
    """الاستثناءُ **باسمه وسببه**، ويخصّ سؤالًا موجودًا — وإلا فهو صمتٌ مموَّه."""
    m = _tool()
    ids = {q["id"] for q in _questions()}
    for qid, why in m.PROOF_EXCEPTIONS.items():
        assert qid in ids, f"استثناءٌ لسؤالٍ غير موجود: {qid}"
        assert isinstance(why, str) and len(why) > 20, f"استثناءٌ بلا سببٍ كافٍ: {qid}"


def test_check_proof_rejects_an_empty_locus():
    """**السمّ**: سؤالٌ يشتقّ صفوفه بلا صفوف ⇒ يُرفض بالاسم (ويعمل بلا كوربوس)."""
    m = _tool()
    q = {"id": "x-01", "derive": {"kind": "count_rows"}}
    empty = {"kind": "count_rows", "proof": {"rows": [], "pages": [7]}}
    filled = {"kind": "count_rows", "proof": {"rows": [12, 13], "pages": [7]}}
    c = _Scan([7])
    rws = [{"page": 7}] * 13                    # سلسلةٌ تكفي الصفّين (12، 13) — **والعالمُ يُمرَّر إلزامًا**
    assert m.check_proof(q, empty, c, rws), "قاعدةُ rows يجب أن تسقط بلا صفوف"
    assert m.check_proof(q, filled, c, rws) is None, "وبصفوفٍ داخل النطاق والسلسلة يجب أن تمرّ"
    assert m.check_proof({"id": "x-02", "derive": {"kind": "نوعٌ مستجدّ"}}, {"proof": {"rows": [1]}}, c, rws), \
        "نوعٌ بلا قاعدةٍ يجب أن يسقط"
    assert m.check_proof({"id": "x-03", "derive": {"kind": "footer"}},
                         {"proof": {"rows": [], "pages": []}}, c, rws), "قاعدةُ pages تسقط بلا صفحات"


def test_a_stale_exception_is_exposed_not_hidden():
    """استثناءٌ صار له إثباتٌ ⇒ **يُعلَن ليُزال** (وإلا صارت القائمةُ غطاءً دائمًا)."""
    m = _tool()
    qid = sorted(m.PROOF_EXCEPTIONS)[0]
    rows_ok = {"kind": "count_rows", "proof": {"rows": [5]}}
    _c, _r = _Scan([5]), [{"page": 5}] * 5      # السلسلةُ تكفي الصفَّ الخامس
    st, why = m.classify_proof({"id": qid, "derive": {"kind": "count_rows"}}, rows_ok, _c, _r)
    assert st == "ok" and "متقادم" in why, "يجب كشفُ الاستثناء المتقادم"
    st2, _ = m.classify_proof({"id": qid, "derive": {"kind": "count_rows"}}, {"proof": {"rows": []}}, _c, _r)
    assert st2 == "exception", "الاستثناءُ المُعلَن يُصنَّف استثناءً لا مكسورًا"
    st3, why3 = m.classify_proof({"id": "not-declared", "derive": {"kind": "count_rows"}}, {"proof": {"rows": []}}, _c, _r)
    assert st3 == "missing" and why3, "بلا استثناءٍ ⇒ مكسور"


# ————————————— موضعٌ لا يشير إلى دليله: يُرفض (مراجعة ٥٢ · R52-2) —————————————
# «غيرُ فارغ» ليست دليلًا: كان موضعُ الامتناع يعيد `[700, 701]` وهي **صفحتان لا وجودَ لهما**
# في كشفٍ من ٦٢٩، ويمرّ لأنّ الحاكم لا يسأل إلا عن قائمةٍ غير فارغة. هذان الضابطان يقيسان
# **الوقوعَ في نطاق الفحص** و**تغطيةَ المطابقات** — ولا يحتاجان قرصًا (كوربوسٌ مُصغَّر).

class _Scan:
    """كوربوسٌ مُصغَّر للضوابط بلا قرص: صفحاتُ الكشف + صفوفُ صفحةٍ لمن يحتاجها.

    **ومقعدُ المعايير (مراجعة ٥٢):** وجودُ هذا البديل هو الدليلُ على أنّ إلزامَ `c`/`rows` في
    `check_proof` **لم يُقيّد الاختبار** بشيء — فلا مبرّرَ لمسارٍ اختياريٍّ يمرّ بحكمٍ أضعفَ صامتًا.
    """

    def __init__(self, pages, raw=None):
        self._pages = list(pages)
        self._raw = dict(raw or {})

    def corpus_page_list(self):
        return list(self._pages)

    def raw_rows(self, page):
        return list(self._raw.get(page) or [])


def test_a_locus_outside_the_scan_is_refused():
    m = _tool()
    c = _Scan([1, 2, 3])
    q = {"id": "x-700", "derive": {"kind": "absent", "reason": "page_outside_pack", "page": 700}}
    bogus = {"kind": "absent", "reason": "page_outside_pack", "proof": {"rows": [], "pages": [700, 701]}}
    why = m.check_proof(q, bogus, c=c, rows=[{"page": 1}])
    assert why and "خارج نطاق الفحص" in why, f"موضعٌ لا وجودَ لصفحته يجب أن يُسقط، مرّ بـ{why!r}"
    real = {"kind": "absent", "reason": "page_outside_pack", "proof": {"rows": [], "pages": [3]}}
    assert m.check_proof(q, real, c=c, rows=[{"page": 1}]) is None, "الحدُّ الموجود يجب أن يمرّ"


def test_rows_outside_the_chain_are_refused():
    m = _tool()
    c = _Scan([1, 2])
    q = {"id": "x-rows", "derive": {"kind": "count_rows", "page": 1}}
    far = {"kind": "count_rows", "proof": {"rows": [9], "pages": [1]}}
    why = m.check_proof(q, far, c=c, rows=[{"page": 1}, {"page": 2}])
    assert why and "خارج السلسلة" in why, f"صفٌّ خارج السلسلة يجب أن يُسقط، مرّ بـ{why!r}"
    ok = {"kind": "count_rows", "proof": {"rows": [2], "pages": [1]}}
    assert m.check_proof(q, ok, c=c, rows=[{"page": 1}, {"page": 2}]) is None


def test_a_silent_loss_in_a_matching_locus_is_refused():
    """**لا تضيع مطابقةٌ صامتة**: (المُوضَّع + المُعلَن) = المطابقات، وكلُّ مُعلَنٍ بسببه.

    قِيس على الحزمة: `cit-01` أربعُ مطابقات إحداها صفُّ مجموعٍ بلا رصيدٍ مطبوع (الصفحة ٦٢٩) ⇒
    يسقطه `build_rows` ⇒ لا موضعَ له في عالم الصفوف. فالضمُّ الصامت ممنوع، والإعلانُ إلزاميّ.
    """
    m = _tool()
    q = {"id": "x-match", "derive": {"kind": "rows_matching", "pattern": "شيك"}}
    hidden = {"kind": "rows_matching", "hits": 4, "proof": {"rows": [1, 2, 3], "pages": [7], "unmapped": []}}
    why = m.check_proof(q, hidden, c=_Scan([7]), rows=[{"page": 7}] * 4)
    assert why and "لا يغطّي المطابقات" in why, f"الضمُّ الصامت يجب أن يُسقط، مرّ بـ{why!r}"
    declared = {"kind": "rows_matching", "hits": 4, "proof": {"rows": [1, 2, 3], "pages": [7],
                                                             "unmapped": [{"page": 629, "index": 3, "why": "يسقطه build_rows"}]}}
    assert m.check_proof(q, declared, c=_Scan([7]), rows=[{"page": 7}] * 4) is None, "الإعلانُ بالسبب يجب أن يمرّ"
    mute = {"kind": "rows_matching", "hits": 4, "proof": {"rows": [1, 2, 3], "pages": [7],
                                                          "unmapped": [{"page": 629, "index": 3, "why": ""}]}}
    why2 = m.check_proof(q, mute, c=_Scan([7]), rows=[{"page": 7}] * 4)
    assert why2 and "بلا سببٍ مُعلَن" in why2, "إعلانٌ بلا سببٍ ليس إعلانًا"


# ————————————————————— ضابطان على العيّنة (يتخطّيان معلنين بلا بيانات) —————————————————————

def _corpus_ready():
    require_run(RUN)
    # ⇐ و**الحزمةُ المجمَّدة شرطٌ لهذا القسم**: الثلاثةُ التي تقرأ `pack_io.pack_path()` هنا (وواحدٌ يقرأ
    #   صفحاتِها) كانت تسقط بـ`FileNotFoundError` في بيئةٍ فيها العيّنةُ بلا الحزمة (قِيس في مراجعة إغلاق ٦٤)
    #   ⇒ الشرطُ يُعلن الحاجةَ كاملةً: قرصٌ **وحزمة**. (وموضعُ الشرط هنا لا في كلّ فحص: كلُّ مناديه يحتاجها.)
    require_pack()


def test_an_empty_run_dir_is_declared_not_failed(tmp_path):
    """**العطبُ الذي وُلد منه (مقعدُ المعايير · الدفعةُ الثالثة · مقيس):** `mkdir -p …/slice_629p` **فارغًا**
    كان يُمرِّر شرطَ `RUN.exists()` ⇒ ثلاثةُ فحوصٍ سقطت فشلًا عاريًا (`SystemExit: لا نتائج في …` من
    `tools/refusal_test.py:85`). والمقيسُ الآن: المجلّدُ الفارغ **يُعلن التخطّي** بنصٍّ يسمّي ما ينقص.
    """
    empty = tmp_path / "slice_629p"
    empty.mkdir()
    assert not run_is_ready(empty), "مجلّدٌ بلا `results/pg-*.json` ليس عيّنةً جاهزة"
    with pytest.raises(pytest.skip.Exception) as excinfo:
        require_run(empty)
    assert "results/pg-*.json" in str(excinfo.value), "الإعلانُ يسمّي ما ينقص ولا يُخفيه"
    (empty / "results").mkdir()
    (empty / "results" / "pg-001.json").write_text("{}", encoding="utf-8")
    assert run_is_ready(empty), "وبالمحتوى المعلَن تمرّ"


def test_all_fifty_questions_have_a_proof_or_a_declared_exception():
    """**القاعدةُ الحاكمة**: مجموعةُ ما لا إثباتَ له = مجموعةُ الاستثناءات المعلنة بالضبط.
    (فتحةٌ جديدةٌ ⇒ يسقط · استثناءٌ متقادمٌ ⇒ يسقط.)"""
    _corpus_ready()
    m = _tool()
    from tools import pack_io
    from tools.refusal_test import build_rows
    pack = json.loads(pack_io.pack_path().read_text())
    pages = sorted(int(p) for p in (pack.get("page_seal") or {}).get("pages") or {})
    c = m.Corpus(RUN, pages)
    rows, _ = build_rows(RUN)
    hole, stale = [], []
    for q in _questions():
        _, safe = m.truth(q, c, pack, rows)
        st, why_proof = m.classify_proof(q, safe, c, rows)      # **العالمُ الحقيقيّ**: حكمٌ لا يُضعَّف
        if st == "missing":
            hole.append(f"{q['id']}: {why_proof}")
        elif st == "ok" and "متقادم" in why_proof:
            stale.append(q["id"])
    assert not hole, f"أسئلةٌ بلا موضعِ إثباتٍ ولا استثناءَ معلن: {hole}"
    assert not stale, f"استثناءاتٌ متقادمة تُزال: {stale}"
    assert len(_questions()) == 50, "الحزمةُ ٥٠ سؤالًا"


def test_the_validate_gate_passes_end_to_end():
    """البوّابةُ نفسها (`--validate`) — لا الدالّةَ وحدها: تُشغَّل ويُقاس رمزُ خروجها."""
    _corpus_ready()
    r = subprocess.run([sys.executable, str(ROOT / "tools/eval_questions.py"), "--validate"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"بوّابةُ الإثبات حمراء:\n{r.stdout[-800:]}"
    assert "abs-02" in r.stdout, "الاستثناءُ المُعلَن يجب أن يُطبع باسمه لا أن يُصمت"


def _measured():
    """الخمسون مُشتقّةً من القرص مرّةً واحدة — للأضابيط التي تقيس المواضع نفسها."""
    m = _tool()
    from tools import pack_io
    from tools.refusal_test import build_rows
    pack = json.loads(pack_io.pack_path().read_text())
    pages = sorted(int(p) for p in (pack.get("page_seal") or {}).get("pages") or {})
    c = m.Corpus(RUN, pages)
    rows, _ = build_rows(RUN)
    return m, c, pack, rows


def test_every_locus_lies_inside_the_scan_and_the_chain():
    """**كلُّ موضعٍ يقع فعلًا**: صفحاتُه في نطاق الفحص وصفوفُه في السلسلة — الخمسون كلُّها.

    هذا هو الضابطُ الذي كان غائبًا: `[700, 701]` لسؤالٍ عن صفحة ٧٠٠ (والكشفُ ٦٢٩) مرّت لأنّ
    `check_proof` لا يسأل إلا «غيرُ فارغ». الإرجاعُ إلى `[page, page + 1]` يُسقط هذا الضابط.
    """
    _corpus_ready()
    m, c, pack, rows = _measured()
    scope = set(c.corpus_page_list())          # **نطاق الفحص** (اسمٌ واحد بعد توحيده)
    stray = []
    for q in _questions():
        _, safe = m.truth(q, c, pack, rows)
        pr = safe.get("proof") or {}
        out_p = [p for p in pr.get("pages") or [] if p not in scope]
        out_r = [r for r in pr.get("rows") or [] if not 1 <= r <= len(rows)]
        if out_p or out_r:
            stray.append((q["id"], out_p[:3], out_r[:3]))
    assert not stray, f"مواضعُ إثباتٍ لا تقع فيما تشير إليه: {stray}"


def test_the_matching_locus_is_the_matching_rows_themselves():
    """**الموضعُ = الصفوفُ المطابِقة** (لا كلُّ صفوفِ صفحاتها)، وكلُّ مطابقةٍ إمّا مُوضَّعة أو مُعلَنة.

    قِيس قبل الإصلاح: `cit-01` موضعُه ٢٥ صفًّا لأربع مطابقات، و`cit-02` ٨٥٩ صفًّا لـ١٦٠.
    وبعد الإصلاح: `cit-02` ١٦٠ صفًّا بالضبط، و`cit-01` ٣ مُوضَّعة + ١ مُعلَنة (صفُّ مجموعٍ على الصفحة
    ٦٢٩ يسقطه `build_rows`) — فالمجموعُ يساوي المطابقات بلا ضمٍّ صامت.
    """
    _corpus_ready()
    m, c, pack, rows = _measured()
    seen = 0
    for q, pat in ((q, q["derive"]["pattern"]) for q in _questions() if q["derive"]["kind"] == "rows_matching"):
        hits, safe = m.truth(q, c, pack, rows)
        pr = safe["proof"]
        assert len(pr["rows"]) + len(pr["unmapped"]) == safe["hits"], \
            f"{q['id']}: موضعٌ لا يغطّي المطابقات ({len(pr['rows'])} + {len(pr['unmapped'])} من {safe['hits']})"
        assert len(pr["rows"]) <= safe["hits"], f"{q['id']}: فائضٌ في الصفوف"
        for n in pr["rows"]:
            assert rows[n - 1].get("page") in pr["pages"], f"{q['id']}: صفُّ موضعٍ في صفحةٍ غيرِ مستشهدة"
            assert pat in str(rows[n - 1].get("desc") or ""), f"{q['id']}: صفُّ موضعٍ لا يحمل النمط"
        for u in pr["unmapped"]:
            assert u.get("why"), f"{q['id']}: مطابقةٌ غيرُ مُوضَّعة بلا سبب"
        seen += 1
    assert seen >= 1, "لا سؤالَ مطابقةٍ في الحزمة — الضابطُ بلا مجتمع"

# ————————————— الموضعُ يحمل **هويةَ** ما طُوبق عليه لا موضعًا فقط —————————————
# (مراجعة ٥٢ · مقعدا المعايير والبنية): شرطُ `i < len(chain)` كان يقيس **وجودَ فهرس** لا **هويةَ صفّ**،
# وإسقاطُ صفٍّ من وسط صفحةٍ يُزيح ما بعده ⇒ استشهادٌ بصفٍّ **آخرَ** يبدو كاملًا. وهذا أسوأُ أشكال الخطأ هنا.

def test_a_shifted_match_is_declared_not_cited():
    """**الإزاحةُ تُعلَن**: صفُّ السلسلة عند الموضع لا يحمل نصَّ المطابقة ⇒ `unmapped`، لا استشهادٌ خاطئ."""
    m = _tool()
    rows = [{"page": 1, "desc": "صفٌّ آخر تمامًا"}]                 # السلسلةُ أزاحت المطابقة
    c = _Scan([1], raw={1: [{"desc": "الايداعات بشيكات", "balance": "12.34"}]})
    ids, unmapped = m._match_row_ids(rows, [(1, 0)], c, "الايداعات بشيكات")
    assert ids == [] and len(unmapped) == 1, f"إزاحةٌ يجب أن تُعلَن: ids={ids} unmapped={unmapped}"
    assert "إزاحة" in unmapped[0]["why"]
    rows_ok = [{"page": 1, "desc": "الايداعات بشيكات"}]            # **الضابطُ الموجب**
    ids2, unm2 = m._match_row_ids(rows_ok, [(1, 0)], c, "الايداعات بشيكات")
    assert ids2 == [1] and unm2 == [], "الصفُّ الذي يحمل النصَّ يُوضع فعّالًا بلا إعلان"


def test_the_unmapped_reason_is_measured_not_presumed():
    """**السببُ يُقاس لا يُفترض** (مقعدُ المعايير): الرصيدُ الغائبُ يُسمّى من الصفحة نفسها لا من الفرض."""
    m = _tool()
    rows = [{"page": 1, "desc": "س"}]
    c = _Scan([1], raw={1: [{"desc": "مطابقة", "balance": None} for _ in range(4)]})
    _, unm = m._match_row_ids(rows, [(1, 3)], c, "مطابقة")
    assert unm and "بلا رصيدٍ مطبوع" in unm[0]["why"], unm
    # وصفٌّ **له رصيدٌ مطبوع** لكن لا مقابلَ له في السلسلة ⇒ لا يُنسب إلى الرصيد (السببُ يُقاس لكلّ صفّ)
    rows2 = [{"page": 1, "desc": "س"}]
    c2 = _Scan([1], raw={1: [{"desc": "مطابقة", "balance": "12.34"} for _ in range(4)]})
    _, unm2 = m._match_row_ids(rows2, [(1, 3)], c2, "مطابقة")
    assert unm2 and "بلا رصيدٍ مطبوع" not in unm2[0]["why"], f"السببُ مُفترَضٌ لا مقيس: {unm2}"
    # وصفٌّ بلا مقابلٍ ولا رصيدَ غائب (فهرسٌ أطولُ من الصفحة) ⇒ سببٌ آخرُ مُعلَن لا تخمين
    _, unm2 = m._match_row_ids(rows, [(1, 9)], c, "مطابقة")
    assert unm2 and "لا صفَّ له في السلسلة" in unm2[0]["why"], unm2


def test_the_boundary_witness_points_at_the_page_the_claim_measures():
    """**الشاهدُ على الدعوى** (مقعدُ البنية): دعوى `boundary` تقيس `page + 1` ⇒ الموضعُ يشير إليها لا إلى `page`."""
    m = _tool()
    c = _Scan([1, 2, 3])
    assert m._absent_pages(c, {"reason": "boundary", "page": 1}) == [2], "الداخلُ يُشهَد بذاته"
    assert m._absent_pages(c, {"reason": "boundary", "page": 3}) == [3], "وحدُّ الكشف يُشهَد بآخرِ صفحة"
    assert m._absent_pages(c, {"reason": "page_outside_pack", "page": 700}) == [3]
