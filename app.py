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

import tempfile
from pathlib import Path

import gradio as gr
import pandas as pd
from pdf2image import convert_from_path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from statement_qa.chunking import chunk_rows
from statement_qa.retriever import build_index
from statement_qa.vlm_reader import chain_derive, read_rows_vlm

STATE = {}

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
.seal { position: absolute; top: 20px; inset-inline-end: 24px; width: 98px; height: 98px;
        opacity: .95; }

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
.ticker.block { border: 1px dashed #C9BFA6; border-radius: 10px; }
.ticker.prose { border: none !important; padding: 0 !important; background: transparent; }
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
      <textPath href="#sealArc" startOffset="50%" text-anchor="middle">السلسلة الرصيدية · حَكَم لا يخطئ</textPath>
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


def _pages_to_pngs(pdf_path: str, dpi: int = 200):
    outdir = tempfile.mkdtemp(prefix="rajhi_pages_")
    paths = convert_from_path(pdf_path, dpi=dpi)
    out = []
    for i, img in enumerate(paths, start=1):
        p = Path(outdir) / f"pg-{i:02d}.png"
        img.save(p)
        out.append(str(p))
    return out


def process_pdf(pdf_path: str, progress=gr.Progress()):
    """Tab 1 handler: read all pages, chain-audit, build chunks+index.

    Cross-page continuity: each page receives the previous page's closing
    balance. A page whose FIRST row is a real transaction (delta == printed
    amount) keeps its movement — scan boundaries never swallow operations.
    """
    if not pdf_path:
        raise gr.Error("ارفع ملف PDF أولاً ثم اضغط «قراءة الكشف».")
    pages = _pages_to_pngs(pdf_path)
    all_rows = []
    prev_closing = None
    for pg, img in enumerate(pages, start=1):
        progress((pg - 1) / len(pages), f"قراءة صفحة {pg}/{len(pages)}…")
        rows = chain_derive(read_rows_vlm(img), prev_balance=prev_closing)
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

    rows_view = pd.DataFrame([
        {"الصفحة": r["page"],
         "النوع": "افتتاحي" if r["kind"] == "opening" else "حركة",
         "الوصف": (r.get("desc") or "—"),
         "المبلغ": _money(r["movement"]),
         "الاتجاه": {"debit": "مدين (سحب)", "credit": "دائن (إيداع)"
                     }.get(r["side"], "—"),
         "الرصيد": _money(r["balance"]),
         "الحالة": "✓" if r["ok"] else "⚠ مشبوه"}
        for r in all_rows
    ])

    progress(0.95, "بناء الفهرس…")
    STATE["rows"] = all_rows
    STATE["chunks"] = chunk_rows(
        [{**r, "row_no": i + 1} for i, r in enumerate(all_rows)])
    STATE["store"] = build_index(STATE["chunks"])
    n_ok = sum(1 for r in all_rows if r["ok"])
    n_susp = len(all_rows) - n_ok
    last_bal = next((r["balance"] for r in reversed(all_rows)
                     if r["balance"] is not None), None)
    summary = (f"✅ قراءة {len(pages)} صفحة → {len(all_rows)} صف "
               f"({n_ok} نظيف السلسلة، {n_susp} مشبوه) — "
               f"جاهز للسؤال والجواب")
    return summary, rows_view, _kpi_html(len(all_rows), n_ok, n_susp, last_bal), pages


def ask_question(question: str, history):
    """Tab 2 handler: append (question, answer) to the chat surface."""
    history = list(history or [])
    if not question or not question.strip():
        return history, "", pd.DataFrame(), ""
    if "store" not in STATE:
        history += [{"role": "user", "content": question},
                    {"role": "assistant",
                     "content": "ارفع الكشف في تبويب «قراءة وتحقق» أولاً."}]
        return history, "", pd.DataFrame(), ""
    from statement_qa.qa import answer_question

    res = answer_question(STATE["store"], question, rows=STATE.get("rows"))
    history += [{"role": "user", "content": question},
                {"role": "assistant", "content": res.answer}]
    sources_md = "\n".join(
        f"- {s['chunk_id']} (صفحة {s['page']}، صفوف {s['row_start']}–{s['row_end']})"
        for s in res.sources)
    raw_table = pd.concat([
        STATE_rows_to_df(h) for h in res.sources[:2]
    ], ignore_index=True) if STATE.get("rows") else pd.DataFrame()
    return history, sources_md, raw_table, ""


def STATE_rows_to_df(hit):
    rows = [r for r in STATE["rows"]
            if r["page"] == hit["page"]]
    return pd.DataFrame([
        {"الصفحة": r["page"],
         "المبلغ": _money(r["movement"]),
         "الرصيد": _money(r["balance"]),
         "الاتجاه": {"debit": "مدين (سحب)", "credit": "دائن (إيداع)"}.get(r["side"], "—"),
         "الوصف": (r.get("desc") or "—")}
        for r in rows
    ])


ABOUT = """# عن المشروع

**المعمارية:** ثلاث طبقات —
1. **قراءة:** مسح ضوئي → نسخ حرفي بالأرقام الهندية (VLM) → تطبيع حتمي للأعداد
2. **تحقق:** كل حركة مشتقة حسابياً من فرق الأرصدة — **السلسلة الرصيدية هي الحَكَم**، والصفوف الشاذة تُعلَّم لا تُخفى
3. **فهم:** استرجاع عربي (FAISS + e5) + **أدوات حتمية** (LangChain) — النموذج يستدعي ويصوغ، ولا يحسب أبداً

**قاعدة خصوصية:** لا ترفع كشوفاً حقيقية إلا إذا قبلت بمعالجتها على السحابة —
العرض العام يستخدم كشفاً اصطناعياً.

**الإصدار:** دفتر الأستاذ — ورق دافئ، حبر زمردي، إبر نحاسية، وختم التدقيق.
"""

with gr.Blocks(title="مُدقّق كشوف الراجحي") as demo:
    gr.HTML(HERO)
    with gr.Tabs():
        with gr.Tab("١. قراءة وتحقق"):
            with gr.Row():
                with gr.Column(scale=1, min_width=340):
                    pdf_in = gr.File(label="كشف PDF (عينة تجريبية موصى بها)",
                                     file_types=[".pdf"])
                    btn = gr.Button("قراءة الكشف وبناء الفهرس", variant="primary",
                                    interactive=False)
                    ticker = gr.Markdown("في انتظار الكشف… ارفع ملفاً ثم ابدأ القراءة.",
                                         rtl=True, elem_classes=["ticker"])
                with gr.Column(scale=2, min_width=420):
                    kpi = gr.HTML("")
            table = gr.Dataframe(label="الجدول المُستخرج (بالسلسلة الرصيدية)",
                                 interactive=False, elem_classes=["ledger-table"],
                                 show_search="search")
            with gr.Accordion("صفحات الكشف (معاينة بصرية)", open=False):
                gallery = gr.Gallery(columns=5, show_label=False)
            pdf_in.change(lambda f: gr.update(interactive=bool(f)),
                          inputs=pdf_in, outputs=btn)
            btn.click(process_pdf, inputs=pdf_in,
                      outputs=[ticker, table, kpi, gallery])
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
                    src = gr.Markdown(label="المصادر (قطع الاسترجاع)", rtl=True)
                    with gr.Accordion("الصفوف الخام (من الجدول الحتمي)", open=False):
                        raw = gr.Dataframe(interactive=False)
            ask.click(ask_question, inputs=[q, chat],
                      outputs=[chat, src, raw, q])
            q.submit(ask_question, inputs=[q, chat],
                     outputs=[chat, src, raw, q])
        with gr.Tab("٣. عن المشروع"):
            gr.Markdown(ABOUT, rtl=True)

if __name__ == "__main__":
    demo.launch(theme=THEME, css=RTL_CSS, head=HEAD)
