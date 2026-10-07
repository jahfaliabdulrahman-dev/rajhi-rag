"""بوّابةُ زرّ Excel (R92 · البند ٢ · وُسِّعت في R93-4): **ملفُّ الزرّ == ملفُّ سطر الأوامر،
إلّا فرقًا مُسمًّى بالاسم — وخارج الأصناف المُعلَنة لا يُقبَل فرقٌ واحد**.

**العطبُ الذي تمنعه:** زرٌّ يبني الملفَّ بطريقٍ ثانٍ ⇒ **حكمان لملفٍّ واحد** يفترقان صامتين: خليّةٌ تصلح
في الزرّ وتفسد في سطر الأوامر، ولا أحدَ يرى الفرق حتى يصل الملفُّ إلى لجنة.

**وكيف تُقاس المساواةُ على الحقيقة لا على الطمأنينة:** يُرندَر الملفُّ مرّتين — مرّةً عبر **نواة الزرّ**
(`export_from_state` — وهي التي تستدعيها الواجهة)، ومرّةً عبر **الـCLI نفسِه** بـ`subprocess` كما
يناديه إنسانٌ من الطرفيّة (`--run … --out … --from-ledger …`) — على **نفس مجلّد التشغيل ونفس الدفتر**،
ثمّ تُقابَل **كلُّ خليّةٍ في كلّ ورقة**.

**وما كان قبل R93-4:** كان الحدُّ **عددًا إجماليًّا** («≤ ٢٤ خليّة»)، والمقارنةُ تمرّ على **متقاطع الصفوف
وحدَه** (`min(len)`) ⇒ **صفٌّ ناقصٌ في أحد الملفّين لا يُعدّ أبدًا** (وقِيس: ورقةُ «صفوف الأسئلة»
٣ صفوفٍ في الزرّ و٥ في سطر الأوامر). فصار العدُّ على **اتّحاد الشبكتين** (والغائبُ يُسجَّل غائبًا)،
وصار كلُّ فرقٍ **يُصنَّف**؛ وما لا صنفَ له يُسقط البوّابة بنصّه. (قرار المالك: الخيار (أ) — «نفسُ الكاتب
بفرقٍ مسمًّى محدود».)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

from statement_qa.export_from_state import export_xlsx_from_state
from test_exports import PROFILE, _synthetic_run
from tools.to_xlsx import load as _load

ROOT = Path(__file__).resolve().parents[1]

#: خليّةٌ موجودةٌ في ملفٍّ وغائبةٌ في الآخر (فرقُ الحجم لا يُمرّ صامتًا).
_MISSING = "<خليّةٌ غائبة>"

#: **الأصنافُ المُعلَنة — ولكلٍّ سببُه المكتوب** (R93-4 · قرار المالك (أ) «فرقٌ مسمًّى محدود» · وبعد
#: R94-3 صارت **خمسةَ فروقٍ مسمّاة** لا واحدًا — والقائمةُ مكتوبةٌ في ورقة «كيف تُقرأ هذه الأوراق» نفسِها):
#: `per_page_read_metadata` — مخبّآتُ القارئ لكلّ صفحة (عددُ الشكوك · مصدرُ القراءة · زمنُها ·
#: راياتُ الاستدراك/إعادة القراءة/الخطأ). حالةُ التطبيق تحمل صفوفًا وتذييلاتٍ لا مخبّآتِ قراءة،
#: فالعمودُ يبقى فارغًا في ملفّ الزرّ.
#: `page_classification` — تصنيفُ «صفحة بلا حركات أو بلا سطر إجماليات» من الملخّص. **وكان يُشتقّ من
#: المخبّآت، وكان الزرُّ لا يكتب مخبّأً لصفحةٍ بلا صفوف** ⇒ فالرقمُ يختلف. وبعد R94-3 يُكتب المخبّأُ
#: **لكلّ صفحةٍ في الدفتر** ⇒ يسقط هذا الصنف من الحساب (يُقاس: صفرٌ متوقَّع).
#: `per_page_cost_and_time` — كلفةُ القراءة لكلّ صفحة وزمنُها: الواجهةُ تحمل كلفةً كلّيّةً من عدّادها
#: لا كلفةَ صفحةٍ من المزوّد ⇒ **أحدُ خمسةِ فروقٍ مُسمّاةٍ بقرار المالك، لا الوحيدُ.**
#: `run_cost_note` — سطرُ «كلفة التشغيل المدفوعة»: التطبيقُ لا ينشر عدّادَه ككلفةٍ مدفوعة (المصدرُ رصيدُ المزوّد).
#: `support_rows_gap` — صفوفُ دعم الجواب من مخبّآت الصفحات المحكَّمة: لا يُنشئها مسارُ الزرّ.
#: `arbitration_page_rows` — **صنفٌ باسمه (R94-3):** خليّةُ السؤال ١٠ (التحكيم) كانت مصنَّفةً
#: «تصنيفَ صفحة» وهي **تحكيمٌ بشريّ** لا تصنيفًا. والفرقُ صفرٌ في القراءة الحيّة (لا تحكيم)، **والاسمُ
#: هو المُصلَح** — فعطبٌ يُسمّى باسمه لا يُدفن في صنفٍ آخر.
#: `source_run_path` — سطرُ «المصدر» يحمل مسارَ التشغيلة التي رُندِر منها كلُّ ملفّ (بالتصميم).
DECLARED: dict[str, str] = {
    "per_page_read_metadata": "مخبّآتُ القارئ لكل صفحة لا تحملها حالةُ التطبيق",
    "page_classification": "تصنيفُ «بلا حركات» من الملخّص (وبعد R94-3 يُتوقَّع صفرًا)",
    "per_page_cost_and_time": "كلفةُ الصفحة وزمنُها (أحدُ خمسةِ فروقٍ مُسمّاةٍ بقرار المالك)",
    "run_cost_note": "التطبيقُ لا ينشر عدّادَه ككلفةٍ مدفوعة",
    "support_rows_gap": "صفوفُ دعم الجواب تُبنى من مخبّآت الصفحات المحكَّمة",
    "arbitration_page_rows": "صفوفُ دعم جواب التحكيم (تحكيمٌ بشريّ لا تصنيفُ صفحة)",
    "source_run_path": "كلُّ ملفّ يعلن مسارَ تشغيلته (بالتصميم)",
}

#: **سقوفٌ مقيسةٌ على تشغيلة العيّنة الاصطناعيّة:** نموُّ صنفٍ فوق سقفه يُسقط البوّابة، وبقاءُ الصنف
#: تحت سقفه **تقدّمٌ** لا يُسقط شيئًا. **وسلسلةُ العدّ (مُدَّت لا استُبدلت):** ٣٨ قبل R93-4 ⇐ **٣٤** بعد
#: إصلاح «None» و«629» ورقم الصفحة المطبوع ⇐ **٢٩** بعد R94-3 (مخبّأٌ لكلّ صفحةٍ + عدُّ الأحكام في
#: التقرير) — **والتراجعُ مأخوذٌ بالعدّ لا بالطمأنينة**، والسقوفُ مُضيَّقةٌ إلى المقيس فمن نما فوقه سقط.
#: **و`page_classification` سقفُه صفر** لأنّه **سقط فعلًا** بعد R94-3 (كان ٤): أيُّ عودةٍ له تُحمرّ.
CEILINGS: dict[str, int] = {
    "per_page_read_metadata": 6,
    "page_classification": 0,
    "per_page_cost_and_time": 3,
    "run_cost_note": 1,
    "support_rows_gap": 16,
    "arbitration_page_rows": 2,
    "source_run_path": 1,
}


def _cells(path: Path) -> dict[str, list[list]]:
    """كلُّ خليّةٍ في كلّ ورقة — **لا مقارنةَ بالحجم ولا بعدد الصفوف**."""
    wb = load_workbook(path)
    return {ws.title: [[c.value for c in row] for row in ws.iter_rows()] for ws in wb.worksheets}


def _label(grid: list[list], r: int) -> str:
    """عنوانُ الصفّ (الخليّةُ الأولى) — به يُصنَّف الفرق، فإزاحةُ صفٍّ تُسقط البوّابةَ ولا تُخفي فرقًا."""
    row = grid[r - 1] if r - 1 < len(grid) else []
    return str(row[0]) if row and row[0] is not None else ""


def _class_of(sheet: str, r: int, c: int, app_grid: list[list]) -> str | None:
    """صنفُ الفرق — و`None` تعني **فرقًا بلا اسم**، وهي التي تُسقط البوّابة."""
    if sheet == "التحقق لكل صفحة":
        return "per_page_read_metadata" if c in (5, 6, 7, 9, 10, 11) else None
    if sheet == "الملخص":
        return {"صفحات بلا حركات أو بلا سطر إجماليات": "page_classification",
                "الكلفة المدفوعة": "per_page_cost_and_time",
                "وسيط زمن الصفحة (ث)": "per_page_cost_and_time"}.get(_label(app_grid, r))
    if sheet == "الأسئلة":
        return {"2": "page_classification", "10": "arbitration_page_rows",
                "12": "per_page_cost_and_time"}.get(_label(app_grid, r))
    if sheet == "كيف تُقرأ هذه الأوراق":
        return {"المصدر": "source_run_path",
                "كلفة التشغيل المدفوعة": "run_cost_note"}.get(_label(app_grid, r))
    if sheet == "صفوف الأسئلة":
        return "support_rows_gap"
    return None


def _both_files(tmp_path) -> tuple[Path, Path]:
    """ملفُّ الزرّ وملفُّ الـCLI على **تشغيلةٍ واحدة ودفترٍ واحد** — بما تحمله حالةُ التطبيق فعلًا."""
    run = _synthetic_run(tmp_path)
    rows, _report, per_page, flags = _load(run)

    # **بلا `run=` — كما تنادي الواجهةُ بالحرف** (P1 مقعدَي Spec/Structure: كان `run=` يقيس فرعًا لا يُشحن).
    # **كما تنادي الواجهةُ بالحرف:** `STATE.get("footers")` — وتذييلاتُ الصفحة مفرداتُها
    # `debits/credits/balance` وهي **عينُ** ما يقرؤه الكاتب (`to_xlsx.py:453-456`)، فلا خَرْطَ مطلوبًا.
    # **وبشكل الواجهة الحقيقيّ:** الإجمالياتُ المطبوعة + حكمُ الصفحة من **التقرير** (مصدرُ الحقيقة)،
    # **وخريطةُ الأرقام المطبوعة** كما تحملها `STATE["printed_pages"]` (R93-4).
    footers = {int(pg): {**(flags.get(int(pg), {}).get("printed") or {}),
                         "verdict": (per_page.get(int(pg), {}) or {}).get("footer") or "unchecked"}
               for pg in per_page}
    printed = {int(pg): (per_page.get(int(pg)) or {}).get("page_no") for pg in per_page}
    printed = {k: v for k, v in printed.items() if isinstance(v, int)}
    out_app, msg = export_xlsx_from_state(rows, footers, profile=PROFILE,
                                          printed_pages=printed,
                                          read_pages=sorted(int(pg) for pg in per_page),
                                          out_dir=tmp_path / "app")
    assert out_app is not None, f"نواةُ الزرّ لم تُنتج ملفًّا: {msg}"
    assert "من الدفتر" in msg, f"المصدرُ غيرُ معلَن في الرسالة: {msg}"

    out_cli = tmp_path / "cli.xlsx"
    proc = subprocess.run(
        [sys.executable, "-m", "tools.to_xlsx", "--out", str(out_cli),
         "--run", str(run),
         "--profile", str(PROFILE), "--from-ledger", str(tmp_path / "app" / "ledger.db")],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, f"الـCLI فشل: {proc.stderr[-500:]}"
    return out_app, out_cli


def test_the_button_file_equals_the_cli_file_except_named_classes(tmp_path) -> None:
    """**كلُّ خليّةٍ تُقابَل في الاتجاهين، وكلُّ فرقٍ يُصنَّف** — ولا حدَّ إجماليًّا يُخفي نموًّا."""
    a, b = (_cells(p) for p in _both_files(tmp_path))
    assert set(a) == set(b), f"أوراقٌ في أحد الملفّين فقط: {sorted(set(a) ^ set(b))}"

    unclassified: list[tuple] = []
    tally: dict[str, int] = {}
    rows_gap: dict[str, int] = {}
    for sh in sorted(a):
        ga, gb = a[sh], b[sh]
        if len(ga) != len(gb):
            rows_gap[sh] = max(len(ga), len(gb)) - min(len(ga), len(gb))
        for i in range(max(len(ga), len(gb))):
            ra = ga[i] if i < len(ga) else []
            rb = gb[i] if i < len(gb) else []
            for j in range(max(len(ra), len(rb))):
                va = ra[j] if j < len(ra) else _MISSING
                vb = rb[j] if j < len(rb) else _MISSING
                if va == vb:
                    continue
                cls = _class_of(sh, i + 1, j + 1, ga)
                if cls is None:
                    unclassified.append((sh, i + 1, j + 1, va, vb))
                else:
                    tally[cls] = tally.get(cls, 0) + 1

    assert not unclassified, (
        "فرقٌ بلا صنفٍ مُعلَن — لا يُقبَل فرقٌ لا اسمَ له (R93-4):\n  "
        + "\n  ".join(f"{sh} r{r}c{c}: app={va!r} · cli={vb!r}"
                      for sh, r, c, va, vb in unclassified[:8]))
    # **وفرقُ الصفوف يُعدّ ولا يُمرّ:** الصفّان الغائبان في «صفوف الأسئلة» ظاهرٌ عدُّهما هنا.
    assert rows_gap == {"صفوف الأسئلة": 2}, f"فرقُ الصفوف تغيّر عن المقيس: {rows_gap}"
    for cls, ceiling in CEILINGS.items():
        assert tally.get(cls, 0) <= ceiling, (
            f"الصنفُ «{cls}» نما: {tally.get(cls, 0)} خليّة (السقفُ المقيس {ceiling}) — {DECLARED[cls]}")


def test_the_notes_carry_the_run_s_own_numbers(tmp_path) -> None:
    """**R93-4:** لا «629 ورقة» ثابتةً · ولا `None` في ورقة الشرح · ولا فراغَ في رقم صفحة «ما لم يُثبت».

    (وهذه الثلاثةُ كانت في الملفّ الذي يُسلَّم: «629» لعيّنةٍ من صفحتين، و«None معاملة»، وخليةٌ فارغة
    تُقرأ نقصَ بياناتٍ بلا اسم.)
    """
    out, _cli = _both_files(tmp_path)
    cells = _cells(out)
    notes = {_label(cells["كيف تُقرأ هذه الأوراق"], r): (cells["كيف تُقرأ هذه الأوراق"][r - 1][1] or "")
             for r in range(1, len(cells["كيف تُقرأ هذه الأوراق"]) + 1)}

    source = str(notes.get("المصدر") or "")
    assert "629" not in source, f"رقمُ ٦٢٩ عاد نصًّا ثابتًا: {source}"
    assert "2 ورقة ممسوحة" in source, f"عددُ أوراق التشغيلة لا يُنشر من مادّتها: {source}"
    for key in ("الصفوف المحتسبة في التقرير", "فرق الصفوف"):
        value = str(notes.get(key) or "")
        assert "None" not in value, f"`None` مطبوعةٌ في «{key}»: {value}"
        assert any(ch.isdigit() for ch in value), f"عدٌّ غائبٌ في «{key}»: {value}"

    unproven = cells["ما لم يُثبت"]
    for row in unproven[1:]:
        assert row[1] is not None, f"رقمُ صفحةٍ فارغٌ في «ما لم يُثبت»: {row}"


def test_the_shipped_branch_is_missing_the_derivation_detail_known_and_owned(tmp_path) -> None:
    """**حدٌّ مُعلَن لا مُصلَح:** على مسار الزرّ لا `footer_detail` ⇒ `verify_derivation` خاملةٌ.

    لا يُوهَم غلقُه: يُقاس فيُعرَف. والمالكُ: الجولةُ التالية — والفرقُ لا يمسّ صفوفَ الدفتر.
    """
    run = _synthetic_run(tmp_path)
    rows, *_ = _load(run)
    out, _msg = export_xlsx_from_state(rows, None, profile=PROFILE, out_dir=tmp_path / "known")
    assert out is not None
    # **قُلب المشهدُ عن قصد (R92-2b):** كان الفرعُ الشاحن بلا مخبّآت، وصار يكتبها من الصفوف والتذييلات
    # ⇒ فالضابطُ الآن **يشهد بالجديد**: المخبّآتُ موجودةٌ لكلّ صفحة، وبالشكل الذي يقرؤه كاتبُ الإكسل.
    caches = sorted((tmp_path / "known" / "run" / "results").glob("pg-*.json"))
    assert caches, "الفرعُ الشاحن لا يكتب مخبّآت الصفحة ⇒ الراياتُ والإجمالياتُ المطبوعة تبقى فارغة"
    import json as _json
    one = _json.loads(caches[0].read_text(encoding="utf-8"))
    assert {"pg", "raw_rows", "recovered", "reread", "error", "arbitrated_by", "footer"} <= set(one), \
        f"شكلُ المخبّأ ناقص: {sorted(one)}"


def test_the_ledger_is_the_row_source_not_the_run_caches(tmp_path) -> None:
    """**والدفترُ هو المصدر:** مجلّدُ تشغيلٍ **بلا مخبّآت** ⇒ كلُّ وصفٍ من الدفتر يظهر في الملفّ.

    (والمقارنةُ على **حضور الصفوف** لا على تساوي الملفّين: أحكامُ الصفحات تُقرأ من الدفتر أيضًا،
    فالمقابلةُ الصحيحةُ هي «كلُّ وصفٍ موجود» — ولا ندّعي تساويًا لا يلزمه الكود.)
    """
    run = _synthetic_run(tmp_path)
    rows, _report, per_page, flags = _load(run)
    bare = tmp_path / "bare"
    (bare / "results").mkdir(parents=True)
    (bare / "slice_report.json").write_text(
        (run / "slice_report.json").read_text(encoding="utf-8"), encoding="utf-8")

    out, msg = export_xlsx_from_state(rows, None, profile=PROFILE,
                                      out_dir=tmp_path / "bareout", run=bare)
    assert out is not None, msg
    blob = {str(c) for _sheet, grid in _cells(out).items() for row in grid for c in row if c}
    descs = {str(r.get("desc") or r.get("description") or "") for r in rows}
    missing = {d for d in descs if d and d not in blob}
    assert not missing, f"وصوفٌ من الدفتر غابت عن الملفّ: {sorted(missing)[:3]}"


def test_the_button_leaves_no_statement_copy_behind(tmp_path, monkeypatch) -> None:
    """**R93-8:** كلُّ نقرةٍ على الزرّ كانت تترك **نسخةً كاملةً من الكشف** في مجلّدٍ مؤقّتٍ دائم:
    `ledger.db` (كلُّ الصفوف) و`run/results/pg-*.json` (الصفوفَ الخامّة) — صنفُ النسخِ في الـcache
    الذي أُغلق قبل. وتُقاس الآن: بعد النقرة **لا دفترَ ولا مخبّآت، ويبقى ملفُّ الإكسل**.
    """
    import pytest

    pytest.importorskip("gradio")
    import tempfile

    import app

    rows, _report, per_page, flags = _load(_synthetic_run(tmp_path))
    footers = {int(pg): {**(flags.get(int(pg), {}).get("printed") or {}),
                         "verdict": (per_page.get(int(pg), {}) or {}).get("footer") or "unchecked"}
               for pg in per_page}
    printed = {int(pg): (per_page.get(int(pg)) or {}).get("page_no") for pg in per_page}
    app.STATE.clear()
    app.STATE.update({"rows": rows, "footers": footers,
                      "printed_pages": {k: v for k, v in printed.items() if isinstance(v, int)}})
    app_tmp = tmp_path / "tmpapp"          # **معزولٌ عن مجلّد العيّنة** (fixture له run/ خاصٌّ به)
    app_tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(app_tmp))       # كلُّ المجلّدات المؤقّتة هنا
    out, note = app.export_xlsx()
    assert out and Path(out).exists(), f"الزرُّ لم يُنتج ملفًّا: {note}"
    assert Path(out).suffix == ".xlsx"
    assert not list(app_tmp.rglob("ledger.db")), "نسخةُ الدفتر بقيت في مجلّدٍ مؤقّت"
    assert not list(app_tmp.rglob("pg-*.json")), "الصفوفُ الخامّة بقيت في مجلّدٍ مؤقّت"


def test_the_button_is_wired_in_the_interface() -> None:
    """**والواجهةُ تستدعيه فعلًا (AST):** زرٌّ بلا مستدعٍ = ميزةٌ معلَّنةٌ نائمة."""
    import ast
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "export_xlsx" in names, "لا دالّةَ تصديرٍ في الواجهة"
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "export_xlsx")
    called = {getattr(c.func, "id", "") or getattr(c.func, "attr", "")
              for c in ast.walk(fn) if isinstance(c, ast.Call)}
    assert "export_xlsx_from_state" in called, "الدالّةُ لا تستدعي النواةَ — طريقٌ ثانٍ للملفّ"
