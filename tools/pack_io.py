#!/usr/bin/env python3
"""قارئُ الحزمة **الواحد** — ومعه مُحدِّدُ جذر البيانات الوعيُ بالشجرات (worktree-aware).

## العلّةُ التي وُلد من أجلها (مقيسة: مراجعة ٤٥)

كان مسارُ الحزمة يُبنى من **موضع ملفّ الأداة** (`Path(__file__).parents[1]`). وفي شجرةِ عملٍ
منفصلة (`git worktree`) لا يوجد `data/` — فالأدلّةُ الثقيلةُ (الحزمة · الالتقاط · المفتاح)
خارج git وباقيةٌ في الشجرة الأمّ — ⇒ **الحمايةُ تختفي صامتةً**: «لا حزمةَ معلَنة» ⇒ لا استثناء،
والالتقاطُ يمرّ `rc=0` وصفحاتُ الحزمة تعود إلى التدريب (قِيس: ٣ من ٤ صفحاتٍ في تشغيلةٍ من worktree).

## الحلُّ من الجذر لا بالترقيع

جذرُ البيانات يُحلّ بـ`git rev-parse --git-common-dir`: كلُّ شجرات العمل تشترك في `.git` واحدة،
وأبوه هو جذرُ الشجرة الأمّ حيث تعيش `data/`. فشجرةُ العمل ترى الأدلّةَ **بحكم البناء** لا بنسخةٍ
تُنسخ في كل شجرة (والنسخُ يُنشئ نسخًا تتفرّق ثم تتناقض).

## وقراءةٌ واحدة

هذا الملفّ هو الموضعُ الوحيدُ لقراءة صفحات الحزمة. من احتاجها استوردها من هنا — وكان في المستودع
أربعُ نسخٍ لها، **واحدةٌ منها سبق أن انحرفت فعلاً** (review-32: إحصى أحدُها المدياتِ وحدَها).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REL_PACK = Path("data/eval_pack/pack.json")
EVIDENCE_GLOB = "*-item4-pack-free-capture.json"


def _git(args: list[str], start: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(start), *args], capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def repo_root(start: Path | None = None) -> Path:
    """جذرُ شجرة العمل الحاليّة (`--show-toplevel`) — أو المجلدُ نفسه إن لم تكن شجرةَ git."""
    here = Path(start or Path(__file__).resolve().parent).resolve()
    top = _git(["rev-parse", "--show-toplevel"], here)
    return Path(top).resolve() if top else here


def data_root(start: Path | None = None) -> Path:
    """**جذرُ الأدلّة المشترك**: شجرةُ العمل → الشجرةُ الأمّ (بحكم `git-common-dir`).

    ولا يُخمَّن: إن تعذّر سؤالُ git (لا مستودع · لا git) رجعنا لجذر الشجرة الحاليّة،
    ويُعلن المستدعي ما قاسه.
    """
    here = Path(start or Path(__file__).resolve().parent).resolve()
    common = _git(["rev-parse", "--git-common-dir"], here)
    if not common:
        return repo_root(here)
    c = Path(common)
    if not c.is_absolute():
        c = (here / c).resolve()
    # `--git-common-dir` = <الشجرة الأمّ>/.git  ⇒  أبوه هو الجذرُ المشترك
    return c.parent if c.name == ".git" else c


def pack_path(start: Path | None = None) -> Path:
    """مسارُ الحزمة المشترك — وهو الافتراضُ الذي تُستثنى صفحاتُه بلا سؤال."""
    return data_root(start) / REL_PACK


def evidence_path(start: Path | None = None) -> Path | None:
    """أحدثُ شهادةٍ مُلتزمةٍ للحزمة (تحمل بصمةَ المجموعة كاملةً) — أو None."""
    d = data_root(start) / "docs/evidence"
    if not d.is_dir():
        return None
    files = sorted(d.glob(EVIDENCE_GLOB))
    return files[-1] if files else None


def pack_facts(path: Path | None, *, expect_identity: str | None = None) -> dict:
    """حقيقةُ الحزمة المجمّدة — أربعةُ أصنافِ عطبٍ تُغلقها وقوفٌ مُسمّى (لا استثناءَ صامت):

      ١) القائمةُ غائبةٌ أو غيرُ مقروءة.  ٢) فارغة.  ٣) **قراءةٌ ناقصة** (ما قُرئ ≠ المقاس المُعلَن).
      ٤) **هويّةٌ أخرى** — والمفتاحُ `(doc_id, page)` كما تُعلنه الحزمةُ نفسُها.
    """
    if path is None:
        return {"pages": set(), "identity": None, "declared": None, "fingerprint": None,
                "file": None, "expect_identity": expect_identity}
    f = Path(path)
    if not f.exists():
        raise SystemExit(f"⛔ قائمةُ استثناءٍ مُعلَنة وغيرُ موجودة ({f.name}) ⇒ لا التقاط")
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"⛔ قائمةُ استثناءٍ لا تُقرأ ({f.name} · {type(e).__name__}) ⇒ لا التقاط") from e

    def _nums(xs, where: str) -> set[int]:
        out: set[int] = set()
        for p in xs or []:
            if isinstance(p, dict) and "page" in p:
                out.add(int(p["page"]))
            elif isinstance(p, int):
                out.add(p)
            else:
                raise SystemExit(f"⛔ عنصرٌ غيرُ معروفٍ في {where} ({type(p).__name__}) ⇒ لا التقاط")
        return out

    out = _nums(d.get("census", {}).get("pages", []), "census.pages")
    for r in d.get("ranges", []):
        out |= _nums(r.get("pages", []), "ranges[].pages")
    if not out:
        raise SystemExit("⛔ قائمةُ الاستثناء فارغةٌ ⇒ استثناءٌ بلا صفحاتٍ لا يُنفَّذ صامتاً")

    declared = d.get("size_gate", {}).get("value")
    if isinstance(declared, int) and len(out) != declared:
        raise SystemExit(f"⛔ قراءةُ الحزمة ناقصة: قُرئ {len(out)} والمُعلَن {declared} ⇒ لا التقاط")
    ident = d.get("identity")
    ident = ident.get("doc_id") if isinstance(ident, dict) else ident
    if expect_identity and ident and str(ident) != str(expect_identity):
        raise SystemExit(f"⛔ الحزمةُ لمستندٍ آخر ({str(ident)[:16]} ≠ {str(expect_identity)[:16]}) ⇒ لا استثناء")
    return {"pages": out, "identity": (str(ident) if ident else None), "declared": declared,
            "fingerprint": (d.get("census") or {}).get("fingerprint"),
            "file": f.name, "expect_identity": expect_identity}


def pack_pages(path: Path | None, *, expect_identity: str | None = None) -> set[int]:
    """صفحاتُ الحزمة وحدَها (غلافٌ حول `pack_facts` لمن يريد المجموعةَ لا الحقيقةَ كاملة)."""
    return pack_facts(path, expect_identity=expect_identity)["pages"]


def pages_sha256(pages) -> str:
    """**بصمةُ المجموعة كاملةً** — نفسُ صيغةِ الشهادة المُلتزمة (لا الإحصاءَ وحدَه)."""
    return hashlib.sha256(json.dumps(sorted(int(p) for p in pages)).encode()).hexdigest()


def seal(start: Path | None = None) -> dict | None:
    """ما تقوله الشهادةُ المُلتزمة: بصمةُ المجموعة وعددُها — **القارئُ الذي لم يكن للختم**."""
    ev = evidence_path(start)
    if ev is None:
        return None
    try:
        d = json.loads(ev.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"file": ev.name, "error": "شهادةٌ لا تُقرأ"}
    p = d.get("pack") or {}
    return {"file": ev.name, "sha256": p.get("pages_sha256"), "count": p.get("pages_count")}


def seal_violation(facts: dict, start: Path | None = None) -> str | None:
    """مقابلةُ الحزمة الحيّة بالختم المُلتزم — ورسالةُ مخالفةٍ مُسمّاة، أو None إن طابق."""
    s = seal(start)
    if s is None:
        return "لا شهادةَ مُلتزمة ⇒ الختمُ بلا قارئ (شغّل tools/pack_evidence.py وحدِّث الشهادة)"
    if s.get("error"):
        return f"الشهادةُ المُلتزمة لا تُقرأ ({s['file']})"
    live = pages_sha256(facts["pages"])
    if s.get("count") != len(facts["pages"]) or s.get("sha256") != live:
        return (f"ختمُ الحزمة لا يطابق الشهادة المُلتزمة ({s['file']}): "
                f"المُلتزم {str(s.get('sha256'))[:16]}×{s.get('count')} ≠ الحيّ {live[:16]}×{len(facts['pages'])}")
    return None
