#!/usr/bin/env python3
"""بوابة الإقفال: تقرأ الملف المُسلَّم من القرص، ولا تثق بمن بناه.

لماذا بوابة واحدة
-----------------
كان عندنا فحوصات محلية كثيرة (أوراكل التذييل لكل صفحة · بوابة أمانة التصدير ·
سجل الادعاءات) ولا **عقد واحد** يقف بين الملف وبين التسليم. هذه البوابة هي ذلك
العقد: تقرأ المصنّف نفسه، تُعيد حساب ما يمكن إعادة حسابه، وتطبع `ALL PASS` أو
تفشل بمؤشر — **ولا يُسلَّم ملف إلا ووراءه ALL PASS**.

الشروط لكل بنك تُقرأ من `profiles/<bank>.json`: الأعمدة، تشريح التذييل، صيغ
الصفر، مجموعات الأرقام، شروط الهوية والفجوة. وتشغيلة بعينها يمكن تجميد أرقامها
الذهبية في ملف محلي (`--golden`) — والأصل أن تُقرأ الأرقام من الورق لا تُكتب بيد.

    python3 tools/verify_close.py --run data/local_sample/slice_629p \
        --xlsx ~/Downloads/rajhi-rag-export-629p.xlsx \
        --profile profiles/al-rajhi.json [--golden <ملف محلي>]
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "src"))

from statement_qa.gap_ledger import identity  # noqa: E402

TOL = Decimal("0.005")
FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(name)


def dec(v) -> Decimal | None:
    if v in (None, ""):
        return None
    try:
        return Decimal(str(v).replace(",", "").replace("٫", "."))
    except (ArithmeticError, ValueError):
        return None


def _measure_stamps(run: Path | str) -> dict:
    """(النموذج · التلقينة) من **الكاش** — المصدر لا ورقةُ الملخص.

    وسبب وجودها: الإعلان في الملخص يحرُس **الحضور** لا **الصدق** — فسطرٌ يقول
    «قارئٌ واحد: X» و«بلا ختم: 0» يمرّ على كوربوسٍ فيه 629 صفحة بلا ختم ومن
    قارئين. فالقيمة تُقابَل بمصدرها، كما تُقابَل كل قيمة أخرى في هذه البوابة.
    """
    import json as _json

    results = Path(run) / "results"
    stamps: set[tuple[str, str]] = set()
    unstamped = pages = 0
    for f in sorted(results.glob("pg-*.json")):
        try:
            c = _json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue          # نقطة غير مقروءة: تُعدّ مفحوصةً لا مختمةً (لا تُخمَّن)
        pages += 1
        model, prompt = c.get("model"), c.get("prompt_version")
        if model and prompt:
            stamps.add((str(model), str(prompt)))
        else:
            unstamped += 1
    return {"stamps": sorted(stamps), "unstamped": unstamped, "pages": pages}


def read_rows(ws) -> list[dict]:
    header = [c.value for c in ws[1]]
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        out.append(dict(zip(header, row)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--profile", default=str(PROJ / "profiles" / "al-rajhi.json"))
    ap.add_argument("--golden", default=None, help="ملف أرقام ذهبية محلي (اختياري)")
    args = ap.parse_args()

    run = Path(args.run)
    book = Path(args.xlsx).expanduser()
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    golden = json.loads(Path(args.golden).read_text(encoding="utf-8")) if args.golden else \
        {k: v for k, v in (profile.get("golden") or {}).items() if not k.startswith("_")}

    if not book.exists():
        print(f"[FAIL] الملف المُسلَّم غير موجود: {book}")
        return 1
    wb = load_workbook(book, data_only=True)

    print("===== الأوراق =====")
    want = profile["artifacts"]["sheets"]
    missing = [s for s in want if s not in wb.sheetnames]
    extra = [s for s in wb.sheetnames if s not in want]
    detail = ("ناقص: " + str(missing) if missing else "") + \
             ("، زائد: " + str(extra) if extra else "")
    check("الأوراق المطلوبة", not missing and not extra,
          detail or str(wb.sheetnames))
    if missing:
        # **ورقة مفقودة = لا حكم.** كان الملف ينهار بـ`KeyError` قبل أن تُطبع
        # `RESULT` — أثرٌ غير مقروء بدل حكم (أمسكه مدقّق خارجي بإعادة تسمية ورقة).
        # والقاعدة: عقد الأوراق يُفحص وجوداً قبل أي قراءة، فلا يُتَّهم الملف
        # بانهيار أداتنا. الفشل يبقى **مغلقاً** (exit 1) ومسمّىً.
        print()
        print("=" * 46)
        print(f"RESULT: {len(FAILS)} FAILURES: {FAILS} — "
              f"لا حكم على ملف ناقص الأوراق: {missing}")
        return 1

    rows = read_rows(wb["الحركات"])
    txns = [r for r in rows if str(r.get("حكم السلسلة على الصفّ") or "").startswith("حركة مثبتة")]
    gaps = [r for r in rows if "قيد فجوة" in str(r.get("حكم السلسلة على الصفّ") or "")]

    print("===== المجاميع والهوية =====")
    sd = sum((dec(r.get("مدين")) or Decimal("0")) for r in rows)
    sc = sum((dec(r.get("دائن")) or Decimal("0")) for r in rows)
    # **الافتتاح من الورق لا من العقد**: الورق يطبع «الرصيد الافتتاحي» في الصفحة
    # الختامية وفي أوّل صفّ. فنأخذه من الملف المُسلَّم (المصدر)، ونستعمل قيمة العقد
    # بديلاً احتياطياً — وإن اختلفا نُعلن الاختلاف بدل أن نمرّ عليه.
    opening = None
    try:
        ws_m = wb["الملخص"] if "الملخص" in wb.sheetnames else None
        if ws_m is not None:
            for row_m in ws_m.iter_rows(values_only=True):
                label_m = str(row_m[0] or "")
                if "الافتتاح" in label_m and (opening := dec(row_m[1])) is not None:
                    break
    except Exception:                                        # noqa: BLE001
        opening = None
    declared = dec(profile["identity"]["opening_default"]) or Decimal("0")
    if opening is None:
        opening = declared
    else:
        check("الافتتاح المقروء من الورق يوافق قيمة العقد",
              abs(opening - declared) <= Decimal("0.005"),
              f"الورق {opening} · العقد {declared}")
    walk = identity(opening, sd, sc)
    closing = None
    # الإقفال المطبوع: من سطر الملخص (رقم الورق) — لا من حسابنا
    for row in wb["الملخص"].iter_rows(min_row=2, values_only=True):
        if str(row[0] or "").startswith("الرصيد الختامي المطبوع"):
            closing = dec(row[1])
    check("رصيد الإقفال مقروء من الملخص", closing is not None, f"{closing}")
    check("الهوية: افتتاح + Σدائن − Σمدين = الإقفال",
          closing is not None and abs(walk - closing) <= TOL,
          f"{walk} مقابل {closing}")

    # مجموع الورق المطبوع (ملخص البنك): من فوتر آخر صفحة مطابقة في التشغيلة
    report = json.loads((run / "slice_report.json").read_text(encoding="utf-8"))
    per_page = {int(e["page"]): e for e in report.get("per_page") or []}
    last_ok = max((p for p, e in per_page.items() if e.get("footer") == "ok"), default=None)
    printed = {}
    if last_ok is not None:
        cache = json.loads((run / f"results/pg-{last_ok:03d}.json").read_text(encoding="utf-8"))
        printed = cache.get("footer") or {}
    if printed:
        check("Σ المدين == المطبوع على الورق",
              abs(sd - (dec(printed.get("debits")) or Decimal("-1"))) <= TOL,
              f"{sd} مقابل {printed.get('debits')}")
        check("Σ الدائن == المطبوع على الورق",
              abs(sc - (dec(printed.get("credits")) or Decimal("-1"))) <= TOL,
              f"{sc} مقابل {printed.get('credits')}")
        check("رصيد الإقفال == المطبوع على الورق",
              closing is not None and abs(closing - (dec(printed.get("balance")) or Decimal("-1"))) <= TOL,
              f"{closing} مقابل {printed.get('balance')}")

    if golden.get("sum_debit") is not None:
        check("Σ المدين == الرقم الذهبي المجمَّد",
              abs(sd - dec(golden["sum_debit"])) <= TOL, f"{sd}")

    print("===== قيود الفجوة =====")
    check("قيود الفجوة قائمة كصفوف", len(gaps) > 0, f"{len(gaps)} قيداً")
    for idx, g in enumerate(gaps, start=1):
        d, c = dec(g.get("مدين")), dec(g.get("دائن"))
        # **يُسمّى القيد بالورق لا بالموقع.** عمود «رقم الصفحة المطبوع» في صفّ القيد
        # يحمل أرقام الأوراق **الغائبة** (فالقيد يمثّل ما بينها) ⇒ الاسم «قيد ص426 · 427».
        # والموقع («الصفحة (ملف)») بديلٌ ثانٍ فقط — لأنه ليس هوية، ولأن بديلاً باسم
        # عمودٍ غير موجود طبع «قيد ص?» في اختبار المدقّق (والمجموعة تحرس حياة الفحص
        # لا صحّة اسمه، فمرّ). **وإن غاب الاثنان فلا علامة بديلة**: ترتيبُ القيد
        # (`#1`) اسمٌ مفهوم — لأن مصنّفاً بلا العمودين كان يُطبع فيه `?` ويمرّ.
        where = g.get("رقم الصفحة المطبوع") or g.get("الصفحة (ملف)")
        name = (f"قيد ص{where} له مقدارا مدين ودائن" if where
                else f"قيد فجوة #{idx} له مقدارا مدين ودائن")
        check(name, d is not None and c is not None, f"{d}/{c}")
    # عدد القيود يجب أن يساوي عدد مجموعات الأوراق الغائبة في تقرير التشغيلة —
    # مقابلة الملف بالدليل، لا تصديق كلامه.
    groups = [p for p, e in (sorted(per_page.items()))
              if e.get("missing_sheets")]
    check("عدد قيود الفجوة == عدد مجموعات الأوراق الغائبة في التشغيلة",
          len(gaps) == len(groups), f"{len(gaps)} قيداً مقابل {len(groups)} مجموعة")
    declared = [g for g in gaps if "الشاهدان متفقان" in str(g.get("حكم السلسلة على الصفّ"))]
    check("كل قيد يُعلن اتفاق شاهديه", len(declared) == len(gaps),
          f"{len(declared)}/{len(gaps)}")

    print("===== نزاهة الصفوف =====")
    neg = [r for r in rows if (dec(r.get("مدين")) or Decimal("0")) < 0
           or (dec(r.get("دائن")) or Decimal("0")) < 0]
    check("لا قيم سالبة في عمودي مدين/دائن", not neg, f"{len(neg)} صفّاً")
    both = [r for r in rows if dec(r.get("مدين")) is not None and dec(r.get("دائن")) is not None]
    check("لا صفّ يحمل الرقمين معاً إلا قيود الفجوة",
          all("قيد فجوة" in str(r.get("حكم السلسلة على الصفّ") or "") for r in both),
          f"{len(both)} صفّاً")
    clash = [r for r in rows if str(r.get("تنبيه") or "").strip()]
    check("لا تناقض وصف↔اتجاه", not clash, f"{len(clash)} صفّاً")

    # **مصدر الإثبات**: عمود «المثبتة بالسلسلة» يحمل في مرساة الفجوة **مبلغاً
    # مطبوعاً** لا تُقفله السلسلة (رفعه مدقّق خارجي) — فالقيمة صحيحة والاسم عليها
    # كاذب. والعلاج صنفٌ: كل حركة تُعلن مصدر إثباتها، ويجب أن يوافق إعلانُها حكمَ
    # السلسلة عليها — وإلا صار الإعلان زينة. (والكشف بالحقن: تزوير مصدر مرساة.)
    mis_declared = [
        r for r in rows
        if (str(r.get("حكم السلسلة على الصفّ") or "").startswith("حركة مثبتة")
            and not str(r.get("مصدر إثبات الحركة") or "").startswith("السلسلة"))
        or (str(r.get("حكم السلسلة على الصفّ") or "").startswith("حركة — مرساة")
            and not str(r.get("مصدر إثبات الحركة") or "").startswith("الورق المطبوع"))]
    no_source = [r for r in rows
                 if str(r.get("حكم السلسلة على الصفّ") or "").startswith("حركة")
                 and not str(r.get("مصدر إثبات الحركة") or "").strip()]
    check("كل حركة تُعلن مصدر إثباتها", not no_source,
          f"{len(no_source)} حركة بلا مصدر من "
          f"{len([r for r in rows if str(r.get('حكم السلسلة على الصفّ') or '').startswith('حركة')])}")
    check("إعلان المصدر يوافق حكم السلسلة (سلسلة ⇄ سلسلة · مرساة ⇄ ورق مطبوع)",
          not mis_declared, f"{len(mis_declared)} صفّاً")

    dates_needed = profile["statement"]["date"].get("require_all_rows", False)
    # ⚠️ مجتمع الفحص كان `txns` (المُثبَتة بالسلسلة وحدها) ⇒ **المرساتان خارج الفحص**
    # — وهما بعينهما الصفّان اللذان استهلكا خمس جولات. فلو فقدت مرساةٌ تاريخها لمرّت
    # البوابةُ وهي تطبع PASS. والمجتمع الصحيح: **كل صفٍّ حكمه يبدأ بـ«حركة»**،
    # والمَراسي داخلة فيه. (اكتشفه المدقّق الخارجي: عددُ البوابة صادقٌ عن مجتمعها
    # لا عن الملف — وهو الصنف نفسه بوجهٍ ثالث: السطر/الفرع/المجتمع.)
    movements = [r for r in rows
                 if str(r.get("حكم السلسلة على الصفّ") or "").startswith("حركة")]
    dated = [r for r in movements if r.get("التاريخ (ميلادي)")]
    # كل عمودين يصفان الشيء نفسه يجب أن يتفقا: صفٌّ أثبتته السلسلة ولا يوافق
    # رقمُه المكتوب رقمَه المطبوع = تناقضٌ داخلي صامت (مرّ ٢٤ مرة قبل أن يراه مدقّق).
    import sys as _sys
    _sys.path.insert(0, str(PROJ / "tools"))
    from to_xlsx import _num as _to_num
    # ⚠️ الدرس: كُتب أولاً بأسماء الباني الداخلية (row_state/printed_movement) بينما
    # `rows` تقرأ **عناوين الأعمدة العربية** — فصار كل .get() يُرجع None، وعبر المرشِّح
    # صفر صفّ، وطبعت البوابة PASS وهي لا تحرس. والفحص الميت أسوأ من الغائب: يُكتب في
    # الوثيقة أنه يحرس. والقاعدة: يُثبَت **بحقن تناقض** — والفارق أن الفحص الحيّ يقول
    # كم صفّاً فحص («من N»)، فتمييزُه عن الميت لا يحتاج قراءة كود.
    contradictory = []
    examined = 0   # العدّ من الحلقة لا من `txns`: المؤكَّدة + مرساتا الفجوة
    for r in rows:
        if not str(r.get("حكم السلسلة على الصفّ") or "").startswith("حركة"):
            continue  # المؤكَّدة ومرساتا الفجوة (والملخص/الافتتاحي خارجها)
        # المقارنة على **المثبتة بالسلسلة** لا على مدين/دائن: الصفّ المؤكَّد يتساويان
        # فيه، ومرساة الفجوة تُثبت مبلغها المطبوع بلا مدين/دائن ⇒ فالمقارنة على
        # الأعمدة المالية كانت تُخرج المرساتين من الفحص — وهما بعينهما الباقيان.
        printed = _to_num(r.get("الحركة كما طُبعت"))
        amount = _to_num(r.get("الحركة المثبتة بالسلسلة"))
        if printed is None or amount is None:
            continue
        examined += 1
        amount = Decimal(str(amount))
        if abs(Decimal(str(printed)) - amount) > Decimal("0.005"):
            contradictory.append(r)
    check("لا تناقض بين «الحركة كما طُبعت» و«المثبتة بالسلسلة»",
          not contradictory,
          f"{len(contradictory)} صفّاً **من {examined} حركة فُحصت**"
          + (f" · مثال ص{contradictory[0].get('الصفحة (ملف)')}" if contradictory else ""))

    # ⚠️ كان `or not dates_needed` ⇒ الشرط مُعطَّل بالعقد (`require_all_rows: false`)
    # فمرّ حذفُ تاريخٍ من حركة مثبتة والبوابة تطبع PASS برمز خروج صفر — **والفحص كان
    # يقول العدد ويُظهر النقص ثم يمرّ**. فالقاعدة: `or` في شرط فحص = بابٌ خلفي،
    # وإعلانُ العدد يكشف الميت بمفتاح خاطئ ولا يكشف الميت بشرطٍ مُعطَّل. صِنفان.
    check("التواريخ: كل صفّ حركة له تاريخ", len(dated) == len(movements),
          f"{len(dated)}/{len(movements)} (الشرط الصارم: {dates_needed})")
    if txns:
        dmin = min(str(r["التاريخ (ميلادي)"]) for r in dated)
        dmax = max(str(r["التاريخ (ميلادي)"]) for r in dated)
        lo, hi = profile["statement"]["date"]["gregorian_range"]
        check(f"النطاق الزمني داخل {lo}–{hi}",
              int(dmin[:4]) >= lo and int(dmax[:4]) <= hi, f"{dmin} → {dmax}")
        if golden.get("date_min"):
            check("النطاق == الرقم الذهبي", dmin.replace("-", "") >= golden["date_min"]
                  and dmax.replace("-", "") <= golden["date_max"], f"{dmin} → {dmax}")

    print("===== محتوى الملخص =====")
    joined = " ".join(str(v) for row in wb["الملخص"].iter_rows(values_only=True)
                      for v in row if v is not None)
    for needle in profile["artifacts"]["summary_must_contain"]:
        # **الإعلان يُطلب في سطرٍ يحمل رقماً لا في ذِكرٍ عابر.** فحص «قيود الفجوة»
        # كان يمرّ لأن سطري المجاميع يقولان «(بعد قيود الفجوة)» — أي أن الملف قد
        # يُسقط سطر القيود نفسه ويبقى الفحص ممرَّاً. وطُلب بدلاً منه سطرٌ عنوانه
        # الفجوة **وفيه قيمتها** — وكشفه الحقن: تسميم وسم السطر لم يُسقط الفحص.
        if "قيود الفجوة" in needle:
            # سطرٌ **يبدأ** بالعنوان (لا سطرٌ يذكره بين قوسين: «Σ المدين (بعد قيود
            # الفجوة)» كان يُمرّر الفحص بعد إسقاط سطر القيود نفسه).
            rows_with_value = [r for r in wb["الملخص"].iter_rows(min_row=2, values_only=True)
                               if str(r[0] or "").startswith(needle) and str(r[1] or "").strip()]
            check(f"الملخص يذكر «{needle}» بعددها وصافيها في سطرها", bool(rows_with_value),
                  f"{len(rows_with_value)} سطراً بقيمة")
            continue
        check(f"الملخص يذكر «{needle}»", needle in joined)
    check("الملخص يعلن حكم الهوية", "مطابق ✓" in joined)
    # ── FM-1: الكوربوس يُعلن بمن قُرئ ────────────────────────────────────────
    # كان الرقم يُنشر بلا نسب: كوربوسٌ بنى نصفه قارئٌ ونصفه آخر يجمع رقمين تحت
    # اسمٍ واحد، ولا شيء في الملف يقول ذلك (D=5: لا رصد). فصار الإعلان فحصاً:
    # سطرٌ يسمّي (النموذج · التلقينة)، وسطرٌ يعدّ ما قُرئ قبل وجود الختم.
    def _summary_row_value(label: str):
        for r in wb["الملخص"].iter_rows(min_row=2, values_only=True):
            if str(r[0] or "").startswith(label):
                return r[1]
        return None

    identity_value = _summary_row_value("هوية القارئ")
    check("الملخص يعلن هوية القارئ (نموذج · تلقينة)",
          bool(identity_value) and "غير مذكور" not in str(identity_value),
          f"{identity_value}")
    unstamped_pages = _summary_row_value("صفحات بلا ختم قارئ")
    check("الملخص يعدّ الصفحات بلا ختم قارئ", unstamped_pages is not None,
          f"{unstamped_pages}")

    # ⚠️ والحضورُ ليس صدقاً: «قارئٌ واحد: X» و«بلا ختم: 0» كانا يمرّان على
    # كوربوسٍ فيه 629 بلا ختم ومن قارئين — لأن الفحص كان يقرأ الورقة وتسألها عن
    # نفسها، ولا يقرأ الختم من الكاش إطلاقاً. فالعلاج هو علاج الجولة السابعة
    # نفسه: **اشترط القيمة وقابِلها بمصدرها.** والمصدر هنا الكاش، وهو في يد
    # البوابة أصلاً (تقرؤه للتذييل).
    measured = _measure_stamps(args.run)
    check("كوربوسٌ واحد بنسبٍ واحد (لا قارئان تحت رقم)",
          len(measured["stamps"]) <= 1,
          f"{len(measured['stamps'])} نسباً: {measured['stamps']}"
          + (f" · بلا ختم: {measured['unstamped']}" if measured["unstamped"] else ""))
    if len(measured["stamps"]) == 1:
        model, prompt = measured["stamps"][0]
        declared_ok = (model in str(identity_value)
                       and prompt in str(identity_value))
        detail = f"الكاش {model} · تلقينة {prompt} — والورقة «{identity_value}»"
    else:
        declared_ok = not any(ch.isalpha() and ch.isascii()
                              for ch in str(identity_value).split("—")[0])
        detail = f"الكاش بلا ختم ({measured['unstamped']} صفحة) — والورقة «{identity_value}»"
    check("هوية القارئ المعلنة توافق الكاش", declared_ok, detail)
    try:
        declared_count = int(str(unstamped_pages).strip())
    except (TypeError, ValueError):
        declared_count = None
    check("عدد الصفحات بلا ختم يطابق الكاش",
          declared_count == measured["unstamped"],
          f"الورقة {unstamped_pages} · الكاش {measured['unstamped']}")
    unproven = wb["ما لم يُثبت"]
    check("ورقة «ما لم يُثبت» قائمة وفيها سطور",
          unproven.max_row >= 2, f"{unproven.max_row - 1} بنداً")

    print()
    print("=" * 46)
    print("RESULT:", "ALL PASS ✓" if not FAILS else f"{len(FAILS)} FAILURES: {FAILS}")
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())
