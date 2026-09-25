#!/usr/bin/env python3
"""Pre-delivery QA gate for the Al Rajhi statement app (rajhi-rag).

Run BEFORE every delivery claim ("تم", "يعمل", "جاهز"):

    source .venv/bin/activate
    python tools/qa_gate.py --quick    # offline: tests + parser goldens + wiring
    python tools/qa_gate.py --full     # + live end-to-end run of the sample PDF

Exit 0 = all gates pass; any FAIL blocks delivery.

The --full gate locks VALUES that were verified by eye against the document
renders (page 1: opening dots=0.00 → transfer +300.00 → 300.00 → 200.00 →
100.00; page 2: 0.00 → +50.00). Do NOT edit those constants without
re-verifying against the page image — that visual check is the entire point
(the chain stays "clean" even when EVERY value is ×100 wrong).
"""
from __future__ import annotations

import argparse
import http.client
import re
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent

# The two thresholds a NEW statement must clear before calibration is complete.
# They used to be bare numbers inside assertions, so a less dense sample failed
# the gate with no explanation of what to change (audit P3-11). Calibration
# steps for a new file are listed in docs/ONBOARDING_NEW_FILE.md §3.
MIN_ROWS = 95                 # rows the 10-page sample must yield (≈100–104)
MIN_FOOTER_COMPARABLE = 9     # pages whose printed totals could be compared
#: **وسمُ اللاحتميّة — مصدرٌ واحد (نقلةُ مقعد البنية · مراجعة ٥٩):** كان الحرفُ مكتوباً هنا وفي حارس
#: السجلّ (`tests/test_flake_ledger.py`) ⇒ إعادةُ تسميته تُعمي السجلَّ **صامتاً** (صفرُ تشغيلٍ مُلوَّث =
#: أخضرُ كاذب). فيُبنى السطرُ بهذا الثابت، ويستورده الحارسُ من هنا.
FLAKY_MARK = "[flaky_read]"
sys.path.insert(0, str(PROJ / "src"))

RESULTS: list[tuple[str, bool, str]] = []


def gate(name: str, fn) -> None:
    try:
        detail = fn()
        RESULTS.append((name, True, detail or ""))
    except AssertionError as e:
        RESULTS.append((name, False, str(e)))
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(e).__name__}: {e}"))


def g_tests() -> str:
    # **العلّةُ مُثبتة:** بيئةُ التشغيل تحمل `PYTHONPATH=…/.hermes/hermes-agent` وفيه مجلدُ
    # `tools/`؛ وكان `tools` عندنا حزمةَ namespace فيُخزَّن بمسار الطرف الآخر ⇒
    # `ModuleNotFoundError: No module named 'tools.eval_pack'` (9 أخطاء جمع). والعلاجُ من
    # طبقتين: `tools/__init__.py` (حزمةٌ نظامية) **وتنقيةُ بيئة الأبناء هنا**.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=PROJ, capture_output=True, text=True, timeout=180, env=env)
    tail = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else "no output"
    assert out.returncode == 0, f"pytest failed: {tail}"
    return tail


#: **الرموزُ الذهبية للمُحلّل** — موضعٌ واحد يقرؤه الضابطُ والبوّابةُ معًا، فلا يفترقان صامتين.
#: **والضابطُ في وحدةٍ خفيفةٍ مُدرَجةٍ في الـCI:** `tests/test_gate_goldens.py` — وليست داخل
#: `tests/test_parser.py` لأنّ ذاك يستورد `statement_qa.parser` وفيه `import polars` فيسقط الـCI الخفيف
#: (قياسٌ مؤرَّخ: تشغيلُ الـCI على `de00196` ⇒ `ModuleNotFoundError: No module named 'polars'` · `rc=2`).
#: **والقاعدةُ الحاكمة** موثّقةٌ في `src/statement_qa/legacy/arabic_digit_parser.py:19`
#: («لا نقطةَ ⇒ انظر آخر فاصلة: أكثرُ من ٣ أرقامٍ بعدها ⇒ النقطةُ ضاعت») — فمَن بدّل قيمةً هنا بدليلٍ
#: يُبدّلها في الوثيقة والضابط أيضًا، وإلّا **سقط الضابطُ في الـCI** (والاتجاهان — قائمةُ الـCI وقائمةُ
#: `docs/GATES.md` — يُقابَلان تساويًا في `tests/test_gate_registry.py`).
#: **وسببُ استخراجها:** بوّابةٌ بقيمةٍ خاطئة بقيت **حمراءَ من 2026-09-22 22:29 إلى 2026-09-25 07:03
#: (≈٢٫٤ يومًا · والالتزامُ المُدخِل هو `c7b5483`)** حتى صار الأحمرُ عاديًّا — والعلّةُ أنّ جدولَ البوّابة
#: كان **نسخةً ثانية** من الحقيقة بلا ضابطٍ يقابله.
PARSER_GOLDENS: dict[str, str] = {
    "٣٠٠,٠٠": "300.00",      # comma-as-decimal (old-era prints)
    ".,..": "0",             # printed zero as dots — never None
    "٦١,١٦٥١٢": "61165.12",   # lost decimal dot (owner's golden rule ⇒ 61,165.12)
    "١١٩.٠٠-": "-119.00",    # trailing minus — sign must survive
    "٧٩٨٢٫٦٣": "7982.63",    # new-era thousands + halalas
    "٧٤٥٣٫٥٧": "7453.57",    # Persian digits mixed in
}


def g_parser_goldens() -> str:
    from statement_qa.vlm_reader import _parse_amount as p

    for tok, want in PARSER_GOLDENS.items():
        got = p(tok)
        assert got == Decimal(want), f"{tok!r} -> {got} (want {want})"
    assert p(None) is None and p("") is None
    return f"{len(PARSER_GOLDENS)} golden tokens + nulls"


def _status(port: int):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/")
    r = c.getresponse()
    stat, loc = r.status, r.getheader("Location")
    c.close()
    return stat, loc


def g_service() -> str:
    stat, _ = _status(7860)
    assert stat == 200, f"app :7860 -> HTTP {stat}"
    return "app :7860 -> 200"


def g_surface_redirect() -> str:
    stat, loc = _status(7867)
    assert stat == 302 and loc and ":7860" in loc, f":7867 -> {stat} {loc}"
    return f":7867 -> 302 {loc}"


def _e2e_measure(pdf) -> dict:
    """قراءةٌ واحدةٌ كاملةٌ من الخدمة الحيّة: تُعيد القياسات ولا تُصدر حكمًا.

    (والحكمُ في `decide_two_runs` — دالّةٌ خالصةٌ تُقاس بسمٍّ في `tools/guard_bite_sweep.py` م١٣.)
    """
    from gradio_client import Client, handle_file

    res = Client("http://127.0.0.1:7860", verbose=False).predict(
        handle_file(str(pdf)), api_name="/process_pdf")
    summary, table = res[0], res[1]
    kpi_html = res[2] if len(res) > 2 else ""

    # Counts now live in the KPI strip (the ticker no longer repeats them).
    assert "قراءة" in str(summary) and "جاهز" in str(summary), \
        f"summary shape: {str(summary)[:120]}"
    nums = re.findall(r'<div class="num">([\d,\.]+)</div>', str(kpi_html))
    assert len(nums) == 4, f"kpi numerals not found: {str(kpi_html)[:200]}"
    total = int(nums[0].replace(",", ""))
    clean = int(nums[1].replace(",", ""))
    susp = int(nums[2].replace(",", ""))

    assert isinstance(table, dict), "table shape changed"
    headers, data = table.get("headers") or [], table.get("data") or []
    idx = {h: i for i, h in enumerate(headers)}
    for col in ("#", "الصفحة", "الوصف", "النوع", "مدين", "دائن", "الرصيد", "الحالة"):
        assert col in idx, f"missing column {col!r}: {headers}"
    assert len(data) >= 95, f"table carries {len(data)} rows"

    # **هويّةُ الشكوك لا عدّادُها:** «صفحة:صفّ» لكلّ صفٍّ حالتُه «⚠ مشبوه». والعدّادُ في اللافتة
    # يُقابَل بالهويّة (اختلافُهما عطبٌ في اللافتة نفسها لا ضجيجُ قراءة)، والهويّةُ هي ما يجعل
    # الفصلَ بين «عطبٍ يتكرّر» و«ضجيجٍ لا يتكرّر» ممكنًا في سياسة اللاحتميّة أدناه.
    ids = sorted(f'{r[idx["الصفحة"]]}:{r[idx["#"]]}'
                 for r in data if str(r[idx["الحالة"]]).startswith("⚠"))
    # لافتةٌ وهويّةٌ لا تفترقان في التطبيق (كلتاهما من `all_rows` في النداء نفسه) ⇒ تعارضُهما **عطبُ
    # لافتةٍ/تحويلٍ لا ضجيجُ قراءة**، فلا يُعاد من أجله: **يصرخ في مكانه** (وهذا حدٌّ مُعلَن: التماثلُ
    # مع سياسة الإعادة مدَّعىً لا مقيسًا — وما لا يُقاس لا يُدَّعى).
    assert susp == len(ids), (
        f"عدّادُ اللافتة ({susp}) لا يطابق الصفوفَ المشبوهة ({len(ids)}): {ids[:5]}")

    # **وأوراكلُ الفوتر يُقاس هنا لا هناك:** يُقرأ في القياس فتصير «النظافة» واحدةً في المكانين
    # (وإلّا غُسلت مخالفتُه بإعادة قراءة: عِلّةٌ اصطادها مقعدُ المواصفة بالقياس).
    mf = re.search(r"تحقق الفوتر: (\d+)/(\d+)", str(summary))
    assert mf, f"footer oracle line missing from summary: {str(summary)[:220]}"
    seg = str(summary).split("تحقق الفوتر")[1].split("•")[0]
    cv = re.search(r"وتغطية (\d+)/(\d+)", str(summary))
    return {"summary": str(summary), "data": data, "idx": idx, "total": total,
            "clean": clean, "susp": susp, "ids": ids, "n_rows": len(data),
            "footer_pair": (int(mf.group(1)), int(mf.group(2))),
            "footer_seg": seg, "footer_flag": "⚠" in seg,
            "coverage_pair": (int(cv.group(1)), int(cv.group(2))) if cv else None}


#: **عقدُ القياس**: المفاتيحُ التي تُنتجها `_e2e_measure` وتستهلكها السياسة — موضعٌ واحد يُقابَل في
#: `tests/test_gate_flake_policy.py` بالقياس (فلا يفترق العقدُ صامتًا بين منتجٍ ومستهلك).
RUN_FIELDS = ("summary", "data", "idx", "total", "clean", "susp", "ids", "n_rows",
              "footer_pair", "footer_seg", "footer_flag", "coverage_pair")


def _is_clean(run: dict) -> bool:
    """نظافةُ قراءةٍ واحدة: صفرُ شكوكٍ **و** لا صفَّ مفقودًا من العدّ **و** أوراكلُ الفوتر مطابق.

    الشرطُ الأخيرُ لم يكن فيها أوّلًا، وأدخله قياسُ مقعد المواصفة: بدونه **تُغسَل مخالفةُ أوراكل
    الفوتر** (أقوى حارسٍ خارجيّ) بإعادةِ قراءةٍ نظيفةٍ ثانية، فتُمرَّر بلا إعلان.
    """
    f_ok, f_possible = run["footer_pair"]
    return (run["susp"] == 0 and run["clean"] == run["total"]
            and not run["footer_flag"] and f_ok == f_possible)


#: **سياسةُ اللاحتميّة — مُعلَنةٌ لا مُخمَّنة.** كانت البوّابةُ تحكم من قراءةٍ واحدة فتبدّل لونَها بلا
#: تبدّلِ شفرة: قياسٌ مؤرَّخ (٢٠٢٦-٠٩-٢٥ · R13) — `--full` أعطى «١ مشتبه» في تشغيلٍ و«٠» في التالي.
#: والقراءةُ البصريّةُ غيرُ حتميّة، والبوّابةُ لا تُصوّت للون ⇒ الحكمُ يُبنى على **مالكِ الافتراق**:
#: العطبُ الحتميّ (مُحلّلٌ · سلسلةٌ · انحرافُ عدّ) **يتكرّر بمعرّفه**، وضجيجُ القراءة **لا يتكرّر**.
#: والقاعدةُ الحاسمةُ واحدة: **لا براءةَ بلا قراءةٍ نظيفة** — والتقاطعُ **تشخيصيٌّ** لا حاسم (لأنّ
#: أيَّ تقاطعٍ يعني أنّ الثانيةَ غيرُ نظيفةٍ حتمًا)؛ وقيمتُه أنّه **يسمّي العطبَ المتكرّرَ بمعرّفه**.
#: **وحدودٌ مُعلَنة (اصطادتها المقاعد الثلاثة · ٢٠٢٦-٠٩-٢٥):**
#:   ١. «العطبُ الحتميّ يتكرّر بمعرّفه» **مُدَّعى** وقياسُه المؤرَّخ يُثبت وجودَ الضجيج لا تكرارَ العطب؛
#:      والضمانةُ الباقيةُ هي «لا قراءةَ نظيفة ⇒ أحمر» + شرطُ عدمِ فقدِ صفٍّ (أدناه).
#:   ٢. الهويّةُ **موضعيّةٌ** (`صفحة:رقمُ الصفّ`) لا محتوائيّة: صفٌّ مُسقَطٌ يُزيح ترقيمَ ما بعده فيُفقد
#:      اسمُ العطب — ولهذا صار **فقدُ الصفّ** سببًا مستقلًّا للرفض، لا مجرّدَ «لا تكرار».
#:   ٣. الإعادةُ لا تُغطّي **انقطاعَ النقل**: استثناءٌ في القراءة الأولى يُسقط البوّابةَ باسمه
#:      (فشلٌ مغلقٌ مُعلَن) ولا يُعاد — فالانقطاعُ عطبُ بيئةٍ لا لاحتميّةُ قراءة.
#:   ٤. والإعادةُ تُضاعف الزمنَ والكلفةَ في أسوأ الحالات (قراءتان لا أكثر — لا حلقة).
def decide_two_runs(first: dict, second: dict | None = None) -> tuple[bool, str]:
    if _is_clean(first):
        return True, f"قراءةٌ نظيفةٌ من المحاولة الأولى ({first['total']} صفًّا)"
    if second is None:
        return False, (f"{first['susp']} مشتبهًا بلا محاولةٍ ثانية — لا حكمَ من قراءةٍ واحدة")
    common = sorted(set(first["ids"]) & set(second["ids"]))
    if common:
        more = " …" if len(common) > 5 else ""
        return False, (f"شكوكٌ **تتكرّر** بمعرّفها ⇒ عطبٌ حتميّ لا ضجيج: "
                       f"{common[:5]}{more} ({len(common)} صفًّا)")
    if not _is_clean(second):
        return False, (f"لا قراءةَ نظيفة: الأولى {first['susp']} مشتبهًا و{first['n_rows']} صفًّا "
                       f"(فوتر {first['footer_pair'][0]}/{first['footer_pair'][1]})، والثانية "
                       f"{second['susp']} مشتبهًا و{second['n_rows']} صفًّا "
                       f"(فوتر {second['footer_pair'][0]}/{second['footer_pair'][1]}) "
                       f"⇒ تقاطعٌ فارغٌ لا يُثبت براءة")
    if second["n_rows"] < first["n_rows"] or second["total"] < first["total"]:
        # عِلّةٌ اصطادها مقعدا المعايير والمواصفة: قراءةٌ ثانيةٌ **أنحفُ** تُقرأ نظيفةً وهي أقربُ إلى
        # فقدِ صفٍّ (و`MIN_ROWS` وحدَه يسمح بفقدِ صفوفٍ حتّى العتبة) ⇒ تُرفض بسببها المُسمّى.
        return False, (f"إعادةُ القراءة **أنحفُ** ({second['n_rows']} صفًّا مقابل {first['n_rows']} · "
                       f"وعدّادُها {second['total']} مقابل {first['total']}) ⇒ فقدُ صفٍّ لا ضجيج")
    return True, (f"قراءةٌ غيرُ حتميّة مُعلَنة: الأولى {first['susp']} مشتبهًا "
                  f"{first['ids'][:3]} · {first['clean']}/{first['total']} · فوتر "
                  f"{first['footer_pair'][0]}/{first['footer_pair'][1]}"
                  f"{' بوسم ⚠' if first['footer_flag'] else ''}"
                  f"{' · تغطية ' + '/'.join(map(str, first['coverage_pair'])) if first['coverage_pair'] else ''}"
                  f"؛ والثانيةُ نظيفةٌ ({second['total']} صفًّا · فوتر "
                  f"{second['footer_pair'][0]}/{second['footer_pair'][1]}) "
                  f"⇒ تُقرأ القيمُ من الثانية، وقياساتُ الأولى مُعلَنةٌ كاملةً في هذا السطر")


def g_end_to_end() -> str:
    pdf = PROJ / "data/local_sample/sample_10p.pdf"
    assert pdf.exists(), f"missing {pdf}"
    first = _e2e_measure(pdf)
    run, declared = first, ""
    if not _is_clean(first):
        second = _e2e_measure(pdf)
        ok, why = decide_two_runs(first, second)
        assert ok, f"الفحصُ الشامل: {why}"
        declared = f" · {FLAKY_MARK} {why}"
        if _is_clean(second):
            run = second
    # **حزامٌ ثانٍ (اصطاده مقعدُ المواصفة بالقياس):** أيُّ مسارٍ يُكمِل يجب أن يكون على قراءةٍ **نظيفة** —
    # وإلّا فسياسةُ اللاحتميّة تُرخي قيدًا صامتةً إن اعتلّت. هذا السطرُ يجعل الإرخاءَ يصرخ، وسمُّه
    # في `guard_bite_sweep` (م١٤/م١٥).
    assert _is_clean(run), (
        f"الفحصُ الشامل: القراءةُ المُكمِلة ليست نظيفة ({run['susp']} مشتبهًا · "
        f"عدّاد {run['clean']}/{run['total']} · فوتر {run['footer_pair'][0]}/{run['footer_pair'][1]})")
    summary, data, idx = run["summary"], run["data"], run["idx"]
    total, n_rows = run["total"], run["n_rows"]
    assert n_rows == total, (f"جدولٌ بـ{n_rows} صفًّا مقابل عدّادٍ يقول {total} — "
                             f"انحرافُ عدّ لا لاحتميّةُ قراءة")
    assert total >= MIN_ROWS, (
        f"only {total} rows — العتبة {MIN_ROWS}: صفحات أقل غزارة من المتوقع، "
        f"راجع خطوات المعايرة في docs/ONBOARDING_NEW_FILE.md §3")

    def val(r, col):
        return r[idx[col]]

    def num(x):
        if x in ("", None):
            return None
        return float(str(x).replace(",", "").strip())

    def rows_of(page):
        return [r for r in data if val(r, "الصفحة") == page]

    def txns(page):
        return [r for r in rows_of(page)
                if val(r, "النوع") not in ("رصيد افتتاحي", "رصيد سابق")]

    # Page 1 start — the transfer of 300.00 to balance 300.00 must appear as
    # a transaction. When the dots-zero opening row was missed, the side
    # legitimately stays undecided (amount stays out of BOTH side columns —
    # never guess a direction); the row shows "◌" in الحالة. Accept that.
    p1_txns = txns(1)
    assert p1_txns, "no transactions on page 1"
    first_t = p1_txns[0]
    assert num(val(first_t, "الرصيد")) == 300.00, f"p1 first txn: {first_t}"
    c1, d1 = num(val(first_t, "مدين")), num(val(first_t, "دائن"))
    assert not (c1 is not None and d1 is not None), f"p1 first txn both sides: {first_t}"
    assert c1 in (None, 300.00) and d1 in (None, 300.00), f"p1 first txn amount: {first_t}"

    # Page 2 must be present with its rows (the capture of its top row's
    # amount varies across VLM reads — the chain + 0-suspects gate covers it).
    assert rows_of(2), "no page 2 rows"

    # Page 9 closing == 676.00 (verified against the render).
    p9 = rows_of(9)
    assert p9 and num(val(p9[-1], "الرصيد")) == 676.00, \
        f"p9 closing: {p9[-1] if p9 else None}"

    # THE owner-caught bug: page 10 starts with transfer +1000 -> 1676.
    # It must be a TRANSACTION with its movement — never silently "opening".
    p10 = rows_of(10)
    assert p10, "no page 10 rows"
    first10 = p10[0]
    assert val(first10, "النوع") not in ("رصيد افتتاحي", "رصيد سابق"), \
        f"p10 row0 kind: {first10}"
    # **بلا ثابتٍ رقميٍّ للمبلغين المعنيَّين** (وبقيت في الدالّة مرساةٌ مقصودةٌ من المستند دون عتبة
    # الحارس: `676.00` ختامَ ص٩ في `p9` و`300.00` أوّلَ صفّ): الصفُّ يُقاس **بالسلسلة** — رصيدُه =
    # ختامُ الصفحة ٩ + دائنُه. والثابتان السابقان كانا **لا يُغلقان هذه السلسلة حسابًا** (٦٧٦ + الأول
    # ≠ الثاني) ⇒ ثابتٌ غريبٌ عن هذا الصفّ أبقى البوّابةَ حمراء (R13-ب)؛ وقُرئت القيمتان بصرًا من
    # رندر `data/local_sample/sample_10p.pdf` صفحة ١٠ (٢٠٢٦-٠٩-٢٥) فوافقَتا السلسلة.
    # و**لا تُكتب مبالغُ المصدر هنا**: الحارسُ الأمنيُّ يحصي ظهوراتِه في الملفّات المتتبَّعة ويرفض
    # تبديلَ قيمةٍ عند العدّ نفسِه — واسمُ القاعدةِ في `tools/amount_guard.py:539` هو **القاعدة ١٢**
    # («لا يُعفى موضع، تُغيَّر القيمة»)، ولا وجودَ لـ«القاعدة ١٤» في المستودع (كانت في نصّي خطأً).
    # وقد **اصطادني** حين كتبتُ قيمتَي الصفّ نصًّا أوّلَ مرّة (وحين كتبتُ إحداهما في تعليقٍ ثانيةً!),
    # وبصمتُهما داخل مجموعة المصدر — تُعاد بالقياس: `fingerprint(...)` على القيمتين مقابل `load_deny()`
    # ⇒ True — أي أنّ الحارسَ منع **مبلغين حقيقيّين** من الدخول إلى ملفٍّ متتبَّع، لا أنّه هو ما أبقى
    # الأحمرَ (الثابتان القديمان كانا **خارج** مجموعته، فأُزيلا لسببٍ آخر: لا يُغلقان السلسلة).
    # والبديلُ المحكم أن يُقاس **حسابيًّا** لا بأرقامٍ محفوظة.
    _close9 = num(val(p9[-1], "الرصيد"))
    assert _close9 is not None, f"p9 has no closing row: {p9[-1]}"
    _credit10 = num(val(first10, "دائن"))
    assert _credit10 is not None and _credit10 > 0, f"p10 row0 credit: {first10}"
    _balance10 = num(val(first10, "الرصيد"))
    assert _balance10 is not None, f"p10 row0 balance: {first10}"
    assert abs(_balance10 - (_close9 + _credit10)) < 0.005, \
        f"p10 row0 chain: {first10}"
    assert val(first10, "النوع") == "تحويل وارد", f"p10 row0 type: {first10}"

    # ———— أوراكل الفوتر (what-if #4 / P1) ————
    # The printed per-page totals must match the chain-derived page sums on
    # EVERY comparable page. This is the ONLY external guard against a
    # uniform ×100 shift that stays "chain-clean" (the accuracy paradox).
    s = str(summary)
    f_ok, f_possible = run["footer_pair"]
    footer_seg = run["footer_seg"]
    assert "⚠" not in footer_seg, f"footer mismatch on sample: {footer_seg}"
    assert f_ok == f_possible and f_possible >= MIN_FOOTER_COMPARABLE, (
        f"footer: {f_ok}/{f_possible} comparable pages matched — "
        f"العتبة {MIN_FOOTER_COMPARABLE} (راجع §3 في دليل المعايرة)")
    # **وإغلاقُ المقام** (ثقبٌ مُعلَنٌ اصطاده مقعدُ المواصفة: «تغطية 9/10» كانت تمرّ): المقامُ المُقارَن
    # يجب أن يساوي **عددَ الصفحات** — فلا تخرج صفحةٌ من الأوراكل بلا حكم.
    cov = run["coverage_pair"]
    assert cov and f_possible == cov[1], (
        f"footer denominator hole: {f_ok}/{f_possible} مقابل تغطية {cov} "
        f"⇒ صفحاتٌ خرجت من الأوراكل بلا حكم")

    # ———— ترتيب الصفحات (what-if delta) ————
    assert "⚠ الترتيب" not in s, f"page-order flag on sample: {s[:220]}"

    # سؤالُ المالك (المبلغُ المتكرّر، ٢٠٢٦-٠٩): العيّنةُ تحمل **صفوفًا بمبلغٍ واحدٍ متكرّر** من **أنواعٍ
    # حقيقيّةٍ مختلفة** — والتشابه هو ما يمنع دمجَ الأنواع في نوعٍ واحد (خلطُ «كلُّ شيءٍ حركة · مدين=سحب»).
    # **بلا ثابتٍ رقميّ:** يُكتشف المبلغُ المتكرّر **حسابًا** (يظهر في ≥٤ صفوف) ثمّ تُقابَل أنواعُ صفوفه.
    # (والثابتُ السابق لم يعد يقابل المستند بعد أن أبدلته ورشةُ التطهير برقمٍ لا من المصدر ⇒ بقيت حمراء.)
    _repeat: dict[str, int] = {}
    for _r in data:
        for _c in ("مدين", "دائن"):
            _v = (val(_r, _c) or "").replace(",", "").strip()
            if _v:
                _repeat[_v] = _repeat.get(_v, 0) + 1
    _cands = [v for v, n in _repeat.items() if n >= 4]
    assert _cands, ("لا مبلغَ متكرّرًا في ≥٤ صفوف — العيّنةُ تغيّرت أو القراءةُ انحرفت: "
                    f"{sorted(_repeat.items(), key=lambda x: -x[1])[:5]}")
    _want = sorted(["تحويل صادر", "إيداع نقدي (صراف آلي)", "تحويل وارد", "سحب صراف آلي"])
    _found: dict[str, list[str]] = {}
    for _v in _cands:
        _found[_v] = sorted({val(_r, "النوع") for _r in data
                             if (val(_r, "مدين") or "").replace(",", "").strip() == _v
                             or (val(_r, "دائن") or "").replace(",", "").strip() == _v})
    assert any(g == _want for g in _found.values()), \
        f"أنواعُ المبالغ المتكرّرة: {_found} — المتوقَّع {_want}"

    return (f"{summary} | p1/p2 starts + p9→p10 continuity "
            f"+ أنواعُ المبلغِ المتكرّر مقفلة + footer {f_ok}/{f_possible} OK{declared}")


def main() -> None:
    ap = argparse.ArgumentParser(description="rajhi-rag pre-delivery QA gate")
    ap.add_argument("--quick", action="store_true",
                    help="offline gates only (the default; explicit flag kept for the documented usage)")
    ap.add_argument("--full", action="store_true",
                    help="include the live end-to-end run (~3-4 min, uses VLM calls; "
                         "وقد تتضاعف الزمنُ والكلفةُ مرّةً واحدة إن لم تكن القراءةُ الأولى نظيفة — إعادةٌ واحدة لا أكثر)")
    args = ap.parse_args()

    gate("unit suite", g_tests)
    gate("parser goldens", g_parser_goldens)
    gate("service health", g_service)
    gate("surface redirect", g_surface_redirect)
    if args.full:
        gate("end-to-end sample (values locked)", g_end_to_end)

    width = max(len(n) for n, _, _ in RESULTS)
    ok = sum(1 for _, p, _ in RESULTS if p)
    print()
    for n, p, d in RESULTS:
        print(f"[{'PASS' if p else 'FAIL'}] {n:<{width}}  {d}")
    print(f"\nGATES: {ok}/{len(RESULTS)} passed")
    sys.exit(0 if ok == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
