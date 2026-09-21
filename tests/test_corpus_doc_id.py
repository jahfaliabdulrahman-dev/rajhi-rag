"""هويةُ الكوربوس مفتاحٌ لا زينة: بوابةُ التقاطع تُقابل `(doc_id, page)`.

صفحاتُ الـ629 قُرئت قبل أن يُسجَّل الوسم في المشروع، فالختمُ **استدراكٌ يُعلن** لا
إعادةُ قراءة. وهذان هما السلوكان اللذان يجب أن يُقاسا لا يُفترَضا: أن يكون الوسمُ من
الملف نفسه، وأن يُعلَن المجهولُ حين يغيب الملفُّ بدل تخمين وسم.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tools.backfill_reader_stamp import main, sha256_16  # noqa: E402

DOC_BYTES = b"%PDF-1.4 fake corpus"


def _run(tmp: Path, with_doc: bool = True) -> Path:
    run = tmp / "run"
    (run / "results").mkdir(parents=True)
    (run / "slice_report.json").write_text(json.dumps(
        {"footer_role": "cumulative_printed_totals"}, ensure_ascii=False))
    (run / "results" / "pg-001.json").write_text(json.dumps({"raw_rows": []}))
    if with_doc:
        (run / "slice_629p.pdf").write_bytes(DOC_BYTES)
    return run


def _stamp(monkeypatch, run: Path) -> dict:
    monkeypatch.setattr(sys, "argv",
                        ["backfill_reader_stamp.py", "--run", str(run)])
    main()
    report = json.loads((run / "slice_report.json").read_text(encoding="utf-8"))
    return report["corpus_provenance"]


def test_the_doc_id_is_the_file_hash_not_a_guess(tmp_path, monkeypatch):
    """الوسمُ يُشتقّ من الملف: نفسُ العُرف المستعمل في capture_training وtext_reader."""
    cp = _stamp(monkeypatch, _run(tmp_path))
    assert cp["doc_id"] == hashlib.sha256(DOC_BYTES).hexdigest()[:16]
    assert cp["doc_file"] == "slice_629p.pdf"
    assert sha256_16(PROJ / "docs" / "handoff-protocol.md") == hashlib.sha256(
        (PROJ / "docs" / "handoff-protocol.md").read_bytes()).hexdigest()[:16]
    assert cp["doc_id_backfilled_at"], "وسمٌ بلا وقتٍ لا يُعرَف متى استُدرك"


def test_the_stamp_is_a_declaration_not_a_re_read(tmp_path, monkeypatch):
    """الختمُ لا يمسّ نقاطَ الفحص: إعلانُ استدراكٍ لا قراءةٌ جديدة تدفع ثمنَها."""
    run = _run(tmp_path)
    before = (run / "results" / "pg-001.json").read_text(encoding="utf-8")
    cp = _stamp(monkeypatch, run)
    assert (run / "results" / "pg-001.json").read_text(encoding="utf-8") == before
    assert cp["legacy_unstamped_pages"] == 1, "الغيرُ مختم يُعدّ ويُعلن لا يُسكَت عنه"
    assert cp["reader"] is None, "قارئٌ مجهولٌ لا يُخترَع له اسم"


def test_a_missing_document_is_declared_unknown_not_guessed(tmp_path, monkeypatch):
    """لا وسمَ بلا ملفّ: المجهولُ يُعلن ويُسمّى المفقود."""
    cp = _stamp(monkeypatch, _run(tmp_path, with_doc=False))
    assert cp["doc_id"] is None
    assert "غير موجود" in cp["doc_id_note"], "المفقودُ يُسمّى، والوسمُ لا يُخمَّن"
