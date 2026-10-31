"""The plain-read comparison counts what it says it counts ($0: no network, no key).

tools/measure_plain_read.py compares a plain model answer with the ledger. Its counts become figures on the
public page, so the reading of a figure and the matching must hold on the shapes a model returns.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import measure_plain_read  # noqa: E402
from measure_plain_read import compare, flagged_rows, number, rows_of  # noqa: E402


def test_a_figure_is_read_in_every_shape_a_page_or_a_model_gives():
    assert number("١٤,٣٦٥.٧٧") == Decimal("14365.77")
    assert number("١٤٬٣٦٥٫٧٧") == Decimal("14365.77")
    assert number("14,365.77 SAR") == Decimal("14365.77")
    assert number(883.29) == Decimal("883.29")
    assert number("-733.43") == Decimal("-733.43")
    assert number(None) is None and number("") is None and number(True) is None


def test_the_array_is_found_inside_fences_and_prose():
    answer = 'Here it is:\n```json\n[{"amount": "1.00", "balance": "2.00"}]\n```'
    assert rows_of(answer) == [{"amount": "1.00", "balance": "2.00"}]
    assert rows_of("no table on this page") == []
    assert rows_of("[not json]") == []


def _row(seq, movement, balance, derived=None, ok=True):
    return {"seq": seq, "page": 1, "movement": movement, "balance": balance,
            "derived_movement": derived or movement, "chain_ok": ok}


def test_matches_and_breaks_are_counted_per_figure():
    opening = {**_row(1, None, "100.00"), "opening": True}
    expected = [opening, _row(2, "10.00", "90.00"), _row(3, "5.00", "95.00")]
    returned = [{"amount": "10.00", "balance": "90.00"},
                {"amount": "5.00", "balance": "96.00"}]          # one balance misread
    counts = compare(expected, returned)
    assert counts["balances_matched"] == 1 and counts["balances_expected"] == 2   # the opening row is not asked for
    assert counts["amounts_matched"] == 2 and counts["amounts_expected"] == 2
    assert counts["breaks_inside_the_answer"] == 1                                  # 96 - 90 is not 5
    assert counts["rows_with_other_fields"] == 0
    consistent = compare(expected, [{"amount": "10.00", "balance": "90.00"}, {"amount": "6.00", "balance": "96.00"}])
    assert consistent["breaks_inside_the_answer"] == 0 and consistent["balances_matched"] == 1   # wrong, and silent
    assert compare(expected, returned + [{"amount": "1.00", "balance": "2.00", "note": "?"}])["rows_with_other_fields"] == 1


def test_a_flagged_row_says_which_figure_the_plain_answer_carried():
    expected = [_row(7, "4501.20", "9000.00", derived="4510.20", ok=False)]
    same_as_system = flagged_rows(expected, [{"amount": "٤,٥٠١.٢٠", "balance": "9000.00"}])
    assert same_as_system == [{"seq": 7, "page": 1, "answer_has_systems_reading": True,
                               "answer_has_balance_difference": False}]
    fixed = flagged_rows(expected, [{"amount": 4510.2, "balance": "9000.00"}])
    assert fixed[0]["answer_has_balance_difference"] is True


def test_an_amount_is_scored_only_where_the_break_says_which_figure_is_wrong():
    """Between two rows the chain holds, the balance difference is the amount; at any other break a balance may be
    the misread figure, so that row is left out rather than scored against a guess."""
    between = [_row(6, "10.00", "100.00"), _row(7, "4501.20", "9000.00", derived="4510.20", ok=False),
               _row(8, "5.00", "8995.00")]
    assert compare(between, [{"amount": "4510.20", "balance": "9000.00"}])["amounts_matched"] == 1
    assert compare(between, [{"amount": "4501.20", "balance": "9000.00"}])["amounts_matched"] == 0
    at_the_edge = between[1:]
    counts = compare(at_the_edge, [{"amount": "4501.20", "balance": "9000.00"}, {"amount": "5.00", "balance": "8995.00"}])
    assert counts["amounts_unknown"] == 1 and counts["amounts_expected"] == 1 and counts["amounts_matched"] == 1


def test_with_rows_out_the_public_record_holds_counts_only(tmp_path, monkeypatch):
    """A real page's returned figures go to the owner's machine; the tracked record carries counts."""
    import statement_qa.api_key as api_key
    import statement_qa.vlm_reader as vlm_reader

    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"source": "s.pdf", "source_sha256": "0" * 64, "n_pages": 9,
                                  "rows": [_row(1, "10.00", "90.00"), {**_row(2, "5.00", "95.00"), "page": 2}]}))
    monkeypatch.setattr(api_key, "get_api_key", lambda *_: "not-a-key")
    monkeypatch.setattr(measure_plain_read, "_page_b64", lambda *_: "")

    def answer(_image, _prompt, max_tokens, stats, api_key):
        stats["cost"] = 0.01
        return '[{"amount": "10.00", "balance": "90.00"}]'

    monkeypatch.setattr(vlm_reader, "chat_vlm_image", answer)
    out, rows = tmp_path / "out.json", tmp_path / "rows.json"
    assert measure_plain_read.main(["--ledger", str(ledger), "--pages", "1", "--runs", "2", "--budget", "0.05",
                                    "--out", str(out), "--rows-out", str(rows)]) == 0
    record = json.loads(out.read_text())["runs"]
    assert len(record) == 2 and all(r["pages_read"] == [1] for r in record)
    assert not any("returned_rows" in p for r in record for p in r["pages"]), "a returned figure in the public record"
    assert [k["run"] for k in json.loads(rows.read_text())] == [1, 2] == [r["run"] for r in record]
    assert sum(r["spent"] for r in record) <= 0.05
    # A later invocation appends under the next run numbers: earlier rows are never lost.
    assert measure_plain_read.main(["--ledger", str(ledger), "--pages", "1", "--budget", "0.05",
                                    "--out", str(out), "--rows-out", str(rows)]) == 0
    assert [k["run"] for k in json.loads(rows.read_text())] == [1, 2, 3] == [r["run"] for r in json.loads(out.read_text())["runs"]]
    # A page with no expected rows is refused before any call is paid for.
    calls = []
    monkeypatch.setattr(vlm_reader, "chat_vlm_image", lambda *a, **k: calls.append(1) or "[]")
    assert measure_plain_read.main(["--ledger", str(ledger), "--pages", "1", "5", "--budget", "0.05",
                                    "--out", str(out)]) == 2 and calls == []
