"""Arabic RTL Gradio app — «دفتر الأستاذ» (light) / «السجل الليلي» (dark).

Design direction locked (2026-09-13, after research pass):
- Borrowings: Notion (warm minimalism, serif display), Stripe (weight-300
  elegance, hairline precision), IBM Carbon (structured data grids) — adapted
  to an archival Arabic palette: warm paper + deep ink + brass hairlines +
  emerald ink accents.
- Signature move: the verification seal (ختم التدقيق) echoing the bank's own
  branch stamp on the scanned pages; hairline «ledger rules» as the recurring
  material. KPI strip built as a ruled ledger table, not floating cards.
- Dark mode is designed independently: «السجل الليلي» (ink blue-black with
  warm paper text), never auto-inverted.

3 tabs:
١. قراءة وتحقق — upload → page renders → VLM+chain rows → KPI ledger strip,
   results table, visual gallery of the scanned pages.
٢. سؤال وجواب — a real Chatbot surface over the Faiss retrieval + the
   deterministic LangChain tools (the model calls, it never computes).
٣. عن المشروع — architecture + privacy rule.

Gate compatibility: process_pdf output[0]=summary text and output[1]=table keep
their exact shape (tools/qa_gate.py depends on them).
"""

from __future__ import annotations

import re
import tempfile
from decimal import Decimal
from pathlib import Path

import gradio as gr
import pandas as pd
from pdf2image import convert_from_path, pdfinfo_from_path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from statement_qa.chunking import chunk_rows
from statement_qa.classify import annotate_types
from statement_qa.retriever import build_index
from statement_qa.vlm_reader import (
    chain_derive, fill_missing_dates, read_rows_vlm, recover_anchor,
)
from statement_qa.bank_check import probe_bank
from statement_qa.era import fingerprint_pages, summarize_ar as summarize_era_ar
from statement_qa.render import (
    answer_refs as render_answer_refs,
    answer_text as render_answer_text,
    date_cell as render_date_cell,
    evidence_mode as render_evidence_mode,
    row_record as render_row_record,
    rows_for_refs as render_rows_for_refs,
)
from statement_qa.verification import (
    caution as verification_caution,
    coverage_line as verification_coverage,
    format_effects,
    verdicts_from_checks,
)
from statement_qa.footer_oracle import (
    check_page_footer, delta_checkable, delta_status, page_diverged,
    read_footer, try_page_reread,
)
from statement_qa.job_lock import JobBusyError, job_lock
from statement_qa.ordering import (
    check_order, check_page_numbers, summarize_ar as summarize_order_ar,
    summarize_page_numbers,
)

STATE = {}

# قفل «مهمة واحدة» — نافذتان متزامنتان كانتا تخلطان النتائج والسجلات.
LOCK_PATH = Path(__file__).resolve().parent / "data" / ".rajhi-job.lock"

# ————— الهوية اللونية —————
PAPER = "#F7F2E9"
PAPER_CARD = "#FFFDF8"
PAPER_DEEP = "#F1EADC"
INK = "#191713"
INK_SUB = "#6B6355"
BRASS = "#A98A4A"
EMERALD = "#0E6B57"
EMERALD_DEEP = "#0A5344"
HAIRLINE = "#E6DCC8"
WARN = "#B4503C"
# dark — السجل الليلي
NIGHT = "#14161C"
NIGHT_CARD = "#1B1E26"
NIGHT_DEEP = "#171A21"
NIGHT_TEXT = "#EDE6D6"
NIGHT_SUB = "#9A927F"
NIGHT_HAIR = "#2A2E39"
NIGHT_EMERALD = "#3FA98C"

RTL_CSS = """
/* ————— طبقات RTL (وصفة مُجرَّبة) ————— */
.gradio-container { direction: rtl; }
.gradio-container .block[dir="ltr"] { direction: rtl; }
.gradio-container label.float { left: auto !important; right: 6px !important; }
footer { direction: ltr; }

/* ————— البطل (hero) والختم ————— */
.hero { position: relative; overflow: hidden; border: 1px solid var(--border-color-primary);
        border-radius: 12px; background: var(--background-fill-primary);
        padding: 26px 30px 18px; }
.hero h1 { font-family: 'Amiri', 'Noto Naskh Arabic', serif !important; font-weight: 700;
           font-size: 2.1rem; line-height: 1.3; margin: 0 0 8px; }
.hero .sub { color: var(--body-text-color-subdued); font-size: .97rem; max-width: 78%; }
.hero .rule { height: 1px; background: #A98A4A; opacity: .45; margin-top: 16px; }
.seal { position: absolute; top: 50%; transform: translateY(-50%); inset-inline-end: 24px;
        width: 98px; height: 98px; opacity: .95; }

/* ————— شريط المؤشرات (جدول دفاتر مُسطَّر) ————— */
.ledger-kpi { display: grid; grid-template-columns: repeat(4, 1fr);
              border: 1px solid var(--border-color-primary); border-radius: 12px;
              overflow: hidden; background: var(--background-fill-primary); }
.ledger-kpi .cell { padding: 18px 20px 14px; }
.ledger-kpi .cell + .cell { border-inline-start: 1px solid var(--border-color-primary); }
.ledger-kpi .num { font-size: 1.75rem; font-weight: 600;
                   font-variant-numeric: tabular-nums; letter-spacing: .3px; }
.ledger-kpi .cap { margin-top: 2px; font-size: .8rem; color: var(--body-text-color-subdued); }
.ledger-kpi .cap::before { content: "— "; color: #A98A4A; }
.ledger-kpi .ok .num { color: var(--color-accent); }
.ledger-kpi .warn .num { color: #B4503C; }

/* ————— شريط الحالة ————— */
/* elem_classes lands on BOTH the block wrapper and the inner prose element —
   scope the border to the wrapper and the dot to the inner prose only
   (otherwise the dot and dashed frame render twice). */
.ticker.block { border: 1px dashed #C9BFA6; border-radius: 10px;
                padding: 14px 18px !important; }
.ticker.prose { border: none !important; padding: 0 !important;
                background: transparent; line-height: 1.7; }
.ticker.prose::before { content: "●"; color: var(--color-accent); font-size: .72rem;
                        margin-inline-end: 8px; }
.ticker p { margin: 0 !important; }

/* ————— الجدول ————— */
.ledger-table table { font-variant-numeric: tabular-nums; }
.ledger-table thead th { background: var(--background-fill-secondary) !important;
                         color: var(--body-text-color-subdued) !important;
                         font-weight: 600 !important; }

/* ————— المحادثة ————— */
#chat-surface { border: 1px solid var(--border-color-primary); border-radius: 12px;
                overflow: hidden; }

/* ————— شارة الملف: زر الإكس لا يعلو شريحة العنوان ————— */
#file-panel .icon-button-wrapper.top-panel {
    left: 6px !important; right: auto !important;
    top: 8px !important;
}

/* الوضع الليلي: ترطيب الإبر — لا انقلاب آلي */
@media (prefers-color-scheme: dark) {
  .hero .rule { background: #C2A468; }
  .ticker.block { border-color: #3A4050; }
  .ledger-kpi .warn .num { color: #C96A57; }
}
"""

ARABIC_FONT = gr.themes.GoogleFont("IBM Plex Sans Arabic",
                                   weights=(400, 500, 600, 700))
MONO_FONT = gr.themes.GoogleFont("JetBrains Mono", weights=(400, 500))

THEME = gr.themes.Soft(
    primary_hue="emerald",
    neutral_hue="stone",
    radius_size="sm",
    spacing_size="md",
    font=ARABIC_FONT,
    font_mono=MONO_FONT,
)
THEME.set(
    # light — دفتر الأستاذ (ورق دافئ + حبر)
    body_background_fill=PAPER,
    body_text_color=INK,
    body_text_color_subdued=INK_SUB,
    background_fill_primary=PAPER_CARD,
    background_fill_secondary=PAPER_DEEP,
    block_background_fill=PAPER_CARD,
    block_border_color=HAIRLINE,
    block_label_text_color=INK_SUB,
    block_title_text_color=INK,
    border_color_primary=HAIRLINE,
    input_background_fill=PAPER_CARD,
    input_border_color="#DDD2BB",
    button_primary_background_fill=EMERALD,
    button_primary_background_fill_hover=EMERALD_DEEP,
    button_primary_text_color=PAPER,
    button_secondary_background_fill=PAPER_CARD,
    button_secondary_text_color=INK,
    button_secondary_border_color="#C9BFA6",
    color_accent_soft="#E9F2EC",
    table_even_background_fill=PAPER_CARD,
    table_odd_background_fill="#FBF6EC",
    table_border_color=HAIRLINE,
    # dark — السجل الليلي (تصميم مستقل لا انقلاب)
    body_background_fill_dark=NIGHT,
    body_text_color_dark=NIGHT_TEXT,
    body_text_color_subdued_dark=NIGHT_SUB,
    background_fill_primary_dark=NIGHT_CARD,
    background_fill_secondary_dark=NIGHT_DEEP,
    block_background_fill_dark=NIGHT_CARD,
    block_border_color_dark=NIGHT_HAIR,
    block_label_text_color_dark=NIGHT_SUB,
    block_title_text_color_dark=NIGHT_TEXT,
    border_color_primary_dark=NIGHT_HAIR,
    input_background_fill_dark=NIGHT_DEEP,
    input_border_color_dark="#333845",
    button_primary_background_fill_dark=NIGHT_EMERALD,
    button_primary_background_fill_hover_dark="#46B795",
    button_primary_text_color_dark="#0F1216",
    button_secondary_background_fill_dark=NIGHT_CARD,
    button_secondary_text_color_dark=NIGHT_TEXT,
    button_secondary_border_color_dark="#3A4050",
    color_accent_soft_dark="#1E2A27",
    table_even_background_fill_dark=NIGHT_CARD,
    table_odd_background_fill_dark="#191C23",
    table_border_color_dark=NIGHT_HAIR,
)

HEAD = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Amiri:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
"""

HERO = """
<div class="hero">
  <svg class="seal" viewBox="0 0 100 100" aria-hidden="true">
    <defs>
      <path id="sealArc" d="M 50,50 m -34,0 a 34,34 0 1,1 68,0 a 34,34 0 1,1 -68,0"/>
    </defs>
    <circle cx="50" cy="50" r="46.5" fill="none" stroke="#A98A4A" stroke-width="1.1"/>
    <circle cx="50" cy="50" r="40" fill="none" stroke="#A98A4A" stroke-width="0.55"/>
    <text font-size="7.6" fill="#A98A4A" letter-spacing="0.6">
      <textPath href="#sealArc" startOffset="25%" text-anchor="middle">السلسلة الرصيدية · حَكَم لا يخطئ</textPath>
    </text>
    <text x="50" y="54" text-anchor="middle" font-family="Amiri, serif" font-size="21" fill="#0E6B57">مُدقَّق</text>
    <text x="50" y="70" text-anchor="middle" font-size="8.5" fill="#6B6355">آلياً</text>
  </svg>
  <h1>مُدقّق كشوف الراجحي</h1>
  <div class="sub">من المسح الضوئي إلى الجواب الموثّق: قراءة حرفية، سلسلة رصيدية هي الحَكَم، وأدوات حسابية لا تخطئ — لأن الرقم أمانة.</div>
  <div class="rule"></div>
</div>
"""


def _money(v) -> str:
    """Decimal/None -> fixed 2dp display so halalas are always visible."""
    return f"{v:,.2f}" if v is not None else ""


def _kpi_html(n_rows: int, n_clean: int, n_susp: int, last_bal) -> str:
    cells = [
        ("الصفوف المستخرجة", f"{n_rows}", ""),
        ("نظيف السلسلة", f"{n_clean}", "ok"),
        ("مشبوه", f"{n_susp}", "warn" if n_susp else ""),
        ("آخر رصيد (ر.س)", _money(last_bal) if last_bal is not None else "—", ""),
    ]
    inner = "".join(
        f'<div class="cell {cls}"><div class="num">{num}</div>'
        f'<div class="cap">{cap}</div></div>'
        for cap, num, cls in cells)
    return f'<div class="ledger-kpi">{inner}</div>'


def _date_cell(r: dict) -> str:
    """Date for the table/export: Gregorian `YYYY/MM/DD`; `*` = inherited.

    The printed cell may carry both calendars (hijri first) — parse_gregorian
    picks the gregorian run; unparseable cells show as printed (never dropped).
    """
    return render_date_cell(r)


def _row_record(no: int, r: dict) -> dict:
    """Delegates to the tested pure implementation (statement_qa.render).

    Callers keep the same shape; the logic that decides the columns — including
    the new «التحقق» column, which is the page's oracle verdict — lives in the
    module the tests can reach (audit P1-5, P3-4).
    """
    return render_row_record(no, r, STATE.get("verdicts") or {})


def _rows_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([_row_record(i, r)
                         for i, r in enumerate(rows, start=1)])


def filter_rows(query: str) -> pd.DataFrame:
    """Server-side table filter.

    The returned dataframe CONTAINS only the matching rows, so the table's
    copy button copies exactly what the user filtered — the built-in search
    box only filtered the view while copying the full set (owner report).
    """
    rows = STATE.get("rows") or []
    df = _rows_df(rows)
    q = (query or "").strip()
    if not q or df.empty:
        return df
    ql = q.lower().replace(",", "")
    hay = df.astype(str).agg(" ".join, axis=1).str.lower()
    mask = (hay.str.contains(ql, regex=False)
            | hay.str.replace(",", "", regex=False).str.contains(ql, regex=False))
    return pd.DataFrame(df.loc[mask]).reset_index(drop=True)


# Hard limits on the browser path (what-if delta #7, audit P2-3). The
# interface has no checkpoint and no resume, so one long upload is hours of
# paid calls inside a single request that dies with the tab and takes every
# paid page with it. The cap is a ROUTING decision, not a limit of the
# engine: the full reader is tools/scale_slice.py (page checkpoints, cost
# ledger, fail-streak and budget gates). Numbers here are the measured ones:
# 100 pages ≈ 50 minutes ≈ $1.4; the fail streak of 5 is what stopped the
# real 402 outage instead of spinning for ~12 hours.
MAX_UI_PAGES = 100
MAX_UI_COST_USD = 3.0
FAIL_STREAK_LIMIT = 5


def _pages_to_pngs(pdf_path: str, dpi: int = 200):
    try:
        n_pages = int(pdfinfo_from_path(pdf_path).get("Pages") or 0)
    except Exception:
        n_pages = 0        # fail open: a broken pdfinfo never blocks a run
    if n_pages > MAX_UI_PAGES:
        raise gr.Error(
            f"الملف {n_pages} صفحة — والحد على هذا المسار {MAX_UI_PAGES} صفحة "
            f"لكل تشغيل من المتصفح: لا نقاط حفظ ولا استئناف هنا، وانقطاع "
            f"الطلب يُهدر كل ما دُفع. للملفات الكبيرة استخدم أداة سطر الأوامر "
            f"(نقاط حفظ + دفتر كلفة + حواجز توقف):\n"
            f"python3 tools/scale_slice.py --first 1 --count {n_pages} "
            f"--out data/local_sample/slice_{n_pages}p --max-cost 12"
        )
    outdir = tempfile.mkdtemp(prefix="rajhi_pages_")
    paths = convert_from_path(pdf_path, dpi=dpi)
    out = []
    for i, img in enumerate(paths, start=1):
        p = Path(outdir) / f"pg-{i:02d}.png"
        img.save(p)
        out.append(str(p))
    return out


def process_pdf(pdf_path: str, progress=gr.Progress()):
    """Tab 1 handler — single-job lock → read all pages → chain-audit →
    footer oracle + era/order checks → chunks+index.

    Cross-page continuity: each page receives the previous page's closing
    balance. A page whose FIRST row is a real transaction (delta == printed
    amount) keeps its movement — scan boundaries never swallow operations.

    Guarded by the single-job lock (what-if delta #3): a second concurrent
    run gets a clear Arabic message instead of interleaving with this one.
    """
    if not pdf_path:
        raise gr.Error("ارفع ملف PDF أولاً ثم اضغط «قراءة الكشف».")
    try:
        with job_lock(LOCK_PATH):
            return _process_pdf_locked(pdf_path, progress)
    except JobBusyError:
        raise gr.Error("يوجد تشغيل جارٍ الآن (نافذة أو طلب آخر) — "
                       "انتظر انتهاءه ثم أعد المحاولة.")


def _process_pdf_locked(pdf_path: str, progress):
    pages = _pages_to_pngs(pdf_path)

    # «بنك غير مدعوم» جملة واضحة بدل فشل غامض — فحص واحد للصفحة الأولى،
    # ويفشل مفتوحاً: أي التباس يمرّر التشغيل (لا قرار على تخمين).
    bank_usage: dict = {}
    try:
        bank = probe_bank(pages[0], stats=bank_usage)
    except Exception:
        bank = {"verdict": "unknown", "bank": None}
    if bank["verdict"] == "other":
        raise gr.Error(f"يبدو أن هذا الملف لا يخص مصرف الراجحي "
                       f"(ظهر: «{bank['bank']}») — الإصدار الحالي يدعم "
                       f"كشوف الراجحي فقط.")

    all_rows = []
    failed_pages: list[int] = []
    footer_checks: list[dict] = []
    era_pages: dict[int, list] = {}
    page_dates: dict[int, list] = {}
    boundaries = {"txn": 0, "carry": 0, "anchor": 0}
    usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
    # cumulative debits/credits for the footer oracle (footer totals are
    # cumulative-to-date — verified against real reads 2026-09-14)
    cum = {"debits": Decimal("0"), "credits": Decimal("0")}
    cum_broken = False

    def _merge_usage(stats: dict) -> None:
        if not stats:
            return
        usage["calls"] += 1
        for k in ("prompt_tokens", "completion_tokens"):
            usage[k] += int(stats.get(k) or 0)
        c = stats.get("cost")
        if isinstance(c, (int, float)):
            usage["cost"] = round(usage["cost"] + c, 6)

    _merge_usage(bank_usage)
    prev_closing = None
    prev_footer = None
    page_nos: list[tuple[int, int | None]] = []
    prev_page_no: int | None = None
    recoveries: list[dict] = []
    page_rereads: list[dict] = []
    fail_streak = 0
    abort_reason = ""
    for pg, img in enumerate(pages, start=1):
        progress((pg - 1) / len(pages), f"قراءة صفحة {pg}/{len(pages)}…")
        if usage["cost"] > MAX_UI_COST_USD:
            abort_reason = (f"أُوقف التشغيل عند الصفحة {pg}: تجاوز سقف الكلفة "
                            f"(${MAX_UI_COST_USD:.2f} لهذا المسار).")
            break
        st: dict = {}
        try:
            raw_rows = read_rows_vlm(img, stats=st)
        except Exception:
            # one flaky page must never kill the whole run (transient VLM /
            # JSON glitches) — record it, keep going, report it honestly.
            # But EVERY page failing is a provider outage, not bad luck: four
            # attempts with 10/20/40s backoff ≈ 70s per page, so 629 pages
            # would spin ~12 hours and produce nothing. Five in a row stops it.
            failed_pages.append(pg)
            cum_broken = True  # cumulative footer chain is now unverifiable
            fail_streak += 1
            if fail_streak >= FAIL_STREAK_LIMIT:
                abort_reason = (f"أُوقف التشغيل عند الصفحة {pg}: "
                                f"{fail_streak} إخفاقات قراءة متتالية "
                                f"(انقطاع المزوّد؟) — والصفحات المقروءة محفوظة "
                                f"في هذه النتيجة.")
                break
            continue
        fail_streak = 0
        _merge_usage(st)
        rows = chain_derive(raw_rows, prev_balance=prev_closing)
        page_no = st.get("page_no")
        page_nos.append((pg, page_no))
        gap_missing: list[int] = []
        if (isinstance(page_no, int) and isinstance(prev_page_no, int)
                and page_no > prev_page_no + 1):
            # قفزة في الترقيم المطبوع ⇒ الأوراق بينهما غائبة من المسح، ودلتا
            # الإطار التالية تقيس حركاتها لا خطأً في هذه الصفحة.
            gap_missing = list(range(prev_page_no + 1, page_no))
        # مرساة حدّية غير محسومة؟ استدراك مقيد: إعادة قراءة موضعية تُقبل
        # فقط إذا أغلقت السلسلة (ما كشفه ص11 في السلايس).
        if pg > 1 and rows and rows[0].get("boundary") == "anchor":
            rst: dict = {}
            raw_rows, recovered = recover_anchor(
                raw_rows, prev_closing, img, pg, rst)
            _merge_usage(rst)
            if recovered is not None:
                rows = chain_derive(raw_rows, prev_balance=prev_closing)
                recoveries.append({"page": pg, "amount": str(recovered)})
        fst: dict = {}
        try:
            footer = read_footer(img, stats=fst)
        except Exception:
            footer = None
        _merge_usage(fst)
        # تحكيم الصفحة: انزياح عن الفوتر يُطلق قراءة جديدة واحدة، تُقبل فقط
        # إذا كانت بلا شكوك وتُطابق دلتا الفوتر (معزولة عن أي تلوث سابق).
        if (not gap_missing
                and page_diverged(rows, cum, prev_footer, footer, cum_broken)):
            pst: dict = {}
            fresh_raw, accepted, note = try_page_reread(
                img, cum, prev_footer, footer, prev_closing, pst)
            _merge_usage(pst)
            if accepted and fresh_raw is not None:
                raw_rows = fresh_raw
                rows = chain_derive(raw_rows, prev_balance=prev_closing)
                if pg > 1 and rows and rows[0].get("boundary") == "anchor":
                    rst2: dict = {}
                    raw_rows, rec = recover_anchor(
                        raw_rows, prev_closing, img, pg, rst2)
                    _merge_usage(rst2)
                    if rec is not None:
                        rows = chain_derive(raw_rows,
                                            prev_balance=prev_closing)
                        recoveries.append({"page": pg, "amount": str(rec)})
                page_rereads.append({"page": pg, "note": note})
        if pg > 1 and rows:
            b = rows[0].get("boundary")
            if b in boundaries:
                boundaries[b] += 1
        era_pages[pg] = [t for r in rows
                         for t in (r.get("raw_movement"), r.get("raw_balance"))
                         if t]
        page_dates[pg] = [r.get("date") for r in rows]
        chk = check_page_footer(rows, footer, prior=cum, skip=cum_broken)
        # أساس العرض = دلتا الصفحة متى توفّرت (تعزل الصفحة عن أي تلوث سابق).
        if delta_checkable(prev_footer, footer):
            dchk = delta_status(rows, prev_footer, footer)
            if dchk["status"] != "unchecked":
                chk = {**chk, **dchk, "basis": "delta"}
        elif chk.get("status") == "mismatch":
            chk = {**chk, "status": "unchecked"}
        if gap_missing and delta_checkable(prev_footer, footer):
            chk = {**chk, "status": "gap", "basis": "delta",
                   "missing_sheets": gap_missing}
        if chk.get("own"):
            cum["debits"] += chk["own"]["debits"]
            cum["credits"] += chk["own"]["credits"]
        footer_checks.append({"page": pg, **chk})
        prev_footer = footer
        prev_page_no = page_no
        for r in rows:
            if r["balance"] is None:
                continue
            if r["opening"]:
                all_rows.append({"page": pg, "kind": "opening",
                                 "balance": r["balance"], "movement": None,
                                 "side": "", "ok": True,
                                 "desc": r.get("desc"), "date": r.get("date")})
            else:
                all_rows.append({"page": pg, "kind": "txn",
                                 "balance": r["balance"],
                                 "movement": r["derived_movement"],
                                 "printed_mv": r["movement"],
                                 "side": r["side"], "ok": r["ok"],
                                 "desc": r.get("desc"), "date": r.get("date")})
            prev_closing = r["balance"]

    annotate_types(all_rows)
    filled_dates = fill_missing_dates(all_rows)
    rows_view = _rows_df(all_rows)

    progress(0.95, "بناء الفهرس…")
    STATE["rows"] = all_rows
    STATE["chunks"] = chunk_rows(
        [{**r, "row_no": i + 1} for i, r in enumerate(all_rows)])
    STATE["store"] = build_index(STATE["chunks"])
    STATE["footer_checks"] = footer_checks
    # أحكام الصفحة بلغة واحدة تُقرأ في كل سطح: الجدول والتصدير والأسئلة
    STATE["verdicts"] = verdicts_from_checks(footer_checks)
    STATE["usage"] = usage
    STATE["boundary_recoveries"] = recoveries
    STATE["page_rereads"] = page_rereads
    STATE["page_numbers"] = check_page_numbers(page_nos)
    era_fp = fingerprint_pages(era_pages)
    order = check_order(page_dates)
    STATE["era"] = era_fp
    STATE["order"] = order
    n_ok = sum(1 for r in all_rows if r["ok"])
    n_susp = len(all_rows) - n_ok
    last_bal = next((r["balance"] for r in reversed(all_rows)
                     if r["balance"] is not None), None)
    if not all_rows:
        raise gr.Error("تعذرت قراءة الكشف — انقطاع مؤقت من خدمة القراءة. أعد المحاولة.")
    n_pages = len(pages)
    if n_pages == 1:
        pages_ar = "صفحة واحدة"
    elif n_pages == 2:
        pages_ar = "صفحتين"
    elif 3 <= n_pages <= 10:
        pages_ar = f"{n_pages} صفحات"
    else:
        pages_ar = f"{n_pages} صفحة"
    if failed_pages:
        base = (f"⚠ تمّت قراءة {n_pages - len(failed_pages)} من {n_pages} صفحة "
                f"(تعذرت: {failed_pages}) — جاهز للسؤال عن المقروء")
    else:
        base = (f"✅ تمّت قراءة {pages_ar} وبناء الفهرس — "
                f"جاهز للسؤال والجواب")
    f_ok = [c for c in footer_checks if c["status"] == "ok"]
    f_bad = [c for c in footer_checks if c["status"] == "mismatch"]
    f_gap = [c for c in footer_checks if c["status"] == "gap"]
    f_absent = [c for c in footer_checks if c["status"] == "absent"]
    f_unchecked = [c for c in footer_checks if c["status"] == "unchecked"]
    # صفحات لا يمكن الحكم عليها وحدها: مجموعها بين إطارين مقروءين هو الدليل.
    # (الدليل تراكمي من بداية الكشف — انظر statement_qa.group_check)
    f_group: list[int] = []
    if f_absent or f_unchecked:
        try:
            from statement_qa.group_check import from_checks

            ok_pages = {c["page"] for c in f_ok}
            f_group = [p for p in from_checks(footer_checks, all_rows)
                       if p not in ok_pages]   # a page is counted once
            STATE["group_verified"] = f_group
            won = set(f_group)
            f_absent = [c for c in f_absent if c["page"] not in won]
            f_unchecked = [c for c in f_unchecked if c["page"] not in won]
        except Exception:  # noqa: BLE001 — a report must never break the read
            f_group = []
    f_possible = len(f_ok) + len(f_bad) + len(f_group)
    # Two numbers, because one number hid the truth (audit P1-2): the
    # denominator used to be ok+mismatch alone, so a file with four frameless
    # pages and two scan gaps still read «621/621 مطابق» and never named them.
    # ACCURACY says how the checked pages did; COVERAGE says how much of the
    # file was checked — and every remaining class is named in Arabic.
    if f_possible:
        seg_f = (f"تحقق الفوتر: {len(f_ok)}/{f_possible} مطابق (دقة)، "
                 f"وتغطية {f_possible}/{n_pages}")
        if f_bad:
            seg_f = ("⚠ " + seg_f + " — صفحات غير مطابقة: "
                     + "، ".join(str(c["page"]) for c in f_bad))
            if any(c.get("is_paradox") for c in f_bad):
                seg_f += " (نمط زيغ ×100)"
        if f_group:
            seg_f += (" — مُوثّق بالمجموع بين إطارين مقروءين: "
                      + "، ".join(str(p) for p in f_group))
        for label, group in (("فجوة مسح", f_gap), ("بلا إطار مطبوع", f_absent),
                             ("غير قابلة للتحقق", f_unchecked)):
            if group:
                seg_f += (f" — {label}: "
                          + "، ".join(str(c["page"]) for c in group))
    else:
        seg_f = "تقرير الفوتر: تعذرت قراءة الإطارات — لا حكم على أي صفحة"
    _verdicts = STATE.get("verdicts") or {}
    _suspect_pages = sorted({r["page"] for r in all_rows if not r.get("ok")})
    segs = [base, seg_f,
            summarize_era_ar(era_fp,
                             format_effects(_verdicts, _suspect_pages)),
            summarize_order_ar(order, boundaries),
            summarize_page_numbers(check_page_numbers(page_nos))]
    if abort_reason:
        segs.insert(0, "⛔ " + abort_reason)
    if filled_dates:
        segs.append(f"تواريخ مُستكملة: {filled_dates}* "
                    f"(لا تاريخ مطبوع في سطرها — سُدّت من الصف السابق)")
    if recoveries:
        segs.append("استُدرك حدّ الصفحة: "
                    + "، ".join(f"ص{r['page']} ({r['amount']})"
                                for r in recoveries))
    if page_rereads:
        segs.append("أُعيدت قراءة صفحة (مُتحقق): "
                    + "، ".join(f"ص{r['page']}" for r in page_rereads))
    summary = " • ".join(segs)
    return (summary, rows_view,
            _kpi_html(len(all_rows), n_ok, n_susp, last_bal), pages, "")


def prepare_ask(question: str, history):
    """Phase 1 (instant): the question appears in the chat immediately and the
    input clears; the heavy answering runs in the chained phase 2 — the owner
    asked for the text to move at once, not after the countdown."""
    history = list(history or [])
    q = (question or "").strip()
    STATE["pending_q"] = q
    if not q:
        return history, ""
    history.append({"role": "user", "content": q})
    return history, ""


_ARG_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_REF_RE = re.compile(
    r"صفحة\s*([٠-٩0-9]+)[^\d٠-٩]{0,14}?صف(?:وف)?\s*([٠-٩0-9]+)"
    r"(?:\s*[–\-—]\s*([٠-٩0-9]+))?")
_BARE_REF_RE = re.compile(
    r"(?:^|[^\d٠-٩])صف(?:وف)?\s*([٠-٩0-9]+)(?:\s*[–\-—]\s*([٠-٩0-9]+))?")


def _answer_refs(answer: str) -> list[tuple[int | None, int, int]]:
    """Citations inside the answer text: (page|None, first_row, last_row)."""
    return render_answer_refs(answer)


def _rows_for_refs(refs, cap: int = 60) -> pd.DataFrame:
    rows = STATE.get("rows") or []
    return pd.DataFrame(render_rows_for_refs(
        rows, refs, cap, STATE.get("verdicts") or {}))


def _evidence_rows(answer: str, sources) -> pd.DataFrame:
    """FALLBACK evidence only (no tool trace — prose answers): rows the ANSWER
    cites, else the retrieval pages. Trace-first lives in ask_followup."""
    refs = _answer_refs(answer)
    if refs:
        df = _rows_for_refs(refs)
        if not df.empty:
            return df
    if not STATE.get("rows"):
        return pd.DataFrame()
    frames, seen = [], set()
    for h in sources:
        if h["page"] in seen:
            continue
        seen.add(h["page"])
        frames.append(STATE_rows_to_df(h))
        if len(frames) == 2:
            break
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


_EVIDENCE_CAP = 150


def _n_rows_ar(n: int) -> str:
    if n == 1:
        return "صف واحد"
    if n == 2:
        return "صفَّان"
    if 3 <= n <= 10:
        return f"{n} صفوف"
    return f"{n} صفاً"


def _note_update(text: str):
    return gr.update(value=text, visible=bool(text))


def _hide_note():
    return gr.update(value="", visible=False)


def _evidence_from_numbers(nos: list[int]) -> tuple[pd.DataFrame, str]:
    """Rows by their GLOBAL statement numbers — the SAME numbers the tools
    cite and the main table shows, so # stays identical across surfaces."""
    rows = STATE.get("rows") or []
    pairs = [(i, rows[i - 1]) for i in nos if 1 <= i <= len(rows)]
    if not pairs:
        return pd.DataFrame(), ""
    note = f"◽ {_n_rows_ar(len(pairs))} دخلت في حساب الجواب."
    if len(pairs) > _EVIDENCE_CAP:
        note = (f" عُرضت أول {_EVIDENCE_CAP} من أصل "
                f"{_n_rows_ar(len(pairs))} دخلت في حساب الجواب.")
        pairs = pairs[:_EVIDENCE_CAP]
    return (pd.DataFrame([_row_record(i, r) for i, r in pairs]), note)


def ask_followup(history):
    """Phase 2: answer STATE['pending_q'] and append the reply to the chat.

    Evidence panel = the rows the TOOLS actually selected (execution trace),
    not the examples the answer prose happens to quote (owner report: a
    13-row sum showed only its 3 quoted examples; a compound question
    evidenced only its second segment).
    """
    history = list(history or [])
    q = STATE.pop("pending_q", "")
    if not q:
        return gr.skip(), gr.skip(), gr.skip(), gr.skip()
    if "store" not in STATE:
        history.append({"role": "assistant",
                        "content": "ارفع الكشف في تبويب «قراءة وتحقق» أولاً."})
        return history, "", pd.DataFrame(), _hide_note()
    from statement_qa.qa import answer_question

    res = answer_question(STATE["store"], q, rows=STATE.get("rows"),
                          chunks=STATE.get("chunks"))
    rows_now = STATE.get("rows") or []
    page_of = {i + 1: r.get("page") for i, r in enumerate(rows_now)}
    verdicts = STATE.get("verdicts") or {}
    history.append({"role": "assistant",
                    "content": render_answer_text(res, page_of, verdicts)})
    sources_md = "\n".join(
        f"- {s['chunk_id']} (صفحة {s['page']}، صفوف {s['row_start']}–{s['row_end']})"
        for s in res.sources)
    mode = render_evidence_mode(res)
    if mode == "none":
        # Tools failed: the panel is emptied ON PURPOSE. Filling it from the
        # model's own citations puts confident evidence under an answer that
        # was never computed (audit P2-10).
        return (history, sources_md, pd.DataFrame(),
                _note_update("⛔ لا أدلة: تعذّرت الأدوات — هذا الجواب لم "
                             "يُحسَب من الكشف (أُفرغت اللوحة عمداً)."))
    if mode == "tools":
        df, note = _evidence_from_numbers(res.used_row_nos)
        return history, sources_md, df, _note_update(note)
    return (history, sources_md,
            _evidence_rows(res.answer, res.sources), _hide_note())


def STATE_rows_to_df(hit):
    """One page's rows with GLOBAL # — same numbers the tools cite and the
    main table shows (real النوع + مدين/دائن split via the shared builder)."""
    rows = STATE.get("rows") or []
    pairs = [(i, r) for i, r in enumerate(rows, start=1)
             if r["page"] == hit["page"]]
    return pd.DataFrame([_row_record(i, r) for i, r in pairs])


ABOUT = """# عن المشروع

**المعمارية:** ثلاث طبقات —
1. **قراءة:** مسح ضوئي → نسخ حرفي بالأرقام الهندية (VLM) → تطبيع حتمي للأعداد
2. **تحقق:** كل حركة مشتقة حسابياً من فرق الأرصدة — **السلسلة الرصيدية هي الحَكَم**، والصفوف الشاذة تُعلَّم لا تُخفى — و**أوراكل الفوتر**: إجماليات كل صفحة المطبوعة (مدين/دائن/الرصيد) تُطابَق آلياً مع مجموع السلسلة، فهو الحارس الخارجي ضد انزياح موحّد يمرّ «نظيف السلسلة»
3. **فهم:** استرجاع عربي (FAISS + e5) + **أدوات حتمية** (LangChain) — النموذج يستدعي ويصوغ، ولا يحسب أبداً

**النطاق الحالي — بصدق:** كشوف **مصرف الراجحي** فقط · العيّنة التجريبية 10 صفحات، والكشف المرجعي الممسوح 629: **621 صفحة مطابقة بإطارها المطبوع + 5 موثّقة بالمجموع بين إطارين + 2 فجوة مسح نقصها مقيس + 1 غير محسومة** — أي أن **كل صفحة محسوبة**، بلا ادعاء تغطية كاملة قبل اجتياز البوابات.

**قاعدة الخصوصية:** القراءة تعمل عبر خدمة سحابية (VLM) — لا ترفع كشفاً حقيقياً إلا إذا قبلت بمعالجته على السحابة. العرض العام يعمل بفيّكسترة **اصطناعية** فقط: لا تستخدم السطح العام لبياناتك الحقيقية.

**الإصدار:** دفتر الأستاذ — ورق دافئ، حبر زمردي، إبر نحاسية، وختم التدقيق.
"""

with gr.Blocks(title="مُدقّق كشوف الراجحي") as demo:
    gr.HTML(HERO)
    with gr.Tabs():
        with gr.Tab("١. قراءة وتحقق"):
            with gr.Row():
                with gr.Column(scale=1, min_width=340):
                    pdf_in = gr.File(label="كشف PDF (عينة تجريبية موصى بها)",
                                     file_types=[".pdf"], elem_id="file-panel")
                    btn = gr.Button("قراءة الكشف وبناء الفهرس", variant="primary",
                                    interactive=False)
                    gr.Markdown(
                        "*نسخة تجريبية: كشوف الراجحي فقط · العيّنة قيد التوسع. "
                        "تُقرأ الصفحات عبر خدمة سحابية — لا ترفع كشفاً حقيقياً "
                        "إلا إن قبلت معالجته سحابياً، ولا ترفعه إلى سطح عام.*",
                        rtl=True)
                    ticker = gr.Markdown("في انتظار الكشف… ارفع ملفاً ثم ابدأ القراءة.",
                                         rtl=True, elem_classes=["ticker"])
                with gr.Column(scale=2, min_width=420):
                    kpi = gr.HTML("")
            with gr.Row():
                filter_box = gr.Textbox(
                    label="فلترة الجدول (يُنسَخ ما يُعرَض فقط)",
                    placeholder="كلمة من الوصف، أو: تحويل · سحب · مدين · دائن · مشبوه · رقم صفحة…",
                    rtl=True, scale=8)
                filter_clear = gr.Button("مسح الفلتر", scale=1)
            table = gr.Dataframe(label="الجدول المُستخرج (بالسلسلة الرصيدية)",
                                 interactive=False, elem_classes=["ledger-table"])
            filter_box.input(filter_rows, inputs=filter_box, outputs=table,
                             api_name="filter_rows")
            filter_box.change(filter_rows, inputs=filter_box, outputs=table)
            filter_clear.click(lambda: ("", filter_rows("")),
                               outputs=[filter_box, table])
            with gr.Accordion("صفحات الكشف (معاينة بصرية)", open=False):
                gallery = gr.Gallery(columns=5, show_label=False)
            pdf_in.change(lambda f: gr.update(interactive=bool(f)),
                          inputs=pdf_in, outputs=btn)
            btn.click(process_pdf, inputs=pdf_in,
                      outputs=[ticker, table, kpi, gallery, filter_box],
                      show_progress_on=[ticker])
        with gr.Tab("٢. سؤال وجواب"):
            with gr.Row():
                with gr.Column(scale=3, min_width=380):
                    chat = gr.Chatbot(
                        label="محادثة التحقق", rtl=True, height=460,
                        elem_id="chat-surface",
                        placeholder="اسأل عن أي مبلغ أو مجموع أو عدد أو رصيد — "
                                    "يُحسب بالأدوات ثم يُصاغ لك.")
                    with gr.Row():
                        q = gr.Textbox(label="سؤالك بالعربية",
                                       placeholder="مثال: كم مجموع السحوبات في الكشف؟",
                                       rtl=True, scale=6)
                        ask = gr.Button("اسأل", variant="primary", scale=1)
                with gr.Column(scale=2, min_width=320):
                    with gr.Accordion("الصفوف التي بُني عليها الجواب", open=True):
                        raw_note = gr.Markdown(visible=False)
                        raw = gr.Dataframe(interactive=False,
                                           elem_id="evidence-table")
                    # Internal retrieval bookkeeping (chunk IDs) — kept for
                    # development diagnostics only, collapsed out of the way.
                    with gr.Accordion("تفاصيل تقنية (قطع الاسترجاع)", open=False):
                        src = gr.Markdown(rtl=True)
            ask.click(prepare_ask, inputs=[q, chat], outputs=[chat, q],
                      show_progress="hidden", api_name="ask_question"
                      ).then(ask_followup, inputs=[chat],
                             outputs=[chat, src, raw, raw_note],
                             show_progress_on=[chat])
            q.submit(prepare_ask, inputs=[q, chat], outputs=[chat, q],
                     show_progress="hidden"
                     ).then(ask_followup, inputs=[chat],
                            outputs=[chat, src, raw, raw_note],
                            show_progress_on=[chat])
        with gr.Tab("٣. عن المشروع"):
            gr.Markdown(ABOUT, rtl=True)

if __name__ == "__main__":
    demo.launch(theme=THEME, css=RTL_CSS, head=HEAD)
