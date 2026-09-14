"""Tests for the what-if deltas: era detector · ordering · job lock · bank
guard · last-balance retrieval bridge. No network."""

from decimal import Decimal

import pytest

from statement_qa.bank_check import verdict_from_name
from statement_qa.era import fingerprint_pages, page_fingerprint, token_style
from statement_qa.job_lock import JobBusyError, job_lock
from statement_qa.ordering import check_order, parse_gregorian
from statement_qa.chunking import Chunk


# ————— era detector —————

def test_token_style_classifies_both_eras():
    assert token_style("٣٠٠,٠٠") == "old"        # comma decimal (old print)
    assert token_style("9001.00") == "new"      # dot halalas + thousands
    assert token_style("9001.00") == "lost_dot"  # lost decimal dot
    assert token_style(".,..") == "zero_style"   # printed zero
    assert token_style("٣٠٠") == "plain"
    assert token_style(None) is None


def test_page_fingerprint_majority_and_mixed():
    old = page_fingerprint(["٣٠٠,٠٠", "١٠٠,٠٠", "٢٠٠,٠٠", ".,.."])
    assert old["style"] == "old" and old["counts"]["zero_style"] == 1
    new = page_fingerprint(["9001.00", "١٠٠.٠٠", "٢٠٠.٠٠"])
    assert new["style"] == "new"
    mixed = page_fingerprint(["٣٠٠,٠٠", "١٠٠.٠٠"])  # 1-1, no 3:1 margin
    assert mixed["style"] == "mixed"


def test_fingerprint_pages_transition_and_outlier():
    pages = {1: ["٣٠٠,٠٠", "١٠٠,٠٠"],
             2: ["١٠٠.٠٠", "٢٠٠.٠٠"],
             3: ["١٠٠.٠٠", "٢٠٠.٠٠"],
             4: ["٣٠٠,٠٠", "١٠٠,٠٠"],  # differs from BOTH neighbours (new)
             5: ["١٠٠.٠٠", "٢٠٠.٠٠"]}
    fp = fingerprint_pages(pages)
    assert fp["styles"][1] == "old" and fp["styles"][2] == "new"
    assert fp["styles"][4] == "old"
    assert (1, 2, "old", "new") in fp["transitions"]
    assert 4 in fp["outliers"]  # isolated old page between new pages


# ————— ordering —————

def test_parse_gregorian_picks_gregorian_of_two_calendars():
    assert parse_gregorian("١٤٣٤١٢٢٦ ۲۰۱۳۱۰۳۱") == "20131031"
    assert parse_gregorian("۲۰۱۳۱۱۰۷") == "20131107"
    assert parse_gregorian("١٤٣٤١٢٢٦") is None      # hijri-only -> None
    assert parse_gregorian(None) is None


def test_check_order_flags_reversed_pages():
    ok = check_order({1: ["20131031", "20131107"],
                      2: ["20131108", "20131121"]})
    assert ok["cross"] == [] and ok["intra"] == {}
    assert ok["coverage"] == (4, 4)
    bad = check_order({1: ["20131121", "20131128"],
                       2: ["20131031", "20131107"]})  # page 2 goes BACK
    assert len(bad["cross"]) == 1
    assert bad["cross"][0][0] == 1 and bad["cross"][0][1] == 2


def test_check_order_counts_intra_inversions():
    res = check_order({1: ["20131121", "20131107"]})
    assert res["intra"] == {1: 1}


# ————— job lock —————

def test_job_lock_busy_then_release(tmp_path):
    lock = tmp_path / "job.lock"
    with job_lock(lock):
        with pytest.raises(JobBusyError):
            with job_lock(lock):
                pass
    # released — a fresh acquisition must now succeed
    with job_lock(lock):
        pass


# ————— bank guard —————

def test_verdict_from_name():
    assert verdict_from_name("مصرف الراجحي") == "rajhi"
    assert verdict_from_name("Al Rajhi Bank") == "rajhi"
    assert verdict_from_name("AL RAJH") == "rajhi"
    assert verdict_from_name("مصرف الرياض") == "other"
    assert verdict_from_name("البنك الأهلي السعودي") == "other"
    assert verdict_from_name(None) == "unknown"
    assert verdict_from_name("") == "unknown"
    assert verdict_from_name("null") == "unknown"


# ————— last-balance bridge —————

def _chunks():
    return [
        Chunk(page=1, start_row=1, end_row=12, text="[صفحة 1]",
              meta={"page": 1}),
        Chunk(page=10, start_row=95, end_row=104, text="[صفحة 10]",
              meta={"page": 10}),
    ]


def test_boost_last_page_for_closing_questions():
    from statement_qa.qa import boost_last_page

    hits = [{"chunk_id": "p001-r01-12", "page": 1, "row_start": 1,
             "row_end": 12, "text": "[صفحة 1]", "score": 0.1}]
    boosted = boost_last_page(hits, _chunks(), "كم آخر رصيد في الكشف؟")
    assert [h["page"] for h in boosted] == [1, 10]
    assert boosted[-1]["chunk_id"] == "p010-r95-104"

    # non-closing question -> untouched
    assert boost_last_page(hits, _chunks(), "كم مجموع السحوبات؟") == hits

    # already present -> untouched
    both = boosted
    assert boost_last_page(both, _chunks(), "ما آخر رصيد؟") == both
