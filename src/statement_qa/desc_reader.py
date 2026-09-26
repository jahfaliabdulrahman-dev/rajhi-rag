"""البيانُ من عمود البيان وحده — استدعاءٌ واحدٌ لكلّ صفحة، والأرقامُ لا تُمسّ.

## لماذا (مقيس)

قراءةُ الصفحة كاملةً **أدقُّ في الأرقام** (السلسلةُ والتذييلُ يُثبتانها صفًّا صفًّا) لكنها **تُخطئ
البيان**: تكملةُ آخرِ حركةٍ المطبوعةُ أعلى الصفحة التالية تُلصق بصفٍّ خاطئ، وقد يجرّ ذلك انزياحَ
البيانات صفًّا كاملًا والمبالغُ سليمة — فلا تراه السلسلة. وقصاصةُ الصفّ الواحد تُصلح البيان لكنها
**تُفسد الأرقام** (الصفرُ الهندي النقطيّ يُشبه الفاصلة؛ والقصاصةُ تفقد اصطفافَ العمود).

فالقسمة: **الأرقامُ والتواريخُ من قراءة الصفحة، والبيانُ من هنا.** مقيسٌ على ٢٠ صفحة (١٨٦ صفًّا):
تطابقُ الكلمات مع مرجع القصاصة المنفصلة ١٧٣ صفًّا، وفرقُ كلمةٍ أو كلمتين في ١١، والفرقان «الأكبر»
مسافةٌ وحرفٌ في رمز حوالة؛ وانزياحُ الصفحتين ٦ و٧ زال. بكلفة ≈ ٠٫٠٠٨$ للصفحة.

## الصورة

منطقةُ البيان والتاريخ من كلّ صفّ (`ZONE_X`)، **بعد مسح كتلة مبلغ المدين** من السطر الأول — المبلغُ
ملاصقٌ للبيان فلا يُقصّ بخطٍّ مستقيم، وأصفارُه نقاطٌ متباعدة فالفراغُ الفاصلُ ≥١٢ وحدة. الصفوفُ
مكدّسةٌ في خاناتٍ مرقّمةٍ بخطوطٍ سوداء عريضة، والصفُّ الأخير يحمل تكملتَه من الصفحة التالية تحت خطٍّ
رماديٍّ رفيع. وعددُ الخانات معروفٌ من الحبر، فالجوابُ الناقصُ خانةً يُرفض ويُعاد — لا يُسدّ.

## الدمج

يُستبدل البيانُ **فقط** حين يساوي عددُ صفوف الصفحة عددَ الخانات (مقيس: ٦٢٥/٦٢٥)؛ وإلا يبقى بيانُ
القراءة الكاملة ويُسمّى السبب. والبيانُ القديمُ يُحفظ في `desc_page` — لا يُمحى أثرٌ.
"""
from __future__ import annotations

import base64
import io

import numpy as np

from statement_qa.row_bands import Band, PageBands

ZONE_X = (325, 720)            # البيانُ والتاريخ (وحدة 100dpi)
AMOUNT_ZONE_END = 420          # كتلةُ مبلغ المدين تبدأ قبل هذا
AMOUNT_GAP = 12                # الفراغُ بين المبلغ والنصّ (الأصفارُ نقاطٌ متباعدة)
AMOUNT_MAX_W = 60              # أعرضُ من هذا ليس مبلغًا — لا يُمسح
LABEL_W, SEP = 70, 6

DESC_PROMPT = """الصورة {n} خانةً مرقّمةً من 1 إلى {n}، مفصولةً بخطوطٍ سوداء عريضة. كلُّ خانةٍ **بيانُ حركةٍ واحدة** من كشف حساب مصرفي سعودي، ورقمُها في المربع على يسارها.
وقد تكون الخانةُ جزأين بينهما خطٌّ رماديٌّ رفيع: الجزءُ السفلي تكملةُ البيان نفسه من الصفحة التالية — فهو من الخانة نفسها.
انسخ البيانَ كما هو مطبوعٌ بكلّ أسطره، **بلا التاريخ** وبلا أي مبلغ. لا تنقل نصًّا من خانةٍ إلى أخرى، ولا تدمج خانتين.
أعد JSON فقط: {{"rows": [{{"n": 1, "desc": "..."}}, ...]}} — عنصرٌ واحدٌ لكلّ خانة، {n} عنصرًا بالضبط."""


def _zone(img, top: int, bottom: int, k: float):
    return img.crop((int(ZONE_X[0] * k), top, int(ZONE_X[1] * k), bottom + 1))


def blank_debit_amount(crop, band: Band, k: float):
    """صفُّ مدين: المبلغُ يسار النصّ في السطر الأول — تُمسح كتلتُه وحدها. صفُّ دائن: مبلغُه خارج المنطقة."""
    from PIL import ImageDraw

    if band.credit_ink:
        return crop
    g = np.asarray(crop.convert("L"))
    y0 = max(0, band.anchor[0] - band.top - int(2 * k))
    y1 = min(g.shape[0], band.anchor[1] - band.top + int(2 * k))
    cols = np.flatnonzero((g[y0:y1] < 150).any(axis=0))
    if cols.size == 0 or cols[0] > (AMOUNT_ZONE_END - ZONE_X[0]) * k:
        return crop
    start = end = int(cols[0])
    for c in cols[1:]:
        if c - end > AMOUNT_GAP * k:
            break
        end = int(c)
    if end - start > AMOUNT_MAX_W * k:
        return crop
    out = crop.copy()
    ImageDraw.Draw(out).rectangle([start - 2, y0, end + 2, y1], fill="white")
    return out


def stack_image(img, pb: PageBands, continuation=None):
    """(صورةٌ مكدّسة، عددُ الخانات). `continuation` = (صورةُ الصفحة التالية، (أعلى، أسفل)) تُلصق بالصفّ الأخير."""
    from PIL import Image, ImageDraw, ImageFont

    k = pb.dpi / 100
    parts = []
    for i, band in enumerate(pb.bands):
        crop = blank_debit_amount(_zone(img, band.top, band.bottom, k), band, k)
        if continuation is not None and i == len(pb.bands) - 1:
            nxt, (t, b) = continuation
            cont = _zone(nxt, t, b, k)
            both = Image.new("RGB", (crop.width, crop.height + 4 + cont.height), "white")
            both.paste(crop, (0, 0))
            both.paste(cont, (0, crop.height + 4))
            ImageDraw.Draw(both).line([(0, crop.height + 2), (both.width, crop.height + 2)],
                                      fill=(160, 160, 160), width=1)
            crop = both
        parts.append(crop)
    font = ImageFont.load_default(size=30)
    w = LABEL_W + max(p.width for p in parts)
    out = Image.new("RGB", (w, sum(p.height for p in parts) + SEP * (len(parts) + 1)), "white")
    d = ImageDraw.Draw(out)
    d.rectangle([0, 0, w, SEP - 1], fill="black")
    y = SEP
    for n, p in enumerate(parts, start=1):
        out.paste(p, (LABEL_W, y))
        d.rectangle([4, y + 4, LABEL_W - 8, y + 44], outline="black", width=2)
        d.text((12, y + 8), str(n), fill="black", font=font)
        y += p.height
        d.rectangle([0, y, w, y + SEP - 1], fill="black")
        y += SEP
    return out, len(parts)


def parse_descriptions(content: str, n: int) -> list[str]:
    """جوابُ النموذج ⇒ n بيانًا بترتيب الخانات. خانةٌ ناقصةٌ أو زائدة ⇒ خطأٌ يُعاد عليه (لا يُسدّ)."""
    from statement_qa.vlm_reader import _extract_json

    data = _extract_json(content)
    rows = data.get("rows", []) if isinstance(data, dict) else data
    got: dict[int, str] = {}
    for r in rows or []:
        if isinstance(r, dict) and str(r.get("n", "")).strip().isdigit():
            got[int(r["n"])] = str(r.get("desc") or "").strip()
    if sorted(got) != list(range(1, n + 1)):
        raise ValueError(f"خانات الجواب {sorted(got)} ≠ 1..{n}")
    return [got[i] for i in range(1, n + 1)]


def read_page_descriptions(img, pb: PageBands, continuation=None,
                           stats: dict | None = None) -> list[str]:
    """استدعاءٌ واحد: صورةُ الصفحة ⇒ بياناتُ صفوفها بالترتيب."""
    from statement_qa.vlm_reader import chat_vlm_image

    image, n = stack_image(img, pb, continuation)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return chat_vlm_image(base64.b64encode(buf.getvalue()).decode(), DESC_PROMPT.format(n=n),
                          max_tokens=3000, stats=stats,
                          parse=lambda c: parse_descriptions(c, n))


def merge_descriptions(rows: list[dict], descs: list[str]) -> bool:
    """يُستبدل البيانُ حين تتساوى الأعداد فقط، ويُحفظ القديمُ في `desc_page`. يعيد: هل دُمج؟

    وخانةٌ أعادها النموذجُ فارغةً لا تمحو بيانًا موجودًا: يبقى بيانُ القراءة الكاملة لذلك الصفّ.
    """
    if len(rows) != len(descs):
        return False
    for r, d in zip(rows, descs):
        if not d:
            continue
        r["desc_page"] = r.get("desc")
        r["desc"] = d
        r["desc_source"] = "column"
    return True


def continuation_for(pb: PageBands, nxt_pb: PageBands | None, nxt_img):
    """(صورةُ التالية، مدى التكملة) إن كان الصفُّ الأخير هنا يُكمَل أعلاها — وإلا None.

    المستدعي يمرّر التاليةَ **فقط** حين يُثبت الحسابُ أنهما ورقتان متتاليتان (`ordering.adjacency`
    = `adjacent`): تكملةٌ بعد ورقةٍ غائبة لصفٍّ ليس عندنا، ولصقُها هنا يُفسد بيانًا سليمًا — والبيانُ
    الناقصُ أهونُ من البيان المنسوب لغير صاحبه.
    """
    pages = ("transactions", "first")
    if (nxt_pb is None or not pb.bands or pb.kind not in pages
            or nxt_pb.orphan is None or nxt_pb.kind not in pages):
        return None
    return nxt_img, nxt_pb.orphan


def summarize_ar(rep: dict, total: int) -> str:
    """سطرُ الملخّص: من أين جاء البيان، وأين بقي بيانُ القراءة الكاملة ولماذا."""
    seg = (f"البيانُ من عمود البيان: {len(rep['merged'])}/{total} صفحة "
           f"(تكملاتٌ ملصوقةٌ بصفوفها: {rep['stitched']})")
    kept = ([f"ص{p} (تعذّرت قراءتُه)" for p in rep["failed"]]
            + [f"ص{p} (عددُ الصفوف لا يطابق)" for p in rep["unaligned"]]
            + [f"ص{p} (سقفُ الكلفة)" for p in rep["skipped"]])
    if kept:
        seg += " · ⚠ بقي بيانُ قراءة الصفحة في: " + "، ".join(kept[:8]) + (" …" if len(kept) > 8 else "")
    return seg


# ——— الملفُّ الجانبيّ للتشغيلات الكبيرة (`tools/desc_pass.py` يكتبه، `tools/to_xlsx.py --desc-column` يقرؤه) ———
# الكاشُ (`results/pg-NNN.json`) **لا يُمسّ**: عليه تقوم أختامُ الصفحات والحزمةُ والأرقامُ المعلنة. والبيانُ
# الجديد يعيش في `results/desc/pg-NNN.json` — مجلّدٌ فرعيٌّ لا يطاله `glob("pg-*.json")`.
SIDECAR_DIR = "desc"


def sidecar_path(results_dir, pg: int):
    from pathlib import Path

    return Path(results_dir) / SIDECAR_DIR / f"pg-{pg:03d}.json"


def read_sidecar(path) -> list[str] | None:
    """بياناتُ الصفحة من ملفّها الجانبي، أو None إن غاب أو فسد (لا يُخمَّن)."""
    import json

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    descs = data.get("descs") if isinstance(data, dict) else None
    return descs if isinstance(descs, list) and all(isinstance(d, str) for d in descs) else None


def merge_into_page(raw_rows: list[dict], descs: list[str]) -> list[dict] | None:
    """نسخةٌ من صفوف الصفحة الخام ببيان العمود على **صفوف الحركة** (ذات الرصيد) — أو None إن اختلف العدد.

    سطرٌ بلا رصيدٍ مطبوع (ملخّصٌ أو افتتاحي) ليس صفًّا في الحبر ولا خانةً في الصورة، فلا يُحسب.
    """
    rows = [dict(r) for r in raw_rows]
    movers = [r for r in rows if r.get("balance") not in (None, "")]
    return rows if merge_descriptions(movers, descs) else None
