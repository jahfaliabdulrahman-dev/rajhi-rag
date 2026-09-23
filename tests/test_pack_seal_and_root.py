"""ختمُ الحزمة صار له قارئ · والحمايةُ صارت ترى من شجرةِ عملٍ منفصلة · والفرعُ يُختبَر مباشرةً.

المراجعةُ ٤٥ أثبتت ثلاثةَ أعطابٍ بتخريباتٍ فعليّة (لا بالقراءة)، وهذه اختباراتُها الدائمة:

  ١) **R45-1 — الختمُ بلا قارئ:** `--verify` كان يطبع «بصمة ✗» ثم يحكم `PASS` بـ`rc=0`، لأنّ الحكمَ
     كان يُبنى من التقاطع والحجم وحدَهما. والتخريباتُ الثلاثةُ صارت هنا **اختباراتٍ تسقط إن عاد**.
  ٢) **R45-2 — الحمايةُ عمياءُ في شجرةِ عملٍ منفصلة (worktree):** مسارُ الحزمة كان من `__file__`،
     و`data/` ليس في git ⇒ «لا حزمةَ معلَنة» ⇒ لا استثناء، و`rc=0`، وصفحاتُ الحزمة تعود للتدريب.
     والحلُّ: `pack_io.data_root` يُحلّ بـ`git-common-dir` ⇒ كلُّ الشجراتِ ترى `data/` الأمَّ.
  ٣) **الضابطُ الموجب كان ينجح كذباً:** حذفُ فرع الاستثناء من الكود يُبقي الاختباراتِ خضراء
     (قِيس: 17 passed). والعلاج: القرارُ صار دالّةً نقيّةً (`classify_page`) يمسّها الاختبارُ مباشرةً.

**وحدُّ هذه الاختبارات:** تقيس القرارَ والحكمَ والختم — لا دقّةَ الأرقام الماليّة (تلك مقاييسُ الحزمة).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import pack_io  # noqa: E402
from tools.capture_training import classify_page  # noqa: E402

PACK = pack_io.pack_path()
RUN = pack_io.data_root() / "data/local_sample/slice_629p"
needs_artifacts = pytest.mark.skipif(not PACK.exists(), reason="الأدلّةُ الثقيلةُ خارج git (مقصود)")


def _verify(pack_file: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/eval_pack.py", "--verify", "--pack", str(pack_file)],
        cwd=ROOT, capture_output=True, text=True)


# ─────────────────────────── (٣) الفرعُ يُختبَر مباشرةً ───────────────────────────

def test_classify_page_precedence_is_declared():
    """حجزُ القسمة أوّلًا، ثم الحزمة — **فإن حُذف فرعُ الحزمة سقط هذا الاختبار**."""
    assert classify_page(9, 3, {9, 10}) == "holdout_reserved"   # القسمةُ تسبق
    assert classify_page(10, 3, {10}) == "pack_reserved"        # صفحةُ الحزمة
    assert classify_page(11, 3, {10}) == "capture"              # لا حجزَ ⇒ تُلتقط


def test_classify_page_never_captures_a_pack_page():
    """لا صفحةَ حزمةٍ تُصنَّف «تُلتقط» — على أيّ معاملِ قسمة."""
    reserved = {p for p in range(0, 60, 7)}
    for mod in (1, 2, 3, 5, 10):
        for p in reserved:
            assert classify_page(p, mod, reserved) != "capture"


# ─────────────────────────── (١) التخريبات الثلاثة تسقط ───────────────────────────

@needs_artifacts
def test_corrupt_census_list_fails_verify(tmp_path):
    """تخريبٌ ١: قائمةُ الإحصاء تُعدَّل وبصمتُها تبقى ⇒ كان PASS·rc=0."""
    d = json.loads(PACK.read_text(encoding="utf-8"))
    c = d["census"]["pages"]
    c[0], c[1] = c[1], c[0]
    f = tmp_path / "pack.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    r = _verify(f)
    assert r.returncode != 0, "قائمةُ إحصاءٍ مُعدَّلةٌ مرّت — الختمُ بلا قارئ"
    assert "بصمةُ الإحصاء" in r.stdout


@needs_artifacts
def test_corrupt_range_numbers_fail_verify(tmp_path):
    """تخريبٌ ٢: رقمٌ في مدًى لا يطابق إعادةَ القياس ⇒ كان يُطبع «مخالفة ✗» ثم PASS."""
    d = json.loads(PACK.read_text(encoding="utf-8"))
    d["ranges"][0]["movements"] = int(d["ranges"][0]["movements"]) + 1
    f = tmp_path / "pack.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    r = _verify(f)
    assert r.returncode != 0
    assert "إعادةُ قياس المديات" in r.stdout or "مخالفة" in r.stdout


@needs_artifacts
def test_dropped_census_row_fails_verify(tmp_path):
    """تخريبٌ ٣: صفٌّ يُحذف من الإحصاء ⇒ كان لا يُطبع شيءٌ ويحكم PASS."""
    d = json.loads(PACK.read_text(encoding="utf-8"))
    d["census"]["pages"] = d["census"]["pages"][1:]
    f = tmp_path / "pack.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    r = _verify(f)
    assert r.returncode != 0
    both = r.stdout + r.stderr      # الفشلُ المغلَق يُعلن على stderr (SystemExit)
    assert "ناقصة" in both or "بصمةُ الإحصاء" in both


@needs_artifacts
def test_verify_passes_on_the_real_pack():
    """**الضابطُ الأوّل**: الحزمةُ الحقيقيّةُ تمرّ ⇒ ليست الاختباراتُ تسقط على كل حال."""
    r = _verify(PACK)
    assert r.returncode == 0, r.stdout[-400:]
    assert "PASS" in r.stdout


# ─────────────────────────── (١ب) الختمُ له قارئٌ مُسمّى ───────────────────────────

@needs_artifacts
def test_seal_has_a_reader_and_names_the_committed_file():
    s = pack_io.seal()
    assert s and s.get("sha256") and s.get("count"), "لا شهادةَ مُلتزمةٌ تُقرأ"
    facts = pack_io.pack_facts(PACK)
    assert pack_io.seal_violation(facts) is None, "الحزمةُ الحيّةُ تخالف ختمَها المُلتزم"


def test_seal_violation_speaks_when_the_pack_moves(tmp_path):
    """حزمةٌ تتغيّر بعد الختم ⇒ رسالةٌ مُسمّاة (لا صمتٌ ولا `True`)."""
    if not pack_io.evidence_path():
        pytest.skip("لا شهادةَ مُلتزمة في هذه النسخة")
    fake = {"pages": {1, 2, 3}, "identity": "x", "declared": 3, "fingerprint": "f",
            "file": "fake", "expect_identity": None}
    msg = pack_io.seal_violation(fake)
    assert msg and ("لا يطابق" in msg or "لا شهادة" in msg)


# ─────────────────────────── (٢) الجذرُ يُحلّ من worktree ───────────────────────────

def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def test_data_root_resolves_from_a_worktree(tmp_path):
    """**جوهرُ R45-2:** من شجرةِ عملٍ منفصلة، جذرُ البيانات = الشجرةُ الأمّ لا الشجرةُ المنفصلة."""
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", cwd=main)
    _git("config", "user.email", "t@t", cwd=main)
    _git("config", "user.name", "t", cwd=main)
    (main / "f.txt").write_text("x", encoding="utf-8")
    _git("add", "-A", cwd=main)
    _git("commit", "-q", "-m", "init", cwd=main)
    wt = tmp_path / "wt"
    _git("worktree", "add", "-q", str(wt), cwd=main)
    (wt / "data").mkdir(exist_ok=True)          # شجرةُ العمل لها مجلدها الفارغ — وهذا مصدرُ العمى
    assert pack_io.repo_root(wt) == wt.resolve(), "الجذرُ الحاليُّ يجب أن يكون الشجرةَ المنفصلة"
    assert pack_io.data_root(wt) == main.resolve(), "جذرُ البيانات يجب أن يكون الشجرةَ الأمّ"


def test_documented_capture_from_a_worktree_announces_the_pack(tmp_path):
    """**يقيس الأمرَ نفسَه لا إعادةَ كتابة المنطق** (S-6 · STR-4): من شجرة عملٍ منفصلة
    (لا `data/` فيها) يشغّل الأمرَ الموثَّق ويقرأ ما طبعه — وهو ما كان يسقط قبل الإصلاح."""
    if not PACK.exists():
        pytest.skip("الأدلّةُ الثقيلةُ خارج git (مقصود)")
    wt = tmp_path / "wt"
    subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "-q", "--detach", str(wt), "HEAD"],
                   check=True, capture_output=True)
    try:
        r = subprocess.run([sys.executable, "tools/capture_training.py",
                            "--run", "data/local_sample/slice_629p",
                            "--export", "data/local_sample/export-629p.xlsx",
                            "--out", str(tmp_path / "out"), "--limit", "2"],
                           cwd=wt, capture_output=True, text=True)
        both = r.stdout + r.stderr
        assert "الحزمةُ المجمّدة" in both and "مستثناة" in both, both[-500:]
        assert r.returncode == 0, both[-500:]
    finally:
        subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(wt)], capture_output=True)


def test_amount_guard_pre_push_checks_bite_on_a_stale_manifest(tmp_path, monkeypatch):
    """**سمُّ حارس المبالغ** (S-3): الفحصان نُقلا إلى مسار الخطّاف — ومانيفستٌ متعفّنٌ يجب أن يسقطهما."""
    from tools import amount_guard as ag
    if not PACK.exists():
        pytest.skip("الأدلّةُ الثقيلةُ خارج git (مقصود)")
    # **الصنفُ الصحيحُ من العطب**: مانيفستٌ **صحيحُ الشكل** يقول عدداً غيرَ عددِ المصدر ⇒ تعفّن.
    mf = tmp_path / "amount-manifest.json"
    mf.write_text(json.dumps({"derivation": {"source_shape_ok": 10 ** 9},
                              "fingerprints": ["0" * 64], "set_digest": "0" * 64}),
                  encoding="utf-8")
    monkeypatch.setattr(ag, "MANIFEST", mf)
    assert ag.pre_push_checks() == 1, "مانيفستٌ متعفّنٌ مرّ من فحص ما قبل الدفع ⇒ الحارسُ لا يعضّ"
    monkeypatch.setattr(ag, "MANIFEST", tmp_path / "absent.json")
    assert ag.pre_push_checks() == 0, "غيابُ المانيفست = «سطحٌ بلا أدلّة» لا تعفّن — يُعلن في مسارٍ آخر"


def test_oracle_confirm_refuses_to_spend_on_pack_pages(tmp_path):
    """**الشاهدُ المدفوع** (F2): إحصاءُ الحزمة مصدرُه الافتراضيّ ⇒ يقف مُعلَنًا بلا عَلَمٍ صريح."""
    if not PACK.exists():
        pytest.skip("الأدلّةُ الثخينةُ خارج git (مقصود)")
    r = subprocess.run([sys.executable, "tools/oracle_confirm.py", "--dry-run", "--max-usd", "0"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0, "شاهدٌ مدفوعٌ سحب إحصاءَ الحزمة بلا وقف"
    assert "حزمة التقييم المجمّدة" in (r.stdout + r.stderr)


# ───────────────── (R45-3) الساحبُ الذي أنفق الحزمة صار يستثنيها ─────────────────

def test_compare_prompts_excludes_pack_pages():
    """الأداةُ التي سحبت عيّنة FM-2 صارت تُسقط صفحاتِ الحزمة — **والدالّةُ نقيّةٌ تُختبَر**."""
    from tools.compare_prompts import excluding_pack
    assert excluding_pack([1, 2, 3, 4], {2, 4}) == [1, 3]
    assert excluding_pack([7, 8], {7, 8}) == []
    assert excluding_pack([5], set()) == [5]


# ───────────────── قرارُ المالك (أ): إعلانُ انحيازٍ مؤرَّخ + عمودُ المقياسين ─────────────────

@needs_artifacts
def test_bias_declaration_is_committed_and_has_a_reader():
    """**الإعلانُ يُقاس ولا يُمحى**: يُلتزم في الشهادة، **ويُعاد حسابُه حيًّا فيُقابَل** ⇒ تعفّنٌ يسقط."""
    from tools import pack_evidence  # noqa: E402
    ev = pack_io.evidence_path()
    assert ev, "لا شهادةَ مُلتزمة"
    b = json.loads(ev.read_text(encoding="utf-8")).get("bias_declaration")
    assert b, "الشهادةُ بلا إعلانِ انحياز — وهذا نقضُ قرار المالك (أ)"
    m = b["metrics"]
    assert b["measured_pages_outside_pack"] == 282
    assert (m["chain_unproven_rows"]["v1"], m["chain_unproven_rows"]["v2"]) == (34, 14)
    assert m["chain_unproven_rows"]["better"] == "v2", "المقياسُ الذي مُنح v2 يجب أن يُعلَن"
    assert m["missing_pairs"]["better"] == "v1" and m["row_count_deviation"]["better"] == "v1", \
        "المقياسان اللذان يرجّحان v1 يجب أن يبقيا معلنين (وإلا صار الإعلانُ دعاية)"
    # **ولكلّ صفٍّ رقمُه ومقياسُه**: كانت هذه الأرقامُ غيرَ مثبَّتة فمرّ خطأُ نقلٍ بين صفَّين.
    assert (m["pages_won"]["v1"], m["pages_won"]["v2"]) == (5, 9), "تفوّقُ مقياس **السلسلة**"
    assert (m["pages_won_pairs"]["v1"], m["pages_won_pairs"]["v2"]) == (9, 15), "تفوّقُ مقياس **الأزواج** (لا يُنقل رقمٌ بين الصفَّين)"
    assert m["pages_won"]["better"] == "v2" and m["pages_won_pairs"]["better"] == "v2", \
        "في مقاييس التفوّق **الأكثرُ أفضل** (والاتجاهُ يُميَّز عن مقاييس الكلفة)"
    assert (m["missing_pairs"]["v1"], m["missing_pairs"]["v2"]) == (28, 32)
    assert (m["row_count_deviation"]["v1"], m["row_count_deviation"]["v2"]) == (0, 18)
    assert b["arms"]["v1"]["sha256"] and b["arms"]["v2"]["sha256"], "الإعلانُ غيرُ مقيَّد بملفَّي الذراعين"
    live = pack_evidence.bias_metrics(set(pack_io.pack_facts(pack_io.pack_path())["pages"]))
    assert live == b, "الإعلانُ تعفّن: الحسابُ الحيّ خالف المُلتزم — أعِد التوليد بـ`tools/pack_evidence.py`"


def test_close_out_dir_removes_what_the_run_did_not_capture(tmp_path):
    """**سمُّ R45-4**: البيانُ يقول «محجوزة» والقرصُ يجب أن يطابق البيان — لا أن يحمل فضلة."""
    from tools.capture_training import close_out_dir
    doc = tmp_path / "3e2d360a665c88aa"
    doc.mkdir()
    for n in (2, 4, 5, 9):
        (doc / f"pg-{n:03d}").mkdir()
        (doc / f"pg-{n:03d}" / "page.png").write_bytes(b"x")
    removed = close_out_dir(doc, {4, 5})
    assert removed == [2, 9], "الفضلةُ لم تُغلق"
    assert sorted(d.name for d in doc.glob("pg-*")) == ["pg-004", "pg-005"], "الصفحاتُ المُلتقَطة مُسحت"
