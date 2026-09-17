"""Public numbers must be derived from the run, not remembered (audit P2-5).

Four drifts were caught by a human reading two files at once; this test is the
mechanism that replaces that. It skips where the evidence does not exist (CI
has no statement cache), which is stated plainly rather than hidden.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def test_public_documents_match_the_measured_report():
    import render_claims as rc

    if not rc.REPORT.exists():
        # CI has no statement cache. Instead of skipping — a gate that guards
        # nothing — it reads the DERIVED snapshot committed with the repo:
        # written by tools/render_claims.py from the measured report, so the
        # numbers stay a product of the run and not of anyone's memory.
        snapshot = ROOT / "docs" / "claims.json"
        if not snapshot.exists():
            pytest.skip("لا تقرير ولا لقطة مشتقّة — لا شيء يُحرَس")
        derived = json.loads(snapshot.read_text(encoding="utf-8"))
        assert rc.check(derived) == [], "الوثيقة تخالف لقطتها المشتقّة"
        return
    derived = rc.derive()
    assert derived is not None
    drifts = rc.check(derived)
    assert drifts == [], f"انزياح بين الوثيقة ومصدرها: {drifts}"


def test_claims_lists_every_metric_it_promises():
    import render_claims as rc

    fake = {"pages": 629, "rows": 5793, "clean": 5770, "clean_pct": "99.6%",
            "ok": 621, "mismatch": 0, "gap": 2, "absent": 4, "unchecked": 2,
            "documented_ratio": "621/629", "clean_ratio": "5770/5793",
            "recoveries": 23, "rereads": 15, "arbitrations": 3,
            "median_page_s": 22.18, "tests": 113}
    pairs = rc.claims(fake)
    assert len(pairs) >= 8
    assert any(n == "621/629" for _f, n, _l in pairs)
    assert any("مرساة" in n for _f, n, _l in pairs)
