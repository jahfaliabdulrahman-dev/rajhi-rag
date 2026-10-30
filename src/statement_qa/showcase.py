"""«جرّب الآن» — قراءةٌ مسجَّلةٌ للكشف الاصطناعيّ في **ملفٍّ نصّيٍّ في المستودع**، يُبنى منه دفترُه.

**قرارُ المالك (2026-10-30):** «يعيش دفتر «جرّب الآن»: 1 (ملفّ نصّيّ في git يُبنى منه الدفتر)». فملفُّ
SQLite لا يدخل المستودع (حارسُ النشر و`.gitignore` بقرارٍ سابق)، والنصُّ يدخل ويقرؤه الحارسان.

**والنصُّ مخرجُ قارئَي الدفتر نفسَيهما** (`ledger.read_rows` · `ledger.read_footers`)، **والبناءُ مسارُ
الكتابة الواحد** (`ledger.ingest` — يناديه التطبيقُ عبر `_ledger_write`): فلا كاتبَ ثانٍ ولا مخطَّطَ
منسوخ، وإن رُقّي المخطَّطُ بُني الدفترُ بالجديد. **ولماذا لا تفريغُ المكتبة** (`sqlite3.iterdump`):
يحمل المخطَّطَ القديمَ نفسَه (فيرفضه `read_ledger` بعد أيّ ترقية)، ومعه فهرسُ البحث وسجلُّ الأسئلة.

**والهويّة:** النصُّ يحمل بصمةَ بايتات الكشف الذي قُرئ، وتُقابَل ببصمة `statement_showcase.pdf`
المتتبَّع عند كلّ بناء — نصٌّ لا يطابق ملفَّه يُرفض باسمه، فلا يُعرض دفترُ كشفٍ آخر تحت اسم هذا.

**ويُبنى في مجلّد كلّ جلسة عند الضغط، لا مرّةً عند الإقلاع (شرطُ (ب) الثالث):** الأسئلةُ تُسجَّل في
الدفتر والمحادثةُ تُحفظ فيه، فدفترٌ واحدٌ مشتركٌ يُري زائرًا أسئلةَ غيره.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import ledger as L

_ROOT = Path(__file__).resolve().parents[2]
#: الكشفُ الاصطناعيّ المتتبَّع (قرارُ المالك ف٢ = ب) — بايتاتُ الملفّ الذي قرأه التطبيق.
PDF = _ROOT / "data" / "sample" / "statement_showcase.pdf"
#: قراءتُه المسجَّلة — نصٌّ بجانبه في المستودع.
RECORD = PDF.with_name(PDF.stem + ".ledger.json")

#: اسما القاعدة اللذان يُخرجهما `read_rows` بجانب اسمَي الرندر (`pg`↔`page` · `proof_source`↔`source`)
#: — والنصُّ يحمل أسماءَ الرندر وحدها، وهي ما يقرؤه `ingest`.
_DB_NAMES = ("pg", "proof_source")


class RecordMismatch(RuntimeError):
    """النصُّ المسجَّلُ قراءةُ بايتاتٍ غيرِ بايتات الكشف المتتبَّع."""


def export(conn, source_pdf: Path, read_on: str) -> dict:
    """القراءةُ المسجَّلة من دفترٍ مفتوح — بقارئَيه، وبصمةِ بايتات الكشف الذي قُرئ، وتاريخِ قراءته."""
    footers = L.read_footers(conn)
    return {
        "source": Path(source_pdf).name,
        "source_sha256": L.source_sha256(source_pdf),
        "read_on": read_on,
        # صفحةٌ لكلّ صفحةِ وثيقة في جدول `pages` (R132-1) ⇒ عددُها عددُ صفحات الكشف.
        "n_pages": len(footers),
        "footers": {str(pg): f for pg, f in footers.items()},
        "rows": [{k: v for k, v in r.items() if k not in _DB_NAMES} for r in L.read_rows(conn)],
    }


def dumps(doc: dict) -> str:
    """النصُّ كما يُحفظ: عربيٌّ مقروء، و`Decimal` نصًّا (المالُ لا يُطبَع عائمًا)."""
    return json.dumps(doc, ensure_ascii=False, indent=1, default=str) + "\n"


def recorded(record: Path = RECORD, pdf: Path = PDF) -> dict:
    """القراءةُ المسجَّلة **بعد مقابلة بصمتها ببايتات الكشف** — وإلّا رفضٌ مسمًّى."""
    doc = json.loads(Path(record).read_text(encoding="utf-8"))
    have = L.source_sha256(pdf)
    if doc.get("source_sha256") != have:
        raise RecordMismatch(
            f"بصمةُ القراءة المسجَّلة ({str(doc.get('source_sha256'))[:12]}…) لا تطابق بايتاتِ "
            f"`{Path(pdf).name}` ({have[:12]}…) — النصُّ قراءةُ ملفٍّ آخر، فلا يُعرض تحت اسمه. "
            f"أعِد إنتاجَه: `python tools/ledger.py export` من دفتر قراءةِ هذا الملفّ.")
    return doc
