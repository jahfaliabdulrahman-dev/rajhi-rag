"""Regression tests for the accepted Track A audit fixes: parsing, QA tools on the ledger path, app contracts, and docs.

The scope-gate and OpenRouter ZDR parts of the outside fix are not landed (owner's decision pending),
so their tests are not here either."""
from __future__ import annotations

import ast
import io
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_qa import bank_check, footer_oracle, ledger, qa_tools, vlm_reader  # noqa: E402
from statement_qa.legacy.arabic_digit_parser import norm_num, norm_num_decimal  # noqa: E402
from statement_qa.session import Session  # noqa: E402


@pytest.fixture(autouse=True)
def _ci_env_defaults(monkeypatch):
    """Keep all Track A unit tests free of owner keys and clean of env bleed."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-ci-only")


def _synthetic_ledger(tmp_path: Path):
    rows = [
        {
            "page": 1, "row_no": 1, "printed_page": 1,
            "date": "2026-01-10", "date_iso": "2026-01-10",
            "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
            "desc": "الرصيد الافتتاحى",
            "printed_movement": None, "printed_balance": "0.00",
            "movement": None, "balance": "0.00",
            "derived_movement": "0.00", "side": "", "opening": True,
            "chain_ok": True, "row_state": "رصيد افتتاحي", "source": "السلسلة",
            "shift": "", "footer": "ok", "counted": 0,
        },
        {
            "page": 1, "row_no": 2, "printed_page": 1,
            "date": "2026-01-11", "date_iso": "2026-01-11",
            "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
            "desc": "تحويل إلى إبراهيم - مكتبة الإسكندرية",
            "printed_movement": "100.00", "printed_balance": "100.00",
            "movement": "100.00", "balance": "100.00",
            "derived_movement": "100.00", "side": "credit", "opening": False,
            "chain_ok": True, "row_state": "حركة مثبتة بالسلسلة", "source": "السلسلة",
            "shift": "", "footer": "ok", "counted": 1,
        },
        {
            "page": 1, "row_no": 3, "printed_page": 1,
            "date": "2026-01-12", "date_iso": "2026-01-12",
            "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
            "desc": "حوالة إلى شركه الراجحى",
            "printed_movement": "250.00", "printed_balance": "350.00",
            "movement": "250.00", "balance": "350.00",
            "derived_movement": "250.00", "side": "", "opening": False,
            "chain_ok": True, "row_state": "حركة غير محسومة الجهة", "source": "السلسلة",
            "shift": "", "footer": "ok", "counted": 1,
        },
        {
            "page": 1, "row_no": 4, "printed_page": 1,
            "date": "2026-01-13", "date_iso": "2026-01-13",
            "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
            "desc": "عملية غير مصنفة",
            "printed_movement": "150.00", "printed_balance": "500.00",
            "movement": "150.00", "balance": "500.00",
            "derived_movement": "150.00", "side": "", "opening": False,
            "chain_ok": True, "row_state": "حركة غير محسومة الجهة", "source": "السلسلة",
            "shift": "", "footer": "ok", "counted": 1,
        },
    ]
    pages = {1: {"page_no": 1, "footer": "ok", "rows": 4}}
    conn = ledger.open_ledger(tmp_path / "ledger.sqlite")
    ledger.ingest(conn, rows, pages, n_pages=1)
    return conn


def test_p0_1_p0_2_p1_3_qa_tools_exact_decimal_undecided_and_arabic_norm(tmp_path):
    conn = _synthetic_ledger(tmp_path)
    try:
        tools = {t.name: t for t in qa_tools.make_qa_tools(conn=conn)}
        # P0-1: exact Decimal scale comparison ("100" matches "100.00", "100.5" does not)
        cnt_100 = tools["count_movements"].invoke({"side": "الكل", "amount": 100})
        assert "العدد = 1" in cnt_100, cnt_100
        cnt_miss = tools["count_movements"].invoke({"side": "الكل", "amount": 100.5})
        assert "العدد = 0 حركة" in cnt_miss, cnt_miss

        # P0-2: undecided rows with Decimal/str movements sum cleanly without TypeError
        summary = tools["page_summary"].invoke({"page": 1})
        assert "غير محسوم" in summary and "400.00" in summary, summary

        # P1-3: Arabic hamza / taa marbuta / alif maqsura / "الى" normalization in search
        assert "العدد = 1" in tools["count_movements"].invoke({"side": "الكل", "keyword": "ابراهيم"})
        assert "العدد = 1" in tools["count_movements"].invoke({"side": "الكل", "keyword": "الاسكندرية"})
        assert "1 حركة مطابقة" in tools["search_rows"].invoke({"keyword": "شركة الراجحي"})
    finally:
        conn.close()


def test_unread_note_reports_mismatch_and_gap_pages(tmp_path):
    base_rows = [
        {
            "page": 1, "row_no": 1, "printed_page": 1,
            "date": "2026-01-10", "date_iso": "2026-01-10",
            "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
            "desc": "حوالة", "printed_movement": "100.00", "printed_balance": "100.00",
            "movement": "100.00", "balance": "100.00",
            "derived_movement": "100.00", "side": "credit", "opening": False,
            "chain_ok": True, "row_state": "حركة مثبتة بالسلسلة", "source": "السلسلة",
            "shift": "", "footer": "ok", "counted": 1,
        },
        {
            "page": 2, "row_no": 1, "printed_page": 2,
            "date": "2026-01-11", "date_iso": "2026-01-11",
            "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
            "desc": "سحب", "printed_movement": "50.00", "printed_balance": "50.00",
            "movement": "50.00", "balance": "50.00",
            "derived_movement": "50.00", "side": "debit", "opening": False,
            "chain_ok": True, "row_state": "حركة مثبتة بالسلسلة", "source": "السلسلة",
            "shift": "", "footer": "mismatch", "counted": 1,
        },
        {
            "page": 3, "row_no": 1, "printed_page": 3,
            "date": "2026-01-12", "date_iso": "2026-01-12",
            "date_status": "ok", "date_source": "من خانة الورق", "year": 2026,
            "desc": "إيداع", "printed_movement": "25.00", "printed_balance": "75.00",
            "movement": "25.00", "balance": "75.00",
            "derived_movement": "25.00", "side": "credit", "opening": False,
            "chain_ok": True, "row_state": "حركة مثبتة بالسلسلة", "source": "السلسلة",
            "shift": "", "footer": "gap", "counted": 1,
        },
    ]
    conn_warn = ledger.open_ledger(tmp_path / "warn.sqlite")
    try:
        ledger.ingest(
            conn_warn,
            base_rows,
            {
                1: {"page_no": 1, "footer": "ok", "rows": 1},
                2: {"page_no": 2, "footer": "mismatch", "rows": 1},
                3: {"page_no": 3, "footer": "gap", "rows": 1},
            },
            n_pages=3,
        )
        tools_warn = {t.name: t for t in qa_tools.make_qa_tools(conn=conn_warn)}
        out = tools_warn["closing_balance"].invoke({})
        assert "صفحات غير مطابقة للتذييل: ص2" in out, out
        assert "فجوة مسح (أوراق غائبة): ص3" in out, out
    finally:
        conn_warn.close()

    conn_ok = _synthetic_ledger(tmp_path)
    try:
        tools_ok = {t.name: t for t in qa_tools.make_qa_tools(conn=conn_ok)}
        assert "⚠" not in tools_ok["closing_balance"].invoke({})
    finally:
        conn_ok.close()


def test_p1_4_arabic_digit_parser_pure_decimal_and_malformed_rejection():
    big = ("9" * 17) + ".25"
    assert norm_num_decimal(big) == Decimal(big)
    assert norm_num_decimal("−٥٠٠٫٢٥") == Decimal("-500.25")
    assert norm_num_decimal("250.50-") == Decimal("-250.50")
    assert norm_num_decimal("12,34567") == Decimal("12345.67")
    assert norm_num("٣٠٠,٠٠") == 300.0
    for bad in ("1.2.3", "12.3,4", "12,3", "12,3456", "12,345678", ",123", ",12345"):
        assert norm_num_decimal(bad) is None, f"should reject {bad!r}"


def test_p1_5_vlm_reader_json_date_and_trailing_minus_chain():
    prose = 'ملاحظة [1]\n```json\n[{"amount": "200.00",}]\n```\nانظر [ص2]'
    assert vlm_reader._extract_json(prose) == [{"amount": "200.00"}]
    mixed = 'Note [1]: {"rows": [{"amount": "100.00",}]} tail [2]'
    assert vlm_reader._extract_json(mixed) == {"rows": [{"amount": "100.00"}]}

    assert vlm_reader._clean_date(None, "سحب 2024/03/15") == "2024/03/15"
    assert vlm_reader._clean_date("None", "تحويل 2024-02-29") == "2024-02-29"
    assert vlm_reader._clean_date(None, "حوالة ١٤٤٥١٠٠٥") == "١٤٤٥١٠٠٥"
    assert vlm_reader._clean_date(None, "مرجع 88123456") is None

    rows = [
        {
            "balance": vlm_reader._parse_amount("300.00"),
            "movement": None, "desc": "رصيد سابق", "kind": "opening",
        },
        {
            "balance": vlm_reader._parse_amount("181.00"),
            "movement": vlm_reader._parse_amount("١١٩.٠٠-"),
            "desc": "سحب", "kind": "txn",
        },
    ]
    derived = vlm_reader.chain_derive(rows)
    assert derived[1]["ok"] is True
    assert derived[1]["derived_movement"] == Decimal("119.00")
    assert derived[1]["side"] == "debit"

    boundary = vlm_reader.chain_derive(
        [{
            "balance": vlm_reader._parse_amount("181.00"),
            "movement": vlm_reader._parse_amount("١١٩.٠٠-"),
            "desc": "سحب", "kind": "txn",
        }],
        prev_balance=Decimal("300.00"),
    )
    assert boundary[0]["boundary"] == "txn"
    assert boundary[0]["derived_movement"] == Decimal("119.00")


def test_pil_image_handles_closed_in_footer_oracle_and_bank_check(tmp_path, monkeypatch):
    png = tmp_path / "page.png"
    Image.new("RGB", (80, 120), "white").save(png, format="PNG")
    opened = []
    real_open = Image.open

    def _tracked_open(*args, **kwargs):
        im = real_open(*args, **kwargs)
        opened.append(im)
        return im

    monkeypatch.setattr(footer_oracle.Image, "open", _tracked_open)
    monkeypatch.setattr(bank_check.Image, "open", _tracked_open)

    crop_bytes = footer_oracle._footer_crop_png(str(png))
    band_bytes = bank_check._band_png(str(png), 0.0, 0.25)
    assert len(opened) == 2
    assert all(getattr(im, "fp", None) is None for im in opened)
    with real_open(io.BytesIO(crop_bytes)) as crop_im:
        assert crop_im.size[0] == 80
    with real_open(io.BytesIO(band_bytes)) as band_im:
        assert band_im.size[0] == 80


def _compile_app_functions(*names: str, namespace: dict) -> dict:
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    mod = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(ROOT / "app.py"), "exec"), namespace)
    return namespace


def test_app_track_a_contracts_and_extracted_helpers(tmp_path):
    app_src = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(app_src)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    # Check try/finally closes `pages` inside _process_pdf_locked
    locked = funcs["_process_pdf_locked"]
    try_nodes = [n for n in ast.walk(locked) if isinstance(n, ast.Try) and n.finalbody]
    assert any(
        any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "close"
            for fstmt in t.finalbody for c in ast.walk(fstmt))
        for t in try_nodes
    ), "_process_pdf_locked must close pages in finally"

    # Check _lock_path(sess) used by process_pdf and _delete_statement_click
    for fname in ("process_pdf", "_delete_statement_click"):
        calls = [
            c for c in ast.walk(funcs[fname])
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "job_lock"
        ]
        assert calls and any(
            isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == "_lock_path"
            for c in calls for a in c.args
        ), f"{fname} must pass _lock_path(sess) to job_lock"

    # Execute actual _lock_path compiled from app.py
    local_lock = tmp_path / "global_job.lock"
    ns = _compile_app_functions(
        "_lock_path", "_evidence_from_numbers", "_page_rows_df",
        namespace={
            "Path": Path,
            "Session": Session,
            "LOCK_PATH": local_lock,
            "_EVIDENCE_CAP": 50,
            "_n_rows_ar": lambda n: f"{n} صفوف",
            "_row_record": lambda i, r, _v: {"#": i, "seq": r.get("seq"), "page": r.get("page")},
            "pd": SimpleNamespace(DataFrame=lambda recs=(): recs),
        },
    )
    pub_a = Session.public()
    pub_b = Session.public()
    try:
        assert ns["_lock_path"](pub_a) == pub_a.home / "job.lock"
        assert ns["_lock_path"](pub_b) == pub_b.home / "job.lock"
        assert ns["_lock_path"](pub_a) != ns["_lock_path"](pub_b)
        assert ns["_lock_path"](Session.local(tmp_path)) == local_lock
    finally:
        pub_a.close()
        pub_b.close()

    # Execute actual _evidence_from_numbers & _page_rows_df with non-contiguous seq [1, 3, 7]
    sess = SimpleNamespace(state={
        "rows": [
            {"seq": 1, "page": 1},
            {"seq": 3, "page": 1},
            {"seq": 7, "page": 2},
        ],
        "verdicts": {},
    })
    ev_rows, note = ns["_evidence_from_numbers"](sess, [7])
    assert ev_rows == [{"#": 7, "seq": 7, "page": 2}], (ev_rows, note)
    pg_rows = ns["_page_rows_df"](sess, {"page": 1})
    assert pg_rows == [{"#": 1, "seq": 1, "page": 1}, {"#": 3, "seq": 3, "page": 1}]


def test_delivery_report_contradictions_resolved():
    text = (ROOT / "docs" / "DELIVERY_REPORT.md").read_text(encoding="utf-8")
    for stale in (
        "البياناتُ لا تغادر الجهاز",
        "لا مبلغَ حقيقيٍّ يغادر الجهاز",
        "ثماني أدوات",
        "MemorySaver",
        "شريطُ «دفترُ الكشف»",
    ):
        assert stale not in text, f"عبارة متناقضة ما زالت في DELIVERY_REPORT.md: {stale!r}"
    assert "OpenRouter" in text
    assert "SqliteSaver" in text
    assert "اثنتا عشرة أداة" in text and "الاثنتي عشرة أداةً" in text
