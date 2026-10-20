"""بوّابةُ ذاكرة المحادثة على `SqliteSaver` (R130 · الخيار ١): تبقى بعد الإغلاق، وتُنزَّل.

**العِلّة المقيسة (مراجعة ١٣٠):** الحافظةُ كانت `MemorySaver` ⇒ المحادثةُ تضيع بإغلاق التطبيق، ولا
ملفَّ يُنزَّل. والآن `langgraph-checkpoint-sqlite.SqliteSaver` والملفُّ هو **قاعدةُ الكشف نفسُها**.
والضوابطُ هنا تقيس ما تنصّ عليه القبولات:

- حوارٌ يُكتب ثمّ **تُغلَق الحافظةُ** (كما عند إعادة التشغيل) ثمّ يُقرأ من ملفّ جديد ⇒ الرسائلُ باقية.
- خيطٌ يُمسح بلا مساسٍ بخيطٍ آخر (`clear_conversation`).
- **ولا `MemorySaver` في الوحدة** — يُقاس بالـAST لا بالوعد.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langgraph.checkpoint.sqlite")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import qa  # noqa: E402


def _texts(thread: str, path: Path) -> list[str]:
    msgs = qa._thread_messages({"configurable": {"thread_id": thread}}, path)
    return [str(getattr(m, "content", "")) for m in msgs]


def test_the_conversation_survives_reopening_the_database(tmp_path):
    """**قبولُ القرار:** «المحادثةُ تُنزَّل بعد إعادة تشغيل التطبيق» — فالرسائلُ على القرص لا في الرام."""
    db = tmp_path / "statement.sqlite"
    qa.remember("st_demo", "كم مجموع السحوبات؟", "المجموع 300.00", memory_path=db)
    assert db.exists(), "لم يُنشأ ملفُّ الحافظة"
    assert any("كم مجموع السحوبات؟" in t for t in _texts("st_demo", db))
    # **إغلاقٌ كإعادة التشغيل:** تُخرج الحافظةُ من الذاكرة ويُفتح المتّصلُ من جديد على الملفّ نفسه.
    assert qa.reset_memory(db)
    got = _texts("st_demo", db)
    assert any("كم مجموع السحوبات؟" in t for t in got), got
    assert any("المجموع 300.00" in t for t in got), got


def test_clearing_one_thread_keeps_the_other(tmp_path):
    db = tmp_path / "statement.sqlite"
    qa.remember("st_a", "سؤال أ", "جواب أ", memory_path=db)
    qa.remember("st_b", "سؤال ب", "جواب ب", memory_path=db)
    qa.clear_conversation("st_a", memory_path=db)
    assert not any("سؤال أ" in t for t in _texts("st_a", db))
    assert any("سؤال ب" in t for t in _texts("st_b", db))


def test_clearing_a_thread_without_a_database_creates_no_file(tmp_path):
    """**لا ملفَّ بلا قاعدة:** `clear_conversation` على مسارٍ غير موجودٍ لا يُنشئ قاعدةً فارغة."""
    ghost = tmp_path / "ghost.sqlite"
    qa.clear_conversation("st_ghost", memory_path=ghost)
    assert not ghost.exists(), "أُنشئ ملفُّ قاعدةٍ من مجرّد مسحِ خيطٍ لا وجودَ له"


def test_the_saver_is_sqlite_and_not_memory_saver():
    """**الثابتُ:** «ذاكرةُ المحادثة بـ`SqliteSaver` بدل `MemorySaver`» — يُقاس بالـAST."""
    tree = ast.parse((ROOT / "src" / "statement_qa" / "qa.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
    assert "langgraph.checkpoint.sqlite" in imported, imported
    assert "langgraph.checkpoint.memory" not in imported, "ما زال يستورد MemorySaver"
