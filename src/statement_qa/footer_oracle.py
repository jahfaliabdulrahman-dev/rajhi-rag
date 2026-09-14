"""Footer oracle — the printed page totals as the EXTERNAL referee.

Why this exists (what-if workshop H1, promoted to P1):
- The balance chain is internally consistent, so a UNIFORM scale shift
  (×100: halalas vs riyals) stays "chain-clean" and slips through every
  internal check. That is the accuracy paradox the workshop named «قاتل».
- Every page carries a printed footer row with THREE numbers — إجمالي مدين /
  إجمالي دائن / الرصيد الختامي (verified on renders; the row sits ≈85% down
  the page in all sampled eras; the legacy case found it on 87/87 old pages).
  Their semantics were VERIFIED against real reads (2026-09-14, sample pp1-6):
    * debits/credits are CUMULATIVE from the statement opening through the
      end of THIS page — p1 650.00/750.00; p2 9001.00/9001.00 (= p1 + p2's
      own 464.00/600.00); p5 9001.00/9001.00 (…+p4 790.00/800.00 + p5
      800.00/9001.00). They stop matching the moment ONE page's sums are
      missed — which is exactly how they exposed a wrong-context read on p5.
    * `balance` is the page's own closing balance.
  Compare:
      prior debits + Σ page debit movements   == footer debits
      prior credits + Σ page credit movements == footer credits
      last balance                            == footer balance

- Any mismatch flags the page (never silently accepted), and a ×100 pattern
  in ALL comparable components is named as the accuracy-paradox signature.
- A page that failed to READ breaks the cumulative chain: subsequent pages
  report «unchecked» (honest — never a guess).

This module is deliberately separate from the frozen row prompt (FRONTIER
stays untouched): one extra small-crop VLM call per page reads the footer
band; everything after that is deterministic Decimal math.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from decimal import Decimal

from PIL import Image

from statement_qa.vlm_reader import _extract_json, _parse_amount, chat_vlm_image

FOOTER_PROMPT = """هذه الحافة السفلية من صفحة كشف حساب مصرفي سعودي (صورة مقصوصة).
تحتوي - إن وُجدت - صف إجماليات مطبوعاً أسفل الجدول: إجمالي عمود المدين، إجمالي عمود الدائن، والرصيد الختامي للصفحة (ثلاثة أرقام في صف واحد؛ الرصيد في أقصى يسار الصف).
انسخ الأرقام حرفياً كما هي مطبوعة بلا أي تحويل.
أعد JSON فقط: {"debits": "الإجمالي في عمود المدين", "credits": "الإجمالي في عمود الدائن", "balance": "الرصيد الختامي"}.
null لأي رقم غير مقروء أو غير موجود. JSON فقط بلا أي تعليق."""

CROP_TOP = 0.75  # bottom band containing the printed totals row


@dataclass
class FooterReading:
    """The three printed page totals, as parsed Decimals (None = unread)."""
    debits: Decimal | None = None
    credits: Decimal | None = None
    balance: Decimal | None = None
    raw: dict = field(default_factory=dict)

    @property
    def any_value(self) -> bool:
        return any(v is not None for v in (self.debits, self.credits, self.balance))


def _footer_crop_png(image_path: str) -> bytes:
    im = Image.open(image_path)
    w, h = im.size
    band = im.crop((0, int(h * CROP_TOP), w, h))
    buf = io.BytesIO()
    band.save(buf, format="PNG")
    return buf.getvalue()


def _reading_from_content(content: str) -> FooterReading | None:
    """VLM answer -> FooterReading; None when nothing readable (runs inside
    the transport retry loop, so malformed JSON re-rolls the call)."""
    data = _extract_json(content)
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {}
    if not isinstance(data, dict):
        return None
    reading = FooterReading(
        debits=_parse_amount(data.get("debits")),
        credits=_parse_amount(data.get("credits")),
        balance=_parse_amount(data.get("balance")),
        raw={k: data.get(k) for k in ("debits", "credits", "balance")},
    )
    return reading if reading.any_value else None


def read_footer(image_path: str, stats: dict | None = None) -> FooterReading | None:
    """Bottom band of the page -> FooterReading (None = nothing readable)."""
    b64 = base64.b64encode(_footer_crop_png(image_path)).decode()
    return chat_vlm_image(b64, FOOTER_PROMPT, max_tokens=1600, stats=stats,
                          parse=_reading_from_content)


def page_totals(rows: list[dict]) -> dict:
    """Page rows -> the three numbers to compare against the footer.

    Accepts chain-derived rows (derived_movement/side/opening) or plain
    app rows (movement/side/kind) — the chain is the arbiter either way.
    Rows whose direction stayed undecided (side "") contribute to NEITHER
    side and are counted, so a mismatch can be explained instead of guessed.
    """
    def _mv(r: dict):
        v = r.get("derived_movement")
        if v is None and (r.get("kind") == "txn"):
            v = r.get("movement")
        return v

    def _is_opening(r: dict) -> bool:
        return bool(r.get("opening")) or r.get("kind") == "opening"

    debits = credits = Decimal("0")
    undecided = 0
    last_balance = None
    for r in rows:
        bal = r.get("balance")
        if bal is not None:
            last_balance = bal
        if _is_opening(r):
            continue
        mv = _mv(r)
        if mv is None:
            continue
        side = r.get("side") or ""
        if side == "debit":
            debits += mv
        elif side == "credit":
            credits += mv
        else:
            undecided += 1
    return {"debits": debits, "credits": credits,
            "balance": last_balance, "undecided": undecided}


def _x100(a: Decimal | None, b: Decimal | None) -> bool:
    if a is None or b is None or a == 0 or b == 0:
        return False
    return a * 100 == b or a == b * 100


def check_page_footer(rows: list[dict], footer: FooterReading | None,
                      prior: dict | None = None, skip: bool = False) -> dict:
    """Deterministic comparison — the heart of the oracle.

    `prior` = {'debits','credits'} accumulated over PREVIOUS pages
    (statement start → previous page); the footer's debits/credits are
    cumulative-to-date (see module docstring for the verified evidence).
    `skip=True` (a previous page failed to read) → status 'unchecked':
    cumulative sums cannot be reconstructed across a missing page.

    status:
      ok         — every comparable component matches exactly (Al Rajhi rule:
                   no signs, exact arithmetic; 2dp).
      mismatch   — with per-field diffs; is_paradox=True when EVERY mismatched
                   component is off by exactly ×100/÷100 (the accuracy-paradox
                   signature — the one scenario that must never pass silently).
      absent     — no footer readable / nothing comparable on the page.
      unchecked  — a prior page failed; the cumulative chain is broken.
    """
    if skip:
        return {"status": "unchecked", "compared": 0}
    own = page_totals(rows)
    prior = prior or {"debits": Decimal("0"), "credits": Decimal("0")}
    cum = {"debits": prior["debits"] + own["debits"],
           "credits": prior["credits"] + own["credits"],
           "balance": own["balance"]}
    if footer is None:
        return {"status": "absent", "totals": cum, "own": own, "compared": 0}
    diffs = []
    compared = 0
    for fname in ("debits", "credits", "balance"):
        fv = getattr(footer, fname)
        av = cum.get(fname)
        if fv is None or av is None:
            continue
        compared += 1
        if av != fv:
            diffs.append({"field": fname, "app": str(av), "footer": str(fv)})
    if not compared:
        return {"status": "absent", "totals": cum, "own": own, "compared": 0}
    if diffs:
        is_paradox = all(_x100(Decimal(d["app"]), Decimal(d["footer"]))
                         for d in diffs)
        return {"status": "mismatch", "totals": cum, "own": own,
                "compared": compared, "diffs": diffs, "is_paradox": is_paradox}
    return {"status": "ok", "totals": cum, "own": own, "compared": compared}


def _main() -> None:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="footer oracle probe")
    ap.add_argument("image", help="page PNG render")
    ap.add_argument("--rows", help="optional statement_rows.jsonl to compare")
    ap.add_argument("--page", type=int, default=1, help="page number in rows file")
    args = ap.parse_args()

    reading = read_footer(args.image)
    print("footer:", reading)
    if args.rows:
        rows = [json.loads(l) for l in open(args.rows, encoding="utf-8")
                if l.strip()]
        page_rows = [r for r in rows if r.get("page") == args.page]
        print("check:", check_page_footer(page_rows, reading))


if __name__ == "__main__":
    _main()
