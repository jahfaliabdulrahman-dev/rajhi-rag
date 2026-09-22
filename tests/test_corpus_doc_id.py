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


# ── عدم التدهور: الحالةُ السابقة جزءٌ من المُدخَل لا خارجٌ عنه ────────────────
# الاختبارُ السابق يُثبت «فارغ → null» وهو صحيح، لكنه **لا يرى الانتقالَ من حالةٍ
# ممتلئة** — وهو الانتقالُ الذي كان يمحو هويةً مُثبتة بخروجٍ ناجح.
def _stamped_run(tmp_path, doc_id: str | None, with_doc: bool = False) -> Path:
    run = _run(tmp_path, with_doc=with_doc)
    report = json.loads((run / "slice_report.json").read_text(encoding="utf-8"))
    report["corpus_provenance"] = {"reader": None, "legacy_unstamped_pages": 629,
                                   "doc_id": doc_id, "doc_file": "slice_629p.pdf",
                                   "custom_declaration": "تصريحٌ سابق يجب ألا يُمحى"}
    (run / "slice_report.json").write_text(json.dumps(report, ensure_ascii=False))
    return run


def test_an_established_identity_is_not_demoted_by_a_missing_document(tmp_path, monkeypatch):
    """⚠️ العطبُ الذي كشفه المدقّق: غيابُ الملفّ كان يمحو `doc_id` مُثبتاً ويُبدّله بـnull."""
    run = _stamped_run(tmp_path, "3e2d360a665c88aa", with_doc=False)
    _stamp(monkeypatch, run)
    report = json.loads((run / "slice_report.json").read_text(encoding="utf-8"))
    cp = report["corpus_provenance"]
    assert cp["doc_id"] == "3e2d360a665c88aa", "هويةٌ مُثبتة دُهوِرت بغياب ملفّ"
    assert cp["custom_declaration"] == "تصريحٌ سابق يجب ألا يُمحى", \
        "الكتابةُ استبدلت التصريحَ السابق بدل أن تدمجه"


def test_the_demotion_guard_is_held_at_the_unit_level():
    """القاعدة نفسها على مستوى الدالّة: هويةٌ مُثبتة + ملفٌّ غائب ⇒ `kept` لا `null`."""
    from tools.backfill_reader_stamp import resolve_doc_id
    cp = {"doc_id": "3e2d360a665c88aa"}
    status = resolve_doc_id(cp, Path("/قطعيًّا/غير-موجود.pdf"))
    assert status == "kept" and cp["doc_id"] == "3e2d360a665c88aa"
    assert "محفوظة" in cp["doc_id_note"], "الحفاظُ على الهوية يُعلن لا يُسكَت عنه"


def test_a_matching_document_leaves_the_identity_unchanged(tmp_path, monkeypatch):
    """ملفٌّ يطابق الوسمَ المُثبت ⇒ لا تغيير، والاستدراكُ لا يُعاد."""
    run = _run(tmp_path)
    cp = _stamp(monkeypatch, run)                    # يُختم أولاً
    assert cp["doc_id"]
    again = _stamp(monkeypatch, run)                 # ثم يُعاد على الحالة الممتلئة
    assert again["doc_id"] == cp["doc_id"]
    assert "لا تغيير" in again["doc_id_note"]


def test_a_conflicting_document_stops_by_name(tmp_path, monkeypatch):
    """مستندٌ مخالف لا يُستبدل به وسمٌ مُثبت صامتاً: يقف بالاسم."""
    run = _stamped_run(tmp_path, "deadbeefdeadbeef", with_doc=True)
    try:
        _stamp(monkeypatch, run)
    except SystemExit as exc:
        assert "تخالف" in str(exc)
    else:
        raise AssertionError("وسمٌ مُثبت استُبدل بمستندٍ مخالف بلا إعلان إرادة")


def test_an_explicitly_missing_document_stops_by_name(tmp_path, monkeypatch):
    """ملفٌّ مطلوبٌ صراحةً وغير موجود ⇒ خروجٌ بخطأ يسمّي السبب لا صمتٌ بنجاح."""
    run = _run(tmp_path)
    monkeypatch.setattr(sys, "argv", ["x", "--run", str(run), "--doc",
                                      str(tmp_path / "not-there.pdf")])
    try:
        main()
    except SystemExit as exc:
        assert "غير موجود" in str(exc)
    else:
        raise AssertionError("ملفٌّ مطلوبٌ غائب مرّ بنجاح")


def test_an_unknown_identity_is_upgraded_when_the_document_appears(tmp_path, monkeypatch):
    """الممنوعُ التدهورُ لا الترقية: مجهولٌ يصير مُثبتاً متى وُجد الملفّ."""
    run = _stamped_run(tmp_path, None, with_doc=False)
    assert _stamp(monkeypatch, run)["doc_id"] is None
    (run / "slice_629p.pdf").write_bytes(DOC_BYTES)
    cp = _stamp(monkeypatch, run)
    assert cp["doc_id"] == hashlib.sha256(DOC_BYTES).hexdigest()[:16]


# ── البابُ المعلن يُسجّل من عبَر: الاستبدالُ الصريح لا يمحو أثرَه ────────────
# `doc_id` مفتاحُ بوابة التقاطع، فحزمةٌ استُبدلت هويتُها تحتها تمرّ البوابةَ لأن
# الطرفين تحرّكا معاً — صنفُ «الشاهدُ يتحرّك مع المشهود له».
def _replace(monkeypatch, run: Path, doc_bytes: bytes) -> dict:
    (run / "slice_629p.pdf").write_bytes(doc_bytes)
    monkeypatch.setattr(sys, "argv", ["x", "--run", str(run), "--replace-doc-id"])
    main()
    return json.loads((run / "slice_report.json").read_text(encoding="utf-8"))["corpus_provenance"]


def test_an_explicit_replacement_records_what_it_replaced(tmp_path, monkeypatch):
    """الاستبدالُ الصريح يُقيَّد: ما استُبدل، ومتى، وبأي سبب — والملاحظةُ لا تكذب."""
    run = _stamped_run(tmp_path, "3e2d360a665c88aa", with_doc=True)
    cp = _replace(monkeypatch, run, b"document B")
    new = hashlib.sha256(b"document B").hexdigest()[:16]
    assert cp["doc_id"] == new
    assert cp["doc_id_previous"] == "3e2d360a665c88aa", "الاستبدالُ بلا أثرٍ لما استُبدل"
    assert "استبدال" in cp["doc_id_note"] and "3e2d360a665c88aa" in cp["doc_id_note"], \
        "الملاحظةُ تحكي الختمَ الأول وتُخفي الاستبدال"
    h = cp["doc_id_history"][-1]
    assert (h["previous"], h["replaced_by"]) == ("3e2d360a665c88aa", new)
    assert h["at"] == cp["doc_id_replaced_at"] and "صريح" in h["reason"], \
        "سجلُّ الاستبدال بلا وقتٍ أو بلا سببٍ معلن"


def test_a_second_replacement_keeps_the_whole_history(tmp_path, monkeypatch):
    """سجلٌّ تراكميّ لا حقلُ «آخر استبدال»: من استُبدل مرّتين يظهر مرّتين."""
    run = _stamped_run(tmp_path, "aaaaaaaaaaaaaaaa", with_doc=True)
    _replace(monkeypatch, run, b"document B")
    cp = _replace(monkeypatch, run, b"document C")
    assert [h["previous"] for h in cp["doc_id_history"]] == [
        "aaaaaaaaaaaaaaaa", hashlib.sha256(b"document B").hexdigest()[:16]]
    assert cp["doc_id_previous"] == hashlib.sha256(b"document B").hexdigest()[:16]

def test_a_round_trip_is_not_declared_unchanged(tmp_path, monkeypatch):
    """⚠️ **حقيقةٌ عادت إلى قيمتها الأولى ليست حقيقةً لم تتغيّر.**

    استبدالٌ ثم رجوعٌ إلى الأصل ⇒ القيمةُ النهائية تُطابق البداية حرفيًّا، والإعلانُ
    «لا تغيير» على هذا المسار كذبٌ: السجلُّ وحدَه يفضح أنها مرّت بمستندين.
    """
    run = _stamped_run(tmp_path, hashlib.sha256(DOC_BYTES).hexdigest()[:16], with_doc=True)
    _replace(monkeypatch, run, b"document B")
    _replace(monkeypatch, run, DOC_BYTES)                     # رجوعٌ إلى الأصل
    cp = _stamp(monkeypatch, run)                             # حارسٌ عادي: الملفُّ == الوسم
    assert cp["doc_id"] == hashlib.sha256(DOC_BYTES).hexdigest()[:16], "القيمةُ عادت"
    assert len(cp["doc_id_history"]) == 2
    # لا نعتمد على حرفٍ مُشكَّلٍ مطبوع (التفخيذُ يكسر المطابقة الحرفيّة)
    assert "مرّت بـ2" in cp["doc_id_note"] and "لا يعني أن المسارَ لم يتغيّر" in cp["doc_id_note"], (
        "الرجوعُ إلى القيمة الأولى أُعلن «لا تغيير» — والمسارُ مرّ بمستندين")
