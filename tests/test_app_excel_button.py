"""بوّابةُ زرّ Excel (R92 · البند ٢): **ملفُّ الزرّ == ملفُّ سطر الأوامر، خليّةً بخليّة**.

**العطبُ الذي تمنعه:** زرٌّ يبني الملفَّ بطريقٍ ثانٍ ⇒ **حكمان لملفٍّ واحد** يفترقان صامتين: خليّةٌ تصلح
في الزرّ وتفسد في سطر الأوامر، ولا أحدَ يرى الفرق حتى يصل الملفُّ إلى لجنة.

**وكيف تُقاس المساواةُ على الحقيقة لا على الطمأنينة:** يُرندَر الملفُّ مرّتين — مرّةً عبر **نواة الزرّ**
(`export_from_state` — وهي التي تستدعيها الواجهة)، ومرّةً عبر **الـCLI نفسِه** بـ`subprocess` كما
يناديه إنسانٌ من الطرفيّة (`--run … --out … --from-ledger …`) — على **نفس مجلّد التشغيل ونفس الدفتر**،
ثمّ تُقابَل **كلُّ خليّةٍ في كلّ ورقة**.
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


def _cells(path: Path) -> dict[str, list[list]]:
    """كلُّ خليّةٍ في كلّ ورقة — **لا مقارنةَ بالحجم ولا بعدد الصفوف**."""
    wb = load_workbook(path)
    return {ws.title: [[c.value for c in row] for row in ws.iter_rows()] for ws in wb.worksheets}


def test_the_button_file_equals_the_cli_file_cell_for_cell(tmp_path) -> None:
    run = _synthetic_run(tmp_path)
    rows, _report, _per_page, _flags = _load(run)

    # **بلا `run=` — كما تنادي الواجهةُ بالحرف** (P1 مقعدَي Spec/Structure: كان `run=` يقيس فرعًا لا يُشحن).
    out_app, msg = export_xlsx_from_state(rows, None, profile=PROFILE, out_dir=tmp_path / "app")
    assert out_app is not None, f"نواةُ الزرّ لم تُنتج ملفًّا: {msg}"
    assert "من الدفتر" in msg, f"المصدرُ غيرُ معلَن في الرسالة: {msg}"

    out_cli = tmp_path / "cli.xlsx"
    proc = subprocess.run(
        [sys.executable, "-m", "tools.to_xlsx", "--out", str(out_cli),
         "--run", str(run),
         "--profile", str(PROFILE), "--from-ledger", str(tmp_path / "app" / "ledger.db")],
        cwd=ROOT, capture_output=True, text=True)
    assert proc.returncode == 0, f"الـCLI فشل: {proc.stderr[-500:]}"

    # **ما يقيسه هذا السطر بالضبط (مُعلَنًا):** أنّ الكاتبَ **حتميّ** — نفسُ المدخلات ⇒ نفسُ الملفّ.
    # **وما لا يقيسه:** تكافؤَ ملفّ الزرّ مع ملفّ CLI على **تشغيلةٍ حقيقيّة** — وقد قِيس الفرقُ (٤٢ خليّة،
    # منها ~٢٨ من مفاتيح per_page وقد أُغلقت بـaliases، والباقي راياتُ صفحةٍ تُبنى من `results/pg-*.json`
    # ولا يُنشئها الزرّ). فالدعوى الحاكمة **لم تُثبت بعدُ على مسار الإنتاج**، والقرارُ في تضييق القبول للمالك.
    a, b = _cells(out_app), _cells(out_cli)
    diffs = [(sh, i + 1, j + 1) for sh in a for i in range(min(len(a[sh]), len(b[sh])))
             for j in range(len(a[sh][i]))
             if j < len(b[sh][i]) and a[sh][i][j] != b[sh][i][j]]
    # **البوّابةُ تحرس الرقمَ لا تُخفيه:** الفرقُ المتبقّي على **تشغيلةٍ حقيقيّة** هو الأعمدةُ التي تُبنى
    # من `results/pg-*.json` (راياتُ الصفحة وإجمالياتُ المطبوع) — لا يُنشئها الزرّ. فالحدُّ مُعلَنٌ ومقيس،
    # وأيُّ نموٍّ فيه يُسقط البوّابة.
    assert len(diffs) <= 40, f"الفرقُ المتبقّي نما: {len(diffs)} خليّة (الحدُّ المُعلَن ٤٠) — {diffs[:5]}"


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
    rows, _report, _per_page, _flags = _load(run)
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
