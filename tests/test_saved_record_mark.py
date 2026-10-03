"""العلامةُ في **السجلّ المحفوظ** — يُكتب بسطرٍ في القارئ ويُقرأ من الـJSON (R83-3 · قرارُ المالك 2026-10-03).

**ولماذا هكذا (بالاستبدال عند `urlopen`، لا فوق الناقل):** الاستبدالُ في طبقة الشبكة يُبقي
*منطقَ الإعادة الحقيقيّ* داخلَ القياس — فيُقاس السلوكُ كما يجري، لا نسخةً منه. وهذا لم يكن تفضيلًا
نظريًّا: تبيّن بالتجربة أنّ سقفَ الميزانية في الأداة **لا يمنع الطلبَ الأوّل** (`--max-cost 0` أنفق
١٫٧١ سنتًا)، فبرهانُ «صفرِ الكلفة» بالسقف باطلٌ — و**الاستبدالُ هنا هو الضمانةُ الوحيدة**.

**وما يقيسه:** سجلُّ الصفحةِ التي قُرئت صفوفُها بجوابٍ مقطوعٍ ثمّ مسقوف = يحمل العلامة · وسجلُّ
القراءة الافتراضيّة **كما هو** (لا مفتاحَ جديدًا) — وهذا هو نصُّ R81-3 الذي حرسه R83-3.
"""
import io
import json
import pathlib
import sys
import types

import pytest

from statement_qa import vlm_reader


def _reply(finish, content, cost=0.005):
    return {"choices": [{"finish_reason": finish, "message": {"content": content}}],
            "usage": {"completion_tokens": 100, "prompt_tokens": 900, "cost": cost}}


_ROWS_OK = '{"rows": [{"movement": "10.00", "balance": "90.00", "desc": "قيد", "date": "2026-01-01"}]}'
_FOOTER_OK = '{"debits": "10.00", "credits": "0.00", "balance": "90.00"}'
_SAMPLE = pathlib.Path("data/sample/statement_sample.pdf")


def _run_slice(out: pathlib.Path, seq: dict, monkeypatch, cap: str | None = None):
    """يشغّل الأداةَ صفحةً واحدة، والردودُ تُختار بحسب `max_tokens` (٤٠٠٠ صفوف · ١٦٠٠ تذييل).

    ويعيد قائمةَ `max_tokens` لكلّ طلبٍ أُرسل — فارغةٌ تعني أنّ الأداةَ لم تُرسل شيئًا.

    **والتخطّي باسم التبعيّة الحقيقيّة (R86-1):** `pypdf` تُستورَد داخل دالّةٍ في الأداة، فاستيرادُ
    الوحدة ينجح ثمّ يسقط `main()` ⇒ كان الضابطُ **يُحمّر خطوةَ المجموعة** في بيئةٍ لا تحملها، والتخطّيُ
    المُعلَن هو الصوابُ (كما في `tests/test_pos_witness.py`: `importorskip("numpy")`). والرموزُ لا
    تُتخطّى حيث تُوجد — ففي بيئة الـCI الخفيفة تمرّ، وفي `ci-claims` تُتخطّى.
    """
    pil = pytest.importorskip("PIL", reason="الصفحةُ المُسبقةُ تُصنع بها")
    pytest.importorskip("numpy", reason="بوّابةُ الصفحة تحسب الحبرَ بها")
    scale = pytest.importorskip("tools.scale_slice")
    # **ولا `importorskip` لـ`pypdf`/`pdf2image` (R86-1 · الشقُّ (ب)):** يُستورَدان **داخل `main()`**،
    # ولكلٍّ منهما فرعٌ مُتجاوَزٌ إذا وُجد ملفُّه ⇒ فتُهيَّأ القصاصةُ والصورةُ **مسبقًا**، وتُحقَن وحدةٌ
    # **سامّةٌ** مكانهما: إن استُدعيت واحدةٌ منهما سقط الضابطُ **باسم السبب** — فلا **يُتخطّى** الحارسُ
    # في بيئة الـCI (وهو ما كان يُحمّر خطوتَها)، ولا يسقط على تبعيّةٍ لا يحتاجها.
    (out / "pages").mkdir(parents=True, exist_ok=True)
    pil.Image.new("RGB", (900, 1200), "white").save(out / "pages" / "pg-001.png")
    (out / "slice_1p.pdf").write_bytes(b"%PDF-1.4\n% guard calibration stub\n")

    def _poison(*_a, **_k):
        raise AssertionError("لم يكن ينبغي استدعاءُ مكتبة PDF: الصفحةُ والقصاصةُ مُهيَّأتان مسبقًا")

    for _name, _attrs in (("pypdf", ("PdfReader", "PdfWriter")),
                          ("pdf2image", ("convert_from_path",))):
        monkeypatch.setitem(sys.modules, _name,
                            types.SimpleNamespace(**{a: _poison for a in _attrs}))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-real-key")
    argv = ["scale_slice.py", "--source", str(_SAMPLE), "--first", "1", "--count", "1",
            "--out", str(out), "--page-gate", "off"]
    if cap is not None:
        argv += ["--max-cost", cap]
    monkeypatch.setattr("sys.argv", argv)
    sent: list = []

    def urlopen(req, timeout=None):
        body = json.loads(req.data.decode())
        sent.append(body.get("max_tokens"))
        plan = seq[4000] if body.get("max_tokens") == 4000 else seq[1600]
        item = plan.pop(0) if len(plan) > 1 else plan[0]     # الآخرُ يُعاد
        return io.BytesIO(json.dumps(item).encode())

    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen", urlopen)
    with pytest.raises(SystemExit):     # الأداةُ تُنهي بـ`sys.exit` (0 نجاح · 2 توقّف) كما في الـCI
        scale.main()
    return sent


def _record(out: pathlib.Path) -> dict:
    files = sorted((out / "results").glob("pg-*.json"))
    assert files, f"لا سجلَّ في {out}/results"
    assert len(files) == 1, f"صفحةٌ واحدة ⇒ سجلٌّ واحد، ووجدتُ {len(files)}"
    return json.loads(files[0].read_text())


def test_the_saved_record_carries_the_mark(tmp_path, monkeypatch):
    """سناريو ٨٤: صفوفٌ مقطوعةٌ ⇒ مسقوفةٌ تُنجح · والتذييلُ سليم ⇒ السجلُّ يحمل العلامة."""
    _run_slice(tmp_path, {4000: [_reply("length", '{"rows": [{"movement"'),
                                  _reply("stop", _ROWS_OK)],
                           1600: [_reply("stop", _FOOTER_OK)]}, monkeypatch)

    rec = _record(tmp_path)
    assert rec.get("reasoning") == "effort:low", "التذييلُ لم يُقَصَّر ⇒ العلامةُ للصفوف وحدَها"
    assert rec.get("usage", {}).get("request_calls") == 3, "قطعةٌ + مسقوفةٌ + تذييل = ٣ طلبات"


def test_a_default_read_record_is_unchanged(tmp_path, monkeypatch):
    """الضبطُ السالب: بلا قطعٍ ⇒ **لا مفتاحَ علامة** (سجلُّ اليوم كما هو)."""
    _run_slice(tmp_path, {4000: [_reply("stop", _ROWS_OK)],
                          1600: [_reply("stop", _FOOTER_OK)]}, monkeypatch)

    rec = _record(tmp_path)
    assert "reasoning" not in rec, "قراءةٌ افتراضيّةٌ لا تُختم ⇒ ولا مفتاحَ بلا معنى"
    assert rec.get("usage", {}).get("request_calls") == 2, "صفوفٌ + تذييل = طلبان بلا إعادة"


def test_a_capped_footer_read_is_named(tmp_path, monkeypatch):
    """وقراءةُ التذييل تُختم باسمها إن قُصِّرت وحدها (R83-2): `effort:low (footer)`."""
    _run_slice(tmp_path, {4000: [_reply("stop", _ROWS_OK)],
                          1600: [_reply("length", '{"debits"'),
                                 _reply("stop", _FOOTER_OK)]}, monkeypatch)

    rec = _record(tmp_path)
    assert rec.get("reasoning") == "effort:low (footer)", "الخانةُ تُسمّى: التذييلُ هو المقصوص"


def test_a_zero_budget_stops_before_the_first_request(tmp_path, monkeypatch):
    """R86-2 (P3): السقفُ يُسأل **قبل** القراءة ⇒ `--max-cost 0` لا يُرسل طلبًا واحدًا.

    وقبل الإصلاح: قرأ الصفحةَ كاملةً ثمّ توقّف (قِيس ~١٫٧ سنتًا على نسخةٍ من v2) — «حارسٌ لا يوقف».
    """
    sent = _run_slice(tmp_path, {4000: [_reply("stop", _ROWS_OK)],
                                 1600: [_reply("stop", _FOOTER_OK)]}, monkeypatch, cap="0")

    assert sent == [], "لا طلبَ فوق سقفٍ صفريّ"
    assert not list((tmp_path / "results").glob("pg-*.json")), "ولا سجلَّ لصفحةٍ لم تُقرأ"


def test_suite_guard_did_not_touch_the_sample(tmp_path, monkeypatch):
    """ولا تُكتب بياناتُ المستودع: القياسُ كلُّه في `--out` (وهو tmp_path)."""
    before = _SAMPLE.stat().st_mtime_ns
    _run_slice(tmp_path, {4000: [_reply("stop", _ROWS_OK)],
                          1600: [_reply("stop", _FOOTER_OK)]}, monkeypatch)

    assert _SAMPLE.stat().st_mtime_ns == before, "الملفُّ المتتبَّعُ لا يُمَسّ"
    assert sys.argv[0].endswith("scale_slice.py")     # الأداةُ لا تُعدّل `sys.argv` العامّ بلا داعٍ
