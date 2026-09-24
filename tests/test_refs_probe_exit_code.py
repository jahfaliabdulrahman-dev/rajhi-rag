"""**رمزُ خروج حيّاز الانكشاف من الحكم لا من شكل المخرَج** — ضابطٌ سلوكيّ (لا نصّيّ).

**العطبُ الذي وُلد منه (قِيس 2026-09-24 بعد ردّ دعم GitHub):** البروتوكولُ يوثّق
`PURGED=0 · STILL EXPOSED=1 · UNMEASURED=2`، لكنّ `return 1` كان **داخل فرع المخرَج النصّيّ**
⇒ `--json` يُرجع **0** والحكمُ `STILL EXPOSED`. ومستهلكٌ آليّ (بوّابة/سكربت) يقرأ صفرًا فيمرّ
على سطحٍ مكشوف: **فشلٌ مفتوح** في الأداة التي يُقرَّر بها إغلاقُ بند الانكشاف نفسه.

والضابطُ **يشغّل `main()` فعلًا** (لا يقرأ المصدر)، بشبكةٍ مزيّفة عبر السبيلَين `_run` و`_http_code`
⇒ سريعٌ، بلا نداءِ شبكة، ويقيس الحالتين **في وضعَي المخرَج**.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location("refs_probe", ROOT / "tools" / "refs_exposure_probe.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ الحيّاز ⇒ لا قياس"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _CP:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def _sha_file(n: int = 2) -> Path:
    """قائمةُ معرّفاتٍ مؤقّتة — **تُوفَّر دائمًا** كي لا يعتمد القياسُ على ملفٍّ محلّيّ.

    (قِيس في نسخةٍ نقيّة: بلا هذا كان الحيّازُ يفشل مُغلَقاً **قبل** الشبكة المزيّفة ⇒ ٣ ضوابط تسقط
    في بيئةٍ لا ملفَّ فيها — وهي بعينها ملاحظةُ المدقّق «الرقمُ في نسختك وحدها».)
    """
    p = Path(tempfile.mkdtemp()) / "refs-cached-shas.json"
    p.write_text(json.dumps({"cached_views": [{"sha": f"{i}" * 40, "what": "x"} for i in range(n)]}),
                 encoding="utf-8")
    return p


def _wire(monkeypatch, mod, *, forms: int, http: int, shas: int = 2) -> None:
    """شبكةٌ مزيّفة: الريموتُ فيه مرجعان · المرآةُ عشرةُ التزامات · والمسحُ يعيد `forms` شكلًا."""
    guard = types.SimpleNamespace(
        load_deny=lambda: {"بصمة"},
        history_forms=lambda deny, repo=None: (11, forms),
    )
    monkeypatch.setattr(mod, "_guard", lambda: guard)
    monkeypatch.setattr(mod, "_http_code", lambda url: http)
    monkeypatch.setattr(mod, "SHA_FILE", _sha_file(shas))   # حتميّةٌ: لا اعتمادَ على ملفٍّ محلّيّ

    def fake_run(cmd, cwd=None):
        if "ls-remote" in cmd:
            return _CP("a\trefs/pull/1/head\nb\trefs/pull/2/head\n")
        if "rev-list" in cmd and "--all" in cmd:
            return _CP("10\n")
        if "rev-list" in cmd:
            return _CP("5\n")
        return _CP("")                      # الاستنساخُ نجح

    monkeypatch.setattr(mod, "_run", fake_run)


def _run_main(mod, monkeypatch, capsys, argv: list[str]) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["refs_exposure_probe", *argv])
    rc = mod.main()
    return rc, capsys.readouterr().out


def test_purged_is_zero_in_both_output_modes(monkeypatch, capsys):
    mod = _load()
    _wire(monkeypatch, mod, forms=0, http=404)          # لا شكلَ مبلغ ولا cached view
    rc_plain, out_plain = _run_main(mod, monkeypatch, capsys, [])
    assert rc_plain == 0, f"PURGED ⇒ 0 (صار {rc_plain})"
    assert "PURGED" in out_plain
    rc_json, out_json = _run_main(mod, monkeypatch, capsys, ["--json"])
    assert rc_json == 0, f"PURGED في وضع `--json` ⇒ 0 (صار {rc_json})"
    assert json.loads(out_json)["verdict"] == "PURGED"


def test_still_exposed_is_one_in_both_output_modes(monkeypatch, capsys):
    """**وهذا هو العطبُ نفسُه**: كان وضعُ `--json` يُرجع 0 مع حكمٍ مكشوف."""
    mod = _load()
    _wire(monkeypatch, mod, forms=123, http=404)        # أشكالُ مبالغَ مرئيّة ⇒ مكشوف
    rc_plain, out_plain = _run_main(mod, monkeypatch, capsys, [])
    assert rc_plain == 1, f"STILL EXPOSED (نصّيّ) ⇒ 1 (صار {rc_plain})"
    assert "STILL EXPOSED" in out_plain
    rc_json, out_json = _run_main(mod, monkeypatch, capsys, ["--json"])
    assert rc_json == 1, f"STILL EXPOSED في وضع `--json` ⇒ 1 (صار {rc_json}) — فشلٌ مفتوح"
    assert json.loads(out_json)["verdict"] == "STILL EXPOSED"


def test_a_cached_view_that_answers_200_is_enough_to_stay_exposed(monkeypatch, capsys):
    """**الشرطان يُقاسان منفصلَين**: صفرُ أشكالٍ مبالغ مع cached view يردّ 200 ⇒ **ما زال مكشوفًا**."""
    mod = _load()
    _wire(monkeypatch, mod, forms=0, http=200)
    rc, _ = _run_main(mod, monkeypatch, capsys, ["--json"])
    assert rc == 1, f"cached view = 200 ⇒ 1 (صار {rc})"


def test_the_cached_sha_list_is_read_from_an_untracked_file(monkeypatch, capsys, tmp_path):
    """**المعرّفاتُ ليست في المستودع** (مراجعة ٥٣): كانت في الأداة المُتتبَّعة ⇒ «رابطٌ موسومٌ» إلى ما لم يُطهَّر."""
    import json as _json
    mod = _load()
    _wire(monkeypatch, mod, forms=0, http=404, shas=3)   # ثلاثةُ معرّفاتٍ لا اثنان
    rc, out = _run_main(mod, monkeypatch, capsys, ["--json"])
    assert rc == 0 and _json.loads(out)["verdict"] == "PURGED"
    assert len(_json.loads(out)["cached_views"]) == 3, "القائمةُ تُقرأ من الملفّ (٣) لا من ثابتٍ في المصدر (٢)"


def test_the_probe_is_hermetic_without_a_local_sha_file(monkeypatch, capsys, tmp_path):
    """**حتميّةٌ في أيّ نسخة**: بلا ملفٍّ محلّيّ يفشل مُغلَقًا — والضابطُ يُثبته لا يُخفيه."""

    mod = _load()
    monkeypatch.setattr(mod, "SHA_FILE", tmp_path / "لا-يوجد.json")
    rc, out = _run_main(mod, monkeypatch, capsys, ["--json"])
    assert rc == 2, f"غيابُ القائمة ⇒ 2 (صار {rc})"


# (حُذف ضابطٌ مكرَّر: صار غيابُ القائمة يُقاس في test_the_probe_is_hermetic_without_a_local_sha_file —
#  وتكرارُه هنا كان يخلط بيّنتَين: متغيّرَ البيئة وملفَّ الحيّاز.)
