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


def test_a_report_asking_the_owner_makes_the_turn_the_owners(monkeypatch, tmp_path, capsys):
    """**المسارُ الذي تأخّر عنده #119**: تقريرٌ يطلب قراراً ⇒ الدورُ للمالك، لا «للطرف الآخر»."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT", "اكتب «ادفع» وأنفّذ — وبيدك أيضاً تدويرُ الرمز")]})
    assert m.main(["--json"]) == 0
    assert '"turn": "المالك"' in capsys.readouterr().out


def test_check_flags_a_stored_value_that_would_go_stale(monkeypatch, tmp_path, capsys):
    """**R55-1 (ب)**: قيمةٌ محفوظة ⇒ ستتقادم بعد كلّ دفعةٍ من الطرف الآخر ⇒ تُكشَف **قبل** أن تقادم."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"claude": [("20260925-0200-review", "بلا طلب")]})
    (tmp_path / "handoff" / "STATE.md").write_text(
        "turn: **المدقّق** (`claude`) — قيمةٌ محفوظة\n", encoding="utf-8")
    assert m.main(["--check"]) == 1, "قيمةٌ محفوظة ⇒ 1 (وإلّا تقادمت بصمت بعد أوّل دفعةٍ من الطرف الآخر)"
    assert "tools/turn.py --write" in capsys.readouterr().out


def test_write_writes_a_pointer_not_a_value(monkeypatch, tmp_path):
    """`--write` يكتب **مُؤشِّراً**: لا معرّفَ طرفٍ بين علامتين خلفيّتين ⇒ لا مادّةَ للتقادُم."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"claude": [("20260925-0200-review", "بلا طلب")]})
    (tmp_path / "handoff" / "STATE.md").write_text("turn: **المدقّق** (`claude`) — قديم\n", encoding="utf-8")
    assert m.main(["--write"]) == 0
    body = (tmp_path / "handoff" / "STATE.md").read_text(encoding="utf-8")
    assert m.POINTER in body and "`claude`" not in body, "كُتبت قيمةٌ لا مُؤشِّراً ⇒ ستعود العلّةُ نفسُها"
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
