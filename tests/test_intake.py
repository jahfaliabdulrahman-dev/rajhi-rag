"""Pre-read inspection: nothing is paid for before the file passes.

Two levels. The decision module (`statement_qa.intake`) is pure and tested
directly. The app wiring is tested by running `_process_pdf_locked` with every
paid call replaced by a recorder — that is the only way to PROVE the two
properties that matter: a blocked upload makes zero paid calls, and the pages
are read in their true order with each footer paid for once.

No network, no API key, no real data.
"""
from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal as D
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parents[1]
for _p in (str(PROJ), str(PROJ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from statement_qa.intake import (  # noqa: E402
    blocked_message_ar, inspect_locally, plan, summary_ar,
)

BLUR = "الصورة غير حادة (اهتزاز/ضبابية)"
NO_REF = "سطر الإطار غير مكشوف"
EMPTY = "الصفحة فارغة"


def _gate(verdicts: dict[int, str]):
    """verdicts: موضع ⇒ reject | blank | warn | accept (الافتراضي)."""
    table = {"reject": ("reject", ["blur"], [BLUR]), "blank": ("reject", ["blank"], [EMPTY]),
             "warn": ("warn", ["no_referee"], [NO_REF]), "accept": ("accept", [], [])}

    def gate_fn(img):
        v, codes, ar = table[verdicts.get(int(Path(img).stem.split("-")[-1]), "accept")]
        return {"verdict": v, "reasons": codes, "reasons_ar": ar}
    return gate_fn


def _images(n):
    return [f"/tmp/pg-{i:02d}.png" for i in range(1, n + 1)]


def _intake(verdicts, n=5, kinds=None):
    kinds = kinds or {}
    return inspect_locally(_images(n), _gate(verdicts),
                           lambda img: kinds.get(int(Path(img).stem.split("-")[-1]),
                                                 "transactions"))


# ————————————————————— القرار —————————————————————

def test_a_rejected_page_stops_the_run_and_says_what_to_reshoot():
    intake = _intake({2: "reject"})
    decision = plan(intake, skip_rejected=False)
    assert decision == {"blocked": True, "process": [], "skipped": [2], "blank": []}
    msg = blocked_message_ar(intake)
    assert "لم يُدفع شيء" in msg and "ص2" in msg and BLUR in msg


def test_skipping_reads_the_rest_and_names_what_was_skipped():
    intake = _intake({2: "reject", 4: "reject"})
    decision = plan(intake, skip_rejected=True)
    assert decision == {"blocked": False, "process": [1, 3, 5], "skipped": [2, 4], "blank": []}
    seg = summary_ar(intake, decision["skipped"])
    assert "مستبعدة بلا قراءة 2" in seg and "ص4" in seg


def test_skipping_every_page_is_still_blocked():
    intake = _intake({p: "reject" for p in range(1, 4)}, n=3)
    assert plan(intake, skip_rejected=True)["blocked"] is True


def test_a_blank_sheet_is_left_unread_and_never_blocks():
    """ملفُّ المالك نفسُه فيه ثلاثُ أوراقٍ بيضاء (حبرُها ٠٫٠): منعُ الرفع بها كان سيوقفه."""
    intake = _intake({3: "blank"})
    decision = plan(intake, skip_rejected=False)
    assert decision == {"blocked": False, "process": [1, 2, 4, 5], "skipped": [], "blank": [3]}
    assert "أوراقٌ فارغة تُركت بلا قراءة: ص3" in summary_ar(intake, decision["skipped"])


def test_a_file_of_only_blank_sheets_does_not_start():
    intake = _intake({1: "blank", 2: "blank"}, n=2)
    assert plan(intake, skip_rejected=True)["blocked"] is True
    assert "لا صفحةَ فيها ما يُقرأ" in blocked_message_ar(intake)


def test_warned_pages_are_read_and_named():
    intake = _intake({3: "warn"})
    decision = plan(intake, skip_rejected=False)
    assert decision["process"] == [1, 2, 3, 4, 5]
    seg = summary_ar(intake, decision["skipped"])
    assert "بتحذير 1" in seg and NO_REF in seg and "مقبولة 4" in seg


def test_a_page_off_the_template_is_named_not_blocked():
    """صورةُ كاميرا أو قصٌّ مختلف: القالبُ لا ينطبق، والقراءةُ لا تعتمد عليه بعد."""
    intake = _intake({}, kinds={2: "unknown"})
    assert plan(intake, skip_rejected=False)["blocked"] is False
    assert "لا يطابق قالبَ الكشف الممسوح: ص2" in summary_ar(intake, [])


def test_a_broken_check_is_a_named_warning_never_a_silent_pass():
    def boom(img):
        raise OSError("unreadable")
    intake = inspect_locally(_images(2), boom, boom)
    assert intake.warned() == [1, 2] and intake.unmatched() == [1, 2]
    assert "تعذّر فحصُ جودتها (OSError)" in summary_ar(intake, [])


# ————————————————————— التطبيق نفسه —————————————————————

def _app_stack() -> bool:
    return all(importlib.util.find_spec(m) is not None
               for m in ("gradio", "pdf2image", "PIL", "langchain"))


@pytest.fixture
def app_run(monkeypatch, tmp_path):
    """`_process_pdf_locked` with every paid call recorded instead of made."""
    if not _app_stack():
        pytest.skip("حزمة التطبيق غير مثبّتة هنا (CI خفيف) — فحص محلي فقط")
    import app
    from statement_qa.footer_oracle import FooterReading

    calls: list[tuple[str, str]] = []
    footers: dict[str, FooterReading] = {}
    verdicts: dict[int, str] = {}

    def probe(img, stats=None):
        calls.append(("bank", img))
        return {"verdict": "rajhi", "bank": None}

    def footer(img, stats=None):
        calls.append(("footer", img))
        return footers[img]

    def rows(img, stats=None, **_):
        calls.append(("rows", img))
        n = len([c for c in calls if c[0] == "rows"])
        return [{"movement": D("1.00"), "balance": D(n), "desc": "حركة", "date": None,
                 "raw_movement": "1.00", "raw_balance": str(n)}]

    def no_network(*a, **k):
        raise AssertionError("استدعاءُ نموذجٍ حقيقيّ في اختبار")

    monkeypatch.setattr(app, "probe_bank", probe)
    monkeypatch.setattr(app, "read_footer", footer)
    monkeypatch.setattr(app, "read_rows_vlm", rows)
    monkeypatch.setattr(app, "page_diverged", lambda *a, **k: False)
    monkeypatch.setattr(app, "recover_anchor", lambda raw, *a, **k: (raw, None))
    import statement_qa.vlm_reader as vr
    monkeypatch.setattr(vr, "chat_vlm_image", no_network)
    monkeypatch.setattr(app, "build_index", lambda chunks: object())
    monkeypatch.setattr(app, "_local_checks",
                        lambda pages: (_gate(verdicts), lambda img: "transactions"))

    def run(cumulative: list[tuple[str, str]], rejected=(), skip=False, via_handler=False):
        pages = _images(len(cumulative))
        for img, (d, c) in zip(pages, cumulative):
            footers[img] = FooterReading(debits=D(d), credits=D(c), balance=None)
        verdicts.clear()
        verdicts.update({p: "reject" for p in rejected})
        monkeypatch.setattr(app, "_pages_to_pngs", lambda _pdf: pages)
        app.STATE.clear()
        app.STATE["store"] = "ملفٌّ سابق"
        if via_handler:        # معالجُ الزرّ نفسه (بقفل التشغيل) — القفلُ في مجلّدٍ مؤقت
            monkeypatch.setattr(app, "LOCK_PATH", tmp_path / "job.lock")
            out = app.process_pdf("upload.pdf", skip, progress=lambda *a, **k: None)
        else:
            out = app._process_pdf_locked("upload.pdf", lambda *a, **k: None, skip)
        return out, calls, pages, app.STATE
    return run


def test_a_blocked_upload_makes_no_paid_call_and_forgets_the_old_file(app_run):
    out, calls, _pages, state = app_run([("10", "0"), ("20", "0"), ("30", "0")],
                                        rejected=[2])
    assert calls == [], "فحصُ ما قبل القراءة يسبق كلَّ استدعاءٍ مدفوع — حتى فحصَ المصرف"
    assert "لم تبدأ القراءة" in out[0]
    assert "store" not in state, "الأسئلةُ لا تُجيب عن ملفٍّ سابق"


def test_pages_are_read_in_their_true_order_and_each_footer_is_paid_once(app_run):
    """الملف: ١، ٣، ٢ بإجمالياتها — تُقرأ ١ ثم ٢ ثم ٣ (بمواضعها: ١، ٣، ٢)."""
    out, calls, pages, _state = app_run([("10", "5"), ("40", "9"), ("25", "7")])
    footer_calls = [img for kind, img in calls if kind == "footer"]
    assert sorted(footer_calls) == sorted(pages), "كلُّ تذييلٍ مرّةً واحدة لا مرّتين"
    assert [img for kind, img in calls if kind == "rows"] == [pages[0], pages[2], pages[1]]
    assert "قُرئت بترتيبها الحقيقي" in out[0]


def test_skipped_pages_are_never_read_and_are_named(app_run):
    out, calls, pages, _state = app_run([("10", "0"), ("20", "0"), ("30", "0")],
                                        rejected=[2], skip=True)
    touched = {img for _kind, img in calls if _kind != "bank"}
    assert pages[1] not in touched
    assert "مستبعدة بلا قراءة 1" in out[0]


def test_the_handler_forwards_the_skip_choice(app_run):
    """الاختبارُ السابق يستدعي الداخلَ مباشرة؛ فتعطيلُ التمرير في المعالج نفسه كان يمرّ (مقيس)."""
    out, calls, pages, _state = app_run([("10", "0"), ("20", "0"), ("30", "0")],
                                        rejected=[2], skip=True, via_handler=True)
    assert pages[1] not in {img for _kind, img in calls if _kind != "bank"}
    assert "مستبعدة بلا قراءة 1" in out[0]


def test_the_read_button_sends_the_skip_checkbox():
    if not _app_stack():
        pytest.skip("حزمة التطبيق غير مثبّتة هنا (CI خفيف) — فحص محلي فقط")
    import app

    fns = app.demo.fns.values() if isinstance(app.demo.fns, dict) else app.demo.fns
    wired = [f for f in fns if getattr(f, "fn", None) is app.process_pdf]
    assert len(wired) == 1
    assert [type(i).__name__ for i in wired[0].inputs] == ["File", "Checkbox"]
