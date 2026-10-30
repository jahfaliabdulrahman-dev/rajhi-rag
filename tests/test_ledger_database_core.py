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
    """**مسارٌ واحد — بالبناء (R132-2):** المفتاحُ من **هويّة المصدر** (`source_sha256`) وحدَها،
    فالواجهةُ والـCLI يُنتجان المفتاحَ نفسَه لنفس البايتات. وبلا هويّةٍ **يرفض** الـCLI بدل أن
    يكتب على مفتاحِ صيغةِ الأرقام (الاحتياطيُّ الذي حُذف).
    """
    import pytest

    import ledger as cli

    sha = "b" * 64
    key = L.statement_key(sha)
    assert cli.default_db({"source": {"sha256": sha}}).name == f"{key}.sqlite"
    with pytest.raises(ValueError):
        cli.default_db({})
    with pytest.raises(ValueError):
        L.statement_key("")


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


def test_a_ledger_rebuilt_from_its_own_rows_is_the_same_ledger(tmp_path):
    """**`read_rows` عكسُ `_row_values` تمامًا (2026-10-30):** صفوفٌ تُقرأ من القاعدة ثمّ تُكتب في
    قاعدةٍ جديدة تُعطي القاعدةَ نفسَها عمودًا عمودًا. كان `proof_source` يعود باسم العمود والكاتبُ
    يقرأ `source` ⇒ كلُّ إثباتٍ يُكتب فارغًا. ويقرأ هذا المسارَ: إعادةُ البناء بعد إعادة التشغيل ·
    الإكسلُ من حالةٍ مستعادة · ودفترُ «جرّب الآن» المبنيُّ من ملفٍّ نصّيّ.
    """
    first = L.open_ledger(tmp_path / "first.sqlite")
    second = L.open_ledger(tmp_path / "second.sqlite")
    try:
        L.ingest(first, _rows((1, 2)), _pages((1, 2)))
        rows = L.read_rows(first)
        L.ingest(second, rows, L.pages_from_state(rows, L.read_footers(first)))
        again = L.read_rows(second)
        unproven = (L.answer(first, "coverage")["unproven"], L.answer(second, "coverage")["unproven"])
    finally:
        first.close()
        second.close()
    assert len(again) == len(rows) == 6
    for want, have in zip(rows, again, strict=True):
        for col in L.COLUMNS:
            assert have[col] == want[col], f"صفّ {want['seq']} عمود {col}: {want[col]!r} ⇒ {have[col]!r}"
    assert unproven[1] == unproven[0], f"«بلا إثبات» تغيّر بإعادة البناء: {unproven}"


def test_two_different_sources_never_share_a_key(tmp_path):
    """**R131-2 (P1):** الهويّةُ من محتوى المصدر لا من صيغة الطباعة. كشفان بالصيغة والطول نفسَيهما
    كانا يتصادمان (البصمةُ أنماطُ طباعةٍ لا هويّة) ⇒ قراءةُ الثاني تمحو صفوفَ الأوّل. والآن
    `source_sha` هي الحاكم، والملفُّ نفسُه يُعطي المفتاحَ نفسَه في الواجهة والـCLI.
    """
    import hashlib

    import ledger as cli

    def sha(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    a, b = sha(b"%PDF-1.4 same-length-A"), sha(b"%PDF-1.4 same-length-B")
    key_a, key_b = L.statement_key(a), L.statement_key(b)
    assert key_a != key_b, "كشفان مختلفان اشتركا في مفتاحٍ واحد"
    assert L.statement_key(a) == key_a, "المفتاحُ تبع شيئًا غير المصدر"
    assert cli.default_db({"source": {"sha256": a}}).name == f"{key_a}.sqlite"


def test_an_incomplete_reread_leaves_one_contiguous_numbering(tmp_path):
    """**R131-3 (P1):** الصفحةُ التي تعثّرت في إعادة القراءة لا تُترك صفوفُها القديمةُ بأرقامها —
    فتصير الشاشةُ ٦ والقاعدةُ ٩ والرقمُ الواحدُ لصفّين. السياسةُ واحدة: صفوفُ القاعدة = صفوفُ هذه
    القراءة، و`seq` فريدٌ متّصل، والصفحةُ الغائبةُ تُسمّى (في سطر الحالة).
    """
    conn = L.open_ledger(tmp_path / "inc.sqlite")
    try:
        L.ingest(conn, _rows((1, 2, 3)), _pages((1, 2, 3)))
        first = L.read_rows(conn)
        assert len(first) == 9
        # إعادةُ قراءةٍ تعثّرت فيها الثانية: تُقرأ ١ و٣ وحدَهما (الصفحةُ ٢ تُسمّى في الحالة)
        L.ingest(conn, _rows((1, 3)), _pages((1, 3)))
        now = L.read_rows(conn)
        assert {r["page"] for r in now} == {1, 3}, "صفوفُ الصفحة المتعثّرة بقيت تُخدَم"
        assert [r["seq"] for r in now] == list(range(1, len(now) + 1)), [r["seq"] for r in now]
        assert len({r["seq"] for r in now}) == len(now)
    finally:
        conn.close()


def test_the_source_identity_has_exactly_one_home():
    """**قبولُ R132-2:** دالّةُ هويّةٍ واحدة بـ`hashlib.file_digest`، ولا حلقةَ تجزئةٍ ثانية في
    المسارات الثلاثة. كان في كلٍّ منها حلقةٌ يدويّةٌ للشيء نفسه — وتفرّقُ النسخِ يُفرّق المفاتيح.
    """
    root = Path(__file__).resolve().parents[1]
    ledger_src = (root / "src" / "statement_qa" / "ledger.py").read_text(encoding="utf-8")
    assert "hashlib.file_digest" in ledger_src, "الهويّةُ لم تُبنَ على file_digest"
    for rel in ("app.py", "tools/scale_slice.py", "tools/ledger.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert ("import hashlib" not in src and "file_digest(" not in src
                and "sha256()" not in src), f"{rel}: نسخةُ تجزئةٍ ثانية"
    # **وحلقةُ القراءة بالقطع نفسُها لا تُنسخ (R133-4):** ثلاثُ نسخٍ أقدم في الأدوات كانت
    # `sha256()` + `fh.read(1 << 20)` — والمكتبةُ القياسيّة تحمل `file_digest` منذ 3.11.
    for rel in ("tools/capture_training.py", "tools/backfill_reader_stamp.py",
                "tools/render_pages.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "1 << 20" not in src and "sha256()" not in src, f"{rel}: حلقةُ تجزئةٍ يدويّة"
        assert "file_digest(" in src, f"{rel}: لم تُستعمل file_digest"
