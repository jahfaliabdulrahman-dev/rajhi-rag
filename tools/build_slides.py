# -*- coding: utf-8 -*-
"""شرائحُ العرض وسيناريوه — PDF عربيٌّ RTL ببوّابةٍ قبل النشر (R92 · البند ٤).

**الأرقامُ من مصادرها لا من الذاكرة:** كلُّ رقمٍ يُشتقّ من `docs/claims.json` أو من قياسٍ مكتوبٍ في
`docs/memory-effect-measurement.md` أو من نقرة الواجهة المقيسة (قراءةُ ١٠ صفحات **$0.2492**).
**والنشرُ ذرّيّ:** يُبنى إلى ملفٍّ شقيق، ويُستبدل الأصلُ **بعد** نجاح البوّابة فقط.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK = pathlib.Path.home() / ".hermes/cache/scratch/r89/slides"
OUT = pathlib.Path.home() / "Downloads" / "شرائح-العرض.pdf"

SLIDES = [
    ("نظامُ قراءة كشوف الحساب — عرضٌ حيّ",
     "<p class='big'>من ورقةٍ ممسوحةٍ إلى إجابةٍ مُدلَّلة</p><p>كشفٌ واحد · قارئٌ نهائيّ: إنسانٌ ينظر · "
     "والذاكرةُ في ملفّ العميل</p>"),
    ("المشكلة",
     "<ul><li>كشوفٌ ممسوحة، وأرقامٌ تُقرأ بالعين فيسقط منها سطر.</li>"
     "<li>سؤالٌ بسيط («كم مجموع السحوبات؟») يحتاج جمعًا يدويًّا خطأُه مكلف.</li>"
     "<li>والمطلوبُ ليس «قراءة» فحسب: بل <b>رقمٍ يُقابَل بالأثر</b>.</li></ul>"),
    ("ما بُني",
     "<ul><li><b>قراءةٌ</b> لكلّ صفحة مع حكمٍ عليها (مطابقة · فجوة · غائبة).</li>"
     "<li><b>دفترُ كشفٍ</b> يحفظ كلَّ صفٍّ متحقَّقٍ منه — الوثيقةُ في حجرٍ واحد.</li>"
     "<li><b>وكيلٌ يستدعي أدواتٍ حسابيّة</b> على الصفوف، لا يجمع بيده.</li>"
     "<li><b>واجهةٌ حيّة</b> + <b>زرُّ تنزيل Excel</b> بنفس كاتب سطر الأوامر.</li></ul>"),
    ("الحُجّة: الدليلُ قبل الرقم",
     "<ul><li>تحت كلّ جوابٍ لوحةٌ تُظهر <b>الصفوفَ التي دخلت في الحساب</b>.</li>"
     "<li>إن تعذّرت الأدواتُ تُفرَّغ اللوحةُ <b>عمدًا</b> ويُقال «لا أدلّة».</li>"
     "<li>والامتناعُ الصحيحُ (صفحةٌ غيرُ موجودة) يُعدّ <b>صوابًا</b> لا نقصًا.</li></ul>"),
    ("الذاكرة: سؤالٌ تابعٌ يُجاب صوابًا — بقياس",
     "<ul><li><b>بذاكرة:</b> «حركاتُ الصفحة ١: ١٠٫٠٠ مدين · ١٥٫٠٠ دائن» ✓</li>"
     "<li><b>بلا ذاكرة:</b> جمعَ الحركاتِ الأربع = ٧٠٫٠٠ ✗ (سؤالٌ آخرُ تمامًا).</li>"
     "<li>والسقفُ مُعلَن: آخرُ ثلاث دورات، وما يُسقطه يُسمّى بعدده.</li></ul>"),
    ("الدفتر: إعادةُ الإنتاج لا الأرشفة",
     "<ul><li>الإكسلُ <b>يُرندَر من الدفتر</b> ⇒ إعادةُ إنتاج الملفّ <b>خليّةً بخليّة</b> ممكنةٌ بعد شهور.</li>"
     "<li>والبوّابةُ تُقابل: ملفُّ الزرّ × ملفّ سطر الأوامر على <b>تشغيلةٍ حقيقيّة</b>.</li></ul>"),
    ("ما تعذّر — يُعلَن ولا يُخفى",
     "<ul><li>صفحةٌ لا يُقرأ تذييلُها: تُسمّى ويُقال «لم يُثبت» — لا تُطمس تحت مجموع.</li>"
     "<li>والمالُ يُخزَّن <b>نصًّا</b> (لا عائمًا) فلا يفقد هللةً في تنسيق.</li></ul>"),
    ("التكلفة: بكلمة صاحبه قبل الإنفاق",
     "<ul><li>قراءةُ <b>١٠ صفحات</b> = <b>$0.2492</b> · سؤالٌ واحد = <b>$0.007863</b> (مقيسان).</li>"
     "<li>وكلُّ إنفاقٍ مدفوعٍ يُقرَّر <b>بكلمة المالك</b> قبل وقوعه.</li></ul>"),
    ("السيناريو الحيّ — خطواتٌ وتوقيت",
     "<ol><li><b>د:٠٠</b> ارفع كشفَ العيّنة (١٠ صفحات).</li>"
     "<li><b>د:٠٠–١:٣٠</b> قراءةٌ وفحصٌ لكلّ صفحة (تُقاس لكلّ صفحة).</li>"
     "<li><b>د:١:٣٠–٢:٠٠</b> اسأل: «كم عدد الحركات في الكشف؟» ⇒ الجوابُ + لوحةُ الأدلّة.</li>"
     "<li><b>د:٢:٠٠–٢:٣٠</b> اسأل تابعًا: «وما مجموع مدينها؟» ⇒ يُحلّ من السابق.</li>"
     "<li><b>د:٢:٣٠–٣:٠٠</b> نزّل الإكسل وافتحه: سبعُ أوراقٍ، وورقةُ «ما لم يُثبت».</li></ol>"
     "<p class='small'>التوقيتُ مبنيٌّ على نقرةٍ مقيسةٍ فعلًا (قراءةُ ١٠ صفحات + سؤالم) — "
     "والفيديو المسجَّل يُنتج منه إن أُريد.</p>"),
    ("أين يقف الآن",
     "<ul><li><b>يعمل ويُقاس:</b> القراءة · الدفتر · الإكسل (سطرُ أوامر وزرّ) · الوكيل بذاكرته · الواجهة.</li>"
     "<li><b>الباقي:</b> كشفُ المالك الكامل (>١٠٠ صفحة لا تقبله الواجهة) ⇒ بعيّنةٍ معتمدة.</li></ul>"),
]


def build_html() -> str:
    c = json.loads((ROOT / "docs" / "claims.json").read_text(encoding="utf-8"))
    n = c["tests_by_env"]
    body = []
    for i, (title, inner) in enumerate(SLIDES, 1):
        mark = f"<div class='mk'>SECMARK{i}</div>" if i > 1 else ""
        body.append(f"<section>{mark}<h1>{title}</h1>{inner}"
                    f"<div class='foot'>اختباراتٌ مقيسة: {n['full']} · والدفعُ بعد بوّابةٍ خضراء</div></section>")
    return ("<!DOCTYPE html><html lang='ar' dir='rtl'><head><meta charset='UTF-8'><style>\n"
            "@page{size:297mm 167mm;margin:0}body{margin:0;font-family:'Geeza Pro','Arial';direction:rtl}\n"
            "section{page-break-after:always;padding:18mm 16mm;height:167mm;box-sizing:border-box;"
            "border-top:6px solid #7c2d12}\n"
            "h1{font-size:24pt;margin:0 0 6mm;color:#7c2d12}\n"
            "ul,ol{font-size:15pt;line-height:1.7}li{margin:2mm 0}\n"
            ".big{font-size:20pt;font-weight:bold}.small{font-size:11pt;color:#555}\n"
            ".foot{position:absolute;bottom:8mm;font-size:9pt;color:#777}\n"
            ".mk{font-size:1pt;color:#fff}\n</style></head><body>\n" + "\n".join(body) + "</body></html>")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    html = WORK / "slides.html"
    html.write_text(build_html(), encoding="utf-8")
    tmp = OUT.with_suffix(".tmp.pdf")
    # **نفسُ مُصيّر الدليل** (Chrome headless) — لا مكتبةٌ أخرى تختلف في العربية.
    rc = subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                         "--headless", "--disable-gpu", "--no-sandbox", "--virtual-time-budget=8000",
                         f"--print-to-pdf={tmp}", html.as_uri()], capture_output=True, text=True)
    if rc.returncode != 0:
        print("فشل البناء:", rc.stderr[-300:])
        return 1
    import pymupdf
    doc = pymupdf.open(tmp)
    text = "\n".join(p.get_text() for p in doc)
    leaks = [w for w in ("**", "##", "|--") if w in text]
    marks = sum(1 for i in range(2, len(SLIDES) + 1) if f"SECMARK{i}" in text)
    print(f"صفحات: {len(doc)} · علامات: {marks}/{len(SLIDES) - 1} · تسريب: {len(leaks)}")
    if len(doc) != len(SLIDES) or leaks:
        print("بوّابةٌ رفضت النشر"); return 1
    shutil.move(tmp, OUT)
    print(f"سُلّم: {OUT} · {OUT.stat().st_size} بايت")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
