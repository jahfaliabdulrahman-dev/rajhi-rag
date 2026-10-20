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

import json
import os
import re
import tempfile
from decimal import Decimal
from pathlib import Path

import gradio as gr
import numpy as np
import pandas as pd
from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from statement_qa.chunking import chunk_rows
# **وعقدُ الصفوف من موضعه الواحد (قرارُ المالك 2026-10-07 · الخيار (أ) · مراجعة ٩٦):** الدالّةُ نفسُها
# التي يناديها سطرُ الأوامر — فلا يبني العقدَ مساران يفترقان صامتين.
from statement_qa.contract_rows import build_page_rows  # noqa: F401
from statement_qa.classify import annotate_types
from statement_qa.qa import scope_text as _scope_text_of      # **صيغةُ النطاق في موضعٍ واحد (R93-10)**
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
    format_effects,
    verdicts_from_checks,
)
from statement_qa.code_hash import code_hash as _code_hash
from statement_qa.page_footers import printed_footers_from
from statement_qa.footer_oracle import (
    check_page_footer, delta_checkable, delta_status, page_diverged,
    page_totals, read_footer, try_page_reread,
)
from statement_qa.desc_reader import (
    continuation_for, merge_descriptions, read_page_descriptions,
    summarize_ar as summarize_desc_ar,
)
from statement_qa.intake import (
    blocked_message_ar, inspect_locally, plan, summary_ar as summarize_intake_ar,
)
from statement_qa.job_lock import JobBusyError, job_lock
from statement_qa import ledger as _ledger
from statement_qa import ledger_ui as _ledger_ui
from statement_qa.row_bands import analyze_page
from statement_qa.ordering import (
    adjacency, check_order, check_page_numbers, decide_order, footer_order,
    summarize_ar as summarize_order_ar,
    summarize_footer_order, summarize_page_numbers,
)

STATE = {}

# **بياناتُ المستخدم خارج المستودع (R130 · قرارُ المالك):** الدفترُ والمحادثةُ والملفّاتُ في مجلّد
# بيانات المستخدم وحده؛ والمستودعُ يُقرأ ويُنشر ولا يحمل بياناتِ كشف. والمسارُ يُقرأ من
# `statement_qa.ledger.data_home()` (متغيّرُ بيئةٍ للتشغيل المعزول، ثمّ مجلّدُ التطبيق النظاميّ).
DATA_HOME = _ledger.data_home()

# قفل «مهمة واحدة» — نافذتان متزامنتان كانتا تخلطان النتائج والسجلات.
LOCK_PATH = DATA_HOME / "job.lock"

# ————— بصمةُ الكود (R74-3 · مراجعة ٧٤ · أُوصي بها المدقّق قبل البروفة) —————
# **العلّةُ التي وُلدت منها:** الفحصُ الشامل يقيس **العمليةَ الجارية** لا الشجرة، وقد قاس فعلًا كودًا
# عمرُه اثنا عشر يومًا وأعلن نجاحًا (٢٠٢٦-٠٩-٢٦)، ثمّ قاس كودًا مُصلَحًا وأعلن فشلًا — والحكمُ واحد:
# **رقمٌ على كودٍ مجهول ليس رقمًا.** فتُكتب البصمةُ عند الإقلاع، ويقابلها `tools/qa_gate.py` بـ`HEAD`
# ويرفض النتيجةَ إن اختلفت (فشلٌ مُغلَق لا تحذير).
CODE_STAMP_PATH = Path(__file__).resolve().parent / "data" / ".app-code.json"


def _write_code_stamp() -> dict:
    """يُكتب مرّةً عند الإقلاع: `{pid, sha, code_hash, started}` — وبلا git أو بلا كتابةٍ يُعلَن `unknown` ولا يُخمَّن.

    **`code_hash` هو ما يحكم (R77-4):** بصمةُ محتوى `app.py` + `src/**` — فوثيقةٌ تهبط وحدَها لا تُبطل
    الختمَ ولا تُلزم بإعادة تشغيل. و`sha` يبقى **للعلم**.
    """
    import datetime as _dt
    import subprocess

    sha = "unknown"
    try:
        sha = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 — بصمةٌ غائبةٌ تُعلَن ولا تُسقط التطبيق
        pass
    try:
        code_hash = _code_hash()
    except Exception:  # noqa: BLE001 — قراءةُ ملفّاتٍ تعذّرت ⇒ `unknown` تُعلَن
        code_hash = "unknown"
    stamp = {"pid": os.getpid(), "sha": sha, "code_hash": code_hash,
             "started": _dt.datetime.now().isoformat(timespec="seconds")}
    try:
        CODE_STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
        CODE_STAMP_PATH.write_text(json.dumps(stamp, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return stamp


# **R78-1 (مراجعة ٧٨) — والكتابةُ عند الاستيراد كانت تُبطل البصمةَ من أصلها:** كانت `_write_code_stamp()`
# تُنادى هنا في مستوى الوحدة، فأيُّ مستورِدٍ لـ`app` **يُعيد كتابةَ البصمة بمعرّف عمليّته هو**؛ وخطوةُ
# الوحدة في `qa_gate --full` تستورد `app` **قبل** فحص النهاية-إلى-النهاية ⇒ الفحصُ يقرأ بصمةً كتبها من
# كود الشجرة بنفسه ⇒ **لا رفضَ لكودٍ قديم أبدًا** (البصمةُ كانت تُوقّع على نفسها).
# ⇒ **والكتابةُ الآن في إقلاع الخادم وحدَه** — انظر `__main__` في آخر الملفّ؛ والفحصُ يقابل `pid`
# البصمة بمستمع ٧٨٦٠ فلا تكفي بصمةٌ من عمليةٍ أخرى. والاسمُ يبقى معلنًا هنا (وهو غيرُ مستعملٍ اليوم)
# فيُقرأ العقدُ من موضعه: **الاستيرادُ لا يكتب بصمة.**
APP_CODE_STAMP: dict | None = None

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
    from statement_qa.money import money as _m   # **الموضعُ الواحد** (قِيس: كانت تسقط على نصّ)
    return _m(v)


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


def _row_iso(r: dict) -> str:
    """تاريخُ الصفّ الميلاديّ — `render.normalize_date` (لا قارئَ ثانٍ) وتُقبل الأقواسُ المطبوعة."""
    from statement_qa.contract_rows import normalize_date

    return normalize_date(r.get("date"))[0]


#: أعمدةُ الفلترة = أعمدةُ الجدول نفسُها (يُشتقّان من `render.row_record` لا من قائمةٍ ثانية).
FILTER_COLUMNS: tuple[str, ...] = ("كل الأعمدة", "#", "الصفحة", "التاريخ", "الوصف",
                                   "النوع", "مدين", "دائن", "الرصيد", "الحالة", "التحقق")


def filter_rows(column: str = "", value: str = "",
                date_from: str = "", date_to: str = "") -> pd.DataFrame:
    """فلترةُ الجدول **بعمودٍ مختار** (البند ٧) وبمدى تاريخٍ من/إلى (البند ٨) — خادميًّا.

    **العِلّة:** كان صندوقًا واحدًا يبحث في كلّ الأعمدة معًا، فطلبُ «النوع = سحب» يطابق أيضًا
    وصفًا فيه «سحب»؛ وصار العمودُ يُختار من قائمة، والقيمةُ تُطابَق فيه وحدَه. والصندوقُ القديم
    يبقى في القائمة باسم «كل الأعمدة» (سلوكُه السابق بالحرف). **والفلترةُ على السجلّ المعروض**
    (بعد التنسيق) لا على الصفّ الخام — فيُطابق ما تراه العين.
    **وحدُّ التاريخ المُعلَن:** صفٌّ بلا تاريخٍ مقروء يُستبعَد حين يُحدَّد مدى (لا يُخمَّن له تاريخ).
    **والجدولُ يُعاد مبنيًّا من النتيجة** فلا يُنسخ ما لم يُعرض (عطبُ النسخ الذي أُغلق قبل).
    """
    rows = STATE.get("rows") or []
    records = [(i, _row_record(i, r)) for i, r in enumerate(rows, start=1)]
    col = (column or "كل الأعمدة").strip()
    q = (value or "").strip()
    df_from = _date_arg(date_from)
    df_to = _date_arg(date_to)

    out = []
    for (i, rec), r in zip(records, rows):
        if df_from or df_to:
            iso = _row_iso(r)
            if not iso:
                continue
            if (df_from and iso < df_from) or (df_to and iso > df_to):
                continue
        if q:
            if col and col != "كل الأعمدة":
                cell = str(rec.get(col, ""))
                if q.lower() not in cell.lower():
                    continue
            else:
                hay = " ".join(str(v) for v in rec.values()).lower()
                if q.lower() not in hay and q.lower() not in hay.replace(",", ""):
                    continue
        out.append(rec)
    return pd.DataFrame(out)


def _date_arg(text: str) -> str:
    """تاريخُ فلترٍ من نصّ → ISO أو `""`؛ ونصٌّ غيرُ مفهوم يعني «لا فلترَ زمنيّ» (والحقلُ يعلن صيغته)."""
    from statement_qa.contract_rows import normalize_date

    return normalize_date(text)[0]


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


RENDER_DPI = 200      # مقاسُ الماسح المرجعي الذي عُويرت عليه بوابةُ الجودة (A4 ≈ 1654×2338)


class _PageImages(list):
    """صورُ الصفحات **مؤلَّمةً بعمر مهمّتها**: قائمةُ مساراتٍ تحمل `TemporaryDirectory` الذي تُنظَّف به.

    **العِلّة (R130-2 · خصوصيّة):** كان `mkdtemp` لصور كلّ قراءةٍ يبقى في مجلّد النظام إلى إعادة
    التشغيل (قِيس يوم الجلسة: ١٩٢٥ مجلّدًا · ٧٥٥MB). والآن المجلّدُ `TemporaryDirectory` **يُغلق في
    `finally`** بعد أن تُنسخ صورُ المعرض إلى حافظة Gradio بمكوّن المكتبة
    (`move_resource_to_block_cache`) — فلا منظّفَ يدويًّا ولا ملفًّا بعد المهمّة.
    والقائمةُ نفسُها تبقى متوافقةً مع الضوابط التي تستبدل `_pages_to_pngs` بقائمةٍ عاديّة (بلا `.close`).
    """

    def __init__(self, paths, tmp: "tempfile.TemporaryDirectory | None" = None):
        super().__init__(paths)
        self.tmp = tmp

    def close(self) -> None:
        if self.tmp is not None:
            self.tmp.cleanup()
            self.tmp = None


def _cache_path(component, path) -> str:
    """مخرجٌ في حافظة Gradio (مكوّنُ المكتبة) قبل حذف مجلّد العمل — تديرها `delete_cache` لا يدنا."""
    return component.move_resource_to_block_cache(str(path))


def _pages_to_pngs(pdf_path: str, dpi: int = RENDER_DPI):
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
    outdir = tempfile.TemporaryDirectory(prefix="rajhi_pages_")
    paths = convert_from_path(pdf_path, dpi=dpi)
    out = []
    for i, img in enumerate(paths, start=1):
        p = Path(outdir.name) / f"pg-{i:02d}.png"
        img.save(p)
        out.append(str(p))
    return _PageImages(out, outdir)


def _local_checks(pages: list[str]):
    """(gate_fn, kind_fn): طبقتا فحص ما قبل القراءة المجانيتان (`statement_qa.intake`).

    البوابةُ تُحمَّل مرّةً واحدة، **وفشلُ تحميلها يوقف التشغيل** بجملةٍ واضحة: تشغيلٌ بلا بوابة
    هو بالضبط ما يُراد منعه (درسُ `tools/scale_slice.py`: استيرادٌ أخفق بصمتٍ فمرّت صفحةٌ فارغة
    إلى استدعاءٍ مدفوع). ولم يُدفع شيءٌ بعد.
    """
    try:
        root = str(Path(__file__).resolve().parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from tools.page_gate import check_page, modal_page_size  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise gr.Error(f"تعذّر تحميل فحص جودة الصفحات ({type(e).__name__}) — "
                       f"لم تبدأ القراءة ولم يُدفع شيء.")
    modal = modal_page_size([{"size": list(Image.open(p).size)} for p in pages]) \
        if pages else None

    def gate_fn(p):
        return check_page(Path(p), modal_size=modal)

    def kind_fn(p):
        return analyze_page(np.asarray(Image.open(p).convert("L")), RENDER_DPI).kind

    return gate_fn, kind_fn


def _own_sums(order: list[int], raw_by_pg: dict[int, list]) -> dict[int, tuple]:
    """حركاتُ كلّ صفحةٍ (مدين، دائن) مشتقّةً بالسلسلة **على هذا الترتيب** — مجّانًا، لقياس التجاور."""
    own: dict[int, tuple] = {}
    prev = None
    for pg in order:
        if pg not in raw_by_pg:
            continue
        t = page_totals(chain_derive(raw_by_pg[pg], prev_balance=prev))
        own[pg] = (t["debits"], t["credits"])
        if t["balance"] is not None:
            prev = t["balance"]
    return own


def _page_descriptions(path: str, next_path: str | None, stats: dict):
    """(بياناتُ صفوف الصفحة من عمود البيان، هل لُصقت تكملة؟) — استدعاءٌ واحد (statement_qa.desc_reader)."""
    img = Image.open(path).convert("RGB")
    pb = analyze_page(np.asarray(img.convert("L")), RENDER_DPI)
    if not pb.bands:
        raise ValueError("لا صفوف في شكل الصفحة")
    cont = None
    if next_path:
        nimg = Image.open(next_path).convert("RGB")
        cont = continuation_for(pb, analyze_page(np.asarray(nimg.convert("L")), RENDER_DPI), nimg)
    return read_page_descriptions(img, pb, cont, stats), cont is not None


def _desc_pass(order: list[int], pages: list[str], all_rows: list[dict],
               pairs: dict, charge, over_budget) -> dict:
    """البيانُ لكلّ صفحة من عمود البيان، والأرقامُ لا تُمسّ.

    التكملةُ تُلصق بالصفّ الأخير **فقط** حين يُثبت الحسابُ أن الصفحةَ التالية في الترتيب الحقيقي
    هي الورقةُ التالية فعلًا (`adjacent`). وأيُّ فشلٍ يُبقي بيانَ قراءة الصفحة ويُسمّى — لا يُسقط التشغيل.
    """
    rep = {"merged": [], "stitched": 0, "failed": [], "unaligned": [], "skipped": []}
    for i, pg in enumerate(order):
        rows = [r for r in all_rows if r["page"] == pg]
        if not rows:
            continue                     # صفحةٌ لم تُقرأ أرقامُها: لا بيانَ يُدفع لها
        if over_budget():
            rep["skipped"] = [p for p in order[i:] if any(r["page"] == p for r in all_rows)]
            break
        nxt = order[i + 1] if i + 1 < len(order) else None
        nxt_path = pages[nxt - 1] if nxt and pairs.get((pg, nxt)) == "adjacent" else None
        st: dict = {}
        try:
            descs, stitched = _page_descriptions(pages[pg - 1], nxt_path, st)
        except Exception:  # noqa: BLE001
            rep["failed"].append(pg)
            continue
        finally:
            charge(st)
        if merge_descriptions(rows, descs):
            rep["merged"].append(pg)
            rep["stitched"] += int(stitched)
        else:
            rep["unaligned"].append(pg)
    return rep


def process_pdf(pdf_path: str, progress=gr.Progress()):
    """Tab 1 handler — single-job lock → read all pages → chain-audit →
    footer oracle + era/order checks → chunks+index → **قاعدةُ الكشف تُكتب تلقائيًّا**.

    Cross-page continuity: each page receives the previous page's closing
    balance. A page whose FIRST row is a real transaction (delta == printed
    amount) keeps its movement — scan boundaries never swallow operations.

    Guarded by the single-job lock (what-if delta #3): a second concurrent
    run gets a clear Arabic message instead of interleaving with this one.

    **وخانةُ «استبعاد الصفحات المرفوضة» أُزيلت (R130 · البند ١١):** لا قرارَ للعميل فيها — الصفحةُ
    المرفوضةُ تُستبعد **وتُسمّى** في رسالة النتيجة، وما عداها يُقرأ. والخانةُ كانت تُقرأ نقصًا وهي
    لا تقول ما وقع؛ والرسالةُ تقوله.
    """
    if not pdf_path:
        raise gr.Error("ارفع ملف PDF أولاً ثم اضغط «قراءة الكشف».")
    try:
        with job_lock(LOCK_PATH):
            return _process_pdf_locked(pdf_path, progress)
    except JobBusyError:
        raise gr.Error("يوجد تشغيل جارٍ الآن (نافذة أو طلب آخر) — "
                       "انتظر انتهاءه ثم أعد المحاولة.")


def _view_rows(contract: list[dict]) -> list[dict]:
    """**صفوفُ العرض/الأسئلة مشتقّةٌ من صفوف العقد — لا بناءٌ ثانٍ (F5 · مقعدُ البنية):**

    كانت تُبنى مستقلّةً عن القراءة نفسِها، فصار لتصنيف «حركة/افتتاح» و«حكم السلسلة» موضعان يزيغان
    (يُعدَّل أحدُهما ويبقى الآخر). والسطحان يبقيان مختلفَين بمفاتيحهما (`kind`/`ok`/`type` للعرض ·
    العقدُ بعشرين عمودًا للدفتر) — **لكنّ المعنى يُحسب مرّةً واحدةً في `build_page_rows`.**
    """
    out: list[dict] = []
    for c in contract:
        if c.get("balance") is None:      # سطرٌ بلا رصيد ليس حركةً في العرض أيضًا (كما كانت)
            continue
        opening = bool(c.get("opening"))
        out.append({"page": c["page"],
                    "kind": "opening" if opening else "txn",
                    "balance": c["balance"],
                    "movement": None if opening else c.get("derived_movement"),
                    "printed_mv": c.get("printed_movement"),
                    "side": c.get("side") or "",
                    "ok": c.get("chain_ok"),
                    "desc": c.get("desc"), "date": c.get("date")})
    return out


def _view_rows_from_contract(contract: list[dict]) -> list[dict]:
    """صفوفُ العرض/الأسئلة من **صفوف القاعدة** — `_view_rows` نفسُها مع ترجمة `pg`⇒`page`.

    **العِلّة (R130):** بعد إعادة تشغيل التطبيق لا حالةَ في الذاكرة؛ فإعادةُ بناء الأسطح من القاعدة
    تحتاج سطحَ العرض بلغته (`kind`/`ok`/`type`) — وهو **نفسُ الباني** المستعمل بعد القراءة، لا نسخةً
    ثانيةً منه. والترجمةُ الوحيدةُ `pg`⇒`page` (اسمُ العمود في القاعدة).
    """
    return _view_rows([{**r, "page": r.get("page", r.get("pg"))} for r in contract])


def _ledger_path_for(key: str | None = None) -> Path:
    """ملفُّ قاعدةِ الكشف الحاليّ — **في مجلّد بيانات المستخدم** لا في المستودع."""
    return _ledger_ui.ledger_file(DATA_HOME, key or _ledger_key())


def _ledger_write() -> dict:
    """**القراءةُ تكتب القاعدةَ عند انتهائها (R130 · الخيار ١)** — لا زرٍّ منفصل.

    تُكتب صفوفُ العقد (٢٢ عمودًا) وأحكامُ الصفحات وأرقامُ تذييلها المطبوعة. والنَّصُّ على صفوف
    **العقد** لا العرض: العرضُ بلا `row_no` فتسقط الكتابةُ (`IntegrityError` — درسُ الزرّ القديم).
    والفشلُ **يُعلَن ولا يُسقط القراءة**: القراءةُ تمّت، والقاعدةُ بياناتٌ مشتقّةٌ تُعاد.
    """
    rows = _ledger_rows()
    if not rows:
        return {"ok": False, "message": "لا صفوفَ لكتابة قاعدةٍ منها."}
    key = _ledger.statement_key(STATE.get("era"), _ledger.pages_of(rows))
    path = _ledger_ui.ledger_file(DATA_HOME, key)
    try:
        conn = _ledger.open_ledger(path)
        try:
            stats = _ledger.ingest(conn, rows, _ledger.pages_from_state(rows, STATE.get("footers") or {}))
        finally:
            conn.close()
    except _ledger.LedgerUnavailable as e:
        return {"ok": False, "key": key, "path": str(path), "message": f"تعذّرت كتابةُ القاعدة — {e}"}
    STATE["ledger_key"] = key
    _ledger_ui.active_set(DATA_HOME, key, STATE.get("source_name") or "")
    note = (f"قاعدةُ الكشف: **{stats['rows']}** صفًّا · **{stats['pages']}** صفحة · "
            f"**{stats.get('pruned_rows', 0)}** صفًّا قديمًا أُزيل")
    return {"ok": True, "key": key, "path": str(path), "stats": stats, "message": note}


def _load_from_ledger(key: str | None = None) -> bool:
    """يُعيد بناء أسطح السؤال من **القاعدة وحدها** — لتبقى بعد إغلاق التطبيق (قبولُ R130).

    يُنادى حين لا `store` في الحالة (بعد إعادة تشغيل) وقبل أيّ سؤال: الصفوفُ من `rows_verified`،
    والتذييلاتُ من `pages`، والقطعُ/الفهرسُ يُعاد بناؤهما من الصفوف نفسِها (بلا نموذجٍ مدفوع).
    وما لا قاعدةَ له يُعلَن بلا اختراع.
    """
    key = key or _ledger_key()
    path = _ledger_ui.ledger_file(DATA_HOME, key)
    try:
        conn = _ledger.read_ledger(path)
    except _ledger.LedgerUnavailable:
        return False
    try:
        contract = _ledger.read_rows(conn)
        footers = _ledger.read_footers(conn)
    finally:
        conn.close()
    if not contract:
        return False
    view = _view_rows_from_contract(contract)
    STATE["rows"] = view
    STATE["rows_contract"] = contract
    STATE["footers"] = footers
    # **وأحكامُ الصفحات تُستعاد من القاعدة** (يقرؤها عمودُ «التحقق» في الجدول) — لا تُترك فارغة.
    STATE["verdicts"] = {int(pg): (f or {}).get("verdict") or "unchecked"
                         for pg, f in footers.items()}
    STATE["printed_pages"] = {int(pg): (f or {}).get("printed_page")
                              for pg, f in footers.items()}
    # **وأرقامُ الصفوف من العقد لا من ترتيب العرض:** `_view_rows` تُسقِط ما لا رصيدَ له، فترقيمُ العرض
    # بالتسلسل يزيح كلَّ اقتباسٍ بعد أوّل صفٍّ مُسقَط — والاقتباسُ يُقرأ في الشاشة برقمه. والصفُّ
    # المطابقُ لعرضٍ هو عقدُه ذو الرصيد، بنفس الترتيب (والسطحان يبقيان مفترقَين: `row_no` لا يدخل العرض).
    _with_balance = [c for c in contract if c.get("balance") is not None]
    STATE["chunks"] = chunk_rows([{**r, "row_no": int(_with_balance[i].get("row_no") or i + 1)
                                   if i < len(_with_balance) else i + 1}
                                  for i, r in enumerate(view)])
    STATE["store"] = build_index(STATE["chunks"])
    STATE["n_pages"] = len({r["page"] for r in view})
    STATE["ledger_key"] = key
    return True


def _intake_outcome(intake, decision: dict) -> str:
    """**رسالةٌ بما حدث فعلًا** مكان خانة «استبعاد الصفحات المرفوضة» (البند ١١).

    كانت خانةً فارغةً افتراضًا تُقرأ نقصًا، ولا تقول ما وقع. والآن يقول السطرُ الحقيقةَ بعد الفحص:
    لم يُستبعد شيءٌ لأنّ كلّ الصفحات قُرئت، أو يسمّي المستبعَدَ بعدده وسببه — ويُذكر ما تُرك فارغًا.
    """
    skipped = list(decision.get("skipped") or [])
    blank = list(decision.get("blank") or [])
    if decision.get("blocked"):
        bits = []
        if skipped:
            bits.append(f"**{len(skipped)}** صفحةً مرفوضةً تحتاج إعادةَ تصوير ("
                        + "، ".join(f"ص{p}" for p in skipped[:8])
                        + (" …" if len(skipped) > 8 else "") + ")")
        if blank:
            bits.append(f"**{len(blank)}** ورقةً فارغة")
        return ("**لم تبدأ القراءة ولم يُدفع شيء** — " + " · ".join(bits) +
                ". أعد تصويرَها وارفع الملفَّ من جديد.") if bits else \
               "**لم تبدأ القراءة ولم يُدفع شيء.**"
    if not skipped and not blank:
        return "**لم يُستبعد شيء — قُرئت الصفحاتُ كلُّها.**"
    bits = []
    if skipped:
        bits.append(f"استُبعدت **{len(skipped)}** صفحةً مرفوضةً بلا قراءة "
                    f"({intake.reason(skipped[0]) if skipped else ''}): "
                    + "، ".join(f"ص{p}" for p in skipped[:8])
                    + (" …" if len(skipped) > 8 else ""))
    if blank:
        bits.append(f"وتُرك **{len(blank)}** ورقةً فارغةً بلا قراءة")
    return " · ".join(bits) + " — وما عداها قُرئ."


def _footer_delta_nonzero(now, prev) -> bool:
    """**هل يُظهر تذييلُ الصفحة حركاتٍ لها؟** الفرقُ بين إجمالياتها المتراكمة وإجمالياتِ سابقتها.

    تُستعمل لتمييز «قراءةٍ فاشلةٍ أرجعت مصفوفةً فارغة» من «صفحةٍ فارغةٍ حقًّا» (الصفحةُ الختامية مثلًا:
    سطورُها في مربّع الملخّص ولا حركةَ لها). والمقارنةُ على `FooterReading` أو `None`:
    تذييلٌ غيرُ مقروء ⇒ **لا حكم** (تُترك الصفحةُ بلا وسم، ولا يُخمَّن لها عطب).
    """
    if now is None:
        return False
    for f in ("debits", "credits"):
        a = getattr(now, f, None)
        b = getattr(prev, f, None) if prev is not None else Decimal("0")
        if a is None or b is None:
            continue
        if a != b:
            return True
    return False


def _close_pages(pages) -> list[str]:
    """ينسخ صورَ المعرض إلى حافظة Gradio **ثمّ يُغلق** مجلّدَ الصور المؤقّت (R130-2).

    والنسخُ قبل الإغلاق شرطٌ: `move_resource_to_block_cache` تقرأ الملفّ الآن؛ وبعده يصير المجلّدُ
    مُنظَّفًا. والقائمةُ العاديّة (ضابطٌ يستبدل `_pages_to_pngs`) تمرّ بلا إغلاق.
    """
    out = []
    for p in pages:
        try:
            out.append(_cache_path(gallery, p))
        except Exception:                    # noqa: BLE001 — صورةٌ تعذّرت لا تُسقط القراءة
            out.append(p)
    close = getattr(pages, "close", None)
    if callable(close):
        close()
    return out


def _process_pdf_locked(pdf_path: str, progress):
    # **ومسحُ ذاكرة المحادثة هنا لا يتوقّف على ترتيب مستمعَي الزرّ** (تصحيحُ مقعد البنية 2026-10-08):
    # الحالةُ **قبل استبدالها** في كلِّ ترتيبٍ ⇒ يُمسح خيطُ الكشف المُغادَر فعلًا؛ ومع مسحِ
    # `_reset_qa_surfaces` عند النقر تُغطّى كلُّ سيناريوهات العودة (كشفٌ جديد · إعادةُ قراءة ·
    # رجوعٌ إلى قديم) **بالترتيب لا بالتُّخمَّن**.
    from statement_qa.qa import clear_conversation

    old_key = _ledger_key()
    old_path = _ledger_ui.ledger_file(DATA_HOME, old_key) if old_key else None
    clear_conversation(old_key, memory_path=old_path if old_path and old_path.exists() else None)
    pages = _pages_to_pngs(pdf_path)

    # فحصُ ما قبل القراءة (statement_qa.intake): مجانيٌّ ويسبق **أيَّ** استدعاءٍ مدفوع — حتى
    # فحصَ المصرف. صفحةٌ مرفوضة ⇒ **تُستبعد وتُسمّى**، وما عداها يُقرأ (البند ١١: لا خانةَ قرار).
    progress(0.0, "فحص الصفحات قبل القراءة…")
    gate_fn, kind_fn = _local_checks(pages)
    intake = inspect_locally(pages, gate_fn, kind_fn)
    decision = plan(intake, True)
    intake_note = _intake_outcome(intake, decision)
    if decision["blocked"]:
        STATE.clear()   # لا تُجيب الأسئلةُ عن ملفٍّ سابقٍ بعد رفعِ ملفٍّ لم يُقرأ
        STATE["intake"] = {"gate": intake.gate, "kinds": intake.kinds, **decision}
        return (blocked_message_ar(intake), _rows_df([]), "", _close_pages(pages),
                "كل الأعمدة", "", "", "",
                _ledger_ui.status_text(DATA_HOME, None, 0), intake_note)

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
    # **ونسخةُ العقد (`ledger.COLUMNS` · ٢٢ عمودًا) — للسطح الذي يستهلكها وحدَه:** زرُّ التنزيل
    # (الدفتر ثمّ الإكسل). أما `all_rows` فهي سطحُ العرض/الأسئلة بلغته (`kind`/`ok`/`type`) — سطحان
    # لاستهلاكين مختلفين، **والعقدُ له بانٍ واحد** (`statement_qa.contract_rows.build_page_rows`)
    # يناديه سطرُ الأوامر أيضًا (قرارُ المالك 2026-10-07 · الخيار (أ) · مراجعة ٩٦).
    rows_contract: list[dict] = []
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

    def over_cap() -> bool:
        return usage["cost"] > MAX_UI_COST_USD

    # ١) التذييلاتُ أولًا (قصاصةٌ صغيرةٌ لكلّ صفحة): مفتاحُ الترتيب (ordering.footer_order)، وهي
    # نفسُها تُستعمل في تحكيم الصفحة أدناه — فلا يُدفع التذييلُ مرّتين. **وللمرور حدّاه كالقراءة**
    # (مراجعة ٧٠ · R70-2): سقفُ الكلفة قبل كلّ استدعاء، ووقفٌ بعد FAIL_STREAK_LIMIT إخفاقاتٍ متتالية —
    # كان يسبقهما ويبتلع أخطاءه، فانقطاعُ المزوّد يُدفع ثمنُه صفحةً صفحة قبل أن يوقفه شيء.
    footers: dict = {}
    footer_failed: list[int] = []
    n_proc = len(decision["process"])
    for i, pg in enumerate(decision["process"]):
        if over_cap():
            abort_reason = (f"أُوقف التشغيل قبل قراءة الصفوف عند إطار الصفحة {pg}: تجاوز سقف "
                            f"الكلفة (${MAX_UI_COST_USD:.2f} لهذا المسار).")
            break
        progress(0.05 * i / n_proc, f"قراءة إطار الإجماليات {i + 1}/{n_proc}…")
        fst: dict = {}
        try:
            footers[pg] = read_footer(pages[pg - 1], stats=fst)
            fail_streak = 0
        except Exception:
            footers[pg] = None
            footer_failed.append(pg)
            fail_streak += 1
        finally:
            _merge_usage(fst)
        if fail_streak >= FAIL_STREAK_LIMIT:
            abort_reason = (f"أُوقف التشغيل قبل قراءة الصفوف عند إطار الصفحة {pg}: "
                            f"{fail_streak} إخفاقات متتالية في قراءة الإطارات (انقطاع المزوّد؟).")
            break
    if abort_reason:
        STATE.clear()   # لا تُجيب الأسئلةُ عن ملفٍّ سابق
        raise gr.Error("⛔ " + abort_reason + " لم يُقرأ صفٌّ واحد.")

    # ٢) الصفوفُ بترتيب الملف — والترتيبُ يُقرَّر بعدها، لأن شاهدَيه الثانيين (الرقمُ المطبوع والتجاورُ
    # المُثبت حسابًا) لا يوجدان إلا بعد القراءة (مراجعة ٧٠ · R70-1). عددُ الاستدعاءات لا يتغيّر.
    raw_by_pg: dict[int, list] = {}
    page_no_by_pg: dict[int, int | None] = {}
    attempted: list[int] = []
    pages_without_rows: list[int] = []
    fail_streak = 0
    for i, pg in enumerate(decision["process"]):
        progress(0.05 + 0.8 * i / n_proc, f"قراءة صفحة {pg} ({i + 1}/{n_proc})…")
        if over_cap():
            abort_reason = (f"أُوقف التشغيل عند الصفحة {pg}: تجاوز سقف الكلفة "
                            f"(${MAX_UI_COST_USD:.2f} لهذا المسار).")
            break
        attempted.append(pg)
        st: dict = {}
        try:
            raw_by_pg[pg] = read_rows_vlm(pages[pg - 1], stats=st)
            page_no_by_pg[pg] = st.get("page_no")
            fail_streak = 0
            # **وصفحةٌ بلا صفوفٍ ليست صفحةً فارغةً بالضرورة (قاسه قياسُ البروفة ٢٠٢٦-٠٩-٣٠):**
            # إجابةٌ صحيحةُ الشكل لكنها مصفوفةٌ فارغة تمرّ بلا استثناء ⇒ كانت صفحةٌ كاملةٌ تُفقد
            # صامتةً (الجدولُ ٩٤ صفًّا بدل ١٠٤، وإعادةُ قراءة الصفحة نفسِها أعادت صفوفَها العشرة).
            # فما دام تذييلُ الصفحة يُظهر حركاتٍ لها (دلتا الإجماليات المتراكمة عن السابقة) ⇒ تُسمّى.
            _prev_pg = decision["process"][i - 1] if i else None
            if not (raw_by_pg.get(pg) or []) and _footer_delta_nonzero(
                    footers.get(pg), footers.get(_prev_pg) if _prev_pg else None):
                pages_without_rows.append(pg)
        except Exception:
            # one flaky page must never kill the whole run (transient VLM /
            # JSON glitches) — record it, keep going, report it honestly.
            # But EVERY page failing is a provider outage, not bad luck: four
            # attempts with 10/20/40s backoff ≈ 70s per page, so 629 pages
            # would spin ~12 hours and produce nothing. Five in a row stops it.
            failed_pages.append(pg)
            fail_streak += 1
        finally:
            _merge_usage(st)
        if fail_streak >= FAIL_STREAK_LIMIT:
            abort_reason = (f"أُوقف التشغيل عند الصفحة {pg}: "
                            f"{fail_streak} إخفاقات قراءة متتالية "
                            f"(انقطاع المزوّد؟) — والصفحات المقروءة محفوظة "
                            f"في هذه النتيجة.")
            break

    # ٣) الترتيب: ترتيبُ التذييلات مرشَّح، لا يُطبَّق إلا بلا تناقضٍ ولا تكرار وبشاهدٍ ثانٍ لكلّ صفحةٍ ينقلها
    # (ordering.decide_order) — والشاهدان يُقاسان على الترتيب المرشَّح نفسه، مجّانًا.
    footer_tuples = {pg: (f.debits, f.credits) if f else None
                     for pg, f in footers.items() if pg in attempted}
    fo = footer_order(footer_tuples)
    printed_by_pg = {pg: n for pg, n in page_no_by_pg.items() if isinstance(n, int)}
    cand_pairs = adjacency(fo["order"], footer_tuples, _own_sums(fo["order"], raw_by_pg),
                           printed_by_pg)
    order_now, order_held = decide_order(attempted, fo, printed_by_pg, cand_pairs)

    # ٤) الاشتقاقُ والتحكيمُ بالترتيب المقرَّر — والاستدراكاتُ المدفوعة تحترم السقف أيضًا.
    own_by_pg: dict[int, tuple] = {}
    for i, pg in enumerate(order_now):
        img = pages[pg - 1]
        progress(0.85 + 0.08 * i / max(1, len(order_now)), f"تحقّق الصفحة {pg}…")
        if pg not in raw_by_pg:
            cum_broken = True  # cumulative footer chain is now unverifiable
            continue
        raw_rows = raw_by_pg[pg]
        rows = chain_derive(raw_rows, prev_balance=prev_closing)
        page_no = page_no_by_pg.get(pg)
        page_nos.append((pg, page_no))
        gap_missing: list[int] = []
        if (isinstance(page_no, int) and isinstance(prev_page_no, int)
                and page_no > prev_page_no + 1):
            # قفزة في الترقيم المطبوع ⇒ الأوراق بينهما غائبة من المسح، ودلتا
            # الإطار التالية تقيس حركاتها لا خطأً في هذه الصفحة.
            gap_missing = list(range(prev_page_no + 1, page_no))
        # مرساة حدّية غير محسومة؟ استدراك مقيد: إعادة قراءة موضعية تُقبل
        # فقط إذا أغلقت السلسلة (ما كشفه ص11 في السلايس).
        if i > 0 and rows and rows[0].get("boundary") == "anchor" and not over_cap():
            rst: dict = {}
            raw_rows, recovered = recover_anchor(
                raw_rows, prev_closing, img, pg, rst)
            _merge_usage(rst)
            if recovered is not None:
                rows = chain_derive(raw_rows, prev_balance=prev_closing)
                recoveries.append({"page": pg, "amount": str(recovered)})
        footer = footers.get(pg)
        # تحكيم الصفحة: انزياح عن الفوتر يُطلق قراءة جديدة واحدة، تُقبل فقط
        # إذا كانت بلا شكوك وتُطابق دلتا الفوتر (معزولة عن أي تلوث سابق).
        if (not gap_missing and not over_cap()
                and page_diverged(rows, cum, prev_footer, footer, cum_broken)):
            pst: dict = {}
            fresh_raw, accepted, note = try_page_reread(
                img, cum, prev_footer, footer, prev_closing, pst)
            _merge_usage(pst)
            if accepted and fresh_raw is not None:
                raw_rows = fresh_raw
                rows = chain_derive(raw_rows, prev_balance=prev_closing)
                if i > 0 and rows and rows[0].get("boundary") == "anchor" and not over_cap():
                    rst2: dict = {}
                    raw_rows, rec = recover_anchor(
                        raw_rows, prev_closing, img, pg, rst2)
                    _merge_usage(rst2)
                    if rec is not None:
                        rows = chain_derive(raw_rows,
                                            prev_balance=prev_closing)
                        recoveries.append({"page": pg, "amount": str(rec)})
                page_rereads.append({"page": pg, "note": note})
        if i > 0 and rows:
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
        if chk.get("own"):
            own_by_pg[pg] = (chk["own"]["debits"], chk["own"]["credits"])
        prev_footer = footer
        prev_page_no = page_no
        # **والعقدُ يُبنى أوّلًا، ثمّ يُشتقّ العرضُ منه (F5):** ترتيبٌ واحدٌ للمعنى — والعقدُ هو ما
        # يقرؤه كاتبُ الإكسل والدفتر. (العلّةُ المقيسة: كانت ٩ حقولٍ من ٢٢ في موضع البناء ⇒ زرُّ
        # التنزيل لا يُنتج ملفًّا: `IntegrityError: NOT NULL constraint failed: rows_verified.row_no`
        # ثمّ `KeyError: None`.) والوسائطُ كما يحملها التطبيق: قراءتُه الخامّ (`raw_rows`) وأحكامُ
        # السلسلة (`rows` من `chain_derive`) وحكمُ الصفحة وأعلامُها ورقمُها المطبوع.
        page_contract = build_page_rows(
            pg, raw_rows, rows,
            {"footer": chk.get("status")},
            # **والتحكيمُ غيرُ معلومٍ هنا بإعلانٍ صريح (R96-2):** يُسجَّل في كاش التشغيل (`arbitrated_by`)
            # ويقرؤه مسارُ سطر الأوامر، فلا يعرفه التطبيق ⇒ فخليّةُ «مصدر الإثبات» لصفحةٍ محكَّمة تفرق
            # بين الملفّين. وهذا **صنفُ فرقِ مصدرِ إدخالٍ مُعلَن** كالكلفة والزمن اللذين لا يملكهما التطبيق،
            # لا انزياحُ عقد. (مقيس: لا تظهر على عيّنةٍ بلا تحكيم، وتظهر بـ«تحكيم موثَّق بمصدره».)
            {"recovered": any(x.get("page") == pg for x in recoveries),
             "reread": any(x.get("page") == pg for x in page_rereads)},
            page_no=page_no)
        rows_contract += page_contract
        all_rows += _view_rows(page_contract)
        # **و`prev_closing` كما كان:** آخرُ رصيدٍ مقروءٍ في الصفحة يقود سلسلةَ التالية — كان يُحدَّث
        # صفًّا صفًّا في حلقة العرض، ويُقرأ الآن من الصفوف نفسِها فلا يُفقد أثرُه.
        _last_bal = next((r["balance"] for r in reversed(rows) if r["balance"] is not None), None)
        if _last_bal is not None:
            prev_closing = _last_bal

    # التواريخُ أولًا: تُستعاد أحيانًا من نصّ بيان قراءة الصفحة، وبيانُ العمود بلا تاريخٍ عن قصد.
    filled_dates = fill_missing_dates(all_rows)
    progress(0.93, "قراءة البيان من عمود البيان…")
    pairs = adjacency(order_now,
                      {pg: (f.debits, f.credits) if f else None for pg, f in footers.items()},
                      own_by_pg, {pos: n for pos, n in page_nos if isinstance(n, int)})
    desc_rep = _desc_pass(order_now, pages, all_rows, pairs, _merge_usage,
                          lambda: usage["cost"] > MAX_UI_COST_USD)
    # والتصنيفُ بعد البيان الأصحّ.
    annotate_types(all_rows)
    rows_view = _rows_df(all_rows)

    progress(0.95, "بناء الفهرس…")
    STATE["rows"] = all_rows
    # **وسطحُ العقد يُكتب باسمه (لا يُخلط بسطح العرض):** يقرؤه زرُّ التنزيل وحده، فيبقى التحويلُ
    # في الدفتر على عقدٍ كامل — وهذا ما كان غائبًا فسقط الزرُّ.
    STATE["rows_contract"] = rows_contract
    # **نطاقُ الكشف يُكتب حيث يُعرَف (R93-1):** `_scope_text` يقرأ `n_pages` و`source_name`، ولم يكن
    # يكتبهما أحد ⇒ كان يقول للنموذج «0 صفحة» في **كلّ** سؤال، وهو نصٌّ كاذبٌ يبلغ التلقين. فيُكتبان
    # هنا من الملفّ المقروء نفسِه — لا من افتراضٍ، ولا من عددٍ ثابت.
    STATE["n_pages"] = len(pages)
    # **ولا سطرَ ولا مُساعدَ من الأداة المحذوفة (أغلقه مقعدُ المواصفة · SPEC-96-2):** كان هنا شرحٌ
    # بنصّ الحاضر («يحتاجها زرُّ التنزيل…») و`_page_no` الجاهزةُ لإعادة شبكها — بعد أن حُذف مفتاحُ
    # `read_pages` ومَن يناديه. فالسطرُ الذي يصف آليةً محذوفةً كنصّ حاضر يُعيد بناءَها، والمُساعدُ الذي
    # لا يناديه أحدٌ يُغري بذلك. حُذفا معًا، والشاهدُ على الإزالة وسببُها في موضعه أعلاه.
    # **ولا مفتاحَ حالةٍ لصفحاتٍ «بلا حركات» (حُذف بالقياس · الدعوى R95-1-a · تبنتها مراجعة ٩٦):** كان
    # يُبنى من عدّ الصفحات المقروءة ليُمرَّر إلى ناقل الإكسل، وقِيس أنّه **لا يُحرّك الخليّةَ المُسلَّمة**
    # (٤ = ٤ = ٤، وهو عددُ ملفّ سطر الأوامر) — فالعدُّ من أحكام الدفتر، **وأخطرُ منه** أنّه كان يُلصق
    # وسمَ «لا حركات» على ما يُسمّيه التطبيقُ نفسُه «قراءةٌ فاشلة». فبقي المعنى في مصدره الواحد.
    STATE["source_name"] = Path(pdf_path).name
    # **وخريطةُ الأرقام المطبوعة (R93-4):** يُمرّرها زرُّ التنزيل إلى ناقل الإكسل، فيُكتب رقمُ
    # الصفحة المطبوع من **مصدره** (قراءةُ الورقة) لا من خريطةٍ محلّيّةٍ ولا `None`.
    STATE["printed_pages"] = dict(page_no_by_pg)
    STATE["chunks"] = chunk_rows(
        [{**r, "row_no": i + 1} for i, r in enumerate(all_rows)])
    STATE["store"] = build_index(STATE["chunks"])
    # **التذييلاتُ المطبوعةُ بصيغةٍ واحدة (R77):** تُبنى من القراءات والأحكام في موضعٍ واحد —
    # `statement_qa.page_footers` — فيرثها مسارُ القراءة (هنا) ومسارُ القياس معًا، ولا نسخةَ ثانيةَ
    # تزيغ بصمت. الأرقامُ كما ظهرت في الورقة، وحكمُها معها.
    printed_footers = printed_footers_from(footers, footer_checks, money=_money)
    STATE["footer_checks"] = footer_checks
    STATE["footers"] = printed_footers
    # أحكام الصفحة بلغة واحدة تُقرأ في كل سطح: الجدول والتصدير والأسئلة
    STATE["verdicts"] = verdicts_from_checks(footer_checks)
    STATE["usage"] = usage
    STATE["boundary_recoveries"] = recoveries
    STATE["page_rereads"] = page_rereads
    STATE["page_numbers"] = check_page_numbers(sorted(page_nos))   # بمواضع الملف
    era_fp = fingerprint_pages(era_pages)
    order = check_order(page_dates)
    STATE["era"] = era_fp
    STATE["order"] = order
    STATE["footer_order"] = fo
    STATE["order_held"] = order_held
    STATE["footer_failed"] = footer_failed
    STATE["desc_pass"] = desc_rep
    STATE["intake"] = {"gate": intake.gate, "kinds": intake.kinds, **decision}
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
        _first_in_order = order_now[0] if order_now else None

        def _page_label(c: dict, label: str) -> str:
            """**والصفحةُ تُسمّى بسببها لا برقمها وحدَه (R76-2 · مراجعة ٧٦):** «غير قابلة للتحقق» تُقرأ
            فيُستنتج سببُها — وقد استنتجتُه خطأً فعلًا (رجّحتُ تخطّيًا بعد إعادة قراءةٍ لا يقع في الكود).
            فيُذكر الأساسُ صريحًا: لا مرجعَ سابق (أوّلُ صفحة) · أو لا مكوّنَ قابلَ للمقارنة (الأساسُ
            الفارق) · أو سلسلةٌ منكسرةٌ بتخطّي (صفحةٌ سابقةٌ لم تُقرأ صفوفُها).
            """
            if label != "غير قابلة للتحقق":
                return str(c["page"])
            if c.get("basis") == "delta":
                return f"{c['page']} (لا مكوّنَ قابلَ للمقارنة)"
            if c["page"] == _first_in_order:
                return f"{c['page']} (أوّلُ صفحة — لا مرجعَ سابق)"
            return f"{c['page']} (سلسلةٌ منكسرة/تخطّي)"

        for label, group in (("فجوة مسح", f_gap), ("بلا إطار مطبوع", f_absent),
                             ("غير قابلة للتحقق", f_unchecked)):
            if group:
                seg_f += (f" — {label}: "
                          + "، ".join(_page_label(c, label) for c in group))
    else:
        seg_f = "تقرير الفوتر: تعذرت قراءة الإطارات — لا حكم على أي صفحة"
    _verdicts = STATE.get("verdicts") or {}
    _suspect_pages = sorted({r["page"] for r in all_rows if not r.get("ok")})
    # **الكلفةُ في الملخّص (R74-4 · مراجعة ٧٤):** كانت تُحسب في `usage` ولا تُعرَض في أيّ مكان ⇒ تعذّر
    # تسجيل كلفة تشغيلٍ مدفوع (ووقع فعلًا في بروفة ٢٠٢٦-٠٩-٣٠). وتُوضع **قبل** سطر الفوتر كي لا تدخل
    # النافذةَ التي تقرؤها البوّابة (`تحقق الفوتر` ← أوّل `•`)، فلا تُشوّش حكمَ الفوتر.
    _cost_seg = (f"الكلفة: ${usage['cost']:.4f} · نداءات {usage['calls']}"
                 if usage.get("calls") else "الكلفة: بلا نداءاتٍ مُسجَّلة")
    segs = [base, _cost_seg, seg_f,
            summarize_era_ar(era_fp,
                             format_effects(_verdicts, _suspect_pages)),
            summarize_order_ar(order, boundaries),
            summarize_footer_order(fo, applied=order_held is None and order_now != attempted,
                                   held=order_held),
            summarize_page_numbers(check_page_numbers(sorted(page_nos))),
            summarize_intake_ar(intake, decision["skipped"]),
            summarize_desc_ar(desc_rep, sum(1 for pg in order_now
                                            if any(r["page"] == pg for r in all_rows)))]
    if abort_reason:
        segs.insert(0, "⛔ " + abort_reason)
    if footer_failed:
        segs.append("⚠ تعذّرت قراءةُ إطار الإجماليات (بلا تحكيمٍ لها): "
                    + "، ".join(f"ص{p}" for p in footer_failed[:8])
                    + (" …" if len(footer_failed) > 8 else ""))
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
    if pages_without_rows:
        segs.append("⚠ صفحةٌ بلا صفوفٍ وتذييلُها يُظهر حركات (قراءةٌ فاشلة لا صفحةٌ فارغة): "
                    + "، ".join(f"ص{p}" for p in pages_without_rows))
    summary = " • ".join(segs)
    # **وقاعدةُ الكشف تُكتب هنا — عند انتهاء المعالجة، لا بزرّ (R130 · الخيار ١).**
    # والفشلُ يُعلَن في سطر الحالة ولا يُسقط قراءةً تمّت (القاعدةُ بياناتٌ مشتقّةٌ تُعاد).
    written = _ledger_write()
    ledger_status = _ledger_ui.status_text(DATA_HOME, _ledger_key(), len(_ledger_rows()),
                                           _ledger.rows_without_page(_ledger_rows()))
    if not written.get("ok"):
        ledger_status = f"### دفترُ الكشف\n**{written.get('message') or 'تعذّرت الكتابة'}**"
    gallery_out = _close_pages(pages)
    return (summary, rows_view,
            _kpi_html(len(all_rows), n_ok, n_susp, last_bal), gallery_out,
            "كل الأعمدة", "", "", "", ledger_status, intake_note)


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


def _reset_qa_surfaces():
    """**كشفٌ جديد ⇒ لا سؤالَ من القديم (R93-2):** المحادثةُ صارت **مُدخَلًا** للنموذج (R92)، فبقاؤها
    يحمل سؤالَ الكشف السابق وجوابَه — بمبلغه واستشهاده («صفحة ٧») — إلى أسئلة الكشف الجديد، وهو الصنفُ
    نفسه الذي أُغلق قبل ٩٢: رقمٌ يُنسب إلى كشفٍ آخر.

    فتُمسح أربعةُ أسطحٍ ومعها **ذاكرةُ المحادثة نفسها** (قرار 98ب · شرط ٢): رسائلُ الخيط تُمحى
    (`clear_conversation`) — لا سطحُ العرض وحده. والمعرّفُ **بصمةُ الكشف الحاليّ** (`_ledger_key`) —
    **وما يضمن الخيطَ المُغادَر في كلِّ ترتيبات النقر** مسحٌ آخرُ في مدخل `_process_pdf_locked`
    حيث الحالةُ قبل استبدالها (تصحيحُ مقعد البنية 2026-10-08) ⇒ وكلُّ سيناريوهات العودة تبدأ
    محادثةً نظيفة **بالقياس لا بالتُّخمَّن**.
    **والمسحُ يقع عند النقر** لا بعد انتهاء القراءة (وهي دقائقُ مدفوعة) — فلا تبقى نافذةٌ يُسأل فيها
    عن القديم، ولا يُنتظر انتهاءُ مسارٍ قد يفشل.
    """
    from statement_qa.qa import clear_conversation

    key = _ledger_key()
    path = _ledger_ui.ledger_file(DATA_HOME, key) if key else None
    clear_conversation(key, memory_path=path if path and path.exists() else None)
    return [], "", pd.DataFrame(), _hide_note()


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


def _scope_n_pages(rows: list[dict]) -> int:
    """عددُ صفحات الكشف المُعلَن للوكيل: من الحالة، وإلّا من **صفحات الصفوف**، وإلّا **صفرٌ بمعنى «غيرُ معروف»**.

    **ولماذا لا يُنشر الصفرُ كما هو (R93-1):** الصفرُ هنا يُقرأ «كشفٌ بلا صفحات»، وهي حقيقةٌ كاذبةٌ تدخل
    تلقينَ الوكيل في كلّ سؤال — والحدُّ الذي يُسقط صنفًا بصمتٍ أسوأُ من توقّفٍ مسموع. فصفرٌ ⇒ يُسمّى
    الغيابُ في `_scope_text` صراحةً، ولمصدرٍ واحدٍ للعدّ يُستعمل `ledger.pages_of` (كما في الدفتر).
    """
    raw = STATE.get("pages")
    n = len(raw) if isinstance(raw, (list, tuple)) else (STATE.get("n_pages") or 0)
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 0
    return n if n > 0 else _ledger.pages_of(rows)


def _scope_text() -> str:
    """نطاقُ الكشف — يُشتقّ من الحالة **بلا افتراض مفتاح**: كلُّ قراءةٍ `.get` ⇒ لا `KeyError`.

    وهذا النطاقُ هو ما يُعلن الوكيلُ عملَه عليه، فسؤالٌ عن «الصفحة ٤» لا يُجاب من كشفٍ آخر.

    **والصيغةُ ليست هنا (R93-10):** هي في `statement_qa.qa.scope_text` — لأنّ أداةَ التقييم تُناديها
    أيضًا، والحزمةُ كانت تُقاس بنطاقٍ فارغٍ بينما التطبيقُ يرسل نصًّا كاملًا. فالواجهةُ تجمع المدخلاتِ
    من حالتها وحدَها، والصيغةُ واحدة.
    """
    rows = STATE.get("rows") or []
    return _scope_text_of(
        name=STATE.get("source_name") or STATE.get("pdf_name") or "",
        n_pages=_scope_n_pages(rows),
        n_rows=len(rows),
        kind=STATE.get("reader_mode") or "",
    )


def export_xlsx():
    """زرُّ التنزيل: **بنفس كاتب سطر الأوامر**، مَرندَرًا من دفترٍ يُكتب من الحالة — **والفرقُ
    المعروفُ محدودٌ ومُسمًّى** (كلفةُ الصفحة وزمنُها: لا يملكهما التطبيق؛ وصفوفُ دعم الجواب
    المبنيّةُ من مخبّآت الصفحات المحكَّمة) — وكلُّ فرقٍ خارج الأصناف المُعلَنة يُسقط البوّابة.

    **ولماذا لا بناءٌ مباشرٌ هنا:** طريقٌ ثانٍ يعني حكمين لملفٍّ واحد يفترقان صامتين. فالنواةُ
    `export_from_state` تكتب الدفترَ ثمّ تستدعي `to_xlsx.build(ledger_db=…)` — وهي المقابَلةُ خليّةً
    بخليّة مع مخرَج الـCLI في `tests/test_app_excel_button.py`.

    **والرفضُ يُعرَض ولا يُبتلع:** كاتبُ الإكسل يرفض التسليم عند اختلاف الاشتقاق أو دورِ التذييل
    (`to_xlsx.py:846`) — ورفضُه إشارةُ أمانةٍ، فيُقرأ نصًّا بدل أن يُخفى.
    """
    from statement_qa.export_from_state import export_xlsx_from_state

    # **ولا تبقى نسخةُ الكشف في مجلّدٍ مؤقّت (R93-8 · وأُغلق العمرُ كاملًا في R130-2):** كان كلُّ
    # نقرةٍ تترك في مجلّدٍ **دائم** `ledger.db` (كلُّ الصفوف) و`run/results/pg-*.json` (الصفوفَ
    # الخامّة) وملفَّ الإكسل — أي نسخةً كاملةً من الكشف مقابل كلّ نقرة. فصار البناءُ في
    # `TemporaryDirectory` **يُحذف بانتهاء النداء**، ويُنسخ **ملفُّ الإكسل وحدَه** إلى حافظة Gradio
    # (`move_resource_to_block_cache`) التي يديرها `delete_cache` — لا منظّفٌ يدويّ.
    with tempfile.TemporaryDirectory(prefix="rajhi_xlsx_") as work:
        out, msg = export_xlsx_from_state(
            STATE.get("rows_contract") or [], STATE.get("footers"),
            printed_pages=STATE.get("printed_pages"),
            out_dir=Path(work))
        if out is None:
            return None, _note_update(msg)
        kept = _cache_path(xlsx_file, out)     # نسخةٌ واحدةٌ في حافظة Gradio
    return str(kept), _note_update(msg + " · ونُظّف مجلّدُ العمل (لا نسخةَ صفوفٍ باقية)")


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
    # **والقاعدةُ تُعيد بناءَ الأسطح بعد إعادة التشغيل (R130):** بلا `store` في الذاكرة تُقرأ
    # الصفوفُ من القاعدة ويُبنى الفهرسُ منها — فالسؤالُ يُجاب ولو فرغت الذاكرة (شرطُ القبول).
    if "store" not in STATE and not _load_from_ledger():
        history.append({"role": "assistant",
                        "content": "ارفع الكشف في تبويب «قراءة وتحقق» أولاً."})
        return history, "", pd.DataFrame(), _hide_note()
    from statement_qa.qa import answer_question, remember

    key = _ledger_key()
    memory_path = _memory_path()
    ledger_path = _ledger_ui.ledger_file(DATA_HOME, key) if key else None
    if ledger_path is not None and not ledger_path.exists():
        ledger_path = None

    # **والذاكرةُ في مكوّنها (قرار 98ب · شرط ١ و٢):** السجلُّ **رسائلُ** خيطٍ في الحافظة بمعرّف
    # الكشف (`_ledger_key` = بصمةُ الكشف — ومصدرُها واحدٌ مع مفتاح الدفتر)، والنطاقُ يُسمّى.
    # و`history_pairs` **محذوفة** (لا طريقان) — فالمُدخلُ الوحيدُ للنموذج سؤالُ هذه اللحظة.
    # **والنموذجُ لا يكتب الذاكرة** (R99-1): نداؤه بلا حافظة، والكتابةُ وحدَها هنا في `remember`.
    # **وعددُ صفحات المستند يُمرَّر إلى الحاجز (R115-7/R117-2):** من يعرف عددَ الصفحات هو من حمّل
    # الكشف ⇒ فقراءةُ الصفحات من الحالة، وإلّا من عدد صفحات الصفوف، وإلّا **يُعلَن الغياب** (كما في
    # نصّ النطاق) ولا يُدَّعى انتهاءُ الكشف. **وهذا هو الشقُّ الغائب الذي قاسه المدقّق:** `classify`
    # كان يقبل `n_pages` ولا مُنادٍ يمرّره ⇒ فالنصُّ يقول للمستخدم «لم تُقرأ سطورُ ٧٠٠ بعد» عن
    # صفحةٍ لا وجودَ لها في كشفٍ من ٦٢٩ صفحة.
    res = answer_question(STATE["store"], q,
                          rows=None if ledger_path else STATE.get("rows"),
                          chunks=STATE.get("chunks"),
                          footers=None if ledger_path else STATE.get("footers"),
                          thread_id=key, scope=_scope_text(),
                          n_pages=_scope_n_pages(STATE.get("rows") or []),
                          ledger_path=ledger_path, memory_path=memory_path)
    rows_now = STATE.get("rows") or []
    page_of = {i + 1: r.get("page") for i, r in enumerate(rows_now)}
    verdicts = STATE.get("verdicts") or {}
    displayed = render_answer_text(res, page_of, verdicts)
    history.append({"role": "assistant", "content": displayed})
    # **والحفظُ عند بوّابة العرض — موضعُ الكتابة الواحد** (R99-1 · قرار 98ب · تصحيحُ مقعد المواصفة):
    # تُحفظ **التبادلَ المقبولَ وحدَه**: سؤالُ المستخدم كما سأله، و**الجوابَ المعروضَ** بحرفه —
    # وبراياتِه التي تُضاف هنا (تعذُّرُ الأدوات · «رقمٌ بلا شاهد»). فالمحفوظُ = ما رآه المستخدم
    # بالبناء، لا نصُّ النموذج ثمّ يُعرض غيرُه. ووحدتُه سؤالُ المستخدم ⇒ **دورةٌ واحدةٌ** لكلّ سؤال
    # (لا المحاولةَ المرفوضة، ولا نصفَ سؤالٍ مركّب، ولا توجيهَ «استخدم أداة»).
    remember(key, q, displayed, memory_path=memory_path)
    # **والتبادلُ يُسجَّل في القاعدة أيضًا (R130):** قصدُ «الأسئلة المسجَّلة» يعرض ما سُئل فعلًا،
    # وأدلّتُه صفوفُ الأثر — لا رسائلُ الحافظة (وهي مقصوصةٌ إلى ثلاثِ دورات).
    _record_qa_row(res, q, displayed)
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
    if mode == "typed":
        # **الاستشهادُ المُصرَّح به من النوع (أ-٤)** — يُعرض هو، وكلُّ استشهادٍ لا شاهدَ له في
        # الأثرِ **يُسمّى في اللوحة** بدل أن يُمرَّر كأنّه مُثبت.
        df, note = _evidence_from_numbers(res.cited_row_ids)
        if getattr(res, "unsupported_citations", None):
            note = ((note + " · ") if note else "") + (
                "⚠ استشهادٌ بلا شاهدِ أثر: "
                + ", ".join(f"صف {n}" for n in res.unsupported_citations))
        return history, sources_md, df, _note_update(note)
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

**النطاق الحالي — بصدق:** كشوف **مصرف الراجحي** فقط · العيّنة التجريبية 10 صفحات، والكشف المرجعي الممسوح 629: **614 صفحة مطابقة بإطارها المطبوع** (وهي القراءةُ التي يقرأ بها هذا التطبيق)، **وأربعٌ تخالف إطارها بأسمائها** (94 · 141 · 310 · 595) · **4 فجوة في الترقيم** (427 · 626 أوراقٌ غائبة من المسح نقصها مقيس · و490 · 596 رقمُ الصفحة قبلهما قُرئ «1»، ولا ورقةَ غائبة) · **3 غير محسومة** (173 · 485 · 603) · **4 بلا سطر إجماليات مطبوع** (172 · 484 · 602 · 629) — أي أن **كل صفحة محسوبة**، بلا ادعاء تغطية كاملة قبل اجتياز البوابات.

**قاعدة الخصوصية:** القراءة تعمل عبر خدمة سحابية (VLM) — لا ترفع كشفاً حقيقياً إلا إذا قبلت بمعالجته على السحابة. العرض العام يعمل بفيّكسترة **اصطناعية** فقط: لا تستخدم السطح العام لبياناتك الحقيقية.

**وأين تعيش بياناتك (R130):** جدولُ الحركات وأحكامُ الصفحات والمحادثةُ تُحفظ في **قاعدة SQLite واحدة على جهازك** داخل مجلّد بيانات المستخدم (`~/Library/Application Support/rajhi-rag` على macOS) — **لا تدخل المستودع ولا تُرفع**، وزرُّ «احذف بيانات هذا الكشف» يمحو القاعدةَ ومحادثتَها وملفّاتها ويترك صفرَ ملفّ.

**الإصدار:** دفتر الأستاذ — ورق دافئ، حبر زمردي، إبر نحاسية، وختم التدقيق.
"""

def _ledger_rows() -> list:
    """صفوفُ الدفتر = **صفوفُ العقد** (`STATE["rows_contract"]`) — لا سطحُ العرض (R98-1).

    سطحُ العرض بلا رقم صفّ ولا حقول العقد ⇒ كان «ابنِ الدفتر» يسقط بـ`IntegrityError … row_no` (كما سقط
    زرُّ Excel قبل ٩٧). وزرُّ Excel يكتب الدفترَ من صفوف العقد نفسِها ⇒ مصدرٌ واحدٌ للزرّين.
    """
    return STATE.get("rows_contract") or []


def _ledger_key() -> str:
    """مفتاحُ الدفتر: من **بصمة الكشف** (STATE["era"]) ⇒ الكشفُ نفسُه يُعطي المفتاحَ نفسَه.

    **وبعد إعادة التشغيل لا بصمةَ في الذاكرة (R130):** يُقرأ المؤشّرُ النشِط من مجلّد بيانات
    المستخدم — فتعرف الواجهةُ أيَّ قاعدةٍ تفتح، ويعمل تنزيلُ المحادثة والأسئلةُ بلا حالةٍ حيّة.
    """
    rows = _ledger_rows()
    era = STATE.get("era")
    if era:
        return _ledger.statement_key(era, _ledger.pages_of(rows))
    return _ledger_ui.active_key(DATA_HOME) or _ledger.statement_key(None, _ledger.pages_of(rows))


def _memory_path():
    """ملفُّ `SqliteSaver` = **قاعدةُ الكشف نفسُها** — أو `None` إن لم تُقرأ بعد (لا ملفَّ يُنشأ).

    **ويُتحقّق من قابليّتها للقراءة قبل تسليمها للحافظة:** قاعدةٌ v1 (قديمة) أو تالفةٌ لا يُضاف إليها
    مخطَّطُ الحافظة، بل تُترك للتشخيص المسمّى (`status_text`) ولإعادة القراءة.
    """
    key = _ledger_key()
    if not key:
        return None
    path = _ledger_ui.ledger_file(DATA_HOME, key)
    if not path.exists():
        return None
    # **قراءةٌ خفيفةٌ للترقيم لا فتحٌ كامل:** `read_ledger` يُنفّذ المخطَّطَ كلَّه (كتابةً) في كلّ
    # سؤال؛ والفحصُ هنا لا يحتاج إلا `user_version` — فقاعدةٌ v1 (أو غيرُ مرقَّمة) تُترك للتشخيص.
    import sqlite3                                                 # noqa: PLC0415

    try:
        c = sqlite3.connect(str(path))
        try:
            ver = int(c.execute("PRAGMA user_version").fetchone()[0])
        finally:
            c.close()
    except sqlite3.DatabaseError:
        return None
    return path if ver == _ledger.SCHEMA_VERSION else None


def _ledger_refresh_click() -> str:
    rows = _ledger_rows()
    return _ledger_ui.status_text(DATA_HOME, _ledger_key(), len(rows),
                                  _ledger.rows_without_page(rows))


def _ledger_build_click():
    rows = _ledger_rows()
    msg = _ledger_ui.build(DATA_HOME, rows, STATE.get("footers") or {}, _ledger_key())
    return msg, _ledger_refresh_click()


def _ledger_ask_click(label: str, value: str):
    got = _ledger_ui.ask(DATA_HOME, _ledger_key(), label, value)
    return pd.DataFrame(got["rows"], columns=got["headers"]), got["note"]


def _delete_statement_click():
    """**زرُّ الحذف الظاهر (R130):** يمحو القاعدةَ ومحادثتَها وملفّاتِها ويترك صفرَ ملفّ.

    **والترتيبُ مقصود:** إغلاقُ الحافظة (`qa.reset_memory`) **قبل** الحذف — متّصلٌ مفتوحٌ يُعيد إنشاء
    `-wal` بعد إزالة الملفّ. ثمّ يُمسح المؤشّر وتُفرَّغ الحالةُ والأسطح. ويُعاد عدُّ ما حُذف.
    """
    from statement_qa.qa import reset_memory

    key = _ledger_key()
    path = _ledger_ui.ledger_file(DATA_HOME, key) if key else None
    if path is not None:
        reset_memory(path)
    got = _ledger_ui.delete(DATA_HOME, key)
    # **وملفّاتُ التنزيل في حافظة Gradio تُمسح بمكوّن المكتبة** (لا منظّفٍ يدويّ): الصورُ والإكسلُ
    # والمحادثةُ المنزَّلة. `delete_files_created_by_app(demo, None)` هي التي يناديها `delete_cache`
    # وعند الإغلاق — فالحذفُ يترك صفرَ ملفٍّ **الآن** لا بعد عشر دقائق.
    try:
        from gradio.route_utils import delete_files_created_by_app   # noqa: PLC0415

        delete_files_created_by_app(demo, age=None)
    except Exception:                          # noqa: BLE001 — لا يُسقط حذفَ البيانات
        pass
    STATE.clear()
    return (got["message"], "", pd.DataFrame(), _kpi_html(0, 0, 0, None), [],
            "", "", pd.DataFrame(), _hide_note(),
            _ledger_ui.status_text(DATA_HOME, None, 0))


def _conversation_markdown() -> tuple[str | None, str]:
    """**تنزيلُ المحادثة (البند ١٠):** سؤالٌ وجوابٌ وأدلّةٌ من **القاعدة** — لا من ذاكرةٍ حيّة.

    والقراءةُ من جدول `qa` + `qa_evidence` + `rows_verified` (لا من رسائل الحافظة): الرسائلُ تُقصّ
    إلى نافذةِ ثلاثِ دورات، والسجلُّ المقصودُ «ما سُئل فعلًا» يبقى كاملًا. فالحذفُ/إعادةُ التشغيل
    لا يقطعان التنزيل.
    """
    key = _ledger_key()
    if not key:
        return None, "**لا كشفَ بعد** — اقرأ كشفًا أو افتح قاعدةً محفوظة."
    path = _ledger_ui.ledger_file(DATA_HOME, key)
    try:
        conn = _ledger.read_ledger(path)
    except _ledger.LedgerUnavailable as e:
        return None, f"**تعذّر فتحُ القاعدة — {e}**"
    try:
        qa_rows = conn.execute(
            "SELECT q.id, q.asked_at, q.question, q.answer, q.refused FROM qa q ORDER BY q.id"
        ).fetchall()
        if not qa_rows:
            return None, "**لا محادثةَ مسجَّلةً بعد** في هذا الكشف."
        name = (_ledger_ui.active_get(DATA_HOME) or {}).get("name") or "كشف"
        lines = [f"# محادثةُ كشف — {name}", ""]
        for r in qa_rows:
            lines.append(f"## {r['asked_at']} — سؤال {r['id']}")
            lines.append(f"**السؤال:** {r['question']}")
            lines.append(f"**الجواب:** {r['answer'] or '—'}")
            ev = conn.execute(
                "SELECT v.pg, v.row_no, v.desc, v.movement FROM qa_evidence e "
                "JOIN rows_verified v ON v.id = e.row_id WHERE e.qa_id = ? ORDER BY v.pg, v.row_no",
                (r["id"],)).fetchall()
            if ev:
                lines += ["**الأدلّة:**", "", "| صفحة | صفّ | البيان | المبلغ |", "|---|---|---|---|"]
                for e in ev:
                    desc = (e["desc"] or "").replace("|", "/")
                    lines.append(f"| {e['pg']} | {e['row_no']} | {desc} | {e['movement'] or ''} |")
            else:
                lines.append("**الأدلّة:** لا صفوفَ دليلٍ مرتبطة (امتناعٌ أو جوابٌ بلا صفوف).")
            lines.append("")
    finally:
        conn.close()
    with tempfile.TemporaryDirectory(prefix="rajhi_chat_") as work:
        out = Path(work) / "conversation.md"
        out.write_text("\n".join(lines), encoding="utf-8")
        kept = _cache_path(conv_file, out)
    return kept, f"**{len(qa_rows)}** سؤالًا وجوابًا · ملفّ Markdown"


def _record_qa_row(res, question: str, displayed: str) -> None:
    """يسجّل السؤالَ والجوابَ وأدلّةَ الأثر في `qa`/`qa_evidence` — **وقصدُ «الأسئلة المسجَّلة»** يقرؤه.

    **العِلّة:** `record_qa` كانت **صفرَ مُنادٍ** (قِيس في مراجعة ١٣٠) ⇒ فالقصدُ يعرض فراغًا أبدًا.
    والصفوفُ المسجّلة هي **ما بنى الجواب** (`used_row_nos`) لا ما ذكره النثر. وأرقامُ الصفوف
    العامّةُ تُترجَم إلى `(pg, row_no)` من نفسِ ترتيب الحالة (وهو ترتيبُ `seq` في القاعدة).
    """
    key = _ledger_key()
    path = _ledger_ui.ledger_file(DATA_HOME, key) if key else None
    if path is None:
        return
    try:
        conn = _ledger.read_ledger(path)
    except _ledger.LedgerUnavailable:
        return
    try:
        # **الترجمةُ من صفوف العقد لا من سطح العرض:** العرضُ بلا `row_no`، والعقدُ يحمله؛ والصفّان
        # متوازيان بالبناء (`_view_rows(contract)`) ⇒ فالمؤشّرُ نفسه.
        contract = STATE.get("rows_contract") or []
        nos = (res.used_row_nos or []) or (res.cited_row_ids or [])
        pairs = [(contract[n - 1].get("page"), contract[n - 1].get("row_no"))
                 for n in nos if 1 <= n <= len(contract)]
        ids = _ledger.row_ids_for(conn, pairs)
        import datetime as _dt

        _ledger.record_qa(conn, _dt.datetime.now().isoformat(timespec="seconds"),
                          question, displayed, ids, refused=bool(res.refused))
    finally:
        conn.close()


with gr.Blocks(title="مُدقّق كشوف الراجحي", delete_cache=(600, 600)) as demo:
    # **`delete_cache=(600, 600)` (R130-2):** ملفّاتُ الحافظة التي تُنشئها المكوّناتُ من مخرجاتنا
    # (صورُ المعرض · الإكسل · المحادثة) يحذفها **مكوّنُ Gradio** بعد عشر دقائق، وكلَّها عند إغلاق
    # الخادم (`route_utils.create_lifespan_handler`، مقروءٌ من النسخة المثبَّتة) — لا منظّفٌ يدويّ.
    gr.HTML(HERO)
    with gr.Tabs():
        with gr.Tab("١. قراءة وتحقق"):
            with gr.Row():
                with gr.Column(scale=1, min_width=340):
                    pdf_in = gr.File(label="كشف PDF (عينة تجريبية موصى بها)",
                                     file_types=[".pdf"], elem_id="file-panel")
                    btn = gr.Button("قراءة الكشف وبناء الفهرس", variant="primary",
                                    interactive=False)
                    # **البند ١١:** مكانُ خانة «استبعاد الصفحات المرفوضة» صار **رسالةً بما حدث**؛
                    # فالخانةُ كانت تُقرأ نقصًا ولا تقول شيئًا، والقراءةُ تكتب القاعدةَ تلقائيًّا.
                    intake_note = gr.Markdown(
                        "**فحصُ الصفحات قبل القراءة:** تظهر نتيجتُه هنا بعد القراءة.",
                        rtl=True)
                    gr.Markdown(
                        "*نسخة تجريبية: كشوف الراجحي فقط · العيّنة قيد التوسع. "
                        "تُقرأ الصفحات عبر خدمة سحابية — لا ترفع كشفاً حقيقياً "
                        "إلا إن قبلت معالجته سحابياً، ولا ترفعه إلى سطح عام.*",
                        rtl=True)
                    ticker = gr.Markdown("في انتظار الكشف… ارفع ملفاً ثم ابدأ القراءة.",
                                         rtl=True, elem_classes=["ticker"])
                    # **زرُّ الحذف الظاهر (R130):** داخل تأكيدٍ صريح — لا يُمسح كشفٌ بنقرةٍ عابرة.
                    delete_ack = gr.Checkbox(
                        label="أؤكّد حذف بيانات هذا الكشف (القاعدة والمحادثة وملفّاتها)",
                        value=False)
                    delete_btn = gr.Button("احذف بيانات هذا الكشف", variant="stop",
                                           interactive=False)
                    delete_note = gr.Markdown(rtl=True)
                with gr.Column(scale=2, min_width=420):
                    kpi = gr.HTML("")
            with gr.Row():
                filter_col = gr.Dropdown(choices=list(FILTER_COLUMNS), value="كل الأعمدة",
                                         label="عمود الفلترة", scale=2)
                filter_value = gr.Textbox(
                    label="القيمة", placeholder="مثال: العمود «النوع» والقيمة «سحب»",
                    rtl=True, scale=3)
                filter_from = gr.Textbox(label="من تاريخ (YYYY-MM-DD)", rtl=True, scale=2)
                filter_to = gr.Textbox(label="إلى تاريخ (YYYY-MM-DD)", rtl=True, scale=2)
                filter_clear = gr.Button("مسح الفلتر", scale=1)
            table = gr.Dataframe(label="الجدول المُستخرج (بالسلسلة الرصيدية)",
                                 interactive=False, elem_classes=["ledger-table"])
            _filter_inputs = [filter_col, filter_value, filter_from, filter_to]
            for _c in _filter_inputs:
                _c.input(filter_rows, inputs=_filter_inputs, outputs=table)
                _c.change(filter_rows, inputs=_filter_inputs, outputs=table)
            filter_clear.click(lambda: ("كل الأعمدة", "", "", "", filter_rows("")),
                               outputs=[filter_col, filter_value, filter_from, filter_to, table])
            with gr.Accordion("صفحات الكشف (معاينة بصرية)", open=False):
                gallery = gr.Gallery(columns=5, show_label=False)
            pdf_in.change(lambda f: gr.update(interactive=bool(f)),
                          inputs=pdf_in, outputs=btn)
            delete_ack.change(lambda v: gr.update(interactive=bool(v)),
                              inputs=delete_ack, outputs=delete_btn)
            # **توصيلُ زرّ القراءة مؤجَّلٌ إلى التبويب ٢** حيث تُعرَّف `ledger_state` — مستمعٌ واحدٌ
            # يكتب سبعَ مخرجاتٍ ومنها حالةُ القاعدة (تعريفُ المكوّن قبل استعماله شرطُ البناء).
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
            # **البند ٢ — زرُّ التنزيل:** الملفُّ يُبنى بالنواة نفسها التي يُبنى بها ملفُّ سطر الأوامر،
            # فالمقابلةُ خليّةً بخليّة في `tests/test_app_excel_button.py` قائمةٌ لا موعودة.
            with gr.Row():
                xlsx_btn = gr.Button("تنزيل الكشف - Excel", variant="secondary", scale=2)
                xlsx_note = gr.Markdown(rtl=True, scale=3)
            xlsx_file = gr.File(label="ملفّ الكشف (xlsx)")
            xlsx_btn.click(export_xlsx, inputs=[], outputs=[xlsx_file, xlsx_note],
                           api_name="export_xlsx")
            # **البند ١٠ — تنزيلُ المحادثة:** سؤالٌ وجوابٌ وأدلّةٌ من القاعدة (تبقى بعد الإغلاق).
            with gr.Row():
                conv_btn = gr.Button("تنزيل المحادثة (سؤال · جواب · أدلّة)", scale=2)
                conv_note = gr.Markdown(rtl=True, scale=3)
            conv_file = gr.File(label="ملفّ المحادثة (Markdown)")
            conv_btn.click(_conversation_markdown, inputs=[], outputs=[conv_file, conv_note],
                           api_name="download_conversation")
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
            # **R93-2 · حدثٌ ثانٍ على زرّ القراءة:** يمسح أسطحَ السؤال الأربعة. وموضعُه هذا لأنّ
            # الأسطحَ تُعرَّف في هذا التبويب، وهو مستقلٌّ عن مسار القراءة فلا يقف في طريقه ولا يُنتظره.
            btn.click(_reset_qa_surfaces, outputs=[chat, src, raw, raw_note],
                      show_progress="hidden")
            # **دفترُ الكشف — أسئلةٌ بلا نموذج وبلا كلفة:** الأسئلةُ البنيويّةُ (مجاميع · تغطية ·
            # بلا إثبات · أحكام صفحات · بحث · سجلّ الأسئلة) تُجاب من SQL وحدَه. والمنطقُ في
            # `statement_qa.ledger_ui` (نقيٌّ يُختبر بلا شاشة)، وهنا التوصيلُ فقط. **والنتائجُ في
            # `gr.Dataframe` (R130-3)** فلا يكسر وصفٌ فيه سطرٌ جديد جدولَ Markdown.
            with gr.Accordion("دفترُ الكشف — أسئلةٌ بلا نموذج وبلا كلفة", open=False):
                ledger_state = gr.Markdown(_ledger_ui.status_text(DATA_HOME, None, 0), rtl=True)
                with gr.Row():
                    l_intent = gr.Dropdown(choices=list(_ledger_ui.INTENT_LABELS),
                                           value=next(iter(_ledger_ui.INTENT_LABELS)),
                                           label="القصد", scale=4)
                    l_value = gr.Textbox(label="القيمة (رقمُ صفحةٍ لقصد «أحكام الصفحات»، أو نصُّ بحث)",
                                         rtl=True, scale=5)
                    l_build = gr.Button("أعد بناء الدفتر", scale=2)
                    l_ask = gr.Button("اسأل الدفتر", variant="primary", scale=2)
                ledger_out = gr.Dataframe(interactive=False, label="نتيجةُ القصد")
                ledger_note = gr.Markdown(rtl=True)
                l_refresh = gr.Button("حدّث الحالة", size="sm")
                l_build.click(_ledger_build_click, outputs=[ledger_note, ledger_state])
                l_ask.click(_ledger_ask_click, inputs=[l_intent, l_value],
                            outputs=[ledger_out, ledger_note])
                l_refresh.click(_ledger_refresh_click, outputs=[ledger_state])
            # **توصيلُ زرّ القراءة (٣):** بعد تعريف كلّ مخرجاتِه، ومنها `ledger_state`.
            btn.click(process_pdf, inputs=[pdf_in],
                      outputs=[ticker, table, kpi, gallery, filter_col, filter_value,
                               filter_from, filter_to, ledger_state, intake_note],
                      show_progress_on=[ticker])
            delete_btn.click(_delete_statement_click, outputs=[
                delete_note, ticker, table, kpi, gallery, chat, src, raw, raw_note, ledger_state])
        with gr.Tab("٣. عن المشروع"):
            gr.Markdown(ABOUT, rtl=True)

if __name__ == "__main__":
    # **البصمةُ تُكتب هنا وحدَه (R78-1):** هذا الموضعُ هو الذي تصير فيه هذه العمليةُ *هي التي تُجيب*
    # على المنفذ — فتصدق البصمةُ على الكود الذي يُنتج الأرقامَ فعلًا، لا على كودٍ استورَد الملفَّ للحظة.
    APP_CODE_STAMP = _write_code_stamp()
    demo.launch(theme=THEME, css=RTL_CSS, head=HEAD)
