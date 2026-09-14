"""Unit tests: VLM read retry behavior (no real network — urlopen monkeypatched).

Regression for the owner-hit failure: a transient RemoteDisconnected mid-run
killed the entire processing because the retry loop did not catch the
ConnectionError family.
"""

import http.client
import json
from decimal import Decimal
from unittest import mock  # noqa: F401  (kept for parity with pytest monkeypatch)

import pytest

from statement_qa import vlm_reader


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body


def _img(tmp_path):
    p = tmp_path / "pg.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    return str(p)


def test_remote_disconnected_is_retried_then_runtime_error(tmp_path, monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise http.client.RemoteDisconnected("Remote end closed connection without response")

    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen", boom)
    monkeypatch.setattr(vlm_reader.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        vlm_reader.read_rows_vlm(_img(tmp_path))
    assert calls["n"] == vlm_reader._ATTEMPTS


def test_success_after_one_blip(tmp_path, monkeypatch):
    calls = {"n": 0}
    content = json.dumps(
        [{"amount": "٣٠٠,٠٠", "balance": "٣٠٠,٠٠", "desc": "تحويل", "greg": None}],
        ensure_ascii=False)
    payload = json.dumps(
        {"choices": [{"message": {"content": content}}]}, ensure_ascii=False).encode()

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise http.client.RemoteDisconnected("blip")
        return _FakeResp(payload)

    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(vlm_reader.time, "sleep", lambda s: None)
    rows = vlm_reader.read_rows_vlm(_img(tmp_path))
    assert calls["n"] == 2
    assert rows[0]["movement"] == Decimal("300.00")
    assert rows[0]["balance"] == Decimal("300.00")


def test_malformed_json_retries_then_succeeds(tmp_path, monkeypatch):
    """Regression: a JSON glitch mid-run once killed a whole processing job."""
    calls = {"n": 0}
    good = json.dumps(
        [{"amount": None, "balance": ".,..", "desc": "x", "greg": None}],
        ensure_ascii=False)
    good_payload = json.dumps(
        {"choices": [{"message": {"content": good}}]}, ensure_ascii=False).encode()
    bad_payload = json.dumps(
        {"choices": [{"message": {"content": "prose without any json at all"}}]},
        ensure_ascii=False).encode()

    def flaky(*a, **k):
        calls["n"] += 1
        return _FakeResp(bad_payload if calls["n"] == 1 else good_payload)

    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(vlm_reader.time, "sleep", lambda s: None)
    rows = vlm_reader.read_rows_vlm(_img(tmp_path))
    assert calls["n"] == 2
    assert rows[0]["balance"] == Decimal("0.00")


def test_always_bad_json_raises_runtime_error(tmp_path, monkeypatch):
    calls = {"n": 0}

    def bad(*a, **k):
        calls["n"] += 1
        return _FakeResp(json.dumps(
            {"choices": [{"message": {"content": "no json"}}]}).encode())

    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen", bad)
    monkeypatch.setattr(vlm_reader.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        vlm_reader.read_rows_vlm(_img(tmp_path))
    assert calls["n"] == vlm_reader._ATTEMPTS


def test_trailing_comma_is_repaired(tmp_path, monkeypatch):
    content = '[{"amount": null, "balance": ".,..", "desc": "x",}]'
    payload = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(payload))
    monkeypatch.setattr(vlm_reader.time, "sleep", lambda s: None)
    rows = vlm_reader.read_rows_vlm(_img(tmp_path))
    assert rows[0]["balance"] == Decimal("0.00")


# ————— boundary auto-recovery (the p11 «extra zero» class) —————

def test_reread_boundary_accepts_only_chain_closing_candidate(tmp_path, monkeypatch):
    from PIL import Image

    p = tmp_path / "pg.png"
    Image.new("RGB", (60, 400), "white").save(p)
    content = json.dumps({"rows": [
        {"movement": "٥٠٠.٠٠", "balance": "١٢٦.٠٠"},   # self-inconsistent → rejected
        {"movement": "٥٠.٠٠", "balance": "١٢٦.٠٠"},    # |126-176| = 50 ✓
    ]}, ensure_ascii=False)
    payload = json.dumps({"choices": [{"message": {"content": content}}]},
                         ensure_ascii=False).encode()
    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(payload))
    got = vlm_reader.reread_boundary(str(p), Decimal("176.00"), page_no=11)
    assert got == Decimal("50.00")


def test_reread_boundary_rejects_when_nothing_closes(tmp_path, monkeypatch):
    from PIL import Image

    p = tmp_path / "pg.png"
    Image.new("RGB", (60, 400), "white").save(p)
    content = json.dumps({"rows": [{"movement": "٥٠٠.٠٠", "balance": "١٢٦.٠٠"}]},
                         ensure_ascii=False)
    payload = json.dumps({"choices": [{"message": {"content": content}}]},
                         ensure_ascii=False).encode()
    monkeypatch.setattr(vlm_reader.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResp(payload))
    assert vlm_reader.reread_boundary(str(p), Decimal("176.00")) is None


def test_recover_anchor_patches_only_on_verified_match(tmp_path, monkeypatch):
    raw = [{"movement": Decimal("500.00"), "balance": Decimal("126.00"),
            "desc": "سحب", "date": None}]
    monkeypatch.setattr(vlm_reader, "reread_boundary",
                        lambda *a, **k: Decimal("50.00"))
    patched, got = vlm_reader.recover_anchor(raw, Decimal("176.00"),
                                             str(tmp_path / "x.png"), 11)
    assert got == Decimal("50.00")
    assert patched[0]["movement"] == Decimal("50.00")
    rows = vlm_reader.chain_derive(patched, prev_balance=Decimal("176.00"))
    assert rows[0]["boundary"] == "txn" and rows[0]["side"] == "debit"

    # non-matching reread -> untouched, anchor stays
    monkeypatch.setattr(vlm_reader, "reread_boundary",
                        lambda *a, **k: Decimal("30.00"))
    kept, got2 = vlm_reader.recover_anchor(raw, Decimal("176.00"),
                                           str(tmp_path / "x.png"), 11)
    assert got2 is None and kept[0]["movement"] == Decimal("500.00")
