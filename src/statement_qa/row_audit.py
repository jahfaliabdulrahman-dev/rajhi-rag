"""تدقيق صفّ واحد: هل وصفُه يوافق الاتجاه الذي أثبتته السلسلة؟

Why this exists
---------------
The balance chain proves the AMOUNT and the DIRECTION of every movement, and the
printed footer proves the page totals. Neither says anything about the free-text
description column — so a row whose description was paired with the wrong amount
passes every gate the pipeline had (measured: 629 pages, 1 page with the
signature, and it reached a delivered workbook).

The check is arithmetic, not visual, and needs no model: «مدفوعات نقاط البيع»
and «سحب الصراف الآلي» take money OUT of the account, so a credit movement
carrying one of those labels cannot be a correct pairing. A debit↔debit shift
stays invisible here — this is a lower bound, and it is documented as one.
"""
from __future__ import annotations

from decimal import Decimal

# أوصاف تُخرج المال من الحساب: لا تكون دائنة في هذا الكشف.
DEBIT_ONLY_DESCRIPTIONS = ("مدفوعات نقاط البيع", "سحب الصراف", "سحب نقدي")
# أوصاف تُدخل المال: لا تكون مدينة.
CREDIT_ONLY_DESCRIPTIONS = ("إيداع راتب", "راتب", "حوالة واردة", "إيداع نقدي")


def desc_direction_clash(rows: list[dict]) -> list[dict]:
    """الصفوف التي يناقض وصفُها اتجاهَ حركتها — دليل إزاحة وصف.

    rows: صفوف مشتقّة بالسلسلة (تحتاج `side` و`desc`). المبلغ للعرض فقط.
    يعيد قائمة بنود مقروءة: {row: 1-based, desc, side, movement, reason}.
    """
    out: list[dict] = []
    for i, r in enumerate(rows, start=1):
        side = (r.get("side") or "").strip()
        desc = str(r.get("desc") or "")
        if not side or not desc:
            continue
        bad = ((side == "credit" and _hit(desc, DEBIT_ONLY_DESCRIPTIONS))
               or (side == "debit" and _hit(desc, CREDIT_ONLY_DESCRIPTIONS)))
        if not bad:
            continue
        mv = r.get("derived_movement") or r.get("movement")
        out.append({
            "row": i,
            "desc": desc[:80],
            "side": side,
            "movement": str(mv) if mv is not None else None,
            "reason": (f"الوصف «{bad}» لا يكون "
                       f"{'دائناً' if side == 'credit' else 'مديناً'} في هذا الكشف "
                       f"— الوصف أُزيح عن مبلغه"),
        })
    return out


def _hit(desc: str, needles: tuple[str, ...]) -> str | None:
    return next((n for n in needles if n in desc), None)


def clash_resolved(before: list[dict], after: list[dict]) -> bool:
    """هل أزالت إعادةُ القراءة تناقضَ الوصف؟

    الشرط: كان هناك تناقض، ولم يبقَ بعده. إعادة القراءة التي تُصلح رقماً
    وتُدخل تناقضاً في الوصف لا تُقبل — القراءة الجديدة تُقاس بنفس الميزان.
    """
    return bool(before) and not after


def nonzero_row_count(rows: list[dict]):
    """عدد الصفوف التي فيها حركة فعلية (لا سطور إجماليات ولا أرصدة مرحّلة)."""
    n = 0
    for r in rows:
        if r.get("opening"):
            continue
        mv = r.get("derived_movement", r.get("movement"))
        if mv is None:
            continue
        try:
            if Decimal(str(mv)) != 0:
                n += 1
        except (ArithmeticError, ValueError):
            continue
    return n
