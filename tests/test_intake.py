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
    knobs = {"printed": {}, "footer_cost": 0.0, "footer_fail": False}

    def probe(img, stats=None):
        calls.append(("bank", img))
        return {"verdict": "rajhi", "bank": None}

    def footer(img, stats=None):
        calls.append(("footer", img))
        if stats is not None:
            stats["cost"] = knobs["footer_cost"]
        if knobs["footer_fail"]:
            raise RuntimeError("VLM network")
        return footers[img]

    def rows(img, stats=None, **_):
        calls.append(("rows", img))
        n = len([c for c in calls if c[0] == "rows"])
        if stats is not None and img in knobs["printed"]:
            stats["page_no"] = knobs["printed"][img]      # الرقمُ المطبوع — الشاهدُ الثاني
        # التاريخُ ليس في خانته بل في نصّ البيان — تستعيده `fill_missing_dates` من البيان القديم
        return [{"movement": D("1.00"), "balance": D(n), "desc": "حركة ٢٠٢٣٠٢٢٥", "date": None,
                 "raw_movement": "1.00", "raw_balance": str(n)}]

    def descriptions(path, next_path, stats):
        calls.append(("desc", path))
        return [f"بيانُ العمود {Path(path).stem}"], False

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
    monkeypatch.setattr(app, "_page_descriptions", descriptions)
    monkeypatch.setattr(app, "_local_checks",
                        lambda pages: (_gate(verdicts), lambda img: "transactions"))

    def run(cumulative: list[tuple[str, str]], rejected=(), skip=False, via_handler=False,
            printed=None, footer_cost=0.0, footer_fail=False):
        pages = _images(len(cumulative))
        knobs.update(printed=dict(zip(pages, printed or [])), footer_cost=footer_cost,
                     footer_fail=footer_fail)
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
    run.calls = calls          # سجلُّ الاستدعاءات يبقى مقروءًا حين يرفع التشغيلُ خطأً
    return run


def test_a_blocked_upload_makes_no_paid_call_and_forgets_the_old_file(app_run):
    out, calls, _pages, state = app_run([("10", "0"), ("20", "0"), ("30", "0")],
                                        rejected=[2])
    assert calls == [], "فحصُ ما قبل القراءة يسبق كلَّ استدعاءٍ مدفوع — حتى فحصَ المصرف"
    assert "لم تبدأ القراءة" in out[0]
    assert "store" not in state, "الأسئلةُ لا تُجيب عن ملفٍّ سابق"


SWAPPED = [("10", "5"), ("40", "9"), ("25", "7")]     # الملف: ١، ٣، ٢ بإجمالياتها


def test_a_witnessed_true_order_is_applied_and_each_footer_is_paid_once(app_run):
    """الرقمُ المطبوع يشهد للتذييلات ⇒ تُعالَج ١ ثم ٢ ثم ٣ (بمواضعها: ١، ٣، ٢)؛ والقراءةُ بترتيب الملف."""
    out, calls, pages, state = app_run(SWAPPED, printed=[1, 3, 2])
    footer_calls = [img for kind, img in calls if kind == "footer"]
    assert sorted(footer_calls) == sorted(pages), "كلُّ تذييلٍ مرّةً واحدة لا مرّتين"
    assert [img for kind, img in calls if kind == "rows"] == pages, "القراءةُ بترتيب الملف"
    assert [r["page"] for r in state["rows"]] == [1, 3, 2], "والمعالجةُ بالترتيب المشهود له"
    assert "عولجت بترتيبها الحقيقي" in out[0]


def test_a_one_digit_footer_misread_keeps_the_file_order(app_run):
    """R70-1: رقمٌ واحدٌ مقروءٌ خطأً في إجمالي مدين ينقل الصفحةَ بعيدًا — ولا شاهدَ ثانٍ يؤيّده."""
    true = [("10", "0"), ("20", "0"), ("30", "0"), ("40", "0"), ("50", "0"), ("60", "0")]
    misread = list(true)
    misread[2] = ("90", "0")                          # ٣٠ ⇒ ٩٠: خانةٌ واحدة
    out, _calls, _pages, state = app_run(misread, printed=[1, 2, 3, 4, 5, 6])
    assert [r["page"] for r in state["rows"]] == [1, 2, 3, 4, 5, 6]
    assert state["order_held"] and "بلا شاهدٍ ثانٍ" in state["order_held"]
    assert "عولجت بترتيب الملف" in out[0]


def test_an_unwitnessed_move_keeps_the_file_order(app_run):
    """التذييلاتُ وحدها تقول ١، ٣، ٢ — بلا رقمٍ مطبوع ولا تجاورٍ مُثبت ⇒ ترتيبُ الملف ويُقال."""
    out, _calls, _pages, state = app_run(SWAPPED)
    assert [r["page"] for r in state["rows"]] == [1, 2, 3]
    assert "عولجت بترتيب الملف" in out[0]


def test_the_footer_pass_stops_at_the_cost_cap(app_run, monkeypatch):
    """R70-2: السقفُ قبل كلّ استدعاء — ولا تُقرأ الصفوف بعده."""
    import gradio as gr

    import app
    monkeypatch.setattr(app, "MAX_UI_COST_USD", 0.025)
    with pytest.raises(gr.Error, match="سقف"):
        app_run([(str(10 * k), "0") for k in range(1, 6)], footer_cost=0.01)
    assert len([c for c in app_run.calls if c[0] == "footer"]) == 3     # ٠ ⇒ ٠٫٠١ ⇒ ٠٫٠٢ ⇒ قف
    assert not [c for c in app_run.calls if c[0] == "rows"]


def test_the_footer_pass_stops_after_five_consecutive_failures(app_run):
    """R70-2: انقطاعُ المزوّد لا يُدفع ثمنُه صفحةً صفحة — خمسُ إخفاقاتٍ متتالية وتقف."""
    import gradio as gr

    with pytest.raises(gr.Error, match="إخفاقات"):
        app_run([(str(10 * k), "0") for k in range(1, 8)], footer_fail=True)
    assert len([c for c in app_run.calls if c[0] == "footer"]) == 5
    assert not [c for c in app_run.calls if c[0] == "rows"]


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


def test_dates_are_settled_from_the_page_reading_before_its_description_is_replaced(app_run):
    """ترتيبٌ مقصود: بيانُ العمود بلا تاريخ، فلو استُبدل البيانُ أوّلًا لضاع التاريخُ المستعاد من نصّه."""
    out, calls, pages, state = app_run(SWAPPED, printed=[1, 3, 2])
    assert [img for kind, img in calls if kind == "desc"] == [pages[0], pages[2], pages[1]]
    for r in state["rows"]:
        assert r["desc"].startswith("بيانُ العمود") and r["desc_source"] == "column"
        assert "٢٠٢٣٠٢٢٥" in r["desc_page"]
        assert r["date"] and r["date_source"] == "recovered-from-description"
    assert "البيانُ من عمود البيان: 3/3 صفحة" in out[0]


def _desc_pass_setup(monkeypatch, fail=()):
    if not _app_stack():
        pytest.skip("حزمة التطبيق غير مثبّتة هنا (CI خفيف) — فحص محلي فقط")
    import app

    seen: list[tuple[str, str | None]] = []

    def descriptions(path, next_path, stats):
        seen.append((path, next_path))
        stats["cost"] = 0.01
        if path in fail:
            raise RuntimeError("VLM JSON")
        return [f"جديد {Path(path).stem}"], next_path is not None
    monkeypatch.setattr(app, "_page_descriptions", descriptions)
    pages = _images(3)
    rows = [{"page": p, "desc": f"قديم {p}"} for p in (1, 2, 3)]
    return app, pages, rows, seen


def test_the_continuation_is_joined_only_across_proven_neighbours(monkeypatch):
    app, pages, rows, seen = _desc_pass_setup(monkeypatch)
    rep = app._desc_pass([1, 3, 2], pages, rows, {(1, 3): "adjacent", (3, 2): "mismatch"},
                         lambda st: None, lambda: False)
    assert seen == [(pages[0], pages[2]), (pages[2], None), (pages[1], None)]
    assert rep["merged"] == [1, 3, 2] and rep["stitched"] == 1


def test_a_failed_page_keeps_its_page_reading_and_is_named(monkeypatch):
    app, pages, rows, _seen = _desc_pass_setup(monkeypatch, fail={_images(3)[1]})
    charged = []
    rep = app._desc_pass([1, 2, 3], pages, rows, {}, charged.append, lambda: False)
    assert rep["failed"] == [2] and rows[1]["desc"] == "قديم 2"
    assert len(charged) == 3, "المحاولةُ الفاشلة تُحتسب كلفتُها أيضًا"


def test_the_description_pass_stops_at_the_cost_cap(monkeypatch):
    app, pages, rows, seen = _desc_pass_setup(monkeypatch)
    spent = []
    rep = app._desc_pass([1, 2, 3], pages, rows, {}, spent.append, lambda: len(spent) >= 1)
    assert len(seen) == 1 and rep["skipped"] == [2, 3]
    assert rows[1]["desc"] == "قديم 2"
