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

import hashlib
import json
import shutil
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
def test_dropped_element_from_the_PACK_LIST_fails_verify(tmp_path):
    """تخريبٌ ٣ (مراجعة ٤٥): عنصرٌ يُحذف من **قائمة الحزمة** ⇒ كان لا يُطبع شيءٌ ويحكم PASS.

    **واسمُه صُحِّح في مراجعة ٤٧**: كان اسمه «صفٌّ يُحذف» وهو يُسقط **عنصرَ قائمة** (عضويّةً)،
    فمرّ `PASS` على حذف صفٍّ من **محتوى** صفحة إحصاء (سمٌّ وكيل). فالعضويّةُ هنا، والمحتوى في
    الاختبارات التالية — ولا يُسمّى اختبارٌ بما لا يقيسه.
    """
    d = json.loads(PACK.read_text(encoding="utf-8"))
    d["census"]["pages"] = d["census"]["pages"][1:]
    f = tmp_path / "pack.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    r = _verify(f)
    assert r.returncode != 0
    both = r.stdout + r.stderr      # الفشلُ المُغلَق يُعلن على stderr (SystemExit)
    assert "ناقصة" in both or "بصمةُ الإحصاء" in both


# ─────────────── (R47-2) ختمُ المحتوى: صفحةٌ تُمسّ ⇒ يسقط، لا العضويّةُ وحدها ───────────────

def _tampered_run(tmp_path: Path, poison) -> Path:
    """نسخةٌ من التشغيلة وحدها (التقريرُ + نتائجُ الصفحات) يمسّها السمُّ — **الشجرةُ لا تُلمس**.

    (وهذا هو شكلُ القياس الذي كشف العلّة: تخريبٌ على نسخة، ثم الأمرُ الموثَّق نفسُه.)
    """
    run = pack_io.data_root() / "data/local_sample/slice_629p"
    dst = tmp_path / "run"
    (dst / "results").mkdir(parents=True)
    shutil.copy2(run / "slice_report.json", dst / "slice_report.json")
    for f in (run / "results").glob("pg-*.json"):
        shutil.copy2(f, dst / "results" / f.name)
    poison(dst)
    return dst


def _verify_on(run: Path, pack: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/eval_pack.py", "--verify", "--run", str(run), "--pack", str(pack)],
        cwd=ROOT, capture_output=True, text=True)


def _pack_copy(tmp_path: Path) -> Path:
    f = tmp_path / "pack.json"
    shutil.copy2(PACK, f)
    return f


def _page_file(run: Path, n: int) -> Path:
    return run / "results" / f"pg-{n:03d}.json"


def _census_first() -> int:
    return int(json.loads(PACK.read_text(encoding="utf-8"))["census"]["pages"][0]["page"])


@needs_artifacts
def test_a_deleted_census_row_in_the_CORPUS_fails_verify(tmp_path):
    """**R47-2 الأساس:** حذفُ صفٍّ من **محتوى** صفحة إحصاء ⇒ كان `PASS rc=0` (قِيس في ٤٧)."""
    n = _census_first()

    def poison(run: Path) -> None:
        f = _page_file(run, n)
        d = json.loads(f.read_text(encoding="utf-8"))
        d["raw_rows"] = (d.get("raw_rows") or [])[1:]
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    r = _verify_on(_tampered_run(tmp_path, poison), _pack_copy(tmp_path))
    assert r.returncode != 0, "محتوى صفحةٍ مُمسَّة مرّ — الختمُ لا يربط المحتوى"
    assert f"[{n}]" in r.stdout or "محتوى مخالف" in r.stdout or "لا يُقفل" in r.stdout, r.stdout[-500:]


@needs_artifacts
def test_an_edited_text_in_the_corpus_fails_verify(tmp_path):
    """تعديلُ **نصّ** (لا مال) ⇒ يسقط بالختم. **وحدُّ الضبط مقيس:** أوّلُ إسقاطٍ قرأ `descr`
    ومفتاحُ الكوربوس `desc` ⇒ مرّ السمُّ؛ فالإسقاطُ يسمّي مفاتيحَه من الشكل المُعلن."""
    n = _census_first()

    def poison(run: Path) -> None:
        f = _page_file(run, n)
        d = json.loads(f.read_text(encoding="utf-8"))
        for row in d.get("raw_rows") or []:
            if row.get("desc"):
                row["desc"] = str(row["desc"]) + "ت"
                break
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    r = _verify_on(_tampered_run(tmp_path, poison), _pack_copy(tmp_path))
    assert r.returncode != 0, "نصٌّ مُعدَّل مرّ — الإسقاطُ لا يحمل النصّ"


@needs_artifacts
def test_a_deleted_results_file_fails_verify_by_name(tmp_path):
    """حذفُ ملفّ نتيجة صفحةٍ **مقيَّدة** ⇒ «صفحاتٌ غائبةٌ من التشغيلة» (لا صمتٌ ولا انفجار)."""
    n = _census_first()
    r = _verify_on(_tampered_run(tmp_path, lambda run: _page_file(run, n).unlink()), _pack_copy(tmp_path))
    assert r.returncode != 0
    assert "غائبة" in r.stdout, r.stdout[-500:]


@needs_artifacts
def test_a_coordinated_amount_pair_fails_only_the_local_money_digest(tmp_path):
    """**أقوى قياسٍ في هذه الجولة:** تعديلُ صفّين على **الجهة نفسها** بـ+X و−X ⇒ لا تتغيّر Σ ولا
    الإطارُ ولا الهوية ⇒ بوّاباتُ المال **عمياء**، والإسقاطُ الخالي من المال (القاعدة ١٣) أعمى أيضاً.
    فالذي يمسكه هو **بصمةُ المال المحلّيّة** وحدَها — فتُثبت أنّها ليست زينة.
    """
    n = _census_first()

    def poison(run: Path) -> None:
        from decimal import Decimal
        f = _page_file(run, n)
        d = json.loads(f.read_text(encoding="utf-8"))
        rows, prev, same = d.get("raw_rows") or [], None, {}
        for i, row in enumerate(rows):
            if not row.get("movement"):
                if row.get("balance"):
                    prev = Decimal(str(row["balance"]))
                continue
            cur = Decimal(str(row["balance"])) if row.get("balance") else None
            side = "debit" if (prev is None or cur is None or cur < prev) else "credit"
            same.setdefault(side, []).append(i)
            if cur is not None:
                prev = cur
        pair = next((v for v in same.values() if len(v) >= 2), [])
        assert len(pair) >= 2, "الصفحةُ المُختارة لا تحمل صفّين على جهةٍ واحدة"
        rows[pair[0]]["movement"] = str(Decimal(str(rows[pair[0]]["movement"])) + 10)
        rows[pair[1]]["movement"] = str(Decimal(str(rows[pair[1]]["movement"])) - 10)
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    r = _verify_on(_tampered_run(tmp_path, poison), _pack_copy(tmp_path))
    out = r.stdout + r.stderr
    verdict = next((ln for ln in r.stdout.splitlines() if ln.startswith("الحكم:")), "")
    assert r.returncode != 0
    assert "قيمُ مبالغ تحرّكت" in verdict, out[-500:]
    # **والقياسُ يخصّ بصمةَ المال وحدَها**: لو أسقطته بوّاباتُ المال لَظهرت أسماؤها في الحكم
    assert "إعادةُ قياس المديات" not in verdict and "لم تُعد تُقفل" not in verdict, verdict


@needs_artifacts
def test_the_real_pack_passes_the_content_seal(tmp_path):
    """**الضابطُ الموجب:** الحزمةُ الحقيقيّةُ على القرص الحقيقيّ تمرّ ⇒ ليست السمومُ تسقط دائماً."""
    r = subprocess.run([sys.executable, "tools/eval_pack.py", "--verify"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-600:]
    assert "ختمُ المحتوى" in r.stdout and "PASS" in r.stdout


@needs_artifacts
def test_the_content_seal_covers_every_pack_page_and_excludes_amounts():
    """الختمُ يغطّي **كلَّ** صفحةٍ مقيَّدة، وحدُّه مُعلَن: لا قيمةَ مبلغٍ في الإسقاط المنشور."""
    from tools import pack_io as io
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    pages = {str(p) for p in io.pack_pages(PACK)}
    live = io.content_seal(io.data_root() / "data/local_sample/slice_629p", io.pack_pages(PACK))
    assert set(live["pages"]) == pages, "ختمُ المحتوى لا يغطّي كلَّ صفحات الحزمة"
    assert not live["missing"] and not live["unreadable"]
    assert live["aggregate_sha16"] == pack["page_seal"]["aggregate_sha16"], \
        "البصمةُ المجمَّعة الحيّة تخالف المُلتزمة في الحزمة (تعفّن) ⇒ أَعِد البناء"
    assert "بلا قيمِ مبالغ" in pack["page_seal"]["schema"]
    # **وحدُّ النشر:** المجمَّعةُ من الخالي من المال؛ وبصمةُ المال (`sha16_local`) **محلّيّة**.
    money_free = hashlib.sha256(json.dumps(
        {k: v["sha16"] for k, v in live["pages"].items()}, sort_keys=True,
        ensure_ascii=False).encode()).hexdigest()[:16]
    assert money_free == live["aggregate_sha16"]
    assert json.dumps(io.page_projection(json.loads(
        (io.data_root() / "data/local_sample/slice_629p/results/pg-002.json").read_text(encoding="utf-8")))) \
        .find("movement") == -1, "الإسقاطُ المنشور يحمل مفتاحَ مبلغ"


@needs_artifacts
def test_the_committed_evidence_carries_the_content_seal_aggregate():
    """الشهادةُ المُلتزمة تحمل البصمةَ المجمَّعة ⇒ الختمُ له مرساةٌ في مستندٍ مُتتبَّع (لا محلّيّاً فقط)."""
    ev = pack_io.evidence_path()
    assert ev, "لا شهادةَ مُلتزمة"
    ps = (json.loads(ev.read_text(encoding="utf-8")).get("pack") or {}).get("page_seal") or {}
    live = pack_io.content_seal(pack_io.data_root() / "data/local_sample/slice_629p",
                                pack_io.pack_pages(PACK))
    assert ps.get("aggregate_sha16") == live["aggregate_sha16"], \
        "الشهادةُ المُلتزمة تحمل بصمةَ محتوىً أخرى ⇒ أَعِد `tools/pack_evidence.py`"
    assert ps.get("covers") == live["covers"] and "بلا قيمِ مبالغ" in (ps.get("policy") or "")


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


def test_close_out_dir_removes_only_what_was_asked_and_reports_what_it_measured(tmp_path):
    """**سمُّ R45-4 — بعد إصلاح R47-1:** الإزالةُ **بمجموعةٍ صريحة** طلبها المُستدعي، لا «كلُّ ما لم
    يُلتقط هذه المرّة» (وذاك كان يحذف بياناتٍ حقيقيّة عند تغيُّر `--holdout-mod`: قِيس ٢٨٣→٠)."""
    from tools.capture_training import close_out_dir
    doc = tmp_path / "3e2d360a665c88aa"
    doc.mkdir()
    for n in (2, 4, 5, 9):
        (doc / f"pg-{n:03d}").mkdir()
        (doc / f"pg-{n:03d}" / "page.png").write_bytes(b"x")
    assert close_out_dir(doc, set()) == ([], []), "طلبٌ فارغٌ لا يحذف شيئاً"
    assert sorted(d.name for d in doc.glob("pg-*")) == ["pg-002", "pg-004", "pg-005", "pg-009"]
    removed, failed = close_out_dir(doc, {4, 5})
    assert (removed, failed) == ([4, 5], []), "الإزالةُ لم تُقَس على القرص"
    assert sorted(d.name for d in doc.glob("pg-*")) == ["pg-002", "pg-009"], \
        "حُذف ما لم يُطلب — وهذا هو العطبُ الأصليّ"


def test_close_out_dir_names_a_removal_that_failed_instead_of_announcing_it(tmp_path):
    """`ignore_errors=True` كان **يُعلن ما لم يقع** (قِيس: أُعلنت `[3]` وبقي `pg-003`)."""
    import os
    from tools.capture_training import close_out_dir
    doc = tmp_path / "doc"
    (doc / "pg-003").mkdir(parents=True)
    (doc / "pg-003" / "page.png").write_bytes(b"x")
    os.chmod(doc / "pg-003" / "page.png", 0o444)
    os.chmod(doc / "pg-003", 0o555)
    try:
        removed, failed = close_out_dir(doc, {3})
        assert (removed, failed) == ([], [3]), "الفشلُ لم يُسمَّ — الإعلانُ صار كذباً"
    finally:
        os.chmod(doc / "pg-003", 0o755)
        os.chmod(doc / "pg-003" / "page.png", 0o644)


# ───────────────── (R47-1) بوّابةُ الإغلاق: شرطٌ يُسمّى ولا يُحذف معه شيء ─────────────────

def _prev_manifest(mod=3, version="1", export="abc123", pack_id="3e2d360a665c88aa", pack_pages=200):
    return {"holdout_rule": f"page % {mod} == 0 ⇒ لا تُلتقط (حجز التقييم)",
            "capture_version": version, "label_source": {"export_sha256": export},
            "pack_exclusion": {"identity": pack_id, "excluded_pages": pack_pages}}


NOW = {"holdout_mod": 3, "capture_version": "1", "export_sha256": "abc123",
       "pack_identity": "3e2d360a665c88aa", "pack_pages": 200}


def test_close_authority_accepts_the_same_rule_the_same_source_and_the_same_pack():
    """**الضابطُ الموجب:** تشغيلةٌ بقاعدةٍ ومصدرٍ وحزمةٍ نفسِها ⇒ لا اعتراض (والبوّابةُ تُغلق)."""
    from tools.capture_training import close_authority
    assert close_authority(is_full_run=True, now=NOW, prev=_prev_manifest(), disk_missing=False) == []


def test_close_authority_refuses_a_holdout_rule_swap():
    """`--holdout-mod 2` على قرصٍ بُني بـ3: أيُّ إغلاقٍ هنا يمحو ١٤٠ صفحةً مُلتقَطة (قِيس)."""
    from tools.capture_training import close_authority
    why = close_authority(is_full_run=True, now={**NOW, "holdout_mod": 2},
                          prev=_prev_manifest(), disk_missing=False)
    assert any("قاعدةُ الحجز تبدّلت" in w for w in why), why


def test_close_authority_refuses_a_changed_export_or_pack_or_capture_version():
    from tools.capture_training import close_authority
    for key, val, needle in (("export_sha256", "other", "مصدرُ الوسم"),
                             ("capture_version", "2", "نسخةُ الالتقاط"),
                             ("pack_pages", 199, "الحزمةُ تبدّلت"),
                             ("pack_identity", "0" * 16, "الحزمةُ تبدّلت")):
        why = close_authority(is_full_run=True, now={**NOW, key: val},
                              prev=_prev_manifest(), disk_missing=False)
        assert any(needle in w for w in why), (key, why)


def test_close_authority_refuses_an_undeclared_disk_and_a_partial_run():
    from tools.capture_training import close_authority
    assert any("ولا بيانَ سابقاً" in w for w in
               close_authority(is_full_run=True, now=NOW, prev=None, disk_missing=False))
    assert close_authority(is_full_run=True, now=NOW, prev=None, disk_missing=True) == [], \
        "قرصٌ فارغٌ بلا بيان = حالةُ أول تشغيلةٍ لا اعتراض فيها"
    assert any("جزئيّة" in w for w in
               close_authority(is_full_run=False, now=NOW, prev=_prev_manifest(), disk_missing=False))


def test_prev_rule_is_read_from_the_string_the_tool_itself_wrote():
    """البيانُ على القرص اليومَ **بصيغةٍ سبقت الحقل الآليّ** ⇒ تُقرأ القاعدةُ من النصّ الذي كتبته
    الأداةُ نفسُها (لا تخمينٌ ولا وقوفٌ كاذب)."""
    from tools.capture_training import _prev_holdout_mod
    assert _prev_holdout_mod({"holdout_rule": "page % 3 == 0 ⇒ لا تُلتقط (حجز التقييم)"}) == 3
    assert _prev_holdout_mod({"holdout_mod": 7, "holdout_rule": "page % 3 == 0"}) == 7
    assert _prev_holdout_mod({"holdout_rule": "قاعدةٌ بلا صيغة"}) is None
    assert _prev_holdout_mod(None) is None


@needs_artifacts
def test_the_documented_capture_refuses_a_holdout_swap_and_touches_nothing(tmp_path):
    """**الأمرُ الموثَّق نفسُه** (`--out data/training --holdout-mod 2`) على **نسخة**: يقف بـ`rc=1`
    ويُعلن الثمنَ، **ولا يُحذف ولا يُكتب** شيء — البوّابةُ تسبق الالتقاط لا تلحقه."""
    import shutil as _sh
    from tools.capture_training import on_disk_pages
    src = pack_io.data_root() / "data/training"
    ident = str(pack_io.pack_facts(PACK).get("identity") or "")
    man = src / ident / "manifest.json"
    if not man.exists():
        pytest.skip("لا بيانَ التقاطٍ للحزمة على هذا القرص")
    doc_id = str(json.loads(man.read_text(encoding="utf-8")).get("doc_id"))
    if not (src / doc_id).is_dir():
        pytest.skip("لا التقاطَ على هذا القرص")
    out = tmp_path / "training"
    _sh.copytree(src, out)
    before = on_disk_pages(out / doc_id)
    r = subprocess.run([sys.executable, "tools/capture_training.py",
                        "--run", "data/local_sample/slice_629p",
                        "--export", "data/local_sample/export-629p.xlsx",
                        "--out", str(out), "--holdout-mod", "2"], cwd=ROOT, capture_output=True, text=True)
    after = on_disk_pages(out / doc_id)
    both = r.stdout + r.stderr
    assert r.returncode == 1, f"لم يقف: {both[-400:]}"
    assert "موقوفٌ بالاسم" in both and "قاعدةُ الحجز تبدّلت" in both, both[-600:]
    assert before == after, "التشغيلةُ المرفوضةُ غيّرت القرص"


def test_data_root_refuses_to_guess_and_never_loses_the_pack_silently(tmp_path):
    """**باقيةُ مراجعة ٤٧.** بلا git كان التخمينُ يُرجع مجلدَ الأداة `tools/` ⇒ الحزمةُ تختفي
    **صامتةً** (قِيس عند المدقّق: تقاطعٌ ٣ من ٤ مع `rc=0` أي صفحاتٍ مقيَّدةٍ تعود للتدريب).

    والقاعدةُ الآن: `RAJHI_DATA_ROOT` الصريحُ يسبق · ثم git · ثم **استثناءةٌ بالاسم** — لا جذرٌ مخمَّن.
    """
    import os
    from tools.pack_io import data_root
    bare = tmp_path / "no_git"
    bare.mkdir()
    old_root = os.environ.pop("RAJHI_DATA_ROOT", None)
    old_ceil = os.environ.get("GIT_CEILING_DIRECTORIES")
    os.environ["GIT_CEILING_DIRECTORIES"] = str(tmp_path)   # لا يصعد السؤالُ إلى مستودعٍ أعلى
    try:
        with pytest.raises(RuntimeError) as e:
            data_root(start=bare)
        assert "مجهول" in str(e.value) and "RAJHI_DATA_ROOT" in str(e.value), str(e.value)
        os.environ["RAJHI_DATA_ROOT"] = str(tmp_path / "shared")
        assert data_root(start=bare) == (tmp_path / "shared").resolve(), \
            "المخرجُ الصريحُ يجب أن يُحترم بلا git"
    finally:
        os.environ.pop("RAJHI_DATA_ROOT", None)
        if old_root:
            os.environ["RAJHI_DATA_ROOT"] = old_root
        if old_ceil is None:
            os.environ.pop("GIT_CEILING_DIRECTORIES", None)
        else:
            os.environ["GIT_CEILING_DIRECTORIES"] = old_ceil


# ═══════ (بوّابةُ التسليم · review-47) منافذُ التفادي التي كشفتها المقاعدُ المعزولة ═══════

def _build_on(tmp_path: Path, run: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "tools/eval_pack.py", "--build",
                           "--run", str(run), "--out", str(tmp_path / "built")],
                          cwd=ROOT, capture_output=True, text=True)


def _verdict(r) -> str:
    return next((ln for ln in r.stdout.splitlines() if ln.startswith("الحكم:")), "")


@needs_artifacts
def test_a_census_page_that_no_longer_closes_is_named_by_the_second_layer(tmp_path):
    """**سمُّ الطبقة ٢** (إعادةُ الاشتقاق): قيمةُ إطارٍ تُبدَّل ⇒ الإسقاطُ لا يتغيّر (الحقولُ بالمفاتيح
    لا بالقيم) ⇒ لا يمسكها الختم، **وتمسكها إعادةُ الاشتقاق باسمها** — فالادّعاءُ بالطبقات صار مُقاساً."""
    n = _census_first()

    def poison(run: Path) -> None:
        f = _page_file(run, n)
        d = json.loads(f.read_text(encoding="utf-8"))
        d["footer"]["debits"] = "999999.99"
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    r = _verify_on(_tampered_run(tmp_path, poison), _pack_copy(tmp_path))
    v = _verdict(r)
    assert r.returncode != 0 and "لم تُعد تُقفل" in v, r.stdout[-400:]
    assert "محتوى مخالف" not in v, "لو تغيّر الإسقاطُ لَما كان السمُّ معزولاً للطبقة ٢"


@needs_artifacts
def test_a_text_edit_past_the_old_120_char_cap_is_now_caught(tmp_path):
    """**ثقبٌ كشفته بوّابةُ التسليم:** كان النصُّ يُقطع عند ١٢٠ خانةً **بلا إعلان**، و٣٢ حقلًا في ٢٩
    صفحةً أطولُ من ذلك ⇒ تعديلُ الذيل يمرّ `PASS`. الآن: النصُّ كاملًا حتى 4096 وطولُه مُعلَنٌ قبلَه."""
    def poison(run: Path) -> None:
        for p in sorted(pack_io.pack_pages(PACK)):
            f = _page_file(run, p)
            d = json.loads(f.read_text(encoding="utf-8"))
            for row in d.get("raw_rows") or []:
                tx = str(row.get("desc") or "")
                if len(tx) > 120:                     # **الذيلُ وحده** — تعديلٌ بنفس الطول
                    row["desc"] = tx[:-1] + ("ز" if tx[-1] != "ز" else "س")
                    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
                    return
        raise AssertionError("لا نصَّ أطولَ من ١٢٠ خانةً في الكوربوس ⇒ السمُّ غيرُ قابلٍ للتنفيذ")

    r = _verify_on(_tampered_run(tmp_path, poison), _pack_copy(tmp_path))
    assert r.returncode != 0 and "محتوى مخالف" in _verdict(r), r.stdout[-400:]


@needs_artifacts
def test_a_corrupt_results_file_is_named_and_never_a_traceback(tmp_path):
    """قراءةٌ غيرُ محروسة في حلقة إعادة الاشتقاق كانت تُنفجر بـ`JSONDecodeError` **قبل** سطر الختم
    والحكم (الحالةُ الفيزيائيّةُ المتوقَّعة: كتابةٌ مُنقطِعة) ⇒ الآن تُسمّى صفحةً غيرَ مقروءة."""
    def poison(run: Path) -> None:
        _page_file(run, _census_first()).write_text("{ ليس JSON", encoding="utf-8")

    r = _verify_on(_tampered_run(tmp_path, poison), _pack_copy(tmp_path))
    out = r.stdout + r.stderr
    assert "Traceback" not in out, "انفجارُ بايثون بدل حكمٍ مُسمّى"
    assert r.returncode != 0 and "غيرُ مقروءة" in out, out[-400:]


@needs_artifacts
def test_build_refuses_when_the_committed_aggregate_drifted(tmp_path):
    """**منفذٌ مقيس:** `--build` على قرصٍ مُحرَّف كان `PASS` (الختمُ يعيد الاشتقاق من القرص نفسِه)
    ⇒ وبعدها `--verify` يقول «الحزمةُ تشهد لنفسها». الآن **المجمَّعةُ المُلتزمة** تُقابَل في البناء أيضًا."""
    def poison(run: Path) -> None:
        f = _page_file(run, _census_first())
        d = json.loads(f.read_text(encoding="utf-8"))
        d["raw_rows"][0]["desc"] = str(d["raw_rows"][0].get("desc") or "") + "ز"
        f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    b = _build_on(tmp_path, _tampered_run(tmp_path, poison))
    assert b.returncode != 0, b.stdout[-400:]
    assert "المجمَّعةُ المُلتزمة" in (b.stdout + b.stderr), b.stdout[-400:]


@needs_artifacts
def test_a_rule_of_zero_is_refused_by_name_and_writes_nothing(tmp_path):
    """`--holdout-mod 0` كان يُفرِّغ الحجزَ (قِيس عند المدقّق: ١٤٢ صفحةً مُقيَّمة دخلت التدريب · `rc=0`)."""
    out = tmp_path / "t0"
    r = subprocess.run([sys.executable, "tools/capture_training.py",
                        "--run", "data/local_sample/slice_629p",
                        "--export", "data/local_sample/export-629p.xlsx",
                        "--out", str(out), "--holdout-mod", "0"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1 and "لا يحجز شيئاً" in (r.stdout + r.stderr), r.stdout[-300:]
    assert not list(out.rglob("pg-*")), "كُتبت صفحاتٌ بقاعدةٍ فارغة"


@needs_artifacts
def test_an_unknown_identity_does_not_abandon_the_pack_silently(tmp_path):
    """**منفذٌ مقيس:** بلا ملفّ أصل يصير `doc_id = unknown_doc` ⇒ الحزمةُ لا تُستثنى **بصمت** وتُكتب
    ١٣٣ من ٢٠٠ صفحةً مقيَّدة في التدريب بـ`rc=0`. الآن: وقوفٌ بالاسم، والمخرجُ بعَلَمٍ صريح."""
    base = [sys.executable, "tools/capture_training.py",
            "--run", "data/local_sample/slice_629p",
            "--export", "data/local_sample/export-629p.xlsx",
            "--pdf", str(tmp_path / "لا-يوجد.pdf"), "--limit", "1"]
    r = subprocess.run([*base, "--out", str(tmp_path / "t1")], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0 and "لم تُستثنَ صفحةٌ واحدة" in (r.stdout + r.stderr), r.stdout[-300:]
    ok = subprocess.run([*base, "--no-pack-exclusion", "--out", str(tmp_path / "t2")],
                        cwd=ROOT, capture_output=True, text=True)
    assert ok.returncode == 0, "القرارُ الصريحُ يجب أن يمرّ: " + ok.stdout[-300:]


@needs_artifacts
def test_a_partial_run_never_certifies_the_disk(tmp_path):
    """**منفذٌ مقيس:** تشغيلةٌ جزئيّةٌ كانت تكتب البيانَ كاملاً فتُبيّض قاعدةَ الحجز ⇒ التشغيلةُ الكاملةُ
    بعدها حذفت ١٤٠ صفحةً بلا عَلَمٍ ولا سببٍ مُسمّى. والقاعدةُ الآن: لا يكتب حقولَ السلطة إلا من صدّق."""
    from tools.capture_training import close_authority
    ident = str(pack_io.pack_facts(PACK)["identity"])
    out = tmp_path / "tp"
    r = subprocess.run([sys.executable, "tools/capture_training.py",
                        "--run", "data/local_sample/slice_629p",
                        "--export", "data/local_sample/export-629p.xlsx",
                        "--out", str(out), "--limit", "1", "--holdout-mod", "2"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-300:]
    man = json.loads((out / ident / "manifest.json").read_text(encoding="utf-8"))
    assert man["close_out"]["mode"] == "not_full_run"
    assert "holdout_mod" not in man and "holdout_rule" not in man and "pack_exclusion" not in man, \
        f"تشغيلةٌ جزئيّةٌ صدّقت على سلطة القرص: {[k for k in man if 'holdout' in k or 'pack' in k]}"
    why = close_authority(is_full_run=True, now={"holdout_mod": 2, "capture_version": "1",
                                                 "export_sha256": "x", "pack_identity": ident,
                                                 "pack_pages": 200},
                          prev=man, disk_missing=False)
    assert any("لا يعلن قاعدةَ الحجز" in w for w in why), why
