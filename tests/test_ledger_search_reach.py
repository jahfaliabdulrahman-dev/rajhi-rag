"""بوّابةُ **مدى البحث** في الدفتر: تُقاس على «الخمسين سؤالًا» الحقيقيّة — بلا عتبةٍ مُختلقة.

**سؤالُ الخارطة (أ-٣):** «FTS5 يُقاس على الخمسين سؤالًا **قبل** أيّ حذف لـFAISS». فالقياسُ هنا ليس
رأيًا: يُقرأ ملفُّ الأسئلة (`docs/eval_pack/questions.json`)، ويُبنى الدفترُ من نتائج تشغيلِ المالك،
ويُسأل كلُّ سؤالٍ بكلماتِه — ويُعدّ: كم سؤالًا يعود بشاهدٍ واحدٍ على الأقل، وكم منها يعود **بالصفحة
الصحيحة** (حين يحدّد السؤالُ صفحتَه). **ولا تُدَّعى عتبةُ نجاحٍ لم يفرضها المالك**: العددُ يُطبع
ويُسلَّم، والقرارُ في حذف FAISS يبقى له — أمّا ما يُنفى هنا فهو **الدعوى** أنّ FTS5 وحدَه يُغني عن
الاسترجاع الدلاليّ لأسئلةٍ بنيويّة.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import ledger as L            # noqa: E402

QUESTIONS = ROOT / "docs" / "eval_pack" / "questions.json"
RUN = ROOT / "data" / "local_sample" / "slice_629p_v2"
_STOP = {"ما", "في", "من", "على", "عن", "هو", "هل", "كم", "التي", "الذي", "إلى", "مع", "خانة",
         "الصفحة", "كشف", "الحساب", "رقم", "أي", "ثم", "أو", "و", "أن"}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"\w+", text) if len(w) >= 3 and w not in _STOP]


def test_what_lexical_search_reaches_on_the_fifty_questions(tmp_path):
    if not (RUN / "results").exists():
        pytest.skip("لا بياناتُ المالك هنا — القياسُ يجري حيث يوجد الكشف")
    assert QUESTIONS.exists(), f"ملفُّ الأسئلة غائب: {QUESTIONS}"
    doc = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    pack = doc["questions"] if isinstance(doc, dict) else doc      # الملفُّ قاموسٌ بمفتاح questions
    assert len(pack) == 50, f"العقدُ يقول خمسون سؤالًا — وُجد {len(pack)}"

    import to_xlsx                              # noqa: PLC0415

    rows, _report, per_page, _flags = to_xlsx.load(RUN)
    conn = L.open_ledger(tmp_path / "reach.sqlite")
    L.ingest(conn, rows, per_page)

    hits, page_hits, no_page, empty_q = 0, 0, 0, []
    for q in pack:
        words = _words(q["q"])
        got = L.search(conn, " OR ".join(words), limit=50) if words else []
        if got:
            hits += 1
        else:
            empty_q.append(q["id"])
        want_pg = (q.get("derive") or {}).get("page")
        if want_pg is None:
            no_page += 1
        elif any(r["pg"] == want_pg for r in got):
            page_hits += 1
    scored = len(pack) - no_page
    print(f"  [FTS5 على الخمسين] بشاهدٍ واحدٍ على الأقلّ: {hits}/{len(pack)}"
          f" · بالصفحة الصحيحة: {page_hits}/{scored} (والأسئلةُ التي تحدّد صفحةً: {scored})"
          f" · بلا شاهد: {len(empty_q)}")
    assert len(empty_q) + hits == len(pack)
    assert hits >= 0 and page_hits >= 0        # القياسُ يُسلَّم كما هو — لا عتبةَ مُختلقة
    conn.close()
