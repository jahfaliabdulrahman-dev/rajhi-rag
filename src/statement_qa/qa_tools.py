"""Deterministic QA tools over the verified statement rows.

The model NEVER computes: every total/count/extreme comes from these tools,
which operate on the chain-verified table (Decimal, exact). The agent picks a
tool, the tool returns the number WITH its evidence rows (page/row refs), and
the model only phrases the answer.

Side values in the table are "debit"/"credit"; the tools accept Arabic input
(مدين/سحب‎, دائن/إيداع‎, الكل) and map it.
"""
from __future__ import annotations

from decimal import Decimal

_MONEY = "{:,.2f}"


def _side_match(row_side: str, want: str) -> bool:
    w = (want or "").strip()
    if w in ("", "الكل", "كل", "both", "all"):
        return True
    if w in ("مدين", "سحب", "مدين (سحب)", "debit", "المدين"):
        return row_side == "debit"
    if w in ("دائن", "إيداع", "ايداع", "دائن (إيداع)", "credit", "الدائن"):
        return row_side == "credit"
    return True  # unknown filter: don't over-filter


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

    def _filtered(side: str, keyword: str) -> list[dict]:
        kw = (keyword or "").strip()
        return [r for r in movements
                if _side_match(r.get("side", ""), side)
                and (not kw or kw in _desc(r))]

    @tool
    def sum_movements(side: str = "الكل", keyword: str = "") -> str:
        """اجمع مبالغ الحركات. side: "مدين" (سحوبات) أو "دائن" (إيداعات) أو "الكل".
        keyword: كلمة تُبحث في وصف الحركة (مثال: "تحويل"، "سحب الصراف") — اتركها فارغة للكل.
        مثال: sum_movements(side="مدين") = مجموع كل السحوبات."""
        sel = _filtered(side, keyword)
        total = sum((r["movement"] for r in sel), Decimal("0"))
        if not sel:
            return "لا توجد حركات مطابقة لهذا الفلتر في الكشف."
        examples = "؛ ".join(
            f"{_MONEY.format(r['movement'])} {_ref(r)}" for r in sel[:3])
        return (f"المجموع = {_MONEY.format(total)} ريال | عدد الحركات = {len(sel)}"
                f" | مثال: {examples}")

    @tool
    def count_movements(side: str = "الكل", keyword: str = "") -> str:
        """عدّ الحركات (لا يجمع مبالغ). side: "مدين"/"دائن"/"الكل"، keyword: تصفية بالوصف.
        مثال: count_movements(keyword="تحويل") = عدد التحويلات."""
        sel = _filtered(side, keyword)
        return f"العدد = {len(sel)} حركة (الفلتر: {side}" + \
               (f" | وصف يحتوي '{keyword}'" if (keyword or '').strip() else "") + ")"

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
    def search_rows(keyword: str, limit: int = 15) -> str:
        """ابحث في وصف الحركات عن كلمة وأعد الصفوف المطابقة (الموقع/المبلغ/الاتجاه/الرصيد).
        مثال: search_rows(keyword="تحويل") أو search_rows(keyword="نقاط البيع")."""
        kw = (keyword or "").strip()
        sel = [r for r in movements if kw and kw in _desc(r)]
        if not sel:
            return f"لا توجد حركات وصفها يحتوي '{keyword}'."
        shown = sel[:max(1, int(limit))]
        lines = [
            f"{_ref(r)}: {r.get('side')} {_MONEY.format(r['movement'])}"
            f" → الرصيد {_MONEY.format(r['balance']) if r.get('balance') is not None else '—'}"
            f" — {_desc(r)[:70]}"
            for r in shown
        ]
        more = "" if len(sel) <= len(shown) else f" (و{len(sel) - len(shown)} أخرى)"
        return f"{len(sel)} حركة مطابقة{more}:\n" + "\n".join(lines)

    return [sum_movements, count_movements, balance_extremes,
            closing_balance, page_summary, search_rows]
