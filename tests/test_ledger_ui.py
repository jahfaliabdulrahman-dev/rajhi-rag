"""قاعدةُ الكشف في جلسة التطبيق (`statement_qa.ledger_ui` ومسارُ `ledger`) — تُقاس بلا شاشة.

كان هذا الملفُّ يقيس لوحةَ «دفترُ الكشف — أسئلةٌ بلا نموذج وبلا كلفة» (أقصدُها وجداولُها وزرُّ إعادة البناء).
**وأُزيلت اللوحةُ بقرار المالك (2026-10-31)**، فأُزيلت ضوابطُها معها، **وبقيت هنا خصائصُ القاعدة نفسِها**
التي كانت تُقاس عبر اللوحة: مصدرا البناء يتّفقان، والقاعدةُ تُجيب بلا شبكة (أدواتُ الوكيل وسطرُ الأوامر يسألانها
بأقصدها الثابتة)، والمفتاحُ من بصمة الكشف، والصفُّ بلا صفحةٍ يُستبعَد ويُعدّ ثمّ يُعلَن في سطر الحالة.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from statement_qa import ledger as L            # noqa: E402
from statement_qa import ledger_ui as U         # noqa: E402

RUN = ROOT / "data" / "local_sample" / "slice_629p_v2"


def _rows() -> list[dict]:
    return [
        {"page": 1, "row_no": 1, "printed_page": 1, "movement": "10.00", "side": "debit",
         "balance": "10.00", "printed_movement": "10.00", "printed_balance": "10.00",
         "desc": "بدايةٌ", "opening": True, "chain_ok": True, "counted": 1},
        {"page": 1, "row_no": 2, "printed_page": 1, "movement": "15.00", "side": "credit",
         "balance": "25.00", "printed_movement": "15.00", "printed_balance": "25.00",
         "desc": "حوالةٌ صادرة", "opening": False, "chain_ok": True, "counted": 1},
        {"page": 2, "row_no": 1, "printed_page": 2, "movement": None, "side": "credit",
         "balance": "25.00", "printed_movement": None, "printed_balance": "25.00",
         "desc": "رسوم حوالة", "opening": False, "chain_ok": False, "counted": 1},
    ]


def _built(tmp_path: Path, rows=None, footers=None, key: str | None = None) -> Path:
    """دفترٌ مبنيٌّ كما تبنيه الشاشةُ: من حالة التطبيق لا من `to_xlsx`."""
    rows = rows if rows is not None else _rows()
    footers = footers if footers is not None else {1: {"verdict": "ok"}, 2: {"verdict": "gap"}}
    db = U.ledger_file(tmp_path, key or L.statement_key("t-1"))
    conn = L.open_ledger(db)
    L.ingest(conn, rows, L.pages_from_state(rows, footers))
    conn.close()
    return db


def test_the_state_source_agrees_with_the_run_source(tmp_path):
    """**مقابلةُ المصدرَين — لا استدعاءَين لنفس الدالّة** (طعنَ فيه مقعدُ الواجهة وكان محقًّا · مُثبت):

    النسخةُ الأولى قابَلت مسارَين **كلاهما يستدعي `L.ingest` نفسَه**، وقد صار يشتقّ العدّ من الصفوف ⇒
    `ca == cb` دائمًا ⇒ **بوّابةٌ لا تستطيع السقوط**. فالصوابُ مقابلةُ **المصدرين**:
    `pages_from_state` (اشتقاقُنا من الصفوف) مقابل `to_xlsx.load`'s `per_page` (عدّادُ التشغيل) —
    والعلاقةُ المُعلَنة: **يختلفان حيث حكمُ الصفحة ليس `ok`** (قِيس: `per_page[629] = {rows: 0,
    footer: 'absent}` مقابل 17 صفًّا تحمل `page=629`) ⇒ فكلُّ خلافٍ **يُفسَّره حكمُ الصفحة**، وما لا
    يفسّره يسقط الضابط.
    """
    if not (RUN / "results").exists():
        # **والحدُّ مُعلَن:** بلا بيانات المالك يُقاس الشكلُ فقط (صفوفٌ اصطناعيّة)، ويُقال ذلك في الاسم.
        rows = _rows()
        got = L.pages_from_state(rows, {1: {"verdict": "ok"}, 2: {"verdict": "gap"}})
        assert got[1]["rows"] == 2 and got[2]["rows"] == 1 and got[1]["page_no"] == 1
        return
    import to_xlsx                                  # noqa: PLC0415

    rows, _report, per_page, _flags = to_xlsx.load(RUN)
    state = L.pages_from_state(rows, {int(pg): {"verdict": (e or {}).get("footer")}
                                      for pg, e in per_page.items()})
    # (أ) اشتقاقُنا يُطابق العدَّ الفعليَّ للصفوف — يقابل مصدرًا مستقلًّا (الصفوف نفسُها)
    for pg, e in state.items():
        assert e["rows"] == sum(1 for r in rows if r.get("page") == pg), pg
    # (ب) وكلُّ خلافٍ مع عدّاد التشغيل يُفسّره حكمُ الصفحة (وإلّا فهو عطبٌ غيرُ مفسَّر)
    unexplained = []
    for pg, run_entry in per_page.items():
        pg = int(pg)
        run_rows = int((run_entry or {}).get("rows") or 0)
        here = state.get(pg, {}).get("rows", 0)
        verdict = str((run_entry or {}).get("footer") or "unchecked")
        if run_rows != here and verdict == "ok":
            unexplained.append((pg, run_rows, here, verdict))
    assert not unexplained, f"خلافٌ في العدّ بلا حكمٍ يفسّره: {unexplained[:5]}"
    # (ج) والصفوفُ بلا صفحة **صفرٌ في المصدر** — فالدعوى السابقة كانت زائفة، ويُقاس الآن
    assert L.rows_without_page(rows) == 0, "ظهرت صفوفٌ بلا صفحة ⇒ يُعلَن عددُها في الشاشة"
    print(f"  [المصدران] صفحات الحالة: {len(state)} · صفحاتُ التشغيل: {len(per_page)} · "
          f"صفوفٌ: {len(rows)} · خلافاتٌ مُفسَّرةٌ بالأحكام: "
          f"{sum(1 for pg, e in per_page.items() if int((e or {}).get('rows') or 0) != state.get(int(pg), {}).get('rows', 0))}")


def test_the_ledger_answers_with_the_network_booby_trapped(tmp_path, monkeypatch):
    """**«بلا نموذج وبلا كلفة» تُقاس بفخّ شبكةٍ مُسلَّح — ويُثبَت أنّه يمسك** (مقعدُ الواجهة P2 · مُثبت):

    النسخةُ الأولى اعترضت `socket.create_connection` وحدَه: قِيس أنّ `requests.get` **يمرّ بلا**
    اعتراض (urllib3 يبني اتصالَه بنفسه). فالفخُّ الآن على أربعة منافذ (`create_connection` ·
    `socket.connect` · `connect_ex` · `getaddrinfo`)، ويُمرَّر من **المداخل الباقية** (الكتابةُ من حالةٍ كما
    يكتب مسارُ القراءة، ثمّ كلُّ قصدٍ ثابت تسأل به أدواتُ الوكيل وسطرُ الأوامر؛ وكانت أزرارُ اللوحة قبل إزالتها).
    **وحدُّه يُعلَن:** يثبت غيابَ DNS/Socket في
    هذا المسار، ولا يثبت غيابَ نقلٍ لا يمرّ بها (كتابةٌ على واصفٍ مفتوحٍ سابقًا).
    """
    def _refuse(*a, **k):
        raise AssertionError("اتصالٌ شبكيّ من مسار الدفتر — وهو يُعلن أنّه بلا كلفة")

    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, _refuse)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, _refuse)

    # (أ) **الفخُّ مُسلَّح**: محاولةٌ مُتعمَّدة تُلتقَط — وإلّا فالضابطُ يُثبت لا شيء
    import pytest as _pytest                         # noqa: PLC0415
    with _pytest.raises(AssertionError):
        socket.getaddrinfo("example.com", 443)
    with _pytest.raises(AssertionError):
        socket.socket().connect(("example.com", 443))

    # (ب) والمداخلُ الباقيةُ كلُّها تمرّ: بناءٌ من حالةٍ (كما يكتب مسارُ القراءة)، ثمّ كلُّ قصدٍ ثابت
    db = _built(tmp_path, key=L.statement_key("x-1"))
    conn = L.read_ledger(db)
    try:
        for intent in L.INTENTS:
            got = L.answer(conn, intent, pg=1 if intent == "pages" else None,
                           q="حوالة" if intent == "search" else None)
            assert got["intent"] == intent, got
    finally:
        conn.close()


def test_the_ledger_key_identifies_the_statement_not_its_page_count(tmp_path):
    """**مقعدُ الواجهة P3 · مُثبت:** كان الاسمُ بعدد الصفحات ⇒ كشفان بـ629 صفحة **يتصادمان**،
    و`pages_of(rows)=626` كان يُسمّي الملفَّ `ui_626p` وهو يخزّن 629 صفحةً. والمفتاحُ الآن من
    بصمة المحتوى ⇒ الكشفُ نفسُه مفتاحُه نفسُه، وكشفٌ آخرُ لا يُصادمه؛ وبلا بصمةٍ يُعلَن النقصُ في الاسم.
    **والسابقةُ `st_` لا `ui_` (R130):** المفتاحُ صار مشتركًا مع سطر الأوامر، فاسمُ «واجهة» يكذب.
    """
    a = L.statement_key("sha-a")
    b = L.statement_key("sha-b")
    assert a != b, "مصدران مختلفان بمفتاحٍ واحد ⇒ تصادم"
    assert L.statement_key("sha-a") == a, "المصدرُ نفسُه تغيّر مفتاحُه"
    # **وبلا هويّةٍ لا مفتاح (R132-2):** لا تُصنَع `st_nop-<N>p` من عدد الصفحات.
    import pytest as _pytest                         # noqa: PLC0415

    with _pytest.raises(ValueError):
        L.statement_key("")


def test_a_row_without_a_page_is_dropped_and_declared(tmp_path):
    """**مقعدُ الواجهة P1 · مُثبت:** نصُّ «تُبقى صفوفًا في الدفتر» كان **يستحيل** (`pg INTEGER
    PRIMARY KEY`) ⇒ ينهار قبل أن يُعلن. فالصواب: تُستبعَد وتُعدّ وتُعلَن — والعددُ يُقاس هنا.
    """
    rows = [*_rows(), {"page": None, "row_no": 9, "desc": "بلا صفحة", "movement": None,
                       "side": "debit", "balance": None, "printed_balance": None,
                       "printed_movement": None, "printed_page": None, "opening": False,
                       "chain_ok": True, "counted": 1}]
    assert L.rows_without_page(rows) == 1
    db = tmp_path / "drop.sqlite"
    conn = L.open_ledger(db)
    got = L.ingest(conn, rows, L.pages_from_state(rows, {1: {"verdict": "ok"}, 2: {"verdict": "gap"}}))
    n = conn.execute("SELECT COUNT(*) FROM rows_verified").fetchone()[0]
    conn.close()
    assert got["dropped_no_page"] == 1, got
    assert n == len(rows) - 1, f"الصفُّ بلا صفحة دخل الدفترَ ({n} مقابل {len(rows) - 1})"
    # **ويُعلَن في سطر الحالة** (كان يُعلَن في لوحة الدفتر قبل إزالتها): العددُ نفسُه بنصٍّ يُقرأ.
    import app                                       # noqa: PLC0415

    note = app._ledger_note({"ok": True, "stats": got}, [])
    assert "1 صفًّا بلا حقل صفحةٍ في المصدر" in note, note
    assert "تعذّرت كتابةُ قاعدة الكشف: سبب" in app._ledger_note({"ok": False, "message": "سبب"}, [])
    assert "لم تُقرأ هذه المرّة: ص2" in app._ledger_note({"ok": True, "stats": {}}, [2])
