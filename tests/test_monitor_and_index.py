"""Gate-3 regressions: the monitor that must speak, and the index that must answer.

P3-8: the periodic monitor wrote a log line every ten minutes and told nobody,
so «the service died» and «the monitor died» looked exactly alike. P3-9… the
parquet index exists so a question about the corpus is a filter, not a new
script — and so the documented `raw_rows`-without-`side` trap stops being
re-risked by every fresh script.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mon = _load("health_monitor")
hc = _load("health_check")


# ── P3-8: speak on change, stay quiet otherwise ──────────────────────────

def test_transition_speaks_only_when_the_state_changes():
    assert mon.transition("OK", "OK") == ""
    assert mon.transition("DOWN", "DOWN") == ""
    assert mon.transition("OK", "DOWN") == "down"
    assert mon.transition("DOWN", "OK") == "up"


def test_the_first_line_ever_is_not_a_change():
    """Nothing to compare against: a notification on boot would be noise."""
    assert mon.transition(None, "DOWN") == ""
    assert mon.transition(None, "OK") == ""


def test_last_state_reads_the_previous_run():
    text = ("2026-09-17 10:00:00 OK app=up redirect=up\n"
            "2026-09-17 10:10:00 DOWN app=down redirect=down\n")
    assert mon.last_state(text) == "DOWN"
    assert mon.last_state("") is None
    assert mon.last_state("garbage line\n") is None


def test_monitor_heartbeat_detects_a_dead_monitor():
    import datetime as dt

    now = dt.datetime(2026, 9, 17, 12, 0, 0)
    fresh = "2026-09-17 11:55:00 OK app=up redirect=up\n"
    stale = "2026-09-17 10:00:00 OK app=up redirect=up\n"
    assert hc.monitor_age_minutes(fresh, now) == 5
    assert hc.monitor_age_minutes(stale, now) == 120
    assert hc.monitor_age_minutes("", now) is None
    assert hc.monitor_age_minutes("no timestamp here", now) is None


# ── the parquet index ───────────────────────────────────────────────────

def _fixture(tmp_path: Path) -> Path:
    res = tmp_path / "results"
    res.mkdir()
    (res / "pg-001.json").write_text(json.dumps({
        "pg": 1, "ms_read": 20000, "recovered": "50.00",
        "raw_rows": [{"movement": None, "balance": "0.00", "desc": "الرصيد الافتتاحى"},
                     {"movement": "300.00", "balance": "300.00", "desc": "تحويل"}],
        "footer": {"debits": "0.00", "credits": "300.00", "balance": "300.00",
                   "raw": {"debits": ".,..", "credits": "٣٠٠,٠٠",
                           "balance": "٣٠٠,٠٠"}}}),
        encoding="utf-8")
    (res / "pg-002.json").write_text(json.dumps({
        "pg": 2, "reread": "قُبلت",
        "raw_rows": [{"movement": "50.00", "balance": "250.00", "desc": "شراء"}],
        "footer": {"debits": "50.00", "credits": "300.00", "balance": "250.00",
                   "raw": {}, "raw_original": {"credits": "٣٠٠,٠٠"}},
        "arbitrated_by": [{"field": "credits", "by": "المالك", "why": "أثر"}]}),
        encoding="utf-8")
    return res


def test_index_answers_a_question_in_one_filter(tmp_path):
    import polars as pl

    from to_parquet import build

    res = _fixture(tmp_path)
    target = build(res, tmp_path / "index.parquet")
    df = pl.read_parquet(target)
    assert df.height == 3
    assert set(["page", "row_no", "movement_raw", "footer_balance",
                "page_recovered", "page_reread", "footer_arbitrated"]) <= set(
                    df.columns)
    repaired = df.filter(pl.col("page_recovered") | pl.col("page_reread"))
    assert sorted(repaired["page"].unique().to_list()) == [1, 2]
    assert df.filter(pl.col("footer_arbitrated"))["page"].unique().to_list() == [2]


def test_calibration_window_bounds_what_is_paid_for():
    """`--first`/`--count` were declared and ignored: calibrating «10 pages»
    against the full file would have cost ~$8 instead of ~$0.15."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "calibrate_reader", ROOT / "tools" / "calibrate_reader.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pages = list(range(629))
    assert mod.select_pages(pages, 1, 10) == list(range(10))
    assert mod.select_pages(pages, 5, 3) == [4, 5, 6]
    assert mod.select_pages(pages, 628, 10) == [627, 628]
    assert mod.select_pages(pages, 1, 0) == []
    assert mod.select_pages(pages, 700, 3) == []


def test_index_deliberately_omits_chain_derived_columns(tmp_path):
    """`side`/`ok` come from the arbiter. Re-deriving them here is the trap that
    once produced two wrong conclusions — the index must not invite it."""
    import polars as pl

    from to_parquet import build

    df = pl.read_parquet(build(_fixture(tmp_path), tmp_path / "i.parquet"))
    assert "side" not in df.columns and "ok" not in df.columns

# ── R107-2: لا «OK» ومراقبُ المصدر لا يُقرأ — المرّةُ الثالثة (R89-2 · R94-2) ──────────────────
def test_a_stamp_that_differs_from_the_tree_is_not_ok():
    """**ضابطُ R107-2:** التطبيقُ يجيب والقالبُ يحوّل **وكودُه مخالفٌ لكود الشجرة** ⇒ ليس `OK`
    بل `STALE` — لأنّ أيَّ توقّفٍ للعملية يُقلعها من كود المجلّد (كودٌ لم يُقَس بالأسئلة).
    **وكان المراقبُ يكتب «OK» طوال الوقت** في هذا الحال (المقيس في المراجعة ١٠٧: ثلاثُ ساعات).
    """
    assert mon.state_of(True, True, True) == "OK"
    assert mon.state_of(True, True, False) == "STALE"      # ← عينُ العطب
    assert mon.state_of(False, True, True) == "DOWN"       # السقوطُ يسبق حكمَ المصدر
    assert mon.state_of(True, False, True) == "DOWN"


def test_stale_is_a_state_the_log_and_the_transition_know():
    """**والحالةُ الثالثةُ تُقرأ وتُنذر:** `last_state` يعرفها، و`transition` ينطق بها مرّةً عند
    التغيّر — ولا يقرؤها «عاد» (فلا إشعارُ شفاءٍ على كودٍ غيرِ مفحوص).
    """
    log = ("2026-10-13 12:00:00 OK app=up redirect=up source=ok\n"
           "2026-10-13 12:10:00 STALE app=up redirect=up source=stale\n")
    assert mon.last_state(log) == "STALE"
    assert mon.transition("OK", "STALE") == "stale"
    assert mon.transition("STALE", "STALE") == ""
    assert mon.transition("STALE", "OK") == "up"


def test_the_provenance_reader_is_the_existing_verdict():
    """**ولا آليّةَ جديدة:** المراقبُ ينادي `tools/qa_gate._provenance_verdict` بدوالّه القائمة —
    يُقاس بوجود الدالّة نفسِها في مخرَج القراءة، لا بنصٍّ في الملفّ.
    """
    ok, why = mon.provenance_state()
    assert isinstance(ok, bool) and isinstance(why, str)
    if not ok:
        assert why, "رفضٌ بلا سبب ⇒ لا يُنبّه بشيء"

