"""ملفُّ قاعدة الكشف في جلسة التطبيق — **مسارُها ومؤشّرُها وحذفُها**، منطقٌ نقيٌّ يُختبر بلا Gradio.

كانت هذه الوحدةُ منطقَ لوحة «دفترُ الكشف — أسئلةٌ بلا نموذج وبلا كلفة» في الواجهة (أقصدُها ونصُّ حالتها
وجداولُ أجوبتها وزرُّ إعادة البناء). **وأُزيلت اللوحةُ بقرار المالك (2026-10-31، إعادةُ تصميم الواجهة)**،
فأُزيل منطقُها معها، ويبقى هنا ما يحتاجه التطبيقُ نفسُه: أين يُكتب ملفُّ القاعدة (`ledger_file`)، وأيُّها
النشِط بعد إعادة التشغيل (`active_*`)، وحذفُه بعدّ (`delete`). والقاعدةُ نفسُها باقية: يكتبها مسارُ القراءة
(`app._ledger_write`)، ومنها تحسب أدواتُ الوكيل، وفيها تُحفظ المحادثة. والأسئلةُ بأقصدٍ ثابتة بلا نموذج
باقيةٌ لصاحب المشروع في سطر الأوامر (`tools/ledger.py ask`).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import ledger as L

#: **مؤشّرُ الكشف النشِط** — ملفٌّ صغيرٌ في مجلّد بيانات المستخدم يُتيح للواجهة أن تعرف *أيّ* قاعدةٍ
#: تفتح بعد إعادة التشغيل (وإلّا لم يُنزَّل الحوارُ بعد إغلاق التطبيق). ويُحذف مع بيانات الكشف.
ACTIVE_FILE = "active.json"


def ledger_dir(root: Path) -> Path:
    """مجلّدُ الدفاتر: `<جذرُ البيانات>/data/ledgers` — **مُهمَلٌ ولا يُتتبَّع** (والحارسُ بامتداده)."""
    return Path(root) / Path(*L.LEDGER_SUBDIR)


def ledger_file(root: Path, key: str) -> Path:
    """ملفُّ دفترِ الكشف — بمفتاحٍ من بصمة الكشف نفسِه (لا عددِ صفحاتٍ قد يتصادم)."""
    import re

    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(key))[:64] or "st_unknown"
    return ledger_dir(root) / f"{safe}.sqlite"


# ── مؤشّرُ الكشف النشِط ─────────────────────────────────────────────────────────
def _active_path(root: Path) -> Path:
    return Path(root) / ACTIVE_FILE


def active_set(root: Path, key: str, name: str = "") -> None:
    """يسجّل قاعدةَ الكشف الحاليّة — لتُفتح بعد إعادة التشغيل (والتنزيلُ يعمل بلا ذاكرة)."""
    import datetime as _dt

    path = _active_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": key, "name": name,
                                "at": _dt.datetime.now().isoformat(timespec="seconds")},
                               ensure_ascii=False), encoding="utf-8")


def active_get(root: Path) -> dict | None:
    try:
        got = json.loads(_active_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return got if isinstance(got, dict) and got.get("key") else None


def active_key(root: Path) -> str | None:
    got = active_get(root)
    return str(got["key"]) if got else None


def active_clear(root: Path, key: str | None = None) -> bool:
    """يمحو المؤشّر — أو يتركه إن كان يشير إلى كشفٍ آخر (لا يُلغي بياناتِ غيره)."""
    got = active_get(root)
    if got is None:
        return False
    if key and got.get("key") != key:
        return False
    try:
        _active_path(root).unlink()
        return True
    except OSError:
        return False


def delete(root: Path, key: str | None) -> dict:
    """يمحو قاعدةَ الكشف (ومحادثتَها داخلها) ويُعيد عدَّ ما حُذف — **الحذفُ بعدّ لا بدعوى.**

    **وإغلاقُ حافظة المحادثة مسؤوليةُ التطبيق قبل هذا:** متّصلٌ مفتوحٌ يُعيد إنشاء `-wal` بعد الحذف.
    ولذلك تُنادى `qa.reset_memory(path)` أوّلًا في `app._delete_statement_click`.
    """
    key = key or active_key(root)
    if not key:
        return {"removed": [], "count": 0, "message": "**لا بياناتَ كشفٍ محفوظة** — لا شيءَ ليُحذف."}
    path = ledger_file(root, key)
    got = L.delete_statement(path)
    active_clear(root, key)
    if not got["count"]:
        return {**got, "message": "**لا ملفَّ قاعدةٍ لهذا الكشف** — لا شيءَ ليُحذف (المؤشّرُ نُظِّف)."}
    return {**got, "message": f"**حُذفت بياناتُ الكشف** — {got['count']} ملفًّا: "
                              + "، ".join(f"`{n}`" for n in got["removed"])}


def write_note(written: dict, missed: list[int]) -> str:
    """**حالةُ القاعدة في سطر الحالة الواحد** (كانت في لوحة الدفتر، وأُزيلت بقرار المالك 2026-10-31)؛ ونتيجةُ
    `app._ledger_write` مُدخلُها. وموضعُها هنا لا في `app.py` لأنّها منطقٌ نقيٌّ يُقاس بلا Gradio (حزمةُ CI الخفيفة):
    كتابةٌ تعذّرت تُسمّى، وقاعدةٌ ناقصةٌ تُسمّى صفحاتُها (فلا يُقرأ «جاهز» كاملًا وهو ناقص · R131-3)، وصفٌّ
    بلا حقل صفحةٍ لم يدخلها يُعدّ (لا إسقاطَ صامت). ونصٌّ فارغٌ حين لا شيءَ يُقال."""
    if not written.get("ok"):
        return f" • ⚠ تعذّرت كتابةُ قاعدة الكشف: {written.get('message') or 'سببٌ غيرُ مسمّى'}"
    note = ""
    if missed:
        note += (" • قاعدةُ الكشف غيرُ مكتملة — لم تُقرأ هذه المرّة: " + "، ".join(f"ص{p}" for p in missed)
                 + " (أرقامُ الصفوف من هذه القراءة وحدَها)")
    dropped = (written.get("stats") or {}).get("dropped_no_page") or 0
    if dropped:
        note += f" • {dropped} صفًّا بلا حقل صفحةٍ في المصدر لم تدخل القاعدة (المخطَّطُ يمنع صفًّا بلا صفحة)"
    return note
