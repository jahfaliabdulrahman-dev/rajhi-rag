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
    assert m.check_proof(q, empty), "قاعدةُ rows يجب أن تسقط بلا صفوف"
    assert m.check_proof(q, filled) is None, "وبصفوفٍ يجب أن تمرّ"
    assert m.check_proof({"id": "x-02", "derive": {"kind": "نوعٌ مستجدّ"}}, {"proof": {"rows": [1]}}), \
        "نوعٌ بلا قاعدةٍ يجب أن يسقط"
    assert m.check_proof({"id": "x-03", "derive": {"kind": "footer"}},
                         {"proof": {"rows": [], "pages": []}}), "قاعدةُ pages تسقط بلا صفحات"


def test_a_stale_exception_is_exposed_not_hidden():
    """استثناءٌ صار له إثباتٌ ⇒ **يُعلَن ليُزال** (وإلا صارت القائمةُ غطاءً دائمًا)."""
    m = _tool()
    qid = sorted(m.PROOF_EXCEPTIONS)[0]
    rows_ok = {"kind": "count_rows", "proof": {"rows": [5]}}
    st, why = m.classify_proof({"id": qid, "derive": {"kind": "count_rows"}}, rows_ok)
    assert st == "ok" and "متقادم" in why, "يجب كشفُ الاستثناء المتقادم"
    st2, _ = m.classify_proof({"id": qid, "derive": {"kind": "count_rows"}}, {"proof": {"rows": []}})
    assert st2 == "exception", "الاستثناءُ المُعلَن يُصنَّف استثناءً لا مكسورًا"
    st3, why3 = m.classify_proof({"id": "not-declared", "derive": {"kind": "count_rows"}}, {"proof": {"rows": []}})
    assert st3 == "missing" and why3, "بلا استثناءٍ ⇒ مكسور"


# ————————————————————— ضابطان على العيّنة (يتخطّيان معلنين بلا بيانات) —————————————————————

def _corpus_ready():
    if not RUN.exists():
        pytest.skip(f"العيّنةُ غير موجودة ({RUN}) — لا يُقاس الإثباتُ بلا قرص")


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
        st, why = m.classify_proof(q, safe)
        if st == "missing":
            hole.append(f"{q['id']}: {why}")
        elif st == "ok" and "متقادم" in why:
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
