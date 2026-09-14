"""Footer oracle tests — the accuracy-paradox guard (no network)."""

import json
from decimal import Decimal

from statement_qa import footer_oracle as fo
from statement_qa.footer_oracle import FooterReading, check_page_footer, page_totals


def _chain_rows():
    return [
        {"kind": "opening", "opening": True, "balance": Decimal("0"),
         "side": "", "derived_movement": Decimal("0")},
        {"kind": "txn", "opening": False, "balance": Decimal("300"),
         "side": "credit", "derived_movement": Decimal("300")},
        {"kind": "txn", "opening": False, "balance": Decimal("200"),
         "side": "debit", "derived_movement": Decimal("100")},
        {"kind": "txn", "opening": False, "balance": Decimal("100"),
         "side": "debit", "derived_movement": Decimal("100")},
    ]


def test_page_totals_uses_derived_and_skips_opening():
    t = page_totals(_chain_rows())
    assert t["debits"] == Decimal("200")
    assert t["credits"] == Decimal("300")
    assert t["balance"] == Decimal("100")
    assert t["undecided"] == 0


def test_page_totals_counts_undecided():
    rows = _chain_rows() + [
        {"kind": "txn", "opening": False, "balance": Decimal("150"),
         "side": "", "derived_movement": Decimal("50")}]
    t = page_totals(rows)
    assert t["undecided"] == 1
    assert t["debits"] == Decimal("200")
    assert t["balance"] == Decimal("150")


def test_check_ok_exact():
    f = FooterReading(debits=Decimal("200"), credits=Decimal("300"),
                      balance=Decimal("100"))
    res = check_page_footer(_chain_rows(), f)
    assert res["status"] == "ok"
    assert res["compared"] == 3


def test_check_cumulative_semantics():
    """Footer debits/credits are CUMULATIVE-to-date (verified on the real
    sample: p2 footer 9001.00/9001.00 = p1 650/750 + p2's own 464/600)."""
    prior = {"debits": Decimal("650"), "credits": Decimal("750")}
    rows = [
        {"kind": "txn", "opening": False, "balance": Decimal("236"),
         "side": "debit", "derived_movement": Decimal("464")},
        {"kind": "txn", "opening": False, "balance": Decimal("236"),
         "side": "credit", "derived_movement": Decimal("600")},
    ]
    f = FooterReading(debits=Decimal("1114"), credits=Decimal("1350"),
                      balance=Decimal("236"))
    ok = check_page_footer(rows, f, prior=prior)
    assert ok["status"] == "ok"
    # ...and the SAME page checked with no prior (per-page reading of a
    # cumulative footer) mismatches — the exact bug the oracle caught live.
    bad = check_page_footer(rows, f, prior=None)
    assert bad["status"] == "mismatch"
    assert [d["field"] for d in bad["diffs"]] == ["debits", "credits"]


def test_check_skip_is_unchecked():
    res = check_page_footer(_chain_rows(), FooterReading(
        debits=Decimal("200")), skip=True)
    assert res["status"] == "unchecked"


def test_check_x100_is_paradox():
    # The accuracy-paradox signature: EVERY component off by exactly ×100.
    f = FooterReading(debits=Decimal("2"), credits=Decimal("3"),
                      balance=Decimal("1"))
    res = check_page_footer(_chain_rows(), f)
    assert res["status"] == "mismatch"
    assert res["is_paradox"] is True
    assert len(res["diffs"]) == 3


def test_check_single_component_mismatch_not_paradox():
    f = FooterReading(debits=Decimal("250"), credits=Decimal("300"),
                      balance=Decimal("100"))
    res = check_page_footer(_chain_rows(), f)
    assert res["status"] == "mismatch"
    assert res["is_paradox"] is False
    assert [d["field"] for d in res["diffs"]] == ["debits"]


def test_check_partial_ok_and_absent():
    # Only the balance is readable and it matches -> ok (partial).
    res = check_page_footer(_chain_rows(), FooterReading(balance=Decimal("100")))
    assert res["status"] == "ok" and res["compared"] == 1
    # Nothing readable -> absent.
    assert check_page_footer(_chain_rows(), None)["status"] == "absent"
    assert check_page_footer(_chain_rows(), FooterReading())["status"] == "absent"


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body


def test_read_footer_parses_and_marks_raw(tmp_path, monkeypatch):
    from PIL import Image
    from statement_qa import vlm_reader

    p = tmp_path / "pg.png"
    Image.new("RGB", (60, 400), "white").save(p)

    content = json.dumps({"debits": "٦٥٠,٠٠", "credits": "٧٥٠,٠٠",
                          "balance": "١٠٠,٠٠"}, ensure_ascii=False)
    payload = json.dumps({"choices": [{"message": {"content": content}}],
                          "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                    "cost": 0.001}}, ensure_ascii=False).encode()

    stats: dict = {}
    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(payload))
    reading = fo.read_footer(str(p), stats=stats)
    assert reading is not None
    assert reading.debits == Decimal("650.00")
    assert reading.credits == Decimal("750.00")
    assert reading.balance == Decimal("100.00")
    assert reading.raw["debits"] == "٦٥٠,٠٠"
    assert stats["cost"] == 0.001  # usage captured for cost evidence


def test_read_footer_all_null_is_none(tmp_path, monkeypatch):
    from PIL import Image
    from statement_qa import vlm_reader

    p = tmp_path / "pg.png"
    Image.new("RGB", (60, 400), "white").save(p)
    content = json.dumps({"debits": None, "credits": None, "balance": None})
    payload = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(payload))
    assert fo.read_footer(str(p)) is None
