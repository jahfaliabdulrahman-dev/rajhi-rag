#!/usr/bin/env python3
"""Keep public numbers DERIVED, never remembered (audit P2-5).

The public documents drifted from their own evidence four separate times: the
README claimed 613 documented pages while the measured number was 621; the QA
checklist claimed 78 tests while 113 existed; PLAN carried an old row count, an
old anchor count and an old cost. Every one of those was caught by a human
reading two files at once — a mechanism that fails silently the moment nobody
feels like reading.

This derives the numbers from the report the run itself wrote (plus the live
test count) and asserts the documents contain them. Local, no API, no cost.

    python3 tools/render_claims.py            # show what it derives and checks
    python3 tools/render_claims.py --check    # exit 1 on any drift
    python3 tools/render_claims.py --write    # refresh docs/claims.json (the
                                              # snapshot CI checks against when
                                              # the local cache is absent)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
# **والرقمُ المنشور = الجولةُ الثانية (قرارُ المالك 2026-10-03 · بعد مراجعة ٨٩):** الكوربوسُ المنشورُ
# قبلها (`slice_629p` · تلقينة v1) لم يعد هو ما يقرأ به التطبيق: `read_rows_vlm` بلا تلقينة ⇒ v2 ⇒ كان
# الرقمُ المنشورُ يوصف تلقينةً لا يستعملها التطبيق. فصارت الأرقامُ العامّةُ تُشتقّ من `slice_629p_v2`،
# **ومعها قسمتُها بالختم** (لا مجموعٌ واحد لكوربوسٍ بنسبين · FM-1 · `reader_declaration` أدناه).
REPORT = PROJ / "data" / "local_sample" / "slice_629p_v2" / "slice_report.json"
RESULTS = PROJ / "data" / "local_sample" / "slice_629p_v2" / "results"
# The CI-visible snapshot. It MUST have a writer: a snapshot nobody regenerates
# drifts silently, and then CI compares a fresh document against a stale copy
# and calls the fresh document the drift (this happened with the test count).
SNAPSHOT = PROJ / "docs" / "claims.json"

# **وللرقم بيئةٌ تُعلَن (مراجعة ٦٧ · حصيلةُ R67-2):** العدُّ يتغيّر بما هو مُثبَّت **وبإصدار المفسّر
# و`pytest` وبصورة العدّاء**؛ وخطوةُ `gate_claims` (`pytest` وحدَه) تجمع أقلَّ من خطوة المجموعة
# (بعد `openpyxl`/`PyYAML`)، وكلتاهما أقلَّ من بيئة المالك الكاملة. **والأرقامُ تُقرأ من اللقطة
# (`tests_by_env`) ولا تُنسَخ هنا (مقعدا المواصفة والبنية · ٦٨د):** قيمتان بقيتا في هذا التعليق
# متقادمتين بعد تحديثهما في اللقطة ⇒ حُذفتا (إغلاقُ الصنف بالحذف لا بحراسة نسخة). **فمقابلةُ رقمَي بيئتين
# مقابلةُ كمّيّتين مختلفتين** — وهي بعينها الخطأُ الذي كشفه إغلاقُ R67-2 أوّلَ مرّة. فاللقطةُ تحمل
# **قياسَ كلّ بيئةٍ بمفتاحها** (`tests_by_env`)، والمفتاحُ تُعلنه الجهةُ المشغِّلة (`RAJHI_CLAIMS_ENV`)،
# **والعددُ المنشور** (`tests`) هو قياسُ بيئة `full` وحدَها (وتُقابَل العلاقةُ داخل الأداة).
CLAIMS_ENV = os.environ.get("RAJHI_CLAIMS_ENV", "full")

# **كائنُ القرار يُستورد في أعلى الملفّ — بلا `try/except` يُخفي** (مقعدُ البنية · مراجعة ٦١): كان
# يُستورد داخل دالّةٍ عبر `sys.path.insert` **ويبتلع الخطأ** فيُعيد `None` ⇒ تُصاغ الوثيقةُ بـ`{None}`
# ويُكتب في اللقطة `null` بصمت. والآن الوحدةُ المجرّدةُ (`tools/gate3.py` — لا تبعيّةَ خارج المكتبة
# القياسية، فلا خدمةَ ولا نموذج) تُستورد بنفس النمط المُعلَن المُستعمل لـ`scale_slice` أدناه.
sys.path.insert(0, str(PROJ / "tools"))
from gate3 import GATE3_DECISION                                    # noqa: E402


def _test_count() -> int | None:
    """عدُّ الاختبارات — ببيئةٍ نظيفة.

    عطلٌ مُعلن كان يُعطي أرقاماً خاطئة (227 · 232 · 233) حين يُستدعى من عمليةٍ
    أخرى: المتغيّرات الموروثة (`PYTHONPATH` خصوصاً) تُغيّر ما يُجمَع. **الوثائق
    ليست البيئة** — فالقياس يُنزع من بيئة الاستدعاء قبل أن يُشغَّل.
    """
    env = {k: v for k, v in os.environ.items()
           if k not in ("PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS")}
    out = subprocess.run([sys.executable, "-m", "pytest", "tests/",
                          "--collect-only", "-q"],
                         cwd=PROJ, capture_output=True, text=True, env=env)
    for line in reversed(out.stdout.splitlines()):
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit() and "test" in parts[1]:
            return int(parts[0])
    return None


def _gate3_price_cap() -> int | None:
    """**سقفُ ثمن الإفراج يُشتقّ من كائنه لا من النثر** (review-60 · R60-1).

    الرقمُ ١٣٣ كان يُكتب بيدٍ في الوثائق — وقد سُحب مرّةً إلى «١٠٠» لأن البوابةَ كانت تقيس مجتمعًا
    ناقصًا. فالآن يُشتقّ من `GATE3_DECISION` (مصدرٌ واحد: **`tools/gate3.py`**) ويُقابَل في موضعين
    معلَنين، فمن غيّر السقفَ في الشيفرة يجد الوثائقَ تحمرّ.

    **وحدُّ الاستيراد (مقعدُ البنية · مراجعة ٦١):** كان يقع في `try/except` يبتلع كلَّ خطأ ويُعيد
    `None`، فيُصاغ الطلبُ ويُكتب في اللقطة `{None} صفحة` **بصمت**. والآن يُستورد **الوحدةَ المجرّدة**
    (`tools/gate3.py`: لا تبعيّةَ خارج المكتبة القياسية) في **أعلى الملفّ** — فإن اختفى كائنُ القرار
    سقطت الأداةُ بالاسم (`ModuleNotFoundError`) لا أن تكتب `null` في وثيقةٍ معلَنة.
    """
    return int(GATE3_DECISION["price_cap_pages"])


# **ونصُّ الكوربوس النظيف يُقرأ من المُنتِج لا يُعاد كتابتُه (مقعدُ البنية · P2):**
# `tools/scale_slice.py` يُصدِر حكمًا نصيًّا دائمًا (`CLEAN_DECLARATION` للنظيف، وما خالفه مختلط)
# ⇒ فالقارئُ هنا يقرأ **الحكمَ** (بالمقارنة بالنصّ النظيف) ولا يعيد اشتقاق شرط الاختلاط؛ ومقابلةُ
# النسختين في `tests/test_public_claims.py` فلا تفترقان صامتتين (وقد سمّى المقعدُ العطب:
# شرطٌ مُعادٌ في موضعين ⇒ سببٌ ثالثٌ في المُنتِج يُنشر ختمًا واحدًا ضدّ إعلان التقرير).
CLEAN_DECLARATION = "كوربوسٌ بنسبٍ واحد"


def _stamp_label(stamp) -> str:
    """ختمُ القارئ نصًّا يُقرأ: الزوجُ (نموذج · تلقينة) لا قاموسٌ خام ولا اسمٌ عامّ."""
    if isinstance(stamp, dict):
        parts = [str(stamp.get(k)) for k in ("model", "prompt_version") if stamp.get(k)]
        return ":".join(parts) or "غير مختم"
    return str(stamp or "غير مختم")


def reader_declaration(rep: dict) -> str:
    """**ما يُنشر عن هوية القارئ — ولا يُجمَع كوربوسٌ بنسبين تحت ختمٍ واحد** (FM-1 · البند ٧).

    **العلّةُ المقيسة:** كان يُنشر `rep["reader_stamp"]` وحدَه، وهو ختمُ **آخر** قراءةٍ لا ختمُ
    الكوربوس. فصفحةٌ تحمل ٦٢٤ سجلًّا قُرئت في سبتمبر **بلا ختم** وخمسةَ سجلاتٍ خُتمت اليوم تُقرأ
    كأنّها من قارئٍ واحد — وهو بعينه ما منعته FM-1 («يُعلن ولا يُجمَع تحت رقمٍ واحد»)، ويكذب معه
    ختمُ الرقم المنشور: يقول تلقينةً لم تُقرأ بها ٦٢٤ صفحة.

    **ومسندُ «الاختلاط» واحدٌ في المُنتِج والقارئ (مقعدُ المعايير):** التقريرُ يُعلن مختلطًا إذا
    وُجدت صفحاتٌ غيرُ مختومة **أو** تعارضَ ختمٌ (`tools/scale_slice.py`: الشرطان معًا) — وكانت
    الدالّةُ تنظر في الشرط الأوّل وحدَه ⇒ تقريرٌ اختلاطُه من التعارض يُنشر منه ختمٌ واحدٌ بينما
    `corpus_declaration` المنقولُ حرفيًّا يقول «مختلط» ⇒ حقلان يتناقضان في اللقطة.

    **والقسمةُ تُشتقّ من فرق عدد الصفحات لا تُكتب بيد**، **ولا يُقال «مختومة» بلا ختمٍ معلَن:**
    تقريرٌ بلا `reader_stamp` (وُجد فعلًا في أرشيف v1) كان يُنتج «٥ مختومة، بختم غير مختم» — نصٌّ
    يناقض نفسَه (سجلُّ backfill يسمّي هذه الحال). فحين يغيب الختمُ يُقال ذلك صريحًا.

    **والضابط:** `tests/test_public_claims.py::test_a_mixed_corpus_is_not_published_under_one_stamp`.
    """
    prov = rep.get("corpus_provenance") or {}
    legacy = int(prov.get("legacy_unstamped_pages") or 0)
    conflicts = int(prov.get("stamp_conflict_pages") or 0)
    raw = rep.get("reader_stamp")
    label = _stamp_label(raw)
    # **والحكمُ من المُنتِج، والعدّانِ بديلٌ احتياطيٌّ لا مسند** (لا يُستعملان إلّا حيث يغيب الحكم —
    # تقريرٌ مصنوعٌ بلا `declaration`): فسببٌ ثالثٌ في المُنتِج يُقرأ مختلطًا هنا بلا تعديلٍ هنا.
    decl = prov.get("declaration")
    # **والتطبيعُ قبل المقابلة** (مقعدُ الجولة الثالثة P3): مسافةٌ أو تشكيلٌ عارضٌ في نصّ الحكم
    # كان يُقرأ مختلطًا خطأً ⇒ فجملةٌ نظيفةٌ بصياغةٍ مختلفة قليلًا تُنتج دعوى اختلاطٍ معدوم.
    decl_s = decl.strip() if isinstance(decl, str) else None
    mixed = (decl_s != CLEAN_DECLARATION.strip()) if decl_s else (legacy > 0 or conflicts > 0)
    if not mixed:
        return label
    declared = decl_s or "يُعلن ولا يُجمَع تحت رقمٍ واحد"
    # **ووجودُ الختم من قيمته لا من نوعها** (مقعدُ البنية P3): ختمٌ بصيغة سلسلةٍ — وهي صيغةٌ
    # تدعمها `_stamp_label` صراحةً — كان يُنشر «غيرُ مُعلَن» عن ختمٍ مُعلَنٍ نصًّا ⇒ نصٌّ يناقض الواقع.
    has_stamp = label != "غير مختم"
    pages = (rep.get("slice") or {}).get("pages_done")
    pieces: list[str] = []
    if legacy > 0:
        pieces.append(f"{legacy} صفحةً غيرَ مختومة (قُرئت قبل تسجيل الهوية)")
        if has_stamp and isinstance(pages, int) and pages - legacy > 0:
            pieces.append(f"{pages - legacy} مختومة")
    elif conflicts > 0:
        pieces.append(f"{conflicts} صفحةً أُعيد قراءتها لتعارض ختم")
    else:
        # **وحكمٌ مختلطٌ بلا عدّادٍ يُسمّيه (سببٌ ثالثٌ مستقبلًا) لا يُسكَت عنه ولا يُخترع له رقم.**
        pieces.append("القسمةُ بالختم غيرُ معلَنة في عدّادات هذا التقرير")
    text = " + ".join(pieces)
    if has_stamp:
        tail = f"بختم {label}"
        if conflicts > 0 and legacy > 0:
            # **وبلا دعوى تضمينٍ غيرِ مُسندة (مقعدُ البنية P3):** «ومن المختومة» كان يفترض
            # `conflicts ⊆ stamped` بلا مقياس؛ فيُقال العددُ بلا نسبةٍ إلى القسمة.
            tail += f" و{conflicts} صفحةً أُعيد قراءتها لتعارض ختم"
    else:
        tail = "وختمُ القارئ غيرُ مُعلَنٍ في هذا التقرير"
    return f"{declared}: {text}، {tail}"


def _split_by_stamp(rep: dict, results: Path) -> tuple[str | None, str | None]:
    """قسمةُ أحكام التذييل بالختم — **(غيرُ المختومة، المختومة)** بصيغةِ «مطابق/المجموع».

    ولماذا في الأداة لا في الوثيقة (صدرُ الملفّ: «Keep public numbers DERIVED, never remembered»):
    القسمةُ صارت جزءًا من الرقم المنشور (البند ٧ · FM-1)، وكانت تُكتب بيدٍ في الوثائق ⇒ انزياحُها
    يفترق صامتًا (`claims()` لا يشترطها). فتُشتقّ من **مصدرَيها الحيّين**: حكمُ كلّ صفحةٍ من التقرير،
    وختمُها من سجلّها في الكاش. والقيمةُ `None` حين ينقص أحدُ الطرفين ⇒ لا دعوى على مقامٍ معدوم.
    """
    per = {p.get("page"): (p.get("footer") or "") for p in (rep.get("per_page") or [])}
    if not per or not results.exists():
        return None, None
    un_n = un_ok = st_n = st_ok = 0
    for f in sorted(results.glob("pg-*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                     # noqa: BLE001 — سجلٌّ غيرُ مقروء لا يُسقط الاشتقاق
            continue
        verdict = per.get(d.get("pg"))
        if verdict is None:
            continue
        if d.get("model") or d.get("prompt_version"):
            st_n += 1
            st_ok += verdict == "ok"
        else:
            un_n += 1
            un_ok += verdict == "ok"
    return (f"{un_ok}/{un_n}" if un_n else None, f"{st_ok}/{st_n}" if st_n else None)


def derive() -> dict | None:
    if not REPORT.exists():
        return None
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    facts = {}
    if RESULTS.exists():
        sys.path.insert(0, str(PROJ / "tools"))
        import scale_slice  # noqa: PLC0415

        facts = scale_slice._cache_facts(RESULTS)
    f = rep["footer"]
    split_un, split_st = _split_by_stamp(rep, RESULTS)
    # **و«لا يُقاس» لا يعني «يُنشَر فراغًا» (مقعدا البنية والمعايير · P2 · ثقبٌ مُثبت):** تقريرٌ
    # مقيسٌ وسجلاتُ صفحاته غيرُ مقروءة ⇒ القسمةُ المنشورةُ غيرُ قابلةٍ للاشتقاق، وكان `--write`
    # يكتب `null` ويمرّ الـCI أخضرَ بلا حارس (`snapshot_drift` لا يُنادى إلّا حيث يُنادى `derive`).
    # فالاشتقاقُ **يُرفض** هنا (رمزُ خروج ٢) بدل أن يُنشَر مقامٌ معدوم — والفشلُ مُغلَقٌ لا مُفتوح
    # (عقيدةُ المُستودع في `_gate3_cap`: «تسقط بالاسم لا أن تُكتب قيمةٌ مخترعة»).
    if (rep.get("per_page") or []) and not (split_un or split_st):
        print(f"  {sys.argv[0]}: التقريرُ موجودٌ ({REPORT}) وسجلاتُ صفحاته غيرُ مقروءة ({RESULTS})"
              " ⇒ قسمةُ القراءتين بالختم غيرُ قابلةٍ للاشتقاق ⇒ **لا تُكتب لقطةٌ بمقامٍ معدوم**.")
        sys.exit(2)
    return {
        # كل رقم معلن مربوطٌ بالزوج الذي أنتجه (FMEA FM-1.4): نموذجٌ وتلقينة — **والكوربوسُ المختلطُ
        # يُنشر بإعلانه وقسمته** لا بختمٍ واحد (`reader_declaration`).
        "reader_stamp": reader_declaration(rep),
        "corpus_declaration": (rep.get("corpus_provenance") or {}).get("declaration"),
        # **وقسمةُ القراءتين جزءٌ من المنشور** (البند ٧): تُشتقّ هنا وتُقابَل في `claims()`.
        "split_unstamped": split_un,
        "split_stamped": split_st,
        "pages": rep["slice"]["pages_done"],
        "rows": rep["totals"]["rows"],
        "clean": rep["totals"]["clean"],
        "clean_pct": f"{rep['totals']['clean_ratio']:.1%}",
        "ok": f["ok"], "mismatch": f["mismatch"], "gap": f["gap"],
        "absent": f["absent"], "unchecked": f["unchecked"],
        "documented_ratio": f"{f['ok']}/{rep['slice']['pages_done']}",
        "clean_ratio": (f"{rep['totals']['clean']}/{rep['totals']['rows']}"),
        "recoveries": len(facts.get("recoveries", [])),
        "rereads": len(facts.get("rereads", [])),
        "arbitrations": len(facts.get("arbitrations", [])),
        "median_page_s": facts.get("median_page_s"),
        "tests": _test_count(),
        # **ومصدرٌ ثالثٌ مُعلَن**: كائنُ قرار البوابة (٣) — يُشتقّ منه سقفُ الثمن ويُقابَل في الوثائق.
        "gate3_price_cap_pages": _gate3_price_cap(),
    }


def _env_values(d: dict) -> dict:
    """**دعاوى البيئات تُبنى في المسارين (مقعدُ المواصفة F3 · ٦٨د):** `derive()` — مسارُ شجرة المالك —
    لا يحمل `tests_by_env`، فكانت دعاوى البيئات تُبنى في مسار اللقطة وحدَه ⇒ وثيقةٌ رقمُ بيئتها متقادمٌ
    **تمرّ محليًّا** حتى يراها الـCI. فصار المصدرُ المُمرَّر، وإلّا فاللقطةُ الملتزمة: فالدعوى قائمةٌ في
    المسارين، والانزياحُ يُحمرّ في الموضع الذي يُحرَّر فيه الرقم."""
    tb = d.get("tests_by_env")
    if not tb and SNAPSHOT.exists():
        try:
            tb = (json.loads(SNAPSHOT.read_text(encoding="utf-8")) or {}).get("tests_by_env")
        except (OSError, ValueError):
            tb = None
    return tb or {}


def snapshot_split_missing(d: dict) -> list[str]:
    """**هل في اللقطة قسمةٌ مشتقّةٌ تُدخل الدعوةَ على الوثيقة؟** — حارسُ الثقبِ الصامت.

    **العِلّةُ المقيسة (مقعدا الجولة الثالثة · اثنان استقلًّا):** دعوتا القسمة في `claims()` مشروطتان
    بوجود المفتاح، فحذفُهما من اللقطة **يُسقط الحارسَ بصمت** و`check` يمرّ أخضر — وسبيلٌ حقيقيٌّ
    يُنتجه: تقريرٌ موجودٌ وسجلاتُ صفحاته غيرُ مقروءة (وقد صار الرفضُ يُغلق هذا الآن: `derive` تخرج ٢).

    **والحدُّ الذي ضُبط أخيرًا:** المطلوب **طرفٌ واحدٌ مشتقٌّ على الأقل**، لا الطرفان. فالشرطُ الأوّل
    («يُعلن كوربوسًا مختلطًا ⇒ المفتاحان معًا») كان يُحمرّ زورًا على كوربوسٍ **نظيف** (طرفُه غيرُ المختوم
    لا مجتمعَ له ⇒ `None`) وعلى أحاديّ الطرف (`legacy` وحدَه · تعارضٌ وحدَه · تقرير `v1`: `('621/629', None)`)
    — قِيس على الأربعة، وكلُّها مشروعة. والطرفُ القائمُ وحدَه يكفي لدخول الوثيقة في الحرس.
    """
    if not d.get("corpus_declaration"):
        return []
    if d.get("split_unstamped") or d.get("split_stamped"):
        return []
    return ["split_unstamped|split_stamped"]


def claims(d: dict) -> list[tuple[str, str, str]]:
    """(file, must-contain, label) — the literal a reader will see."""
    return [
        ("README.md", d["documented_ratio"], "نسبة الصفحات الموثّقة"),
        ("README.md", d["clean_ratio"], "نظافة السلسلة"),
        ("README.md", d["clean_pct"], "نسبة النظافة المئوية"),
        # **وقسمةُ القراءتين تُقابَل أيضًا (البند ٧ · FM-1 · مقعدا المعايير والبنية):** كانت
        # القسمةُ تُكتب بيدٍ في الوثائق ولا يشترطها شيء ⇒ انزياحُها يفترق صامتًا، وهو صنفُ «نسختين
        # من الحقيقة». **وكلُّ طرفٍ يُشترَط على حِدته** (مقعدُ البنية P2): العطفُ `and` كان يُسقِط
        # طرفًا صحيحًا قائمًا إذا غاب أخوه (قِيس على تقرير v1 الحيّ: `('621/629', None)` ⇒ تُسقَط
        # دعوى `621/629` وهي قائمة). ولا تُدَّعى قيمةٌ لم تُشتقق (المفتاحُ غائبًا أو `None`).
        *([("README.md", d["split_unstamped"], "قسمةُ القراءتين — غيرُ المختومة (FM-1)")]
          if d.get("split_unstamped") else []),
        *([("README.md", d["split_stamped"], "قسمةُ القراءتين — المختومة (FM-1)")]
          if d.get("split_stamped") else []),
        ("PLAN.md", d["documented_ratio"], "نسبة الصفحات الموثّقة"),
        ("PLAN.md", d["clean_ratio"], "نظافة السلسلة"),
        ("PLAN.md", f"{d['recoveries']} مرساة", "عدد المراسي المُستدركة"),
        ("PLAN.md", f"{d['rereads']} إعادة قراءة", "عدد إعادات القراءة"),
        ("docs/QA_CHECKLIST.md", f"حالياً {d['tests']}", "عدد الاختبارات"),
        # **وأرقامُ البيئات المنشورة تُقابَل بلقطتها (مقعدا المعايير والبنية · ٦٨د · T5):** كانت قيمتا
        # `ci-light`/`ci-claims` مكتوبتين بيدٍ في الوثيقة **بلا ربطٍ باللقطة** ⇒ تتقادمان بصمت (وهو ما
        # وقع فعلًا: بقيت قيمةٌ متقادمةٌ في موضعٍ وحدّثتُ الآخر). فالآن كلُّ مفتاحٍ في `tests_by_env` له دعوى
        # على الوثيقة بصيغتها المنشورة، والانزياحُ يُحمرّ البوّابةَ.
        *[("docs/QA_CHECKLIST.md", f"⇒ **{v}**", f"قيمةُ بيئة `{e}` المنشورة")
          for e, v in sorted(_env_values(d).items())],
        # The ABOUT screen said «about 1.6% of 629 pages» long after the project
        # accounted for every page: the number a stranger reads first had no
        # guard at all (external audit).
        ("app.py", f"{d['ok']} صفحة", "الصفحات المطابقة بإطارها (شاشة ABOUT)"),
        # **وسقفُ ثمن الإفراج يُقابَل في موضعين** (review-60 · R60-1): الرقمُ ١٣٣ كان يُكتب بيدٍ،
        # فسُحب مرّةً إلى «١٠٠» لمّا قاست البوابةُ مجتمعًا ناقصًا. والصيغةُ تحمل الرقمَ **معناه**
        # (سقفُ ثمنِ الإفراج) فلا يُنسَخ رقمٌ آخر في مكانه؛ والمصدرُ كائنُ القرار لا نصّ.
        ("docs/EVAL_PACK.md", f"سقفُ ثمنِ الإفراج {d.get('gate3_price_cap_pages')} صفحة",
         "سقفُ ثمن الإفراج (البوابة ٣)"),
        ("docs/GATES.md", f"سقفُ ثمنِ الإفراج {d.get('gate3_price_cap_pages')} صفحة",
         "سقفُ ثمن الإفراج (سجلّ البوابات)"),
    ]


def check(d: dict) -> list[tuple[str, str, str]]:
    """-> [(file, missing_claim, label)] for every drift."""
    drifts = []
    for rel, needle, label in claims(d):
        path = PROJ / rel
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if needle not in text:
            drifts.append((rel, needle, label))
    return drifts


def snapshot_drift(d: dict) -> list[tuple[str, object, object]]:
    """-> [(key, في اللقطة, في الاشتقاق)] — **البوّابةُ التي كانت عمياء**.

    كان `check()` يقابل الوثائقَ بالاشتقاق الحيّ **فقط**، ولا يقرأ اللقطةَ الملتزمة التي يقرأها CI ⇒
    لقطةٌ متقادمة (٥٩٠ مقابل ٦٠٢) تمرّ محليًّا وتسقط في نسخةٍ نظيفة. اللقطةُ الآن **شاهدٌ يُقابَل** لا حجرٌ
    يُوثق به.
    """
    if not SNAPSHOT.exists():
        return [("<لقطة>", "غائبة", "مطلوبة")]
    try:
        old = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except Exception as e:                                    # noqa: BLE001
        return [("<لقطة>", f"غيرُ مقروءة: {type(e).__name__}", "مطلوبة")]
    return [(k, old.get(k), v) for k, v in d.items() if old.get(k) != v]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any public document drifts from the report")
    ap.add_argument("--write", action="store_true",
                    help="refresh docs/claims.json from this derivation")
    args = ap.parse_args()
    d = derive()
    if d is None:
        # **بلا تقريرٍ لا يُصمت** (مراجعة ٥٠ · مقعدا Standards وSpec): كان الخروجُ هنا يسبق كلّ مقابلة ⇒
        # خطوةُ CI المسمّاة «اللقطة» كانت تقابل **لا شيء** (rc=0 ولقطةٌ مسمومة). الآن تُقابَل **اللقطةُ
        # الملتزمةُ بالوثائق** — وهو ما يفعله `tests/test_public_claims.py` في غياب الكاش — فيحمرّ على CI.
        if not SNAPSHOT.exists():
            print(f"لا تقرير مقيس هنا ({REPORT}) ولا لقطةٌ ملتزمة — لا شيء يُحرس.")
            sys.exit(0)
        snapdoc = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        # **«المنشور = قياسُ بيئة `full`» محروسًا (مقعدُ البنية · جولة ٦٧):** كان `tests` مربوطًا
        # بالوثيقة، و`tests_by_env[البيئة النشطة]` بالسياق، **ولا شيءَ يربط الاثنين** ⇒ فتعديلٌ يدويّ
        # متزامن في اللقطة والوثيقة يمرّ أخضرَ في الـCI (لأنّ الـCI يقيس `ci-light`، والوثيقةَ تُقابَل
        # بـ`tests`). فالعلاقةُ المُعلَنة تُقابَل هاهنا، فلا يبقى فراغٌ في مسار الـCI.
        _full = (snapdoc.get("tests_by_env") or {}).get("full")
        if _full is not None and snapdoc.get("tests") != _full:
            print(f"⛔ فشلٌ مُغلَق — العددُ المنشور `tests`={snapdoc.get('tests')!r} ≠ قياسُ بيئة `full` "
                  f"({_full!r}): الاثنان يجب أن يتطابقا (تُصحَّح اللقطةُ بـ`--write` في بيئة `full`).")
            sys.exit(1)
        # **وللقطةِ كاتبٌ حتى بلا تقريرٍ مقيس (R66-1 · مراجعة ٦٦):** كان `--write` لا يعمل إلّا بتقريرٍ
        # مقيس ⇒ فاللقطةُ في بيئة الـCI **بلا كاتب**، وتُقابَل بالوثيقة وحدَها ⇒ يتقادمان معًا بصمت.
        # **وحدُّ الكتابة يُعلَن:** يُحدَّث ما يُقاس هنا (`tests` من `_test_count()`)، وبقيةُ الحقول لا تُمسّ.
        if args.write:
            if CLAIMS_ENV == "off":
                print("⚠ بيئةٌ تُعلن أنّها لا تقيس (`off`) ⇒ لا كتابة.")
                sys.exit(2)
            live = _test_count()
            if live is None:
                print(f"⚠ تعذّر العدُّ الحيُّ في بيئة `{CLAIMS_ENV}` ⇒ لا كتابة. [الرمز ٢ = تعذّرُ القياس]")
                sys.exit(2)
            env_map = dict(snapdoc.get("tests_by_env") or {})
            before = env_map.get(CLAIMS_ENV)
            env_map[CLAIMS_ENV] = live
            snapdoc["tests_by_env"] = env_map
            if CLAIMS_ENV == "full":
                snapdoc["tests"] = live            # «العددُ المنشور» = قياسُ البيئة الكاملة
            SNAPSHOT.write_text(json.dumps(snapdoc, ensure_ascii=False, indent=1) + "\n",
                                encoding="utf-8")
            print(f"[claims] كُتبت اللقطةُ بلا تقريرٍ مقيس: tests_by_env[{CLAIMS_ENV}] "
                  f"{before!r} ⇒ {live!r}"
                  + (" · و`tests` (العددُ المنشور) تبعه" if CLAIMS_ENV == "full" else "")
                  + f" | **وحدُّ الكتابة مُعلَن:** بقيةُ الحقول تحتاج تقريرًا مقيسًا "
                    f"(`{REPORT.relative_to(PROJ)}`) ولم تُمسّ.")
        # **والعددُ المنشور يُقاس حيًّا حتى بلا تقرير (R66-1 · مراجعة ٦٦):** مقابلةُ الوثيقةِ باللقطة
        # وحدَهما تجعل الانزياحَ **غيرَ مرئيٍّ في CI** — لقطةٌ متقادمةٌ توافق وثيقةً متقادمةً بالعدد نفسه —
        # و`_test_count()` لا يحتاج كاشَ التصريح. **قِيس قبل الإغلاق:** لقطةٌ متقادمةٌ والعدُّ الحيّ مخالفٌ لها
        # والحكمُ «توافق» (`rc=0`) ⇒ صار يُقاس.
        if CLAIMS_ENV == "off":
            # **وبيئةٌ تُعلن أنّها لا تقيس (R67-2 · حصيلةُ القياس):** خطوةُ `gate_claims` تجري **قبل**
            # تثبيت `openpyxl`/`PyYAML` ⇒ جمعُها جزئيٌّ: في **مهمّة الـCI نفسِها** تجمع هذه الخطوةُ أقلَّ
            # من خطوة المجموعة (وكان الرقمان قبل ثلاثة ضوابط أقلَّ — والقياسُ يتحرّك مع المدى،
            # ولذلك يُقاس ولا يُنقل؛ ومقعدُ المعايير قاس أنّ هذين الرقمين بقيا متقادمين هنا في جولةٍ
            # حدّثت الموضعَ الآخر ⇒ فصارا معًا من قياس الـCI نفسه). فمقابلةُ أيّ منهما بالرقم المنشور
            # مقابلةُ كمّيّتين مختلفتين.
            # فالقياسُ الحيّ هنا **مُعلَّقٌ بإعلانٍ** (لا تخطٍّ صامت)، والوثيقةُ تُقابَل بلقطتها، والقياسُ
            # الحيّ يجري في الخطوة التي **أعلنت بيئتها** (وتحرسها ضابطةُ المجموعة).
            print("ℹ القياسُ الحيُّ **مُعلَّقٌ بإعلان** في هذه الخطوة (RAJHI_CLAIMS_ENV=off · تبعيّاتٌ جزئيّة): "
                  "تُقابَل الوثيقةُ بلقطتها، والقياسُ الحيّ في الخطوة التي أعلنت بيئتها.")
        else:
            live = _test_count()
            if live is None:
                # **ورمحُ الخروج ٢ لا ١ (مقعدُ المعايير · جولة ٦٧):** قاعدتُنا المُعلَنة في `docs/GATES.md`
                # تفصل: «١ = تحوّل/غياب · ٢ = تعذّرُ القياس» — وهذا تعذُّرُ قياسٍ لا تحوّل ⇒ رمزُه ٢.
                print("⛔ فشلٌ مُغلَق — تعذّر قياسُ العدد حيًّا (لا `pytest` في هذه البيئة): لا يُقابَل "
                      "رقمٌ برقمٍ لا يُقاس. ثبّت `pytest` في الخطوة نفسِها التي تُشغّل هذا الفحص (R67-2). "
                      "[الرمز ٢ = تعذّرُ القياس — `docs/GATES.md`]")
                sys.exit(2)
            expected = (snapdoc.get("tests_by_env") or {}).get(CLAIMS_ENV)
            if expected is None:
                print(f"⛔ فشلٌ مُغلَق — بيئةُ القياس `{CLAIMS_ENV}` غيرُ مُعلَنةٍ في اللقطة "
                      f"(المُعلَن: {sorted((snapdoc.get('tests_by_env') or {}))}) ⇒ سجِّل قياسَها بـ`--write`.")
                sys.exit(1)
            if expected != live:
                print(f"⚠ عددُ `{CLAIMS_ENV}` في اللقطة {expected!r} ≠ المعدود حيًّا {live!r} "
                      f"⇒ `--write` (والوثيقةُ تُصحَّح في سطرها)")
                sys.exit(1)
        sdrifts = check(snapdoc)
        if sdrifts:
            print("⚠ الوثائقُ تخالف لقطتها الملتزمة:")
            for rel, needle, label in sdrifts:
                print(f"  {rel}: تفتقد {needle!r}  ({label})")
            sys.exit(1)
        print("الحكم: الوثائقُ توافق لقطتها الملتزمة (لا تقريرٌ حيّ هنا).")
        sys.exit(0)
    print("[claims] الأرقام المشتقّة من تقرير التشغيل:")
    for k, v in d.items():
        print(f"  {k}: {v}")
    if args.write:
        # **الكاتبُ لا يمحو ما أُعلِن (مقعدا المعايير والبنية · جولة ٦٧):** كان هذا الفرعُ يكتب مخرَجَ
        # `derive()` كما هو، وهو لا يحمل `tests_by_env` ⇒ فـ`--write` (وهو العلاجُ الذي توصي به رسالةُ
        # الانزياح نفسُها) **يمحو خريطةَ البيئات**، ثم تفشل خطوةُ الـCI مُغلَقةً على «بيئةٍ غير مُعلَنة»
        # — أي أنّ الكاتبَ يهدم ما يحرسه الفشلُ المُغلَق. فالمفاتيحُ المُعلَنة تنجو، ويُسجَّل فيها
        # قياسُ البيئة النشطة (والمنشورُ `tests` يبقى قياسَ `full` وحدَه).
        if CLAIMS_ENV == "off":
            print("⚠ بيئةٌ تُعلن أنّها لا تقيس (`off`) ⇒ لا كتابة.")
            sys.exit(2)
        d["tests_by_env"] = {**(json.loads(SNAPSHOT.read_text(encoding="utf-8")).get("tests_by_env") or {}),
                             CLAIMS_ENV: d.get("tests", _test_count())}
        SNAPSHOT.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        print(f"\nكُتبت اللقطة: {SNAPSHOT.relative_to(PROJ)} "
              f"(مشتقّة من التقرير، لا مكتوبة بيد) · وقياسُ بيئة `{CLAIMS_ENV}` سُجِّل في المفاتيح.")
    # **اللقطةُ شاهدٌ يُقابَل** (مراجعة ٥٠ · CI): كانت `check` تقابل الوثائقَ بالاشتقاق الحيّ وحده،
    # فلا ترى لقطةً متقادمة يقرأها CI ⇒ البوّابةُ تمرّ محليًّا وتسقط هناك.
    snap = snapshot_drift(d)
    if snap:
        print("\n⚠ اللقطةُ الملتزمة متقادمة (CI يقرأ اللقطةَ لا الاشتقاقَ الحيّ):")
        for k, o, n in snap:
            print(f"  docs/claims.json: {k}: اللقطة {o!r} ≠ الاشتقاق {n!r} ⇒ `--write`")
        if args.check:
            sys.exit(1)
    drifts = check(d)
    if not drifts:
        print("\nالحكم: كل رقم معلن يطابق مصدره.")
        sys.exit(0)
    print("\n⚠ انزياح بين الوثيقة ومصدرها:")
    for rel, needle, label in drifts:
        print(f"  {rel}: تفتقد {needle!r}  ({label})")
    sys.exit(1 if args.check else 0)


if __name__ == "__main__":
    main()
