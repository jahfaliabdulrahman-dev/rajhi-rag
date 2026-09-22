"""ترقيمُ قواعد البروتوكول وإحالاتُها: رقمٌ واحدٌ لكلّ قاعدة، وكلُّ إحالةٍ تُحلّ، وأداةُ المراجعة موجودة.

**السبب (مراجعة ٤٠/٥):** كان لكلٍّ من «١٨» و«١٩» عنوانان، وكانت الأداةُ تستشهد بالقاعدة نفسِها
مرّةً «١٤» ومرّةً «١٦» — فأُصلح الترقيمُ والإحالات، **وهذا الاختبارُ يمنع عودتهما**: الترقيمُ
والإحالاتُ نصوصٌ يُقاس عليها، لا عُرفٌ يُتذكَّر.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs" / "handoff-protocol.md"
AR = "٠١٢٣٤٥٦٧٨٩"
HEAD = re.compile(r"^### ([٠-٩]+) — (.+)$", flags=re.M)
CITE = re.compile(r"القاعدة ([٠-٩]+)")


def _num(s: str) -> int:
    return int("".join(str(AR.index(c)) for c in s))


def _heads() -> list[str]:
    text = PROTOCOL.read_text(encoding="utf-8")
    found = [m.group(1) for m in HEAD.finditer(text)]
    assert found, "لا عنوانَ قاعدةٍ في البروتوكول ⇒ التعبيرُ لا يطابق الشكل (أو الملفُّ تبدّل)"
    return found


def _titles() -> dict[int, str]:
    text = PROTOCOL.read_text(encoding="utf-8")
    return {_num(m.group(1)): m.group(2) for m in HEAD.finditer(text)}


def test_every_rule_number_appears_once():
    seen: dict[int, list[str]] = {}
    for h in _heads():
        seen.setdefault(_num(h), []).append(h)
    dup = {k: v for k, v in seen.items() if len(v) > 1}
    assert not dup, f"رقمُ قاعدةٍ يحمل أكثرَ من عنوان: {dup}"


def test_every_citation_resolves_to_a_rule():
    heads = {_num(h) for h in _heads()}
    cites: dict[int, list[str]] = {}
    for f in sorted(list((ROOT / "tools").glob("*.py")) + list((ROOT / "tests").glob("*.py"))):
        for c in CITE.findall(f.read_text(encoding="utf-8")):
            cites.setdefault(_num(c), []).append(f.name)
    missing = {k: sorted(set(v)) for k, v in cites.items() if k not in heads}
    assert not missing, f"إحالةٌ إلى قاعدةٍ غيرِ موجودة: {missing} (الموجود: {sorted(heads)})"


def test_the_review_gate_script_is_in_the_repository_and_can_fail():
    """القاعدةُ الحديديّة ٦: كلُّ ما يُتحقَّق منه ممثَّلٌ في المستودع — والقاعدة ٢٠ تستشهد به."""
    script = ROOT / "scripts" / "check_review_report.py"
    assert script.exists(), "القاعدة ٢٠ تستشهد بـ`scripts/check_review_report.py` وهو غيرُ موجود"
    r = subprocess.run([sys.executable, str(script), "--self-test"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and "SELF-TEST PASSED" in r.stdout, r.stdout + r.stderr


@pytest.mark.parametrize("n", [12, 20])
def test_the_two_rules_the_round_cited_are_the_ones_it_meant(n):
    """العنوانُ المقصود بالرقم: ١٢ = الإعفاءُ بالقيمة لا بالموضع · ٢٠ = المراجعةُ قبل التسليم."""
    titles = _titles()
    assert n in titles, f"القاعدة {n} غيرُ موجودة"
    if n == 12:
        assert "يُعفى قيمة" in titles[12]
    else:
        assert "مراجعةٍ مستقلّة" in titles[20]
