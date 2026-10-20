"""بوّابةُ القاعدة في التطبيق (R130): القراءةُ تكتبها، والحذفُ يمحوها، والصورُ لا تبقى في النظام.

**العِلّة المقيسة (مراجعة ١٣٠):** «القراءةُ تكتب قاعدةً» كانت **زرًّا منفصلًا** لا يُضغط؛ و«الملفّاتُ
المؤقّتةُ لا تُحذف» كانت `mkdtemp` بلا `finally` (١٩٢٥ مجلّدًا · ٧٥٥MB يوم الجلسة). والضوابطُ هنا
تشغّل **مسارَ القراءة نفسَه** على العيّنة المصطنعة (نموذجٌ مستبدَل، شبكةٌ مغلقة ⇒ $0) ثمّ تقيس:

- القاعدةَ موجودةٌ بعد المعالجة **بلا زرّ**، وفيها الصفوفُ والتذييلات.
- أسطحَ السؤال تُعاد من القاعدة بعد فقدِ الحالة (كما بعد إعادة التشغيل).
- زرَّ الحذف يترك **صفرَ ملفّ** ويُفرّغ الحالة.
- تنزيلَ المحادثة يقرأ من `qa`/`qa_evidence` لا من الرام.
- وصفرَ مجلّدٍ `rajhi_*` بعد قراءةٍ وتنزيلٍ، و`delete_cache` يحذف ملفّاتِ الحافظة بحسب المكتبة.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("gradio")
pytest.importorskip("langchain")
pytest.importorskip("langgraph.checkpoint.sqlite")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import ledger as L  # noqa: E402

#: العيّنةُ والـfixture من ملفّ ضابط الزرّ (نموذجٌ مستبدَلٌ وشبكةٌ مغلقة) — تُطلَب **بالاسم** عبر
#: `request` فلا يُعاد تعريفُ اسمٍ فيُسقطه الحارسُ البنيويّ (درسُ R57-4)، ولا تُنسخ استبدالاتُها.
from test_button_builds_a_workbook import SAMPLE, read_sample  # noqa: E402


@pytest.fixture
def app(request):
    """حالةُ التطبيق بعد قراءةِ العيّنة — الـfixture الأصلُّ `read_sample` بلا إعادة تعريفٍ هنا."""
    return request.getfixturevalue(read_sample.__name__)


def _db(app) -> Path:
    return app._ledger_ui.ledger_file(app.DATA_HOME, app._ledger_key())


def test_processing_writes_the_database_without_pressing_a_button(app):
    path = _db(app)
    assert path.exists(), "القراءةُ لم تكتب القاعدةَ (قرارُ المالك: عند انتهاء المعالجة لا بزرّ)"
    conn = L.read_ledger(path)
    try:
        rows = L.read_rows(conn)
        footers = L.read_footers(conn)
    finally:
        conn.close()
    assert len(rows) == len(app.STATE["rows"]) == 5, len(rows)
    assert set(footers) == {1, 2}
    assert footers[1]["debits"] and footers[1]["verdict"] == "ok", footers[1]


def test_the_question_surfaces_are_rebuilt_from_the_database_alone(app, monkeypatch):
    """**قبولُ القرار:** «الأداةُ تجيب من القاعدة ولو فرغت الذاكرة» — تُمسح الحالةُ ثمّ تُبنى منها."""
    key = app._ledger_key()
    app.STATE.clear()
    # فهرسُ البحث خارج الدعوى (الـfixture يستبدله بـNone لئلّا يحمّل نموذجَ تضمين) — يُثبت هنا.
    monkeypatch.setattr(app, "build_index", lambda chunks: f"index:{len(chunks)}")
    assert app._load_from_ledger(key), "تعذّرت إعادةُ البناء من القاعدة"
    assert app.STATE.get("store"), "لم يُبنَ الفهرسُ من القاعدة"
    assert len(app.STATE["rows"]) == 5
    assert app.STATE.get("footers"), "التذييلاتُ لم تُقرأ من القاعدة"


def test_deleting_a_statement_leaves_zero_files_and_empties_the_state(app):
    path = _db(app)
    folder = path.parent
    assert path.exists()
    out = app._delete_statement_click()
    assert "حُذفت" in out[0], out[0]
    assert not list(folder.glob("*.sqlite*")), list(folder.iterdir())
    assert not (app.DATA_HOME / "active.json").exists(), "مؤشّرُ الكشف بقي بعد الحذف"
    assert app.STATE == {}, "الحالةُ لم تُفرَّغ بعد الحذف"


def test_the_conversation_downloads_from_the_database(app):
    """**البند ١٠:** الملفُّ يُبنى من `qa`+`qa_evidence` (لا من ذاكرةٍ حيّة) — فيبقى بعد الإغلاق."""
    path = _db(app)
    conn = L.read_ledger(path)
    try:
        ids = L.row_ids_for(conn, [(1, 2), (1, 3)])
        L.record_qa(conn, "2026-10-20T09:00:00", "كم مجموع السحوبات؟",
                    "المجموع 20.00 (صفحة 1، صف 2)", ids)
    finally:
        conn.close()
    app.STATE.clear()                         # كأنّ التطبيق أُعيد تشغيلُه
    got, note = app._conversation_markdown()
    assert got and Path(got).exists(), note
    text = Path(got).read_text(encoding="utf-8")
    assert "كم مجموع السحوبات؟" in text and "المجموع 20.00" in text
    assert "الأدلّة" in text and "| 1 | 2 |" in text, text[:400]


def test_no_rajhi_work_folder_is_left_in_the_system_temp_dir(app):
    """**قبولُ R130-2:** بعد قراءةٍ وتنزيلٍ ⇒ صفرُ مجلّدٍ `rajhi_*` في مجلّد النظام."""
    tmp = Path(tempfile.gettempdir())
    before = {p.name for p in tmp.glob("rajhi_*")}
    app._process_pdf_locked(str(SAMPLE), progress=lambda *_a, **_k: None)
    out, _note = app.export_xlsx()
    assert out and Path(out).exists()
    after = {p.name for p in tmp.glob("rajhi_*")}
    assert after - before == set(), f"مجلّداتٌ بقيت: {sorted(after - before)}"


def test_the_library_purges_the_cache_files_it_created(app):
    """**«بمكوّن المكتبة لا منظّفٍ يدويّ»:** `delete_files_created_by_app` (التي يناديها `delete_cache`
    وعند الإغلاق) تحذف ملفّاتِ المخرجات التي سجّلتها المكوّنات."""
    from gradio.route_utils import delete_files_created_by_app

    app.export_xlsx()
    tracked = [f for s in app.demo.temp_file_sets for f in s if Path(f).exists()]
    assert tracked, "لم تُسجَّل ملفّاتُ الحافظة (النسخُ لم يقع؟)"
    delete_files_created_by_app(app.demo, age=None)
    left = [f for f in tracked if Path(f).exists()]
    assert not left, f"ملفّاتٌ لم تُحذف: {left[:3]}"


def test_the_table_filter_uses_a_chosen_column_and_a_date_range(app):
    """**البندان ٧ و٨:** الفلترةُ بعمودٍ مختار («النوع») وبمدى تاريخٍ من/إلى.

    والمدى يُقاس على صفوفٍ بتواريخ ثمانيةِ أرقام (كما تُطبع في كشوف الراجحي) — لا على تواريخ
    العيّنة المصطنعة (`01/01/2023` بصيغة يوم/شهر/سنة، وهي شكلٌ **لا يقرؤه** قارئُ العقد المعلَن؛
    فلا يُخترع لها قارئٌ ثالث في ضابط).
    """
    everything = app.filter_rows()
    typed = app.filter_rows("النوع", "إيداع")
    assert not typed.empty and len(typed) < len(everything)
    assert all("إيداع" in str(v) for v in typed["النوع"]), typed["النوع"].tolist()
    app.STATE["rows"] = [
        {"page": 1, "kind": "txn", "balance": "10.00", "movement": "10.00",
         "side": "debit", "ok": True, "desc": "أ", "date": "20260301", "type": "سحب"},
        {"page": 1, "kind": "txn", "balance": "20.00", "movement": "10.00",
         "side": "debit", "ok": True, "desc": "ب", "date": "20260415", "type": "سحب"},
        {"page": 1, "kind": "txn", "balance": "30.00", "movement": "10.00",
         "side": "debit", "ok": True, "desc": "ج", "date": "", "type": "سحب"},
    ]
    dated = app.filter_rows("", "", "2026-03-01", "2026-03-31")
    assert len(dated) == 1 and dated.iloc[0]["الوصف"] == "أ", dated
    assert len(app.filter_rows("", "", "", "2026-03-31")) == 1, "حدُّ «إلى» لم يُطبَّق"
    assert len(app.filter_rows("", "", "2026-04-01")) == 1, "حدُّ «من» لم يُطبَّق"
