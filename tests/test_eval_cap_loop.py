"""ضابطٌ **سلوكيّ** لحلقة السقف — يشغّل `run_questions` نفسَها بمزوّدٍ مُحاكى (صفرُ صرف) ويسأل:

    هل توقّفت الحلقة؟ وأين؟ وبأيّ رمز خروج؟

مراجعة ٥١ · البند «قبل أي صرف»: «ضابطاه يفحصان الدالة ونص المصدر **لا التوقف**. رفعتُ عتبة التوقف ألف
ضعف فبقيت الاختبارات الـ٦٠٨ خضراء.» ⇒ هذا الملفّ يقيس **التوقّفَ في الحلقة**، ويرسب إذا رُفعت العتبة
أو نُزع `break` أو صار التوقّفُ يُعاد بـ0. (الاختبارُ لا يمسّ الشبكة: كلُّ نداءات المزوّد مُستبدَلة.)

**ومراجعة ٥٢ أضافت ضابطين بنفس الطريقة** (سلوكًا لا نصًّا): تغطيةٌ واحدة من **رصيدٍ غير صفريّ** (R52-4 ·
كان يبدأ من صفر فتصحّ فيه المقارنةُ العائمة بالمصادفة)، وسجلٌّ يحمل **الأثرَ كاملًا** وطولَه (R52-3 · كان
الحارسُ نصًّا يُقاس بتهجئة العلّة).
"""

import importlib.util
import json
import threading

import pytest
import pathlib
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Meter:
    """عدّادُ مزوّدٍ مُحاكى: يُقرأ **قبل كلّ سؤال**، وكلفةُ كلّ نداءٍ `per_call`، ويتأخّر `lag` نداءً.

    و`base` = رصيدُ مفتاحٍ **غيرُ صفريّ**: عدّادُ OpenRouter الحقيقيّ لا يبدأ من صفر، والفروقُ العائميّة
    تنشأ من طرح أرقامٍ كبيرة (مقيس: قراءتان من رصيد ٢٨٩ مجموعهما `0.6 + 2.27e-14` ⇒ تبدو تجاوزًا).
    """

    def __init__(self, per_call: float, lag: int = 0, reverse: bool = False, base: float = 0.0):
        self.per_call, self.lag, self.reverse, self.calls = per_call, lag, reverse, 0
        self.base = base

    def read(self):
        shown = max(0, self.calls - self.lag) * self.per_call
        if self.reverse:
            shown = -abs(shown)
        return {"usage": self.base + shown, "limit": 999.0}


class _Ans:
    answer, used_row_nos, scope, refused = "جوابٌ مُحاكى", [1], "ok", False


class _Reply:
    """ردُّ نموذجٍ مُحاكى **بالشكل الذي يقرأه `finish_reasons_from`**: `generations` ثمّ `llm_output`.

    و`ردٌّ = نداءٌ واحد` — وهو العدُّ الذي صار يحمل السعر (R113-1) بدل أرضية «الأدوات + ١».
    """

    def __init__(self, reason: str = "stop") -> None:
        self.generations = [[types.SimpleNamespace(generation_info={"finish_reason": reason})]]
        self.llm_output = {"finish_reason": reason}


class _ExpiredThread:
    """خيطٌ **يعمل فعلًا ثمّ يُعلن نفسَه حيًّا**: النداءاتُ وقعت (فالرموزُ تُحتسب) والمهلةُ انتهت قبل جمعها.

    لماذا لا `time.sleep`: النومُ يجعل الضابطَ رهينةَ الزمن وسباقًا على القراءة، وهذا يحمل المعنى نفسه
    بحتميّة: **كلُّ نداءٍ وقع وبُرمج عليه**، والنتيجةُ تُقرأ «انتهت المهلة» (`res = None` ⇒ أثرٌ فارغ)
    — وهو بالحرف سيناريو مراجعة ١١٣.
    """

    def __init__(self, target=None, args: tuple = (), kwargs=None, daemon=None) -> None:   # noqa: ANN001
        self._t, self._a, self._k = target, tuple(args), kwargs or {}

    def start(self) -> None:
        self._t(*self._a, **self._k)

    def join(self, timeout=None) -> None:                                         # noqa: ANN001
        return None

    def is_alive(self) -> bool:
        return True


def _questions_file(tmp_path) -> pathlib.Path:
    """ملفُّ أسئلةٍ صغيرٌ في `tmp` — فلا يُتخطّى الضابطُ أبدًا (ضابطٌ متخطّى ثقب، لا ضابط)."""
    p = tmp_path / "questions.json"
    p.write_text(json.dumps({"questions": [{"id": f"q{i:02d}", "q": f"س{i}", "type": "count_rows",
                                            "cat": "count", "metric": "مُحاكى", "expect": "…",
                                            "derive": {"kind": "mock"}} for i in range(1, 9)]},
                            ensure_ascii=False), encoding="utf-8")
    return p


def _run(tmp_path, monkeypatch, meter: _Meter, budget: float, n: int = 8,
         rows_n: int = 1, used: list[int] | None = None, calls_for: dict[str, int] | None = None,
         tools_for: dict[str, int] | None = None, expire_on: set[str] | None = None,
         late: tuple[int, int] | None = None, no_replies: bool = False):
    """تشغيلُ `run_questions` بمزوّدٍ مُحاكى. و`calls_for` = نداءاتُ سؤالٍ بعينه (والافتراضُ نداءٌ واحد)،
    و`tools_for` = أدواتُ أثرِه · و`expire_on` = أسئلةٌ **تنتهي مهلتُها** (خيطٌ يعمل ثمّ يُعلن نفسَه حيًّا)،
    و`late = (بعدَ أيّ سؤال, كم نداءً)** = رموزٌ تصل **بين النافذتين** (خيطٌ مُتخلّى عنه يردّ متأخّرًا).
    """
    m = _load("evalq_cap_loop", "tools/eval_questions.py")
    import tools.refusal_test as rt
    from statement_qa import chunking, qa, retriever

    monkeypatch.setattr(rt, "build_rows",
                        lambda run: ([{"row_no": i + 1, "text": "س", "page": 1} for i in range(rows_n)], 1))
    monkeypatch.setattr(chunking, "chunk_rows", lambda rows: [{"text": "س", "row_no": 1}])
    monkeypatch.setattr(retriever, "build_index", lambda chunks: object())
    # **ومراكنبُ المكتبة تُرصَد فعلًا (R113-1):** `build_llm` يُخزّن ما مُرِّر إليه من `callbacks`،
    # وكلُّ نداءٍ مُحاكى يُطلق `on_llm_end` مرّةً واحدة ⇒ فيُعدّ سجلُّ الانتهاء **الردودَ** كما يفعل
    # في المسار الحقيقيّ (مسباري: طلبان ⇒ مدخلان)، لا أرضيةَ الأدوات.
    seen: dict = {"cbs": []}

    def _build_llm(model=None, callbacks=None):
        seen["cbs"] = list(callbacks or [])
        return None

    monkeypatch.setattr(qa, "build_llm", _build_llm)

    def _fire(reason: str = "stop", times: int = 1) -> None:
        if no_replies:            # **مراقبٌ غيرُ موصول**: النداءاتُ تقع ولا يُرصد لها ردّ (R113-1)
            return
        for _ in range(times):
            for cb in seen["cbs"]:
                cb.on_llm_end(_Reply(reason))

    # **ورموزُ المزوّد المُحاكى (R112-1):** كلُّ نداءٍ يُضيف **مليونَ رمزٍ مدخلًا**، وبسعرٍ مُعلَن
    # `$0.30/M` تصير كلفةُ النافذة **$0.30 لكلّ نداء** — وعددُ نداءات السؤال يُضبط بـ`calls_for`.
    snap = {"n": 0}

    def _snap(_h):
        snap["n"] += 1
        if late and snap["n"] == 2 * late[0] + 1:   # نافذةُ السؤال التالي تُفتح: الرموزُ المتأخّرة تصل هنا
            meter.calls += late[1]
            _fire("stop", late[1])
        return {"mock": {"input_tokens": meter.calls * 1_000_000, "output_tokens": 0}}

    monkeypatch.setattr(m, "usage_snapshot", _snap)
    if used is not None:                     # أثرٌ بحجمٍ محدَّد (لضابط القصّ) — يُرجَع تلقائيًّا
        monkeypatch.setattr(_Ans, "used_row_nos", list(used))

    def _answer(store, qtext, rows=None, chunks=None, llm=None, footers=None, scope=None):
        k = int((calls_for or {}).get(qtext, 1))
        meter.calls += k                      # الكلفةُ تُحتسب عند النداء — كما يفعل المزوّد
        _fire("tool_calls" if k > 1 else "stop", k)
        t = int((tools_for or {}).get(qtext, 0))     # أثرُ السؤال: ٢٤ أداةً لسؤالٍ بـ٢٥ نداءً مُجاب
        return types.SimpleNamespace(answer=_Ans.answer,
                                     used_row_nos=list(used) if used is not None else list(_Ans.used_row_nos),
                                     scope=_Ans.scope, refused=_Ans.refused,
                                     tools_used=[f"tool{j}" for j in range(t)])

    monkeypatch.setattr(qa, "answer_question", _answer)
    monkeypatch.setattr(m, "_key_usage", meter.read)
    monkeypatch.setattr(m, "truth", lambda q, c, pack, rows: ({"kind": "مُحاكى"}, "مُحاكى"))
    monkeypatch.setattr(m, "score_answer", lambda q, t, ans, res, rows: (True, "ok"))
    if expire_on:                        # خيطٌ يعمل ثمّ يُعلن نفسَه حيًّا ⇒ النتيجةُ «انتهت المهلة»
        class _T(_ExpiredThread):        # **ولا يُتخلّى إلا عن الأسئلة المسمّاة** (غيرُها يجمع نتيجته)
            def is_alive(self) -> bool:
                return self._a[0] in expire_on

        # `eval_questions` تستورد `threading` **داخل الدالّة** ⇒ الرَقْمُ يجري على الوحدة نفسِها
        # (‏`sys.modules`) لا على صفةٍ في وحدة الأداة (أوّلُ فرضٍ سقط بالقياس: `no attribute 'threading'`).
        monkeypatch.setattr(threading, "Thread", _T)
    qs = [{"id": f"q{i:02d}", "q": f"س{i}", "type": "count_rows", "cat": "count", "metric": "مُحاكى",
           "expect": "…", "derive": {"kind": "mock"}} for i in range(1, n + 1)]
    a = types.SimpleNamespace(
        run=ROOT / "data/local_sample/slice_629p", model=None, out=tmp_path / "answers.json",
        budget=budget, timeout=5, only=None, questions=_questions_file(tmp_path), rescore=False,
        execute=False,
        # **والسعرُ صريحٌ من سطر الأمر (R112-1):** $0.30 للمليون مدخلًا ومخرجًا ⇒ فكلفةُ نداءٍ
        # واحدٍ $0.30 بالضبط. **وبلا سطرِ الأمر يُقرأ السعرُ من قائمة النماذج العامّة** — والضابطُ
        # لا يمسّ الشبكة بحال.
        price_in_per_m=0.30, price_out_per_m=0.30)
    rc = m.run_questions(a, qs, None, {}, {})
    out = tmp_path / "answers.json"
    saved = json.loads(out.read_text()) if out.exists() else {}
    return rc, saved.get("results", [])


def test_the_cap_stops_the_loop_with_an_instant_meter(tmp_path, monkeypatch):
    """**والأرقامُ أُعيدت في R110-1 لأنّ قاعدةَ القرار تغيّرت:** صار الإيقافُ الاستباقيُّ يقارن
    **سقفَ السؤال التالي** (حدُّ نداءاته من بنية المسار × كلفةِ النداء × الهامش = ٠٫٣٠ × ٣٦ × ١٫٥
    = **١٦٫٢**) لا أعلى ما رُئي. فالسقفُ الماليُّ الذي يسمح بسؤالين صار **١٦٫٥٠** (١٦٫٢ + ٠٫٣٠)،
    وبـ٠٫٦٠ كان القياسُ يتوقّف قبل السؤال الثاني بحقّ — **وليس ذلك عطبًا بل شرطُ القرار**:
    «سقفٌ لا يُخترق ولو قلّت التغطية».
    """
    rc, results = _run(tmp_path, monkeypatch, _Meter(0.30), 16.50)
    assert len(results) == 2, f"لم تتوقّف الحلقة عند السقف: طُرح {len(results)} سؤالاً"
    assert rc == 3, f"التوقّفُ بالسقف يجب أن يُقرأ رمزًا غيرَ صفريّ لا {rc}"


def test_a_lagging_meter_no_longer_moves_the_decision(tmp_path, monkeypatch):
    """**R112-1 · وما كان قياسًا في R110-1 صار مُبطَلًا بقياس:** العدّادُ المتأخّرُ نداءً واحدًا كان
    يسمح بنداءٍ زائدٍ واحدٍ (**ثلاثةٌ** بدل اثنين على الميزانية نفسها) لأنّ سعرَ النداء كان يُستنتَج
    **منه**. وقد صار السعرُ يُشاهَد من **رموز الردود** ⇒ **فالتأخّرُ لا يُحرّك القرار**: نفسُ التغطية
    (٢) مع عدّادٍ لحظيّ ومع عدّادٍ متأخّر — وهو الفرقُ المطلوبُ في مراجعة ١١٢ (رصيدُ الحساب شاهدٌ على
    مجموع الجولة، لا سعرٌ يحكم). **والمتأخّرُ يبقى مقروءًا:** رصيدُه يُسجَّل لكلّ سؤال (`meter_delta_usd`)
    ولا يدخل القانون.
    """
    d1 = tmp_path / "live"
    d1.mkdir(exist_ok=True)
    rc_live, live = _run(d1, monkeypatch, _Meter(0.30), 16.50)
    d2 = tmp_path / "lagging"
    d2.mkdir(exist_ok=True)
    rc_lag, lag = _run(d2, monkeypatch, _Meter(0.30, lag=1), 16.50)
    assert (rc_live, len(live)) == (3, 2), f"العدّادُ اللحظيّ: رمز {rc_live} وتغطية {len(live)} بدل 3/2"
    assert (rc_lag, len(lag)) == (3, 2), (
        f"التأخّرُ حرّك القرار (رمز {rc_lag} وتغطية {len(lag)}) ⇒ السعرُ ما زال يُستنتَج من العدّاد")


def test_a_reverse_meter_halts_and_does_not_read_as_success(tmp_path, monkeypatch):
    """عدّادٌ تراجعيّ ⇒ **وقوفٌ مُسمّى برمز 4**، ولا يُقرأ «نجاحًا» في أيّ أتمتة (مراجعة ٥١ · البند ٥)."""
    rc, results = _run(tmp_path, monkeypatch, _Meter(0.30, reverse=True), 0.60)
    assert rc == 4, f"التوقّفُ عند عدّادٍ تراجعيّ يجب أن يكون 4 لا {rc}"
    assert len(results) == 1, f"يجب أن يتوقّف قبل السؤال الثاني لا بعد {len(results)}"


def test_without_a_budget_the_loop_is_not_capped(tmp_path, monkeypatch):
    """**الضابطُ الموجب**: بلا ميزانيةٍ يمرّ كلُّ السؤال — فلا يكون «التوقّف» أثرَ عطبٍ آخر."""
    rc, results = _run(tmp_path, monkeypatch, _Meter(0.30), 0)
    assert len(results) == 8, f"بلا سقفٍ يجب أن تُطرح الثمانية، طُرق {len(results)}"
    assert rc == 0, f"بلا سقفٍ ولا فشلٍ ⇒ 0، صار {rc}"


def test_a_nonzero_meter_baseline_gives_the_same_coverage(tmp_path, monkeypatch):
    """**السقفُ يُقاس بالسنتات لا بمصادفةٍ عشريّة** (مراجعة ٥٢ · R52-4).

    الضابطُ السابق كان يبدأ من **صفر** فتصحّ فيه المقارنةُ العائمة بالمصادفة ⇒ «سؤالان». ومن رصيدٍ واقعيّ
    (مقيس: ٢٨٩ · ٢٨٦٫٥) كان التوقّفُ الاستباقيّ يُطلق **سؤالًا مبكّرًا** (١ بدل ٢) لأنّ
    `0.6 + 2.27e-14 > 0.6`. فالمقارنةُ صارت بالسنتات: نفسُ التغطية من أيّ رصيد.
    """
    for base in (0.0, 289.0, 286.5, 1000, 12345.678):
        # **شاهدٌ منفصلٌ لكلّ رصيد**: ضابطٌ يُعيد استعمال المجلّد نفسَه **يستأنف** أجوبةَ الضابط
        # السابق (`done` من `answers.json`) فيقرأ تغطيةً مركّبة — قِيس: ٤ بدل ٢. لا يُقاس ضابطان بيتٌ واحد.
        d = tmp_path / f"base_{base}"
        d.mkdir(exist_ok=True)
        rc, results = _run(d, monkeypatch, _Meter(0.30, base=base), 16.50)
        assert (rc, len(results)) == (3, 2), f"رصيد {base}: رمز {rc} وتغطية {len(results)} بدل 3/2"


def test_the_stored_record_carries_the_whole_trace_and_its_length(tmp_path, monkeypatch):
    """**القصُّ في الكاتب يُقاس بالسلوك لا بتهجئة النصّ** (مراجعة ٥٢ · R52-3).

    الحارسُ السابق كان `assert "or [])[:40]" not in src` — يقيس **نصَّ العلّة** لا العلّة: نفسُها
    بمسافةٍ واحدة تمرّ (مقيس: ٦٢١/٦٢١)، والقصُّ في السجلّ وحده يمرّ كذلك. هذا الضابطُ يُشغّل
    `run_questions` نفسَها بأثرٍ مُحاكى **٤٥ صفًّا** ويطالب السجلَّ بثلاثةٍ معًا: الطولَ كاملًا،
    وهويّة `trace_len == len(used_row_nos)`، والصفحاتِ المستشهدة من الأثر نفسه.
    """
    used = list(range(1, 46))
    rc, results = _run(tmp_path, monkeypatch, _Meter(0.30), 0.60, n=1, rows_n=45, used=used)
    assert rc == 0 and len(results) == 1, f"سؤالٌ واحدٌ متوقّع، طُرق {len(results)} برمز {rc}"
    rec = results[0]
    assert len(rec["used_row_nos"]) == 45, f"السجلُّ مقصوص: {len(rec['used_row_nos'])} من ٤٥"
    assert rec["trace_len"] == len(rec["used_row_nos"]) == 45, "هويّةُ trace_len انكسرت"
    assert rec["cited_pages"] == [1], f"الصفحاتُ المستشهدة ليست من الأثر: {rec['cited_pages']}"


def test_the_anticipatory_stop_decides_by_the_next_questions_ceiling(tmp_path, monkeypatch):
    """**R110-1 · القرارُ بالحدّ لا بالماضي — ويُقاس باتّجاهين بمزوّدٍ واحد:**
    نفسُ المزوّد ونفسُ الأسئلة، والفرقُ في متسع الميزانية فقط ⇒ **سؤالان** إن غطّى السقفُ الماليُّ
    سقفَ السؤال التالي، و**واحدٌ** إن لم يغطّه. ولو كان القرارُ بأعلى ما رُئي (وهو ٠٫٣٠ في الحالين)
    لحُوكم الحالان حكمًا واحدًا — فالضابطُ يفصل القاعدتين.
    """
    from statement_qa.qa import question_ceiling

    ceiling_next = 0.30 * question_ceiling("س1") * 1.5          # كلفةُ النداء × حدُّ السؤال × الهامش
    assert question_ceiling("س1") == 36, question_ceiling("س1")

    # **وشاهدٌ منفصلٌ لكلّ حال** (ضابطٌ يعيد استعمال المجلّد يستأنف أجوبةَ الضابط السابق — قِيس في R52-4)
    d_rich, d_poor = tmp_path / "rich", tmp_path / "poor"
    d_rich.mkdir(exist_ok=True)
    d_poor.mkdir(exist_ok=True)
    # **والفارقُ عشرةُ سنتاتٍ لا جزءٌ من مليار:** المقارنةُ بالسنتات بتسامحٍ مُعلَن (≤٠٫٥ سنت في
    # `tools/spend`)، ففرقٌ أدقُّ منها يُقرأ «مساويًا» ولا يفصل القاعدتين.
    rc_rich, rich = _run(d_rich, monkeypatch, _Meter(0.30), ceiling_next + 0.30 + 0.10)
    rc_poor, poor = _run(d_poor, monkeypatch, _Meter(0.30), ceiling_next + 0.30 - 0.10)

    assert (rc_rich, len(rich)) == (3, 2), f"ميزانيةٌ تغطّي السقفَ يجب أن تطرح سؤالين لا {len(rich)}"
    assert (rc_poor, len(poor)) == (3, 1), f"ميزانيةٌ لا تغطّيه يجب أن تتوقّف بعد سؤالٍ لا {len(poor)}"
    # **والسقفُ يُسجَّل كما حُوكم به:** السؤالُ الثاني حُكم بسقفٍ = ما حسبته هذه الملفّ من الكود،
    # **وبالسعر المشهود من الرموز** (R112-4: حقلٌ واحد لكلّ معنى — والحقلُ المكرَّرُ `next_ceiling_usd`
    # أُزيل لأنّه كان يُحسب من الوسائط نفسِها في الدورة نفسِها).
    assert rich[1]["cap_bound_usd"] == pytest.approx(ceiling_next, rel=1e-6), rich[1]
    assert rich[1]["cap_price_usd"] == pytest.approx(0.30, rel=1e-6), rich[1]
    assert rich[1]["cap_price_source"] == "observed-tokens", rich[1]
    assert "next_ceiling_usd" not in rich[1], "الحقلُ المكرَّرُ عاد إلى السجلّ"


def test_a_timed_out_question_prices_its_calls_not_its_window(tmp_path, monkeypatch):
    """**R113-1 · أحمرُ أوّلًا: سؤالٌ تنتهي مهلتُه يُسعَّر نداؤه بنافذته كلِّها فتتوقّف الجولة.**

    الآليّة (مراجعة ١١٣، من الكود): عند المهلة `res = None` ⇒ أثرٌ فارغ ⇒ أرضيةُ النداءات **١**
    ⇒ `per_call = كلفةُ النافذة كلِّها` ⇒ `× 36 × 1.5` = سقفٌ أكبرُ من أيّ ميزانية معقولة.

    **وهذا الضابطُ هو سيناريو المراجعة نفسُه بمقياس هذا الملفّ:** السؤالُ الثالث ينادي النموذجَ **٢٥
    مرّة** (‏$7.50 برموز المُحاكي) **ثمّ تنتهي مهلتُه** — والسؤالُ الذي أُجيب بـ٢٥ نداءً يُقارَن به.

    | | التغطية | سعرُ النداء بعده | التوقّف |
    | :--- | :--- | :--- | :--- |
    | **قبل الإصلاح** | **٣ من ٦** | نافذةُ المهلة كلُّها ($7.50) | سقفُ السؤال الرابع **$405** ⇒ توقّفٌ مُسمّى (رمز ٣) |
    | **بعد الإصلاح** | **٦ من ٦** | **$0.30 كحالِ الجواب** | **لا توقّفَ بالسقف** — ورمزُ الخروج **١** لأنّ جوابَ السؤال نفسه سقط بمهلته (وهو غيرُ التوقّف) |

    ⇒ فالرموزُ نفسُها والنداءاتُ نفسُها، **والفرقُ الوحيد أنّ الأداةَ تخلّت عن السؤال** — فلا يجوز أن
    يغيّر ذلك السعر. والمهلةُ وقعت في **خمسينَين من آخر أربع جولات** (‏`r105` السؤال ٤ · `r108` السؤال ٣٠)
    ⇒ فلا يُدفع قبل هذا الإصلاح.
    """
    d = tmp_path / "expired"
    d.mkdir(exist_ok=True)
    rc, results = _run(d, monkeypatch, _Meter(0.30), 25.0, n=6,
                       calls_for={"س3": 25}, expire_on={"س3"})
    assert rc != 3, (f"توقّفَت الجولةُ بالسقف بعد سؤالٍ انتهت مهلتُه (رمز {rc} · تغطية {len(results)} "
                     f"من 6) ⇒ سعرُ النداء صار كلفةَ نافذته كلَّها")
    assert rc == 1, f"المتوقَّعُ ١ (جوابٌ سقط بمهلته) لا {rc}"
    assert len(results) == 6, f"التغطيةُ {len(results)} من 6 بعد مهلةِ سؤالٍ"
    timed_out = results[2]
    assert timed_out["why"].startswith("عطبٌ/مهلة"), timed_out["why"]
    assert timed_out["replies_observed"] == 25, timed_out
    assert timed_out["tools_in_trace"] == 0, "الأثرُ فارغٌ عند المهلة (وهو مصدرُ العطب)"
    # **والمُهِمُّ: السعرُ لم يقفز** — سعرُ القرار الرابع كسعر القرار الثاني (كلاهما نداءٌ بـ$0.30).
    assert results[3]["cap_price_usd"] == pytest.approx(results[1]["cap_price_usd"], rel=1e-9), (
        results[1]["cap_price_usd"], results[3]["cap_price_usd"])
    assert results[3]["cap_price_usd"] == pytest.approx(0.30, rel=1e-6), results[3]["cap_price_usd"]


def test_a_question_that_answers_with_the_same_calls_prices_the_same(tmp_path, monkeypatch):
    """**والضابطُ المضادّ (حتى لا يمرّ الإصلاحُ بإلغاء السعر):** السؤالُ نفسُه بـ٢٥ نداءً **مُجابًا**
    يُنتج السعرَ نفسَه — فلا يكون «لا توقّف» أثرَ سعرٍ صفريّ، بل سعرٌ صحيحٌ في الحالين.
    """
    d = tmp_path / "answered"
    d.mkdir(exist_ok=True)
    rc, results = _run(d, monkeypatch, _Meter(0.30), 25.0, n=6,
                       calls_for={"س3": 25}, tools_for={"س3": 24})
    assert (rc, len(results)) == (0, 6), f"الحالُ المُجابة: رمز {rc} وتغطية {len(results)} من 6"
    assert results[2]["replies_observed"] == 25, results[2]
    assert results[3]["cap_price_usd"] == pytest.approx(0.30, rel=1e-6), results[3]["cap_price_usd"]


def test_a_run_whose_replies_are_never_counted_stops_instead_of_being_uncapped(tmp_path, monkeypatch):
    """**وسقفٌ لا يُحسب لا يُفرض (R113-1):** لو لم تُرصد الردودُ (مراقبٌ غيرُ موصول) لصار السعرُ صفرًا
    والسقفُ صفرًا ⇒ **فلا يوقف شيءٌ الصرفَ أبدًا** — وهو الصمتُ الذي يُنشر كأنّه سقفٌ يعمل.

    فهذه الحالُ **تتوقّف مُسمّاةً برمز ٥** بعد السؤال الأوّل (fail-closed) بدل أن تمضي بلا حدّ.
    """
    d = tmp_path / "no-replies"
    d.mkdir(exist_ok=True)
    rc, results = _run(d, monkeypatch, _Meter(0.30), 25.0, n=6, no_replies=True)
    assert rc == 5, f"مراقبٌ غيرُ موصول ⇒ المتوقَّعُ توقّفٌ مُسمّى (5) لا {rc} بتغطية {len(results)}"
    assert len(results) == 1, f"التوقّفُ يجب أن يقع بعد السؤال الأوّل لا بعد {len(results)}"


def test_tokens_that_land_between_windows_still_enter_the_spend(tmp_path, monkeypatch):
    """**R113-1 · الوجهُ الثاني: رموزٌ تصل بين نافذتين لا تسقط من المُنفَق.**

    خيطُ سؤالٍ مُتخلّى عنه يواصل الإنفاق بعد إغلاق نافذته ⇒ برموزِ النوافذ (مجموعِ الفروق) تسقط
    تلك الرموزُ من المُنفَق كلَّه ولو بُرمج عليها. والمُنفَقُ الآن **تراكميٌّ من عدّاد المكتبة** ⇒
    يدخلها عند القرار التالي.

    الأرقام: ثلاثةُ أسئلة (‏$0.90)، ثمّ **نداءان متأخّران** (‏$0.60) يصلان بين نافذة الثالث والرابع
    ⇒ فمُنفَقُ القرار الرابع **$1.50** (لا $0.90).
    """
    d = tmp_path / "late"
    d.mkdir(exist_ok=True)
    rc, results = _run(d, monkeypatch, _Meter(0.30), 25.0, n=6, late=(3, 2))
    assert (rc, len(results)) == (0, 6), f"رمز {rc} وتغطية {len(results)}"
    assert results[3]["spent_before_usd"] == pytest.approx(1.50, rel=1e-6), (
        f"رموزٌ وقعت بين النافذتين لم تدخل المُنفَق: {results[3]['spent_before_usd']} بدل 1.50")
    assert results[1]["spent_before_usd"] == pytest.approx(0.30, rel=1e-6), results[1]

