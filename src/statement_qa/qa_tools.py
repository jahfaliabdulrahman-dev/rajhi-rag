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

An optional `trace` list (server-side only) records which rows each non-empty
call selected: {"tool": name, "row_nos": [...]}. The evidence panel is built
from that trace — what BUILT the numbers — never from the row refs the model
happens to repeat in prose; and it never enters the text the model reads.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

_MONEY = "{:,.2f}"
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
    refs and quoted sources always agree."""
    return [{**r, "row_no": i + 1} for i, r in enumerate(rows)]


def _ref(r: dict) -> str:
    return f"(صفحة {r['page']}، صف {r['row_no']})"


def _desc(r: dict) -> str:
    return (r.get("desc") or "").replace("\n", " ").strip()


def used_rows_from_trace(trace: list[dict]) -> list[int]:
    """Union of the row numbers the tools actually selected — sorted, deduped.
    The evidence backbone: what BUILT the numbers, not what the prose cited."""
    return sorted({no for call in trace for no in call.get("row_nos", [])})


def make_qa_tools(rows: list[dict], trace: list[dict] | None = None):
    """Bind the verified rows to LangChain tools (import kept lazy).

    When `trace` is a list, every successful non-empty call appends
    {"tool": name, "row_nos": [...]} — the raw material for the evidence
    panel. Pure bookkeeping: it never changes any tool's return text.
    """
    from langchain_core.tools import tool

    numbered = _number_rows(rows)
    movements = [r for r in numbered if r.get("kind") == "txn"
                 and r.get("movement") is not None]

    def _record(name: str, sel: list[dict]) -> None:
        """Server-side evidence trace — zero tokens, no text markers."""
        if trace is not None and sel:
            trace.append({"tool": name,
                          "row_nos": [r["row_no"] for r in sel]})

    def _on_page(r: dict, page: int) -> bool:
        """**مطابقةُ الصفحة في موضعٍ واحد** — يستهلكها `_page_scope` و`_filtered` معًا.

        (قِيس في مقعد البنية: كان `_filtered` يبني مقارنتَه بنفسه (`!= pg`) ⇒ تغييرُ مطابقة الصفحة
        يستلزم تعديلَ موضعين متباعدين. **ونطاقا الصفوف يبقيان مختلفين بإعلان**: `_page_scope` كلُّ
        صفوف الصفحة · و`_filtered` الحركاتُ وحدها.)
        """
        return r.get("page") == int(page)

    def _page_scope(page: int) -> list[dict]:
        """**موضعٌ واحد لنطاق الصفحة**: كلُّ صفوف الصفحة (بما فيها الافتتاحيّ) بأرقام الكشف.

        (كان مبنيًّا حرفيًّا في `page_summary` و`page_rows` معًا ⇒ نطاقان قد يفترقان بصمت).
        """
        return [r for r in numbered if _on_page(r, page)]

    def _row_line(r: dict) -> str:
        """**تنسيقُ سطرِ صفٍّ واحد** — يستعملُه `page_rows` و`search_rows`.

        (كان مكرَّرًا في الأداةين بحدَّي وصفٍ **صامتين** (`[:60]` مقابل `[:70]`) ⇒ صار حدًّا واحدًا
        مسمًّى `_ROW_DESC_LEN`، ولم يبقَ معامَلٌ لا يمرّره أحدٌ — قِيس في مقعد البنية: كان `desc_len`
        معامَلًا بلا مستدعٍ. **وتغيّرُ مخرَج `page_rows` بذلك (٦٠ ⇒ ٧٠ خانة) مُعلَن** ولا مستهلكَ له.)
        """
        move = _MONEY.format(r["movement"]) if r.get("movement") is not None else "—"
        bal = _MONEY.format(r["balance"]) if r.get("balance") is not None else "—"
        return (f"{_ref(r)}: [{r.get('type') or 'غير مصنّف'}] "
                f"{_SIDE_AR.get(r.get('side') or '', 'غير محسوم')} {move}"
                f" → الرصيد {bal} — {_desc(r)[:_ROW_DESC_LEN]}")

    def _filtered(side: str = "الكل", keyword: str = "", tx_type: str = "",
                  amount=None, page: int | None = None) -> list[dict]:
        kw = (keyword or "").strip()
        tt = (tx_type or "").strip()
        amt = _parse_amount_arg(amount)
        pg = None if page is None else int(page)
        out = []
        for r in movements:
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

    @tool
    def sum_movements(side: str = "الكل", keyword: str = "", tx_type: str = "",
                      amount: float | None = None) -> str:
        """اجمع مبالغ الحركات. side: الاتجاه فقط — "مدين" أو "دائن" أو "الكل".
        tx_type: نوع العملية — "سحب صراف آلي" / "تحويل صادر" / "تحويل وارد" /
        "إيداع نقدي (صراف آلي)" / "مشتريات (نقاط بيع)" / "فواتير ومدفوعات سداد".
        keyword: جزء من الوصف. amount: مبلغ محدد بالريال (مثال: 1000).
        تنبيه: «مدين» تعني أي حركة صادرة وليست «سحب صراف آلي» — للأنواع استخدم tx_type.
        مثال: sum_movements(tx_type="تحويل صادر") أو sum_movements(tx_type="سحب صراف آلي", amount=1000)."""
        sel = _filtered(side, keyword, tx_type, amount)
        _record("sum_movements", sel)
        if not sel:
            return "لا توجد حركات مطابقة لهذا الفلتر في الكشف."
        total = sum((r["movement"] for r in sel), Decimal("0"))
        examples = "؛ ".join(
            f"[{r.get('type') or 'غير مصنّف'}] {_MONEY.format(r['movement'])} {_ref(r)}"
            for r in sel[:3])
        return (f"المجموع = {_MONEY.format(total)} ريال | عدد الحركات = {len(sel)}"
                f" | أمثلة: {examples}")

    @tool
    def count_movements(side: str = "الكل", keyword: str = "", tx_type: str = "",
                        amount: float | None = None) -> str:
        """عدّ الحركات (بلا جمع مبالغ). نفس فلاتر sum_movements:
        side (اتجاه) | tx_type (النوع) | keyword (وصف) | amount (مبلغ بالريال).
        مثال: count_movements(tx_type="سحب صراف آلي", amount=1000) = عدد السحوبات بهذا المبلغ."""
        sel = _filtered(side, keyword, tx_type, amount)
        _record("count_movements", sel)
        return (f"العدد = {len(sel)} حركة "
                f"(الفلتر: {_filter_note(side, keyword, tx_type, amount)})")

    @tool
    def balance_extremes() -> str:
        """أعلى رصيد وأدنى رصيد ظهر في الكشف (مع موقعهما)."""
        with_bal = [r for r in numbered if r.get("balance") is not None]
        if not with_bal:
            return "لا توجد أرصدة في الكشف."
        hi = max(with_bal, key=lambda r: r["balance"])
        lo = min(with_bal, key=lambda r: r["balance"])
        _record("balance_extremes", [hi, lo])
        return (f"أعلى رصيد = {_MONEY.format(hi['balance'])} {_ref(hi)}"
                f" | أدنى رصيد = {_MONEY.format(lo['balance'])} {_ref(lo)}")

    @tool
    def closing_balance() -> str:
        """آخر رصيد في الكشف (آخر صف يحمل رصيداً) — الرصيد الختامي."""
        with_bal = [r for r in numbered if r.get("balance") is not None]
        if not with_bal:
            return "لا توجد أرصدة في الكشف."
        last = with_bal[-1]
        _record("closing_balance", [last])
        return f"آخر رصيد = {_MONEY.format(last['balance'])} {_ref(last)}"

    @tool
    def page_summary(page: int) -> str:
        """ملخص صفحة واحدة: أول/آخر رصيد + إجمالي المدين وإجمالي الدائن فيها.
        مثال: page_summary(page=10)."""
        rows_on_page = _page_scope(page)
        if not rows_on_page:
            return f"لا توجد بيانات للصفحة {page} في هذا الكشف."
        _record("page_summary", rows_on_page)
        with_bal = [r for r in rows_on_page if r.get("balance") is not None]
        debits = sum((r["movement"] for r in rows_on_page
                      if r.get("kind") == "txn" and r.get("side") == "debit"
                      and r.get("movement") is not None), Decimal("0"))
        credits = sum((r["movement"] for r in rows_on_page
                       if r.get("kind") == "txn" and r.get("side") == "credit"
                       and r.get("movement") is not None), Decimal("0"))
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
                    f"بإجمالي {_MONEY.format(tot)} — غير مشمول في المجاميع")
        if not with_bal:
            return (f"صفحة {page}: لا توجد أرصدة مقروءة"
                    f" | إجمالي مدين = {_MONEY.format(debits)}"
                    f" | إجمالي دائن = {_MONEY.format(credits)}"
                    f" | عدد الصفوف = {len(rows_on_page)}" + note)
        first, last = with_bal[0], with_bal[-1]
        return (f"صفحة {page}: أول رصيد = {_MONEY.format(first['balance'])} {_ref(first)}"
                f" | آخر رصيد = {_MONEY.format(last['balance'])} {_ref(last)}"
                f" | إجمالي مدين = {_MONEY.format(debits)}"
                f" | إجمالي دائن = {_MONEY.format(credits)}"
                f" | عدد الصفوف = {len(rows_on_page)}" + note)

    @tool
    def page_rows(page: int, limit: int = 40) -> str:
        """اعرض **سطور صفحةٍ بعينها** بأرقامها: رقمُ الصفّ ومبلغُه واتجاهُه ورصيدُه ووصفُه.

        استعملها حين يكون السؤال عن **صفٍّ داخل صفحة**: «أكبر حركةٍ في الصفحة ٤٠» · «صفوفُ الصفحة ١٢» ·
        «آخرُ حركةٍ في الصفحة ٧» — فهي الموضعُ الذي يُظهر الصفوفَ ورقمَ كلٍّ منها (ومنه يُقرأ الأكبرُ/الأخير).
        **والتنبيهُ الملازم:** أرقامُ الصفوف هنا **على مستوى الكشف** (تكمل من صفحةٍ إلى التي بعدها) وهي نفسُها
        التي تُقتبَس بها المصادرُ (صفحة N، صف M) — فلا تُعَدّ من ١ داخل الصفحة.
        **والفرقُ عن `search_rows(page=…)` مُعلَن:** هذه تُظهر **كلَّ** صفوف الصفحة (ومنه صفُّ الرصيد
        الافتتاحيّ)، وتلك تُظهر **الحركات** وحدَها (تُسقط غيرَ الحركة).
        مثال: page_rows(page=40)."""
        sel = _page_scope(page)
        if not sel:
            return f"لا توجد صفوفٌ للصفحة {int(page)} في هذا الكشف."
        shown = sel[:max(1, int(limit))]
        _record("page_rows", shown)     # **ما ظهر فعلًا** لا كلَّ الصفحة (كان يُسجّل الصفوفَ التي لم تُعرَض)
        more = "" if len(sel) <= len(shown) else f" (و{len(sel) - len(shown)} أخرى)"
        return (f"صفحة {int(page)}: {len(sel)} صفًّا{more} — والأرقامُ على مستوى الكشف:\n"
                + "\n".join(_row_line(r) for r in shown))

    @tool
    def search_rows(keyword: str = "", tx_type: str = "", amount: float | None = None,
                    limit: int = 15, *, page: int | None = None) -> str:
        """ابحث وأعد سطور الحركات المطابقة (الموقع/النوع/الاتجاه/المبلغ/الرصيد/الوصف).
        فلاتر: keyword (وصف) | tx_type (النوع) | amount (مبلغ محدد، مثال 1000) | page (صفحة واحدة).
        مثال: search_rows(amount=1000) = كل الحركات بمبلغ 1000 مع أنواعها الحقيقية.
        مثال: search_rows(page=40) = حركاتُ الصفحة ٤٠ وحدها (مرتّبةً بأرقام صفوفها).
        **و`page` معامَلٌ لفظيٌّ وحدَه** (`page=`) — فالنداءُ الموضعيُّ القديم لا يتغيّر معناه.
        **وتُسقِط غيرَ الحركة** (صفَّ الرصيد الافتتاحيّ): لِسرد الصفحة كاملةً استعمل `page_rows`.
        **والأثرُ:** يُسجَّل **كلُّ ما اختارته** الأداة لا المقصوصَ بالحدّ — سلوكٌ قائمٌ قبل هذه الجولة،
        ومُعلَن: أمّا `page_rows` فتسجّل ما **ظهر** فيها. (و`search_rows` بقي على حاله عمدًا بلا ضابطٍ
        يفرض غيرَه — تغييرُه يمسّ مقاييسَ الأثر على تشغيلٍ حقيقيّ غيرِ مقيس.)"""
        sel = _filtered("الكل", keyword, tx_type, amount, page)
        _record("search_rows", sel)
        if not sel:
            return "لا توجد حركات مطابقة."
        shown = sel[:max(1, int(limit))]
        lines = [_row_line(r) for r in shown]
        more = "" if len(sel) <= len(shown) else f" (و{len(sel) - len(shown)} أخرى)"
        return f"{len(sel)} حركة مطابقة{more}:\n" + "\n".join(lines)

    return [sum_movements, count_movements, balance_extremes,
            closing_balance, page_summary, page_rows, search_rows]