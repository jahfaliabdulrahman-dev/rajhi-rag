"""Tests for the what-if deltas: era detector · ordering · job lock · bank
guard · last-balance retrieval bridge. No network."""

import pytest

from statement_qa.bank_check import verdict_from_name
from statement_qa.era import fingerprint_pages, page_fingerprint, token_style
from statement_qa.job_lock import JobBusyError, job_lock
from statement_qa.contract_rows import normalize_date
from statement_qa.ordering import check_order
from statement_qa.chunking import Chunk


# ————— era detector —————

def test_token_style_classifies_both_eras():
    assert token_style("٣٠٠,٠٠") == "old"        # comma decimal (old print)
    assert token_style("٩,٠٠٦.٠٠") == "new"      # dot halalas + thousands
    assert token_style("٦١,١٦٥١٢") == "lost_dot"  # lost decimal dot
    assert token_style(".,..") == "zero_style"   # printed zero
    assert token_style("٣٠٠") == "plain"
    assert token_style(None) is None


def test_page_fingerprint_majority_and_mixed():
    old = page_fingerprint(["٣٠٠,٠٠", "١٠٠,٠٠", "٢٠٠,٠٠", ".,.."])
    assert old["style"] == "old" and old["counts"]["zero_style"] == 1
    new = page_fingerprint(["٩,٠٠٦.٠٠", "١٠٠.٠٠", "٢٠٠.٠٠"])
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

def test_the_date_reader_picks_gregorian_of_two_calendars():
    """The rule `ordering.parse_gregorian` held, now held by the one date reader."""
    assert normalize_date("١٤٣٤١٢٢٦ ۲۰۱۳۱۰۳۱")[:2] == ("2013-10-31", "ok")
    assert normalize_date("۲۰۱۳۱۱۰۷")[:2] == ("2013-11-07", "ok")
    assert normalize_date("١٤٣٤١٢٢٦")[0] == ""      # hijri-only -> no date
    assert normalize_date(None)[0] == ""


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


def test_pages_for_names_the_last_page_of_a_closing_question():
    """**`boost_last_page` طُويت في `pages_for` (R105-4):** الصفحةُ الأخيرةُ لسؤال الرصيد الختاميّ
    صارت **رقمًا يُمرَّر إلى مرشِّح الفهرس** بدل إلحاقٍ يدويّ بعد النتائج — ونفسُ الحكم: سؤالُ
    الرصيد يُطلِب أخيرَ صفحة، وغيره لا يُطلِب شيئًا، والمسمّاةُ في السؤال تسبق الكلّ."""
    from statement_qa.qa import pages_for

    assert pages_for("كم آخر رصيد في الكشف؟", _chunks()) == [10]
    assert pages_for("كم مجموع السحوبات؟", _chunks()) == []
    assert pages_for("ما آخر رصيد؟", None) == []              # بلا قطعٍ لا يُخمَّن رقم
    # والمسمّاةُ في السؤال نفسِها تُقرأ ولو كان السؤال عن الرصيد (السؤالُ أسبقُ من الحالتين)
    assert pages_for("ما رصيد نهاية الصفحة ٣؟", _chunks()) == [3]
    assert pages_for("قارن الصفحتين ٢ و٣.", _chunks()) == [2, 3]


def test_check_page_numbers_detects_a_gap():
    """Printed page numbers vs scan positions: a jump = missing sheets."""
    from statement_qa.ordering import check_page_numbers, summarize_page_numbers
    pn = check_page_numbers([(1, 1), (2, 2), (3, 3), (4, 6), (5, 7)])
    assert pn["gaps"] == [(3, 3, 4, 6, [4, 5])]
    assert pn["duplicates"] == {} and pn["backwards"] == []
    assert pn["checked"] == 5 and pn["unread"] == 0
    seg = summarize_page_numbers(pn)
    assert "ينقص" in seg and "4" in seg and "5" in seg


def test_check_page_numbers_flags_duplicates_backwards_and_unread():
    from statement_qa.ordering import check_page_numbers
    pn = check_page_numbers([(1, 5), (2, 5), (3, 4), (4, None)])
    assert pn["duplicates"].get(5) == [1, 2]
    assert pn["backwards"] and pn["backwards"][0] == (2, 5, 3, 4)
    assert pn["unread"] == 1 and pn["checked"] == 3
