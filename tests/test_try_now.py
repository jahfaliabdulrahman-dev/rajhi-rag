"""«جرّب الآن» (المرحلة ١ · الجزء الثاني) — الكشفُ الاصطناعيّ المقروءُ مسبقًا، بلا مفتاحٍ وبلا كلفة.

**قرارُ المالك (2026-10-30):** «يعيش دفتر «جرّب الآن»: 1 (ملفّ نصّيّ في git يُبنى منه الدفتر)». والضوابطُ
هنا تقيس ما يَعِد به ذلك:

- النصُّ المتتبَّع **قراءةُ الكشف المتتبَّع نفسِه** (بصمةُ بايتاته) — ٥٤ صفًّا وصفٌّ أحمرُ حقيقيٌّ واحد.
- النصُّ ودفترُه **شيءٌ واحد**: يُبنى الدفترُ من النصّ ثمّ يُصدَّر ⇒ النصُّ نفسُه حرفًا بحرف.
- الزرُّ على السطح العامّ **بلا مفتاحٍ وبلا شبكة**: فخُّ شبكةٍ مسلَّح، وحلُّ مفتاح التطبيق ممنوع.
- **لكلّ زائرٍ دفترُه** في مجلّد جلسته (شرطُ (ب) الثالث)، ويُمحى بانتهائها (الثاني).
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("gradio")
pytest.importorskip("langchain")
pytest.importorskip("langgraph.checkpoint.sqlite")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from statement_qa import ledger as L  # noqa: E402
from statement_qa import showcase as SC  # noqa: E402


def test_the_record_is_the_read_of_the_tracked_statement():
    doc = SC.recorded()
    assert doc["source"] == SC.PDF.name
    assert doc["source_sha256"] == L.source_sha256(SC.PDF)
    assert doc["n_pages"] == 5 and len(doc["rows"]) == 54, (doc["n_pages"], len(doc["rows"]))
    assert {f["verdict"] for f in doc["footers"].values()} == {"ok"}, doc["footers"]
    # **الصفُّ الأحمرُ لا يُصنع (SHOWCASE_PLAN ف٢):** قراءةٌ خاطئةٌ واحدةٌ أمسكتها السلسلة في ص٢.
    flagged = [(r["seq"], r["page"]) for r in doc["rows"] if r["chain_ok"] is False]
    assert flagged == [(22, 2)], flagged


def test_a_record_of_other_bytes_is_refused_by_name(tmp_path):
    other = tmp_path / "statement_showcase.pdf"
    other.write_bytes(b"%PDF-1.4 not the statement that was read")
    with pytest.raises(SC.RecordMismatch, match="بصمة"):
        SC.recorded(pdf=other)


def test_the_text_and_its_ledger_are_one_thing(tmp_path):
    """يُبنى الدفترُ من النصّ بمسار الكتابة الواحد ثمّ يُصدَّر ⇒ النصُّ المتتبَّعُ نفسُه حرفًا بحرف.

    فلا عمودَ يضيع في الذهاب والإياب — وهو ما كان يقع لـ`proof_source` قبل إصلاح `read_rows`.
    """
    doc = SC.recorded()
    conn = L.open_ledger(tmp_path / "rebuilt.sqlite")
    try:
        L.ingest(conn, doc["rows"], L.pages_from_state(doc["rows"], doc["footers"]),
                 n_pages=doc["n_pages"])
        again = SC.export(conn, SC.PDF, doc["read_on"])
        unproven = L.answer(conn, "coverage")["unproven"]
    finally:
        conn.close()
    assert SC.dumps(again) == SC.RECORD.read_text(encoding="utf-8")
    assert unproven == sum(1 for r in doc["rows"] if not r["source"]), unproven


def test_the_command_line_exports_the_same_text(tmp_path):
    """الأمرُ الذي يُعيد إنتاجَ النصّ (`tools/ledger.py export`) — ويرفض دفترًا باسم كشفٍ آخر."""
    import ledger as cli

    doc = SC.recorded()
    db = tmp_path / f"{L.statement_key(doc['source_sha256'])}.sqlite"
    conn = L.open_ledger(db)
    try:
        L.ingest(conn, doc["rows"], L.pages_from_state(doc["rows"], doc["footers"]),
                 n_pages=doc["n_pages"])
    finally:
        conn.close()
    out = tmp_path / "out.json"
    assert cli.main(["export", "--db", str(db), "--source", str(SC.PDF),
                     "--read-on", doc["read_on"], "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == SC.RECORD.read_text(encoding="utf-8")

    wrong = db.with_name("st_another.sqlite")
    db.rename(wrong)
    assert cli.main(["export", "--db", str(wrong), "--source", str(SC.PDF),
                     "--read-on", doc["read_on"], "--out", str(tmp_path / "no.json")]) == 2
    assert not (tmp_path / "no.json").exists()


# ————— الزرّ في التطبيق —————

@pytest.fixture
def public(monkeypatch, tmp_path):
    """التطبيقُ على السطح العامّ والشبكةُ مسلَّحةٌ بفخّ، وحلُّ مفتاح التطبيق ممنوع."""
    import app
    from statement_qa import api_key as _api_key_mod

    def _refuse(*_a, **_k):
        raise AssertionError("اتصالٌ شبكيّ من «جرّب الآن» — وهو يَعِد بلا كلفة")

    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, _refuse)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, _refuse)
    with pytest.raises(AssertionError):                 # الفخُّ مسلَّح فعلًا
        socket.getaddrinfo("openrouter.ai", 443)

    def _no_app_key(*_a, **_k):
        raise AssertionError("حُلَّ مفتاحُ التطبيق في «جرّب الآن»")

    monkeypatch.setattr(_api_key_mod, "get_api_key", _no_app_key)
    monkeypatch.setattr(app, "SURFACE", "public")
    # الصورُ تُرسم بـpoppler (محلّيٌّ بلا شبكة، ومسارُ القراءة نفسُه) — وقد يغيب عن CI، فتُرسم هنا
    # صفحاتٌ بيضاء بعدد صفحات الكشف في مجلّدٍ مؤقّت.
    def _blank_pages(_pdf_path, *_a, **_k):
        from PIL import Image

        out = []
        for i in range(1, SC.recorded()["n_pages"] + 1):
            p = tmp_path / f"pg-{i:02d}.png"
            Image.new("RGB", (60, 80), "white").save(p)
            out.append(str(p))
        return out

    monkeypatch.setattr(app, "_pages_to_pngs", _blank_pages)
    opened: list = []

    def visitor():
        s = app._new_session()
        opened.append(s)
        return s

    yield app, visitor
    for s in opened:
        s.close()


def test_try_now_needs_no_key_and_calls_nothing(public):
    app, visitor = public
    sess = visitor()
    ticker, table, kpi, gallery, *filters, intake_note, back = app.try_now(sess)
    assert back is sess, "«جرّب الآن» لم يُعِد جلستَه — فلا تعرفها Gradio ولا تحذفها"
    assert len(table) == 54, len(table)
    assert "قراءةٌ مسجَّلة" in ticker and "بلا مفتاح" in ticker, ticker
    assert ">1<" in kpi and ">54<" in kpi, kpi           # الصفوفُ ٥٤ والمشبوهُ واحد
    assert len(gallery) == 5
    assert filters == ["كل الأعمدة", "", "", ""]
    path = app._ledger_ui.ledger_file(sess.home, app._ledger_key(sess))
    assert path.exists() and path.is_relative_to(sess.home), path
    # الدفترُ مبنيٌّ من القراءة المسجَّلة بلا مفتاح (منه تحسب أدواتُ الوكيل)، وتنزيلُ Excel يعمل
    conn = L.read_ledger(path)
    try:
        assert L.answer(conn, "totals")["rows_counted"] > 0
    finally:
        conn.close()
    xlsx, xnote = app.export_xlsx(sess)
    assert xlsx and Path(xlsx).exists(), xnote


def test_try_now_replaces_the_previous_statement_whole(public):
    """ما بقي في الجلسة من قراءةٍ سابقة لا يُقرأ على الكشف الاصطناعيّ (حالةٌ من كشفٍ آخر)."""
    app, visitor = public
    sess = visitor()
    sess.state.update({"footer_checks": ["من كشفٍ سابق"], "era": "سابق", "usage": {"cost": 9}})
    app.try_now(sess)
    assert not {"footer_checks", "era", "usage"} & set(sess.state), sorted(sess.state)
    assert sess.state["source_sha"] == L.source_sha256(SC.PDF)


def test_two_visitors_get_two_ledgers_and_never_see_each_others_questions(public):
    """**شرطُ (ب) الثالث:** الأسئلةُ تُسجَّل في الدفتر — فدفترٌ مشتركٌ يُري زائرًا أسئلةَ غيره."""
    app, visitor = public
    a, b = visitor(), visitor()
    app.try_now(a)
    app.try_now(b)
    pa = app._ledger_ui.ledger_file(a.home, app._ledger_key(a))
    pb = app._ledger_ui.ledger_file(b.home, app._ledger_key(b))
    assert pa != pb and pa.name == pb.name, (pa, pb)    # الكشفُ نفسُه، ودفتران
    res = SimpleNamespace(used_row_nos=[2], cited_row_ids=[], refused=False)
    app._record_qa_row(a, res, "سؤالُ الزائر الأوّل", "جوابٌ له")

    def questions(path):
        conn = L.read_ledger(path)
        try:
            return L.answer(conn, "qa")["qa"]
        finally:
            conn.close()

    assert questions(pb) == [], questions(pb)
    assert questions(pa), "سؤالُ الزائر الأوّل لم يُسجَّل في دفتره"


def test_the_session_end_takes_its_try_now_ledger(public):
    """**شرطُ (ب) الثاني:** دفترُ «جرّب الآن» في مجلّد الجلسة، فيُمحى بانتهائها."""
    app, visitor = public
    sess = visitor()
    app.try_now(sess)
    home = sess.home
    assert any(home.rglob("*.sqlite"))
    assert sess.close() == {"files_left": 0, "home_left": False}
    assert not home.exists()


def test_the_index_is_not_built_until_a_question_needs_it(public, monkeypatch):
    """الفهرسُ الدلاليّ يخدم المحادثةَ وحدها (وهي بمفتاح الزائر) — فلا يُحمَّل نموذجُ التضمين عند الضغط."""
    app, visitor = public

    def _built(_chunks):
        raise AssertionError("بُني الفهرسُ عند «جرّب الآن»")

    monkeypatch.setattr(app, "build_index", _built)
    sess = visitor()
    app.try_now(sess)
    assert "store" not in sess.state


def test_a_question_without_a_key_does_not_build_the_index(public, monkeypatch):
    """**مراجعةُ الكود (2026-10-30):** السؤالُ بلا مفتاحٍ بعد «جرّب الآن» كان يبني الفهرسَ (نموذجُ التضمين،
    ٤٧٠ ميغابايت عند أوّل نداء — مقيسٌ 2026-10-30) **ثمّ** يطلب المفتاح — عملٌ لا يخدم شيئًا قبل جملة «ضع مفتاحك»."""
    app, visitor = public

    def _built(_chunks):
        raise AssertionError("بُني الفهرسُ لسؤالٍ بلا مفتاح")

    monkeypatch.setattr(app, "build_index", _built)
    sess = visitor()
    app.try_now(sess)
    history, _q, sess = app.prepare_ask("كم مجموع الإيداعات؟", [], sess)
    history, *_rest = app.ask_followup(history, "", sess)
    assert "مفتاح OpenRouter" in history[-1]["content"], history[-1]
    assert "store" not in sess.state


def test_the_owners_surface_does_not_offer_it(monkeypatch, tmp_path):
    """**المحلّيّ مجلّدُ بيانات المالك الدائم:** «جرّب الآن» كان سيكتب فيه ويحوّل مؤشّرَ كشفه النشِط."""
    import gradio as gr

    import app

    assert app.SURFACE == "local"                       # الضوابطُ محلّيّةٌ بإعلان conftest
    assert app.try_card.visible is False
    owner = tmp_path / "owner-data"
    owner.mkdir()
    monkeypatch.setattr(app, "DATA_HOME", owner)
    with pytest.raises(gr.Error, match="السطح العامّ"):
        app.try_now(app._new_session())
    assert not any(owner.rglob("*")), sorted(owner.rglob("*"))


def test_the_button_is_wired_with_the_session():
    import app

    fns = app.demo.fns.values() if isinstance(app.demo.fns, dict) else app.demo.fns
    wired = [f for f in fns if getattr(f, "fn", None) is app.try_now]
    assert len(wired) == 1, "«جرّب الآن» غيرُ موصولٍ بزرّ"
    assert app.sess_state in wired[0].inputs and app.sess_state in wired[0].outputs
    assert (app.try_btn._id, "click") in wired[0].targets, wired[0].targets
