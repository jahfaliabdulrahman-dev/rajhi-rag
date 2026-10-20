"""Deterministic QA tools over the verified statement rows.

The model NEVER computes: every total/count/extreme comes from these tools,
which operate on the chain-verified table (Decimal, exact). The agent picks a
tool, the tool returns the number WITH its evidence rows (page/row refs), and
the model only phrases the answer.

Filters (all optional, combinable):
- side: the movement DIRECTION only — "مدين" (صادرة) / "دائن" / "الكل".
  مدين ≠ سحب صراف آلي: a debit can be a transfer, a purchase, a fee…
- tx_type: the real TYPE label from the deterministic classifier —
  "سحب صراف آلي", "تحويل صادر", "تحويل وارد", "إيداع نقدي (صراف آلي)",
  "مشتريات (نقاط بيع)", "فواتير ومدفوعات سداد", …
- keyword: substring of the description.
- amount: exact riyal amount after 2dp rounding (accepts 1000 / "9,001.00").
- date_from / date_to: Gregorian range (YYYY-MM-DD) — **البُعدُ الزمنيّ (R130)**، ومعه
  `statement_period` و`balance_on` و`group_by_date` و`movement_days`.

**وقاعدةُ الصدق الزمنيّ (R130-1):** ما لا تسأله أداةٌ عن التاريخ لا يُجاب عنه بدعوى غياب في الكشف.
والمدى خارج فترة الكشف تُسمّيه الأدواتُ «خارج مدّة الكشف» **مع المدّة وسندها** (أول/آخر صفٍّ
مؤرّخ)، وتاريخٌ غيرُ مفهوم يُرفض بحدِّ الأداة لا يُخمَّن. **ولا قائمةَ عباراتٍ تمنع جملة** — المنعُ
بالقدرة (أداةٌ قرأت البُعد) لا باللفظ.

An optional `trace` list (server-side only) records which rows each non-empty
call selected: {"tool": name, "row_nos": [...]}. The evidence panel is built
from that trace — what BUILT the numbers — never from the row refs the model
happens to repeat in prose; and it never enters the text the model reads.
"""
from __future__ import annotations

import re
from datetime import date as _date
from decimal import Decimal, InvalidOperation

# **المالُ في موضعٍ واحد (R93-7):** كان هنا `_MONEY` و`_dec` و`_m` — نسخةٌ ثانيةٌ من
# `statement_qa.money`، **وفرقُهما مقيس:** `money(None)` ⇒ "" و`_m(None)` ⇒ «—» ⇒ افتراقٌ صامتٌ
# ينتظر. فصارت الأدواتُ تنادي الموضعَ الواحد: `money` للتنسيق و`amount` للتحويل الرقميّ.
from statement_qa.money import amount as _dec, money as _money


def _m(value) -> str:
    """**غلافٌ بسطرٍ واحد — لا منطقَ ثانيًا:** الشرطةُ («—») هي صيغةُ العرض في الأدوات وحدَها،
    والمنطقُ (التنسيقُ وحدُّ غير الرقميّ) في `statement_qa.money`."""
    return _money(value, dash="—")

_ROW_DESC_LEN = 70     # حدُّ الوصف في سطر الصفّ — **موضعٌ واحد** (كان ٦٠ في `page_rows` و٧٠ في `search_rows`)

_SIDE_AR = {"debit": "مدين", "credit": "دائن"}


def _side_match(row_side: str, want: str) -> bool:
    w = (want or "").strip()
    if w in ("", "الكل", "كل", "both", "all"):
        return True
    if w in ("مدين", "debit", "المدين"):
        return row_side == "debit"
    if w in ("دائن", "credit", "الدائن"):
        return row_side == "credit"
    # «Match everything» used to be the answer to an unknown filter, so a
    # garbled «مجموع السحوبات» quietly returned the sum of ALL movements in a
    # sentence that looked filtered (audit P3-3). Refusing loudly lets the
    # model correct itself instead of trusting a wrong number.
    raise ValueError(
        f"فلتر اتجاه غير معروف: {w!r} — القيم الصحيحة: مدين / دائن / الكل")


def _parse_amount_arg(amount) -> Decimal | None:
    """Riyal amount -> Decimal(2dp); empty/unparseable -> None (no filter)."""
    if amount in (None, "", "لا شيء"):
        return None
    try:
        return Decimal(str(amount).replace(",", "").replace("٬", "")
                       .strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _number_rows(rows: list[dict]) -> list[dict]:
    """Attach the statement-wide 1-based row number — SAME numbering the RAG
    chunks and the UI sources use (p1 rows 1..N, p2 continues N+1..), so tool
    refs and quoted sources always agree.

    **والقاعدةُ تُحفظ ترتيبَها (R130):** القاعدةُ تُخزّن `seq` وتُقرأ به، فترتيبُ الصفوف الوارد هنا
    هو ترتيبُ الكشف الحقيقيّ — ورقمُ `i+1` هو نفسُه رقمُ الشاشة والمصادر. ولا يُعاد الترتيبُ بـ`pg`.
    **و`seq` إن وُجد فهو الحكم** (R130 · إصلاحُ مقعد البنية): صفوفُ القاعدة تحمله، فيُقرأ كما هو؛
    وإعادةُ ترقيمها بالتسلسل هنا كانت تُنتج رقمًا ثالثًا يخالف الشاشةَ والقاعدةَ معًا.
    """
    return [{**r, "row_no": int(r.get("seq") or i)} for i, r in enumerate(rows, start=1)]


# ── البُعدُ الزمنيّ (R130-1) ────────────────────────────────────────────────────
#: **العلّة:** سؤالُ «الرصيد في تاريخ» كان يُجاب «لا توجد حركات» **بلا أداةٍ سألت التاريخ** — دعوى
#: عن الكشف لا يدعمها شيء. والعلاجُ قدرةٌ لا قائمةُ عبارات: التاريخُ يُقرأ ويُرشَّح ويُجمَّع، وما
#: لا تقدر عليه الأداةُ يُقال **حدَّ أداة**.
_DATE_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _iso_date(row: dict) -> str:
    """تاريخُ الصفّ الميلاديّ `YYYY-MM-DD` — من `date_iso` المخزَّن، وإلّا من الخانة المطبوعة.

    **ولماذا التحويلُ هنا:** صفوفُ التطبيق تحمل `date` (خانةً مطبوعةً قد تجمع هجريًّا وميلاديًّا)،
    وصفوفُ القاعدة تحمل `date_iso` محسوبًا. والقاعدةُ `contract_rows.normalize_date` — **لا قارئَ
    ثانٍ** (وهو درسُ `scope.pages_in`). وما لا يُقرأ تاريخًا يبقى `""` (لا يُخمَّن).
    """
    iso = str(row.get("date_iso") or "").strip()
    if _ISO.match(iso):
        return iso
    from statement_qa.contract_rows import normalize_date     # noqa: PLC0415 — خفيفٌ بلا تبعيّات

    return normalize_date(row.get("date"))[0]


def _parse_date_arg(value, name: str) -> str | None:
    """تاريخُ وسيطٍ (من/إلى) ⇒ `YYYY-MM-DD` — أو `None`، أو **خطأُ أداةٍ مسمّى**.

    والقبول: `2026-03-15` · `2026/03/15` · `20260315` · أرقامٌ عربيةٌ-هنديةٌ أو ممتدّة. وما سواها
    **يُرفض بحدِّ الأداة**: «صيغةُ التاريخ غيرُ مفهومة — استعمل YYYY-MM-DD». ولا يُقرأ تاريخٌ
    تخمينًا، ولا يُحوَّل فشلُ القراءة إلى «لا توجد حركات».
    """
    raw = str(value or "").translate(_DATE_AR).strip()
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    fmt = ""
    if _ISO.match(raw.replace("/", "-")):
        fmt = raw.replace("/", "-")
    elif len(digits) == 8:
        fmt = f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"
    if fmt:
        try:
            return _date.fromisoformat(fmt).isoformat()
        except ValueError:
            pass
    raise ValueError(
        f"{name}={value!r} تاريخٌ غيرُ مفهوم — حدُّ الأداة: تواريخُ ميلاديّةٌ بصيغة YYYY-MM-DD")


def _ref(r: dict) -> str:
    return f"(صفحة {r['page']}، صف {r['row_no']})"


def _desc(r: dict) -> str:
    return (r.get("desc") or "").replace("\n", " ").strip()


def used_rows_from_trace(trace: list[dict]) -> list[int]:
    """Union of the row numbers the tools actually selected — sorted, deduped.
    The evidence backbone: what BUILT the numbers, not what the prose cited."""
    return sorted({no for call in trace for no in call.get("row_nos", [])})


def citation_truth(cited, trace) -> dict:
    """**الاستشهادُ المُصرَّح به يُقابَل بالأثر — ولا يُصدَّق بلفظه** (بوّابةُ أ-٤).

    «الأثرُ» هو الصفوفُ التي **أخذتها الأدواتُ فعلًا** (`used_rows_from_trace`) ⇒ فما استشهد به
    النموذجُ ولم يشهد به الأثرُ **يُسمّى باسمه** (`unsupported`) ولا يُحذف ولا يُمرَّر صامتًا.
    وهذا نصفُ البوّابة الثاني: «**النوعُ يُصلح الاستخراج · والأثرُ يُصلح الصدق**».
    """
    witness = set(used_rows_from_trace(trace or []))
    got: list[int] = []
    unparsed: list = []
    for x in (cited or []):
        try:
            n = int(str(x).strip())
        except (TypeError, ValueError):
            unparsed.append(x)      # **يُسمّى ولا يُسقَط صامتًا** (مقعدُ أ-٤ P3 · مُثبت)
            continue
        if n < 1:
            unparsed.append(x)      # **صفٌّ برقمٍ سالبٍ أو صفر غيرُ موجود** — لا يُعدّ استشهادًا
            continue
        got.append(n)
    cited_sorted = sorted(set(got))
    return {"cited": cited_sorted, "witnessed": sorted(witness),
            "unsupported": [n for n in cited_sorted if n not in witness],
            "unparsed": unparsed}


_FOOTER_AR = {
    "ok": "مطابق",
    "mismatch": "غيرُ مطابق — صفوفُ الصفحة لا تُغلق الرقمَ المطبوع",
    "unchecked": "غيرُ مُتحقَّق — تعذّر الحكم عليها (لا مقارنةَ ممكنة)",
    "absent": "لا سطرَ تذييلٍ مطبوعٍ في هذه الصفحة",
    "gap": "فجوةُ مسح — أوراقٌ ناقصة قبلها فالمقارنةُ التراكميّةُ غيرُ ممكنة",
}


# ── ترميزُ التاريخ المطبوع (R90) ────────────────────────────────────────────────
# **العلّة (مقيسة):** سؤالُ الحزمة «كم صفًّا كُتب تاريخُه بأرقامٍ عربيّةٍ-هندية؟» انتهى **بمهلة** لأنّه
# لا سبيلَ للعدّ بترميز التاريخ: الوكيلُ يستنطق ٥٧٩٢ صفًّا بأدواته ⇒ يتجاوز المهلة. **والترميزُ حقيقيّ
# ومقيسٌ في البيانات:** التاريخُ المطبوع في صدر الوصف عربيٌّ-هنديّ (U+0660-0669) في ٣٣١٠ صفًّا،
# بينما حقلُ `date` المنظَّم يستعمل المجموعةَ **الممتدّة** (U+06F0-06F9) في الأسطر كلِّها — مجموعتان
# لا تُخلطان. فصار العدُّ قدرةً واحدةً في الأداة العامّة بدل «أداةٍ لكلّ سؤال».
_DATE_LEAD = re.compile(r"^\s*([0-9\u0660-\u0669\u06F0-\u06F9]{8})")
_AR_IND = re.compile(r"[\u0660-\u0669]")
_AR_EXT = re.compile(r"[\u06F0-\u06F9]")


def _stored_date_encoding(row: dict) -> str:
    """ترميزُ **حقل التاريخ المخزَّن**: `arabic_ind` (المجموعتان معًا: العربيّة-الهندية والممتدّة —
    وهو تعريفُ الحاكم في `eval_questions`) | `latin` | `none`."""
    dt = str(row.get("date") or "")
    if not dt:
        return "none"
    if re.search(r"[\u0660-\u0669\u06F0-\u06F9]", dt):
        return "arabic_ind"
    return "latin" if re.search(r"\d", dt) else "none"


def _printed_date_encoding(row: dict) -> str:
    """ترميزُ التاريخ **المطبوع** في صدر الوصف: `arabic_ind` | `extended` | `latin` | `none`."""
    m = _DATE_LEAD.match(str(row.get("desc") or ""))
    if not m:
        return "none"
    token = m.group(1)
    if _AR_IND.search(token):
        return "arabic_ind"
    if _AR_EXT.search(token):
        return "extended"
    return "latin"


def make_qa_tools(rows: list[dict] | None = None, trace: list[dict] | None = None,
                  footers: dict | None = None, conn=None):
    """Bind the verified rows to LangChain tools (import kept lazy).

    **ومصدرُ الصفوف صار القاعدةَ نفسَها (R130 · قرارُ المالك · الخيار ١):** بتمرير `conn` تُقرأ
    الصفوفُ والتذييلاتُ من القاعدة (`ledger.read_rows`/`read_footers`) **لا من قائمةٍ في الذاكرة**؛
    فالسؤالُ يُجاب ولو فرغت حالةُ التطبيق — وهو شرطُ القبول المنصوص. و`rows` يبقى للتجارب والوحدات
    التي تبني صفوفًا بلا قاعدة (والاختبارات). **ولا مصدران معًا:** `conn` يعلو ويُتجاهَل `rows`
    حين يُمرَّر (وإلّا قُرئت نسخةٌ قديمةٌ بجانب القاعدة).

    When `trace` is a list, **every** call appends
    ``{"tool": name, "args": {…what was passed…}, "row_nos": [...]}`` — the raw
    material for the evidence panel. Pure bookkeeping: it never changes any
    tool's return text. (**المدخلاتُ تُسجَّل لكلّ نداء — R109-3** · وكان لا يُسجَّل
    إلا ما اختار صفوفًا، فيقرأ المحاسبُ الأثرَ ناقصًا.)

    `footers` (optional): per-page **printed** footer totals as read from the
    page itself, with their match verdict — the external referee made
    answerable (R77 · مراجعة ٧٧). Its absence is declared by the tool, not
    guessed around.

    **وكلُّ أداةٍ ترفض المدخلَ المجهول (R109-3 · مراجعة ١١٧):** كان مخطّطُ المكتبة
    يتجاهل الخانةَ الزائدة **صامتًا** (قِيس: نداءٌ بـ`foo=1` ينفّذ ويعيد جوابًا كأنّ لا
    شيءَ زائدًا) ⇒ فصار المخطّطُ يُبنى من التوقيع نفسه **بـ`extra="forbid"`**.

    **والطبقةُ اليدويّة أُزيلت (R118-1 · مراجعة ١١٨):** كانت فوق `forbid` مُحقِّقًا
    (`@model_validator(mode="before")`) يرفع خطأً **على مستوى النموذج كلّه بلا `loc`**،
    ومرشّحةُ `ToolNode` (`_filter_validation_errors`) تُسقِط ما ليس على وسيطٍ يتحكّم به
    النموذج ⇒ **فرسالتُه تصل النموذجَ فارغة**: قِيس عبر `answer_question` بنموذجٍ مُبرمَج
    `"… with error:\n \n Please fix the error and try again."` — بلا اسمِ الخانة، فلا يعرف
    النموذجُ ما يُصلح (وهو صنفُ سقوط `cit-02` في جولاتٍ سابقة). والمكتبةُ تسمّي الخانةَ
    بنفسها (`page: Extra inputs are not permitted`) **والوسائطُ المقبولةُ معلَنةٌ في مخطّط
    الأداة المرسَل** ⇒ فلا طبقةَ يدويّةً تُفرِغ الرسالة (ومكوّنُ المكتبة أولى — قاعدةُ المالك).
    """
    from langchain_core.tools import tool

    if conn is not None:
        from statement_qa import ledger as _L                      # noqa: PLC0415
        from statement_qa.classify import annotate_types          # noqa: PLC0415

        rows = _L.read_rows(conn)
        # **وسطحُ الأدوات يُشتقّ من عقد القاعدة (R130):** القاعدةُ تحفظ ٢٢ عمودَ عقدٍ لا سطحَ
        # العرض؛ فـ`kind` يُشتقّ من `opening`/`balance`، والنوعُ يُعاد تصنيفُه بـ`annotate_types`
        # — **الباني الواحد** (لا نسخةً ثانيةً من قواعد التصنيف) ⇒ فما تقوله الأدواتُ من نوعٍ هو ما
        # تقوله الشاشةُ بالحرف. **ولا عمودَ نوعٍ في القاعدة:** النوعُ مُشتقٌّ رخيصٌ من الوصف، وتخزينُه
        # يفتح بابَ انزياحٍ صامتٍ بين المخزَّن والمحسوب.
        for r in rows:
            # الترجمةُ الوحيدةُ `pg`⇒`page` (اسمُ العمود في القاعدة) ثمّ سطحُ العرض المشتقّ.
            r["page"] = r.get("pg", r.get("page"))
            r["kind"] = ("opening" if r.get("opening")
                         else "txn" if r.get("balance") is not None else "summary")
        annotate_types(rows)
        footers = _L.read_footers(conn) if footers is None else footers
    numbered = _number_rows(rows or [])
    movements = [r for r in numbered if r.get("kind") == "txn"
                 and r.get("movement") is not None]
    #: **المدى الزمنيّ للكشف** — يُحسب مرّةً من الصفوف، وتستعمله أدواتُ الزمن الثلاثُ برسالةٍ واحدة
    #: («خارج مدّة الكشف + المدّة + سندها») فلا تختلف صياغةُ الحدّ بين أداةٍ وأخرى.
    dated = [(iso, r) for r in numbered if (iso := _iso_date(r))]
    first_dated = min(dated, key=lambda p: p[0]) if dated else None
    last_dated = max(dated, key=lambda p: p[0]) if dated else None
    #: المدّةُ كوحدةٍ واحدة `(أوّل، آخر، صفُّ الأوّل، صفُّ الآخر)` — أو `None` إن لا تاريخ.
    period = ((first_dated[0], last_dated[0], first_dated[1], last_dated[1])
              if first_dated and last_dated else None)
    undated_rows = [r for r in numbered if not _iso_date(r)]
    # **وحالةُ «لم تُقرأ» تصل من القاعدة في موضعٍ واحد (R133-1):** `read_footers` يحمل `basis`،
    # والصفحةُ التي لم تُقرأ تُوسم `unread`. فأدواتُ الصفحة تقول «لم تُقرأ» (كما `page_footer`)،
    # ومجاميعُ الكشف تسمّي ما لم يدخلها — ولا كلمةَ زائدةً على قاعدةٍ كاملة.
    unread_pages = sorted(pg for pg, f in (footers or {}).items()
                          if (f or {}).get("basis") == "unread")

    def _unread_reply(pg) -> str | None:
        """رسالةُ صفحةٍ داخلةٍ في الكشف ولم تُقرأ — **لا دعوى غيابٍ ولا صفرٌ يُخترع**."""
        pg = int(pg)
        if pg not in unread_pages:
            return None
        return (f"**الصفحة {pg} داخلةٌ في الكشف ولم تُقرأ هذه المرّة** — لا سطورَ ولا تذييل لها، "
                f"فلا أُعلن غيابًا فيها ولا أُخرج لها صفرًا.")

    def _unread_note() -> str:
        """ذيلُ المجاميع: يسمّي ما لم يدخلها. **وفارغٌ على قاعدةٍ كاملة** (صفرُ كلمةٍ زائدة)."""
        if not unread_pages:
            return ""
        listed = "، ".join(f"ص{p}" for p in unread_pages)
        return f" · **ولم تُقرأ: {listed} — لا تدخلها هذه الأرقام**"

    def _strict_args(fn):
        """مخطّطُ وسائط الأداة: من **التوقيع نفسه** + منعُ المدخل المجهول (R109-3 · R118-1)."""
        from langchain_core.tools.base import create_schema_from_function    # noqa: PLC0415
        from pydantic import ConfigDict                                     # noqa: PLC0415

        base = create_schema_from_function(fn.__name__, fn)

        class StrictArgs(base):                     # pylint: disable=too-few-public-methods
            # **ولا مُحقِّقَ يدويًّا فوقه (R118-1):** خطأُ `extra_forbidden` من المكتبة
            # يحمل `loc=('page',)` فيمرّ إلى النموذج باسم الخانة، وخطأُ المُحقِّق اليدويّ
            # على مستوى النموذج (بلا `loc`) تُسقِطه مرشّحةُ `ToolNode` ⇒ نصٌّ فارغ.
            model_config = ConfigDict(extra="forbid")

        return StrictArgs

    def _tool(fn):
        """`@tool` + المخطّطُ الصارم — **موضعٌ واحد** فلا تُنسى أداةٌ من ثمانٍ."""
        return tool(args_schema=_strict_args(fn))(fn)

    def _record(name: str, sel: list[dict], args: dict | None = None) -> None:
        """Server-side evidence trace — zero tokens, no text markers.

        **والنداءُ يُسجَّل كلُّه** (بصفوفٍ أو بلا): المدخلُ محفوظٌ كما وصل، والصفوفُ كما
        اختارتها الأداة ⇒ فالوصلُ يُقرأ من الأثر لا يُفترض.
        """
        if trace is None:
            return
        trace.append({"tool": name, "args": dict(args or {}),
                      "row_nos": [r["row_no"] for r in sel]})

    def _on_page(r: dict, page: int) -> bool:
        """**مطابقةُ الصفحة في موضعٍ واحد — داخل هذا الملفّ** (يُقيَّد النطاق بصدق):

        يستهلكها `_page_scope` و`_filtered` معًا. (قِيس في مقعد البنية: كان `_filtered` يبني مقارنتَه
        بنفسه (`!= pg`) ⇒ تغييرُ مطابقة الصفحة يستلزم تعديلَ موضعين متباعدين.) **والنطاقُ المُعلَن:**
        ثلاثةُ مواضعَ أخرى تبني المطابقةَ نفسَها **خارج هذا الملفّ** — `src/statement_qa/footer_oracle.py`
        · `src/statement_qa/render.py` · `tools/eval_questions.py` (الواصفُ الذي يشتقّ أرقامَ صفوف
        الصفحة لعائلة `argmax_row`) ⇒ فتوحيدُ الحزمة كلِّها **لم يُدَّع**، ويُقاس إن طُلب.
        **والتعدادُ لا يُدَّعى حصرًا (قِيس في مراجعة إغلاق ٦٤ — «ثلاثة» كانت أدنى من الواقع):** المطابقةُ
        تُبنى كذلك في `tools/eval_questions.py:118,292,549,556` · `tools/qa_gate.py:380` ·
        `tools/to_xlsx.py:116,840` · `tools/audit_types.py:130` · `src/statement_qa/footer_oracle.py:402` ·
        `src/statement_qa/render.py:109` — و**لا ضابطَ اليومَ يمنع تباعدَها**، فتُعلَن ولا تُوحَّد بالادّعاء.

        **وعقدُ المعامَل: `page` عددٌ صحيح** (`int`) — فالتحويلُ يقع مرّةً عند مدخل كلّ مستهلك لا لكلّ صفّ.
        **ونطاقا الصفوف يبقيان مختلفين بإعلان**: `_page_scope` كلُّ صفوف الصفحة · و`_filtered` الحركاتُ وحدها.
        """
        return r.get("page") == page

    def _page_scope(page: int) -> list[dict]:
        """**موضعٌ واحد لنطاق الصفحة**: كلُّ صفوف الصفحة (بما فيها الافتتاحيّ) بأرقام الكشف.

        (كان مبنيًّا حرفيًّا في `page_summary` و`page_rows` معًا ⇒ نطاقان قد يفترقان بصمت).
        """
        return [r for r in numbered if _on_page(r, int(page))]

    def _row_line(r: dict) -> str:
        """**تنسيقُ سطرِ صفٍّ واحد** — يستعملُه `page_rows` و`search_rows`.

        (كان مكرَّرًا في الأداةين بحدَّي وصفٍ **صامتين** (`[:60]` مقابل `[:70]`) ⇒ صار حدًّا واحدًا
        مسمًّى `_ROW_DESC_LEN`، ولم يبقَ معامَلٌ لا يمرّره أحدٌ — قِيس في مقعد البنية: كان `desc_len`
        معامَلًا بلا مستدعٍ. **وتغيّرُ مخرَج `page_rows` بذلك (٦٠ ⇒ ٧٠ خانة) مُعلَن** ولا مستهلكَ له.)
        """
        move = _m(r["movement"]) if r.get("movement") is not None else "—"
        bal = _m(r["balance"]) if r.get("balance") is not None else "—"
        return (f"{_ref(r)}: [{r.get('type') or 'غير مصنّف'}] "
                f"{_SIDE_AR.get(r.get('side') or '', 'غير محسوم')} {move}"
                f" → الرصيد {bal} — {_desc(r)[:_ROW_DESC_LEN]}")

    def _period_text() -> str:
        """نصُّ مدّة الكشف **بسندها** — موضعٌ واحدٌ تستعمله كلُّ أداةٍ زمنيّة."""
        if period is None:
            return "لا تاريخَ ميلاديًّا مقروءًا في هذا الكشف (حدُّ الأداة: التاريخُ من الصفوف)"
        return (f"المدّة من {period[0]} إلى {period[1]} "
                f"(سندها: {_ref(period[2])} — {_ref(period[3])})")

    def _outside_period(d_from: str | None, d_to: str | None) -> bool:
        """هل المدى المطلوب خارج فترة الكشف كلِّه؟ — يقينٌ لا تخمين (أوّله وآخرُه مؤرّخان)."""
        if period is None:
            return False
        a = d_from or period[0]
        b = d_to or period[1]
        return b < period[0] or a > period[1]

    def _empty_result(d_from: str | None, d_to: str | None, undated: int) -> str:
        """جوابُ فراغٍ صادق: **خارج المدّة حدُّ أداةٍ يسمّي المدّة**، وداخلها «لا مطابقة» للفلتر.

        **ولا يُقلب أحدهما على الآخر:** مدىً خارج الكشف ليس «لا حركات» (دعوى عن الكشف)، ومطابقةٌ
        غابت داخل المدّة ليست «خارج مدّة» — لكلٍّ لفظُه وسندُه.
        """
        if (d_from or d_to) and _outside_period(d_from, d_to):
            return (f"خارج مدّة الكشف — {_period_text()}؛ فلا يومَ في المدى المطلوب. "
                    f"لم أدّعِ غيابَ حركاتٍ عن يومٍ داخل المدّة.")
        tail = (f" · و{undated} صفًّا بلا تاريخٍ مقروء لم يُفحَص بالتاريخ"
                if undated else "")
        return "لا توجد حركات مطابقة لهذا الفلتر." + tail

    def _filtered(side: str = "الكل", keyword: str = "", tx_type: str = "",
                  amount=None, page: int | None = None,
                  base: list[dict] | None = None,
                  date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        kw = (keyword or "").strip()
        tt = (tx_type or "").strip()
        amt = _parse_amount_arg(amount)
        pg = None if page is None else int(page)
        d_from = _parse_date_arg(date_from, "date_from")
        d_to = _parse_date_arg(date_to, "date_to")
        if d_from and d_to and d_from > d_to:
            raise ValueError(f"المدى مقلوب: date_from={d_from} بعد date_to={d_to} — حدُّ الأداة")
        out = []
        # **الوحدةُ تُختار بالسؤال (R90):** سؤالُ العدّ الافتراضيّ عن **الحركات**؛ وسؤالُ ترميز
        # التاريخ عن **الصفوف المطبوعة** (ومنها صفوفٌ ليست حركة) — فيُقاس على القاعدة المطلوبة.
        src = movements if base is None else base
        for r in src:
            if pg is not None and not _on_page(r, pg):
                continue
            if not _side_match(r.get("side", ""), side):
                continue
            if kw and kw not in _desc(r):
                continue
            if tt and tt not in (r.get("type") or ""):
                continue
            mv = r.get("movement")
            if amt is not None and (mv is None or mv != amt):
                continue
            if d_from or d_to:
                iso = _iso_date(r)
                if not iso:                       # صفٌّ بلا تاريخٍ لا يُنسب إلى مدى
                    continue
                if (d_from and iso < d_from) or (d_to and iso > d_to):
                    continue
            out.append(r)
        return out

    def _filter_note(side, keyword, tx_type, amount) -> str:
        bits = [f"الاتجاه={side or 'الكل'}"]
        if (tx_type or "").strip():
            bits.append(f"النوع يحتوي '{tx_type.strip()}'")
        if (keyword or "").strip():
            bits.append(f"الوصف يحتوي '{keyword.strip()}'")
        if amount not in (None, ""):
            bits.append(f"المبلغ={amount}")
        return " | ".join(bits)

    @_tool
    def sum_movements(side: str = "الكل", keyword: str = "", tx_type: str = "",
                      amount: float | None = None, *,
                      page: int | None = None,
                      date_from: str = "", date_to: str = "") -> str:
        """اجمع مبالغ الحركات. side: الاتجاه فقط — "مدين" أو "دائن" أو "الكل".
        tx_type: نوع العملية — "سحب صراف آلي" / "تحويل صادر" / "تحويل وارد" /
        "إيداع نقدي (صراف آلي)" / "مشتريات (نقاط بيع)" / "فواتير ومدفوعات سداد".
        keyword: جزء من الوصف. amount: مبلغ محدد بالريال (مثال: 1000).
        page: صفحةٌ واحدة — جمعُ حركاتِها وحدَها (مثال: sum_movements(page=486)).
        date_from / date_to: مدىً ميلاديٌّ (YYYY-MM-DD) — مثال: sum_movements(tx_type="سحب صراف آلي", date_from="2026-03-01", date_to="2026-03-31").
        تنبيه: «مدين» تعني أي حركة صادرة وليست «سحب صراف آلي» — للأنواع استخدم tx_type.
        مثال: sum_movements(tx_type="تحويل صادر") أو sum_movements(tx_type="سحب صراف آلي", amount=1000).

        **و`page` معامَلٌ لفظيٌّ وحدَه** (`page=`) — فالنداءُ الموضعيُّ القديم لا يتغيّر معناه (كما في
        `search_rows`). **وسببُ وجوده (R108-1):** القاعدةُ ٢ تمنع النموذجَ من الجمع بيده، ولم تكن
        أداةٌ تُخرج **مجموعَ صفحةٍ واحدة** ⇒ فكلُّ جوابٍ صحيحٍ في هذا الصنف كان يُجمع في الرأس (قِيس:
        ١٦ جوابًا في خمس قياسات حملت مجموعًا لا وجودَ له في مخرَج أيّ أداة)، وفي r107 التزم النموذجُ
        القاعدةَ فخسر `num-08`. **و`page_summary` لا تُغني:** تُخرج إجماليَّ المدين وإجماليَّ الدائن
        **منفصلين**، والمطلوبُ مجموعهما.

        **والمدى الزمنيّ (R130-1):** يُرشَّح بالتاريخ الميلاديّ المخزَّن؛ ومدىً خارج الكشف يُجاب
        «خارج مدّة الكشف» مع المدّة وسندها — لا «لا توجد حركات».
        """
        if page is not None and (msg := _unread_reply(page)):
            _record("sum_movements", [], {"side": side, "keyword": keyword, "tx_type": tx_type,
                                          "amount": amount, "page": page,
                                          "date_from": date_from, "date_to": date_to})
            return msg
        sel = _filtered(side, keyword, tx_type, amount, page,
                        date_from=date_from, date_to=date_to)
        _record("sum_movements", sel, {"side": side, "keyword": keyword, "tx_type": tx_type,
                                       "amount": amount, "page": page,
                                       "date_from": date_from, "date_to": date_to})
        if not sel:
            # **ولفظُ الفراغ يتبع السؤال:** سؤالٌ بلا تاريخٍ لا يُنطَق فيه بمدّة (R130-1 يمنع دعوى
            # الغياب عن بُعدٍ لم يُسأل)؛ وسؤالٌ بمدىً يُجاب بحدِّه: خارج المدّة أو لا مطابقة.
            if date_from or date_to:
                return _empty_result(_parse_date_arg(date_from, "date_from"),
                                     _parse_date_arg(date_to, "date_to"), len(undated_rows))
            return "لا توجد حركات مطابقة لهذا الفلتر في الكشف."
        vals = [_dec(r.get("movement")) for r in sel]
        total = sum((v for v in vals if v is not None), Decimal("0"))
        examples = "؛ ".join(
            f"[{r.get('type') or 'غير مصنّف'}] {_m(r['movement'])} {_ref(r)}"
            for r in sel[:3])
        return (f"المجموع = {_m(total)} ريال | عدد الحركات = {len(sel)}"
                + (f" · واستُبعد {sum(1 for v in vals if v is None)} بلا مبلغ"
                   if any(v is None for v in vals) else "")
                # **ولا يُسكَت عن صفٍّ بلا تاريخ (إصلاحُ مقعد المعايير P2):** المدى لا ينسبه،
                # وعدُّه في الجواب يمنع «مجموعًا ناقصًا يبدو كاملًا».
                + (f" · و{len(undated_rows)} صفًّا بلا تاريخٍ لم يدخل المدى"
                   if (date_from or date_to) and undated_rows else "")
                + (_unread_note() if page is None else "")
                + f" | أمثلة: {examples}")

    @_tool
    def count_movements(side: str = "الكل", keyword: str = "", tx_type: str = "",
                        amount: float | None = None, date_encoding: str = "",
                        printed_date_encoding: str = "",
                        date_from: str = "", date_to: str = "") -> str:
        """عدّ الحركات (بلا جمع مبالغ). نفس فلاتر sum_movements:
        side (اتجاه) | tx_type (النوع) | keyword (وصف) | amount (مبلغ بالريال).
        date_from / date_to: مدىً ميلاديٌّ (YYYY-MM-DD).

        **معيارا التاريخ (لا تخلطهما):**
        ① `date_encoding` يعدّ بحسب **حقل التاريخ المخزَّن** (النظاميّ): `"arabic_ind"`
        (المجموعتان معًا: العربيّة-الهندية ٠١٢…٩ والممتدّة ۰۱۲…۹) · `"latin"` · `"none"`.
        ② `printed_date_encoding` يعدّ بحسب **التاريخ المطبوع في صدر الوصف**:
        `"arabic_ind"` · `"extended"` · `"latin"` · `"none"`.
        **والكشفُ يحمل تاريخين:** هجريًّا مطبوعًا (عربيٌّ-هنديّ غالبًا) وميلاديًّا مخزَّنًا (ممتدٌّ) —
        فاسأل عن الذي يعنيه السؤال، وأعلن أيَّهما عدَدت.

        مثال: count_movements(tx_type="سحب صراف آلي", amount=1000) = عدد السحوبات بهذا المبلغ.
        مثال: count_movements(date_encoding="arabic_ind") = عددُ الصفوف التي تاريخُها المخزَّن بالأرقام العربيّة-الهندية.
        مثال: count_movements(printed_date_encoding="arabic_ind") = عددُ الصفوف التي تاريخُها المطبوع كذلك.
        مثال: count_movements(tx_type="سحب صراف آلي", date_from="2026-03-01", date_to="2026-03-07") = سحوباتُ أسبوع."""
        by_date = bool(date_encoding or printed_date_encoding)
        d_from = _parse_date_arg(date_from, "date_from")
        d_to = _parse_date_arg(date_to, "date_to")
        sel = _filtered(side, keyword, tx_type, amount,
                        base=(numbered if by_date else None),
                        date_from=date_from, date_to=date_to)
        if date_encoding:
            sel = [r for r in sel if _stored_date_encoding(r) == date_encoding]
        if printed_date_encoding:
            sel = [r for r in sel if _printed_date_encoding(r) == printed_date_encoding]
        _record("count_movements", sel, {"side": side, "keyword": keyword, "tx_type": tx_type,
                                         "amount": amount, "date_encoding": date_encoding,
                                         "printed_date_encoding": printed_date_encoding,
                                         "date_from": date_from, "date_to": date_to})
        note = _filter_note(side, keyword, tx_type, amount)
        if date_encoding:
            note = f"{note} | ترميزُ التاريخ المخزَّن = {date_encoding}"
        if printed_date_encoding:
            note = f"{note} | ترميزُ التاريخ المطبوع = {printed_date_encoding}"
        if d_from or d_to:
            note = f"{note} | المدى {d_from or '…'} إلى {d_to or '…'}"
        if not sel and (d_from or d_to):
            # سؤالُ عدٍّ بلا تاريخٍ يُجاب «العدد = 0» صريحًا؛ وبمدىً يُجاب بحدِّ المدّة.
            return _empty_result(d_from, d_to, len(undated_rows))
        return (f"العدد = {len(sel)} {'صفًّا' if by_date else 'حركة'} "
                f"(الفلتر: {note})" + _unread_note())

    @_tool
    def balance_extremes() -> str:
        """أعلى رصيد وأدنى رصيد ظهر في الكشف (مع موقعهما) — **بالمقارنة الرقميّة لا النصّيّة**.

        **والعطبُ المقيس (R93-7):** كانت `max(..., key=r["balance"])` والمبالغُ نصوصٌ ⇒ تُقارَن
        نصًّا: بمبالغ `9.00 · 10.00 · 120.00` تقول «أعلى = 9.00» و«أدنى = 10.00» — **جوابٌ خاطئ
        يُسلَّم**، وضابطُها القديم كان يقيس غيابَ `TypeError` فقط فيمرّ عليه.
        """
        pairs: list[tuple[dict, Decimal]] = []
        unparsed = 0
        for r in numbered:
            bal = r.get("balance")
            if bal is None:
                continue
            val = _dec(bal)
            if val is None:
                unparsed += 1              # **يُعدّ ولا يُبتلع:** يُقال بعدده في الجواب
                continue
            pairs.append((r, val))
        if not pairs:
            _record("balance_extremes", [], {})
            return "لا توجد أرصدة في الكشف."
        hi = max(pairs, key=lambda p: p[1])[0]
        lo = min(pairs, key=lambda p: p[1])[0]
        _record("balance_extremes", [hi, lo], {})
        tail = (f" · و{unparsed} رصيدًا غيرُ مقروء لم يُدخَل في المقارنة (لم يُخمَّن رقمُه)"
                if unparsed else "")
        return (f"أعلى رصيد = {_m(hi['balance'])} {_ref(hi)}"
                f" | أدنى رصيد = {_m(lo['balance'])} {_ref(lo)}{tail}" + _unread_note())

    @_tool
    def closing_balance() -> str:
        """آخر رصيد في الكشف (آخر صف يحمل رصيداً) — الرصيد الختامي."""
        with_bal = [r for r in numbered if r.get("balance") is not None]
        if not with_bal:
            _record("closing_balance", [], {})
            return "لا توجد أرصدة في الكشف."
        last = with_bal[-1]
        _record("closing_balance", [last], {})
        return f"آخر رصيد = {_m(last['balance'])} {_ref(last)}" + _unread_note()

    @_tool
    def page_summary(page: int) -> str:
        """ملخص صفحة واحدة: أول/آخر رصيد + إجمالي المدين وإجمالي الدائن فيها.
        مثال: page_summary(page=10)."""
        if (msg := _unread_reply(page)):
            _record("page_summary", [], {"page": page})
            return msg
        rows_on_page = _page_scope(page)
        if not rows_on_page:
            _record("page_summary", [], {"page": page})     # **النداءُ يُسجَّل ولو لم يجد شيئًا**
            return f"لا توجد بيانات للصفحة {page} في هذا الكشف."
        _record("page_summary", rows_on_page, {"page": page})
        with_bal = [r for r in rows_on_page if r.get("balance") is not None]
        debits = sum((_dec(r.get("movement")) for r in rows_on_page
                      if r.get("kind") == "txn" and r.get("side") == "debit"
                      and _dec(r.get("movement")) is not None), Decimal("0"))
        credits = sum((_dec(r.get("movement")) for r in rows_on_page
                       if r.get("kind") == "txn" and r.get("side") == "credit"
                       and _dec(r.get("movement")) is not None), Decimal("0"))
        # Rows whose direction the chain could not decide are NOT in either
        # total. Staying silent about them made a page total look complete
        # while a real movement was missing from it (audit P3-2).
        undecided = [r for r in rows_on_page
                     if r.get("kind") == "txn"
                     and r.get("side") not in ("debit", "credit")
                     and r.get("movement") is not None]
        note = ""
        if undecided:
            tot = sum((r["movement"] for r in undecided), Decimal("0"))
            note = (f" | تحفّظ: {len(undecided)} صف غير محسوم الاتجاه "
                    f"بإجمالي {_m(tot)} — غير مشمول في المجاميع")
        if not with_bal:
            return (f"صفحة {page}: لا توجد أرصدة مقروءة"
                    f" | إجمالي مدين = {_m(debits)}"
                    f" | إجمالي دائن = {_m(credits)}"
                    f" | عدد الصفوف = {len(rows_on_page)}" + note)
        first, last = with_bal[0], with_bal[-1]
        return (f"صفحة {page}: أول رصيد = {_m(first['balance'])} {_ref(first)}"
                f" | آخر رصيد = {_m(last['balance'])} {_ref(last)}"
                f" | إجمالي مدين = {_m(debits)}"
                f" | إجمالي دائن = {_m(credits)}"
                f" | عدد الصفوف = {len(rows_on_page)}" + note)

    @_tool
    def page_footer(page: int) -> str:
        """أرقامُ **التذييل المطبوع في الكشف نفسه** لصفحةٍ واحدة — إجمالي مدين تراكميّ · إجمالي دائن
        تراكميّ · رصيدُ الصفحة — **مع حكمِ مطابقتها**، وكلُّها كما ظهرت في الورقة لا محسوبةً من هنا.

        **استعملها لكلّ سؤالٍ عن رقمٍ مطبوع في صفحة** («إجمالي الصفحة ٥» · «المدين في الصفحة ١٢» ·
        «مجموع الصفحة ٧ كما هو مكتوب») — **ولا تجمع صفوفَ الصفحة لتجيب عنه**: التذييلُ **تراكميٌّ من
        أوّل الكشف**، فمجموعُ صفوفِ صفحةٍ واحدةٍ لا يساويه إلا في الصفحة الأولى.
        وإن كان الحكمُ **غير مطابق** فاذكره في جوابك ولا تُخفِه، وإن كان **بلا تذييل** فقل ذلك ولا تخمّن.
        مثال: page_footer(page=5)."""
        pg = int(page)
        f = (footers or {}).get(pg)
        # **أثرُ الاستدعاء:** شاهدُ الفوتر **ليس صفًّا** (هو سطرُ التذييل المطبوع) ⇒ يُسجَّل الاستدعاءُ
        # بلا أرقام صفوف، ويُقرأ في `qa.py` دليلًا على أنّ أداةً استُدعيت فعلًا — فلا يُوصَم جوابُ
        # الفوتر بأنّه «بلا أداة» (R77 · مراجعة ٧٧).
        if trace is not None:
            trace.append({"tool": "page_footer", "args": {"page": pg}, "row_nos": []})
        if not f:
            return (f"الصفحة {pg}: لا تذييلَ مطبوعًا مقروءًا لها في هذا الكشف "
                    f"(تُسمّى ولا تُخمَّن).")
        def _v(key: str) -> str:
            val = f.get(key)
            return "لم يُقرأ" if val is None else str(val)
        basis = f" ({f['basis']})" if f.get("basis") else ""
        return (f"صفحة {pg} — التذييلُ المطبوع كما في الورقة: إجمالي مدين = {_v('debits')}"
                f" | إجمالي دائن = {_v('credits')} | رصيدُ الصفحة = {_v('balance')}"
                f" | حكمُ المطابقة = {_FOOTER_AR.get(str(f.get('verdict') or ''), f.get('verdict'))}"
                f"{basis}")

    @_tool
    def page_rows(page: int, limit: int = 40) -> str:
        """اعرض **سطور صفحةٍ بعينها** بأرقامها: رقمُ الصفّ ومبلغُه واتجاهُه ورصيدُه ووصفُه.

        استعملها حين يكون السؤال عن **صفٍّ داخل صفحة**: «أكبر حركةٍ في الصفحة ٤٠» · «صفوفُ الصفحة ١٢» ·
        «آخرُ حركةٍ في الصفحة ٧» — فهي الموضعُ الذي يُظهر الصفوفَ ورقمَ كلٍّ منها (ومنه يُقرأ الأكبرُ/الأخير).
        **والتنبيهُ الملازم:** أرقامُ الصفوف هنا **على مستوى الكشف** (تكمل من صفحةٍ إلى التي بعدها) وهي نفسُها
        التي تُقتبَس بها المصادرُ (صفحة N، صف M) — فلا تُعَدّ من ١ داخل الصفحة.
        **والفرقُ عن `search_rows(page=…)` مُعلَن:** هذه تُظهر **كلَّ** صفوف الصفحة (ومنه صفُّ الرصيد
        الافتتاحيّ)، وتلك تُظهر **الحركات** وحدَها (تُسقط غيرَ الحركة).
        مثال: page_rows(page=40)."""
        if (msg := _unread_reply(page)):
            _record("page_rows", [], {"page": page, "limit": limit})
            return msg
        sel = _page_scope(page)
        if not sel:
            _record("page_rows", [], {"page": page, "limit": limit})
            return f"لا توجد صفوفٌ للصفحة {int(page)} في هذا الكشف."
        shown = sel[:max(1, int(limit))]
        _record("page_rows", shown, {"page": page, "limit": limit})   # **ما ظهر فعلًا** لا كلَّ الصفحة
        more = "" if len(sel) <= len(shown) else f" (و{len(sel) - len(shown)} أخرى)"
        return (f"صفحة {int(page)}: {len(sel)} صفًّا{more} — والأرقامُ على مستوى الكشف:\n"
                + "\n".join(_row_line(r) for r in shown))

    @_tool
    def search_rows(keyword: str = "", tx_type: str = "", amount: float | None = None,
                    limit: int = 15, *, page: int | None = None,
                    date_from: str = "", date_to: str = "") -> str:
        """ابحث وأعد سطور الحركات المطابقة (الموقع/النوع/الاتجاه/المبلغ/الرصيد/الوصف).
        فلاتر: keyword (وصف) | tx_type (النوع) | amount (مبلغ محدد، مثال 1000) | page (صفحة واحدة).
        date_from / date_to: مدىً ميلاديٌّ (YYYY-MM-DD) — مثال: search_rows(date_from="2026-03-01", date_to="2026-03-31").
        مثال: search_rows(amount=1000) = كل الحركات بمبلغ 1000 مع أنواعها الحقيقية.
        مثال: search_rows(page=40) = حركاتُ الصفحة ٤٠ وحدها (مرتّبةً بأرقام صفوفها).
        **و`page` معامَلٌ لفظيٌّ وحدَه** (`page=`) — فالنداءُ الموضعيُّ القديم لا يتغيّر معناه.
        **وتُسقِط غيرَ الحركة** (صفَّ الرصيد الافتتاحيّ): لِسرد الصفحة كاملةً استعمل `page_rows`.
        **والأثرُ:** يُسجَّل **كلُّ ما اختارته** الأداة لا المقصوصَ بالحدّ — سلوكٌ قائمٌ قبل هذه الجولة،
        ومُعلَن: أمّا `page_rows` فتسجّل ما **ظهر** فيها. (و`search_rows` بقي على حاله عمدًا بلا ضابطٍ
        يفرض غيرَه — تغييرُه يمسّ مقاييسَ الأثر على تشغيلٍ حقيقيّ غيرِ مقيس.) **وموضعُ الأثر هذا يمسّ
        مستهلكًا قائمًا:** `tools/eval_questions.py` يشتقّ دقّةَ الاستشهاد من الصفوف المسجَّلة ⇒ فقد
        تُحصى صفوفٌ لم يرها النموذجُ «مُستشهَدةً» — التعارضُ **مُوثَّقٌ لا مُغلَق**، وإغلاقُه يقتضي
        قياسَ أثرِ التوحيد على مقياسٍ حقيقيّ (غيرُ مقيس)."""
        if page is not None and (msg := _unread_reply(page)):
            _record("search_rows", [], {"keyword": keyword, "tx_type": tx_type, "amount": amount,
                                        "limit": limit, "page": page,
                                        "date_from": date_from, "date_to": date_to})
            return msg
        sel = _filtered("الكل", keyword, tx_type, amount, page,
                        date_from=date_from, date_to=date_to)
        _record("search_rows", sel, {"keyword": keyword, "tx_type": tx_type, "amount": amount,
                                     "limit": limit, "page": page,
                                     "date_from": date_from, "date_to": date_to})
        if not sel:
            if date_from or date_to:
                return _empty_result(_parse_date_arg(date_from, "date_from"),
                                     _parse_date_arg(date_to, "date_to"), len(undated_rows))
            return "لا توجد حركات مطابقة."
        shown = sel[:max(1, int(limit))]
        lines = [_row_line(r) for r in shown]
        more = "" if len(sel) <= len(shown) else f" (و{len(sel) - len(shown)} أخرى)"
        return f"{len(sel)} حركة مطابقة{more}:\n" + "\n".join(lines)

    @_tool
    def statement_period() -> str:
        """مدّةُ الكشف: أوّلُ تاريخٍ وآخرُ تاريخٍ مقروءٍ ميلاديًّا، وعددُ الأيام، والمدّةُ بالأسابيع.

        استعملها لكلّ سؤالٍ عن «فترة الكشف» أو «مدّة الكشف» أو قبل حساب معدّلٍ أسبوعيّ — فالمعدّلُ
        يحتاج المدّةَ من أداة، لا من حسابك. والسندُ (صفحة/صف) يُذكر مع الطرفين.
        """
        if period is None:
            _record("statement_period", [], {})
            return ("لا تاريخَ ميلاديًّا مقروءًا في هذا الكشف — **حدُّ الأداة**: لا أستطيع أن أُعلن "
                    "مدّته ولا معدّلًا أسبوعيًّا من غير تواريخ.")
        days = (_date.fromisoformat(period[1]) - _date.fromisoformat(period[0])).days + 1
        weeks = (Decimal(days) / Decimal(7)).quantize(Decimal("0.01"))
        _record("statement_period", [period[2], period[3]], {})
        tail = (f" | و{len(undated_rows)} صفًّا بلا تاريخٍ مقروء (لم تُدخَل في المدّة)"
                if undated_rows else "")
        return (f"المدّة: من {period[0]} إلى {period[1]} | عددُ الأيام = {days} "
                f"| الأسابيع = {weeks} | سندُ الطرفين: {_ref(period[2])} و{_ref(period[3])}"
                f"{tail}" + _unread_note())

    @_tool
    def balance_on(date: str) -> str:
        """رصيدُ الحساب في يومٍ بعينه: آخرُ رصيدٍ مقروءٍ في ذلك اليوم أو قبله، مع موقعه.

        `date`: تاريخٌ ميلاديٌّ بصيغة YYYY-MM-DD (أو 2026/03/15، أو 20260315).
        **وإن كان اليومُ خارج مدّة الكشف** يقول الجوابُ ذلك صراحةً **مع المدّة وسندها** — ولا يقول
        «لا توجد حركات» (تلك دعوى عن الكشف تحتاج أداةً سألت اليوم، وهذه هي).
        """
        d = _parse_date_arg(date, "date")
        if d is None:
            raise ValueError("balance_on تحتاج تاريخًا (YYYY-MM-DD) — حدُّ الأداة: لا يومَ بلا تاريخ")
        with_bal = [r for r in numbered if r.get("balance") is not None]
        if not with_bal:
            _record("balance_on", [], {"date": date})
            return "لا أرصدةَ مقروءةً في هذا الكشف (حدُّ الأداة: الرصيدُ من الصفوف)."
        if period is not None and (d < period[0] or d > period[1]):
            _record("balance_on", [period[2], period[3]], {"date": d})
            side = "قبل" if d < period[0] else "بعد"
            return (f"خارج مدّة الكشف — {period[0]} إلى {period[1]} "
                    f"(سندها: {_ref(period[2])} — {_ref(period[3])})؛ فاليوم {d} {side} المدّة. "
                    f"لم أدّعِ غيابَ حركاتٍ في الكشف، وإنّما أنّ هذا اليومَ خارج ما يغطّيه.")
        upto = [(iso, r) for r in with_bal if (iso := _iso_date(r)) and iso <= d]
        if not upto:
            _record("balance_on", [], {"date": d})
            return (f"لا رصيدَ مقروءًا في {d} ولا قبله داخل المدّة "
                    f"({period[0] if period else '؟'} إلى {period[1] if period else '؟'}) — "
                    f"حدُّ الأداة: أوّلُ رصيدٍ مقروءٍ بعد هذا اليوم.")
        iso, row = max(upto, key=lambda p: (p[0], p[1]["row_no"]))
        _record("balance_on", [row], {"date": d})
        when = "في اليوم نفسه" if iso == d else f"آخرُ رصيدٍ قبلَه بتاريخ {iso}"
        return f"الرصيد = {_m(row['balance'])} ريال ({when}) — {_ref(row)}"

    @_tool
    def group_by_date(side: str = "الكل", keyword: str = "", tx_type: str = "",
                      date_from: str = "", date_to: str = "", limit: int = 31) -> str:
        """تجميعُ الحركات بالتاريخ: لكلّ يومٍ عددُ الحركات ومجموعُ المدين ومجموعُ الدائن وصافيها.

        استعملها لأسئلة «أيّ يومٍ كان أكثر…» أو «حركةُ كلّ يوم» أو حين تحتاج تفصيلًا يوميًّا.
        `date_from`/`date_to` يحصران المدى، و`limit` (افتراضًا 31) يحدّ عددَ الأيام المعروضة من
        أوّل المدى — **وعددُ الأيام كلِّه ومجاميعُه تُذكر دائمًا**، فالقصُّ مُعلَنٌ لا صامت.
        """
        sel = _filtered(side, keyword, tx_type, None, None,
                        date_from=date_from, date_to=date_to)
        d_from = _parse_date_arg(date_from, "date_from")
        d_to = _parse_date_arg(date_to, "date_to")
        _record("group_by_date", sel, {"side": side, "keyword": keyword, "tx_type": tx_type,
                                       "date_from": date_from, "date_to": date_to,
                                       "limit": limit})
        if not sel:
            return _empty_result(d_from, d_to, len(undated_rows) if (d_from or d_to) else 0)
        days: dict[str, dict] = {}
        undated = [r for r in sel if not _iso_date(r)]
        for r in sel:
            iso = _iso_date(r)
            if not iso:                  # صفٌّ بلا تاريخٍ لا يُنسب إلى يوم — ولا يُفتح له مفتاحٌ فارغ
                continue
            e = days.setdefault(iso, {"count": 0, "debit": Decimal("0"), "credit": Decimal("0")})
            e["count"] += 1
            val = _dec(r.get("movement"))
            if val is not None and r.get("side") == "debit":
                e["debit"] += val
            elif val is not None and r.get("side") == "credit":
                e["credit"] += val
        ordered = sorted(days)
        shown = ordered[:max(1, int(limit))]
        tot = sum((e["debit"] for e in days.values()), Decimal("0"))
        tot_c = sum((e["credit"] for e in days.values()), Decimal("0"))
        lines = [f"{d}: {days[d]['count']} حركة · مدين {_m(days[d]['debit'])} · "
                 f"دائن {_m(days[d]['credit'])} · صافٍ {_m(days[d]['credit'] - days[d]['debit'])}"
                 for d in shown]
        more = ("" if len(ordered) <= len(shown)
                else f" (ويُعرض أوّلُ {len(shown)} من {len(ordered)} يومًا — ضيّق المدى أو ارفع limit)")
        return (f"أيامٌ لها حركات = {len(ordered)} · مدينُ المدّة {_m(tot)} · دائنُها {_m(tot_c)}{more}"
                + (f" · و{len(undated)} صفًّا بلا تاريخٍ لم يُنسب إلى يوم" if undated else "")
                + "\n" + "\n".join(lines))

    @_tool
    def movement_days(side: str = "الكل", keyword: str = "", tx_type: str = "",
                      date_from: str = "", date_to: str = "") -> str:
        """عددُ أيّام الحركة ومعدّلُها في الأسبوع — عدًّا ومبلغًا، من مدّة الكشف نفسِها.

        استعملها لسؤال «كم يومًا فيه سحوبات؟» و«ما معدّل السحب في الأسبوع؟». «اليوم» هو تاريخٌ
        ميلاديٌّ ظهرت فيه حركةٌ مطابقة (لا عددُ الحركات)، والمعدّلُ = المجموع ÷ أسابيع مدّة الكشف
        (أو أسابيع المدى المطلوب إن حُدِّد). **ولا تقسم أنت:** كلُّ الأرقام تُحسب هنا.
        """
        sel = _filtered(side, keyword, tx_type, None, None,
                        date_from=date_from, date_to=date_to)
        d_from = _parse_date_arg(date_from, "date_from")
        d_to = _parse_date_arg(date_to, "date_to")
        _record("movement_days", sel, {"side": side, "keyword": keyword, "tx_type": tx_type,
                                       "date_from": date_from, "date_to": date_to})
        if not sel:
            return _empty_result(d_from, d_to, len(undated_rows) if (d_from or d_to) else 0)
        if period is None:
            return ("لا تاريخَ ميلاديًّا مقروءًا — حدُّ الأداة: المعدّلُ الأسبوعيّ يحتاج مدّةً "
                    "مؤرّخة، فلا أُخرجه من غيرها.")
        first = max(d_from or period[0], period[0])
        last = min(d_to or period[1], period[1])
        days = max(1, (_date.fromisoformat(last) - _date.fromisoformat(first)).days + 1)
        weeks = (Decimal(days) / Decimal(7)).quantize(Decimal("0.01"))
        used_days = sorted({_iso_date(r) for r in sel if _iso_date(r)})
        total = sum((_dec(r.get("movement")) or Decimal("0") for r in sel), Decimal("0"))
        rate_n = (Decimal(len(sel)) / weeks).quantize(Decimal("0.01")) if weeks else None
        rate_a = (total / weeks).quantize(Decimal("0.01")) if weeks else None
        span = (f"{first} إلى {last}" if (d_from or d_to) else period[0] + " إلى " + period[1])
        return (f"أيّامُ الحركة = {len(used_days)} · عددُ الحركات = {len(sel)} · "
                f"مجموعُ المبالغ = {_m(total)} ريال | المدى = {span} ({days} يومًا = {weeks} أسبوع) | "
                f"المعدّلُ الأسبوعيّ = {_m(rate_a)} ريالًا و{rate_n} حركة/أسبوع"
                + (f" | أوّلُ يومٍ {used_days[0]} وآخرُها {used_days[-1]}" if used_days else ""))

    return [sum_movements, count_movements, balance_extremes,
            closing_balance, page_summary, page_footer, page_rows, search_rows,
            statement_period, balance_on, group_by_date, movement_days]