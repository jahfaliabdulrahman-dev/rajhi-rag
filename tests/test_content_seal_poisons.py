"""سمومُ **ختم المحتوى** على أرضيّةٍ صناعيّةٍ صغيرةٍ **مُلتزمة** — لا `skip` في أيّ بيئة.

## العلّةُ التي وُلد هذا الملفُّ لأجلها (القرارُ الثالث · تسليمُ مراجعة ٤٧)

سمومُ الختم كانت كلُّها `@needs_artifacts`: تُقاس على `data/local_sample` المحجوبةِ عن git ⇒ في أيّ
استنساخٍ أو CI **تُتخطّى كلُّها `skip`**، فالرجوعُ عن الإصلاح يمرّ أخضرَ في الآلة الوحيدة التي لا تملك
الأدلّة. وهذه الأرضيّةُ (`tests/fixtures/mini_corpus/`) صناعيّةٌ ومُلتزمةٌ ⇒ السمومُ **تعضّ في كل مكان**.

## والقاعدة ١٣

الأرضيّةُ **ليست من كشف** (أرقامٌ مصنوعة: ١٫٠٠ · ٢٫٠٠ · ٥٫٠٠ · ١٠٫٠٠ … ونصٌّ تجريبيّ)، ويشهد بذلك
حقلُ `synthetic` في `slice_report.json` ويحرسه اختبارٌ هنا — فلا يتسرّب مبلغٌ حقيقيٌّ إلى مستودعٍ عامّ
من هذا الباب.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/mini_corpus"
GENERATOR = ROOT / "tests/fixtures/make_mini_corpus.py"
PAGES = (2, 3, 4)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.pack_io import content_seal, page_content_sha16  # noqa: E402
from tools.eval_pack import seal_findings  # noqa: E402
from tests.fixtures.make_mini_corpus import LONG_TAIL  # noqa: E402


def _fresh(tmp_path: Path) -> Path:
    """نسخةٌ من الأرضيّة في tmp — **والأصلُ لا يُمَسّ** (القاعدةُ في كل سموم هذا المستودع)."""
    d = tmp_path / "mini"
    shutil.copytree(FIXTURE, d)
    return d


def _page_file(run: Path, n: int) -> Path:
    return run / "results" / f"pg-{n:03d}.json"


def _seal(run: Path) -> dict:
    return content_seal(run, PAGES)


def _edit(run: Path, n: int, mutate) -> None:
    f = _page_file(run, n)
    d = json.loads(f.read_text(encoding="utf-8"))
    mutate(d)
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


# ───────────────────────────── الضابطُ الموجب: الأرضيّةُ تشهد لنفسها ─────────────────────────────

def test_the_synthetic_floor_passes_its_own_seal():
    """الضابطُ الموجب: الأرضيّةُ == ختمُها ⇒ لا اعتراض. (وبدونه: كلُّ فشلٍ أدناه قد يكون ضجيجاً.)"""
    live = _seal(FIXTURE)
    assert live["covers"] == len(PAGES) and not live["missing"] and not live["unreadable"]
    findings, detail = seal_findings(live, live, PAGES)
    assert findings == [], findings
    assert detail == {"gaps": [], "mismatched": [], "amounts_moved": []}


def test_the_floor_declares_itself_synthetic_and_carries_no_real_amounts():
    """**حارسُ القاعدة ١٣ على الباب الجديد:** الأرضيّةُ تشهد بأنّها صناعيّة، وأرقامُها من مجموعةٍ
    مُعلَنةٍ صغيرة — فلا يُدسّ كشفٌ حقيقيٌّ في اختبارٍ لاحقٍ باسم «أرضيّة»."""
    rep = json.loads((FIXTURE / "slice_report.json").read_text(encoding="utf-8"))
    assert rep.get("synthetic") is True, "أرضيّةٌ بلا شهادةِ صناعة"
    allowed = {"1.00", "2.00", "3.00", "4.00", "5.00", "6.00", "7.00", "10.00", "11.00", "13.00",
               "14.00", "18.00", "19.00", "25.00"}
    for p in PAGES:
        d = json.loads(_page_file(FIXTURE, p).read_text(encoding="utf-8"))
        for r in d["raw_rows"]:
            for k in ("movement", "balance"):
                if r[k]:
                    assert r[k] in allowed, f"قيمةٌ خارج المجموعة الصناعيّة المُعلَنة: {r[k]}"
        for k in ("debits", "credits", "balance"):
            assert d["footer"][k] in allowed, d["footer"][k]
    assert LONG_TAIL in _page_file(FIXTURE, 2).read_text(encoding="utf-8")


def test_the_committed_floor_matches_its_generator(tmp_path):
    """**الوثيقةُ تُقابَل بمخرَجها:** الأرضيّةُ المُلتزمة يجب أن تساوي ما يُنتجه مولِّدُها الآن —
    وإلا فالأصلُ والمُشتقُّ افترقا (وهو أوّل ما يفسد في الأرضيات الصناعيّة)."""
    r = subprocess.run([sys.executable, str(GENERATOR), "--out", str(tmp_path)],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    made = tmp_path / "mini_corpus"
    for p in PAGES:
        assert (_page_file(made, p).read_bytes() == _page_file(FIXTURE, p).read_bytes()), \
            f"pg-{p:03d} انحرفت عن مولِّدها ⇒ أَعِد التوليدَ والالتزام"
    assert ((made / "slice_report.json").read_bytes()
            == (FIXTURE / "slice_report.json").read_bytes()), "تقريرُ الأرضيّة انحرف عن مولِّده"


# ───────────────────────────── سمومُ المحتوى (طبقات ١ و٣) ─────────────────────────────

def test_editing_a_row_text_is_named(tmp_path):
    run = _fresh(tmp_path)
    frozen = _seal(run)
    _edit(run, 2, lambda d: d["raw_rows"][0].update(desc="قيدٌ تجريبيٌّ معدَّل"))
    findings, detail = seal_findings(_seal(run), frozen, PAGES)
    assert detail["mismatched"] == [2] and any("محتوى مخالف" in f for f in findings), findings


def test_editing_the_tail_beyond_the_old_120_char_cap_is_named(tmp_path):
    """الثقبُ الذي كشفته بوّابةُ التسليم: كان النصُّ يُقطع عند ١٢٠ خانةً **بلا إعلان** ⇒ تعديلُ الذيل
    يمرّ `PASS`. والسمُّ هنا **في الذيل وبنفس الطول** — فلا يمسكه إلا نصٌّ كامل."""
    run = _fresh(tmp_path)
    assert len(LONG_TAIL) > 120, "الأرضيّةُ فقدت النصَّ الطويل ⇒ السمُّ غيرُ قابلٍ للتنفيذ"
    frozen = _seal(run)
    _edit(run, 2, lambda d: d["raw_rows"][1].update(desc=LONG_TAIL[:-1] + "ز"))
    findings, detail = seal_findings(_seal(run), frozen, PAGES)
    assert detail["mismatched"] == [2], detail


def test_deleting_a_page_file_is_named_as_missing(tmp_path):
    run = _fresh(tmp_path)
    frozen = _seal(run)
    _page_file(run, 3).unlink()
    findings, detail = seal_findings(_seal(run), frozen, PAGES)
    assert detail["gaps"] == [3] and any("غائبة" in f for f in findings), findings


def test_a_corrupt_page_is_named_and_never_raises(tmp_path):
    """تلفُ ملفٍّ (كتابةٌ مُنقطِعة) يُسمّى «غيرَ مقروءة» — لا Traceback."""
    run = _fresh(tmp_path)
    frozen = _seal(run)
    _page_file(run, 4).write_text("{ ليس JSON", encoding="utf-8")
    live = _seal(run)                     # لا يرفع
    assert live["unreadable"] == [4] and live["pages"].keys() == {"2", "3"}
    findings, detail = seal_findings(live, frozen, PAGES)
    assert any("غيرُ مقروءة" in f for f in findings), findings


def test_a_missing_or_short_seal_is_named(tmp_path):
    run = _fresh(tmp_path)
    full = _seal(run)
    short = {**full, "pages": {"2": full["pages"]["2"]}, "covers": 1}
    findings, _ = seal_findings(full, short, PAGES)
    assert any("غائبٌ أو ناقصٌ" in f for f in findings), findings
    findings, _ = seal_findings(full, {}, PAGES)
    assert any("غائبٌ أو ناقصٌ" in f for f in findings), findings


# ───────────────────────────── المال: ما يراه الختمُ وما لا يراه ─────────────────────────────

def test_any_content_change_moves_the_published_aggregate(tmp_path):
    """**العددُ المنشورُ صار له قارئ:** أيُّ مسٍّ بمحتوى صفحةٍ يُحرّك المجمَّعةَ الخاليةَ من المال —
    وهي التي تُقابَل في `--build` و`--verify` بالشهادة المُلتزمة."""
    run = _fresh(tmp_path)
    before = _seal(run)["aggregate_sha16"]
    _edit(run, 3, lambda d: d["raw_rows"][0].update(desc="قيدٌ تجريبيٌّ ٣ معدَّل"))
    after = _seal(run)["aggregate_sha16"]
    assert before != after


def test_a_coordinated_amount_pair_moves_only_the_local_money_digest(tmp_path):
    """**حدُّ البصمة المُنشورة:** تعديلُ صفّين بـ+X و−X يُبقي الإسقاطَ الخالي من المال (وبصمتَه
    المنشورة) **كما هو** — ولا تمسكه إلا `sha16_local` **المحلّيّة**. فالمالُ تحرسه بوّاباتُه
    (الهوية/الإطار/العدّاد) وبصمةُ المال، ولا يُنشَر منه شيء (القاعدة ١٣)."""
    run = _fresh(tmp_path)
    frozen = _seal(run)
    live_before = _seal(run)

    def coord(d):
        rs = d["raw_rows"]
        rs[0]["movement"], rs[1]["movement"] = "3.00", "0.00"      # +٢ و−٢ على المجموع نفسه
    _edit(run, 2, coord)
    after = _seal(run)
    assert after["pages"]["2"]["sha16"] == live_before["pages"]["2"]["sha16"], \
        "الإسقاطُ الخالي من المال تحرّك: كان يجب ألا يرى المبالغ"
    assert after["pages"]["2"]["sha16_local"] != live_before["pages"]["2"]["sha16_local"], \
        "بصمةُ المال لم تتحرّك ⇒ هي زينةٌ لا حارس"
    findings, detail = seal_findings(after, frozen, PAGES)
    assert detail["mismatched"] == [] and detail["amounts_moved"] == [2], detail
    assert any("مبالغ" in f for f in findings), findings


def test_the_page_digest_is_deterministic_and_order_independent_of_keys():
    """حتميّةٌ صريحة: نفسُ الصفحة ⇒ نفسُ البصمة، وإعادةُ ترتيبِ المفاتيح لا تُحرّكها."""
    d = json.loads(_page_file(FIXTURE, 2).read_text(encoding="utf-8"))
    reordered = {k: d[k] for k in reversed(list(d))}
    assert page_content_sha16(d) == page_content_sha16(reordered)
    assert page_content_sha16(d) == page_content_sha16(json.loads(json.dumps(d, ensure_ascii=False)))
