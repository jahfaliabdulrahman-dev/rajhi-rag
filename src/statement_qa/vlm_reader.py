"""VLM-assisted row reader (OpenRouter gemini-3.7-flash).

v2 — INHERITS THE FROZEN PROMPT SET from the 629-page case
(src/statement_qa/legacy/prompts.py, owner directive: "العلم تراكمي").
Chain-derived architecture (validated on real page 5 — 8/10 exact):
- VLM transcribes printed numbers EXACTLY (Arabic-Indic, ٬ thousands,
  . 00 halalas) — tesseract garbles dense-table digits (skill lesson 6).
- The BALANCE CHAIN derives the true movement: mv[i] = bal[i] − bal[i−1];
  the VLM movement token is only a cross-check (side included).
- VLM rows that fail the chain → suspect → targeted re-read (not silent).

Chain-index rule (legacy lesson 3): balance prints AFTER the transaction —
amt[i+1] == bal[i] − bal[i+1]. Single-key discipline (legacy lesson 10):
one stream, retry with backoff, JSON-parse gate separate from rate-limit
retries.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.request
from decimal import Decimal
from pathlib import Path

from statement_qa.legacy.prompts import (
    FRONTIER_PROMPT, STRUCTURE_AWARE_PROMPT, TOP_BAND_PROMPT, HARD_RULES,
)
from statement_qa.legacy.arabic_digit_parser import norm_num as _legacy_norm_num

MODEL = os.environ.get("OPENROUTER_MODEL_VLM", "google/gemini-3.7-flash")


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    for line in open(Path.home() / ".hermes" / ".env"):
        if line.strip().startswith("OPENROUTER_API_KEY="):
            return line.strip().split("=", 1)[1].strip("\"'")
    raise RuntimeError("OPENROUTER_API_KEY not found")


def _parse_amount(tok: str | None) -> Decimal | None:
    """Printed Arabic-Indic money token -> Decimal (Western digits, dot halalas).

    DELEGATES to the proven legacy parser (629-page case) — it owns the full
    separator zoo: '٣٠٠,٠٠' -> 300.00 (comma is the decimal point on old
    prints), '.,..' -> 0.00 (printed zero), '٥٧,٥٠٢٧٥' -> 57502.75 (lost
    dot), '١١٩.٠٠-' -> -119.00 (trailing minus). A local re-implementation
    once regressed all four of these at once — never re-implement; inherit.
    """
    if not tok:
        return None
    v = _legacy_norm_num(tok)
    if v is None:
        return None
    # money is 2dp forever: Decimal('300.0') would display as '300.0' —
    # quantize keeps the halala scale so every display/format shows 300.00
    return Decimal(str(v)).quantize(Decimal("0.01"))


def read_rows_vlm(image_path: str, prompt: str | None = None,
                  max_tokens: int = 4000) -> list[dict]:
    """One page image -> [{'movement': Decimal|None, 'balance': Decimal|None,
                           'desc': str|None, 'date': str|None}].

    Uses the FROZEN era-neutral prompt from the 629-page case by default
    (FRONTIER_PROMPT) — proven copy-exact behavior. Pass
    prompt=STRUCTURE_AWARE_PROMPT for red-band anatomy reads, or a
    TOP_BAND_PROMPT.format(...) for boundary recovery.

    Raises RuntimeError after retries; caller decides suspect handling.
    """
    user_prompt = prompt or FRONTIER_PROMPT
    b64 = base64.b64encode(open(image_path, "rb").read()).decode()
    payload = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]}],
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {_api_key()}",
                 "Content-Type": "application/json"})
    delay = 10
    for attempt in range(3):
        try:
            out = json.loads(urllib.request.urlopen(req, timeout=180).read().decode())
            content = out["choices"][0]["message"]["content"]
            m = re.search(r"[\[{].*[\]}]", content, re.DOTALL)
            if not m:
                raise ValueError(f"no JSON in VLM answer: {content[:120]}")
            data = json.loads(m.group(0))
            vlm_rows = data if isinstance(data, list) else data.get("rows", [])
            rows = []
            for r in vlm_rows:
                rows.append({
                    "movement": _parse_amount(r.get("amount") or r.get("movement")),
                    "balance": _parse_amount(r.get("balance")),
                    "desc": r.get("desc") or r.get("desc_main"),
                    "date": r.get("greg") or r.get("date"),
                })
            return rows
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(delay); delay *= 2
                continue
            raise RuntimeError(f"VLM HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 2:
                time.sleep(delay); delay *= 2
                continue
            raise RuntimeError(f"VLM network: {e}") from e
    raise RuntimeError("VLM retries exhausted")


_OPENING_MARKERS = ("افتتاح", "سابق")


def _looks_opening(r: dict) -> bool:
    """Opening/carry rows print افتتاح/سابق descriptions; anything else with a
    printed amount is a transaction we must not swallow."""
    d = r.get("desc") or ""
    return any(m in d for m in _OPENING_MARKERS)


def chain_derive(rows: list[dict], prev_balance: Decimal | None = None) -> list[dict]:
    """Balance chain is the arbiter: movement/side derived; VLM mv cross-checks.

    Row 0 of a fresh read = opening (its printed balance starts the chain).

    prev_balance (closing of the PREVIOUS page) enables cross-page continuity —
    the first balance row of a new page is NOT blindly an opening:
    - delta == 0                → carried balance row (رصيد سابق).
    - delta == the printed amt  → a REAL transaction starting the page (a scan
      boundary must not swallow its movement: a transfer +1000 turning 676 into
      1676 was once displayed as "opening 1676", losing the operation entirely).
    - anything else (incl. unreadable amt) → opening anchor; a movement is NEVER
      fabricated across a boundary we cannot verify.

    Suspect rows (|Δ| != printed mv) get ok=False; the caller re-reads them.
    Scale guard (×100 ambiguity, 629-page case): when a printed balance breaks
    the chain but ×100 fits (or vice versa), the chain value wins and the row is
    marked scale_fixed — never silently scaled.
    None balances (VLM null) don't crash the walk; they mark gaps.
    """
    out: list[dict] = []
    prev: Decimal | None = prev_balance
    boundary_pending = prev_balance is not None
    for r in rows:
        bal = r["balance"]
        if bal is None:
            out.append({**r, "derived_movement": None, "side": "",
                        "ok": False, "opening": False, "scale_fixed": False})
            prev = None  # chain broken; next row re-anchors
            boundary_pending = False
            continue
        if boundary_pending:
            boundary_pending = False
            delta = bal - prev
            printed = r["movement"]
            if delta == 0:
                out.append({**r, "derived_movement": Decimal("0"), "side": "",
                            "ok": True, "opening": True, "scale_fixed": False})
            elif printed is not None and printed == abs(delta):
                side = "credit" if delta > 0 else "debit"
                out.append({**r, "derived_movement": abs(delta), "side": side,
                            "ok": True, "opening": False, "scale_fixed": False})
            else:
                out.append({**r, "derived_movement": Decimal("0"), "side": "",
                            "ok": True, "opening": True, "scale_fixed": False})
        elif prev is None:
            printed = r["movement"]
            if printed is not None and not _looks_opening(r):
                # Fresh start whose opening row was not read (VLM occasionally
                # misses the dots-zero line): the row demonstrably IS a
                # transaction (printed amount + a real description) — keep its
                # movement visible; side stays undecided (no previous balance
                # to derive it from — never guess).
                out.append({**r, "derived_movement": printed, "side": "",
                            "ok": True, "opening": False, "scale_fixed": False})
            else:
                out.append({**r, "derived_movement": Decimal("0"), "side": "",
                            "ok": True, "opening": True, "scale_fixed": False})
        else:
            delta = bal - prev
            mv = abs(delta)
            side = "credit" if delta > 0 else "debit" if delta < 0 else ""
            printed = r["movement"]
            ok = printed is None or printed == mv
            scale_fixed = False
            if not ok and printed is not None and printed != 0:
                # ×100 ambiguity: printed*100 == mv or printed == mv*100
                if printed * 100 == mv or printed == mv * 100:
                    ok, scale_fixed = True, True
            out.append({**r, "derived_movement": mv, "side": side,
                        "ok": ok, "opening": False, "scale_fixed": scale_fixed})
        prev = bal
    return out


if __name__ == "__main__":
    import sys

    rows = read_rows_vlm(sys.argv[1])
    for r in chain_derive(rows):
        mark = "✓" if r["ok"] else "✗"
        print(f"{mark} bal={r['balance']} mv={r['movement']} "
              f"derived={r['derived_movement']} side={r['side']}")
