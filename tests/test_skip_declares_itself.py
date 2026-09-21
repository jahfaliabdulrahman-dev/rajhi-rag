"""**التخطّي يُعلن نفسَه بالاسم** — ولا يُسكَت عن فحصٍ غائب.

سببُ هذا الملف: فحصٌ يُخطّى بلا سببٍ مكتوب = فحصٌ ميت تُقرأ نتيجتُه نجاحاً. وقد ثبت
بالقياس (RCA · 2026-09-21) أنّ ثلاثةَ اختباراتٍ تُخطّى في **worktree** لأن `git worktree`
لا يحمل المُتجاهَل (`data/local_sample/*`)، وأنّ تغطيةَ المراجعة **دالّةٌ على البيئة**.
فالمطلوب: كلُّ تخطيطٍ يذكر **ما فُقد**، حتى يُقرأ الرقمُ مقروناً ببيئته.

    العادة: bash tools/link_local_data.sh <worktree>   ⇒ 0 تخطّى
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (الملف، السطر أو النمط، ما يجب أن يذكره السبب)
CORPUS_MARKERS = [
    ("tests/test_page_gate.py", "المسحة الحقيقية غير موجودة"),
    ("tests/test_text_reader.py", "الكشف الرقمي محليّ لا يدخل المستودع"),
]


def test_corpus_dependent_tests_declare_what_is_missing():
    for rel, reason in CORPUS_MARKERS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "skipif" in text or "skip(" in text, f"{rel}: لا تخطّي فيه أصلاً؟"
        assert reason in text, f"{rel}: التخطّي لا يذكر ما فُقد («{reason}» مفقود)"


def test_the_linking_habit_exists_and_is_executable():
    """العلاجُ عادةٌ تُعاد: سكربتٌ قائمٌ بصلاحية تنفيذ وسببٍ مكتوب في رأسه."""
    script = ROOT / "tools" / "link_local_data.sh"
    assert script.exists(), "لا سكربت وصل البيانات المحلية"
    assert script.stat().st_mode & 0o111, "السكربت غير قابل للتنفيذ"
    head = script.read_text(encoding="utf-8")[:600]
    assert "worktree" in head and "data/local_sample" in head, "لا سببَ مكتوباً في رأس السكربت"
