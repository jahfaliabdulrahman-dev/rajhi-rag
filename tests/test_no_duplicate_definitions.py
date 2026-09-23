"""حارسٌ بنيويّ لكلّ الأداة والمصدر: **لا تعريفٌ ثانٍ بالاسم نفسه في المستوى الأعلى**.

سقطتُ فيه بنفسي: تعديلٌ جراحيّ في `tools/capture_training.py` ضاعف نصفَ الملفّ (١٠٦٢ سطراً،
`def main` مرّتين) — و**لا مُدقّقٌ ساكنٌ ولا اختبارٌ رآه**، لأنّ التعريفَ الثاني يطغى بصمت،
والاختباراتُ تُمرّ على الثاني. الحارسُ أرخصُ من البحث عن العطب: ‏`ast` + عدُّ الأسماء.
"""
import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILES = sorted(list((ROOT / "tools").glob("*.py")) + list((ROOT / "src").rglob("*.py")))
KINDS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@pytest.mark.parametrize("path", FILES, ids=[str(p.relative_to(ROOT)) for p in FILES])
def test_no_duplicate_top_level_definitions(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = [n.name for n in tree.body if isinstance(n, KINDS)]
    dup = sorted({n for n in names if names.count(n) > 1})
    assert not dup, f"{path.relative_to(ROOT)}: تعريفٌ مكرّرٌ {dup} — الثاني يطغى بصمت"
