"""The description-accuracy harness (`tools/desc_accuracy.py compare`): counts, never text.

The committed evidence (`docs/evidence/desc_accuracy_{20,50}p.json`) is produced by this
function from real statement pages, so what it may write is the whole privacy question:
page numbers, integers and booleans — no description word, no amount. Checked here on a
synthetic run with words chosen to be greppable. Stdlib only; no network, no real data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
if str(PROJ / "tools") not in sys.path:
    sys.path.insert(0, str(PROJ / "tools"))

from desc_accuracy import compare, relation, words  # noqa: E402


def _run(tmp_path: Path) -> Path:
    """صفحتان: الأولى تنتهي بصفٍّ يُكمَل في الثانية، وقراءةُ الصفحة ألصقت التكملةَ بأوّل صفّ الثانية."""
    run = tmp_path / "run"
    (run / "results").mkdir(parents=True)
    pages = {1: ["ZEBRA", "QUOKKA"], 2: ["KIWI TAPIR", "OKAPI"]}   # «TAPIR» تكملةُ «QUOKKA»
    for pg, descs in pages.items():
        rows = [{"balance": "7.77", "desc": d} for d in descs]
        (run / "results" / f"pg-{pg:03d}.json").write_text(json.dumps({"pg": pg, "raw_rows": rows}),
                                                          encoding="utf-8")
    return run


REFERENCE = {"rows": {
    "1:0": {"stitched": False, "row": {"desc": "ZEBRA"}},
    "1:1": {"stitched": True, "row": {"desc": "QUOKKA TAPIR"}},
    "2:0": {"stitched": False, "row": {"desc": "KIWI"}},
    "2:1": {"stitched": False, "row": {"desc": "OKAPI"}},
}}
COLUMN = {"pages": {"1": {"descs": {"1": "ZEBRA", "2": "QUOKKA TAPIR"}},
                    "2": {"descs": {"1": "KIWI", "2": "OKAPI"}}}}


def test_the_categories_are_word_sets_ignoring_order_digits_and_script_joins():
    assert words("تحويل IBOUOAعبد ٠٢") == words("عبد IBOUOA تحويل")
    assert relation(words("a b c"), words("a b c")) == "same"
    assert relation(words("aa bb"), words("aa bb cc")) == "one_side_extra"
    assert relation(words("aa bb"), words("aa cc")) == "small"
    assert relation(words("aa bb cc"), words("dd ee ff")) == "big"


def test_the_continuation_and_its_misplacement_are_counted(tmp_path):
    out = compare(_run(tmp_path), [1, 2], REFERENCE, COLUMN)
    p2 = out["per_page"]["2"]["after_continuation"]
    assert p2 == {"continuation_isolated": True, "page_read_pasted_into_first_row": True,
                  "column_carried_on_previous": True, "column_first_row_same_as_reference": True,
                  "page_read_first_row_same_as_reference": False}
    assert out["totals"]["column_vs_reference"] == {"same": 4}
    assert out["totals"]["page_read_vs_reference"] == {"same": 2, "one_side_extra": 2}


def test_the_counts_file_carries_no_description_text(tmp_path):
    dumped = json.dumps(compare(_run(tmp_path), [1, 2], REFERENCE, COLUMN))
    for word in ("ZEBRA", "QUOKKA", "TAPIR", "KIWI", "OKAPI", "7.77"):
        assert word not in dumped, f"نصٌّ من البيان تسرّب إلى ملفّ الأعداد: {word}"
