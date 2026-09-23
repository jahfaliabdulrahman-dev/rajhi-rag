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


def test_pack_path_is_not_derived_from_file_location():
    """رائحةُ العلّة: المسارُ لا يُبنى من موضع ملفّ الأداة بل من الجذر المشترك."""
    assert pack_io.pack_path() == pack_io.data_root() / "data/eval_pack/pack.json"
    assert pack_io.pack_path() == PACK


# ───────────────── (R45-3) الساحبُ الذي أنفق الحزمة صار يستثنيها ─────────────────

def test_compare_prompts_excludes_pack_pages():
    """الأداةُ التي سحبت عيّنة FM-2 صارت تُسقط صفحاتِ الحزمة — **والدالّةُ نقيّةٌ تُختبَر**."""
    from tools.compare_prompts import excluding_pack
    assert excluding_pack([1, 2, 3, 4], {2, 4}) == [1, 3]
    assert excluding_pack([7, 8], {7, 8}) == []
    assert excluding_pack([5], set()) == [5]
