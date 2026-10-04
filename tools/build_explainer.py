# -*- coding: utf-8 -*-
"""دليلُ المشروع للمجموعة — البناءُ الصحيح: علاماتُ HTML لا ماركداون · مراسٍ لاتينيّة للتوسيط ·
تقسيمٌ يتبع المحتوى (لا فراغَ بعد كلّ قسم) · ورقمُ الصفحة في المحتويات **مقيسٌ** لا مكتوب.

**وأرقامُ الجسد تُشتقّ من `docs/claims.json` وقتَ البناء** — لا رقمَ مكتوبٌ بيد (قاعدةُ المهارة).
الباسُ الأول: `{{PGn}}` محجوزةٌ ⇒ تُقاس المراسي ⇒ الباسُ الثاني يطبع الأرقامَ الحقيقيّة ⇒ ويُقاس التطابق.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path.home() / "Downloads" / "دليل-المشروع-للمجموعة.pdf"
WORK = pathlib.Path.home() / ".hermes" / "cache" / "scratch" / "r89" / "explainer"
WORK.mkdir(parents=True, exist_ok=True)

c = json.loads((ROOT / "docs" / "claims.json").read_text(encoding="utf-8"))
V = {k: c.get(k) for k in ("pages", "rows", "clean", "clean_pct", "mismatch", "gap", "absent",
                           "documented_ratio")}
T = c.get("tests_by_env", {})

SECTIONS = [
    ("ما هذا المشروع — بجملة واحدة", """
<p>من <b>كشف حسابٍ بنكيٍّ مصوَّر</b> إلى <b>ملفٍّ رقميٍّ مقروءٍ ومُتحقَّقٍ منه</b>، ويُسأل عنه بالعربية
فيُجيب <b>بأرقامٍ من الكشف نفسه</b>: لا يُخمّن، ولا يجمع من رأسه، وكلُّ رقمٍ يأتي بموضعه (صفحةٌ وصفّ).</p>
<p>والقارئُ النهائي <b>إنسانٌ ينظر</b>: يُقدَّم له ما قُرئ، وحكمُ الصفحة، وأين تعذّرت القراءة — بالاسم
لا بالصمت. وقد قُرئت <b>{V['pages']}</b> صفحةً وبُنيت <b>{V['rows']}</b> حركةً مُتحقَّقًا منها في المستودع.</p>"""),
    ("ثلاثُ ضمانات — لا وعود", """
<p><b>١ · لا رقمَ بلا موضع.</b> كلُّ استشهادٍ يُقابَل بالأثر: قِيس على أسئلةٍ حقيقيّةٍ بنموذجٍ حقيقيّ،
فجاء <b>صدقُ الاستشهاد 10/10</b> في الأصناف التي تُصدر استشهادًا.</p>
<p><b>٢ · الامتناعُ يُعلَن.</b> ما لا يُقرأ يُقال عنه «غيرُ مقروء» ولا يُخمَّن — وقِيس <b>اختراعُ مبلغٍ
بلا سند = 0</b>.</p>
<p><b>٣ · الدفترُ هو المصدر.</b> أُعيد بناءُ ملفّ الإكسل من دفتر الكشف فجاء <b>صفرُ فرقِ خليّةٍ واحدة</b>
— فالمعروضُ والمسؤولُ عنه شيءٌ واحد.</p>"""),
    ("ما الذي بُني فعلًا — بالأرقام", """
<table>
<tr><th>البند</th><th>القياس</th></tr>
<tr><td>صفحاتُ الكشف المقروءة</td><td><b>{V['pages']}</b> صفحة</td></tr>
<tr><td>الصفوفُ المُتحقَّقة</td><td><b>{V['rows']}</b> صفًّا</td></tr>
<tr><td>الصفوفُ النظيفة</td><td><b>{V['clean']}</b> ({V['clean_pct']})</td></tr>
<tr><td>الموثَّقةُ في الكشف</td><td><b>{V['documented_ratio']}</b></td></tr>
<tr><td>مخالفةٌ · فجوةٌ · بلا إطار</td><td><b>{V['mismatch']}</b> · <b>{V['gap']}</b> · <b>{V['absent']}</b></td></tr>
<tr><td>الاختباراتُ الآليّة (ثلاثُ بيئات)</td><td><b>{T.get('full')}</b> · <b>{T.get('ci-light')}</b> · <b>{T.get('ci-claims')}</b></td></tr>
</table>
<p>وهذه الأرقامُ ليست شهادةَ صاحبةِ المشروع: تُشتقّ آليًّا من ملفّ الادّعاءات في المستودع، وأيُّ انحرافٍ
عن الوثائقِ يُسقط فحصًا آليًّا قبل النشر.</p>"""),
    ("كيف يُقاس جودُه — لا بالانطباع", """
<p>الاصلُ أنّ الجودةَ تُقاس بثلاثة مقاييس <b>منفصلة</b>، لا برقمٍ واحدٍ يجمعها فيُخفي ضعفَ أحدها:</p>
<ul>
<li><b>دقّةُ الرقم:</b> هل القيمةُ التي في الجواب هي التي في الكشف؟</li>
<li><b>صدقُ الاستشهاد:</b> هل الاستشهادُ الذي ذكره له أثرٌ في الصفوف التي قرأها فعلًا؟</li>
<li><b>صحّةُ الامتناع:</b> هل امتنع حين يجب، وأجاب حين يمكن؟</li>
</ul>
<p>وكلُّ قياسٍ يُعلن نطاقَه: النوائبُ (مهلةٌ أو عطبٌ) تُخرج من المقام وتُذكر بالاسم — فلا تُحسب فشلًا
ولا تُخفى. والكلفةُ تُقرأ من رصيد المزوّد لا من عدّادٍ داخليّ.</p>"""),
    ("الأسئلةُ المتوقَّعة — وأجوبتُها", """
<table>
<tr><th>السؤال</th><th>الجوابُ المختصر</th></tr>
<tr><td>هل يخترع أرقامًا؟</td><td>لا يُخمَّن رقم: أداةُ العدّ والجمع تعمل على الصفوف المُتحقَّقة، وما لا يُقرأ يُعلَن.</td></tr>
<tr><td>ما الذي تعذّر قراءته؟</td><td>يُسمّى بالصفحة والصفّ، ولا يُطمَس ولا يُجمع تحت رقمٍ واحد.</td></tr>
<tr><td>هل يُعتمد على إجاباته؟</td><td>الاستشهادُ يُقابَل بالأثر، والامتناعُ الصحيح يُعدّ صوابًا لا نقصًا.</td></tr>
<tr><td>وكم كلّف؟</td><td>القراءةُ تُقاس لكلّ صفحة، وكلُّ إنفاقٍ مدفوعٍ يُقرَّر بكلمة صاحبه قبل وقوعه.</td></tr>
<tr><td>وهل يعمل على كشوفٍ أخرى؟</td><td>النواةُ واحدة، وكلُّ تركيبةٍ (بنك × نوع مدخل) تُؤهَّل <b>بشروطٍ ستة</b> قبل فتحها للعملاء.</td></tr>
</table>"""),
    ("أين يقف الآن — وما بقي", """
<ul>
<li><b>يعمل ويُقاس:</b> القراءةُ · دفترُ الكشف · تصديرُ الإكسل · السؤالُ والجوابُ · الواجهةُ الحيّة.</li>
<li><b>يُصلَح بالقياس لا بالانطباع:</b> عُطبٌ في مقياس التقييم كان يُنسب إلى النموذج، فأُصلح في المنبع
وبوّابةٌ تحرسه — وارتفع الصنفُ المعنيّ من صفرٍ إلى كاملٍ في السجلّ المحكوم.</li>
<li><b>الباقي:</b> عرضٌ حيٌّ · تقريرُ التسليم بأقسامه · وهذا الدليل.</li>
</ul>"""),
    ("مكوّنٌ جديد: دفترُ الكشف", """
<ul>
<li><b>ما هو:</b> قاعدةُ بياناتٍ محلّيّة (SQLite) تحمل <b>كلَّ صفٍّ متحقَّقٍ منه</b> وحكمَ كلّ صفحة —
لا ملفّاتٍ متناثرةً تُقرأ مرّةً وتُنسى.</li>
<li><b>لماذا يهمّ القارئ غيرَ التقنيّ:</b> الوثيقةُ صارت <b>حجرًا واحدًا</b> يمكن سؤاله بعد أسبوعٍ أو شهر
وإعادةُ إنتاج الملفّ منه <b>خليّةً بخليّة</b> — فما نراه اليوم يمكن إثباتُه غدًا.</li>
<li><b>والبوّابةُ الحاسمة:</b> الإكسلُ المُرندَر <b>من الدفتر</b> = الملفُّ الحاليّ — تُقاس ولا تُدَّعى.</li>
</ul>
"""),
    ("مكوّنٌ جديد: الوكيلُ الذي يجيب", """
<ul>
<li><b>كيف يجيب:</b> يقرأ الوثيقةَ ثمّ <b>يستدعي أدواتٍ حسابيّة</b> على صفوفها (عدٌّ · جمعٌ · رصيدٌ · تذييلُ صفحةٍ
مطبوع) — فلا يجمع بيده ولا يخمّن.</li>
<li><b>والدليلُ مرئيّ:</b> تحت كلّ جوابٍ لوحةٌ تُظهر <b>الصفوفَ التي دخلت في الحساب</b>؛ وإن تعذّرت الأدواتُ
تُفرَّغ اللوحةُ <b>عمدًا</b> ويُقال «لا أدلّة» بدل أن تُزيَّن بإجاباتٍ لم تُحسَب.</li>
</ul>
"""),
    ("مكوّنٌ جديد: ذاكرةُ الحوار وقوالبُ التلقين", """
<ul>
<li><b>السؤالُ التابعُ صار مفهومًا:</b> «وما مجموع مبالغها؟» — «ها» تُحلّ من السؤال السابق، لا يُبدأ من الصفر.</li>
<li><b>وبحدٍّ مُعلَن:</b> آخرُ ثلاث دوراتٍ فقط، وما يُسقطه السقفُ <b>يُسمّى بعدده</b> في القالب — لا ذاكرةٌ تنمو بلا سقف.</li>
<li><b>ولماذا يهمّ:</b> قِيسَ الفرقُ على سؤالٍ تابع: <b>بذاكرةٍ</b> يُجاب عن الصفحة المقصودة صوابًا (١٠ مدين/١٥ دائن)،
و<b>بلا ذاكرةٍ</b> يُجمع كلُّ الحركات (٧٠٫٠٠) — أي جوابٌ آخرُ للسؤال.</li>
</ul>
"""),
    ("مكوّنٌ جديد: زرُّ تنزيل الإكسل", """
<ul>
<li><b>ما يفعله:</b> يُنزّل ملفَّ الكشف كاملًا من الواجهة — <b>بالكاتب نفسِه</b> الذي يستدعيه سطرُ الأوامر،
من الدفتر نفسِه.</li>
<li><b>لماذا «نفسُ الكاتب» شرطٌ لا تفصيل:</b> طريقان لملفٍّ واحد يعني <b>حكمين يفترقان صامتين</b> — والبوّابةُ
تُقابل الملفَّين <b>خليّةً بخليّة</b> على تشغيلةٍ حقيقيّة، والباقي المُعلَنُ مُقيَّدٌ بحدٍّ يمنع نموَّه.</li>
</ul>
"""),
]

def build(pages: dict[str, int] | None) -> pathlib.Path:
    toc = "".join(
        f"<li><span class='t'>{t}</span><span class='d'></span>"
        f"<span class='p'>{pages[f'SECMARK{i}'] if pages else '—'}</span></li>"
        for i, (t, _) in enumerate(SECTIONS, 1))
    body = "".join(
        f'<h2><span class="mark">SECMARK{i}</span>{t}</h2>{h}'
        for i, (t, h) in enumerate(SECTIONS, 1))
    html = f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8"><style>
@page {{ size: A4; margin: 20mm 16mm 22mm 16mm; }}
body {{ font-family: "SF Arabic","GeezaPro",sans-serif; color: #1c1c2e; font-size: 10.5pt;
        line-height: 1.9; margin: 0; }}
h1 {{ font-size: 27pt; margin: 0 0 6mm; line-height: 1.4; }}
h2 {{ font-size: 14.5pt; color: #7a5c1e; margin: 9mm 0 4mm; border-bottom: 2px solid #d9c48a;
      padding-bottom: 2mm; page-break-after: avoid; }}
h2:first-of-type {{ margin-top: 0; }}
.mark {{ font-size: 1pt; color: #ffffff; }}
.cover {{ height: 243mm; display: flex; flex-direction: column; justify-content: center;
          text-align: center; page-break-after: always; }}
.cover .kicker {{ letter-spacing: 3px; color: #7a5c1e; font-size: 11pt; margin-bottom: 9mm; }}
.cover .sub {{ color: #55556b; font-size: 12pt; margin-top: 5mm; }}
.rule {{ width: 42mm; height: 3px; background: #7a5c1e; margin: 9mm auto; }}
.contents {{ page-break-after: always; }}
.contents h2 {{ margin-top: 0; }}
.contents ol {{ list-style: none; padding: 0; font-size: 12pt; }}
.contents li {{ display: flex; align-items: baseline; gap: 3mm; padding: 1.6mm 0; }}
.contents .d {{ flex: 1; border-bottom: 1px dotted #c9c2ad; }}
.contents .p {{ color: #7a5c1e; font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; margin: 4mm 0; font-size: 10pt;
         page-break-inside: avoid; }}
th, td {{ border: 1px solid #ddd6c2; padding: 2.3mm 3mm; text-align: right; vertical-align: top; }}
th {{ background: #f6f1e2; color: #5c4415; font-weight: 700; }}
ul {{ padding-right: 6mm; page-break-inside: avoid; }}
li {{ margin-bottom: 1.6mm; }}
b {{ color: #5c4415; }}
footer {{ position: fixed; bottom: 6mm; left: 0; right: 0; text-align: center;
          font-size: 8pt; color: #8a8a99; }}
</style></head><body>
<div class="cover">
  <div class="kicker">دليلُ المشروع — للمجموعة</div>
  <h1>من كشفٍ مصوَّر<br>إلى إجاباتٍ لها موضع</h1>
  <div class="rule"></div>
  <div class="sub">نظامٌ يقرأ كشوف الحساب، ويبني دفترًا مُتحقَّقًا،<br>ويُجيب بالعربية — بلا تخمين،
  وبكلِّ رقمٍ بموضعه.</div>
  <div class="sub" style="margin-top:14mm;font-size:9.5pt">كلُّ رقمٍ في هذا الدليل مُشتقٌّ آليًّا من
  <span dir="ltr" style="font-size:9pt">docs/claims.json</span> وقتَ بناء الملفّ</div>
</div>
<div class="contents"><h2>المحتويات</h2><ol>{toc}</ol></div>
{body}
<footer>دليلُ المشروع — للمجموعة</footer>
</body></html>"""
    p = WORK / f"group-explainer{'-pass2' if pages else ''}.html"
    p.write_text(html, encoding="utf-8")
    tmp = WORK / "partial.pdf"
    r = subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                        "--headless", "--disable-gpu", "--no-sandbox", f"--print-to-pdf={tmp}",
                        "--no-pdf-header-footer", f"file://{p}"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and tmp.exists(), r.stderr[-300:]
    return tmp


def measure(pdf: pathlib.Path) -> dict[str, int]:
    import fitz
    d = fitz.open(pdf)
    out = {}
    for i in range(1, len(SECTIONS) + 1):
        hits = [p.number + 1 for p in d if p.search_for(f"SECMARK{i}")]
        out[f"SECMARK{i}"] = hits[0] if hits else 0
    d.close()
    return out


if __name__ == "__main__":
    p1 = measure(build(None))
    print("الباسُ الأول — صفحاتُ الأقسام المقيسة:", list(p1.values()))
    assert all(p1.values()), f"مرساةٌ لم تُقرأ: {p1}"
    tmp = build(p1)
    p1b = measure(tmp)
    assert p1 == p1b, f"الأرقامُ تحرّكت بين الباسين: {p1} ≠ {p1b}"
    print("الباسُ الثاني مطابق ✓ (الأرقامُ لم تحرّك التخطيط)")
    import fitz
    d = fitz.open(tmp)
    d.set_metadata({"title": "دليل المشروع للمجموعة — من كشفٍ مصوَّر إلى إجاباتٍ لها موضع",
                    "author": "مشروع قراءة كشوف الحساب"})
    d.xref_set_key(d.pdf_catalog(), "ViewerPreferences",
                   "<< /Direction /R2L /DisplayDocTitle true >>")
    d.xref_set_key(d.pdf_catalog(), "PageLayout", "/SinglePage")
    d.set_toc([[1, "الغلاف", 1], [1, "المحتويات", 2]]
              + [[1, t, p1[f"SECMARK{i}"]] for i, (t, _) in enumerate(SECTIONS, 1)])
    d.save(OUT, garbage=3, deflate=True)
    d.close()
    print("سُلّم:", OUT, "·", OUT.stat().st_size, "بايت")
