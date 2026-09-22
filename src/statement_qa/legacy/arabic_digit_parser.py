#!/usr/bin/env python3
"""Proven Arabic/Persian digit parser for Saudi bank statement scans.

Validated live across 629 scanned pages (Al Rajhi, 2013-2024, Gemini 3.7 Flash
reads). Handles the full zoo of quirks the model and the old prints produce.

Rules baked in (each one was discovered by a live failure):
- BOTH digit tables: Arabic-Indic U+0660-0669 AND Persian U+06F0-06F9.
  Gemini mixes them within a single page and even within one number.
- Dot/comma-only strings like '.,..' = a PRINTED ZERO balance (old pages
  print zero as dots). Return 0.0 — never None — or the balance chain breaks.
- Separators: ٫ (U+066B) and '.' = decimal; ٬ (U+066C) and ، (U+060C) = comma.
- Trailing or leading '-' = negative (old rows print '5,375.80-').
- NO dot present → look at the LAST comma:
    * exactly 2 digits after it  → comma IS the decimal point
      (OLD pages print '300,00' = 300.00; '٥٠,٠٠' = 50.00)
    * exactly 3 digits after it  → thousands separator ('2,900' = 2900)
    * more than 3 after it       → the decimal dot was LOST
      ('61,16512' = 61,165.12 — owner's golden rule)
- Fraction length 1 or 3 after an explicit dot → return None (ambiguous,
  never guess; the balance chain will supply the value).
"""
import re

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

def norm_num(s):
    if s is None:
        return None
    raw = str(s).translate(DIGITS).replace("٫", ".").replace("٬", ",").replace("،", ",")
    if re.fullmatch(r"[\s.,]+", raw):
        # The old prints write a printed zero as «.,..» — several marks. A
        # SINGLE '.' or ',' is a blank/garbled cell, and promoting it to a hard
        # 0.00 injects a fake balance into the chain (audit P3-1: measured zero
        # live cases, latent by construction). Two-plus marks = printed zero.
        if len(raw.strip()) < 2:
            return None
        return 0.0
    neg = raw.strip().startswith("-") or raw.strip().endswith("-")
    t = re.sub(r"[^0-9.,]", "", raw)
    if not t:
        return None
    def f(v):
        return -v if neg else v
    if "." in t:
        a, _, b = t.partition(".")
        a = a.replace(",", "")
        b = re.sub(r"\D", "", b)
        if len(b) == 2 and a:
            return f(round(float(a) + int(b) / 100, 2))
        if len(b) == 0 and a:
            return f(float(a))
        return None
    if "," in t:
        a, _, b = t.rpartition(",")
        a = a.replace(",", "")
        if len(b) == 2:
            return f(round(float(a) + int(b) / 100, 2)) if a else f(float(b) / 100)
        if len(b) == 3:
            return f(float(a) * 1000 + float(b)) if a else f(float(b))
        if len(b) > 3:
            return f(round(float(a) * 1000 + float(b[:3]) + int(b[3:5]) / 100, 2))
        return f(float(a)) if a else None
    return f(float(t))

def gdate(s):
    """Gregorian date from a Gemini date cell like '١٤٣٩٠٧٢٢ ٢٠١٨٠٤٠٨'.
    Prefers the 8-digit run starting with '20' (Hijri runs start with '14')."""
    if not s:
        return None
    nums = re.findall(r"[0-9]{8}", str(s).translate(DIGITS))
    for n in nums:
        if n.startswith("20"):
            return n
    return nums[-1] if nums else None

if __name__ == "__main__":
    cases = {
        "۳۰۰,۰۰": 300.00, "۱۰۰,۰۰": 100.00, "٥٠,٠٠": 50.00,       # قديمة: فاصلة عشرية
        "9001.00": 9001.00, "9001.00": 9001.00,                   # جديدة: نقطة
        "٦١,١٦٥,١٢": 61165.12, "61,16512": 61165.12,              # نقطة ضائعة
        ".,..": 0.0, "٠.٠٠": 0.0, "٥,٣٧٥٫٨٠-": -5375.80,           # صفر وناقص
        "٢٤٥.٠٠": 245.00, "9001.00": 9001.00,                     # قيم عادية
    }
    bad = 0
    for s, want in cases.items():
        got = norm_num(s)
        ok = got is not None and abs(got - want) < 0.01
        if not ok:
            bad += 1
        print(f"{'OK ' if ok else 'FAIL'} {s!r} -> {got} (want {want})")
    assert bad == 0, f"{bad} failures"
    print("all parser cases pass")
