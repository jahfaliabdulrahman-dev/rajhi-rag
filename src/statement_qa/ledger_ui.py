"""واجهةُ الدفتر في التطبيق — **منطقٌ نقيٌّ يُختبر بلا Gradio**، و`app.py` يوصّله بأزرارٍ فقط.

**العِلّة:** قسمُ الواجهة يحتاج أربعةَ أشياء — نصَّ الحالة، تسميةَ الأقصد بالعربية، صياغةَ الجواب،
وبناءً من حالة التطبيق. وكلُّها منطقٌ يُختبر بلا سطحٍ رسوميّ؛ فوجودُه في `app.py` يعني منطقًا لا يُقاس
إلّا بتشغيل التطبيق — **وهو بعينه صنفُ العطب الذي أمسكه مقعدُ الترتيب** حين قاس مسارَ الأداة على
`--json` وحدَه. فالقاعدة: ما يمكن قياسُه بلا شاشةٍ يُخرَج من الشاشة.

**والكلفة:** كلُّ ما هنا يقرأ من SQLite — **ولا نداءَ نموذجٍ واحدًا** (وضابطٌ يُثبت ذلك بفخّ شبكةٍ
مُصاد في `tests/test_ledger_ui.py`). ولذلك تُسمّى هذه الأسئلةُ في الواجهة «بلا كلفة».
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import ledger as L

#: **التسميةُ العربية ⇄ القصدُ الثابت** — والتطابقُ **مجموعةً** لا ترتيبًا (لفظُ «بالضبط» صُحّح:
#: مقعدُ الواجهة قاس أنّ `totals…` يخالف ترتيبَ `INTENTS`، والوظيفةُ لا تتأثّر — والأدقُّ يُقال). والواجهةُ تقبل هذه المفاتيحَ وحدَها ⇒ فلا اسمَ حرٌّ يدخل،
#: ولا استعلامَ يُبنى من نصّ المستخدم (وهو معنى «النموذجُ لا يكتب SQL» في الشاشة كما في الطرفيّة).
INTENT_LABELS: dict[str, str] = {
    "المجاميع (مدين/دائن)": "totals",
    "تغطيةُ الكشف (صفوف · صفحات · بلا إثبات)": "coverage",
    "الصفوفُ بلا إثبات": "unproven",
    "أحكامُ الصفحات": "pages",
    "بحثٌ في البيان": "search",
    "الأسئلةُ المسجَّلة": "qa",
}

#: ما يحتاج قيمةً من المستخدم: قصدُ `pages` رقمًا، وقصدُ `search` نصًّا. وما سواهما يُجاب بلا مُدخل.
NEEDS_VALUE = {"pages", "search"}

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def parse_page(text: str) -> int | None:
    """رقمُ صفحةٍ من نصٍّ عربيِّ الأرقام — و`None` إن لم يكن رقمًا (فيُقال للمستخدم لا يُخمَّن)."""
    t = (text or "").translate(_DIGITS).strip()
    return int(t) if t.isdigit() else None


def ledger_dir(root: Path) -> Path:
    """مجلّدُ الدفاتر: `<جذرُ المستودع>/data/ledgers` — **مُهمَلٌ ولا يُتتبَّع** (والحارسُ بامتداده)."""
    return Path(root) / Path(*L.LEDGER_SUBDIR)


def statement_key(era: dict | None, n_pages: int) -> str:
    """مفتاحُ الكشف: **تجزئةُ بصمته** (لا عددُ صفحاته).

    **العِلّة (مقعدُ الواجهة P3 · مُثبت):** كان الاسمُ `ui_<عدد الصفحات>p.sqlite` ⇒ (١) كشفان
    بـ629 صفحة **يتصادمان**، و(٢) `pages_of(rows)=626` كان يُسمّي الملفَّ `ui_626p` وهو يخزّن 629
    صفحةً. فالمفتاحُ يُشتقّ من **بصمة المحتوى** (`STATE["era"]`) ⇒ الكشفُ نفسُه يُعطي المفتاحَ نفسَه،
    وكشفٌ آخرُ لا يُصادمه. وبلا بصمةٍ يُنسب إلى عدد الصفحات **مع إعلان النقص** في الاسم (`nop-`).
    """
    if era:
        raw = json.dumps(era, sort_keys=True, ensure_ascii=False, default=str)
        return "ui_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"ui_nop-{int(n_pages)}p"


def ledger_file(root: Path, key: str) -> Path:
    """ملفُّ دفترِ الكشف — بمفتاحٍ من بصمة الكشف نفسِه (لا عددِ صفحاتٍ قد يتصادم)."""
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(key))[:64] or "ui_unknown"
    return ledger_dir(root) / f"{safe}.sqlite"


def status_text(root: Path, key: str | None, rows_count: int, dropped: int = 0) -> str:
    """نصُّ الحالة المعروضُ فوق الأزرار: **غائبٌ يُعلن غيابَه، وخطأٌ يُسمّى باسمه**، ومقروءٌ يُعدّ أرقامَه.

    وثلاثُ حالاتٍ لا رابعة: (١) لا كشفَ محمَّلًا، (٢) الدفترُ غيرُ مبنيّ بعد، (٣) مبنيٌّ ⇒ **يُقرأ
    فعلًا** (`coverage`) فتُعرَض أرقامُه — فلا يُدّعى «جاهز» بنصٍّ لم يُقابل بقاعدة.
    """
    if not rows_count:
        return ("### دفترُ الكشف\n**لا كشفَ محمَّلًا بعد** — اقرأ كشفًا في التبويب ١ ثمّ عُد."
                + _dropped_note(dropped))
    path = ledger_file(root, key or "ui_unknown")
    try:
        conn = L.read_ledger(path)
    except L.LedgerUnavailable as e:
        return (f"### دفترُ الكشف\n**تعذّر فتحُ الدفتر — {e}**\n\n"
                f"المسار: `{path.name}` · والحلُّ: اضغط **«ابنِ دفترَ الكشف»** (بناءٌ من القراءة الحالية، "
                f"بلا نموذج وبلا كلفة).")
    try:
        cov = L.answer(conn, "coverage")
        ver = conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()
    return (f"### دفترُ الكشف — مبنيٌّ وجاهز ✅\n"
            f"**{cov['rows']}** صفًّا · **{cov['pages']}** صفحة · **{cov['unproven']}** بلا إثبات · "
            f"نسخةُ المخطَّط `{ver}` · الملفّ `{path.name}`\n\n"
            f"أحكامُ الصفحات: " + " · ".join(f"{k}: {v}" for k, v in cov["page_verdicts"].items())
            + _dropped_note(dropped))


def _dropped_note(dropped: int) -> str:
    """إعلانُ الصفوف بلا صفحة **في نصّ الحالة لا في البناء وحدَه** (مقعدُ الواجهة P3 · مُثبت):
    كان الإعلانُ في مسار البناء، وهو مسارٌ كان ينهار على صفٍّ بلا صفحة ⇒ فلا إعلانَ عمليًّا.
    وصفرٌ هو الصوابُ في مصدرك (قِيس)، فالسطرُ لا يظهر إلّا متى وُجد فعلًا.
    """
    if not dropped:
        return ""
    return (f"\n\n> **{dropped} صفًّا بلا حقل صفحةٍ في المصدر** — لم تُدخَل إلى الدفتر (المخطَّطُ يمنع "
            f"صفًّا بلا صفحة) **وليس إسقاطًا صامتًا**: العددُ مُعلَنٌ هنا.")


def build(root: Path, rows: list[dict], footers: dict | None, key: str | None = None) -> str:
    """يبني الدفترَ من **حالة القراءة الحالية** ويكتب ملخّصًا — بلا نموذجٍ وبلا شبكة.

    **والمصدرُ يُعلَن مع الرقم:** الصفوفُ من قراءة التطبيق، وأحكامُ الصفحات من حالة التطبيق، و**كلفةُ
    الصفحة لا تُملأ** (حالةُ التطبيق تحمل كلفةً كلّيّةً لا كلفةَ صفحة — فلا يُوزَّع رقمٌ بالتخمين).
    """
    if not rows:
        return "**لا صفوفَ لبناء دفترٍ منها** — اقرأ كشفًا أولًا."
    pages = L.pages_from_state(rows, footers)
    path = ledger_file(root, key or "ui_unknown")
    conn = L.open_ledger(path)
    try:
        got = L.ingest(conn, rows, pages)
        cov = L.answer(conn, "coverage")
    finally:
        conn.close()
    # **والصفُّ بلا صفحة يُستبعَد ويُعدّ** — لا يُبقى (المخطَّطُ يمنعه) ولا يُسقَط صامتًا:
    # نصُّ «تُبقى صفوفًا» السابق كان **دعوى يستحيل تنفيذُها** (مقعدُ الواجهة P1 · مُثبت).
    orphan = got.get("dropped_no_page") or 0
    note = (f"\n> **{orphan} صفًّا بلا حقل صفحةٍ في المصدر** — لم تُدخَل (المخطَّطُ يمنع صفًّا بلا "
            f"صفحة: `pg` مفتاحٌ أساسيّ) وليس إسقاطًا صامتًا: العددُ مُعلَنٌ هنا." if orphan else "")
    return (f"**بُني الدفترُ** ✅ — {got['rows']} صفًّا · {got['pages']} صفحة · "
            f"{cov['unproven']} بلا إثبات · الملفّ `{path.name}`{note}\n\n"
            f"وكلفةُ الصفحة **تُترك فارغةً في المسارين**: حالةُ التطبيق تحمل كلفةً كلّيّةً لا لكلّ صفحة، "
            f"و`per_page` في التشغيل المُقاس لا يحمل كلفةَ صفحةٍ أصلًا (قِيس: صفرُ صفحاتٍ بكلفة) — فلا "
            f"يُوزَّع رقمٌ بالتخمين. ومتى حمل التشغيلُ كلفةَ صفحةٍ كُتبت من مسار الأداة.")


def ask(root: Path, key: str | None, label: str, value: str = "") -> str:
    """جوابُ قصدٍ من القائمة المغلقة — يُعاد نصًّا (Markdown) للشاشة، **من SQL وحدَه**.

    ويرفض بلا استثناء: قصدًا بغير المفاتيح المُعلَنة، وقيمةً غائبةً لقصدٍ يحتاجها، ودفترًا غيرَ مقروء
    ⇒ برسالةٍ مسمّاةٍ في كلّ حال (فالشاشةُ لا تعرض traceback أبدًا).
    """
    intent = INTENT_LABELS.get(label)
    if intent is None:
        return f"**قصدٌ غيرُ مُعدَّد** — المسموح: {' · '.join(INTENT_LABELS)}"
    if intent in NEEDS_VALUE and not (value or "").strip():
        want = "رقمَ الصفحة" if intent == "pages" else "نصَّ البحث"
        return f"**هذا القصدُ يحتاج {want}** — اكتبه في خانة القيمة ثمّ أعد المحاولة."
    pg = None
    if intent == "pages":
        pg = parse_page(value)
        if pg is None:
            return f"**«{value}» ليس رقمَ صفحة** — اكتب رقمًا (عربيًّا أو لاتينيًّا)."
    path = ledger_file(root, key or "ui_unknown")
    try:
        conn = L.read_ledger(path)
    except L.LedgerUnavailable as e:
        return f"**تعذّر فتحُ الدفتر — {e}**\n\nاضغط **«ابنِ دفترَ الكشف»** أوّلًا."
    try:
        got = L.answer(conn, intent, pg=pg, q=(value or None) if intent == "search" else None,
                       limit=25)
    finally:
        conn.close()
    return _render(got)


def _render(got: dict) -> str:
    """صياغةُ الجواب في جدولٍ عربيّ يُقرأ في ثوانٍ — والرقمُ مع عدّاده (لا رقمَ بلا مصدره)."""
    intent = got["intent"]
    if intent == "totals":
        return ("| البند | المبلغ | الصفوف |\n|---|---|---|\n"
                f"| المجموع المدين | **{got['debit']}** | {got['debit_rows']} |\n"
                f"| المجموع الدائن | **{got['credit']}** | {got['credit_rows']} |\n\n"
                f"من **{got['rows_counted']}** صفًّا — جمعٌ عشريٌّ من نصّ، لا عائم.")
    if intent == "coverage":
        return (f"**{got['rows']}** صفًّا · **{got['pages']}** صفحة · "
                f"**{got['unproven']}** بلا إثبات.\n\n"
                f"أحكامُ الصفحات: " + " · ".join(f"{k}: {v}" for k, v in got["page_verdicts"].items()))
    if intent == "unproven":
        if not got["count"]:
            return "**لا صفَّ بلا إثبات** ✓ — كلُّ صفٍّ يحمل شاهدَه."
        head = "| صفحة | صفّ | البيان | المبلغ |\n|---|---|---|---|\n"
        body = "\n".join(f"| {r['pg']} | {r['row_no']} | {(r['desc'] or '')[:60]} | {r['amount'] or ''} |"
                         for r in got["rows"])
        return f"**{got['count']} صفًّا بلا إثبات** (يُعرَض {len(got['rows'])}):\n\n{head}{body}"
    if intent == "pages":
        if not got["pages"]:
            return "**لا صفحةَ بهذا الرقم** في هذا الدفتر."
        head = "| صفحة | مطبوع | الحكم | صفوف |\n|---|---|---|---|\n"
        body = "\n".join(f"| {r['pg']} | {r['printed_page'] or ''} | {r['verdict']} | {r['rows_count']} |"
                         for r in got["pages"])
        return f"{head}{body}"
    if intent == "search":
        if not got["rows"]:
            return f"**لا صفَّ يحمل «{got['query']}»** — والبحثُ لفظيٌّ في البيان (لا دلاليّ)."
        head = "| صفحة | صفّ | البيان | المبلغ |\n|---|---|---|---|\n"
        body = "\n".join(f"| {r['pg']} | {r['row_no']} | {(r['desc'] or '')[:60]} | {r['movement'] or ''} |"
                         for r in got["rows"])
        return f"**«{got['query']}» ⇒ {len(got['rows'])} صفًّا**:\n\n{head}{body}"
    if not got["qa"]:
        return "**لا سؤالَ مسجَّلًا بعد** في هذا الدفتر."
    head = "| متى | السؤال | الجواب | أدلّة |\n|---|---|---|---|\n"
    body = "\n".join(f"| {r['asked_at']} | {(r['question'] or '')[:50]} | "
                     f"{(r['answer'] or '—')[:40]} | {r['evidence']} |" for r in got["qa"])
    return f"{head}{body}"
