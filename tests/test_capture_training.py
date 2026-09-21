"""Synthetic tests for the training-sample capture — no real statement data.

The dataset rule is "no sample without proof of its label", and two of its
clauses are the kind that fail silently if untested:

  · the evaluation holdout — if a held-out page ever lands in the training set,
    every later measurement is worthless, and nothing in the artifacts shows it;
  · the header mask — a page image that keeps the account holder's name and
    account number is a privacy leak that no count would reveal.

So both are checked here mechanically, on a fixture built in this file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from tools.capture_training import (  # noqa: E402
    HEADER_MASK_FRACTION,
    adopt_legacy,
    attach_balances,
    capture_page,
    is_holdout,
    redact_top,
    split_rows,
    write_index,
)


# ── بيانٌ لكل مستند، لا بيانٌ واحد (عطب ف٢) ─────────────────────────────────
# كان البيانُ يُكتب في أعلى مجلد الالتقاط، فتشغيلةُ مستندٍ ثانٍ تمحو بيانَ الأول:
# عيّناتٌ تفقد نسبَها ولا شيء في الأثر يدلّ عليها.
def test_two_documents_leave_two_manifests_and_an_index(tmp_path):
    """مستندان مُلتقَطان ⇒ بيانان وفهرسٌ يجمعهما بمفتاح (doc_id, page)."""
    out = tmp_path / "training"
    for did in ("docA", "docB"):
        (out / did).mkdir(parents=True)
        (out / did / "manifest.json").write_text(json.dumps(
            {"doc_id": did, "captured_at": "2026-09-22",
             "pages": {"captured": 2, "holdout_reserved": 1},
             "holdout_rule": "page % 3 == 0", "cost_usd": "0"}))
    idx = write_index(out)
    assert idx["count"] == 2, "بيانٌ واحد لمستندَين = عيّناتٌ تفقد نسبَها"
    assert {d["doc_id"] for d in idx["documents"]} == {"docA", "docB"}
    assert (out / "docB" / "manifest.json").exists(), "بيانُ المستند الثاني مُحي"


def test_a_legacy_manifest_stops_the_capture_by_name(tmp_path):
    """بيانٌ بصيغةٍ قديمة لا يُهمَل صامتاً: الكتابةُ تتوقّف ويُسمّى العلاج."""
    out = tmp_path / "training"
    out.mkdir()
    (out / "manifest.json").write_text(json.dumps({"doc_id": "old"}))
    try:
        write_index(out)
    except SystemExit as exc:
        assert "adopt-legacy" in str(exc)
    else:
        raise AssertionError("بيانٌ بصيغةٍ قديمة مرّ صامتاً — وهذا هو العطبُ نفسه")


def test_adopting_a_legacy_manifest_keeps_the_original_on_disk(tmp_path):
    """الترحيلُ نسخٌ وإعادةُ تسمية: القيمُ تُنقل والأصلُ لا يُحذف."""
    out = tmp_path / "training"
    out.mkdir()
    (out / "manifest.json").write_text(json.dumps(
        {"doc_id": "old", "pages": {"captured": 3}}))
    adopt_legacy(out)
    moved = json.loads((out / "old" / "manifest.json").read_text())
    assert moved["pages"]["captured"] == 3
    assert (out / "manifest.json.adopted").exists(), "الأصل يجب ألا يُحذف"
    assert not (out / "manifest.json").exists()
    assert write_index(out)["count"] == 1


# ── حجز التقييم ─────────────────────────────────────────────────────────────
def test_the_holdout_is_deterministic_and_repeatable():
    """نفس الصفحة تُحجز في كل تشغيلة — وإلا فالتقييم يتغيّر بين قياسين."""
    assert [is_holdout(p, 3) for p in (3, 6, 9)] == [True, True, True]
    assert [is_holdout(p, 3) for p in (1, 2, 4, 5)] == [False] * 4
    assert is_holdout(7, 0) is False  # صفر ⇒ لا حجز (يُعلن صراحةً)


def test_a_held_out_page_is_never_captured(tmp_path):
    """القاعدة الأهمّ: ما يُقاس عليه لا يُتدرَّب عليه — وهي بنيوية لا حسن نيّة."""
    run = _fixture_run(tmp_path)
    rows = _rows_for_page(3)
    out = tmp_path / "training"
    if not is_holdout(3, 3):
        capture_page(3, run, out, rows, "doc", _meta(), HEADER_MASK_FRACTION)
    assert not (out / "doc" / "pg-003").exists()


# ── القناع ──────────────────────────────────────────────────────────────────
def test_the_mask_leaves_no_ink_above_it_and_keeps_the_table():
    img = Image.new("L", (200, 400), 255)
    a = np.asarray(img).copy()
    a[:80, :] = 0        # ترويسة (اسم/حساب)
    a[120:, :] = 0       # جدول
    src = Image.fromarray(a)
    out = np.asarray(redact_top(src, 0.3))
    assert out[:120].max() == 255, "بقي حبرٌ في الشريط المحجوب"
    assert out[120:].min() == 0, "القناع أكل الجدول"


# ── الوسم: ما لا دليل عليه لا يُحفظ ────────────────────────────────────────
def test_unproven_rows_are_dropped_and_counted_not_hidden():
    rows = [
        {"row_no": 1, "proof_source": "السلسلة: فرق رصيدين متتاليين", "proven_amount": "10"},
        {"row_no": 2, "proof_source": "الورق المطبوع: مبلغ المرساة", "proven_amount": "5"},
    ]
    kept, dropped = split_rows(rows)
    assert [r["row_no"] for r in kept] == [1]
    assert [r["row_no"] for r in dropped] == [2]


def test_balance_is_joined_by_value_not_by_position():
    """المحاذاة تُقاس: إن اختلف المبلغ المطبوع عن المقروء فلا رصيد يُقرَن."""
    kept = [{"printed_amount": "٣٠٠,٠٠", "proof_source": "السلسلة"}]
    ok, bad = attach_balances(kept, [{"movement": "300.00", "balance": "689.41"}])
    assert (ok, bad) == (1, 0)
    assert kept[0]["balance"] == "689.41"

    kept2 = [{"printed_amount": "٣٠٠,٠٠", "proof_source": "السلسلة"}]
    ok2, bad2 = attach_balances(kept2, [{"movement": "301.00", "balance": "689.41"}])
    assert (ok2, bad2) == (0, 1)
    assert "balance" not in kept2[0], "رصيدٌ قُرن بصفٍّ غير محاذٍ"


# ── التوليف الكامل على عيّنة مبنية هنا ─────────────────────────────────────
def test_capture_writes_a_self_describing_label(tmp_path):
    run = _fixture_run(tmp_path)
    out = tmp_path / "training"
    res = capture_page(1, run, out, _rows_for_page(1), "doc", _meta(), HEADER_MASK_FRACTION)
    assert res["status"] == "captured"
    label = json.loads((out / "doc" / "pg-001" / "label.json").read_text())
    prov = label["rows"][0]["field_provenance"]
    assert prov["proven_amount"] == "chain_delta"
    assert prov["descr"] == "read"
    assert label["label_source"]["gate"], "الوسم بلا إشارة إلى مصدره"
    assert label["privacy"], "وسمٌ لا يُعلن الخصوصية"


def _meta() -> dict:
    return {"label_source": {"export": "x.xlsx", "export_sha256": "0" * 16,
                             "gate": "verify_close ALL PASS"},
            "ink_ratio": None}


def _rows_for_page(page: int) -> list[dict]:
    return [
        {"row_no": 2, "date_iso": "2013-10-31", "descr": "تحويل",
         "printed_amount": "٣٠٠,٠٠", "proven_amount": "300", "side": "credit",
         "proof_source": "السلسلة: فرق رصيدين متتاليين"},
        {"row_no": 3, "date_iso": "2013-11-07", "descr": "سحب",
         "printed_amount": "١٠٠,٠٠", "proven_amount": "100", "side": "debit",
         "proof_source": "الورق المطبوع: مبلغ المرساة"},
    ]


def _fixture_run(tmp: Path) -> Path:
    run = tmp / "run"
    (run / "pages").mkdir(parents=True)
    (run / "results").mkdir(parents=True)
    a = np.full((400, 200), 255, dtype=np.uint8)
    a[80:120, 10:190] = 0
    a[200:, 10:190] = 0
    Image.fromarray(a).save(run / "pages" / "pg-001.png")
    Image.fromarray(a).save(run / "pages" / "pg-003.png")
    (run / "results" / "pg-001.json").write_text(json.dumps(
        {"raw_rows": [{"movement": "300.00", "balance": "689.41"},
                      {"movement": "100.00", "balance": "589.41"}]}))
    Workbook().save(tmp / "export.xlsx")  # الصفوف تُمرَّر مباشرةً في هذا الاختبار
    return run
