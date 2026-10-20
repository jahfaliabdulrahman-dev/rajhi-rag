"""واجهةُ الدفتر في التطبيق — **منطقٌ نقيٌّ يُختبر بلا Gradio**، و`app.py` يوصّله بأزرارٍ فقط.

**العِلّة:** قسمُ الواجهة يحتاج أربعةَ أشياء — نصَّ الحالة، تسميةَ الأقصد بالعربية، صياغةَ الجواب،
وبناءً من حالة التطبيق. وكلُّها منطقٌ يُختبر بلا سطحٍ رسوميّ؛ فوجودُه في `app.py` يعني منطقًا لا يُقاس
إلّا بتشغيل التطبيق — **وهو بعينه صنفُ العطب الذي أمسكه مقعدُ الترتيب** حين قاس مسارَ الأداة على
`--json` وحدَه. فالقاعدة: ما يمكن قياسُه بلا شاشةٍ يُخرَج من الشاشة.

**والكلفة:** كلُّ ما هنا يقرأ من SQLite — **ولا نداءَ نموذجٍ واحدًا** (وضابطٌ يُثبت ذلك بفخّ شبكةٍ
مُصاد في `tests/test_ledger_ui.py`). ولذلك تُسمّى هذه الأسئلةُ في الواجهة «بلا كلفة».

**والشكلُ صار بياناتٍ لا Markdown (R130-3):** كان `_render` يبني جدولَ Markdown بيده، فوصفٌ فيه سطرٌ
جديد (أو `|`) يكسر الصفَّ كلَّه — قِيس ٤٩ صفًّا في دفتر المالك منها ٨ من ١٧ نتيجةَ «تحويل». والآن
تُعاد `{"note", "headers", "rows"}` ويعرضها `gr.Dataframe` (مكوّنُ Gradio)، فالسطرُ الجديد يبقى في
خانته **بالبناء** لا بالتهريب.

**ومفتاحُ الكشف انتقل إلى `ledger.statement_key` (R130):** سطرُ الأوامر يكتب القاعدةَ نفسَها بمفتاحٍ
واحد، فالمفتاحُ مفهومُ قاعدةٍ لا مفهومُ شاشة — والاسمُ هنا يُبقي الواجهةَ على عهده.
"""
from __future__ import annotations

import json
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

#: المفتاحُ نفسُه — **موضعُ التعريف في `ledger`** (يقرؤه التطبيقُ وسطرُ الأوامر معًا).
statement_key = L.statement_key

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

#: **مؤشّرُ الكشف النشِط** — ملفٌّ صغيرٌ في مجلّد بيانات المستخدم يُتيح للواجهة أن تعرف *أيّ* قاعدةٍ
#: تفتح بعد إعادة التشغيل (وإلّا لم يُنزَّل الحوارُ بعد إغلاق التطبيق). ويُحذف مع بيانات الكشف.
ACTIVE_FILE = "active.json"


def parse_page(text: str) -> int | None:
    """رقمُ صفحةٍ من نصٍّ عربيِّ الأرقام — و`None` إن لم يكن رقمًا (فيُقال للمستخدم لا يُخمَّن)."""
    t = (text or "").translate(_DIGITS).strip()
    return int(t) if t.isdigit() else None


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


def status_text(root: Path, key: str | None, rows_count: int, dropped: int = 0) -> str:
    """نصُّ الحالة المعروضُ فوق الأزرار: **غائبٌ يُعلن غيابَه، وخطأٌ يُسمّى باسمه**، ومقروءٌ يُعدّ أرقامَه.

    وثلاثُ حالاتٍ لا رابعة: (١) لا كشفَ محمَّلًا، (٢) الدفترُ غيرُ مبنيّ بعد، (٣) مبنيٌّ ⇒ **يُقرأ
    فعلًا** (`coverage`) فتُعرَض أرقامُه — فلا يُدّعى «جاهز» بنصٍّ لم يُقابل بقاعدة.
    **ومع الجديد (R130):** الحالةُ تُقابل قاعدةً **مطابقةً للقراءة الحالية**؛ قاعدةٌ تحمل عددًا آخر
    من الصفوف لا تُقرأ «جاهز» بل تُسمّى «لا تطابق القراءة» — فلا تبقى نسخةٌ قديمةٌ تحت اللافتة.
    """
    key = key or active_key(root)
    path = ledger_file(root, key) if key else None
    if not rows_count:
        if path is not None and path.exists():
            return (f"### دفترُ الكشف\n**قاعدةٌ محفوظةٌ من جلسةٍ سابقة** (`{path.name}`) — "
                    f"اقرأ كشفًا لتُحدَّث، أو اسأل أسئلتَها من هنا، أو احذف بياناتها بالزرّ الأحمر.")
        return ("### دفترُ الكشف\n**لا كشفَ محمَّلًا بعد** — اقرأ كشفًا في التبويب ١ ثمّ عُد."
                + _dropped_note(dropped))
    if path is None:
        return ("### دفترُ الكشف\n**لا مفتاحَ للكشف بعد** — اقرأ كشفًا في التبويب ١ (القراءةُ تكتب "
                "القاعدةَ تلقائيًّا).")
    try:
        conn = L.read_ledger(path)
    except L.LedgerUnavailable as e:
        return (f"### دفترُ الكشف\n**تعذّر فتحُ الدفتر — {e}**\n\n"
                f"المسار: `{path.name}` · والحلُّ: أعد قراءة الكشف (القراءةُ تكتب القاعدةَ بلا كلفةٍ "
                f"إضافيةٍ على السؤال)، أو احذف بياناتِ هذا الكشف.")
    try:
        cov = L.answer(conn, "coverage")
        ver = conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()
    if cov["rows"] != int(rows_count):
        return (f"### دفترُ الكشف\n**القاعدةُ لا تطابق القراءةَ الحالية** — "
                f"القاعدةُ **{cov['rows']}** صفًّا والقراءةُ **{rows_count}** صفًّا. "
                f"أعد قراءة الكشف لتُحدَّث القاعدة (لا نسخةَ قديمةَ تحت «جاهز»)."
                + _dropped_note(dropped))
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

    **والقراءةُ صارت تكتبه تلقائيًّا (R130)**، وهذا الزرُّ يبقى **إعادةَ بناءٍ يدويّة** (بعد تعديلِ
    تذييلٍ أو لفحصٍ) — لا الطريقَ الوحيد. **ومصدرُ الرقم يُعلَن:** الصفوفُ من قراءة التطبيق، وأحكامُ
    الصفحات من حالة التطبيق، وكلفةُ الصفحة لا تُملأ (حالةُ التطبيق تحمل كلفةً كلّيّةً لا لكلّ صفحة).
    """
    if not rows:
        return "**لا صفوفَ لبناء دفترٍ منها** — اقرأ كشفًا أولًا."
    pages = L.pages_from_state(rows, footers)
    key = key or statement_key(None, L.pages_of(rows))
    path = ledger_file(root, key)
    conn = L.open_ledger(path)
    try:
        got = L.ingest(conn, rows, pages)
        cov = L.answer(conn, "coverage")
    finally:
        conn.close()
    active_set(root, key)
    orphan = got.get("dropped_no_page") or 0
    note = (f"\n> **{orphan} صفًّا بلا حقل صفحةٍ في المصدر** — لم تُدخَل (المخطَّطُ يمنع صفًّا بلا "
            f"صفحة: `pg` مفتاحٌ أساسيّ) وليس إسقاطًا صامتًا: العددُ مُعلَنٌ هنا." if orphan else "")
    stale = got.get("pruned_rows") or 0
    stale_note = f" · وأُزيل {stale} صفًّا قديمًا" if stale else ""
    return (f"**بُني الدفترُ** ✅ — {got['rows']} صفًّا · {got['pages']} صفحة · "
            f"{cov['unproven']} بلا إثبات · الملفّ `{path.name}`{stale_note}{note}")


def ask(root: Path, key: str | None, label: str, value: str = "") -> dict:
    """جوابُ قصدٍ من القائمة المغلقة — **بياناتٌ للعرض** (`note` + `headers` + `rows`)، من SQL وحدَه.

    الحقول: `note` جملةٌ تُقرأ (أو الخطأُ المسمّى)، و`headers`/`rows` جدولٌ للـ`gr.Dataframe`.
    ويرفض بلا استثناء: قصدًا بغير المفاتيح المُعلَنة، وقيمةً غائبةً لقصدٍ يحتاجها، ودفترًا غيرَ مقروء
    ⇒ برسالةٍ مسمّاةٍ في كلّ حال (فالشاشةُ لا تعرض traceback أبدًا).
    """
    intent = INTENT_LABELS.get(label)
    if intent is None:
        return _msg(f"**قصدٌ غيرُ مُعدَّد** — المسموح: {' · '.join(INTENT_LABELS)}")
    if intent in NEEDS_VALUE and not (value or "").strip():
        want = "رقمَ الصفحة" if intent == "pages" else "نصَّ البحث"
        return _msg(f"**هذا القصدُ يحتاج {want}** — اكتبه في خانة القيمة ثمّ أعد المحاولة.")
    pg = None
    if intent == "pages":
        pg = parse_page(value)
        if pg is None:
            return _msg(f"**«{value}» ليس رقمَ صفحة** — اكتب رقمًا (عربيًّا أو لاتينيًّا).")
    key = key or active_key(root)
    if not key:
        return _msg("**لا كشفَ بعد** — اقرأ كشفًا في التبويب ١ (القراءةُ تكتب القاعدةَ تلقائيًّا).")
    path = ledger_file(root, key)
    try:
        conn = L.read_ledger(path)
    except L.LedgerUnavailable as e:
        return _msg(f"**تعذّر فتحُ الدفتر — {e}**\n\nأعد قراءة الكشف (القراءةُ تكتب القاعدةَ)، "
                    f"أو احذف بياناتِ هذا الكشف.")
    try:
        got = L.answer(conn, intent, pg=pg, q=(value or None) if intent == "search" else None,
                       limit=25)
    finally:
        conn.close()
    return _table(got)


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


def _msg(text: str) -> dict:
    return {"note": text, "headers": [], "rows": []}


def _table(got: dict) -> dict:
    """جدولُ الجواب: `headers` + `rows` **كما هي** (وصفٌ بسطرٍ جديد يبقى في خانته)."""
    intent = got["intent"]
    if intent == "totals":
        return {"note": f"جمعٌ عشريٌّ من نصّ (لا عائم) على **{got['rows_counted']}** صفًّا.",
                "headers": ["البند", "المبلغ", "الصفوف"],
                "rows": [["المجموع المدين", got["debit"], got["debit_rows"]],
                         ["المجموع الدائن", got["credit"], got["credit_rows"]]]}
    if intent == "coverage":
        return {"note": " · ".join(f"{k}: {v}" for k, v in got["page_verdicts"].items()),
                "headers": ["البند", "القيمة"],
                "rows": [["صفوف", got["rows"]], ["صفحات", got["pages"]],
                         ["بلا إثبات", got["unproven"]]]}
    if intent == "unproven":
        if not got["count"]:
            return _msg("**لا صفَّ بلا إثبات** ✓ — كلُّ صفٍّ يحمل شاهدَه.")
        return {"note": f"**{got['count']} صفًّا بلا إثبات** (يُعرَض {len(got['rows'])}).",
                "headers": ["صفحة", "صفّ", "البيان", "المبلغ"],
                "rows": [[r["pg"], r["row_no"], r["desc"] or "", r["amount"] or ""]
                         for r in got["rows"]]}
    if intent == "pages":
        if not got["pages"]:
            return _msg("**لا صفحةَ بهذا الرقم** في هذا الدفتر.")
        return {"note": f"{len(got['pages'])} صفحة.",
                "headers": ["صفحة", "مطبوع", "الحكم", "صفوف"],
                "rows": [[r["pg"], r["printed_page"] or "", r["verdict"], r["rows_count"]]
                         for r in got["pages"]]}
    if intent == "search":
        if not got["rows"]:
            return _msg(f"**لا صفَّ يحمل «{got['query']}»** — والبحثُ لفظيٌّ في البيان (لا دلاليّ).")
        return {"note": f"**«{got['query']}» ⇒ {len(got['rows'])} صفًّا**.",
                "headers": ["صفحة", "صفّ", "البيان", "المبلغ"],
                "rows": [[r["pg"], r["row_no"], r["desc"] or "", r["movement"] or ""]
                         for r in got["rows"]]}
    if not got["qa"]:
        return _msg("**لا سؤالَ مسجَّلًا بعد** في هذا الدفتر — كلُّ سؤالٍ يُطرح في التبويب ٢ يُسجَّل هنا.")
    return {"note": f"آخرُ {len(got['qa'])} سؤالًا مسجَّلًا (بالأحدث).",
            "headers": ["متى", "السؤال", "الجواب", "أدلّة"],
            "rows": [[r["asked_at"], r["question"] or "", r["answer"] or "—", r["evidence"]]
                     for r in got["qa"]]}
