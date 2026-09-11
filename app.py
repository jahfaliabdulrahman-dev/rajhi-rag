"""Arabic RTL Gradio app — 3 tabs (نقطة دخول Space).

Tab 1 قراءة وتحقق: PDF upload → page renders → VLM+chain rows → table +
suspect flags. No LLM answers here; deterministic provenance only.
Tab 2 سؤال وجواب: FAISS retrieval + strict-prompt answer with sources.
Tab 3 عن المشروع: architecture + links.
"""

from __future__ import annotations

import json
import tempfile
import time
from decimal import Decimal
from pathlib import Path

import gradio as gr
import pandas as pd
from pdf2image import convert_from_path

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from statement_qa.chunking import chunk_rows
from statement_qa.retriever import build_index, retrieve
from statement_qa.vlm_reader import chain_derive, read_rows_vlm

STATE = {}


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
    """Tab 1 handler: read all pages, chain-audit, build chunks+index."""
    if not pdf_path:
        raise gr.Error("ارفع ملف PDF أولاً")
    pages = _pages_to_pngs(pdf_path)
    all_rows = []
    prev_closing = None
    for pg, img in enumerate(pages, start=1):
        progress((pg - 1) / len(pages), f"قراءة صفحة {pg}/{len(pages)}…")
        rows = chain_derive(read_rows_vlm(img))
        for i, r in enumerate(rows, start=1):
            if r["balance"] is None:
                continue
            if r["opening"]:
                all_rows.append({"page": pg, "kind": "opening",
                                 "balance": r["balance"], "movement": None,
                                 "side": "", "ok": True})
            else:
                all_rows.append({"page": pg, "kind": "txn",
                                 "balance": r["balance"],
                                 "movement": r["derived_movement"],
                                 "printed_mv": r["movement"],
                                 "side": r["side"], "ok": r["ok"]})
            prev_closing = r["balance"]

    rows_view = pd.DataFrame([
        {"الصفحة": r["page"],
         "النوع": "افتتاحي" if r["kind"] == "opening" else "حركة",
         "المبلغ": float(r["movement"]) if r["movement"] is not None else "",
         "الاتجاه": {"debit": "مدين (سحب)", "credit": "دائن (إيداع)"
                     }.get(r["side"], "—"),
         "الرصيد": float(r["balance"]),
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
        return "اكتب سؤالاً أولاً", "", ""
    if "store" not in STATE:
        return "ارفع الكشف في تبويب «قراءة وتحقق» أولاً", "", ""
    res_hits = retrieve(STATE["store"], question, k=4)
    from statement_qa.qa import answer_question

    res = answer_question(STATE["store"], question)
    sources_md = "\n".join(
        f"- {h['chunk_id']} (صفحة {h['page']}، صفوف {h['row_start']}–{h['row_end']})"
        for h in res_hits)
    raw_table = pd.concat([
        STATE_rows_to_df(h) for h in res_hits[:2]
    ], ignore_index=True) if STATE.get("rows") else pd.DataFrame()
    return res.answer, sources_md, raw_table


def STATE_rows_to_df(hit):
    rows = [r for r in STATE["rows"]
            if r["page"] == hit["page"]]
    return pd.DataFrame([
        {"الصفحة": r["page"], "المبلغ": float(r["movement"]) if r["movement"] else "",
         "الرصيد": float(r["balance"]), "الاتجاه": r["side"] or "—"}
        for r in rows
    ])


ABOUT = """# سؤال وجواب على كشف حساب الراجحي 🏦

**المعمارية:** طبقات ثلاث —
1. **قراءة:** مسح → VLM (نسخ حرفي بالأرقام الهندية) + **السلسلة الرصيدية حَكَم**
2. **تحقق:** كل حركة مشتقة حسابياً من فرق الأرصدة (لا يُحسب من النص)
3. **فهم:** RAG عربي — إجابة من القطع حصراً بمصدرها، و"غير موجود في الكشف" عند غياب الدليل

**قاعدة خصوصية:** لا ترفع كشوفاً حقيقية إلا إذا قبلت بمعالجتها على السحابة —
العرض العام يستخدم كشفاً اصطناعياً.
"""

with gr.Blocks(title="سؤال وجواب على كشف الراجحي", css="footer {direction:ltr}") as demo:
    gr.Markdown("# 🏦 سؤال وجواب على كشف الراجحي (RAG عربي)")
    with gr.Tabs():
        with gr.Tab("١. قراءة وتحقق"):
            pdf_in = gr.File(label="ارفع كشف PDF (عينة تجريبية موصى بها)",
                             file_types=[".pdf"])
            btn = gr.Button("قراءة الكشف وبناء الفهرس", variant="primary")
            summary = gr.Markdown()
            table = gr.Dataframe(label="الجدول المُستخرج (بالسلسلة الرصيدية)",
                                 interactive=False)
            btn.click(process_pdf, inputs=pdf_in, outputs=[summary, table])
        with gr.Tab("٢. سؤال وجواب"):
            q = gr.Textbox(label="سؤالك بالعربية", placeholder="مثال: كم آخر رصيد في الكشف؟")
            ask = gr.Button("اسأل", variant="primary")
            ans = gr.Markdown(label="الجواب")
            with gr.Row():
                src = gr.Markdown(label="المصادر")
            raw = gr.Dataframe(label="الصفوف الخام (من الجدول الحتمي)", interactive=False)
            ask.click(ask_question, inputs=q, outputs=[ans, src, raw])
        with gr.Tab("٣. عن المشروع"):
            gr.Markdown(ABOUT)

if __name__ == "__main__":
    demo.launch()
