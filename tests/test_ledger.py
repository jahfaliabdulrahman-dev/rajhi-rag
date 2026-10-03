"""بوّاباتُ دفتر الكشف (أ-٣) — ثلاثَ عشرةَ بوّابةً، كلُّ واحدةٍ تقيس ما تنصّ عليه الخارطة بالاسم.

**والقاعدةُ الحاكمة:** البوّابةُ الحاسمةُ الأولى — **ما كُتب يُقرأ صفًّا بصفّ**. فكلُّ قيدٍ آخر
(المبالغُ TEXT · الفهرسُ لا ينطفئ · التطبيع · الخطأُ المسمّى) يُقاس لأنّه يحمي هذه القراءة.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import ledger as L  # noqa: E402


def _rows(n: int = 3) -> list[dict]:
    """صفوفٌ بأعمدة الرندر العشرين — **نفسُ الأسماء** التي يقرؤها الدفتر."""
    out = []
    for i in range(1, n + 1):
        out.append({
            "page": 1, "row_no": i, "printed_page": 1,   # قِيس في الرندر الحقيقيّ: int (5801) أو None (8)
            "date": "2026-01-0%d" % i, "date_iso": "2026-01-0%d" % i, "date_status": "ok",
            "date_source": "من خانة الورق", "year": 2026,
            "desc": "حوالة صادرة رقم %d" % i,
            "printed_movement": "10.00", "printed_balance": "15.00",
            "movement": "10.00", "balance": "15.00", "derived_movement": "10.00",
            "side": "debit", "opening": (i == 1), "chain_ok": 1,   # بوول في الرندر (قِيس: 5809 بوولًا)
            "row_state": "حركة", "source": "من خانة الورق", "shift": "",
            "footer": "ok", "counted": 1,
        })
    return out


def _pages() -> dict[int, dict]:
    return {1: {"pg": 1, "page_no": "١", "footer": "ok", "rows": 3}}


def _fresh(tmp_path: Path):
    return L.open_ledger(tmp_path / "ledger.sqlite"), tmp_path / "ledger.sqlite"


def _want(row: dict, col: str):
    """قيمةُ العمود في **الصفّ المصدر** — والترجمةُ مُعلَنةٌ في موضعٍ واحد (`ledger._row_values`).

    وثلاثةُ أسماءٍ تختلف بين الرندر والمواصفة: `page`↔`pg` و`source`↔`proof_source` (والمواصفةُ
    سمّتها `proof_source` في الخارطة أ-٣)، وما سواها متطابقٌ — ويُقاس التطابقُ في ضابطٍ مجموعيّ.
    """
    return row[{"pg": "page", "proof_source": "source"}.get(col, col)]


def _same(want, have) -> bool:
    """المقابلةُ **القانونيّة** بين ما أنتجه الرندرُ وما خزّنه الدفتر.

    والعلّةُ مُقيسة: الرندرُ يحمل `Decimal` للمبالغ (وهو الصوابُ في حسابه)، والدفترُ يخزّن **نصًّا**
    (وهو الصوابُ في عقده: «المبالغُ `TEXT`»)، و`Decimal('10.00') == '10.00'` غيرُ صحيحةٍ في بايثون ⇒
    فتُقابَل الصورةُ النصّيّةُ للطرفين. **وهذا ليس تهاونًا**: هو الموضعُ الذي لو أُهمل لَمَرّ مبلغٌ
    نصُّه «10.0» مقابل `Decimal('10.00')` بلا شاهد — فيُقابَل النصُّ بعد التحويل الصريح.
    """
    if isinstance(want, bool) or isinstance(have, bool):
        # **والعلمُ المنطقيُّ يُقابَل عددًا** (`False` ↔ `0`): المخرَجُ يحمل `False` علامةً في
        # `opening` لصفٍّ ليس حركةً، والدفترُ يخزّن `0` (لا نوعَ منطقيًّا في SQLite) ⇒ فالتحويلُ
        # **صريحٌ هنا ومُعلَن**، لا يُمرّ صامتًا كما لو تطابق النوعان.
        try:
            return int(want) == int(have)
        except (TypeError, ValueError):
            return bool(want) == bool(have)
    if want is None or have is None:
        return want is None and have is None
    if isinstance(want, (int, float)) or isinstance(have, (int, float)):
        try:
            return type(want)(have) == want if isinstance(want, (int, float)) else False
        except (TypeError, ValueError):
            return False
    return str(want) == str(have)


def test_written_rows_read_back_row_by_row(tmp_path):
    """**البوّابةُ الحاسمة (الخارطة أ-٣):** قيدٌ واحدٌ يُخالف ⇒ أحمر. والقراءةُ بأسماء الرندر."""
    conn, _ = _fresh(tmp_path)
    src = _rows()
    L.ingest(conn, src, _pages())
    got = L.read_rows(conn)
    assert len(got) == len(src), "عددُ الصفوف"
    for want, have in zip(src, got, strict=True):
        for col in L.COLUMNS:
            assert _same(_want(want, col), have[col]), \
                f"عمود {col} في الصفّ {want['row_no']}: {_want(want, col)!r} ≠ {have[col]!r}"
    conn.close()


def test_an_amount_never_lands_as_a_float(tmp_path):
    """**قيدُ أ-٣:** المبالغُ `TEXT` — ولو سُلّم رقمٌ عائمٌ فلا يُخزَّن `REAL` (القراءةُ نصٌّ دائمًا).

    **والدقيقتان:** عمودُ المبلغ مُعلَنٌ `TEXT` فتُحوّله ملازمةُ النوع عند الإدخال، **و`CHECK(typeof)` سياجٌ
    ثانٍ** لو غُيِّر العمودُ يومًا فأُسقطت الملازمة. وهذا ما يمنع طباعةَ مبلغٍ برقمٍ عائمٍ طويلٍ لا يُقرأ في كشفٍ قانونيّ.
    """
    conn, _ = _fresh(tmp_path)
    L.ingest(conn, _rows(1), _pages())
    conn.execute("UPDATE rows_verified SET movement = ? WHERE row_no = 1",
                 (float("10.00"),))          # رقمٌ عائمٌ عمدًا: ملازمةُ TEXT هي الحارس
    kinds = {r[0] for r in conn.execute(
        "SELECT typeof(movement) FROM rows_verified WHERE movement IS NOT NULL")}
    assert kinds == {"text"}, f"نوعُ المبلغ في الجدول: {kinds}"
    assert conn.execute("SELECT movement FROM rows_verified").fetchone()[0] == "10.0", \
        "قيمةُ المبلغ نصًّا كما خُزّنت"
    conn.close()


def test_the_index_never_goes_dark_silently(tmp_path):
    """**بلا triggers** يُدرَج صفٌّ فلا يُوجَد بالبحث أبدًا — عطبٌ صامتٌ (نصُّ الخارطة)."""
    conn, _ = _fresh(tmp_path)
    L.ingest(conn, _rows(3), _pages())
    assert L.search(conn, "حوالة"), "الإدراجُ لم يُفهرَس"
    conn.execute("UPDATE rows_verified SET desc = 'رسوم إدارة' WHERE row_no = 2")
    assert L.search(conn, "رسوم"), "التحديثُ لم يُتبَع في الفهرس"
    assert not [r for r in L.search(conn, "حوالة") if r["row_no"] == 2], "القديمُ بقي"
    conn.execute("DELETE FROM rows_verified WHERE row_no = 3")
    assert not [r for r in L.search(conn, "حوالة") if r["row_no"] == 3], "المحذوفُ بقي"
    conn.close()


def test_arabic_normalisation_is_measured_not_hoped(tmp_path):
    """«اجمالي الايداعات» = «إجماليّ الإيداعات» = «اجمالى الايداعات» — صفٌّ واحدٌ في العين."""
    conn, _ = _fresh(tmp_path)
    L.ingest(conn, [{**_rows(1)[0], "desc": "إجماليّ الإيداعات"}], _pages())
    for probe in ("اجمالي الايداعات", "اجمالى الايداعات", "إجمالي الإيداعات", "اجماليـ ـالايداعات"):
        assert L.search(conn, probe), f"التطبيعُ لم يجد: {probe}"
    conn.close()


def test_a_missing_or_corrupt_ledger_is_a_named_error(tmp_path):
    """**بندُ الإرشادات:** قاعدةٌ غائبةٌ أو تالفة ⇒ خطأٌ مسمّى بلا انهيار."""
    missing = tmp_path / "nope.sqlite"
    with pytest.raises(L.LedgerUnavailable) as e:
        L.open_ledger(missing, create=False)
    assert e.value.state == L.MISSING and "غيرُ موجودة" in str(e.value)

    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_text("هذا ليس ملفّ قاعدة بيانات", encoding="utf-8")
    with pytest.raises(L.LedgerUnavailable) as e2:
        L.open_ledger(corrupt)
    assert e2.value.state == L.CORRUPT, str(e2.value)


def test_unproven_is_derived_and_the_anchor_must_prove_itself(tmp_path):
    """«ما لم يُثبت» **يُشتقّ من المنظار**، ومرساةٌ بلا `source` يرفضها القيدُ نفسه."""
    conn, _ = _fresh(tmp_path)
    rows = _rows(2)
    rows[1] = {**rows[1], "row_state": "حركة — مرساة بعد ورقة غائبة", "source": ""}
    with pytest.raises(sqlite3.IntegrityError):
        L.ingest(conn, rows, _pages())
    L.ingest(conn, [rows[0]], _pages())
    assert [r["row_no"] for r in L.unproven(conn)] == []
    conn.close()


def test_both_guards_cover_the_ledger_path(tmp_path):
    """**قرارُ المالك:** «ويغطّيه حارسا النشر والمبالغ، وضابطٌ يُثبت ذلك» — **بالخاصيّة لا بالعضويّة**.

    **والعِلّةُ المقيسة (مقعدُ المعايير F2 · مُثبت):** كان الضابطُ يقول «`.sqlite` في `BINARY_EXTS`»
    و«`data/` في `BINARY_DIRS`» — وكلاهما **عضويّةٌ في مجموعةٍ** لا **حجبٌ**: `BINARY_EXTS` مجموعةُ
    تخطٍّ، و`amount_guard.undeclared_binaries()` على ملفٍّ مُتتبَّعٍ `data/ledgers/x.sqlite` تُعيد `[]`
    (لا تعضّ)، فالحارسُ الثاني **لا يحجب قاعدةً** — والفعّالُ `publish_guard` بامتداد `.sqlite`
    (`OPAQUE_EXTS`) + **الإهمالُ** في `.gitignore`. فالضابطُ الآن يقيس الثلاثةَ كما هي:
    الحجبَ الفعليَّ، والإهمالَ الفعليَّ، وغيابَ حجب حارس المبالغ (يُعلَن لا يُخفى).
    """
    import amount_guard as ag           # noqa: PLC0415
    import publish_guard as pg          # noqa: PLC0415

    rel = str(L.ledger_path(ROOT, "alrajhi-1234").relative_to(ROOT))
    assert rel.startswith("data/") and rel.endswith(".sqlite"), rel

    # ١) حارسُ النشر **يحجب** المسار: يُقاس بالدالّة التي تُنتج الحكمَ في الماسح نفسِه
    #    (`_check_path` تُطبّق PATH_RULES) — لا بعضويّةٍ في ثابتٍ (وهو ما قاسه المقعد).
    findings: list = []
    pg._check_path(rel, "tree", findings, [])   # noqa: SLF001
    assert any(f[0] == "BLOCK" for f in findings), f"حارسُ النشر لا يحجب دفترًا: {findings}"

    # ٢) والإهمالُ واقعٌ: `git check-ignore` يشهد به (لا نصُّ `.gitignore` يُقرأ بالعين).
    check = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT)
    assert check.returncode == 0, "مسارُ الدفتر غيرُ مُهمَل ⇒ قرارُ المالك غيرُ واقع"

    # ٣) **وحارسُ المبالغ لا يحجب `.sqlite`** — يُقاس ويُعلَن بدل أن يُدّعى:
    assert not getattr(ag, "BINARY", set()) & {".sqlite", ".db", ".sqlite-wal"}, \
        "تغيّرت تغطيةُ حارس المبالغ (صار يحجب القاعدة) ⇒ يُحدَّث هذا السطر والتعليقُ في الوحدة"
    assert any(str(b).startswith("data") for b in ag.BINARY_DIRS), "حارسُ المبالغ لا يرى data/"
    assert not pg.real_data_path(rel), "تغيّر مسارُ الدفتر ⇒ يُعاد النظرُ في مصدر حمايته"


def test_a_question_with_a_quote_cannot_crash_the_search(tmp_path):
    """**مقعدُ المعايير F4 · مُثبت:** سؤالٌ فيه `"` كان يرفع `unterminated string` — انهيارٌ خامٌ على
    نصٍّ يكتبه نموذجٌ أو إنسان. والقاعدة: الصيغةُ تُبنى من **حروف السؤال وحدَها**، والباقي يُنقّى."""
    conn, _ = _fresh(tmp_path)
    L.ingest(conn, _rows(2), _pages())
    for probe in ('حوالة "10.00"', "حوالة*", "(حوالة)", 'حوالة" OR "x', "NEAR(حوالة)"):
        got = L.search(conn, probe)          # لا انهيار — نتيجةٌ أو فراغ
        assert isinstance(got, list), probe
    assert L.search(conn, 'حوالة "10.00"'), "التنقيةُ أزالت الحروفَ أيضًا"
    conn.close()


def test_re_reading_a_statement_does_not_eat_the_evidence(tmp_path):
    """**مقعدا المواصفة والبنية · مُثبت:** `INSERT OR REPLACE` كان يُسقط `id` و`ON DELETE CASCADE`
    يمسح `qa_evidence` ⇒ **فقدانُ دليلِ الأسئلة صامتًا** عند إعادة قراءة كشفٍ سُئل عنه. الآن التحديثُ
    يُبقي المعرّفَ فيبقى الدليل — وهو شرطُ «سجلُّ الأسئلة **مع صفوف الدليل**»."""
    conn, _ = _fresh(tmp_path)
    L.ingest(conn, _rows(2), _pages())
    ids = [r[0] for r in conn.execute("SELECT id FROM rows_verified WHERE pg=1 ORDER BY row_no")]
    L.record_qa(conn, "2026-10-04T00:00:00", "ما مجموع الحوالات؟", "جوابٌ", [ids[0]])
    before = conn.execute("SELECT COUNT(*) FROM qa_evidence").fetchone()[0]
    assert before == 1
    L.ingest(conn, [{**_rows(2)[0], "desc": "وصفٌ مُنقَّح"}, _rows(2)[1]], _pages())   # إعادةُ قراءة
    after = conn.execute("SELECT COUNT(*) FROM qa_evidence").fetchone()[0]
    assert after == 1, "إعادةُ القراءة محت دليلَ السؤال"
    ids2 = [r[0] for r in conn.execute("SELECT id FROM rows_verified WHERE pg=1 ORDER BY row_no")]
    assert ids2 == ids, "تبدّلت المعرّفات ⇒ الدليلُ عرضةٌ للمسح"
    conn.close()


def test_the_column_contract_is_equal_in_both_directions():
    """**مقعدُ البنية P2 · مُثبت:** كان الضابطُ **احتواءً** وحدَه ⇒ عمودٌ يُضاف في الرندر يُسقَط صامتًا.
    وهنا **تساوٍ مجموعيٌّ في الاتجاهين** بين أعمدة الدفتر ومفاتيحِ صفِّ الرندر — يُشتقّان من المصدرين
    (المخطَّطِ النصّيّ و`to_xlsx`) لا من قائمةٍ ثالثةٍ في الاختبار.
    """
    import ast                          # noqa: PLC0415

    # أعمدةُ المخطَّط من نصّ الـSQL (لا من COLUMNS نفسِه، وإلّا لكأنّ الشيءَ يقابل نفسه).
    body = L.SCHEMA.split("CREATE TABLE IF NOT EXISTS rows_verified", 1)[1].split(");", 1)[0]
    sql_cols = []
    for line in body.splitlines():
        line = line.split("--", 1)[0].strip()
        # سطرُ عمودٍ = اسمٌ ثمّ نوع (وما دون ذلك قيودٌ متعدّدةُ الأسطر تُتخطّى — قِيس أنّ الحصاد
        # الساذج بالقطع عند الفاصلة يُدخل '(' و'OR' أعمدةً وهميّة).
        parts = line.rstrip(",").split()
        if (len(parts) >= 2 and parts[0].isidentifier()
                and parts[1].upper().split("(")[0] in {"TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC"}):
            sql_cols.append(parts[0])
    assert sql_cols, "تعذّر استخراجُ أعمدة المخطَّط — البوّابةُ تحتاج إصلاحًا لا تعطيلًا"

    # مفاتيحُ صفِّ الرندر من مصدره (شجرةُ `rows.append({...})` — تُقرأ لا تُستحضر).
    tree = ast.parse((ROOT / "tools" / "to_xlsx.py").read_text(encoding="utf-8"))
    render_keys: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "append" and node.args
                and isinstance(node.args[0], ast.Dict)):
            render_keys |= {k.value for k in node.args[0].keys
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    assert render_keys, "تعذّر استخراجُ مفاتيح الرندر"

    ledger_from_render = {("pg" if k == "page" else "proof_source" if k == "source" else k)
                          for k in render_keys}
    assert set(L.COLUMNS) == ledger_from_render, (
        f"عقدُ الأعمدة افترق — في الدفتر وليس في الرندر: {sorted(set(L.COLUMNS) - ledger_from_render)} · "
        f"وفي الرندر وليس في الدفتر: {sorted(ledger_from_render - set(L.COLUMNS))}")
    assert set(sql_cols) == {"id", *L.COLUMNS, "desc_norm"}, \
        f"المخطَّطُ والثابتُ افترقا: {sorted(set(sql_cols) ^ {'id', *L.COLUMNS, 'desc_norm'})}"


def test_the_workbook_rendered_from_the_ledger_equals_the_current_file(tmp_path):
    """**البوّابةُ الحاسمة (الخارطة أ-٣ · مقعدا المواصفة والبنية P1):** «الإكسل المُرندَر **من الدفتر**
    = الملف الحالي **صفًّا بصفّ** — فرقٌ واحد = توقّف».

    **وهنا تُقابَل الخلايا ورقةً بورقة** (لا الصفوفُ وحدها)، لأنّ نصَّ البوّابةِ الورقةَ: أيُّ فرقٍ في
    خليّة — عمودٌ مُشتقٌّ أو تنسيقُ قيمة — يُسقِط المقابلة. وكان قبل هذا المسارِ قياسٌ طوطولوجيّ يقابل
    الدفترَ بمصدره (قاسه المقعدان)، والآن يمرّ الرندرُ فعليًّا من القاعدة عبر `to_xlsx --from-ledger`.

    **وقد كانت مفتوحةً بإعلانٍ صادق** (`xfail strict`) لأنّ الرندرَ من الدفتر كان يُصفّر مدين/دائن؛
    وطعنَ مقعدُ التثبيت إعلاني: ليست `opening` وحدَه بل **أربعةُ أعمدةٍ تفقد نوعَها** (قِيس: إصلاحُ واحدٍ
    يُبقي 11881 خليّةً مختلفة، و`strict` لا تصيح على إصلاحٍ جزئيّ). فصُنعت سياسةُ الأنواع المُعلَنة في
    الوحدة (`BOOL_COLUMNS`/`INT_COLUMNS`/`DEC_COLUMNS`) ⇒ ** XPASS فأسقط المجموعةَ حتى نُزع الوسمُ**،
    وهذا هو الحرسُ ذاتيُّ التنظيف يعمل: البوّابةُ الآن بوّابةٌ لا إعلان.
    """
    run = ROOT / "data" / "local_sample" / "slice_629p_v2"
    if not (run / "results").exists():
        pytest.skip("لا بياناتُ المالك هنا — البوّابةُ الحاسمةُ تُقاس حيث يوجد المصدر")
    import openpyxl                     # noqa: PLC0415
    import to_xlsx                      # noqa: PLC0415

    db = tmp_path / "gate.sqlite"
    rows, _report, per_page, _flags = to_xlsx.load(run)
    conn = L.open_ledger(db)
    L.ingest(conn, rows, per_page)
    conn.close()

    plain, from_db = tmp_path / "plain.xlsx", tmp_path / "from-ledger.xlsx"
    prof = ROOT / "profiles" / "al-rajhi.json"       # العقدُ كما يمرّرهما `main`
    to_xlsx.build(run, plain, None, profile=prof)
    to_xlsx.build(run, from_db, None, profile=prof, ledger_db=db)
    wa, wb = openpyxl.load_workbook(plain), openpyxl.load_workbook(from_db)
    assert wa.sheetnames == wb.sheetnames, (wa.sheetnames, wb.sheetnames)
    diffs = []
    for name in wa.sheetnames:
        sa, sb = wa[name], wb[name]
        for r in range(1, max(sa.max_row, sb.max_row) + 1):
            for c in range(1, max(sa.max_column, sb.max_column) + 1):
                va, vb = sa.cell(r, c).value, sb.cell(r, c).value
                if va != vb:
                    diffs.append((name, r, c, va, vb))
    assert not diffs, (f"الرندرُ من الدفتر خالف الملفَّ: {len(diffs)} فرقًا · "
                       f"أوّلُها {diffs[0]}")


def test_each_state_is_named_by_its_own_cause(tmp_path):
    """**مقعدُ التثبيت P3 · مُثبت:** `unable to open database file` كانت تُسمّى `unsupported` («البيئةُ لا
    تدعم») وهي في الحقيقة **مسارٌ أو إذن** ⇒ علاجٌ خاطئ (بناءُ البيئة بدل تصحيح المسار). والآن لكلٍّ اسمُه،
    وتُقاس الحالاتُ الثلاثُ بالفعل لا بالوصف: مجلّدٌ كقاعدة، وملفٌّ بلا إذن قراءة، ونصٌّ ليس قاعدةً.
    """
    d = tmp_path / "a_directory"
    d.mkdir()
    no_perm = tmp_path / "no_perm.sqlite"
    # **ولا `serialize()` هنا (عطبٌ قِيس بعد الهبوط · مُثبت):** كانت تُنتج بايتاتِ قاعدةٍ في الذاكرة،
    # وهي **تسقط في بايثون ٣.١٢** (`sqlite3.OperationalError: unable to serialize 'main'`) وتمرّ في ٣.١١
    # ⇒ **فبوّابةٌ خضراءُ في بيئة المالك حمراءُ في بيئة الـCI**. والغرضُ بايتاتٌ فقط: فحالُ الإذن
    # يُرفع **قبل** قراءة المحتوى، فالمحتوى لا يُهمّ — والدرس: **الضابطُ الجديدُ يُشغَّل في مفسِّرَي
    # الـCI معًا (٣.١١ و٣.١٢)، لا في مفسّرِ المالك وحدَه.**
    no_perm.write_bytes(b"x")
    no_perm.chmod(0o000)
    text = tmp_path / "not_a_db.sqlite"
    text.write_text("هذا نصٌّ لا قاعدة", encoding="utf-8")

    cases = [(d, L.UNREADABLE), (no_perm, L.UNREADABLE), (text, L.CORRUPT),
             (tmp_path / "ghost.sqlite", L.MISSING)]
    seen = {}
    for path, want in cases:
        with pytest.raises(L.LedgerUnavailable) as ei:
            L.read_ledger(path)
        seen[str(path.name)] = ei.value.state
        assert ei.value.state == want, f"{path.name}: {ei.value.state} ≠ {want}"
    no_perm.chmod(0o600)          # نظافةُ tmp
    assert L.UNSUPPORTED not in seen.values(), "ما زال عطبُ المسار/الإذن يُسمّى «بيئة»"


def test_the_ingest_consumes_the_real_builder_when_the_data_is_here():
    """**مصدرٌ واحد:** الدفترُ يستهلك مخرَجَ `to_xlsx.load` نفسَه — لا نسخةً ثانيةً من بنائه."""
    run = ROOT / "data" / "local_sample" / "slice_629p_v2"
    if not (run / "results").exists():
        pytest.skip("لا بياناتُ المالك هنا — البوّابةُ تقيس المصدرَ حيث يوجد")
    import to_xlsx                       # noqa: PLC0415

    rows, _report, per_page, _flags = to_xlsx.load(run)
    assert rows and per_page
    assert set(rows[0]) >= (set(L.COLUMNS) - {"pg", "proof_source"}) | {"page", "source"}, \
        "أسماءُ الرندر تغيّرت — والدفترُ يتبعها"


def test_the_ledger_rows_are_the_render_rows_field_by_field(tmp_path):
    """**النصفُ الثاني من البوّابة الحاسمة (الخارطة أ-٣):** «الإكسل المُرندَر من الدفتر = الملف الحالي صفًّا بصفّ».

    **وحدُّ هذا القياس مُعلَن:** يُقابَل **الصفُّ** لا الخليّةُ في `xlsx` — لأنّ الورقةَ دالّةٌ صرفٌ في
    صفوفها (لا حالةَ مخفيّةً بين `load` و`write`)، فمقابلةُ الصفوف بجميع أعمدتها العشرين هي المقابلةُ
    التي تعنيها البوّابة. ومقابلةُ الخلايا ورقةً بورقة تبقى تحقّقًا زائدًا لا يُدّعى هنا.
    """
    run = ROOT / "data" / "local_sample" / "slice_629p_v2"
    if not (run / "results").exists():
        pytest.skip("لا بياناتُ المالك هنا — البوّابةُ تُقاس حيث يوجد المصدر")
    import to_xlsx                       # noqa: PLC0415

    rows, _report, per_page, _flags = to_xlsx.load(run)
    conn, _ = _fresh(tmp_path)
    L.ingest(conn, rows, {p: e for p, e in per_page.items()} if isinstance(per_page, dict) else per_page)
    back = L.read_rows(conn)
    assert len(back) == len(rows), f"عددُ الصفوف: {len(back)} مقابل {len(rows)}"
    for want, have in zip(rows, back, strict=True):
        for col in L.COLUMNS:
            assert _same(_want(want, col), have[col]), \
                f"صفحة {want.get('page')} صفّ {want.get('row_no')} عمود {col}: {_want(want, col)!r} ≠ {have[col]!r}"
    conn.close()


def test_the_intents_are_a_closed_list_and_nothing_else_is_answerable(tmp_path):
    """**البندُ الثاني («النموذجُ لا يكتب SQL») · مُثبت:** الواجهةُ **مغلقةٌ** — قصدٌ من ستّة، ومعاملٌ
    بقيمة. و«لا يكتب SQL» دعوى لا تصحّ بنصٍّ في وثيقة، بل بواجهةٍ لا يملك فيها النداءُ إلا اختيارَ قصد.
    """
    conn, _ = _fresh(tmp_path)
    L.ingest(conn, _rows(2), _pages())
    for intent in L.INTENTS:
        got = L.answer(conn, intent)
        assert got["intent"] == intent, intent
    assert tuple(L.INTENTS) == ("coverage", "unproven", "totals", "search", "pages", "qa")
    with pytest.raises(ValueError, match="قصدٌ غيرُ مُعدَّد"):
        L.answer(conn, "SELECT * FROM rows_verified")
    conn.close()
    # **ونهايةً إلى نهاية:** الأداةُ ترفض غير المُعدَّد بالرمز ٢ (لا بانهيار) — قِيس بـsubprocess.
    db = tmp_path / "cli.sqlite"
    c = L.open_ledger(db); L.ingest(c, _rows(2), _pages()); c.close()
    for bad in ("SELECT * FROM rows_verified", "drop"):
        out = subprocess.run([sys.executable, str(ROOT / "tools" / "ledger.py"),
                              "ask", "--db", str(db), bad],
                             capture_output=True, text=True, cwd=ROOT)
        assert out.returncode == 2, (bad, out.returncode, out.stderr[-200:])


def test_the_money_totals_come_back_exact(tmp_path):
    """**قصدُ `totals` · مُثبت:** المجموعُ نصٌّ عشريٌّ لا عائم — لأنّ `SUM()` على عمودٍ نصّيٍّ في SQLite
    يُحوّل إلى `REAL`، والمالُ أوّلُ ما يُسقِط العائمُ تدقيقه.
    """
    src = _rows(3)
    conn, _ = _fresh(tmp_path)
    L.ingest(conn, src, _pages())
    out = L.answer(conn, "totals")
    # **والتوقّعُ يُشتقّ من المصدر نفسِه** (لا رقمٌ مكتوبٌ بيد): مجموعُ مدين الصفوف المصدرية بعشريّة.
    from decimal import Decimal as D                    # noqa: PLC0415
    want = sum((D(r["movement"]) for r in src if r["side"] == "debit" and r["movement"]), D("0"))
    assert isinstance(out["debit"], str) and "." in out["debit"], out
    assert D(out["debit"]) == want, (out["debit"], str(want))
    assert out["rows_counted"] == 3
    conn.close()


def test_the_schema_version_is_stamped_and_foreign_versions_are_refused(tmp_path):
    """**البندُ الرابع (الترقيم) · مُثبت:** الدفترُ **مُشتقٌّ** — فقاعدةٌ أقدمُ من الكود تُعاد (رخيصةٌ
    ومُتاحة)، وقاعدةٌ أحدثُ **لا تُقرأ** بمخطَّطٍ لا يعرفه الكاتب، وما بينهما **لا يُخمَّن**.
    """
    fresh = tmp_path / "fresh.sqlite"
    conn = L.open_ledger(fresh)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == L.SCHEMA_VERSION
    conn.close()

    newer = tmp_path / "newer.sqlite"
    c = sqlite3.connect(newer); c.execute("PRAGMA user_version = 99")
    c.execute("CREATE TABLE x(a)"); c.commit(); c.close()
    with pytest.raises(L.LedgerUnavailable) as ei:
        L.read_ledger(newer)
    assert ei.value.state == L.NEWER, ei.value.state

    old = tmp_path / "old.sqlite"
    c = sqlite3.connect(old); c.execute("CREATE TABLE rows_verified(a)"); c.commit(); c.close()
    with pytest.raises(L.LedgerUnavailable) as ei:
        L.read_ledger(old)                       # user_version = 0 مع جداول ⇒ مخطَّطٌ مجهولٌ بالنصّ
    assert ei.value.state == L.OUTDATED, ei.value.state


def test_every_intent_renders_on_the_human_path_too(tmp_path):
    """**البوّابةُ التي كان يجب أن تمسك `tools/ledger.py:84`** (مقعدُ الترتيب P1 · مُثبت: `ask pages`
    بلا `--json` ⇒ `KeyError: 'row_count'`):

    كانت ضوابطي تُشغّل الـCLI بـ**مسار `--json` وحدَه**، فمرّ عطبُ سطرِ العرض. والقاعدةُ المستفادة:
    **واجهةٌ تُقاس على مسارٍ واحدٍ تُخفي النصفَ الآخر** — فكلُّ قصدٍ يُقاس هنا على **مسارَيه معًا**
    (إنسانيّ + JSON)، ومعها حالُ فشلٍ معروف (قاعدةٌ غائبة ⇒ خروجٌ مسمًّى بالرمز ٢ لا traceback).
    """
    db = tmp_path / "cli.sqlite"
    c = L.open_ledger(db); L.ingest(c, _rows(3), _pages()); c.close()
    for intent in L.INTENTS:
        for extra in ([], ["--json"]):
            out = subprocess.run([sys.executable, str(ROOT / "tools" / "ledger.py"), "ask",
                                  "--db", str(db), intent, *extra],
                                 capture_output=True, text=True, cwd=ROOT)
            assert out.returncode == 0, (intent, extra, out.returncode, out.stderr[-300:])
            assert "Traceback" not in out.stderr, (intent, extra, out.stderr[-300:])
        assert out.stdout.strip(), f"القصدُ {intent} لم يُخرج شيئًا"
    miss = subprocess.run([sys.executable, str(ROOT / "tools" / "ledger.py"), "ask",
                           "--db", str(tmp_path / "ghost.sqlite"), "coverage"],
                          capture_output=True, text=True, cwd=ROOT)
    assert miss.returncode == 2, (miss.returncode, miss.stderr[-200:])
    assert "Traceback" not in miss.stderr and "غيرُ موجودة" in miss.stderr, miss.stderr[-200:]
