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


def _verdict_counts(per_page: list[dict]) -> dict[str, int]:
    """عدُّ أحكام الصفحات من صفوف الدفتر — **بمفردات العقد الخمس، والصفرُ مُعلَنٌ لا غائب**.

    **ولماذا هنا:** كاتبُ الإكسل يبني ملخّصَه من `report["footer"]` (عدُّ أحكامٍ لا قائمةَ صفحات)،
    ومساراتُ سطر الأوامر تكتبه من منسّق التشغيلة (`scale_slice`). ومسارُ الزرّ كان لا يكتبه ⇒
    أعدادُ الملخّص كلُّها صفر. والعدُّ هنا من **مصدرٍ واحد**: صفوفُ `pages` التي رُندِر منها الملفّ.
    """
    counts = {k: 0 for k in ("ok", "mismatch", "absent", "unchecked", "gap")}
    for d in per_page:
        v = str(d.get("verdict") or "").strip()
        counts[v if v in counts else "unchecked"] += 1
    return counts


def export_xlsx_from_state(rows: list[dict], footers: dict | None = None, *,
                          profile: Path | str | None = None,
                          out_dir: Path | None = None,
                          gate: Path | None = None,
                          run: Path | None = None,
                          printed_pages: dict | None = None,
                          read_pages=None,
                          recoveries=None, rereads=None) -> tuple[Path | None, str]:
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
        pages = L.pages_from_state(rows, footers)
        # **رقمُ الصفحة المطبوع من مصدره (R93-4):** `pages_from_state` تقرؤه من الصفوف إن حملته،
        # وصفوفُ التطبيق لا تحمله (القراءةُ تحفظه في `STATE["printed_pages"]` من `page_no_by_pg`)
        # ⇒ يُمرَّر من الحالة. وبلا مصدرٍ يبقى العمودُ الرقميُّ فارغًا (لا يُخترع رقم)، والعرضُ
        # يسمّي الفراغ «غيرُ مقروء».
        for pg, printed in (printed_pages or {}).items():
            entry = pages.get(int(pg))
            if entry is not None and isinstance(printed, int):
                entry["page_no"] = printed
        # **والصفحةُ التي قُرئت ولا حركات فيها تُكتب صفحةً (R94-3):** الدفترُ يُبنى من الصفوف
        # والتذييلات وحدَهما، فصفحةٌ قُرئت ولا حركةَ فيها **تسقط من الدفتر أصلًا** ⇒ يقول ملخّصُ
        # الملفّ «صفر صفحات بلا حركات» بينما ورقةُ «ما لم يُثبت» **تسمّيها** — تناقضٌ داخل ملفٍّ
        # يُسلَّم. والقارئُ يحكم على هذه الصفحة بـ`absent` (لا حركات) وهو الحكمُ نفسُه الذي يكتبه
        # مسارُ سطر الأوامر ⇒ **فالمصدرُ واحدٌ والمعنى واحد.**
        for pg in (read_pages or []):
            entry = pages.get(int(pg))
            if entry is None:
                pages[int(pg)] = {"page_no": None, "footer": "absent", "rows": 0, "usage": None}
            elif not entry.get("rows") and str(entry.get("footer") or "").strip() in ("", "unchecked", "None"):
                entry["footer"] = "absent"
        stats = L.ingest(conn, rows, pages)
        # **أحكامُ الصفحات تُقرأ من الدفتر لا من التقرير** (مقيس: مجلّدُ تشغيلٍ بلا مخبّآت كان يُسقط
        # ورقةَ «ما لم يُثبت» كاملةً ⇒ ملفٌّ ناقصٌ يقرؤه صاحبُه تامًّا). فالمصدرُ واحد: جدول `pages`.
        # **الاسمُ المزدوج مقصودٌ (قِيس):** كاتبُ الإكسل يقرأ `footer`/`rows`/`page_no`، ومدخلاتُ
        # الدفتر تستعمل `verdict`/`rows_count`/`printed_page`. فتُكتب بالاسمين ⇒ لا خمولَ ولا كسرَ قارئ.
        per_page = []
        for row in conn.execute("SELECT pg, printed_page, verdict, rows_count FROM pages ORDER BY pg"):
            d = dict(row)
            # **والعمودُ نصّيّ في الدفتر** ⇒ يُعاد رقمًا كما هو في تقرير CLI، وإلّا اختلف الملفّان
            # في النوع وحده ('2' مقابل 2) — وهو فرقٌ يُقاس ولا يُتسامَح عنه (R93-4).
            printed = d["printed_page"]
            if isinstance(printed, str) and printed.strip().isdigit():
                printed = int(printed.strip())
            per_page.append({"page": d["pg"], "pg": d["pg"],
                             "page_no": printed, "printed_page": printed,
                             "footer": d["verdict"], "verdict": d["verdict"],
                             "rows": d["rows_count"], "rows_count": d["rows_count"]})
    finally:
        conn.close()

    owned_run = run is None
    if run is None:
        role = _contract_footer_role(profile)
        if role in ("", "غير مُعلن في العقد"):
            return None, ("العقدُ لا يُعلن دورَ التذييل ⇒ لا يُسلَّم ملفٌّ يخالف عقده. "
                          f"راجع: {profile}")
        run = work / "run"
        (run / "results").mkdir(parents=True, exist_ok=True)
        # **التقريرُ يحمل الدورَ من العقد حرفيًّا** ⇒ فلا يخالف `build` بين العقد والتقرير.
        # **و`totals` تُكتب (R93-4):** ورقةُ «كيف تُقرأ هذه الأوراق» تقرأ عددَ الحركات المحتسبة
        # من `report["totals"]["rows"]` — وكان الزرُّ لا يكتبه ⇒ «None معاملة» و«المحتسب في
        # التقرير None» مطبوعةً في ملفٍّ يُسلَّم. والقيمةُ من **الدفتر** (مصدر الصفوف) لا من عدٍّ ثانٍ.
        (run / "slice_report.json").write_text(
            json.dumps({"footer_role": role, "per_page": per_page,
                        # **وعدُّ الأحكام يُكتب (R94-3):** كاتبُ الإكسل يقرأ `report["footer"]` لعدّ
                        # «بلا حركات / غير قابلة للتحقق / فجوات» في الملخّص، وكان الزرُّ **لا يكتبه**
                        # ⇒ فكلُّ تلك الأعداد **صفر** في ملفٍّ يُسلَّم: «0 بلا حركات» بينما ورقةُ
                        # «ما لم يُثبت» تسمّيها — تناقضٌ داخليّ. والعدُّ من **الدفتر** (جدول `pages`)
                        # لا من عدٍّ ثانٍ: كلُّ حكمٍ يُعدّ باسمه، والمفرداتُ الخمسُ تبقى ظاهرةً وإن
                        # كانت صفرًا (فالصفرُ المُعلَن يفرق عن الغياب).
                        "footer": _verdict_counts(per_page),
                        "totals": {"rows": stats["rows"], "pages": stats["pages"]}},
                       ensure_ascii=False),
            encoding="utf-8")
    else:
        run = Path(run)

    # **مخبّأ كلّ صفحة** — يقرؤه كاتبُ الإكسل للرايات وإجماليات المطبوع (`to_xlsx.py:315-323`).
    # ويُكتب في التشغيلة التي بنيناها: أمّا تشغيلةٌ مُمرَّرة فمخبّآتها ليست ملكَنا فلا نمسّها.
    if owned_run:
        recovered_pages = {int(e.get("page")) for e in (recoveries or []) if e.get("page") is not None}
        reread_pages = {int(e.get("page")) for e in (rereads or []) if e.get("page") is not None}
        by_page: dict[int, list[dict]] = {}
        for r in rows:
            pg = r.get("page")
            if pg is not None:
                by_page.setdefault(int(pg), []).append(r)
        # **ومخبّأٌ لكلّ صفحةٍ قرأها الدفتر — لا لصفحات الصفوف وحدَها (R94-3):** كانت المخبّآتُ تُكتب
        # لصفحاتٍ فيها صفوفٌ فقط، فصفحةُ «بلا حركات» (وهي صفحةٌ حقيقيّةٌ في الكشف — أو الصفحةُ
        # الختامية) **تختفي من العدّ** ⇒ يقول ملخّصُ الملفّ «صفر صفحات بلا حركات» بينما ورقةُ
        # «ما لم يُثبت» تسمّيها، وورقةُ التحقق تفقد صفَّها ⇒ **تناقضٌ داخل ملفٍّ يُسلَّم**. والعدُّ هنا
        # من **الدفتر** (كلُّ صفحةٍ في `pages`)، لا من الصفوف ⇒ فلا مخبّأَ ناقص.
        all_pages = sorted({int(d["pg"]) for d in per_page})
        for pg in all_pages:
            page_rows = by_page.get(pg, [])
            footer = (footers or {}).get(pg)
            if footer is None:
                footer = (footers or {}).get(str(pg))
            (run / "results" / f"pg-{pg:03d}.json").write_text(
                json.dumps({"pg": pg, "raw_rows": page_rows,
                            "recovered": pg in recovered_pages, "reread": pg in reread_pages,
                            "error": False, "arbitrated_by": None,
                            "footer": footer or {}}, ensure_ascii=False, default=str), encoding="utf-8")

    out = work / "statement.xlsx"
    try:
        build(run, out, gate, profile=profile, ledger_db=db)
    except SystemExit as exc:                                   # noqa: PERF203
        return None, f"رفض الكاتبُ التسليم: {exc}"
    return out, (f"رُندِر من الدفتر: {stats['rows']} صفًّا · {stats['pages']} صفحة"
                 + (f" · واستُبعد {stats['dropped_no_page']} صفًّا بلا صفحة"
                    if stats.get("dropped_no_page") else ""))
