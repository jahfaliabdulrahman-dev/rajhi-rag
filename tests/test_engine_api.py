"""عقدُ المحرّك — ما تناديه واجهةُ React من الـSpace (`docs/SHOWCASE_PLAN.md` §٤ الشرط ٢ · `docs/CP1_STEPS.md` خ١).

**لماذا:** المرحلةُ ٣ تلمس الواجهةَ وحدها، وكلُّ ما تحتاجه من المحرّك يُبنى في المرحلة ١ ثمّ **يُجمَّد عند CP1**.
والعقدُ يُقاس بعميل Gradio الرسميّ (`gradio_client`، من صاحب المكتبة نفسه) على **خادمٍ حقيقيّ يُقلَع كما
يُقلعه الـSpace** — السطحُ العامّ، وبلا مفتاح التطبيق في البيئة ⇒ لا نداءَ مدفوعًا ولا شبكةَ خارجيّة.

**العِلّةُ التي كشفها القياس (2026-10-30):** ٢٦ ربطًا كلُّها عامّة، ثلاثةٌ منها فقط باسمٍ ثابت. والقراءةُ و«جرّب الآن»
بلا اسم، ونقطةُ `ask_question` **لا تجيب** (تضع السؤالَ في المحادثة فقط، والجوابُ في نقطةٍ تالية بلا اسم)،
والفلترةُ ثماني نقاطٍ للدالّة نفسِها. **وتغييرُ اسمٍ هنا كسرٌ للواجهة** — فلا يُغيَّر إلّا مع هذا الملفّ.
"""
from __future__ import annotations

import pytest

pytest.importorskip("gradio")
gradio_client = pytest.importorskip("gradio_client")

#: **العقدُ المجمَّد:** اسمُ كلّ نقطةٍ عامّة. وكلُّ ربطٍ آخر خاصّ.
CONTRACT = {
    "try_now", "process_pdf",                                 # كشفٌ في الجلسة: مسجَّلٌ بلا مفتاح · أو حيٌّ بمفتاح الزائر
    "add_question", "answer",                                 # السؤالُ بخطوتيه
    "filter_rows", "export_xlsx", "download_conversation",    # الجدولُ وملفّاه
    "delete_statement",
}
#: **وأُزيلت نقاطُ الدفتر الثلاث** (`ledger_ask` · `ledger_build` · `ledger_status`) مع لوحتها بقرار المالك
#: (2026-10-31، إعادةُ تصميم الواجهة قبل CP1). والقاعدةُ نفسُها باقية: منها تحسب أدواتُ الوكيل.
ALL_COLUMNS = "كل الأعمدة"


def test_the_public_api_is_the_frozen_contract():
    """**الأسماءُ هي العقد:** العامُّ = القائمةُ بالضبط، ولكلٍّ وصفٌ في صفحة الـAPI، والباقي خاصّ (لا «غيرُ موثَّق»)."""
    import app

    fns = list(app.demo.fns.values())
    public = {f.api_name: f for f in fns if f.api_visibility == "public"}
    assert set(public) == CONTRACT, (f"زائدٌ على العقد: {sorted(set(public) - CONTRACT)} · "
                                     f"ناقصٌ منه: {sorted(CONTRACT - set(public))}")
    undescribed = sorted(n for n, f in public.items() if not f.api_description)
    assert not undescribed, f"نقطةٌ عامّةٌ بلا وصف: {undescribed}"
    others = {f.api_visibility for f in fns if f.api_name not in CONTRACT}
    assert others <= {"private"}, f"ربطٌ خارج العقد ليس خاصًّا: {others}"


@pytest.fixture(scope="module")
def server(tmp_path_factory, start_app_server):
    """خادمٌ واحدٌ للملفّ، يُوقف في آخره — فلا يبقى خيطُ نبضٍ لعميلٍ متّصلًا به في ملفٍّ تالٍ."""
    srv = start_app_server(tmp_path_factory.mktemp("engine-api"))
    yield srv
    srv.proc.terminate()
    srv.proc.wait(timeout=60)


@pytest.fixture
def client(server):
    """كلُّ عميلٍ زائرٌ بجلسته — كما تفتح واجهةُ React جلسةً لكلّ متصفّح — ويُغلق بعد الضابط (`Client.close`)."""
    opened = []

    def new():
        opened.append(gradio_client.Client(server.url, verbose=False))
        return opened[-1]

    yield new
    for c in opened:
        c.close()


def _rows(table) -> int:
    return len(table["data"])


def test_try_now_loads_the_recorded_statement_without_a_key(client):
    summary, table, *_ = client().predict(api_name="/try_now")
    assert "قراءةٌ مسجَّلة لا حيّة" in summary
    assert _rows(table) == 54


def test_a_question_without_a_key_is_answered_with_the_rule_before_any_call(client):
    """**السؤالُ خطوتان في العقد:** `/add_question` يضعه، و`/answer` يجيب — وبلا مفتاحٍ جوابُه القاعدة، قبل أيّ نموذج."""
    visitor = client()
    visitor.predict(api_name="/try_now")
    history, _ = visitor.predict("كم مجموع السحوبات؟", [], api_name="/add_question")
    assert history[-1]["role"] == "user"
    chat, *_ = visitor.predict(history, "", api_name="/answer")
    assert chat[-1]["role"] == "assistant"
    assert "ضع مفتاح OpenRouter" in str(chat[-1]["content"])


def test_two_clients_never_share_a_session(client):
    """**الشرط ٣ عبر الـAPI:** زائرٌ حمّل كشفًا وزائرٌ لم يحمّل — الثاني لا يرى صفًّا من الأوّل."""
    first, second = client(), client()
    first.predict(api_name="/try_now")
    assert _rows(first.predict(ALL_COLUMNS, "", "", "", api_name="/filter_rows")) == 54
    assert _rows(second.predict(ALL_COLUMNS, "", "", "", api_name="/filter_rows")) == 0


def test_delete_empties_only_the_callers_session(client):
    mine, other = client(), client()
    mine.predict(api_name="/try_now")
    other.predict(api_name="/try_now")
    mine.predict(api_name="/delete_statement")
    assert _rows(mine.predict(ALL_COLUMNS, "", "", "", api_name="/filter_rows")) == 0
    assert _rows(other.predict(ALL_COLUMNS, "", "", "", api_name="/filter_rows")) == 54


def test_private_wiring_is_not_offered_to_clients(client):
    """**الخاصُّ لا يُعرض للعميل** — وليس حاجزَ أمان: الواجهةُ نفسُها تناديه (التعليقُ فوق `gr.Blocks` في `app.py`)."""
    visitor = client()
    offered = set(visitor.view_api(print_info=False, return_format="dict")["named_endpoints"])
    assert offered == {f"/{n}" for n in CONTRACT}
    with pytest.raises(ValueError):
        visitor.predict(api_name="/_start_session")
