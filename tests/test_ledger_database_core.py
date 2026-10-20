"""بوّابةُ قاعدة البيانات في القلب (R130 · الخيار ١) — ما يخصّ **القاعدة** لا الشاشة.

**العِلّة:** قرارُ المالك (بكلمته) نقلَ الدفترَ من «زرٍّ جانبيّ» إلى **قلبِ النظام**: القراءةُ تكتبه،
والأدواتُ تقرأ منه، والحذفُ يمحوه. والبوّاباتُ هنا تقيس ثلاثةَ ما لا يقيسه غيرُها:

1. **إعادةُ القراءة تُحدّث ولا تُبقي نسخةً قديمة** (صفوفٌ وصفحاتٌ سقطت من القراءة الجديدة تُحذف).
2. **التذييلاتُ المطبوعة تُقرأ من القاعدة** (`page_footer` بلا حالةِ واجهة).
3. **الحذفُ يترك صفرَ ملفّ** (بما فيه `-wal` و`-shm`) — ويُعدّ ما حذفه.
4. **الأسئلةُ تُسجَّل بأدلّتها** (`qa` + `qa_evidence`) — قصدُ «الأسئلة المسجَّلة» كان يعرض فراغًا أبدًا.
5. **بياناتُ المستخدم خارج المستودع** (`data_home`).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from statement_qa import ledger as L  # noqa: E402


def _rows(pages=(1,), per_page=3, desc="حوالة صادرة") -> list[dict]:
    out = []
    for pg in pages:
        for i in range(1, per_page + 1):
            out.append({
                "page": pg, "row_no": i, "printed_page": pg,
                "date": f"2026-03-{i:02d}", "date_iso": f"2026-03-{i:02d}",
                "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
                "desc": f"{desc} {pg}-{i}", "printed_movement": "10.00",
                "printed_balance": "15.00", "movement": "10.00", "balance": "15.00",
                "derived_movement": "10.00", "side": "debit", "opening": False,
                "chain_ok": True, "row_state": "حركة مثبتة بالسلسلة", "source": "السلسلة",
                "shift": "", "footer": "ok", "counted": 1,
            })
    return out


def _pages(pages=(1,), verdict="ok") -> dict:
    return {int(pg): {"page_no": pg, "footer": verdict, "rows": 3} for pg in pages}


def test_a_re_read_removes_the_rows_the_new_read_no_longer_carries(tmp_path):
    """**قبولُ القرار:** «إعادةُ القراءة تُحدّثها ولا تُبقي نسخةً قديمةً تحت جاهز».

    القراءةُ الأولى: صفحتان وستّةُ صفوف. والثانيةُ: صفحةٌ واحدةٌ وثلاثةٌ ⇒ ما سقط يُحذف **باسمه**
    (لا يُترك صفٌّ من الأمس بجانب صفوف اليوم).
    """
    db = tmp_path / "ledger.sqlite"
    conn = L.open_ledger(db)
    try:
        L.ingest(conn, _rows(pages=(1, 2)), _pages(pages=(1, 2)))
        assert len(L.read_rows(conn)) == 6
        stats = L.ingest(conn, _rows(pages=(1,)), _pages(pages=(1,)))
        left = L.read_rows(conn)
    finally:
        conn.close()
    assert len(left) == 3 and {r["pg"] for r in left} == {1}, left
    assert stats["pruned_rows"] == 3 and stats["pruned_pages"] == 1, stats


def test_the_printed_footers_survive_in_the_database(tmp_path):
    """`page_footer` يُجيب من القاعدة: الأرقامُ المطبوعة (مدين/دائن/رصيد) وحكمُها — لا من الشاشة."""
    conn = L.open_ledger(tmp_path / "l.sqlite")
    try:
        pages = _pages()
        pages[1].update({"debits": "1,234.00", "credits": "987.00",
                         "balance": "247.00", "basis": "delta"})
        L.ingest(conn, _rows(), pages)
        got = L.read_footers(conn)
    finally:
        conn.close()
    assert got[1]["debits"] == "1,234.00" and got[1]["credits"] == "987.00"
    assert got[1]["balance"] == "247.00" and got[1]["verdict"] == "ok"
    assert got[1]["basis"] == "delta"


def test_the_questions_are_recorded_with_their_evidence(tmp_path):
    """**قصدُ «الأسئلة المسجَّلة»** (كان `record_qa` بلا مُنادٍ): سؤالٌ وجوابٌ وصفوفُ دليلٍ حقيقيّة."""
    conn = L.open_ledger(tmp_path / "l.sqlite")
    try:
        L.ingest(conn, _rows(), _pages())
        ids = L.row_ids_for(conn, [(1, 1), (1, 2)])
        assert len(ids) == 2
        L.record_qa(conn, "2026-10-20T10:00:00", "كم مجموع الحوالات؟", "المجموع 20.00",
                    ids, refused=False)
        out = L.answer(conn, "qa")
    finally:
        conn.close()
    assert out["qa"] and out["qa"][0]["question"] == "كم مجموع الحوالات؟"
    assert out["qa"][0]["evidence"] == 2, out["qa"][0]


def test_deleting_a_statement_leaves_zero_files(tmp_path):
    """**قبولُ الحذف:** ملفُّ القاعدة و`-wal` و`-shm` — صفرُ ملفّ، وعدٌّ يُذكر."""
    db = tmp_path / "l.sqlite"
    conn = L.open_ledger(db)
    L.ingest(conn, _rows(), _pages())
    conn.close()
    # ملفّاتُ WAL قد تبقى بعد الإغلاق على بعض الأنظمة ⇒ تُنشأ هنا عمدًا ليُقاس حذفُها
    for suffix in ("-wal", "-shm"):
        Path(str(db) + suffix).write_bytes(b"x")
    got = L.delete_statement(db)
    assert got["count"] == 3, got
    assert not list(tmp_path.glob("l.sqlite*")), list(tmp_path.iterdir())


def test_the_user_data_home_is_outside_the_repository(monkeypatch, tmp_path):
    """**قرارُ المالك:** «القاعدةُ في مجلّد بيانات المستخدم وحده، ولا تدخل المستودع»."""
    monkeypatch.delenv("RAJHI_DATA_HOME", raising=False)
    home = L.data_home()
    assert ROOT not in home.parents and home != ROOT, f"بياناتُ المستخدم داخل الشجرة: {home}"
    monkeypatch.setenv("RAJHI_DATA_HOME", str(tmp_path / "h"))
    assert L.data_home() == tmp_path / "h"


def test_the_schema_is_v2_and_a_v1_database_is_named_outdated(tmp_path):
    import sqlite3

    fresh = tmp_path / "fresh.sqlite"
    conn = L.open_ledger(fresh)
    try:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2
        cols = {r[1] for r in conn.execute("PRAGMA table_info(rows_verified)")}
        assert "seq" in cols
    finally:
        conn.close()
    old = tmp_path / "old.sqlite"
    c = sqlite3.connect(old)
    c.execute("PRAGMA user_version = 1")
    c.execute("CREATE TABLE rows_verified(a)")
    c.commit()
    c.close()
    try:
        L.read_ledger(old)
    except L.LedgerUnavailable as e:
        assert e.state == L.OUTDATED
    else:                                          # pragma: no cover
        raise AssertionError("قاعدةُ v1 قُرئت بمخطَّط v2")


def test_the_ui_and_the_cli_sign_the_same_statement_with_the_same_key(tmp_path):
    """**مسارٌ واحد — بالبناء لا بالصدفة (إصلاحُ المقاعد الثلاثة P1):** الواجهةُ تُجزّئ بصمةَ
    `fingerprint_pages` كاملةً (ستّة حقول)، وتقريرُ التشغيل يكتب أربعة (بلا `per_page`/`majority`)
    ⇒ كانت تجزئتان مختلفتان لكشفٍ واحد وقاعدتان. والمفتاحُ الآن من **الحقول المشتركة** وحدها.
    """
    import ledger as cli

    full = {"overall": "o", "styles": {"a": 1}, "transitions": {"b": 2}, "outliers": [],
            "per_page": {1: {"rows": 2}}, "majority": "m"}
    report_era = {k: full[k] for k in ("overall", "styles", "transitions", "outliers")}
    pages = _pages((1, 2))

    ui_key = L.statement_key(full, 626)          # عددُ صفوف العرض
    cli_key = L.statement_key(report_era, 629)   # عددُ صفحات التقرير
    assert ui_key == cli_key, (ui_key, cli_key)
    assert cli.default_db({"era": report_era}, pages).name == f"{ui_key}.sqlite"
    # وبلا بصمةٍ يُعلَن النقصُ في الاسم بدل مفتاحٍ يكذب
    assert cli.default_db({}, pages).name.startswith("st_nop-")


def test_the_scope_gate_reads_the_page_dimension_from_the_database(tmp_path):
    """**حاجزُ الصدق فقد بُعده (مقعدا المواصفة والمعايير P2):** صفوفُ القاعدة تحمل `pg` و`_data_facts`
    يقرأ `page` ⇒ `max_page=None` و`pages_read=∅`، فشرطُ «صفحةٌ لم تُقرأ» في `scope.classify` لا يشتغل
    أبدًا على المسار الإنتاجيّ. `read_rows` يُخرج الاسمين، وهذا الضابطُ يقيس ما يصل إلى الحاجز.
    """
    from statement_qa.qa import _data_facts

    path = tmp_path / "scope.sqlite"
    conn = L.open_ledger(path)
    try:
        L.ingest(conn, _rows((1, 2)), _pages((1, 2)))
        rows = L.read_rows(conn)
    finally:
        conn.close()
    _years, max_page, _amounts, pages_read = _data_facts(rows)
    assert max_page == 2, max_page
    assert pages_read == {1, 2}, pages_read
