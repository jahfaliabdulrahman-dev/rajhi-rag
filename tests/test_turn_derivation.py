"""**الدورُ يُشتقّ من الوقائع** (P-6 · تبنّاه المدقّق في مراجعة ٥٤) — وضابطُ التقادُم الحيّ.

**ما وُلد منه:** `handoff/STATE.md` أوّلُ ملفٍّ يُقرأ، وكان يُحدَّث بيد الطرف الذي أنهى دوره ⇒ قِيس تقادُمُه:
ظلّ يقول «`P-1..P-3` تنتظر قرارَ المدقّق» بعد أن قُرِّرت ونُفِّذت. ⇒ الدورُ صار **مُشتقّاً**:
آخرُ فاعلٍ (من زمن اسمِ تقريره) ⇒ الدورُ للآخر… إلّا إذا طلب آخرُ تقريرٍ قراراً من المالك ⇒ فالدورُ **للمالك**
(وهو الموضعُ الذي تأخّر فيه دمجُ #119 بلا مالكٍ ظاهر).

والضابطُ الأخير **حيّ**: يقيس `handoff/STATE.md` نفسه — فيمنع الصنفَ لا الحادثةَ وحدها.
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
    """(الطرف ⇒ [(الاسم، متن)]): يبني صناديقَ تقاريرَ مصغّرة بنفس اصطلاح الأسماء."""
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
    assert m.main([]) == 0
    assert "claude" in capsys.readouterr().out


def test_a_report_asking_the_owner_makes_the_turn_the_owners(monkeypatch, tmp_path, capsys):
    """**المسارُ الذي تأخّر عنده #119**: تقريرٌ يطلب قراراً ⇒ الدورُ للمالك، لا «للطرف الآخر»."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"sulaiman": [("20260925-0130-REPORT", "اكتب «ادفع» وأنفّذ — وبيدك أيضاً تدويرُ الرمز")]})
    assert m.main([]) == 0
    out = capsys.readouterr().out
    assert "المالك" in out, out


def test_check_reports_staleness_and_prints_the_right_line(monkeypatch, tmp_path, capsys):
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    # آخرُ فاعلٍ = claude ⇒ الدورُ المُشتقُّ على sulaiman، والملفُّ يُعلن claude ⇒ **متقادم**
    _tree(tmp_path, {"claude": [("20260925-0200-review", "بلا طلب")]})
    (tmp_path / "handoff" / "STATE.md").write_text("turn: **المدقّق** (`claude`) — قديم\n", encoding="utf-8")
    assert m.main(["--check"]) == 1, "تقادُمٌ مُقاس ⇒ 1"
    out = capsys.readouterr().out
    assert "'sulaiman'" in out and "'claude'" in out, out   # المُعلَنُ والمُشتقُّ في السطر نفسه


def test_write_repairs_the_line_then_check_passes(monkeypatch, tmp_path, capsys):
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    _tree(tmp_path, {"claude": [("20260925-0200-review", "بلا طلب")]})
    (tmp_path / "handoff" / "STATE.md").write_text("turn: **المدقّق** (`claude`) — قديم\n", encoding="utf-8")
    assert m.main(["--write"]) == 0
    assert m.main(["--check"]) == 0, "بعد الإصلاح: مطابق"
    assert (tmp_path / "handoff" / "STATE.md").read_text(encoding="utf-8").count("turn:") == 1


def test_no_reports_fails_closed(monkeypatch, tmp_path, capsys):
    """**غيابُ الأدلّة ليس دوراً**: بلا تقريرٍ لا يُعلَن أحد."""
    m = _load()
    monkeypatch.setattr(m, "ROOT", tmp_path)
    (tmp_path / "handoff" / "sulaiman").mkdir(parents=True)
    assert m.main(["--check"]) == 2
    assert "UNMEASURED" in capsys.readouterr().out


def test_the_live_state_file_is_not_stale():
    """**البوّابةُ الحيّة**: `handoff/STATE.md` المُتتبَّع سطرُ دورِه مطابقٌ للمُشتقّ الآن."""
    m = _load()
    assert m.main(["--check"]) == 0, "سطرُ الدور في handoff/STATE.md متقادمٌ عن الواقع ⇒ يُصلَح بـ`tools/turn.py --write`"
