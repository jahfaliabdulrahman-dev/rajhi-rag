"""Gate-1 regressions: honest disclosure and re-derivable evidence.

Every test here locks a statement the project makes to a reader, or the chain
that lets that statement be checked. They were written after an external audit
showed the maths was sound while the DECLARATION was not (audit P1-2, P1-3,
P2-1, P2-2, P2-4, P2-9, P3-1, P3-2, P3-3, S2).
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import scale_slice as ss                                    # noqa: E402
from statement_qa import qa_tools                           # noqa: E402
from statement_qa.legacy.arabic_digit_parser import norm_num  # noqa: E402
from statement_qa.ordering import summarize_page_numbers     # noqa: E402
from statement_qa import qa as qa_mod                        # noqa: E402
import arbitrate_footer as af                                # noqa: E402
import verify_provenance as vp                               # noqa: E402


# ── P1-3: a green check must be something the evidence can carry ──────────

def test_page_number_summary_refuses_a_verdict_on_thin_coverage():
    thin = {"checked": 17, "unread": 612, "gaps": [], "duplicates": {},
            "backwards": [], "position_breaks": []}
    out = summarize_page_numbers(thin)
    assert "لا حكم" in out and "✓" not in out


def test_page_number_summary_names_a_real_gap():
    pn = {"checked": 40, "unread": 0, "gaps": [(426, 425, 427, 428, [426, 427])],
          "duplicates": {}, "backwards": [], "position_breaks": []}
    out = summarize_page_numbers(pn)
    assert "ينقص قبلها" in out and "426" in out


def test_page_number_summary_is_quiet_only_when_it_deserves_it():
    full = {"checked": 100, "unread": 0, "gaps": [], "duplicates": {},
            "backwards": [], "position_breaks": []}
    assert "✓ متسلسل" in summarize_page_numbers(full)
    partial = {"checked": 60, "unread": 40, "gaps": [], "duplicates": {},
               "backwards": [], "position_breaks": [(5, 9)]}
    out = summarize_page_numbers(partial)
    assert "غير محسوم" in out and "✓" not in out


# ── P2-1/P2-2: the ledger holds cost, and the report survives a replay ────

def test_ledger_sums_only_usage_shaped_keys():
    """A stray `page_no` used to land in the cost ledger as if it were money."""
    out = ss._sum_dicts({"cost": 1.0, "calls": 1},
                        {"cost": 0.5, "calls": 1, "page_no": 3422,
                         "request_calls": 2})
    assert out == {"cost": 1.5, "calls": 2, "request_calls": 2}


def test_cache_facts_read_durable_state_not_session_state(tmp_path):
    (tmp_path / "pg-001.json").write_text(json.dumps({
        "pg": 1, "ms_read": 20_000, "ms_footer": 2_000,
        "recovered": "50.00", "reread": "قُبلت",
        "arbitrated_by": [{"field": "credits", "by": "المالك", "why": "أثر"}]}),
        encoding="utf-8")
    (tmp_path / "pg-002.json").write_text(json.dumps({
        "pg": 2, "ms_read": 18_000, "ms_footer": 1_000}), encoding="utf-8")
    facts = ss._cache_facts(tmp_path)
    assert facts["recoveries"] == [{"page": 1, "amount": "50.00"}]
    assert facts["rereads"] == [{"page": 1}]
    assert facts["arbitrations"][0]["field"] == "credits"
    assert facts["median_page_s"] == Decimal("22.0") or \
        abs(facts["median_page_s"] - 22.0) < 0.01
    assert facts["timed_pages"] == 2


def test_damaged_checkpoint_is_unreadable_not_fatal(tmp_path):
    broken = tmp_path / "pg-003.json"
    broken.write_text('{"pg": 3, "raw_rows": [', encoding="utf-8")
    assert ss._read_cache(broken) is None          # never raises
    assert ss._read_cache(tmp_path / "missing.json") is None


def test_partial_run_first_page_is_not_a_false_mismatch():
    """Every investigation window used to open with a fake «mismatch»."""
    assert ss.partial_first_status(424, 424)["status"] == "unchecked"
    assert ss.partial_first_status(425, 424) is None
    assert ss.partial_first_status(1, 1) is None


def test_cache_write_is_atomic(tmp_path):
    target = tmp_path / "pg-004.json"
    ss._write_json_atomic(target, {"pg": 4, "ok": True})
    assert json.loads(target.read_text(encoding="utf-8"))["pg"] == 4
    assert not list(tmp_path.glob("*.tmp"))        # no half-written leftovers


# ── S2: arbitration is recorded, never silent ────────────────────────────

def _page_with_mismatch(tmp_path: Path) -> Path:
    (tmp_path / "pg-491.json").write_text(json.dumps({
        "pg": 491,
        "footer": {"debits": "9001.00", "credits": "9001.00",
                   "balance": "7.84",
                   "raw": {"debits": "9001.00",
                           "credits": "9001.00",
                           "balance": "٧.٨٤"}}}), encoding="utf-8")
    return tmp_path


def test_unmarked_mismatch_is_a_violation(tmp_path):
    res = vp.audit(_page_with_mismatch(tmp_path))
    assert len(res["unmarked"]) == 1 and res["unmarked"][0][1] == "credits"


def test_arbitration_marks_the_value_and_keeps_the_original(tmp_path):
    res_dir = _page_with_mismatch(tmp_path)
    af.arbitrate(res_dir, 491, "credits", "9001.00",
                 "خطأ قراءة في رقم واحد", "المالك", "suspects_log")
    after = vp.audit(res_dir)
    assert after["unmarked"] == [] and len(after["arbitrated"]) == 1
    data = json.loads((res_dir / "pg-491.json").read_text(encoding="utf-8"))
    f = data["footer"]
    assert f["credits"] == "9001.00"                    # the decided value
    assert f["raw"]["credits"] == "9001.00"            # evidence untouched
    assert f["raw_original"]["credits"] == "9001.00"
    rec = data["arbitrated_by"][0]
    for key in ("by", "why", "at", "field", "old_value", "new_value"):
        assert key in rec
    assert rec["raw_parsed"] == "9001.00"


def test_arbitration_requires_a_written_reason(tmp_path):
    res_dir = _page_with_mismatch(tmp_path)
    try:
        af.arbitrate(res_dir, 491, "credits", "9001.00", "   ", "المالك")
    except ValueError as exc:
        assert "سبب" in str(exc)
    else:                                                  # pragma: no cover
        raise AssertionError("arbitration without a reason was accepted")


def test_nothing_to_record_when_evidence_agrees(tmp_path):
    (tmp_path / "pg-001.json").write_text(json.dumps({
        "pg": 1, "footer": {"debits": "1.00", "credits": None, "balance": None,
                            "raw": {"debits": "١.٠٠"}}}), encoding="utf-8")
    try:
        af.arbitrate(tmp_path, 1, "debits", "1.00", "لا شيء", "المالك")
    except SystemExit:
        pass
    else:                                                  # pragma: no cover
        raise AssertionError("recorded an arbitration with nothing to record")


# ── P3-1 / P3-2 / P3-3 / P2-9 ────────────────────────────────────────────

def test_a_lone_dot_is_not_a_printed_zero():
    assert norm_num(".") is None and norm_num(",") is None
    assert norm_num(".,.") == 0.0 and norm_num("  .,..  ") == 0.0


def test_unknown_side_filter_is_refused_loudly():
    assert qa_tools._side_match("debit", "مدين")
    try:
        qa_tools._side_match("debit", "سحوبات")
    except ValueError as exc:
        assert "غير معروف" in str(exc)
    else:                                                  # pragma: no cover
        raise AssertionError("an unknown filter silently matched everything")


def test_closing_question_matches_without_a_hamza():
    """«اخر رصيد» is how the commonest phrasing is actually typed."""
    for q in ("اخر رصيد", "آخر رصيد", "الرصيد الختامي", "الرصيد المتبقي",
              "كم تبقى في الحساب", "closing balance"):
        assert qa_mod._CLOSING_RE.search(qa_mod._normalize_ar(q)), q
    assert not qa_mod._CLOSING_RE.search(qa_mod._normalize_ar("كم عدد السحوبات؟"))
