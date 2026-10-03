"""بوّاباتُ دفتر الكشف (أ-٣) — ستُّ بوّابات، كلُّ واحدةٍ تقيس ما تنصّ عليه الخارطة بالاسم.

**والقاعدةُ الحاكمة:** البوّابةُ الحاسمةُ الأولى — **ما كُتب يُقرأ صفًّا بصفّ**. فكلُّ قيدٍ آخر
(المبالغُ TEXT · الفهرسُ لا ينطفئ · التطبيع · الخطأُ المسمّى) يُقاس لأنّه يحمي هذه القراءة.
"""
from __future__ import annotations

import sqlite3
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
            "page": 1, "row_no": i, "printed_page": "١",
            "date": "2026-01-0%d" % i, "date_iso": "2026-01-0%d" % i, "date_status": "ok",
            "date_source": "من خانة الورق", "year": 2026,
            "desc": "حوالة صادرة رقم %d" % i,
            "printed_movement": "10.00", "printed_balance": "15.00",
            "movement": "10.00", "balance": "15.00", "derived_movement": "10.00",
            "side": "debit", "opening": "105.00", "chain_ok": 1,
            "row_state": "حركة", "source": "من خانة الورق", "shift": "",
            "footer": "ok", "counted": 1,
        })
    return out


def _pages() -> dict[int, dict]:
    return {1: {"pg": 1, "page_no": "١", "footer": "ok", "rows": 3}}


def _fresh(tmp_path: Path):
    return L.open_ledger(tmp_path / "ledger.sqlite"), tmp_path / "ledger.sqlite"


def _want(row: dict, col: str):
    """قيمةُ العمود في **الصفّ المصدر**: اسمٌ واحدٌ يختلف — الرندرُ يسمّيها `page` والدفترُ `pg`."""
    return row["page"] if col == "pg" else row[col]


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
    """**قرارُ المالك:** «ويغطّيه حارسا النشر والمبالغ، وضابطٌ يُثبت ذلك» — يُقاس لا يُدّعى."""
    import amount_guard as ag           # noqa: PLC0415
    import publish_guard as pg          # noqa: PLC0415

    p = str(L.ledger_path(ROOT, "alrajhi-1234").relative_to(ROOT))
    assert p.startswith("data/"), p
    assert p.endswith(".sqlite")
    # حارسُ النشر: امتدادُ القاعدة **ممنوعٌ في الشجرة** (BINARY_EXTS) — فالملفُّ لا يُدفع ولو أُضيف.
    assert ".sqlite" in pg.BINARY_EXTS, "الحارسُ لا يمنع امتداد .sqlite"
    # وحارسُ المبالغ: `data/` مجلّدُ أدلّةٍ ثنائيّةٌ عنده ⇒ لا يُنزع منه ملفُّ دليلٍ بلا إعلان.
    assert any(str(b).startswith("data") for b in ag.BINARY_DIRS), \
        "حارسُ المبالغ لا يعدّ data/ من مجلدات الأدلّة"
    # ومسارُ الدفتر **ليس** تحت مسار بيانات العيّنة، فهو محروسٌ بالامتداد لا بالمسار: يُقاس صريحًا
    # حتى لا يُقرأ لاحقًا كأنّ الملفّ مُهمَلٌ بلا حارس.
    assert not pg.real_data_path(p), "تغيّر مسارُ الدفتر ⇒ يُعاد النظرُ في مصدر حمايته"


def test_the_ingest_consumes_the_real_builder_when_the_data_is_here():
    """**مصدرٌ واحد:** الدفترُ يستهلك مخرَجَ `to_xlsx.load` نفسَه — لا نسخةً ثانيةً من بنائه."""
    run = ROOT / "data" / "local_sample" / "slice_629p_v2"
    if not (run / "results").exists():
        pytest.skip("لا بياناتُ المالك هنا — البوّابةُ تقيس المصدرَ حيث يوجد")
    import to_xlsx                       # noqa: PLC0415

    rows, _report, per_page, _flags = to_xlsx.load(run)
    assert rows and per_page
    assert set(rows[0]) >= (set(L.COLUMNS) - {"pg"}) | {"page"}, \
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
