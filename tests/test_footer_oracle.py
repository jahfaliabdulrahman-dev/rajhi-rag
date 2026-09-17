"""Footer oracle tests — the accuracy-paradox guard (no network)."""

import json
from decimal import Decimal

from statement_qa import footer_oracle as fo
from statement_qa.footer_oracle import (FooterReading, check_page_footer,
                                       delta_status, page_totals)


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
    # The signature on the FIRST page (prior = 0) — the only case the old
    # code could ever see (see the two tests below).
    f = FooterReading(debits=Decimal("2"), credits=Decimal("3"),
                      balance=Decimal("1"))
    res = check_page_footer(_chain_rows(), f)
    assert res["status"] == "mismatch"
    assert res["is_paradox"] is True
    assert len(res["diffs"]) == 3


def _x100_page_rows():
    """A page whose own sums were misread ×100 (the real signature's shape)."""
    return [
        {"kind": "txn", "opening": False, "balance": Decimal("100"),
         "side": "debit", "derived_movement": Decimal("20000")},
        {"kind": "txn", "opening": False, "balance": Decimal("100"),
         "side": "credit", "derived_movement": Decimal("30000")},
    ]


def test_x100_paradox_is_visible_after_the_first_page():
    """AUDIT P1-1: with a non-zero prior the flag could never fire.

    The comparison was `prior + own` versus `footer`, and adding a prior breaks
    the ×100 ratio arithmetically — so on 628 of 629 pages the one signature
    that must never pass silently was unreachable, while BOTH consumers (the
    paid-run stop gate and the ticker) consulted it.
    """
    prior = {"debits": Decimal("650"), "credits": Decimal("750")}
    f = FooterReading(debits=Decimal("850"), credits=Decimal("1050"),
                      balance=Decimal("100"))   # = prior + 200 / prior + 300
    res = check_page_footer(_x100_page_rows(), f, prior=prior)
    assert res["status"] == "mismatch"
    assert res["is_paradox"] is True
    assert {d["field"] for d in res["diffs"]} == {"debits", "credits"}
    assert [d["own"] for d in res["diffs"]] == ["20000", "30000"]
    assert [d["expected"] for d in res["diffs"]] == ["200", "300"]


def test_delta_basis_carries_the_paradox_flag():
    """The delta basis is where the report lives now — so it must carry it."""
    prev = FooterReading(debits=Decimal("650"), credits=Decimal("750"),
                         balance=Decimal("50"))
    f = FooterReading(debits=Decimal("850"), credits=Decimal("1050"),
                      balance=Decimal("100"))
    res = delta_status(_x100_page_rows(), prev, f)
    assert res["status"] == "mismatch" and res["basis"] == "delta"
    assert res["is_paradox"] is True
    assert all(d["is_paradox"] for d in res["diffs"] if not d["ok"])


def test_a_x10_drift_is_not_dressed_up_as_the_x100_signature():
    """The other internally-consistent misread class must stay distinguishable."""
    prev = FooterReading(debits=Decimal("650"), credits=Decimal("750"),
                         balance=Decimal("50"))
    f = FooterReading(debits=Decimal("850"), credits=Decimal("1050"),
                      balance=Decimal("100"))
    rows = [
        {"kind": "txn", "opening": False, "balance": Decimal("100"),
         "side": "debit", "derived_movement": Decimal("2000")},
        {"kind": "txn", "opening": False, "balance": Decimal("100"),
         "side": "credit", "derived_movement": Decimal("3000")},
    ]
    res = delta_status(rows, prev, f)
    assert res["status"] == "mismatch" and res["is_paradox"] is False


def test_the_paradox_key_always_exists():
    """Consumers call .get('is_paradox'): None silently reads as False, so the
    key must be present in every status, not just in mismatch."""
    for res in (
            check_page_footer(_chain_rows(), None),
            check_page_footer(_chain_rows(), FooterReading(), skip=True),
            check_page_footer(_chain_rows(), FooterReading()),
            check_page_footer(_chain_rows(), FooterReading(
                debits=Decimal("200"), credits=Decimal("300"),
                balance=Decimal("100"))),
            delta_status(_chain_rows(), None, None)):
        assert "is_paradox" in res and res["is_paradox"] is False


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


def test_empty_provider_content_is_a_named_retryable_error(monkeypatch):
    """A provider can return empty content; that must not surface as a TypeError
    from deep inside the parser (measured: 2 of 10 pages in a calibration)."""
    import pytest

    from statement_qa import vlm_reader

    body = json.dumps({"choices": [{"message": {"content": None}}]}).encode()
    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(body))
    monkeypatch.setattr(vlm_reader.time, "sleep", lambda *_: None)
    with pytest.raises(RuntimeError, match="empty content|retries exhausted"):
        vlm_reader.chat_vlm_image("Zm9v", "prompt")


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


# ————— page-level arbitration (footer-delta reread acceptance) —————

def _two_rows():
    return [
        {"kind": "txn", "opening": False, "balance": Decimal("100"),
         "side": "credit", "derived_movement": Decimal("100")},
        {"kind": "txn", "opening": False, "balance": Decimal("50"),
         "side": "debit", "derived_movement": Decimal("50")},
    ]


def test_delta_ok_isolates_the_page():
    prev_footer = FooterReading(debits=Decimal("650"), credits=Decimal("750"),
                                balance=Decimal("100"))
    good = FooterReading(debits=Decimal("700"), credits=Decimal("850"),
                         balance=Decimal("50"))
    ok, compared = fo.delta_ok(_two_rows(), prev_footer, good)
    assert ok and compared == 3
    bad = FooterReading(debits=Decimal("701"), credits=Decimal("850"),
                        balance=Decimal("50"))
    ok2, _ = fo.delta_ok(_two_rows(), prev_footer, bad)
    assert not ok2


def test_page_diverged_delta_and_fallback():
    zero = {"debits": Decimal("0"), "credits": Decimal("0")}
    prev_footer = FooterReading(debits=Decimal("650"), credits=Decimal("750"),
                                balance=Decimal("100"))
    banner = FooterReading(debits=Decimal("700"), credits=Decimal("850"),
                           balance=Decimal("50"))
    assert fo.page_diverged(_two_rows(), zero, prev_footer, banner) is False
    off = FooterReading(debits=Decimal("699"), credits=Decimal("850"),
                        balance=Decimal("50"))
    assert fo.page_diverged(_two_rows(), zero, prev_footer, off) is True
    # fallback (no prev footer): cumulative against a clean prior
    cum_ok = FooterReading(debits=Decimal("50"), credits=Decimal("100"),
                           balance=Decimal("50"))
    assert fo.page_diverged(_two_rows(), zero, None, cum_ok) is False
    cum_off = FooterReading(debits=Decimal("51"), credits=Decimal("100"),
                            balance=Decimal("50"))
    assert fo.page_diverged(_two_rows(), zero, None, cum_off) is True


def test_try_page_reread_accepts_only_clean_and_reconciled(monkeypatch):
    clean = [
        {"movement": Decimal("100.00"), "balance": Decimal("100.00"),
         "desc": "ايداع", "date": None,
         "raw_movement": "١٠٠.٠٠", "raw_balance": "١٠٠.٠٠"},
        {"movement": Decimal("50.00"), "balance": Decimal("50.00"),
         "desc": "سحب", "date": None,
         "raw_movement": "٥٠.٠٠", "raw_balance": "٥٠.٠٠"},
    ]
    monkeypatch.setattr(fo, "read_rows_vlm", lambda *a, **k: clean)
    prev_footer = FooterReading(debits=Decimal("650"), credits=Decimal("750"),
                                balance=Decimal("100"))
    banner = FooterReading(debits=Decimal("700"), credits=Decimal("850"),
                           balance=Decimal("50"))
    raw, accepted, note = fo.try_page_reread(
        "x.png", {"debits": Decimal("0"), "credits": Decimal("0")},
        prev_footer, banner, Decimal("0"))
    assert accepted and raw is clean and "دلتا" in note

    broken = [
        {"movement": Decimal("100"), "balance": Decimal("100"),
         "desc": "a", "date": None, "raw_movement": "١٠٠", "raw_balance": "١٠٠"},
        {"movement": Decimal("77"), "balance": Decimal("50"),
         "desc": "b", "date": None, "raw_movement": "٧٧", "raw_balance": "٥٠"},
    ]
    monkeypatch.setattr(fo, "read_rows_vlm", lambda *a, **k: broken)
    raw2, accepted2, note2 = fo.try_page_reread(
        "x.png", {"debits": Decimal("0"), "credits": Decimal("0")},
        prev_footer, banner, Decimal("0"))
    assert not accepted2 and raw2 is None and "شكوك" in note2


def test_try_page_reread_never_raises_on_provider_error(monkeypatch):
    """A repair attempt must reject, not crash: 402/429/timeout are expected."""
    def boom(*a, **k):
        raise RuntimeError("VLM HTTP 402")
    monkeypatch.setattr(fo, "read_rows_vlm", boom)
    raw, accepted, note = fo.try_page_reread(
        "x.png", {"debits": Decimal("0"), "credits": Decimal("0")},
        None, None, Decimal("0"))
    assert raw is None and accepted is False and "فشل" in note


def test_delta_status_works_after_a_broken_cumulative_chain():
    """After a lost page the cumulative check is dead but the DELTA is not."""
    rows = _two_rows()  # own: debits 50, credits 100, closing 50
    prev_footer = FooterReading(debits=Decimal("650"), credits=Decimal("750"),
                                balance=Decimal("100"))
    good = FooterReading(debits=Decimal("700"), credits=Decimal("850"),
                         balance=Decimal("50"))
    st = fo.delta_status(rows, prev_footer, good)
    assert st["status"] == "ok" and all(d["ok"] for d in st["diffs"])
    off = FooterReading(debits=Decimal("701"), credits=Decimal("850"),
                        balance=Decimal("50"))
    st2 = fo.delta_status(rows, prev_footer, off)
    assert st2["status"] == "mismatch" and not st2["diffs"][0]["ok"]
    assert fo.delta_status(rows, None, good)["status"] == "unchecked"
