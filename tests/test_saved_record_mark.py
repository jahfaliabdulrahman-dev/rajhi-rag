"""العلامةُ في **السجلّ المحفوظ** — يُكتب بسطرٍ في القارئ ويُقرأ من الـJSON (R83-3 · قرارُ المالك 2026-10-03).

**ولماذا هكذا (بالاستبدال عند `urlopen`، لا فوق الناقل):** الاستبدالُ في طبقة الشبكة يُبقي
*منطقَ الإعادة الحقيقيّ* داخلَ القياس — فيُقاس السلوكُ كما يجري، لا نسخةً منه. وهذا لم يكن تفضيلًا
نظريًّا: تبيّن بالتجربة أنّ سقفَ الميزانية في الأداة **لا يمنع الطلبَ الأوّل** (`--max-cost 0` أنفق
١٫٧١ سنتًا)، فبرهانُ «صفرِ الكلفة» بالسقف باطلٌ — و**الاستبدالُ هنا هو الضمانةُ الوحيدة**.

**وما يقيسه:** سجلُّ الصفحةِ التي قُرئت صفوفُها بجوابٍ مقطوعٍ ثمّ مسقوف = يحمل العلامة · وسجلُّ
القراءة الافتراضيّة **كما هو** (لا مفتاحَ جديدًا) — وهذا هو نصُّ R81-3 الذي حرسه R83-3.

**والملفُّ يقيس اليوم بابين — وهو نصُّ التزام «أ» (مراجعة ٨٩: R89-3 · R89-4):**

- **بابُ العلامة (R87-1 · R83-2 · حالاتُه الثلاث):** الإعادةُ المقبولة **تُعيد حسابَ العلامة من
  قراءتها هي** — وما لم تُسقَف الإعادةُ ولا حُمِل تذييلٌ مسقوف ⇒ **تُحذف** العلامةُ (`pop`). وكان
  الإلحاقُ يُبقي علامةَ صفوفٍ **استُبدلت** صفوفُها بالإعادة (مقلوبُ «تضعها أو تحذفها»).
- **بابُ السقف (R89-3 · «فخُّ ص١٨٧»):** الحدُّ يقابل **ما صرفته هذه الجلسة** لا مجموعَ الكوربوس
  المحفوظ، **ويعدّ ثمنَ القراءة الفاشلة** أيضًا (محاولاتُها المدفوعة تُصرَف فعلًا).

**ولماذا نافذةُ صفحتين في الحاضنة:** القاعدتان لا تُقاسان على صفحةٍ واحدة: إعادةُ القراءة تُشترط
بـ`pg > first` (الصفحةُ الأولى لا جارَ لها)، **والسقفُ يُسأل بين الصفحات**. فالحاضنةُ تُهيّئ صورتين
وقصاصةَ صفحتين وتُهيّئ القطعةَ والصورةَ **قبل** التشغيل — والوحدتان السامّتان والنومُ المُبطَّل كما هما.
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


_ROW = '{{"movement": "{}", "balance": "{}", "desc": "قيد", "date": "2026-01-01"}}'


def _rows(movement: str, balance: str) -> str:
    """جوابُ صفوفٍ صالحٌ بمبلغٍ ورصيد — والسلسلةُ تُشتقّ من فرق الرصيدين (لا يُخمَّن اتجاه)."""
    return '{"rows": [' + _ROW.format(movement, balance) + ']}'


def _footer(debits: str, credits: str, balance: str) -> str:
    return ('{"debits": "%s", "credits": "%s", "balance": "%s"}'
            % (debits, credits, balance))


_ROWS_OK = _rows("10.00", "90.00")
_FOOTER_OK = _footer("10.00", "0.00", "90.00")
# **نافذةُ الحالات أ/ب/ج (صفحتان):** الأولى سليمةٌ ومطابقةٌ لإطارها ⇒ لا إعادةَ لها؛ والثانيةُ تُقرأ
# أوّلًا بمبلغٍ **يخالف دلتا إطارها** (٢٥٫٠٠ مقابل دلتا ١٠٫٠٠) ⇒ إعادةُ قراءةٍ تُشعَل، وتُقبل لأنّها
# تُطابق الدلتا والرصيدَ المطبوع (بلا شكوك).
_P2_DIVERGED = _rows("25.00", "65.00")          # ٦٥ = ٩٠ − ٢٥ … ودلتا الإطار تقول ١٠٫٠٠ ⇒ انزياح
_P2_FOOTER = _footer("20.00", "0.00", "80.00")  # دلتا الإطار: ٢٠٫٠٠ − ١٠٫٠٠ = ١٠٫٠٠
_P2_ACCEPTED = _rows("10.00", "80.00")          # ٨٠ = ٩٠ − ١٠ ⇒ تُطابق الدلتا (١٠٫٠٠) والرصيدَ المطبوع
# **ونافذةُ حالة السقف (د):** صفحةٌ ثانيةٌ سليمةٌ تمامًا (مبلغُها = فرقُ رصيدها عن السابقة،
# **واتجاهُها من السلسلة**: رصيدُها يرتفع ⇒ دائنٌ — فتُطابق دلتا الإطار في دائنها لا في مدينها).
_P2_OK = _rows("15.00", "105.00")
_P2_OK_FOOTER = _footer("10.00", "15.00", "105.00")
_SAMPLE = pathlib.Path("data/sample/statement_sample.pdf")


def _run_slice(out: pathlib.Path, seq: dict, monkeypatch, cap: str | None = None,
               *, pages: int = 1, pre_cache: dict | None = None):
    """يشغّل الأداةَ على نافذةٍ من `pages` صفحة، والردودُ تُختار بحسب `max_tokens`.

    (`max_tokens` ٤٠٠٠ = قراءةُ الصفوف — ومنها الإعاداتُ — و١٦٠٠ = قراءةُ التذييل؛ والقائمتان
    تُستهلَكان بترتيبهما الزمنيّ لكلّ نوع، فيصير ترتيبُ الطلبات نفسِه مُدخَلًا مقيسًا.)

    ويعيد قائمةَ `max_tokens` لكلّ طلبٍ أُرسل — فارغةٌ تعني أنّ الأداةَ لم تُرسل شيئًا.

    **والحاضنةُ تُهيّئ نافذةً كاملةً لتُقاس حالاتُها (R89-4):** القاعدتان تحتاجان صفحةً ثانية
    (الإعادةُ تُشترط بـ`pg > first`، والسقفُ يُسأل بين الصفحات) — وإضافةُ `--count 2` بلا صورةٍ
    ثانية تُشغّل `convert_from_path` الحقيقيَّ (وهو سامٌّ هنا عن قصد).

    **`pre_cache`** = سجلاتُ صفحاتٍ تُكتَب **قبل** التشغيل (مفتاحُها رقمُ الصفحة) — لقياس «تاريخُ
    الكاش لا يُعدّ»: صفحةٌ مخزّنةٌ بكلفةٍ تاريخيّةٍ كبيرة والسقفُ دونها.

    **ولا تخطّيَ لـ`pypdf`/`pdf2image` هنا أبدًا (R86-1 · الشقُّ (ب)):** يُستورَدان داخل `main()`،
    ولكلٍّ فرعٌ مُتجاوَزٌ إذا وُجد ملفُّه ⇒ فتُهيَّأ القصاصةُ والصورةُ **قبل** التشغيل، وتُحقَن وحدةٌ
    **سامّةٌ** مكانهما: إن استُدعيت إحداهما سقط الضابطُ **باسم السبب**. (والتخطّي المُعلَن محفوظٌ
    للتبعيّات التي **تُستورَد** فعلًا — `PIL` و`numpy` — حيث تصحّ `importorskip`.)
    """
    pil = pytest.importorskip("PIL", reason="الصفحةُ المُسبقةُ تُصنع بها")
    pytest.importorskip("numpy", reason="بوّابةُ الصفحة تحسب الحبرَ بها")
    scale = pytest.importorskip("tools.scale_slice")
    # **R87-2: النومُ يُبطَّل ولا يُنتظَر (قِيس 10.14 و10.02 ث لكلّ تشغيلِ CI):** القارئُ ينام في
    # مسارِ إعادةِ الطلب ⇒ يُستبدَل `sleep` في وحده، كما في ضابط الناقل — فتُقاس المحاولاتُ ولا تُؤخّر.
    import statement_qa.vlm_reader as _vr  # noqa: PLC0415
    monkeypatch.setattr(_vr.time, "sleep", lambda *_a, **_k: None)
    # **ولا `importorskip` لـ`pypdf`/`pdf2image` (R86-1 · الشقُّ (ب)):** يُستورَدان **داخل `main()`**،
    # ولكلٍّ منهما فرعٌ مُتجاوَزٌ إذا وُجد ملفُّه ⇒ فتُهيَّأ القصاصةُ والصورةُ **مسبقًا**، وتُحقَن وحدةٌ
    # **سامّةٌ** مكانهما: إن استُدعيت واحدةٌ منهما سقط الضابطُ **باسم السبب** — فلا **يُتخطّى** الحارسُ
    # في بيئة الـCI (وهو ما كان يُحمّر خطوتَها)، ولا يسقط على تبعيّةٍ لا يحتاجها.
    (out / "pages").mkdir(parents=True, exist_ok=True)
    for n in range(1, pages + 1):
        pil.Image.new("RGB", (900, 1200), "white").save(out / "pages" / f"pg-{n:03d}.png")
    (out / f"slice_{pages}p.pdf").write_bytes(b"%PDF-1.4\n% guard calibration stub\n")
    if pre_cache:
        (out / "results").mkdir(parents=True, exist_ok=True)
        for pg, rec in pre_cache.items():
            (out / "results" / f"pg-{pg:03d}.json").write_text(
                json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    def _poison(*_a, **_k):
        raise AssertionError("لم يكن ينبغي استدعاءُ مكتبة PDF: الصفحةُ والقصاصةُ مُهيَّأتان مسبقًا")

    for _name, _attrs in (("pypdf", ("PdfReader", "PdfWriter")),
                          ("pdf2image", ("convert_from_path",))):
        monkeypatch.setitem(sys.modules, _name,
                            types.SimpleNamespace(**{a: _poison for a in _attrs}))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-not-a-real-key")
    argv = ["scale_slice.py", "--source", str(_SAMPLE), "--first", "1", "--count", str(pages),
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


def _record(out: pathlib.Path, page: int = 1) -> dict:
    files = sorted((out / "results").glob("pg-*.json"))
    assert files, f"لا سجلَّ في {out}/results"
    one = out / "results" / f"pg-{page:03d}.json"
    assert one.exists(), f"لا سجلَّ للصفحة {page} (والموجود: {[f.name for f in files]})"
    return json.loads(one.read_text(encoding="utf-8"))


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


# ————— الحالاتُ الخمس (R89-4 · التزام «أ»): نافذةُ صفحتين — كلٌّ يسقط على ما قبل الإصلاح —————

def _two_page_seq(rows_plan: list, footer_plan: list) -> dict:
    """تسلسلُ نافذةِ صفحتين: صفحةٌ أولى سليمةٌ ثابتةٌ + تسلسلُ الثانية كما يُمرَّر."""
    return {4000: [_reply("stop", _ROWS_OK)] + rows_plan,
            1600: [_reply("stop", _FOOTER_OK)] + footer_plan}


def test_case_a_a_capped_first_read_of_the_page_leaves_no_mark(tmp_path, monkeypatch):
    """(أ) قراءةُ الصفحة الثانية الأولى تُقطع ثمّ تُسقَف، **والإعادةُ افتراضيّة** ⇒ **لا مفتاحَ `reasoning`**.

    ولماذا: العلامةُ تصف **ما بقِي في السجلّ**، والصفوفُ المسقوفةُ استُبدلت بصفوف الإعادة (R87-1)
    ⇒ فعلامتُها تذهب معها. وعلى ما قبل الإصلاح يبقى `effort:low` لقراءةٍ لم تُحفظ.
    """
    sent = _run_slice(tmp_path, _two_page_seq(
        [_reply("length", '{"rows": [{"movement"'),
         _reply("stop", _P2_DIVERGED),
         _reply("stop", _P2_ACCEPTED)],
        [_reply("stop", _P2_FOOTER)]), monkeypatch, pages=2)

    rec = _record(tmp_path, 2)
    assert "reasoning" not in rec, \
        f"إعادةٌ افتراضيّةٌ محت صفوفًا مسقوفة ⇒ لا علامةَ باقية (والمقروء: {rec.get('reasoning')!r})"
    assert sent == [4000, 1600, 4000, 4000, 1600, 4000], \
        "تسلسلُ الطلبات: قطعةٌ + مسقوفة + تذييل + إعادةٌ افتراضيّة"
    assert rec.get("reread"), "والإعادةُ قُبلت فعلًا (وإلّا فالحالةُ لم تُشعَل أصلًا)"


def test_case_b_a_capped_reread_is_named_once(tmp_path, monkeypatch):
    """(ب) وكذلك، **والإعادةُ تُقطع ثمّ تُسقَف** ⇒ `effort:low` — لا `effort:low + effort:low`.

    والعلّةُ المقيسة: الإلحاقُ القديم كان يجمع علامتَين لقراءةٍ واحدة (الأولى استُبدلت صفوفُها).
    """
    _run_slice(tmp_path, _two_page_seq(
        [_reply("length", '{"rows": [{"movement"'),
         _reply("stop", _P2_DIVERGED),
         _reply("length", '{"rows": [{"movement"'),
         _reply("stop", _P2_ACCEPTED)],
        [_reply("stop", _P2_FOOTER)]), monkeypatch, pages=2)

    rec = _record(tmp_path, 2)
    assert rec.get("reasoning") == "effort:low", \
        f"علامةُ الإعادة وحدَها (لا جمعٌ مع علامةِ قراءةٍ استُبدلت): {rec.get('reasoning')!r}"
    assert "+" not in rec.get("reasoning", ""), "لا إلحاقَ علامتَين لقراءةٍ واحدة"


def test_case_c_a_capped_footer_is_carried_through_the_reread(tmp_path, monkeypatch):
    """(ج) صفوفُ الثانية **وتذييلُها** كلٌّ يُقطع ثمّ يُسقَف، **والإعادةُ افتراضيّة** ⇒ `effort:low (footer)`.

    ولماذا يُحمَل التذييل: الإعادةُ لا تُعيد قراءةَ التذييل ⇒ فعلامتُه وحدَها تبقى صادقةً.
    """
    _run_slice(tmp_path, _two_page_seq(
        [_reply("length", '{"rows": [{"movement"'),
         _reply("stop", _P2_DIVERGED),
         _reply("stop", _P2_ACCEPTED)],
        [_reply("length", '{"debits"'),
         _reply("stop", _P2_FOOTER)]), monkeypatch, pages=2)

    rec = _record(tmp_path, 2)
    assert rec.get("reasoning") == "effort:low (footer)", \
        f"التذييلُ مسقوفٌ ولم يُعَد قراءتُه ⇒ يُسمّى في العلامة (والمقروء: {rec.get('reasoning')!r})"


def test_case_d_a_cached_history_does_not_stop_a_live_run(tmp_path, monkeypatch):
    """(د) الصفحةُ الأولى مخزّنةٌ بكلفةٍ **تاريخيّةٍ** كبيرة وحدٌّ دونها ⇒ **تُقرأ الثانية**.

    والعلّةُ (فخُّ ص١٨٧): كان الفحصُ يقابل `usage_total` — وهو يجمع كلفةَ الصفحاتِ المستأنَفةِ
    المحفوظةَ أيضًا — بسقفِ **الجلسة** ⇒ فيتوقّف تشغيلٌ مجّانيٌّ بلا طلبٍ واحد.
    """
    pre = {"pg": 1, "page_no": 1, "ms_read": 1, "ms_footer": 1,
           "raw_rows": [json.loads(_ROW.format("10.00", "90.00"))],
           "footer": {"debits": "10.00", "credits": "0.00", "balance": "90.00", "raw": {}},
           # كلفةٌ تاريخيّةٌ من تشغيلةٍ سابقة — لها سجلُّها ولا تُصرَف في هذه الجلسة
           "usage": {"calls": 1, "cost": 5.0}}
    sent = _run_slice(tmp_path, {4000: [_reply("stop", _P2_OK)],
                                 1600: [_reply("stop", _P2_OK_FOOTER)]},
                      monkeypatch, cap="1", pages=2, pre_cache={1: pre})

    assert sent == [4000, 1600], \
        f"صفحةٌ مخزّنةٌ بكلفةٍ تاريخيّةٍ لا تُصرف في هذه الجلسة ⇒ لا تُوقف الحدّ (أُرسل: {sent})"
    rec = _record(tmp_path, 2)
    assert rec.get("usage", {}).get("cost", 0) > 0, "والثانيةُ قُرئت فعلًا (لها كلفةُ جلسة)"


def test_case_e_a_failed_read_is_charged_against_the_cap(tmp_path, monkeypatch):
    """(هـ) الصفحةُ الأولى تُقطع مرّتين فتفشل بعد **طلبين مدفوعين**، والحدُّ دون ثمنهما ⇒ لا طلبَ للثانية.

    وهذه هي R89-3: كانت كلفةُ القراءة الفاشلة تُكتَب في سجلّ الصفحة ولا تُضاف إلى كلفة الجلسة ⇒
    فالحدُّ لا يراها (قِيس: بحدٍّ دون ثمن المحاولتين صُرف ثمنُهما والسطرُ يقول `live $0.0000`).
    """
    sent = _run_slice(tmp_path, {4000: [_reply("length", '{"rows": [{"movement"', cost=0.011)],
                                 1600: [_reply("stop", _FOOTER_OK)]},
                      monkeypatch, cap="0.02", pages=2)

    assert sent == [4000, 4000], \
        f"محاولتان مدفوعتان بلغتا السقف ⇒ لا يُرسَل طلبٌ ثانٍ للصفحة التالية (أُرسل: {sent})"
    assert not (tmp_path / "results" / "pg-002.json").exists(), "ولا سجلَّ لصفحةٍ لم تُقرأ"
    failed = _record(tmp_path, 1)
    assert failed.get("error"), "والصفحةُ الأولى سجّلت فشلَها باسمه"
