"""Arabic RTL Gradio app — 3 tabs (نقطة دخول Space).

Tab 1 قراءة وتحقق: PDF upload → page renders → VLM+chain rows → table +
suspect flags. No LLM answers here; deterministic provenance only.
Tab 2 سؤال وجواب: FAISS retrieval + LangChain agent with DETERMINISTIC tools
(sum/count/extremes/page summaries) — the model never computes, it calls.
Tab 3 عن المشروع: architecture + links.

Design layer (verified against gradio 6.27 — see the gradio-design skill):
- Arabic RTL 5-layer recipe (container direction, native rtl flags, block
  flips, upload-badge anchor, LTR footer)
- Soft/teal theme + IBM Plex Sans Arabic with explicit weights
- theme/css passed to launch() — Gradio 6 canonical placement
"""

from __future__ import annotations

import tempfile
from decimal import Decimal
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

RTL_CSS = """
.gradio-container { direction: rtl; }
/* Components with no native rtl flag expose dir="ltr" block shells —
   flip them so labels and toolbars sit on the right */
.gradio-container .block[dir="ltr"] { direction: rtl; }
/* File-upload badge is absolutely positioned — swap its anchor side */
.gradio-container label.float { left: auto !important; right: 6px !important; }
/* Gradio footer chrome is Latin — keep it LTR inside an RTL app */
footer { direction: ltr; }
"""

ARABIC_FONT = gr.themes.GoogleFont("IBM Plex Sans Arabic", weights=(400, 500, 600, 700))

THEME = gr.themes.Soft(
    primary_hue="teal",
    neutral_hue="slate",
    radius_size="md",
    font=ARABIC_FONT,
)

def _money(v) -> str:
    """Decimal/None -> fixed 2dp display so halalas are always visible."""
    return f"{v:,.2f}" if v is not None else ""

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
    summary = (f"✅ قراءة {len(pages)} صفحة → {len(all_rows)} صف "
               f"({n_ok} نظيف السلسلة، {len(all_rows)-n_ok} مشبوه) — "
               f"جاهز للسؤال والجواب")
    return summary, rows_view

def ask_question(question: str):
    if not question.strip():
        return "اكتب سؤالاً أولاً", "", pd.DataFrame()
    if "store" not in STATE:
        return "ارفع الكشف في تبويب «قراءة وتحقق» أولاً", "", pd.DataFrame()
    from statement_qa.qa import answer_question

    res = answer_question(STATE["store"], question, rows=STATE.get("rows"))
    sources_md = "\n".join(
        f"- {s['chunk_id']} (صفحة {s['page']}، صفوف {s['row_start']}–{s['row_end']})"
        for s in res.sources)
    raw_table = pd.concat([
        STATE_rows_to_df(h) for h in res.sources[:2]
    ], ignore_index=True) if STATE.get("rows") else pd.DataFrame()
    return res.answer, sources_md, raw_table

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

ABOUT = """# سؤال وجواب على كشف حساب الراجحي 🏦

**المعمارية:** طبقات ثلاث —
1. **قراءة:** مسح → VLM (نسخ حرفي بالأرقام الهندية) + **السلسلة الرصيدية حَكَم**
2. **تحقق:** كل حركة مشتقة حسابياً من فرق الأرصدة (لا يُحسب من النص)
3. **فهم:** RAG عربي + **أدوات حتمية** — النموذج يستدعي أدوات (جمع/عدد/قصوى) ولا يحسب بنفسه

**قاعدة خصوصية:** لا ترفع كشوفاً حقيقية إلا إذا قبلت بمعالجتها على السحابة —
العرض العام يستخدم كشفاً اصطناعياً.
"""

with gr.Blocks(title="سؤال وجواب على كشف الراجحي") as demo:
    gr.Markdown("# 🏦 سؤال وجواب على كشف الراجحي (RAG عربي)", rtl=True)
    with gr.Tabs():
        with gr.Tab("١. قراءة وتحقق"):
            pdf_in = gr.File(label="ارفع كشف PDF (عينة تجريبية موصى بها)",
                             file_types=[".pdf"])
            btn = gr.Button("قراءة الكشف وبناء الفهرس", variant="primary",
                            interactive=False)
            summary = gr.Markdown(rtl=True)
            table = gr.Dataframe(label="الجدول المُستخرج (بالسلسلة الرصيدية)",
                                 interactive=False)
            # gate the primary action on the required input (no dead-end clicks)
            pdf_in.change(lambda f: gr.update(interactive=bool(f)),
                          inputs=pdf_in, outputs=btn)
            btn.click(process_pdf, inputs=pdf_in, outputs=[summary, table])
        with gr.Tab("٢. سؤال وجواب"):
            q = gr.Textbox(label="سؤالك بالعربية", placeholder="مثال: كم مجموع السحوبات في الكشف؟",
                           rtl=True)
            ask = gr.Button("اسأل", variant="primary")
            ans = gr.Markdown(label="الجواب", rtl=True)
            with gr.Row():
                src = gr.Markdown(label="المصادر", rtl=True)
            raw = gr.Dataframe(label="الصفوف الخام (من الجدول الحتمي)", interactive=False)
            ask.click(ask_question, inputs=q, outputs=[ans, src, raw])
        with gr.Tab("٣. عن المشروع"):
            gr.Markdown(ABOUT, rtl=True)

if __name__ == "__main__":
    demo.launch(theme=THEME, css=RTL_CSS)
