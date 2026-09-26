"""The large-run description pass (`tools/desc_pass.py`) and the export flag that reads it.

The cache (`results/pg-NNN.json`) is never written: page seals, the eval pack and the
published numbers stand on it. Descriptions live in `results/desc/`, and the workbook takes
them only with `--desc-column`. A synthetic three-page run, a fake reader instead of the
model. No network, no API key, no real data.
"""
from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
from PIL import Image

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src"), str(PROJ / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import desc_pass  # noqa: E402
from statement_qa.desc_reader import sidecar_path  # noqa: E402
from statement_qa.footer_oracle import page_totals  # noqa: E402
from statement_qa.vlm_reader import chain_derive  # noqa: E402

K = 2.0


def _box(g, x0, x1, y0, y1):
    g[int(y0 * K):int(y1 * K), int(x0 * K):int(x1 * K)] = 0


def _png(path: Path, n_rows: int, orphan: bool):
    g = np.full((int(1170 * K), int(827 * K)), 255, np.uint8)
    _box(g, 400, 590, 332, 340)
    _box(g, 650, 700, 977, 985)
    y = 400
    if orphan:
        _box(g, 380, 600, y, y + 10)
        y += 20
    for _ in range(n_rows):
        _box(g, 110, 160, y, y + 8)
        _box(g, 640, 705, y, y + 8)
        _box(g, 360, 390, y + 1, y + 7)
        _box(g, 430, 620, y - 1, y + 8)
        _box(g, 380, 600, y + 15, y + 25)
        y += 30
    Image.fromarray(g).save(path)


def _run(tmp_path: Path, rows_per_page=(3, 2, 2), orphans=(False, True, True), break_pair=None):
    """ثلاثُ صفحاتٍ متسلسلةُ الرصيد، وتذييلاتُها التراكمية محسوبةٌ بنفس الدالة ⇒ كلُّ جارَين `adjacent`
    — إلا `break_pair` (رقمُ صفحة) فيُفسَد تذييلُها ⇒ الجاران حولها `mismatch`."""
    run = tmp_path / "data" / "local_sample" / "run"
    (run / "results").mkdir(parents=True)
    (run / "pages").mkdir()
    bal, prev, cum_d, cum_c = Decimal("8413.29"), None, Decimal("0"), Decimal("0")
    for pg, (n, orphan) in enumerate(zip(rows_per_page, orphans), start=1):
        raw = []
        for j in range(n):
            bal -= Decimal("12.34")
            raw.append({"movement": "12.34", "balance": str(bal), "desc": f"قديم {pg}-{j}",
                        "date": "٢٠٢٤٠١٠١", "raw_movement": "12.34", "raw_balance": str(bal)})
        derived = chain_derive([{**r, "movement": Decimal(r["movement"]),
                                 "balance": Decimal(r["balance"])} for r in raw], prev_balance=prev)
        t = page_totals(derived)
        prev = t["balance"]
        cum_d, cum_c = cum_d + t["debits"], cum_c + t["credits"]
        footer = {"debits": str(cum_d + (5 if pg == break_pair else 0)), "credits": str(cum_c),
                  "balance": str(bal)}
        (run / "results" / f"pg-{pg:03d}.json").write_text(json.dumps(
            {"pg": pg, "page_no": pg, "raw_rows": raw, "footer": footer}, ensure_ascii=False),
            encoding="utf-8")
        _png(run / "pages" / f"pg-{pg:03d}.png", n, orphan)
    (run / "slice_report.json").write_text(json.dumps(
        {"per_page": [{"page": p} for p in (1, 2, 3)]}), encoding="utf-8")
    return run


def _reader(seen):
    def read(img, pb, cont, stats):
        page = hashlib.md5(img.tobytes()).hexdigest()[:6]
        seen.append((len(pb.bands), cont is not None))
        stats["cost"] = 0.01
        return [f"عمود {page}-{i}" for i in range(len(pb.bands))]
    return read


def _cache_digest(run):
    return {f.name: f.read_bytes() for f in sorted((run / "results").glob("pg-*.json"))}


def test_one_sidecar_per_page_the_cache_untouched_and_the_continuation_joined(tmp_path):
    run = _run(tmp_path)
    before = _cache_digest(run)
    seen: list = []
    rep = desc_pass.run_pass(run, reader=_reader(seen))
    assert rep["written"] == [1, 2, 3] and rep["stitched"] == 2
    assert seen == [(3, True), (2, True), (2, False)]
    assert _cache_digest(run) == before, "الكاشُ لا يُمسّ"
    side = json.loads(sidecar_path(run / "results", 1).read_text(encoding="utf-8"))
    assert side["stamp"]["prompt_version"].startswith("custom:") and len(side["descs"]) == 3


def test_no_continuation_across_neighbours_the_arithmetic_does_not_prove(tmp_path):
    run = _run(tmp_path, break_pair=3)        # تذييلُ ٣ فاسد ⇒ ٢→٣ غيرُ مثبت
    seen: list = []
    rep = desc_pass.run_pass(run, reader=_reader(seen))
    assert seen == [(3, True), (2, False), (2, False)] and rep["stitched"] == 1


def test_a_rerun_pays_nothing_and_a_changed_prompt_is_reread(tmp_path):
    run = _run(tmp_path)
    desc_pass.run_pass(run, reader=_reader([]))
    seen: list = []
    rep = desc_pass.run_pass(run, reader=_reader(seen))
    assert seen == [] and rep["cached"] == 3
    side = sidecar_path(run / "results", 2)
    data = json.loads(side.read_text(encoding="utf-8"))
    data["stamp"] = {"model": "x", "prompt_version": "custom:old"}
    side.write_text(json.dumps(data), encoding="utf-8")
    rep = desc_pass.run_pass(run, reader=_reader(seen))
    assert rep["stale"] == 1 and rep["written"] == [2]


def test_the_cost_cap_stops_and_a_mismatched_page_is_never_paid(tmp_path):
    run = _run(tmp_path)
    rep = desc_pass.run_pass(run, max_cost=0.015, reader=_reader([]))
    assert rep["written"] == [1, 2] and rep["stopped_at"] == 3
    run2 = _run(tmp_path / "b", rows_per_page=(3, 2, 2))
    _png(run2 / "pages" / "pg-002.png", 3, True)          # الحبرُ ٣ صفوف والكاشُ ٢
    seen: list = []
    rep = desc_pass.run_pass(run2, reader=_reader(seen))
    assert rep["unaligned"] == [2] and 2 not in rep["written"] and len(seen) == 2


def test_the_tool_refuses_a_run_the_repository_would_track(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["desc_pass.py", "--run", str(PROJ / "data" / "sample")])
    assert desc_pass.main() == 2


def test_the_workbook_takes_the_column_only_with_the_flag(tmp_path):
    from tools.to_xlsx import load

    run = _run(tmp_path)
    desc_pass.run_pass(run, reader=_reader([]))
    plain, report, _v, _f = load(run)
    assert all(r["desc"].startswith("قديم") for r in plain), "بلا العلم: المصنّفُ كما كان"
    assert "desc_column" not in report
    side = sidecar_path(run / "results", 3)
    data = json.loads(side.read_text(encoding="utf-8"))
    data["descs"] = data["descs"][:1]                         # عددٌ لا يطابق ⇒ يبقى القديم
    side.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rows, report, _v, _f = load(run, desc_column=True)
    assert report["desc_column"] == {"applied": [1, 2], "unaligned": [3], "absent": []}
    assert [r["desc"].startswith("عمود") for r in rows] == [True] * 5 + [False] * 2
    assert [r["movement"] for r in rows] == [r["movement"] for r in plain], "الأرقامُ لا تُمسّ"
