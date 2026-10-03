"""بوّاباتُ واجهة الدفتر (`statement_qa.ledger_ui`) — المنطقُ الذي تراه الشاشة، يُقاس بلا شاشة.

**العِلّة في وجود هذا الملفّ:** واجهةُ الشاشة تحتاج: بناءً من حالة التطبيق، ونصَّ حالة، وصياغةَ جواب،
ورفضًا مسمّى. ولو عاشت هذه في `app.py` لكانت **منطقًا لا يُقاس إلّا بتشغيل التطبيق** — وهو بعينه
صنفُ العطب الذي أمسكه مقعدُ الترتيب (قياسُ المسار الواحد). فالقاعدةُ المُنفَّذة: **ما يُقاس بلا شاشةٍ
يُخرَج من الشاشة**، وما بقي في `app.py` توصيلٌ رقيقٌ لا منطق.

**والبوّابةُ الأهمّ:** «بلا كلفة» دعوى في الواجهة ⇒ تُقاس **بفخّ شبكةٍ مُصاد**: يُمنع الاتصالُ الصادرُ
كلُّه، فتمرّ الأقصدُ الستّة. فإن جرى نداءُ نموذجٍ واحدٌ في هذا المسار، يسقط الضابط.
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


def _built(tmp_path: Path, rows=None, footers=None) -> Path:
    """دفترٌ مبنيٌّ كما تبنيه الشاشةُ: من حالة التطبيق لا من `to_xlsx`."""
    rows = rows if rows is not None else _rows()
    footers = footers if footers is not None else {1: {"verdict": "ok"}, 2: {"verdict": "gap"}}
    db = U.ledger_file(tmp_path, L.pages_of(rows))
    conn = L.open_ledger(db)
    L.ingest(conn, rows, L.pages_from_state(rows, footers))
    conn.close()
    return db


def test_every_label_maps_to_a_declared_intent():
    """**القائمةُ المغلقةُ في الشاشة هي القائمةُ المغلقةُ في الوحدة** — لا اسمَ حرٌّ ثالث."""
    assert set(U.INTENT_LABELS.values()) == set(L.INTENTS), sorted(U.INTENT_LABELS.values())
    assert len(U.INTENT_LABELS) == 6, "ستّةُ أقصدٍ في الشاشة كما في الوحدة"
    assert set(U.NEEDS_VALUE) <= set(L.INTENTS)


def test_the_screen_build_agrees_with_the_tool_build(tmp_path):
    """**مسرَبان لبناء الدفتر ⇒ ضابطٌ يقابل بينهما** (وإلّا افترقا صامتين):

    (أ) من `tools/to_xlsx.load` + `per_page` — مسارُ الأداة. (ب) من **حالة التطبيق** (صفوفٌ + أحكامُ
    صفحات) عبر `pages_from_state`. والقياس: نفسُ الصفوف، ونفسُ أحكام الصفحات وعددِ صفوفها.
    **وحدٌّ يُعلَن:** كلفةُ الصفحة تُملأ في (أ) ولا تُملأ في (ب) — حالةُ التطبيق كلفتُها كلّيّةٌ لا
    لكلّ صفحة، ولا يُوزَّع رقمٌ بالتخمين؛ فالضابطُ يقابل على ما يُقابَل، ويُعلن ما لا يُقابَل.
    """
    db_a, db_b = tmp_path / "a.sqlite", tmp_path / "b.sqlite"   # مساران مختلفان للمقابلة
    if (RUN / "results").exists():
        import to_xlsx                              # noqa: PLC0415

        rows, _report, per_page, _flags = to_xlsx.load(RUN)
        conn = L.open_ledger(db_a)
        L.ingest(conn, rows, per_page)
        conn.close()
        footers = {int(pg): {"verdict": (e or {}).get("footer")} for pg, e in per_page.items()}
        conn = L.open_ledger(db_b)
        L.ingest(conn, rows, L.pages_from_state(rows, footers))
        conn.close()
    else:                                           # بلا بيانات: القياسُ على الصفوف الاصطناعيّة
        rows = _rows()
        conn = L.open_ledger(db_a)
        L.ingest(conn, rows, L.pages_from_state(rows, {1: {"verdict": "ok"}, 2: {"verdict": "gap"}}))
        conn.close()
        conn = L.open_ledger(db_b)
        L.ingest(conn, rows, L.pages_from_state(rows, {1: {"verdict": "ok"}, 2: {"verdict": "gap"}}))
        conn.close()

    a, b = L.read_ledger(db_a), L.read_ledger(db_b)
    try:
        assert L.read_rows(a) == L.read_rows(b), "الصفوفُ افترقت بين المسارين"
        ca = {r["pg"]: (r["verdict"], r["rows_count"]) for r in
              a.execute("SELECT pg, verdict, rows_count FROM pages")}
        cb = {r["pg"]: (r["verdict"], r["rows_count"]) for r in
              b.execute("SELECT pg, verdict, rows_count FROM pages")}
        # **الأحكامُ تتطابق، والفرقُ في العدّ يُفسَّر بالمعادلة لا بالتسامح** (قاسه الضابط أوّلًا:
        # 17 صفًّا بلا حقل صفحةٍ في المصدر — فالمسارُ (ب) لا ينسبها ولا يخترع لها صفحة).
        assert {k: v[0] for k, v in ca.items()} == {k: v[0] for k, v in cb.items()}, "الأحكامُ افترقت"
        deficit = sum(ca[k][1] - cb.get(k, ("", 0))[1] for k in ca)
        assert deficit == L.rows_without_page(rows), (
            f"فرقُ العدّ ({deficit}) لا يفسّره عددُ الصفوف بلا صفحة ({L.rows_without_page(rows)})")
        cost_a = [r[0] for r in a.execute("SELECT cost_usd FROM pages WHERE cost_usd IS NOT NULL")]
        cost_b = [r[0] for r in b.execute("SELECT cost_usd FROM pages WHERE cost_usd IS NOT NULL")]
        assert cost_b == [], "كلفةُ الصفحة مُلئت من حالة التطبيق ⇒ رقمٌ مُوزَّعٌ بالتخمين"
        assert L.pages_of(rows) <= len(ca)
        print(f"  [المساران] صفحات: {len(ca)} · صفوف: {len(L.read_rows(a))} · "
              f"كلفةٌ في مسار الأداة: {len(cost_a)}")
    finally:
        a.close()
        b.close()


def test_the_ledger_answers_with_the_network_booby_trapped(tmp_path, monkeypatch):
    """**«بلا نموذج وبلا كلفة» تُقاس بفخّ شبكة** — لا بنصٍّ في الشاشة.

    يُمنع الاتصالُ الصادرُ من جذره (`socket.create_connection`) ⇒ فإن مرّت الأقصدُ الستّة، فالمسارُ
    SQL وحدَه بالبرهان؛ وإن جرى نداءُ نموذجٍ واحد، يسقط الضابطُ بـ`RuntimeError` من الفخّ نفسه.
    """
    def _refuse(*a, **k):
        raise AssertionError("محاولةُ اتصالٍ شبكيّ من مسار الدفتر — وهو يُعلن أنّه بلا كلفة")

    monkeypatch.setattr(socket, "create_connection", _refuse)
    db = _built(tmp_path)
    conn = L.read_ledger(db)
    try:
        for intent in L.INTENTS:
            got = L.answer(conn, intent, q="حوالة" if intent == "search" else None,
                           pg=1 if intent == "pages" else None)
            assert got["intent"] == intent
    finally:
        conn.close()


def test_a_missing_or_unreadable_ledger_shows_a_named_message(tmp_path):
    """**الشاشةُ لا تعرض traceback**: غائبٌ ⇒ رسالةُ بناءٍ مسمّاة؛ وقصدٌ بغير القائمة ⇒ رفضٌ بالاسم؛
    وقيمةٌ ناقصةٌ لقصدٍ يحتاجها ⇒ طلبٌ صريح. (وهذا هو عقدُ الوحدة نفسُه، مُقاسًا من باب الشاشة.)
    """
    ghost = U.ask(tmp_path, 10, "المجاميع (مدين/دائن)")
    assert "تعذّر فتحُ الدفتر" in ghost and "ابنِ دفترَ الكشف" in ghost
    _built(tmp_path)                                     # باسم الملفّ الذي تطلبه الشاشة
    status = U.status_text(tmp_path, 2, 3)
    assert "مبنيٌّ وجاهز" in status and "تعذّر" not in status, status
    out = U.ask(tmp_path, 2, "قصدٌ مُخترَع")
    assert "قصدٌ غيرُ مُعدَّد" in out and "المجاميع" in out
    assert "يحتاج رقمَ الصفحة" in U.ask(tmp_path, 2, "أحكامُ الصفحات")
    assert "يحتاج نصَّ البحث" in U.ask(tmp_path, 2, "بحثٌ في البيان", "   ")
    assert "ليس رقمَ صفحة" in U.ask(tmp_path, 2, "أحكامُ الصفحات", "كذا")
    # والمسارُ: داخل مجلّدٍ مُهمَلٍ تحت data/ وباسمٍ يميّز الكشف
    f = U.ledger_file(tmp_path, 2)
    assert f.name == "ui_2p.sqlite" and str(f.parent).endswith("data/ledgers"), f


def test_the_answers_render_as_arabic_marks(tmp_path):
    """الجوابُ يُصاغ **جدولًا يُقرأ في ثوانٍ**، وكلُّ رقمٍ مع عدّاده — لا نصًّا سائلًا."""
    db = _built(tmp_path)
    assert db.exists()
    for label, needle in (("المجاميع (مدين/دائن)", "| المجموع المدين |"),
                          ("تغطيةُ الكشف (صفوف · صفحات · بلا إثبات)", "صفًّا"),
                          ("الصفوفُ بلا إثبات", "بلا إثبات"),
                          ("أحكامُ الصفحات", "| صفحة | مطبوع |"),
                          ("بحثٌ في البيان", "حوالة")):
        got = U.ask(tmp_path, 2, label, "2" if "أحكام" in label else "حوالة")
        assert needle in got, (label, got[:200])
    assert U.ask(tmp_path, 2, "أحكامُ الصفحات", "٢")        # أرقامٌ عربية تُقبل
    assert "لا صفحةَ بهذا الرقم" in U.ask(tmp_path, 2, "أحكامُ الصفحات", "99")
