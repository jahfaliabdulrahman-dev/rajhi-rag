"""**ماسحُ الأسرار: يرى أصنافَ هذا المشروع، ولا يطبع قيمةً، ويفشل مُغلَقًا.**

وُلد من مراجعة ٥٣ (مدقّقٌ مستقلّ بمفاتيحَ مصطنعة): النمطُ الواحد في `pre-commit` كان يمرّر
`sk-or-v1-…` و`sk-ant-…` (صنفُ الرمز الذي تسرّب فعلًا) و`sk-proj-…` و`github_pat_…` — لأنّه توقّف عند
أوّل شَرطة. ⇒ الفحصُ انتقل إلى أداةٍ ذاتِ نمطٍ لكلّ صنف، وهذه ضوابطُها.

⚠ **ولا يُكتب سِرٌّ في هذا الملفّ حرفيًّا**: القيمُ تُبنى بالضَمّ وقتَ التشغيل ⇒ فلا الخطّافُ ولا أيُّ
ماسحٍ يرى سِرًّا حقيقيًّا في هذه الضوابط. (والمقاطعُ وحدها **يجب ألّا تُطابَق** — وهذا ضابطٌ بنفسه.)
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("secret_scan", ROOT / "tools" / "secret_scan.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ الماسح ⇒ لا قياس"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _fakes() -> dict[str, str]:
    """قيمٌ مصطنعةٌ لكلّ صنف (تُبنى ولا تُكتب) — الحشوُ تكرارُ حرفٍ واحد فلا يشبه شيئًا حقيقيًّا."""
    return {
        "anthropic": "sk-ant-" + "api03-" + "x" * 40,
        "openrouter": "sk-or-v1-" + "0" * 40,
        "openai_project": "sk-proj-" + "y" * 40,
        "openai_legacy": "sk-" + "z" * 40,
        "github_pat": "github_pat_" + "a" * 30,
        "github_token": "ghp_" + "b" * 40,
        "aws_access_key": "AKIA" + "C" * 16,
        "google_api_key": "AIza" + "d" * 35,
        "slack_token": "xoxb-" + "e" * 20,
        "private_key_block": "-----BEGIN RSA " + "PRIVATE KEY-----",
        "jwt": "eyJ" + "f" * 20 + "." + "eyJ" + "g" * 20 + "." + "h" * 20,
    }


def test_every_secret_class_is_caught():
    """**الضابطُ الأساسي**: كلُّ صنفٍ على حدة، والماسحُ يسمّي صنفَه (بلا قيمة)."""
    m = _load()
    missed = []
    for name, value in _fakes().items():
        hits = m.scan_lines([(1, f"KEY={value}")])
        if name not in [h[1] for h in hits]:
            missed.append(name)
    assert not missed, f"أصنافٌ تمرّ صامتة: {missed} (وهي بعينها ما أمسكه المدقّق في الجولة السابقة)"


def test_a_named_assignment_with_an_opaque_value_is_caught():
    """**الحدُّ المُعلَن يُغلق ما يمكن إغلاقه**: سِرٌّ مجهولُ الشكل لكنه مُسنَدٌ باسمٍ صريح."""
    m = _load()
    hits = m.scan_lines([(7, 'api_key = "' + "q" * 30 + '"')])
    assert hits and hits[0] == (7, "named_assignment"), hits


def test_the_building_blocks_alone_are_not_secrets():
    """**ضابطٌ سالب**: مقاطعُ الأسماء وحدها (`sk-ant-` · `AKIA` · `github_pat_`) ليست أسرارًا.

    (وهو ما يجعل كتابةَ هذه الضوابط نفسِها آمنة: لا سِرَّ حرفيًّا في المستودع.)
    """
    m = _load()
    for frag in ("sk-ant-", "sk-or-v1-", "sk-proj-", "github_pat_", "AKIA", "xoxb-"):
        assert m.scan_lines([(1, f"اسمُ الصنف: {frag}")]) == [], f"مقطعٌ يُطابَق خطأً: {frag}"


def test_a_clean_text_has_no_hits():
    m = _load()
    clean = ["# تعليقٌ عاديّ", "def f(x):", "    return x + 1", "TOKEN_ENV_NAME = 'OPENROUTER_API_KEY'",
             'notes = "ضع المفتاح في .env لا في الكود"', "sha = 'a' * 64"]
    assert m.scan_lines(list(enumerate(clean, 1))) == []


def test_the_report_never_prints_the_value(tmp_path, capsys):
    """**القاعدة ١٣**: ما يُقاس لا يُسرّب — يُطبَع رقمُ السطر واسمُ الصنف فقط."""
    m = _load()
    value = _fakes()["anthropic"]
    p = tmp_path / "leak.txt"
    p.write_text(f"ANTHROPIC_API_KEY={value}\n", encoding="utf-8")
    rc = m.main(["--text", str(p)])
    out = capsys.readouterr().out
    assert rc == 1, f"سِرٌّ في ملفّ ⇒ 1 (صار {rc})"
    assert value not in out, "طُبعت القيمة! (القاعدة ١٣)"
    assert "anthropic" in out, "لم يُسمَّ الصنف"


def test_a_missing_file_fails_closed(tmp_path, capsys):
    """**فشلٌ مُغلَق**: تعذّرُ الفحص لا يُقرأ نظافةً."""
    m = _load()
    rc = m.main(["--text", str(tmp_path / "لا-يوجد.txt")])
    assert rc == 2, f"تعذّر الفحص ⇒ 2 (صار {rc})"
    assert "مُغلَق" in capsys.readouterr().out
