"""شروطُ (ب) الأربعة على السطح العامّ (G3 البند ٣ · قرارُ المالك 2026-10-28 · المرحلة ١ في `docs/SHOWCASE_PLAN.md`).

**نصُّ القاعدة:** «اقرأ كشفك» يقبل كشفًا يرفعه الزائر بمفتاحه، بشروطٍ أربعة:
١) لا شيءَ يُحفظ بعد الجلسة · ٢) دفترٌ ومؤقّتٌ **لكلّ جلسة** يُحذفان بانتهائها · ٣) **جلسةٌ لا ترى دفترَ
جلسةٍ أخرى** ولو كان الكشفُ نفسَه · ٤) لا سجلَّ لمحتوى الكشف أو للمفتاح.
**ولا يُفتح الرفعُ على السطح العامّ قبل أن تحرس كلَّ شرطٍ ضابطٌ أخضر** — وهذه الضوابط.

**العِلّة التي تقيسها:** كانت الواجهةُ لمستخدمٍ واحد — حالةٌ عامّة (`app.STATE`) ومجلّدٌ دائم ومؤشّرُ
«كشفٍ نشِط» فيه ⇒ زائران يتشاركان الدفتر. والآن لكلّ زائرٍ `Session` في `gr.State`، وتُغلق بـ
`delete_callback` حين تحذف Gradio حالتَه. **والمسارُ كلُّه مسارُ التطبيق نفسه** (`process_pdf` بقفله،
والنموذجُ وحده مستبدَل، والشبكةُ مغلقة ⇒ $0).

**وحدُّ الشرط الثاني مُعلَن (مقيسٌ من النسخة المثبَّتة `gradio/state_holder.py`):** Gradio تُبقي حالةَ
الجلسة بعد إغلاق الصفحة **ساعةً** من آخر تحديثٍ لها (فرصةُ عودة الزائر)، ثمّ تحذفها فيقع الإغلاق.
والضابطُ هنا يقيس أنّ حذفَ Gradio **يُغلق الجلسة فعلًا** — لا طولَ المهلة.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("gradio")
pytest.importorskip("langgraph.checkpoint.sqlite")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from test_button_builds_a_workbook import _FOOTERS, _ROWS, SAMPLE, _page_of  # noqa: E402

VISITOR = "visitor-key-sentinel"
#: محتوى الكشف المصطنع — يُبحث عنه في كلّ مخرجٍ وسجلّ (البياناتُ والأرقامُ كما في ردود النموذج المكتوبة).
CONTENT = ("رصيد افتتاحي", "شراء", "إيداع", "رسوم", "480.00", "515.00")


@pytest.fixture
def public(monkeypatch):
    """التطبيقُ على السطح العامّ: قرّاؤه المدفوعون مستبدَلون بالعيّنة، والشبكةُ مغلقة."""
    import app
    from statement_qa.footer_oracle import FooterReading

    def _no_network(*_a, **_k):
        raise AssertionError("نداءُ شبكةٍ في ضابطٍ وعدُه $0")

    monkeypatch.setattr(socket.socket, "connect", _no_network)

    def read_footer(img, stats=None, api_key=None):
        dr, cr, bal = _FOOTERS[_page_of(img)]
        return FooterReading(debits=dr, credits=cr, balance=bal)

    def read_rows_vlm(img, stats=None, api_key=None):
        pg = _page_of(img)
        if stats is not None:
            stats["page_no"] = pg
        return [dict(r) for r in _ROWS[pg]]

    def read_page_descriptions(*_a, **_k):
        raise ValueError("البيانُ مستبدَل في الضابط")

    monkeypatch.setattr(app, "probe_bank", lambda _img, stats=None, api_key=None:
                        {"verdict": "alrajhi", "bank": "مصرف الراجحي"})
    monkeypatch.setattr(app, "read_footer", read_footer)
    monkeypatch.setattr(app, "read_rows_vlm", read_rows_vlm)
    monkeypatch.setattr(app, "read_page_descriptions", read_page_descriptions)
    monkeypatch.setattr(app, "build_index", lambda _chunks: None)
    monkeypatch.setattr(app, "SURFACE", "public")
    opened: list = []

    def visitor():
        s = app._new_session()
        opened.append(s)
        return s

    yield app, visitor
    for s in opened:
        s.close()


def _read(app, sess) -> tuple:
    """زرُّ القراءة كما توصله الواجهة: `process_pdf` بقفل المهمّة، والجلسةُ آخرُ مُخرَجاته."""
    out = app.process_pdf(str(SAMPLE), False, VISITOR, sess, progress=lambda *_a, **_k: None)
    assert out[-1] is sess, "مسارُ القراءة لم يُعِد جلستَه — فلا تعرفها Gradio ولا تحذفها"
    return out


def _converse(app, sess) -> None:
    """سؤالٌ مسجَّلٌ في الدفتر وفي ذاكرة المحادثة — كما يكتبهما `ask_followup` بعد الجواب."""
    from statement_qa import qa

    res = SimpleNamespace(used_row_nos=[2], cited_row_ids=[], refused=False)
    app._record_qa_row(sess, res, "كم مجموع المشتريات؟", "المجموع 20.00 (صفحة 1، صف 2) شراء")
    qa.remember(app._ledger_key(sess), "كم مجموع المشتريات؟", "المجموع 20.00 شراء",
                memory_path=app._memory_path(sess))


def _files(root: Path) -> set[Path]:
    return {p for p in Path(root).rglob("*") if p.is_file()} if Path(root).exists() else set()


# ————— الشرط ١: لا شيءَ يُحفظ بعد الجلسة —————

def test_condition_1_nothing_the_session_wrote_survives_it(public):
    app, visitor = public
    cache = Path(app.demo.GRADIO_CACHE)
    before_cache, before_home = _files(cache), _files(app.DATA_HOME)
    sess = visitor()
    _read(app, sess)
    _converse(app, sess)
    xlsx, _n = app.export_xlsx(sess)
    conv, _n = app._conversation_export(sess)
    ledger = app._ledger_path_for(sess)
    assert ledger.exists() and xlsx and conv, "الجلسةُ لم تكتب ما يُقاس محوُه"
    written = (_files(cache) - before_cache) | _files(sess.home)
    assert len(written) >= 4, sorted(map(str, written))      # صورُ الصفحات · الإكسل · المحادثة · الدفتر

    app._end_session(sess)                                    # ما تناديه Gradio بانتهاء الجلسة

    assert not sess.home.exists(), "مجلّدُ الجلسة بقي بعد انتهائها"
    left = sorted(str(p) for p in written if p.exists())
    assert not left, f"ملفّاتٌ كتبتها الجلسةُ بقيت بعدها: {left}"
    # **ومجلّدُ البيانات الدائم لا يحمل شيئًا من الجلسة** — إلّا ملفَّ قفل المهمّة: رقمُ عمليّةٍ ووقتٌ
    # لا بياناتُ كشف (حكمُ R131-5)، ويبقى لأنّ حذفَه أثناء قراءةٍ يفتح البابَ لمهمّتين.
    new_home = {p.name for p in _files(app.DATA_HOME) - before_home}
    assert new_home <= {"job.lock"}, f"السطحُ العامّ كتب في مجلّد البيانات الدائم: {new_home}"
    assert sess.state == {}, "حالةُ الجلسة في الذاكرة لم تُفرَّغ"


def test_condition_1_the_conversation_memory_is_closed_with_the_session(public):
    """حافظةُ المحادثة (`SqliteSaver`) متّصلٌ مفتوحٌ في العمليّة — يُغلق مع الجلسة فلا يُعيد إنشاءَ ملفّها."""
    from statement_qa import qa

    app, visitor = public
    sess = visitor()
    _read(app, sess)
    _converse(app, sess)
    mine = [k for k in qa._MEMORY if k.startswith(str(sess.home))]
    assert mine, "لم تُفتح حافظةٌ للجلسة — فالضابطُ لا يقيس إغلاقها"
    app._end_session(sess)
    assert not [k for k in qa._MEMORY if k.startswith(str(sess.home))], "حافظةُ الجلسة بقيت مفتوحة"
    assert not sess.home.exists()


# ————— الشرط ٢: دفترٌ ومؤقّتٌ لكلّ جلسة، يُحذفان بانتهائها —————

def test_condition_2_each_session_has_its_own_folder_for_its_ledger(public):
    app, visitor = public
    a, b = visitor(), visitor()
    assert a.home != b.home and a.home.exists() and b.home.exists()
    assert not a.home.is_relative_to(app.DATA_HOME), "مجلّدُ الجلسة العامّة داخل مجلّد البيانات الدائم"
    _read(app, a)
    assert app._ledger_path_for(a).is_relative_to(a.home), "دفترُ الجلسة خارج مجلّدها"
    assert all(Path(f).exists() for f in a.files) and a.files, "نسخُ العرض لم تُسجَّل في جلستها"


def test_condition_2_gradio_ending_the_session_deletes_it(public):
    """**عبر آليّة Gradio نفسِها لا نداءٍ مباشر:** حاملُ الحالة (`StateHolder`) يحذف حالةَ جلسةٍ أُغلقت
    ومضت مهلتُها ⇒ يُنادي `delete_callback` ⇒ تُغلق الجلسة. والمهلةُ تُصفَّر هنا (حدُّها مُعلَن أعلاه)."""
    from gradio.state_holder import StateHolder

    app, visitor = public
    sess = visitor()
    _read(app, sess)
    old = getattr(app.demo, "state_holder", None)
    holder = StateHolder()
    holder.set_blocks(app.demo)
    try:
        state = holder["visitor-1"]
        state[app.sess_state._id] = sess                    # كما تكتبها Gradio حين يُعيدها حدثٌ
        state.is_closed = True                               # أُغلقت الصفحة
        state.STATE_TTL_WHEN_CLOSED = 0                      # ومضت مهلةُ العودة
        holder.delete_all_expired_state()
    finally:
        app.demo.state_holder = old
    assert sess.closed and not sess.home.exists(), "حذفُ Gradio لحالة الجلسة لم يُغلقها"


def test_condition_2_the_wiring_hands_every_event_its_own_session():
    """**كلُّ حدثٍ يقرأ جلسةً يأخذها مُدخلًا** (فلا يقرأ جلسةَ غيره)، **والقراءةُ والسؤالُ يُعيدانها**
    (فتسجّلها Gradio وتحذفها)، **والحذفُ موصولٌ** بـ`_end_session`."""
    import inspect

    import app

    assert app.sess_state.delete_callback is app._end_session
    fns = app.demo.fns.values() if isinstance(app.demo.fns, dict) else app.demo.fns
    readers, writers = [], set()
    for f in fns:
        fn = getattr(f, "fn", None)
        if fn is None:
            continue
        takes = "sess" in inspect.signature(fn).parameters or fn.__name__ == "<lambda>"
        if takes and "sess" in inspect.signature(fn).parameters:
            readers.append(fn.__name__)
            assert app.sess_state in f.inputs, f"{fn.__name__} يقرأ جلسةً لا يأخذها مُدخلًا"
        if app.sess_state in f.outputs:
            writers.add(fn.__name__)
    assert {"process_pdf", "prepare_ask", "ask_followup", "export_xlsx",
            "_delete_statement_click"} <= set(readers), readers
    assert {"process_pdf", "prepare_ask", "_start_session"} <= writers, writers


# ————— الشرط ٣: جلسةٌ لا ترى دفترَ جلسةٍ أخرى ولو كان الكشفُ نفسَه —————

def test_condition_3_a_session_never_sees_another_sessions_ledger(public):
    app, visitor = public
    a, b = visitor(), visitor()
    _read(app, a)
    _converse(app, a)
    # **قبل أن تقرأ ب:** لا كشفَ ولا دفترَ ولا محادثة — ولو قرأت أ الكشفَ نفسَه للتوّ.
    assert app._ledger_key(b) == ""
    assert "لا كشف" in app._ledger_refresh_click(b) or "لم يُقرأ" in app._ledger_refresh_click(b), \
        app._ledger_refresh_click(b)
    got, note = app._conversation_export(b)
    assert got is None, note
    # **وبعد أن تقرأ ب الكشفَ نفسَه:** المفتاحُ واحد (بصمةُ الكشف) والدفتران ملفّان مختلفان.
    _read(app, b)
    assert app._ledger_key(a) == app._ledger_key(b)
    assert app._ledger_path_for(a) != app._ledger_path_for(b)
    got, note = app._conversation_export(b)
    assert got is None and "لا محادثة" in note, f"ب ترى محادثةَ أ: {note}"
    from statement_qa import qa

    thread = {"configurable": {"thread_id": app._ledger_key(b)}}
    assert qa._thread_messages(thread, app._memory_path(a)), "ذاكرةُ أ فارغة — الضابطُ لا يقيس شيئًا"
    assert not qa._thread_messages(thread, app._memory_path(b)), "ب ترى رسائلَ محادثة أ"


def test_condition_3_one_sessions_delete_and_end_leave_the_other_whole(public):
    app, visitor = public
    a, b = visitor(), visitor()
    _read(app, a)
    _read(app, b)
    b_ledger, b_copies = app._ledger_path_for(b), set(b.files)
    assert b_ledger.exists() and b_copies
    msg = app._delete_statement_click(a)[0]
    assert "حُذفت" in msg, msg
    app._end_session(a)
    assert b_ledger.exists(), "حذفُ أ محا دفترَ ب"
    assert all(Path(f).exists() for f in b_copies), "حذفُ أ محا نسخَ عرض ب"
    assert len(b.state.get("rows") or []) == 5, "حالةُ ب تغيّرت بحذف أ"


def test_the_library_purge_reaches_every_session_so_the_delete_is_per_session(public):
    """**قياسُ سبب البناء (قاعدةُ المالك: لا إعادةَ اختراعٍ إلّا بقياس):** دالّةُ المكتبة
    `delete_files_created_by_app(demo, None)` — التي كان زرُّ الحذف يناديها — **تمحو نسخَ عرض كلّ
    الجلسات** ⇒ على السطح العامّ يمحو حذفُ زائرٍ صورَ زائرٍ آخر. فالحذفُ صار بقائمة الجلسة نفسها."""
    from gradio.route_utils import delete_files_created_by_app

    app, visitor = public
    a, b = visitor(), visitor()
    _read(app, a)
    _read(app, b)
    assert b.files and all(Path(f).exists() for f in b.files)
    delete_files_created_by_app(app.demo, age=None)          # «حذفُ أ» بدالّة المكتبة
    assert not any(Path(f).exists() for f in b.files), \
        "دالّةُ المكتبة لم تعد تمسّ جلساتٍ أخرى — راجع هل تكفي وحدَها الآن"


def test_two_identical_uploads_share_one_file_so_the_upload_is_not_deleted_per_session(monkeypatch):
    """**حدُّ الشرط الأوّل المُعلَن، مقيسًا بمسار الرفع الحقيقيّ:** Gradio تضع المرفوعَ في مجلّدٍ ببصمة
    محتواه (`route_utils.upload_fn`) ⇒ زائران رفعا الكشفَ نفسَه يتشاركان **ملفًّا واحدًا**، وحذفُه مع
    جلسة أحدهما يمحوه من تحت الآخر. فلا يُحذف مع الجلسة، وتحذفه المكتبةُ بعمره (`delete_cache`)."""
    import shutil

    from fastapi.testclient import TestClient
    from gradio.routes import App

    import app

    monkeypatch.setattr(app.demo, "max_file_size", None, raising=False)    # يضبطه `launch()` عادةً
    body = b"%PDF-1.4\n% identical upload probe\n"
    with TestClient(App.create_app(app.demo)) as client:
        got = [client.post("/gradio_api/upload",
                           files={"files": ("statement.pdf", body, "application/pdf")}).json()[0]
               for _visitor in (1, 2)]
    try:
        assert got[0] == got[1], f"المرفوعان المتطابقان صارا ملفّين — راجع حذفَ المرفوع مع الجلسة: {got}"
    finally:
        shutil.rmtree(Path(got[0]).parent, ignore_errors=True)


# ————— الشرط ٤: لا سجلَّ لمحتوى الكشف أو للمفتاح —————

def test_condition_4_no_output_or_log_carries_the_statement_or_the_key(public, capfd, caplog):
    import logging

    app, visitor = public
    caplog.set_level(logging.DEBUG)
    sess = visitor()
    out = _read(app, sess)
    _converse(app, sess)
    app.export_xlsx(sess)
    app._conversation_export(sess)
    assert any(c in str(out[1].to_string()) for c in CONTENT), "الجدولُ بلا محتوى — الضابطُ لا يقيس شيئًا"
    captured = capfd.readouterr()
    logged = "\n".join(r.getMessage() for r in caplog.records)
    for stream, text in (("stdout", captured.out), ("stderr", captured.err), ("log", logged)):
        assert VISITOR not in text, f"المفتاحُ ظهر في {stream}"
        leaked = [c for c in CONTENT if c in text]
        assert not leaked, f"محتوى الكشف ظهر في {stream}: {leaked}"


def test_condition_4_the_key_is_kept_nowhere(public):
    """المفتاحُ يُمرَّر مع الحدث ولا يُحفظ: لا في حالة الجلسة ولا في ملفٍّ كتبته."""
    app, visitor = public
    sess = visitor()
    _read(app, sess)
    _converse(app, sess)
    assert VISITOR not in repr(sess.state), "المفتاحُ في حالة الجلسة"
    for f in _files(sess.home) | {Path(p) for p in sess.files}:
        assert VISITOR.encode() not in f.read_bytes(), f"المفتاحُ في ملفٍّ كتبته الجلسة: {f.name}"


# ————— ما كشفه نزعُ الحالة العامّة —————

def test_the_table_shows_the_verdicts_of_this_read(public):
    """كان الجدولُ يُبنى قبل كتابة أحكام هذه القراءة فيقرأ عمودُ «التحقق» أحكامَ ما قبلها؛ وفي جلسةٍ
    جديدةٍ لا شيءَ قبلها ⇒ كان يُظهر «غير محكوم» لصفحاتٍ طابقت تذييلَها."""
    from statement_qa.verification import verdict_label

    app, visitor = public
    sess = visitor()
    table = _read(app, sess)[1]
    assert set(table["التحقق"]) == {verdict_label("ok")}, set(table["التحقق"])
