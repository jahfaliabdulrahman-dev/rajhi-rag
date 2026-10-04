"""رندرةُ ملفّ الإكسل **من حالة التطبيق** — وهي النواةُ التي يستدعيها زرُّ التنزيل.

**العطبُ الذي يمنعه:** زرٌّ يبني الملفَّ بطريقٍ ثانٍ (Polars مباشرةً أو `DataFrame`) ⇒ **حكمان لملفٍّ
واحد** يفترقان صامتين: خليّةٌ تصلح في الزرّ وتفسد في سطر الأوامر. فالطريقُ **واحد**:

    حالةُ التطبيق  →  دفترُ SQLite (أ-٣)  →  to_xlsx.build(ledger_db=…)

**ولماذا دفترٌ وسيطٌ لا استدعاءٌ مباشر:** كاتبُ الإكسل لا يقبل صفوفًا — يقبل **مجلّدَ تشغيلٍ** أو
**دفترًا** (`tools/to_xlsx.py:827`). والدفترُ هو المصدرُ الذي رُندِر منه الملفُّ في الخارطة (أ-٣)،
فيصير الزرُّ والـCLI **مصدرًا واحدًا** لا مصدرين يُقابَلان.

**وحدُّه المُعلَن:** `slice_report.json` يُكتب بدور التذييل **من العقد** (`profiles/al-rajhi.json`
افتراضًا — وهو نفسُ افتراض الـCLI)، وبـ`per_page` **مقروءةٍ من جدول `pages` في الدفتر**؛ وأحكامُ الصفحات تأتي من الدفتر لا من التقرير. فإن غاب العقدُ صار الدورُ «غير مُعلن في العقد» **وتوقف الرندرُ بصوتٍ
مسموع** بدل أن يُسلَّم ملفٌّ يخالف عقده.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def default_profile() -> Path:
    """عقدُ التذييل الافتراضيّ — **نفسُ افتراض الـCLI** (`tools/to_xlsx.py:1279`)."""
    return _ROOT / "profiles" / "al-rajhi.json"


def export_xlsx_from_state(rows: list[dict], footers: dict | None = None, *,
                          profile: Path | str | None = None,
                          out_dir: Path | None = None,
                          gate: Path | None = None,
                          run: Path | None = None) -> tuple[Path | None, str]:
    """(مسارُ الملفّ أو None، رسالةٌ تُعرَض للمستخدم) — **والفشلُ يُعلَن ولا يُخترع ملفّ**.

    **ولا يُبتلع `SystemExit` بصمت:** كاتبُ الإكسل يرفض التسليم عند اختلاف الاشتقاق أو دورِ التذييل
    (`to_xlsx.py:846`)، ورفضُه **إشارةُ أمانةٍ** لا عطبٌ ⇒ تُلتقَط وتُعاد نصًّا مقروءًا.

    `run`: مجلّدُ تشغيلٍ جاهزٌ (حين تُقاس البوّابة على مجلّدٍ واحدٍ للطرفين)؛ وإن غاب كُتب مجلّدٌ
    وسيطٌ **بدور التذييل من العقد** وبأحكام الصفحات من **الدفتر** لا من التقرير.
    """
    from statement_qa import ledger as L                                   # noqa: PLC0415
    from tools.to_xlsx import _contract_footer_role, build                 # noqa: PLC0415

    if not rows:
        return None, "لا صفوفَ بعد — اقرأ كشفًا أولًا."

    profile = Path(profile) if profile else default_profile()
    work = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="rajhi_export_"))
    work.mkdir(parents=True, exist_ok=True)

    db = work / "ledger.db"
    if db.exists():
        db.unlink()                       # تشغيلٌ نظيف: لا صفوفَ باقية من نداءٍ سابق
    conn = L.open_ledger(db)
    try:
        stats = L.ingest(conn, rows, L.pages_from_state(rows, footers))
        # **أحكامُ الصفحات تُقرأ من الدفتر لا من التقرير** (مقيس: مجلّدُ تشغيلٍ بلا مخبّآت كان يُسقط
        # ورقةَ «ما لم يُثبت» كاملةً ⇒ ملفٌّ ناقصٌ يقرؤه صاحبُه تامًّا). فالمصدرُ واحد: جدول `pages`.
        per_page = [dict(row) for row in conn.execute(
            "SELECT pg AS \"page\", printed_page, verdict, rows_count FROM pages ORDER BY pg")]
    finally:
        conn.close()

    if run is None:
        role = _contract_footer_role(profile)
        if role in ("", "غير مُعلن في العقد"):
            return None, ("العقدُ لا يُعلن دورَ التذييل ⇒ لا يُسلَّم ملفٌّ يخالف عقده. "
                          f"راجع: {profile}")
        run = work / "run"
        (run / "results").mkdir(parents=True, exist_ok=True)
        # **التقريرُ يحمل الدورَ من العقد حرفيًّا** ⇒ فلا يخالف `build` بين العقد والتقرير.
        (run / "slice_report.json").write_text(
            json.dumps({"footer_role": role, "per_page": per_page}, ensure_ascii=False),
            encoding="utf-8")
    else:
        run = Path(run)

    out = work / "statement.xlsx"
    try:
        build(run, out, gate, profile=profile, ledger_db=db)
    except SystemExit as exc:                                   # noqa: PERF203
        return None, f"رفض الكاتبُ التسليم: {exc}"
    return out, (f"رُندِر من الدفتر: {stats['rows']} صفًّا · {stats['pages']} صفحة"
                 + (f" · واستُبعد {stats['dropped_no_page']} صفًّا بلا صفحة"
                    if stats.get("dropped_no_page") else ""))
