"""Bank guard — «بنك غير مدعوم بعد» must read as ONE clear sentence.

What-if workshop «غير ذلك» scenario: a non-Rajhi (or non-statement) file
currently fails somewhere deep in the pipeline and reads as a mysterious
crash. Instead, ONE probe of page 1 — letterhead (top band) + footer stamp
(bottom band) as two crops in a single VLM call — asks for the bank name:

- confidently mentions الراجحي / rajhi → supported, run proceeds.
- confidently names ANOTHER bank → the app stops BEFORE the long read with
  a clear Arabic message naming what it saw.
- nothing readable / no name → FAIL-OPEN: the run proceeds (never block on
  a guess; the reading itself will decide).

Only `verdict_from_name` matters to the rest of the app; it is pure and
unit-tested. The probe is best-effort and wrapped by callers so a VLM blip
can never stop a run.
"""
from __future__ import annotations

import base64
import io
import re

from PIL import Image

from statement_qa.vlm_reader import _extract_json, chat_vlm_image

# «راجح» covers الراجحي/الراجحى (alef-maqsura) and the Latin stamp AL RAJH…
_MARKER_RE = re.compile(r"راجح|rajh", re.IGNORECASE)

BANK_PROMPT = """هاتان قصّتان من الصفحة الأولى لكشف حساب مصرفي (أعلى الصفحة وأسفلها).
ما اسم البنك الظاهر في أي منهما (شعار، ترويسة، ختم فرع، أو أي نص)؟
أعد JSON فقط: {"bank_name": "اسم البنك كما يظهر حرفياً، أو null إن لم يظهر أي اسم"}.
JSON فقط بلا أي تعليق."""

CROP_TOP_BAND = (0.0, 0.25)     # letterhead band
CROP_BOTTOM_BAND = (0.75, 1.0)  # footer / branch stamp band


def verdict_from_name(bank_name) -> str:
    """'rajhi' | 'other' | 'unknown' — pure, unit-tested."""
    if bank_name is None:
        return "unknown"
    s = str(bank_name).strip()
    if not s or s.lower() in ("null", "none", "غير مقروء", "لا يوجد"):
        return "unknown"
    return "rajhi" if _MARKER_RE.search(s) else "other"


def _band_png(image_path: str, lo: float, hi: float) -> bytes:
    im = Image.open(image_path)
    w, h = im.size
    band = im.crop((0, int(h * lo), w, int(h * hi)))
    buf = io.BytesIO()
    band.save(buf, format="PNG")
    return buf.getvalue()


def _probe_from_content(content: str) -> dict:
    data = _extract_json(content)
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {}
    name = data.get("bank_name") if isinstance(data, dict) else None
    return {"verdict": verdict_from_name(name), "bank": name}


def probe_bank(image_path: str, stats: dict | None = None) -> dict:
    """Page 1 -> {'verdict': ..., 'bank': ...}. Callers catch exceptions."""
    crops = [base64.b64encode(_band_png(image_path, *CROP_TOP_BAND)).decode(),
             base64.b64encode(_band_png(image_path, *CROP_BOTTOM_BAND)).decode()]
    return chat_vlm_image(crops, BANK_PROMPT, max_tokens=800, stats=stats,
                          parse=_probe_from_content)
