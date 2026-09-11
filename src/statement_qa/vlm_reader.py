"""VLM-assisted row reader (OpenRouter gemini-3.7-flash).

Chain-derived architecture (validated on real page 5 — 8/10 exact):
- VLM transcribes printed numbers EXACTLY (Arabic-Indic, ٬ thousands,
  . 00 halalas) — tesseract garbles dense-table digits (skill lesson 6).
- The BALANCE CHAIN derives the true movement: mv[i] = bal[i] − bal[i−1];
  the VLM movement token is only a cross-check (side included).
- VLM rows that fail the chain → suspect → targeted re-read (not silent).

Single-key discipline (skill lesson 10): one stream, retry with backoff,
JSON-parse gate separate from rate-limit retries.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

MODEL = os.environ.get("OPENROUTER_MODEL_VLM", "google/gemini-3.7-flash")
AR_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


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

    '9001.00' -> 9001.00 ; '١١٩.٠٠' -> 119.00 ; null/'' -> None.
    """
    if not tok:
        return None
    t = tok.translate(AR_INDIC).replace("٬", ",").replace("٫", ".").strip()
    t = t.replace("-", "").replace("−", "").replace(" ", "")
    if not t or not re.search(r"\d", t):
        return None
    t = t.replace(",", "")
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def read_rows_vlm(image_path: str) -> list[dict]:
    """One page image -> [{'movement': Decimal|None, 'balance': Decimal|None}].

    Raises RuntimeError after retries; caller decides suspect handling.
    """
    b64 = base64.b64encode(open(image_path, "rb").read()).decode()
    payload = {
        "model": MODEL,
        "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": (
                "This is ONE page of an Al Rajhi bank statement (scanned, Arabic). "
                "In the lower table, each transaction row has numbers on its LEFT side. "
                "Transcribe EVERY transaction row as JSON: "
                '{"rows":[{"movement":"<number closer to the description, exactly as '
                'printed in Arabic-Indic>",'
                '"balance":"<leftmost number, exactly as printed>"}]} '
                "RULES: copy digits EXACTLY as printed (Arabic-Indic with dots/commas "
                "as-is), NO conversion, null for unreadable, JSON only. Include the "
                "opening-balance line at top-left and the totals row at bottom.")},
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
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if not m:
                raise ValueError(f"no JSON in VLM answer: {content[:120]}")
            data = json.loads(m.group(0))
            rows = []
            for r in data.get("rows", []):
                rows.append({
                    "movement": _parse_amount(r.get("movement")),
                    "balance": _parse_amount(r.get("balance")),
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


def chain_derive(rows: list[dict]) -> list[dict]:
    """Balance chain is the arbiter: movement/side derived; VLM mv cross-checks.

    Row 0 = opening (its printed balance starts the chain). Suspect rows
    (|Δ| != printed mv) get ok=False; the caller re-reads them.

    Scale guard (×100 ambiguity, from the 629-page case): when a printed
    balance breaks the chain but ×100 fits (or vice versa), the chain
    value wins and the row is marked scale_fixed — never silently scaled.
    None balances (VLM null) don't crash the walk; they mark gaps.
    """
    out: list[dict] = []
    prev: Decimal | None = None
    for r in rows:
        bal = r["balance"]
        if bal is None:
            out.append({**r, "derived_movement": None, "side": "",
                        "ok": False, "opening": False, "scale_fixed": False})
            prev = None  # chain broken; next row re-anchors
            continue
        if prev is None:
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
