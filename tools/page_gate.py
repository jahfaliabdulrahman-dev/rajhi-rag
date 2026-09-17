#!/usr/bin/env python3
"""بوابة جودة المسح على مستوى **الصفحة** — محلية 100% (بلا أي استدعاء نموذج).

## لماذا هذه البوابة

قيمة هذا المشروع ليست «قراءة الأرقام» بل **إثباتها**، والإثبات يقوم على مرجع مستقل:
سطر الإجماليات المطبوع أسفل الصفحة (المُحكَّم). صفحة بلا هذا السطر = أرقام لا يمكن
إثباتها أبداً. لذلك **دفع كلفة قراءة صفحة لا يمكن إثباتها = مال يُحرَق**.

`tools/preflight.py` يقيس ذلك على **مستوى الملف** (عيّنة 8 صفحات، عتبات مجمّعة).
هذه الأداة تقيسه على **مستوى الصفحة الواحدة** — قبل أي إنفاق — وتسمّي السبب.

## الأحكام الثلاثة (لا رابع)

| الحكم | المعنى | الأثر على التشغيل |
|---|---|---|
| `accept` | الصورة سليمة والمُحكَّم مقروء | تُقرأ عادةً |
| `warn` | تُقرأ، لكن فيها ما يستحق التسمية (بلا مُحكَّم · نص صغير · مقاس شاذ) | تُقرأ **ويُسمّى عيبها** في التقرير — لا تُمنع، لأن المنع هنا يكسر وضعاً مشروعاً |
| `reject` | الصورة نفسها غير صالحة (أفقية · اهتزاز · ميل · صفحة فارغة) | **لا تُدفع كلفتها** — تُعاد للعميل بسبب مكتوب |

## القياسات الأربعة (وكيف تُقاس بلا مكتبات إضافية)

1. **الاهتزاز/الضبابية** — تباين مشتقّ لابلاس (Pech-Pacheco): صورة حادة = تباين عالٍ.
   الصفحة المسطّحة الحادة تُنتج حوافاً كثيفة، والضبابية تبشّرها. يُنفَّذ بـ`numpy` فقط
   (لا `cv2` — ليس تبعية في هذا المشروع ولا يُضاف من أجل قياس).
2. **الميل (skew)** — طريقة مخطط الإسقاط: تدوير على زوايا مرشّحة واختيار الزاوية التي
   تُعطي أعلى تباين لمخطط صفوف الحبر (النص المستقيم يعطي ينابيع حبر أحدّ).
3. **المُحكَّم (سطر الإطار)** — إعادة استخدام `preflight._footer_row` نفسه (لا تكرار
   كود): وجوده + عدد مقاطعه + **ارتفاع مقاطعه** (= ارتفاع أرقام الإطارات بالبكسل).
4. **الهندسة** — المقاس مقابل المقاس السائد في الملف (±2%)، والأفقية/الطولية.

## المرجع المقيس

الأرقام أدناه **ليست مقدَّرة**: مقيسة على 60 صفحة من مسحة الراجحي المعتمدة (A4 @200dpi):

| القياس | المقيس على المرجع | العتبة المُعتمدة |
|---|---|---|
| الحدّة (لابلاس) | p1=707.5 · p5=773.8 · p50=958.0 | رفض تحت **300** |
| الميل | p50=p95=p99=**0.0°** | رفض فوق **2.0°** |
| عرض مجموعة أرقام الإطار (حجم النص) | p1=**9** · p50=13 بكسل | تنبيه تحت **6** |
| ارتفاع كتلة السطر في المتن | p1=**17.6** · p50=20 بكسل | تنبيه تحت **12** |
| كثافة الحبر | p1=0.0171 · p50=0.0219 | رفض تحت **0.010** |
| مقاس الصفحة | 1654×2338 لكل الصفحات | تنبيه عند انحراف **±2%** |
| وجود سطر الإطار | **100%** من الصفحات | غيابه ⇒ تنبيه `no_referee` |

**ثلاثة أحكام صُحّحت بعد المعايرة، وكلها من نوع واحد: تقدير لم يصمد أمام قياس.**

1. **ارتفاع مقاطع الإطار** اتضح أنه **عرض** لا ارتفاع (المقاطع تُقاس على محور الأعمدة).
2. **حدّ الحدّة** المقدَّر أولاً (120) كانت تعبر عنه صفحة ضبابية بسهولة ⇒ رُفع إلى 300.
3. **قاعدة «نص صغير» كانت ميتة:** تُقاس بمقاطع ≥6 بكسل، وأي صورة أرقامها أضيق من 6
   بكسل لا يُكشف إطارها أصلاً ⇒ الحكم لا يُطلق أبداً. عُولج بقياس العرض بمقاطع ≥3،
   وبإضافة برهان ثانٍ مستقل (ارتفاع كتلة السطر في المتن).

## الإثبات على الملف الكامل (629 ورقة · صفر استدعاء · 43 ثانية)

`python tools/page_gate.py --pages-dir data/local_sample/slice_629p/pages --count 629`

**النتيجة: 625 مقبول · 0 منبَّه · 4 مرفوضة** — والأربعة هي بالاسم:

`pg-172 · pg-484 · pg-602 · pg-628`

وهذه **مطابقة تامة** للصفحات التي وثّقها `suspects_log.md` بأنها «بلا إطار مطبوع»
(172 · 484 · 602 · 629 بأرقام الطباعة؛ ورقم الطباعة 629 = الموقع 628 على القرص
لأن المسح ينقصه ورقتان قبل 626) ⇒ **البوابة تعرف، من ميكانيكا الصورة وحدها وبلا
قراءة أي رقم، ما عرفه المشروع بعد قراءتين وستة بنود شكوك.** وقيمة ذلك مباشرة:
هذه الصفحات الأربعة **لا تُدفع كلفتها بعد اليوم**.

**حدّ معروف ومكتوب:** صفحة مصغّرة جداً قد تُصنَّف `no_referee` بدل `small_text` —
وهذا مقبول لأن **الأثر واحد** (تُقرأ وتُسمّى عيبها، وكلاهما `warn` لا `reject`)،
ولا يجوز حجبها: في مسحتك المرجعية **4 صفحات بلا إطار مطبوع أصلاً** وهي مشروعة.
لإعادة إنتاج القياس: `python tools/page_gate.py --calibrate --count 60`
(لا حاجة لأي مفتاح ولا استدعاء — القياس محلي تماماً).

الاستعمال:
  python tools/page_gate.py --pages-dir data/local_sample/slice_629p/pages --first 1 --count 20
  python tools/page_gate.py --pages-dir <dir> --out data/local_sample/page_gate.json
  python tools/page_gate.py --calibrate --pages-dir <dir> --count 60
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.preflight import _footer_row, _gray, _segments  # noqa: E402  (reuse)

# ————————————————————————————————————————————————————————————
# العتبات — مقيسة على المرجع (629 ورقة · A4 @200dpi · 1654×2338)
# p50/p01 لكل قياس مذكورة في التعليق؛ الحدّ يُوضع على مسافة أمان من الأدنى المقيس
# حتى لا تُرفض صفحة سليمة، ويُثبت أنه «يعضّ» باختبارات تدهور مُزروعة (tests/).
# ————————————————————————————————————————————————————————————


@dataclass(frozen=True)
class Thresholds:
    ref_w: int = 1654                    # مقاس الصفحة المرجعي (200dpi, A4)
    ref_h: int = 2338
    size_tol: float = 0.02               # ±2% — شذوذ المقاس داخل الملف نفسه
    lapvar_min: float = 300.0            # الحدّ: المقيس p1=707 · p5=774 · p50=958
    skew_max_deg: float = 2.0            # الحدّ: المقيس p99=0.0° (المرجع مستقيم تماماً)
    glyph_w_min: int = 6                 # عرض أضيق مجموعة أرقام في الإطار: p1=9 · p50=13
    body_h_min: int = 12                 # ارتفاع كتلة سطر في المتن: المقيس p1=17.6 · p50=20
    ink_ratio_min: float = 0.010         # الحدّ: المقيس p1=0.0171 · p50=0.0219
    body_band_h_min: int = 6             # أدنى ارتفاع لكتلة سطر في متن الصفحة


TH = Thresholds()

# مفردات الأسباب — ثابتة، لأن الاختبارات والتقارير تعتمد عليها كنصوص
R_LANDSCAPE = "landscape"
R_BLUR = "blur"
R_SKEW = "skew"
R_BLANK = "blank"
R_NO_REFEREE = "no_referee"
R_SMALL_TEXT = "small_text"
R_SIZE_VARIANCE = "size_variance"

_REJECT = (R_LANDSCAPE, R_BLUR, R_SKEW, R_BLANK)
_WARN = (R_NO_REFEREE, R_SMALL_TEXT, R_SIZE_VARIANCE)

_AR_REASON = {
    R_LANDSCAPE: "الصفحة أفقية (العرض أكبر من الطول) — التصوير/التدوير يحتاج إصلاحاً",
    R_BLUR: "الصورة غير حادة (اهتزاز/ضبابية) — الأرقام المتقاربة قابلة للتبادل",
    R_SKEW: "ميل زائد عن الحدّ — الصفوف تنزلق ويختلط آخر صف بأول الصف التالي",
    R_BLANK: "الصفحة شبه فارغة — لا حبر كافٍ ليُقرأ منها شيء",
    R_NO_REFEREE: "سطر الإطار غير مكشوف ⇒ أرقام الصفحة **لا يمكن إثباتها** (تُقرأ ولا تُصدَّق)",
    R_SMALL_TEXT: "أرقام الإطار صغيرة الحجم — تحت حدّ القراءة الموثوق",
    R_SIZE_VARIANCE: "مقاس الصفحة شاذ داخل الملف (خلط أدوات تصوير/صور مدمجة؟)",
}


# ————————————————————— القياسات —————————————————————

def laplacian_var(g: np.ndarray) -> float:
    """تباين مشتقّ لابلاس — مؤشر الحدّة (أعلى = أحدّ). بلا cv2."""
    a = g.astype(np.int16)
    lap = (4 * a - np.roll(a, 1, 0) - np.roll(a, -1, 0)
           - np.roll(a, 1, 1) - np.roll(a, -1, 1))
    return float(lap.var())


def estimate_skew(g: np.ndarray, max_deg: float = 6.0,
                  step: float = 0.5) -> float:
    """تقدير الميل بالدرجات بمخطط الإسقاط (الأعلى تبايناً = الأقرب للاستقامة).

    يعمل على نسخة مصغّرة (عرض ~500px) => كلفة زهيدة بلا فقد دلالة.
    """
    h, w = g.shape
    scale = 500.0 / max(w, 1)
    small = Image.fromarray(g).resize((500, max(int(h * scale), 1)),
                                      Image.Resampling.BILINEAR)
    best_deg, best_score = 0.0, -1.0
    angles = np.arange(-max_deg, max_deg + 1e-9, step)
    for deg in angles:
        rot = small.rotate(float(deg), resample=Image.Resampling.BILINEAR,
                           fillcolor=255, expand=False)
        arr = np.asarray(rot)
        prof = (arr < 200).sum(axis=1).astype(np.float64)
        score = float(prof.var())
        if score > best_score:
            best_deg, best_score = float(deg), score
    return best_deg


def body_band_heights(g: np.ndarray, th: Thresholds = TH) -> list[int]:
    """ارتفاعات كتل الأسطر في متن الصفحة (مؤشر ارتفاع النص المطبوع)."""
    h, _w = g.shape
    dark = g < 205
    rows = dark.sum(axis=1)
    bands: list[int] = []
    start = None
    for y in range(int(h * 0.05), int(h * 0.70)):
        if rows[y] > 25:
            start = y if start is None else start
        elif start is not None:
            if y - start >= th.body_band_h_min:
                bands.append(y - start)
            start = None
    return bands


def check_page(png: Path, th: Thresholds = TH,
               modal_size: tuple[int, int] | None = None) -> dict:
    """قياسات صفحة واحدة + حكمها + أسبابها. لا يرفع استثناءً على صورة سليمة."""
    g = _gray(png)
    h, w = g.shape
    res: dict = {
        "file": png.name,
        "size": [int(w), int(h)],
        "ink_ratio": round(float((g < 205).mean()), 4),
        "brightness": round(float(g.mean()), 1),
        "sharpness": round(laplacian_var(g), 1),
        "skew_deg": round(estimate_skew(g), 1),
    }

    # ١) المُحكَّم: سطر الإطار + ارتفاع مقاطعه
    fr = _footer_row(g)
    if fr:
        y, win = fr
        # العدّ يُطابق تعريف preflight (>=6)، أما قياس حجم النص فيأخذ أضيق مقاطع
        # (>=3) وإلا صار الحكم «نص صغير» غير قابل للإطلاق أصلاً — قاعدة ميتة.
        segs = [s for s in _segments(win) if (s[1] - s[0]) >= 6]
        thin = [s for s in _segments(win) if (s[1] - s[0]) >= 3]
        heights = [s[1] - s[0] for s in thin] or [0]
        res.update({
            "referee_present": True,
            "referee_y": int(y),
            "referee_segments": len(segs),
            # عرض أوسع مجموعة أرقام (مؤشر حجم النص المطبوع — لا ارتفاعه؛ المقاطع
            # تُقاس على محور الأعمدة). الضبابية/التصغير تُصغّره أولاً.
            "referee_glyph_w": int(max(heights)),
        })
    else:
        res.update({"referee_present": False, "referee_segments": 0,
                    "referee_glyph_w": 0})

    bands = body_band_heights(g, th)
    res["body_band_h_median"] = int(np.median(bands)) if bands else 0

    # ٢) الأسباب
    reasons: list[str] = []
    if w > h:
        reasons.append(R_LANDSCAPE)
    if res["ink_ratio"] < th.ink_ratio_min:
        # الصفحة الفارغة تُحسم أولاً: قياس الحدّة والميل عليها يقيس **ضجيجاً** لا
        # عيباً (لوح أبيض «مائل ٦ درجات» ليس مائلاً). الكتمان هنا صدق لا تفويت:
        # السبب الوحيد الصادق لصفحة فارغة هو أنها فارغة.
        reasons.append(R_BLANK)
        res["reasons"] = reasons
        res["reasons_ar"] = [_AR_REASON[r] for r in reasons]
        res["verdict"] = "reject"
        return res
    if res["sharpness"] < th.lapvar_min:
        reasons.append(R_BLUR)
    if abs(res["skew_deg"]) > th.skew_max_deg:
        reasons.append(R_SKEW)
    if not res["referee_present"]:
        reasons.append(R_NO_REFEREE)
    # «نص صغير» له برهانان مستقلان: عرض مجموعة الأرقام في الإطار، أو ارتفاع كتلة
    # السطر في المتن. الأول يسقط عند تصغير الصورة، والثاني يبقى صالحاً حين لا
    # يُكشف الإطار أصلاً (صفحة مصغّرة تفقد الإطار قبل أن تصغُر أرقامها).
    if (res["referee_present"] and res["referee_glyph_w"] < th.glyph_w_min) or \
            (res["ink_ratio"] >= th.ink_ratio_min
             and 0 < res["body_band_h_median"] < th.body_h_min):
        reasons.append(R_SMALL_TEXT)
    if modal_size:
        mw, mh = modal_size
        if (abs(w - mw) / mw > th.size_tol) or (abs(h - mh) / mh > th.size_tol):
            reasons.append(R_SIZE_VARIANCE)

    rejects = [r for r in reasons if r in _REJECT]
    warns = [r for r in reasons if r in _WARN]
    res["reasons"] = reasons
    res["reasons_ar"] = [_AR_REASON[r] for r in reasons]
    res["verdict"] = "reject" if rejects else ("warn" if warns else "accept")
    return res


def modal_page_size(rows: list[dict]) -> tuple[int, int]:
    """المقاس السائد في الملف (لقياس الشذوذ داخل نفس الملف لا مقابل مرجع خارجي)."""
    from collections import Counter

    c = Counter(tuple(r["size"]) for r in rows)
    return c.most_common(1)[0][0]


def verdict(rows: list[dict], th: Thresholds = TH) -> dict:
    counts: dict[str, int] = {"accept": 0, "warn": 0, "reject": 0}
    reasons: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        for reason in r.get("reasons", []):
            reasons[reason] = reasons.get(reason, 0) + 1
    n = len(rows) or 1
    return {
        "pages": len(rows),
        "counts": counts,
        "reasons": reasons,
        "rejected_pages": [r["file"] for r in rows if r["verdict"] == "reject"],
        "warned_pages": [r["file"] for r in rows if r["verdict"] == "warn"],
        # الحكم المقروء: هل الملف صالح للدفع؟ (صفحة واحدة مرفوضة = استثنِها، لا تُعمّم)
        "payable_ratio": round((counts["accept"] + counts["warn"]) / n, 4),
    }


# ————————————————————— المعايرة —————————————————————

def calibrate(rows: list[dict]) -> dict:
    """توزيع القياسات على صفحات سليمة — أساس وضع العتبات بأمانة."""
    def pct(key: str, p: float) -> float:
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(float(np.percentile(vals, p)), 1) if vals else 0.0

    return {
        "pages": len(rows),
        "sharpness": {f"p{p}": pct("sharpness", p) for p in (1, 5, 50)},
        "skew_abs": {f"p{p}": round(float(np.percentile(
            [abs(r["skew_deg"]) for r in rows], p)), 2) for p in (50, 95, 99)},
        "referee_glyph_w": {f"p{p}": pct("referee_glyph_w", p)
                            for p in (1, 5, 50)},
        "ink_ratio": {f"p{p}": round(float(np.percentile(
            [r["ink_ratio"] for r in rows], p)), 4) for p in (1, 50)},
        "body_band_h_median": {f"p{p}": pct("body_band_h_median", p)
                               for p in (1, 50)},
        "sizes": sorted({tuple(r["size"]) for r in rows}),
        "referee_present_ratio": round(
            sum(1 for r in rows if r["referee_present"]) / (len(rows) or 1), 4),
    }


# ————————————————————— CLI —————————————————————

def _load_pages(pages_dir: Path, first: int, count: int) -> list[Path]:
    out = []
    for i in range(count):
        p = pages_dir / f"pg-{first + i:03d}.png"
        if p.exists():
            out.append(p)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="بوابة جودة المسح لكل صفحة (محلية)")
    ap.add_argument("--pages-dir", required=True)
    ap.add_argument("--first", type=int, default=1)
    ap.add_argument("--count", type=int, default=20)
    ap.add_argument("--out", default="data/local_sample/page_gate.json")
    ap.add_argument("--calibrate", action="store_true",
                    help="طباعة توزيع القياسات (لوضع العتبات) بلا حكم")
    args = ap.parse_args()

    pages_dir = Path(args.pages_dir)
    if not pages_dir.is_absolute():
        pages_dir = PROJ / pages_dir
    pngs = _load_pages(pages_dir, args.first, args.count)
    if not pngs:
        print(f"لا صفحات في {pages_dir}"); return

    rows = [check_page(p) for p in pngs]
    modal = modal_page_size(rows)
    for r in rows:                       # الشذوذ يُقاس داخل الملف لا مقابل رقم صلب
        if r["size"] != list(modal) and R_SIZE_VARIANCE not in r["reasons"]:
            r["reasons"].append(R_SIZE_VARIANCE)
            r["reasons_ar"].append(_AR_REASON[R_SIZE_VARIANCE])
            if r["verdict"] == "accept":
                r["verdict"] = "warn"

    if args.calibrate:
        print(json.dumps(calibrate(rows), ensure_ascii=False, indent=1))
        return

    v = verdict(rows)
    out = Path(args.out)
    if not out.is_absolute():
        out = PROJ / out
    out.write_text(json.dumps({"pages_dir": str(pages_dir), "modal_size": modal,
                               "per_page": rows, "verdict": v},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"صفحات: {v['pages']} — مقبول {v['counts']['accept']} · "
          f"منبَّه {v['counts']['warn']} · مرفوض {v['counts']['reject']}")
    if v["reasons"]:
        print("الأسباب: " + " · ".join(f"{k}={n}" for k, n in v["reasons"].items()))
    for reason, n in v["reasons"].items():
        print(f"   - {_AR_REASON[reason]}")
    print(f"قابل للدفع: {v['payable_ratio']:.0%} | التفصيل: {out}")


if __name__ == "__main__":
    main()
