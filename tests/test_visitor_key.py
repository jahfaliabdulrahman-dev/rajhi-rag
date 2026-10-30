"""مفتاحُ الزائر وحدَه في القراءة الحيّة (G3 البند ٣ · قرارُ المالك 2026-10-28 · المرحلة ١ في `docs/SHOWCASE_PLAN.md`).

**القاعدة:** «اقرأ كشفك» يقبل كشفًا يرفعه الزائر **بمفتاح الزائر وحده**، ولا يقرأ بمفتاح التطبيق أبدًا.
والضوابطُ هنا تقيسها على ثلاثة مستويات — والشبكةُ مغلقةٌ والكلفةُ صفر:

1. **الناقلُ الواحد** (`chat_vlm_image`) يرسل المفتاحَ المُمرَّر ولا يحلّ مفتاحَ التطبيق أصلًا، ويرفض
   مفتاحًا فارغًا قبل أيّ طلب (الفارغُ لا يعود إلى مفتاح التطبيق بصمت).
2. **كلُّ دالّةِ قراءةٍ مدفوعة** تمرّر المفتاحَ إلى الناقل — دالّةٌ تُسقطه تُرجع الناقلَ إلى مفتاح التطبيق.
3. **التطبيقُ على السطح العامّ:** يرفض القراءةَ بلا مفتاح قبل أيّ نداء، ويسلّم مفتاحَ الزائر لكلّ نداءٍ
   مدفوع وللوكيل.

**والحارسُ في كلّ ضابط:** حلُّ مفتاح التطبيق (`get_api_key`) يُفشل الضابطَ فورًا، ومفتاحُ التطبيق في
البيئة قيمةٌ حارسة — فلو وصل طلبًا لظهر في الترويسة.
"""
from __future__ import annotations

import io
import json
import socket
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import api_key as _api_key_mod  # noqa: E402
from statement_qa import bank_check, desc_reader, footer_oracle, vlm_reader  # noqa: E402

#: قيمتان حارستان لا تشبهان مفتاحًا حقيقيًّا (ماسحُ الأسرار يمنع شكلَ المفتاح في الفهرس — بحقّ).
VISITOR = "visitor-key-sentinel"
APP_KEY = "app-key-sentinel"


class _Stop(Exception):
    """يوقف النداءَ بعد تسجيل مفتاحه — لا يُبنى جوابٌ لا يحتاجه الضابط."""


@pytest.fixture
def app_key_forbidden(monkeypatch):
    """حلُّ مفتاح التطبيق ممنوعٌ في هذا الضابط — ومفتاحُ التطبيق في البيئة قيمةٌ حارسة."""
    monkeypatch.setenv("OPENROUTER_API_KEY", APP_KEY)

    def _resolved(*_a, **_k):
        raise AssertionError("حُلَّ مفتاحُ التطبيق في مسارٍ يجب أن يحمل مفتاحَ الزائر وحده")

    monkeypatch.setattr(_api_key_mod, "get_api_key", _resolved)
    return _resolved


def _png(tmp_path: Path) -> str:
    from PIL import Image

    path = tmp_path / "pg-01.png"
    Image.new("RGB", (400, 600), "white").save(path)
    return str(path)


def test_the_transport_sends_the_given_key_and_never_resolves_the_app_key(monkeypatch,
                                                                           app_key_forbidden):
    seen: list[str | None] = []

    def fake_urlopen(req, timeout=None):
        seen.append(req.get_header("Authorization"))
        body = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"cost": 0}}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen", fake_urlopen)
    assert vlm_reader.chat_vlm_image("AAAA", "p", api_key=VISITOR) == "ok"
    assert seen == [f"Bearer {VISITOR}"], seen


def test_an_empty_key_is_refused_before_any_request(monkeypatch, app_key_forbidden):
    """**الفارغُ لا يعود إلى مفتاح التطبيق:** خانةٌ تُركت فارغةً ترفض القراءةَ ولا تُرسل طلبًا."""
    def fake_urlopen(*_a, **_k):
        raise AssertionError("أُرسل طلبٌ بمفتاحٍ فارغ")

    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError):
        vlm_reader.chat_vlm_image("AAAA", "p", api_key="")
    with pytest.raises(ValueError):
        vlm_reader.chat_vlm_image("AAAA", "p", api_key="   ")


def _readers(png: str):
    """كلُّ دالّةِ قراءةٍ مدفوعةٍ يناديها التطبيق — بوسائطَ تبلغ الناقل."""
    from PIL import Image

    return {
        "read_rows_vlm": lambda: vlm_reader.read_rows_vlm(png, api_key=VISITOR),
        "reread_boundary": lambda: vlm_reader.reread_boundary(png, Decimal("100"), 1,
                                                              api_key=VISITOR),
        "recover_anchor": lambda: vlm_reader.recover_anchor(
            [{"balance": Decimal("150")}], Decimal("100"), png, 1, api_key=VISITOR),
        "read_footer": lambda: footer_oracle.read_footer(png, api_key=VISITOR),
        "try_page_reread": lambda: footer_oracle.try_page_reread(
            png, {}, None, None, Decimal("0"), api_key=VISITOR),
        "read_page_descriptions": lambda: desc_reader.read_page_descriptions(
            Image.new("RGB", (40, 40), "white"), None, api_key=VISITOR),
        "probe_bank": lambda: bank_check.probe_bank(png, api_key=VISITOR),
    }


@pytest.mark.parametrize("name", sorted(_readers("x")))
def test_every_paid_reader_hands_the_key_to_the_transport(name, tmp_path, monkeypatch,
                                                          app_key_forbidden):
    from PIL import Image

    calls: list[str | None] = []

    def transport(*_a, **k):
        calls.append(k.get("api_key"))
        raise _Stop

    for mod in (vlm_reader, footer_oracle, bank_check):
        monkeypatch.setattr(mod, "chat_vlm_image", transport)
    monkeypatch.setattr(desc_reader, "stack_image",
                        lambda img, pb, cont: (Image.new("RGB", (40, 40), "white"), 1))
    try:
        _readers(_png(tmp_path))[name]()
    except _Stop:
        pass                                   # الدوالُّ التي لا تبتلع الخطأ يصعد منها الإيقاف
    assert calls == [VISITOR], f"{name}: وصل الناقلَ {calls!r} لا مفتاحُ الزائر"


def test_the_agent_model_uses_the_given_key_only(app_key_forbidden):
    from statement_qa.qa import build_llm

    llm = build_llm(api_key=VISITOR)
    assert llm.openai_api_key.get_secret_value() == VISITOR
    with pytest.raises(ValueError):
        build_llm(api_key="")


# ————— التطبيقُ على السطح العامّ —————

pytest.importorskip("gradio")


@pytest.fixture
def public_app(monkeypatch, app_key_forbidden):
    """التطبيقُ على السطح العامّ، وقرّاؤه المدفوعون يسجّلون المفتاحَ الذي وصلهم ثمّ يجيبون بالعيّنة."""
    import app
    from statement_qa.footer_oracle import FooterReading
    from test_button_builds_a_workbook import _FOOTERS, _ROWS, _page_of

    def _no_network(*_a, **_k):
        raise AssertionError("نداءُ شبكةٍ في ضابطٍ وعدُه $0")

    monkeypatch.setattr(socket.socket, "connect", _no_network)
    keys: list[tuple[str, str | None]] = []

    def probe_bank(_img, stats=None, api_key=None):
        keys.append(("probe_bank", api_key))
        return {"verdict": "alrajhi", "bank": "مصرف الراجحي"}

    def read_footer(img, stats=None, api_key=None):
        keys.append(("read_footer", api_key))
        dr, cr, bal = _FOOTERS[_page_of(img)]
        return FooterReading(debits=dr, credits=cr, balance=bal)

    def read_rows_vlm(img, stats=None, api_key=None):
        keys.append(("read_rows_vlm", api_key))
        pg = _page_of(img)
        if stats is not None:
            stats["page_no"] = pg
        return [dict(r) for r in _ROWS[pg]]

    def read_page_descriptions(*_a, api_key=None, **_k):
        keys.append(("read_page_descriptions", api_key))
        raise ValueError("البيانُ مستبدَل في الضابط")

    monkeypatch.setattr(app, "probe_bank", probe_bank)
    monkeypatch.setattr(app, "read_footer", read_footer)
    monkeypatch.setattr(app, "read_rows_vlm", read_rows_vlm)
    monkeypatch.setattr(app, "read_page_descriptions", read_page_descriptions)
    monkeypatch.setattr(app, "build_index", lambda _chunks: None)
    monkeypatch.setattr(app, "SURFACE", "public")
    app.STATE.clear()
    yield app, keys
    app.STATE.clear()


def test_a_public_read_without_a_key_is_refused_before_any_call(public_app):
    import gradio as gr
    from test_button_builds_a_workbook import SAMPLE

    app, keys = public_app
    for empty in ("", "   ", None):
        with pytest.raises(gr.Error):
            app._process_pdf_locked(str(SAMPLE), lambda *_a, **_k: None, api_key=empty)
    assert keys == [], f"نداءٌ مدفوعٌ بلا مفتاح زائر: {keys}"


def test_a_public_read_hands_the_visitor_key_to_every_paid_call(public_app):
    from test_button_builds_a_workbook import SAMPLE

    app, keys = public_app
    app._process_pdf_locked(str(SAMPLE), lambda *_a, **_k: None, api_key=f"  {VISITOR}  ")
    called = {name for name, _k in keys}
    assert {"probe_bank", "read_footer", "read_rows_vlm"} <= called, called
    wrong = [(n, k) for n, k in keys if k != VISITOR]
    assert not wrong, f"نداءاتٌ بغير مفتاح الزائر: {wrong}"


def test_a_public_question_builds_the_agent_with_the_visitor_key(public_app, monkeypatch):
    from test_button_builds_a_workbook import SAMPLE

    app, _keys = public_app
    app._process_pdf_locked(str(SAMPLE), lambda *_a, **_k: None, api_key=VISITOR)
    app.STATE["store"] = object()
    got: dict = {}

    def answer_question(_store, _q, llm=None, **_k):
        got["key"] = llm.openai_api_key.get_secret_value() if llm is not None else None
        raise _Stop

    import statement_qa.qa as qa

    monkeypatch.setattr(qa, "answer_question", answer_question)
    app.STATE["pending_q"] = "كم مجموع السحوبات؟"
    with pytest.raises(_Stop):
        app.ask_followup([], api_key=VISITOR)
    assert got == {"key": VISITOR}, got


def test_a_public_question_without_a_key_is_refused_before_the_model(public_app, monkeypatch):
    from test_button_builds_a_workbook import SAMPLE

    app, _keys = public_app
    app._process_pdf_locked(str(SAMPLE), lambda *_a, **_k: None, api_key=VISITOR)
    app.STATE["store"] = object()
    import statement_qa.qa as qa

    def answer_question(*_a, **_k):
        raise AssertionError("نُودي الوكيلُ بلا مفتاح زائر")

    monkeypatch.setattr(qa, "answer_question", answer_question)
    app.STATE["pending_q"] = "كم مجموع السحوبات؟"
    history, *_rest = app.ask_followup([], api_key="")
    assert "مفتاح" in history[-1]["content"], history[-1]
