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
- amount: exact riyal amount after 2dp rounding (accepts 1000 / "9001.00").
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

_MONEY = "{:,.2f}"

_SIDE_AR = {"debit": "مدين", "credit": "دائن"}


def _side_match(row_side: str, want: str) -> bool:
    w = (want or "").strip()
    if w in ("", "الكل", "كل", "both", "all"):
        return True
    if w in ("مدين", "debit", "المدين"):
        return row_side == "debit"
    if w in ("دائن", "credit", "الدائن"):
        return row_side == "credit"
    return True  # unknown filter: don't over-filter


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


def make_qa_tools(rows: list[dict]):
    """Bind the verified rows to LangChain tools (import kept lazy)."""
    from langchain_core.tools import tool

    numbered = _number_rows(rows)
    movements = [r for r in numbered if r.get("kind") == "txn"
                 and r.get("movement") is not None]

    def _filtered(side: str = "الكل", keyword: str = "", tx_type: str = "",
                  amount=None) -> list[dict]:
        kw = (keyword or "").strip()
        tt = (tx_type or "").strip()
        amt = _parse_amount_arg(amount)
        out = []
        for r in movements:
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
        return (f"أعلى رصيد = {_MONEY.format(hi['balance'])} {_ref(hi)}"
                f" | أدنى رصيد = {_MONEY.format(lo['balance'])} {_ref(lo)}")

    @tool
    def closing_balance() -> str:
        """آخر رصيد في الكشف (آخر صف يحمل رصيداً) — الرصيد الختامي."""
        with_bal = [r for r in numbered if r.get("balance") is not None]
        if not with_bal:
            return "لا توجد أرصدة في الكشف."
        last = with_bal[-1]
        return f"آخر رصيد = {_MONEY.format(last['balance'])} {_ref(last)}"

    @tool
    def page_summary(page: int) -> str:
        """ملخص صفحة واحدة: أول/آخر رصيد + إجمالي المدين وإجمالي الدائن فيها.
        مثال: page_summary(page=10)."""
        page_rows = [r for r in numbered if r["page"] == int(page)]
        if not page_rows:
            return f"لا توجد بيانات للصفحة {page} في هذا الكشف."
        with_bal = [r for r in page_rows if r.get("balance") is not None]
        debits = sum((r["movement"] for r in page_rows
                      if r.get("kind") == "txn" and r.get("side") == "debit"
                      and r.get("movement") is not None), Decimal("0"))
        credits = sum((r["movement"] for r in page_rows
                       if r.get("kind") == "txn" and r.get("side") == "credit"
                       and r.get("movement") is not None), Decimal("0"))
        if not with_bal:
            return (f"صفحة {page}: لا توجد أرصدة مقروءة"
                    f" | إجمالي مدين = {_MONEY.format(debits)}"
                    f" | إجمالي دائن = {_MONEY.format(credits)}"
                    f" | عدد الصفوف = {len(page_rows)}")
        first, last = with_bal[0], with_bal[-1]
        return (f"صفحة {page}: أول رصيد = {_MONEY.format(first['balance'])} {_ref(first)}"
                f" | آخر رصيد = {_MONEY.format(last['balance'])} {_ref(last)}"
                f" | إجمالي مدين = {_MONEY.format(debits)}"
                f" | إجمالي دائن = {_MONEY.format(credits)}"
                f" | عدد الصفوف = {len(page_rows)}")

    @tool
    def search_rows(keyword: str = "", tx_type: str = "", amount: float | None = None,
                    limit: int = 15) -> str:
        """ابحث وأعد سطور الحركات المطابقة (الموقع/النوع/الاتجاه/المبلغ/الرصيد/الوصف).
        فلاتر: keyword (وصف) | tx_type (النوع) | amount (مبلغ محدد، مثال 1000).
        مثال: search_rows(amount=1000) = كل الحركات بمبلغ 1000 مع أنواعها الحقيقية."""
        sel = _filtered("الكل", keyword, tx_type, amount)
        if not sel:
            return "لا توجد حركات مطابقة."
        shown = sel[:max(1, int(limit))]
        lines = [
            f"{_ref(r)}: [{r.get('type') or 'غير مصنّف'}] "
            f"{_SIDE_AR.get(r.get('side') or '', 'غير محسوم')} "
            f"{_MONEY.format(r['movement'])}"
            f" → الرصيد {_MONEY.format(r['balance']) if r.get('balance') is not None else '—'}"
            f" — {_desc(r)[:70]}"
            for r in shown
        ]
        more = "" if len(sel) <= len(shown) else f" (و{len(sel) - len(shown)} أخرى)"
        return f"{len(sel)} حركة مطابقة{more}:\n" + "\n".join(lines)

    return [sum_movements, count_movements, balance_extremes,
            closing_balance, page_summary, search_rows]
