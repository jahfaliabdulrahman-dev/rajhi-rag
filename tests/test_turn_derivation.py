"""**الدورُ يُشتقّ من الوقائع** (P-6 · تبنّاه المدقّق في مراجعة ٥٤) — **ولا تُحفَظ قيمتُه** (R55-1).

**ما وُلد منه:** `handoff/STATE.md` أوّلُ ما يُقرأ، وكان يُحدَّث **بيد** الطرف الذي أنهى دوره ⇒ قِيس تقادُمُه:
ظلّ يقول «`P-1..P-3` تنتظر قرارَ المدقّق» بعد أن قُرِّرت ونُفِّذت. ⇒ الدورُ صار **مُشتقّاً** من زمن أسماء التقارير.

ثم أمسك المدقّق في مراجعة ٥٥ **صنفَين** في التصميم الأوّل — وكلاهما مُثبتٌ بقياسٍ هنا:
- **R55-1 (أ):** نمطُ الاسم كان يشترط **أربع** خاناتٍ للوقت، وأسماءُ المدقّق **ستّ** (`HHMMSS`) — وهي الصيغةُ
  الموثَّقة في البروتوكول ⇒ كان **أعمى عن صندوقه كاملاً**، والدورُ لا ينتقل إليه أبداً.
- **R55-1 (ب):** ولو أُصلح النمط، فقيمةٌ **محفوظةٌ** في ملفٍّ يكتبه طرفٌ واحد كانت ستتقادم **بعد كلّ دفعةٍ من
  الطرف الآخر** فيسقط الفحصُ بلا ذنب. ⇒ **لا تُحفَظ القيمة**: السطرُ **مُؤشِّرٌ** إلى الأمر، والقيمةُ تُقاس
  لحظةَ الطلب ⇒ **صنفُ التقادُم يموت** بدل أن يُعالَج بعد وقوعه.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("turn", ROOT / "tools" / "turn.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ مُشتقّ الدور ⇒ لا قياس"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _tree(tmp: Path, reports: dict[str, list[tuple[str, str]]]) -> None:
    """(الطرف ⇒ [(الاسم، متن)]): صناديقُ تقاريرَ مصغّرة بنفس اصطلاح الأسماء."""
    for side, files in reports.items():
        d = tmp / "handoff" / side
        d.mkdir(parents=True, exist_ok=True)
        for name, body in files:
            (d / f"{name}.md").write_text(body, encoding="utf-8")


def test_last_actor_passes_the_turn_to_the_other_side(monkeypatch, tmp_path, capsys):
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT", "لا شيء")],
                     "claude": [("20260925-0100-review", "قديم")]})
    assert m.main(["--json"]) == 0
    assert '"turn": "claude"' in capsys.readouterr().out


def test_a_six_digit_name_is_seen_like_a_four_digit_one(monkeypatch, tmp_path, capsys):
    """**R55-1 (أ) بعينه**: اسمُ المدقّق بستّ خانات (`HHMMSS`) يجب أن يُرى ويُزيح الدور — وإلّا فالأداةُ عمياء."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0203-REPORT", "لا طلب")],
                     "claude": [("20260925-021953-third-eye-review-55", "بلا طلب")]})
    assert m.main(["--json"]) == 0
    out = capsys.readouterr().out
    assert '"last_actor": "claude"' in out, f"صندوقُ المدقّق لم يُرَ (R55-1): {out}"
    assert '"turn": "sulaiman"' in out, out


def test_the_two_name_lengths_are_ordered_on_one_scale(monkeypatch, tmp_path, capsys):
    """**مقياسٌ واحد**: `-020359` أحدثُ من `-0203` (والمكمَّلةُ بـ`00` = 02:03:00 ⇒ تسبقه).

    ولو قُورنت الخانتان الخامّتان لكان الترتيبُ حظّاً من ترتيب الحروف لا من الزمن.
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"claude": [("20260925-020359-review", "الأحدث")],
                     "sulaiman": [("20260925-0203-REPORT", "نفسُ الدقيقة، بلا ثوانٍ ⇒ الأقدم")]})
    assert m.main(["--json"]) == 0
    assert '"last_actor": "claude"' in capsys.readouterr().out, "اختلّ الترتيبُ بين الطولين"


def test_a_blocking_owner_request_makes_the_turn_the_owners(monkeypatch, tmp_path, capsys):
    """**المسارُ الذي تأخّر عنده #119**: تقريرٌ **يُعلن توقّفاً** على قرار المالك ⇒ الدورُ للمالك.

    والعلامةُ هي إعلانُ التوقّف المُصطلَح — **بصيغته الواحدة الموثّقة في المستودع** (`status: AWAITING_FOUNDER`
    · `handoff/STATE.md:60` · `docs/claude-auditor-directive.md:43`) لا ذكرُ المالك في قائمة. وهذا هو
    الحقلُ الذي سقط في `ba6c219` (**تراجع** قاسه المدقّق في مراجعة ٥٧ · R57-2ب).
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT",
                                   "status: AWAITING_FOUNDER — لا أُكمل قبل قرارِ المالك")]})
    assert m.main(["--json"]) == 0
    out = capsys.readouterr().out
    assert '"turn": "المالك"' in out, out
    assert '"owner_declared_in"' in out and "آخرُ تقريرٍ" in out, out


def test_the_owner_lock_in_the_shared_state_file_is_read(monkeypatch, tmp_path, capsys):
    """**R57-2 (أ) — قفلٌ موثَّقٌ لا يُقرأ.** `handoff/STATE.md:60` يقول للمالك: «اكتب `status: AWAITING_FOUNDER`
    هنا»، والأداةُ **لم تكن تقرأ الملفّ المشترك أصلًا** ⇒ القفلُ الموثَّقُ لا يوقف الدورَ المشتقّ، والدورُ
    يمضي إلى الطرف الآخر بينما المالكُ هو المنتظَر. والضابطُ يقيس الموضعَ الثاني المُعلَن.
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT", "بلا إعلان")]})
    shared = tmp_path / "handoff" / "STATE.md"
    shared.write_text("status: AWAITING_FOUNDER — أوقفني المالك\n", encoding="utf-8")
    assert m.main(["--json"]) == 0
    out = capsys.readouterr().out
    assert '"turn": "المالك"' in out, out
    assert "قفلُ المالك" in out, out


def test_only_the_documented_field_form_declares_a_stop(monkeypatch, tmp_path, capsys):
    """**«صيغةٌ واحدةٌ في موضعٍ واحد» (R57-2)**: الصيغةُ الحرّةُ (`AWAITING_FOUNDER` في أوّل سطر) ليست إعلاناً
    بعد التوحيد، وكذلك حقلٌ آخرُ مثل `next:` يحمل العلامة — وإلّا تعدّدت الصيغُ فصار كلُّ اقتباسٍ إعلاناً.

    (والمُعلَن صريحاً في ترويسة `tools/turn.py`، فلا تُقرأ قاعدةٌ لم تُكتب.)
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    for body in ("AWAITING_FOUNDER — صيغةٌ حرّةٌ بلا حقل",
                 "next: AWAITING_FOUNDER — لا تدعمها",
                 "awaiting: AWAITING_FOUNDER"):
        _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT", body)]})
        assert m.main(["--json"]) == 0
        assert '"turn": "claude"' in capsys.readouterr().out, f"صيغةٌ غيرُ موثّقةٍ أزاحت الدور: {body!r}"


def test_a_quoted_marker_in_a_fence_or_backticks_does_not_declare_a_stop(monkeypatch, tmp_path, capsys):
    """**R57-2 (ج)** — القاعدتان اللتان تمنعان الاقتباسَ من إزاحة الدور:

    (١) العلامةُ في أوّل سطرٍ **داخل كتلةِ شِفرة** (كما تقتبسها التقاريرُ والوثيقة) — كانت **تُزيح الدور**
    إلى المالك فتُوقف الطرفين بلا سبب. (٢) و**السطرُ التوثيقيّ الحقيقيّ** من `handoff/STATE.md:60` نفسه،
    وفيه الصيغةُ بين علامتين خلفيّتين: تعليمةٌ **تُعلّم** الصيغةَ وليست إعلانَ توقّف.
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    fenced = "## الحكم\n```\nstatus: AWAITING_FOUNDER — اقتباسٌ في كتلة\n```\nبلا إعلانٍ حقيقيّ\n"
    _tree(tmp_path, {"sulaiman": [("20260925-0300-REPORT", fenced)]})
    assert m.main(["--json"]) == 0
    assert '"turn": "claude"' in capsys.readouterr().out, "اقتباسٌ في كتلةِ شِفرةٍ أزاح الدورَ (العلّةُ باقية)"

    documented = "- **قفل المالك:** عند رغبتك في إيقاف الحلقة، اكتب `status: AWAITING_FOUNDER` هنا — الطرفان يتوقفان.\n"
    _tree(tmp_path, {"sulaiman": [("20260925-0301-REPORT", documented)]})
    assert m.main(["--json"]) == 0
    assert '"turn": "claude"' in capsys.readouterr().out, "سطرُ التوثيق (اقتباسٌ بعلامتين) أزاح الدورَ"


def test_the_fenced_header_is_read_not_ignored(monkeypatch, tmp_path, capsys):
    """**R58-3 (قاسه المدقّق في مراجعة ٥٨)**: صيغةُ §٢ تكتب الترويسةَ **كتلةً مسيّجة** (كما في كلّ تقريرٍ في
    هذا المستودع)، فاستثناءُ ما بين سياجين كان يُهمِل `status:` في الترويسة **صامتاً** — إعلانٌ موثَّقٌ لا
    يُقرأ، و`ignored_markers` فارغٌ فلا تنبيهَ أيضاً. والضابطُ يقيس **شكلَ الترويسة الحقيقيّ** لا شكلاً مصغَّراً.
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    real = ("```\n"
            "id:      20260925-1300-sulaiman\n"
            "from:    sulaiman\n"
            "to:      claude\n"
            "type:    REPORT\n"
            "status:  AWAITING_FOUNDER — القرارُ للمالك\n"
            "commit:  deadbeef\n"
            "```\n\n"
            "# عنوانٌ\nمتنٌ طويلٌ بعد الترويسة\n")
    _tree(tmp_path, {"sulaiman": [("20260925-1300-REPORT", real)]})
    assert m.main(["--json"]) == 0
    out = capsys.readouterr().out
    assert '"turn": "المالك"' in out, f"ترويسةٌ مسيّجةٌ بصيغة §٢ لم تُقرأ (R58-3 باقٍ): {out}"
    assert '"ignored_markers": []' in out, f"إعلانٌ مقروءٌ لا يجوز أن يُعرَض مُهمَلاً: {out}"
    # **والحدُّ محفوظٌ في الاتجاه الآخر**: العلامةُ في كتلةٍ **ليست** الترويسة تبقى اقتباساً (R57-2 كما هو)
    quoted = "## الحكم\n```\nstatus: AWAITING_FOUNDER — اقتباسٌ في المتن\n```\nبلا إعلانٍ حقيقيّ\n"
    _tree(tmp_path, {"sulaiman": [("20260925-1301-REPORT", quoted)]})
    assert m.main(["--json"]) == 0
    assert '"turn": "claude"' in capsys.readouterr().out, "اقتباسٌ في غير الترويسة أزاح الدورَ"
    # **والهويّةُ لا الشكل (نقلةُ مقعد البنية في مراجعة ٥٩):** ترويسةُ تقريرٍ **آخرَ** تُقتبَس في أعلى ملفّ
    # تحمل شكلَ ترويسةٍ كاملاً (`id` وحقولاً) — وكان شرطُ «الشكل» يقرؤها **ترويسةً لهذا الملفّ** فيُطبّق
    # إعلانَ غيرِه عليه. والآن تُقاس **الهويّة** (زمنُ `id` == زمنُ الاسم) فتبقى اقتباساً.
    foreign = ("```\n"
               "id:      20260101-0000-sulaiman\n"
               "from:    sulaiman\n"
               "status:  AWAITING_FOUNDER — إعلانُ تقريرٍ آخر\n"
               "commit:  deadbeef\n"
               "```\n\n# متنٌ\n")
    _tree(tmp_path, {"sulaiman": [("20260925-1302-REPORT", foreign)]})
    assert m.main(["--json"]) == 0
    out = capsys.readouterr().out                       # قراءةٌ واحدة (الثانيةُ تُفرّغ المخزن)
    assert '"turn": "claude"' in out, \
        "ترويسةُ تقريرٍ آخر (شكلٌ صحيح · هويّةٌ غريبة) أزاحت الدورَ"
    assert '"ignored_markers": []' in out, \
        "كتلةٌ مُقتبَسة في الرأس لا يجوز أن تُعرَض إعلاناً مُهمَلاً (ليست إعلاناً من الأصل)"


def test_the_declaration_is_read_in_the_header_only(monkeypatch, tmp_path, capsys):
    """**حدُّ الترويسة (أمرُ المالك: «الأكثر حرصاً ووضوحاً» · SP-3 — قاسه مقعدُ المواصفة)**: الإعلانُ يُقرأ
    من أوّل الملفّ **قبل أوّل عنوان `## `** (وضمن أوّل ٣٠ سطراً) — فترويسةُ تقريرٍ يُعلن فيها = توقّفٌ حقيقيّ،
    و**متنُه = توثيقٌ لا يُزيح الدور**.

    والعلّةُ المقيسة: مطابقةُ العلامة في أيّ موضعٍ جعلت تقريراً **يشرح القاعدةَ** يُوقف الطرفين بلا سبب؛
    وصفرُ نصوصٍ في الشجرة تُعلن من المتن ⇒ فالحدُّ يمنع الصنفَ **ولا يُلغي إعلاناً واقعاً**. وما يُهمَل يُعرَض
    بتنبيه وضوحٍ لا يُغيّر الحكم (وإلّا ظنّ كاتبُه أنّه أوقف الدورَ وهو لم يُوقف).
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    header_decl = "status: AWAITING_FOUNDER — القرارُ للمالك\n\n## ما فعلتُه\nشرحٌ طويل\n"
    _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT", header_decl)]})
    assert m.main(["--json"]) == 0
    assert '"turn": "المالك"' in capsys.readouterr().out, "إعلانٌ في الترويسة لم يُقرأ (تضييقٌ زائد)"

    body_decl = "\n".join(["## ما فعلتُه", "عشرةُ أسطرٍ من الشرح"] + ["سطرٌ عاديّ"] * 20 +
                          ["status: AWAITING_FOUNDER — القرارُ للمالك"])
    _tree(tmp_path, {"sulaiman": [("20260925-0131-REPORT", body_decl)]})
    assert m.main([]) == 0
    out = capsys.readouterr().out
    assert "claude" in out, "إعلانٌ في المتن أزاح الدورَ (العلّةُ باقية)"
    assert "تنبيهُ وضوح" in out and "لم يُقرأ" in out, \
        "سطرٌ مُهمَلٌ لم يُعرَض ⇒ كاتبُه يظنّ أنّه أوقف الدور (الصمتُ أسوأُ من التنبيه)"


def test_a_headingless_file_longer_than_the_header_is_body(monkeypatch, tmp_path, capsys):
    """**سقفُ `HEADER_LINES`**: ملفٌّ بلا عنوانٍ أصلًا لا يُقرأ نصُّه كلُّه — فإعلانٌ بعد السطر ٣٠ **ليس في
    الترويسة** (وإلّا صار أيُّ نصٍّ طويلٍ بلا عناوين ترويسةً كاملة، وعاد الصنفُ الذي مُنع)."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    long_body = "\n".join(["سطرٌ عاديّ"] * 40 + ["status: AWAITING_FOUNDER — بعد الثلاثين"])
    _tree(tmp_path, {"sulaiman": [("20260925-0132-REPORT", long_body)]})
    assert m.main(["--json"]) == 0
    out = capsys.readouterr().out
    assert '"turn": "claude"' in out, "سقفُ الترويسة لم يُحترم (ملفٌّ بلا عنوانٍ صار كلُّه ترويسة)"
    assert '"ignored_markers": [\n    "handoff/sulaiman/20260925-0132-REPORT' in out or \
           '"0132-REPORT' in out, out


def test_quoting_the_marker_in_prose_does_not_move_the_turn(monkeypatch, tmp_path, capsys):
    """**نقدُ مقعد Spec**: مطابقةُ العلامة في **أيّ موضع** تعني أنّ تقريراً **يقتبسها** — كما تقتبسها الوثيقةُ
    نفسُها في §٢٦ — يُزيح الدورَ إلى المالك ويوقف الطرفين بلا سبب.

    ⇒ الاقتباسُ بعلامتين خلفيّتين ليس إعلاناً؛ والإعلانُ حقلُ `status:` يحمل العلامة (R57-2).
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0300-REPORT",
                                    "البروتوكول §٣: الرمزُ `AWAITING_FOUNDER` يعني أنّ الدورَ للمالك …")]})
    assert m.main(["--json"]) == 0
    assert '"turn": "claude"' in capsys.readouterr().out, "اقتباسٌ في نثرٍ أزاح الدورَ (العلّةُ باقية)"

    _tree(tmp_path, {"sulaiman": [("20260925-0301-REPORT", "status: AWAITING_FOUNDER — نعم، إعلانٌ فعليّ")]})
    assert m.main(["--json"]) == 0
    assert '"turn": "المالك"' in capsys.readouterr().out, "إعلانٌ صريحٌ لم يُزِح الدور"


def test_an_owner_queue_line_does_not_move_the_turn(monkeypatch, tmp_path, capsys):
    """**R56-3 (قاسه المدقّق)**: قائمةُ «ما بيد المالك» في آخر كلّ تقرير **ضجيجٌ** لا طلبَ توقّف.

    قبل الإصلاح: أيُّ «بيدك» في أيّ موضعٍ كانت تُزيح الدورَ إلى المالك، وتقريرُ المنفّذ ينتهي بها دائماً ⇒
    الدورُ يقف عند المالك أبداً بينما المنتظَرُ فعلًا هو الطرفُ الآخر. ⇒ السالبُ هنا يمنع عودةَ ذلك.
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT",
                                   "بيدك: تدويرُ الرمز · نصُّ التذكرة · قرارُ الفروع الخمسة عشر")]})
    assert m.main(["--json"]) == 0
    assert '"turn": "claude"' in capsys.readouterr().out, "قائمةٌ عاديّةٌ أزاحت الدور إلى المالك (R56-3)"


def test_the_default_command_prints_the_turn_and_its_reason(monkeypatch, tmp_path, capsys):
    """**R56-2 (قاسه المدقّق)**: المُؤشِّرُ في `handoff/STATE.md` يعِد بأنّ الأمرَ **بلا وسيط** يعرض الدورَ وسببَه.

    وكان يطبع سطرَ الإشارة وحده ⇒ وعدٌ في المصدر لا يفي به التنفيذ. والضابطُ يقيس الوفاءَ لا الوعد.
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT", "بلا طلب")]})
    assert m.main([]) == 0
    out = capsys.readouterr().out
    assert "claude" in out and "آخرُ فاعلٍ" in out, f"الأمرُ الافتراضيّ لا يعرض الدورَ وسببَه: {out!r}"


def test_check_flags_every_stored_value_variant(monkeypatch, tmp_path, capsys):
    """**R55-1 (ب)** — والقياسُ **حرفيّ** لأنّ الصيغَ الأربع كلَّها نَجَت من نسخةٍ أضيق (قاسها المقعدُ التركيبيّ):

    `` (`Claude`) `` · `` (`sulaiman-2`) `` · `(claude)` بلا علامتين · `Turn:` بحرفٍ كبير — كلُّها قيمٌ
    محفوظةٌ كانت تُقرأ «لا قيمةَ محفوظة» ⇒ تقادُمٌ يمرّ بصمت. و**غيابُ السطر** عطبٌ أيضاً (القارئُ الأوّل يفقد الأمر).
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"claude": [("20260925-0200-review", "بلا طلب")]})
    shared = tmp_path / "handoff" / "STATE.md"
    for body in ("turn: **المدقّق** (`claude`) — قيمةٌ محفوظة\n",
                 "turn: **المدقّق** (`Claude`) — بحرفٍ كبير\n",
                 "turn: **المدقّق** (`sulaiman-2`) — معرّفٌ مركّب\n",
                 "turn: **المدقّق** (claude) — بلا علامتين\n",
                 "Turn: **المدقّق** (`claude`) — بحرفٍ كبير في المفتاح\n"):
        shared.write_text(body, encoding="utf-8")
        assert m.main(["--check"]) == 1, f"قيمةٌ محفوظةٌ مرّت: {body!r}"
        assert "tools/turn.py --write" in capsys.readouterr().out
    shared.write_text("ملفٌّ بلا سطر دورٍ أصلاً\n", encoding="utf-8")
    assert m.main(["--check"]) == 1, "غيابُ المُؤشِّر عطبٌ لا «لا تقادُم»"
    assert "لا سطرَ" in capsys.readouterr().out


def test_write_replaces_any_variant_and_leaves_no_second_line(monkeypatch, tmp_path):
    """`--write` يستبدل **أيّ** صيغة (وبحرفٍ كبير) ولا يُدرج سطراً ثانياً يُبقي القيمة (قاسه المقعدُ التركيبيّ)."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"claude": [("20260925-0200-review", "بلا طلب")]})
    shared = tmp_path / "handoff" / "STATE.md"
    shared.write_text("handoff/STATE.md — تقريرُ الحالة\nTurn: **المدقّق** (`claude`) — قديم\n", encoding="utf-8")
    assert m.main(["--write"]) == 0
    body = shared.read_text(encoding="utf-8")
    assert body.count("turn:") + body.count("Turn:") == 1, f"سطران للدور ⇒ قيمةٌ باقية: {body!r}"
    assert m.POINTER in body and "`claude`" not in body
    assert m.main(["--check"]) == 0


def test_no_reports_fails_closed(monkeypatch, tmp_path, capsys):
    """**غيابُ الأدلّة ليس دوراً**: بلا تقريرٍ لا يُعلَن أحد."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    (tmp_path / "handoff" / "sulaiman").mkdir(parents=True)
    assert m.main(["--check"]) == 2
    assert "UNMEASURED" in capsys.readouterr().out


def test_the_live_state_file_stores_no_value():
    """**البوّابةُ الحيّة**: `handoff/STATE.md` المُتتبَّع لا يحفظ قيمةَ دورٍ ⇒ لا تقادُمَ بعده أبداً."""
    m = _load()
    assert m.main(["--check"]) == 0, "سطرُ الدور يحفظ قيمةً ⇒ ستتقادم؛ أصلِحْه بـ`tools/turn.py --write`"


def test_a_field_carrying_a_leading_backtick_is_not_a_declaration(monkeypatch, tmp_path, capsys):
    """**S-4 (مقعد ٥٧): التجريدُ كان يخالف وصْفَه** — كان `` `[^`]*` `` يُحذَف قبل المطابقة، وقِيس أنّ إسقاطَه
    (أ) لا يُسقط أيَّ ضابط، (ب) وأنّ التجريد **يوسّع** المطابقة: سطرٌ يبدأ باقتباسٍ ثمّ يحمل الحقلَ يُقرأ
    إعلاناً **معه**، ولا يُقرأ **بدونه**. والقاعدةُ الموثَّقة «لا يُقرأ بين علامتين خلفيّتين» ⇒ فالمرساةُ
    وحدَها تكفي، والسطرُ الذي لا **يبدأ** بالحقل ليس إعلاناً (والدالّةُ خالصة ⇒ تُقاس في الذاكرة).
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    assert m.declarations("`x` status: AWAITING_FOUNDER — اقتباسٌ ثمّ حقلٌ في سطرٍ لا يبدأ به\n",
                          "probe.md") == [], \
        "التجريدُ يُوسّع المطابقة: سطرٌ يبدأ باقتباسٍ صار إعلاناً"
    assert m.declarations("status: AWAITING_FOUNDER — إعلانٌ حقيقيّ\n", "probe.md") == ["AWAITING_FOUNDER"], \
        "الإعلانُ الحقيقيُّ لم يُقرأ (تضييقٌ زائد)"


def test_an_unpaired_fence_does_not_hide_a_real_declaration(monkeypatch, tmp_path, capsys):
    """**ST-6 (مقعد ٥٧): السياجُ كان قلْبَ حالةٍ لا مُقابَلةً** — سطرُ سياجٍ واحدٍ بلا قِرْن يقلب معنى كلّ ما
    بعده ⇒ إعلانٌ حقيقيٌّ بعد سياجٍ غيرِ مُغلق **يُهمَل** ولا ينتقل الدورُ إلى المالك (وهو إهمالُ إعلان،
    وأسوأُ من قراءة اقتباس). والآن تُقابَل الأسوارُ **زوجاً**: عددٌ فرديٌّ يُبطِل التسييجَ كلَّه فيُقرأ النصّ.
    """
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    unpaired = "```\nاقتباسٌ لم يُقفَل أصلًا\n\nstatus: AWAITING_FOUNDER — إعلانٌ حقيقيّ بعد سياجٍ يتيم\n"
    _tree(tmp_path, {"sulaiman": [("20260925-0302-REPORT", unpaired)]})
    assert m.main(["--json"]) == 0
    assert '"turn": "المالك"' in capsys.readouterr().out, "إعلانٌ حقيقيٌّ بعد سياجٍ يتيمٍ أُهمِل"

    paired = "```\nstatus: AWAITING_FOUNDER — اقتباسٌ مُقفَل\n```\nبلا إعلانٍ حقيقيّ\n"
    _tree(tmp_path, {"sulaiman": [("20260925-0303-REPORT", paired)]})
    assert m.main(["--json"]) == 0
    assert '"turn": "claude"' in capsys.readouterr().out, "كتلةُ شِفرةٍ **مُقفَلة** أزاحت الدور"
