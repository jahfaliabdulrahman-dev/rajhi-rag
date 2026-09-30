"""بصمةُ **كود التطبيق** — لا بصمةُ الالتزام (R77-4 · مراجعة ٧٧).

**العلّةُ المقيسة:** كانت البصمةُ المنشورة (`data/.app-code.json`) تُقابَل بـ`HEAD` كلِّه ⇒ كلُّ هبوطٍ
يُبطلها، **ولو كان وثيقةً لا تمسّ سطرًا من الكود** ⇒ إعادةُ تشغيلٍ إلزاميّةٌ في يوم العرض لسببٍ لا علاقةَ له
بالكود. والضمانُ المطلوبُ أضيقُ من ذلك: **ألّا يُحكم على نتيجةٍ أنتجها كودٌ مخالفٌ لكود الشجرة**.

**الحلُّ:** البصمةُ من **محتوى** ما يعمل فعلًا — `app.py` و`src/**/*.py` مرتَّبةً بأسمائها — لا من تاريخ
الالتزامات. ⇒ تعديلُ حرفٍ في الكود يغيّرها، وهبوطُ وثيقةٍ لا يغيّرها. ويبقى `sha` (الالتزام) في الختم
**للعلم** لا للحكم.

**والحدُّ المُعلَن:** البصمةُ تغطّي الكودَ الذي يُنفَّذ في مسار القراءة/الإجابة (`app.py` + `src/`)، ولا
تغطّي `tools/` (أدواتُ الفحص تُشغَّل في اللحظة نفسِها فيكفي أن تكون من الشجرة) ولا ملفّاتِ الإعداد خارجَ
الشجرة. فمن غيّر `tools/qa_gate.py` وحدَه لا تُبطل بصمتُه — **وهذا مقصودٌ ومُعلَن** لا سهو.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PROJ = Path(__file__).resolve().parents[2]   # جذرُ المستودع: src/statement_qa/code_hash.py ⇒ ../..


def code_files(proj: Path | None = None) -> list[Path]:
    """ملفّاتُ الكود التي تُصوَّر: `app.py` وكلُّ `src/**/*.py` — مرتَّبةً ليكون الترتيبُ حتميًّا."""
    root = Path(proj) if proj else PROJ
    out = [root / "app.py"]
    out += sorted((root / "src").rglob("*.py"))
    return [p for p in out if p.is_file()]


def code_hash(proj: Path | None = None, n: int = 8) -> str:
    """بصمةٌ قصيرة (٨ خانات) لمحتوى ملفّات الكود — تُقارَن نصًّا في الختم وفي البوّابة."""
    root = Path(proj) if proj else PROJ
    h = hashlib.sha256()
    for p in code_files(root):
        h.update(str(p.relative_to(root)).encode("utf-8"))
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:n]
