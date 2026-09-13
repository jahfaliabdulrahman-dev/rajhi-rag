"""Deterministic transaction-type classification — a LABEL layer only.

The type is derived from the printed description; it NEVER touches amounts,
balances, or sides (those come from the balance chain, which stays the sole
arbiter). Pure rules, no model: same input -> same label, auditable.

Vocabulary is built from the REAL 10-page sample inventory (Phase-0 audit):
  - سحب الصراف الآلي / الألي / الالى (+ EN ATM locations)
  - تحويل / التحويل من الحساب ... / التحويل للحساب ...  (صادر/وارد by side)
  - ايداع الصراف الالي Cash Deposit
  - مدفوعات نقاط البيع (POS)
  - فواتير نظام سداد / مدفوعات سداد رخص القيادة
Unknown text falls back to "غير مصنّف" — transparent, never a wrong claim.
"""
from __future__ import annotations

import re

__all__ = ["classify", "annotate_types"]

_TATWEEL = "\u0640"
_DIACRITICS = "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0670"

_ATM_RE = re.compile(r"\batm\b")
_POS_RE = re.compile(r"\bpos\b")


def _norm(s: str | None) -> str:
    """Arabic normalization: strip diacritics/tatweel, unify alef/ya/ta
    variants, collapse whitespace, lowercase latin."""
    s = s or ""
    for ch in _DIACRITICS:
        s = s.replace(ch, "")
    s = s.replace(_TATWEEL, "")
    s = (s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
         .replace("ة", "ه").replace("ى", "ي").replace("ئ", "ي").replace("ؤ", "و"))
    return " ".join(s.split()).lower()


def classify(desc: str | None, side: str = "") -> str:
    """One description + chain side -> user-facing Arabic type label.

    Rule order matters — first match wins:
    transfers come FIRST because "التحويل ... الصراف الالي" contains صراف
    but is an account-to-account transfer, never an ATM operation.
    """
    d = _norm(desc)
    if not d:
        return "غير مصنّف"

    if "افتتاح" in d:
        return "رصيد افتتاحي"

    if "تحويل" in d or "حواله" in d:
        if side == "credit":
            return "تحويل وارد"
        if side == "debit":
            return "تحويل صادر"
        return "تحويل"

    if "صراف" in d or _ATM_RE.search(d):
        if "ايداع" in d or "deposit" in d:
            return "إيداع نقدي (صراف آلي)"
        return "سحب صراف آلي"

    if "ايداع" in d or "deposit" in d:
        if "راتب" in d or "مرتب" in d:
            return "إيداع راتب"
        return "إيداع"

    if ("نقاط البيع" in d or "نقاط بيع" in d or "مشتريات" in d
            or _POS_RE.search(d)):
        return "مشتريات (نقاط بيع)"

    if "سداد" in d:
        return "فواتير ومدفوعات سداد"

    if ("فاتوره" in d or "فواتير" in d or "كهرباء" in d or "مياه" in d
            or "اتصالات" in d or "موبايلي" in d):
        return "فواتير خدمات"

    if "راتب" in d or "مرتب" in d:
        return "إيداع راتب"

    if "رسوم" in d or "عموله" in d or "اتعاب" in d or "غرامه" in d:
        return "رسوم وعمولات"

    if "شيك" in d or "صك" in d:
        return "شيك"

    if "قسط" in d or "تمويل" in d or "مرابحه" in d:
        return "تمويل/أقساط"

    if "تعديل" in d or "تسويه" in d or "تصحيح" in d or "عكس" in d:
        return "تسوية/تعديل"

    if "سحب" in d:
        return "سحب"

    return "غير مصنّف"


def annotate_types(rows: list[dict]) -> None:
    """Attach r['type'] in place. Opening rows carry the structural label
    (رصيد افتتاحي / رصيد سابق); classification NEVER modifies movement,
    balance, side or ok."""
    for r in rows:
        if r.get("kind") == "opening":
            d = _norm(r.get("desc") or "")
            r["type"] = "رصيد سابق" if "سابق" in d else "رصيد افتتاحي"
        else:
            r["type"] = classify(r.get("desc"), r.get("side") or "")
