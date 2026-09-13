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
