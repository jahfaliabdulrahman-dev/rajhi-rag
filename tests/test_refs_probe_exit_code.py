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


def _wire(monkeypatch, mod, *, forms: int, http: int) -> None:
    """شبكةٌ مزيّفة: الريموتُ فيه مرجعان · المرآةُ عشرةُ التزامات · والمسحُ يعيد `forms` شكلًا."""
    guard = types.SimpleNamespace(
        load_deny=lambda: {"بصمة"},
        history_forms=lambda deny, repo=None: (11, forms),
    )
    monkeypatch.setattr(mod, "_guard", lambda: guard)
    monkeypatch.setattr(mod, "_http_code", lambda url: http)

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
    f = tmp_path / "shas.json"
    f.write_text(_json.dumps({"cached_views": [{"sha": "a" * 40, "what": "x"}, {"sha": "b" * 40, "what": "y"}]}),
                 encoding="utf-8")
    monkeypatch.setenv("REFS_CACHED_SHAS", str(f))
    mod = _load()                                    # يُعاد التحميلُ ليقرأ المتغيّر
    _wire(monkeypatch, mod, forms=0, http=404)
    monkeypatch.setattr(mod, "_http_code", lambda url: 404)
    rc, out = _run_main(mod, monkeypatch, capsys, ["--json"])
    assert rc == 0 and _json.loads(out)["verdict"] == "PURGED"
    assert len(_json.loads(out)["cached_views"]) == 2, "القائمةُ المقيسة تأتي من الملفّ لا من ثابتٍ في المصدر"


def test_a_missing_sha_list_fails_closed(monkeypatch, capsys, tmp_path):
    """**غيابُ الأدلّة ليس نظافة**: بلا قائمةٍ لا يُقاس الكاش ⇒ `UNMEASURED` (rc=2)."""
    mod = _load()
    monkeypatch.setenv("REFS_CACHED_SHAS", str(tmp_path / "لا-يوجد.json"))
    mod = _load()
    _wire(monkeypatch, mod, forms=0, http=404)
    rc, out = _run_main(mod, monkeypatch, capsys, ["--json"])
    assert rc == 2, f"لا قائمةَ ⇒ 2 (صار {rc})"
    assert "UNMEASURED" in out

