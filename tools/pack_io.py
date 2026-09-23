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
import os
import re
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

    ولا يُخمَّن أبداً: `RAJHI_DATA_ROOT` الصريحُ يسبق، ثم git — وإن تعذّر الاثنان **ترتفع استثناءةٌ
    بالاسم** بدل الرجوع إلى جذرٍ مخمَّن. (مراجعة ٤٧ · باقية P2: كان التخمينُ يُرجع مجلدَ الأداة
    `tools/` ⇒ الحزمةُ تختفي **صامتةً**، ولا استثناء، والالتقاطُ يمرّ `rc=0` على صفحاتٍ مقيَّدة.)
    """
    env = os.environ.get("RAJHI_DATA_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    here = Path(start or Path(__file__).resolve().parent).resolve()
    common = _git(["rev-parse", "--git-common-dir"], here)
    if not common:
        raise RuntimeError(
            f"جذرُ الأدلّة مجهول: لا git يُسأل عنه في {here} — **لا تخمين** "
            "(التخمينُ كان يُرجع مجلدَ الأداة فتختفي الحزمةُ صامتةً). "
            "اضبط RAJHI_DATA_ROOT صراحةً إن كان القصدُ شجرةً بلا مستودع."
        )
    c = Path(common)
    if not c.is_absolute():
        c = (here / c).resolve()
    # `--git-common-dir` = <الشجرة الأمّ>/.git  ⇒  أبوه هو الجذرُ المشترك
    return c.parent if c.name == ".git" else c


def pack_path(start: Path | None = None) -> Path:
    """مسارُ الحزمة المشترك — وهو الافتراضُ الذي تُستثنى صفحاتُه بلا سؤال."""
    return data_root(start) / REL_PACK


def evidence_path(start: Path | None = None) -> Path | None:
    """أحدثُ شهادةٍ مُلتزمةٍ للحزمة — من **الشجرة الجاريّة** لا من الشجرة الأمّ.

    (مراجعة ٤٥+ · S-1/S-2): `docs/evidence` **مُتتبَّعة** في git، فحقُّها أن تُقرأ وتُكتب في النسخة
    التي تعمل فيها — بخلاف `data/` (أدلّةٌ ثقيلةٌ مُهمَلةٌ باقيةٌ في شجرةٍ واحدة). وخلطُ الجذرين
    جعل الأمرَ الموثَّق يسقط من شجرة عملٍ (`relative_to` ValueError) **بعد** أن كتب في نسخةٍ أخرى.
    """
    d = repo_root(start) / "docs/evidence"
    if not d.is_dir():
        return None
    files = sorted(d.glob(EVIDENCE_GLOB))
    return files[-1] if files else None


def pack_facts(path: Path | None, *, expect_identity: str | None = None,
               absent_ok: bool = False) -> dict:
    """حقيقةُ الحزمة المجمّدة — أربعةُ أصنافِ عطبٍ تُغلقها وقوفٌ مُسمّى (لا استثناءَ صامت):

      ١) القائمةُ غائبةٌ أو غيرُ مقروءة.  ٢) فارغة.  ٣) **قراءةٌ ناقصة** (ما قُرئ ≠ المقاس المُعلَن).
      ٤) **هويّةٌ أخرى** — والمفتاحُ `(doc_id, page)` كما تُعلنه الحزمةُ نفسُها.
    """
    if path is None:
        return {"pages": set(), "identity": None, "declared": None, "fingerprint": None,
                "file": None, "expect_identity": expect_identity, "note": "لا حزمةَ مُعلَنة"}
    f = Path(path)
    if not f.exists():
        if absent_ok:                       # **سياسةُ غيابٍ واحدة** لكلّ الساحبين (STR-5)
            return {"pages": set(), "identity": None, "declared": None, "fingerprint": None,
                    "file": f.name, "expect_identity": expect_identity, "note": "الحزمةُ غائبة ⇒ لا استثناء"}
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
        # (F3): حزمةُ **مستندٍ آخر** لا تُلوّث مستندَنا (أرقامُ الصفحات تتشابه بلا معنى) ⇒ لا استثناء،
        # ويُعلَن الاختلافُ بدل أن يتوقّف أمرٌ موثَّق. والضمانةُ الحقيقيّةُ للمستند نفسِه تبقى في المسار
        # المطابق: مفتاحُ `(doc_id, page)` وسَمُّ التصادم المُلتزم.
        return {"pages": set(), "identity": (str(ident) if ident else None), "declared": declared,
                "fingerprint": (d.get("census") or {}).get("fingerprint"), "file": f.name,
                "expect_identity": expect_identity,
                "note": f"حزمةٌ لمستندٍ آخر ({str(ident)[:16]} ≠ {str(expect_identity)[:16]}) ⇒ لا استثناء"}
    return {"pages": out, "identity": (str(ident) if ident else None), "declared": declared,
            "fingerprint": (d.get("census") or {}).get("fingerprint"),
            "file": f.name, "expect_identity": expect_identity}


def pack_pages(path: Path | None, *, expect_identity: str | None = None) -> set[int]:
    """صفحاتُ الحزمة وحدَها (غلافٌ حول `pack_facts` لمن يريد المجموعةَ لا الحقيقةَ كاملة)."""
    return pack_facts(path, expect_identity=expect_identity)["pages"]


def excluding_pack(pool: list[int], pages: set[int]) -> list[int]:
    """يُسقط صفحاتِ الحزمة من مجموعة السحب — **الدالّةُ الواحدةُ لكلّ ساحب** (كانت في أداةٍ واحدة)."""
    return [p for p in pool if p not in pages]


def pages_sha256(pages) -> str:
    """**بصمةُ المجموعة كاملةً** — نفسُ صيغةِ الشهادة المُلتزمة (لا الإحصاءَ وحدَه)."""
    return hashlib.sha256(json.dumps(sorted(int(p) for p in pages)).encode()).hexdigest()


# ── ختمُ المحتوى: ما لا تراه بوّاباتُ المال ─────────────────────────────────
#: إسقاطُ الصفحة الذي يُختم — **ويُعلن حدَّه**: لا قيمةَ مبلغٍ فيه (القاعدة ١٣: بصمةُ مبلغٍ
#: ليست قناعاً، فمجالُه قابلٌ للتعداد). فالمالُ تحرسه بوّاباتُه (الهوية/الإطار/العدّاد)
#: التي تُعاد اشتقاقُها من القرص، والختمُ يحرس ما لا تراه: **الوجودُ والنصُّ والبنيةُ والأعلام**.
PAGE_SEAL_SCHEMA = ("sha256 لِإسقاطٍ قياسيٍّ للصفحة: pg · page_no · حقولُ الإطار · عددُ الصفوف · "
                    "(الترتيب · التاريخ · مصدرُ التاريخ · العمودُ المطبوع · وُجودُ مبلغ · "
                    "النصّ **كاملًا** حتى 4096 خانةً ومع طولِه المُعلَن قبلَه) · "
                    "وأعلامُ القارئ — **بلا قيمِ مبالغ** (القاعدة ١٣)")
SEAL_TEXT_MAX = 4096
SEAL_FLAGS = ("recovered", "reread", "arbitrated_by", "superseded_reason", "page_no_source", "page_no_note")


def page_projection(pg: dict) -> dict:
    """إسقاطٌ قياسيٌّ لمحتوى صفحة — **حتميّ**: نفسُ المحتوى ⇒ نفسُ الإسقاط، حرفاً بحرف.

    ومفاتيحُ الصفّ **من الشكل المُعلن للكوربوس** (`movement`/`balance`/`desc`/`date`/`date_source`،
    و`col`/`printed_col` للكوربوس ذي العمود المطبوع) — ودرسٌ مدفوع: أوّلُ نسخةٍ قرأت `descr`
    فكان الإسقاطُ فارغاً من النصّ **وضبطُ تعديل النصّ لم يَعَضّ** (قِيس: `PASS` على سمٍّ حقيقيّ).
    """
    def txt(x) -> str:
        """نصٌّ مطبَّعٌ **بكاملِه** حتى `SEAL_TEXT_MAX`، وطولُه **مُعلَنٌ قبلَه** فلا يُخفي ذيلًا.

        (بوّابةُ التسليم: كان `[:120]` يقطع صمتاً، وقِيس أنّ ٣٢ حقلًا في ٢٩ صفحةً أطولُ من ١٢٠
        ⇒ سمٌّ في الذيل يمرّ `PASS`. والطولُ المُعلَن يجعل أيَّ تغييرٍ للطول مرئيًّا، حتى فوق الحدّ.)
        """
        s = re.sub(r"\s+", " ", str(x if x is not None else "")).strip()
        return f"{len(s)}:{s[:SEAL_TEXT_MAX]}"

    rows = pg.get("raw_rows") or []
    return {
        "pg": pg.get("pg"),
        "page_no": pg.get("page_no"),
        "footer": sorted((pg.get("footer") or {}).keys()),
        "n_rows": len(rows),
        "rows": [[i + 1, txt(r.get("date")), txt(r.get("date_source")),
                  txt(r.get("col")), txt(r.get("printed_col")),
                  bool(str(r.get("movement") or "").strip()), txt(r.get("desc") or r.get("descr"))]
                 for i, r in enumerate(rows)],
        "flags": [bool(pg.get(k)) for k in SEAL_FLAGS],
    }


def page_content_sha16(pg: dict, *, with_amounts: bool = False) -> str:
    """بصمةُ محتوى صفحة — تُشتقّ من الملفّ نفسِه، لا من تقريرٍ عنه.

    و`with_amounts=True` تُضيف **قيمَ المبالغ كما طُبعت** ⇒ بصمةٌ **محلّيّةٌ لا تُنشر** (القاعدة ١٣).
    وهي التي تسدّ ثغرةً مقيسةً في الختم الخالي من المال: **تعديلٌ منسَّق** (صفّان على الجهة نفسها
    بـ+X و−X) يُبقي الهويةَ والإطارَ مغلقَين ⇒ لا تُسقطه بوّاباتُ المال ولا إسقاطٌ بلا مبالغ.
    """
    payload = page_projection(pg)
    if with_amounts:
        rows = pg.get("raw_rows") or []
        payload = {**payload, "amounts": [
            [i + 1, str(r.get("movement") or ""), str(r.get("balance") or ""),
             str(r.get("raw_movement") or ""), str(r.get("raw_balance") or "")]
            for i, r in enumerate(rows)]}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
                                     sort_keys=True).encode("utf-8")).hexdigest()[:16]


def run_page(run_dir: Path, page: int) -> dict | None:
    """ملفُّ نتيجة صفحةٍ في تشغيلة — `None` تعني **غائبة** (تُسمّى ولا تُخمَّن)."""
    f = Path(run_dir) / "results" / f"pg-{int(page):03d}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def content_seal(run_dir: Path, pages) -> dict:
    """ختمُ محتوى **كلّ** صفحةٍ مقيَّدة: الوجودُ + البصمة — يُبنى ويُقابَل بنفس الدالّة.

    لكلّ صفحةٍ بصمتان: `sha16` (بلا مال — وهي التي تُنشر مجمَّعةً في الشهادة) و`sha16_local`
    (**بقيم المبالغ** — تبقى في الحزمة المحلّيّة ولا تخرج، القاعدة ١٣).
    """
    per: dict[str, dict] = {}
    missing: list[int] = []
    unreadable: list[int] = []
    for p in sorted(int(x) for x in pages):
        d = run_page(run_dir, p)
        if d is None:
            (missing if not (Path(run_dir) / "results" / f"pg-{p:03d}.json").exists()
             else unreadable).append(p)
            continue
        per[str(p)] = {"sha16": page_content_sha16(d), "sha16_local": page_content_sha16(d, with_amounts=True),
                       "rows": len(d.get("raw_rows") or [])}
    # والبصمةُ المجمَّعة **من الخالي من المال وحدَه** ⇒ ما يُلتزم في الشهادة لا يحمل بصمةَ مبلغ
    agg = hashlib.sha256(json.dumps({k: v["sha16"] for k, v in per.items()},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return {"schema": PAGE_SEAL_SCHEMA, "pages": per, "missing": missing, "unreadable": unreadable,
            "aggregate_sha16": agg, "covers": len(per),
            "aggregate_note": ("المجمَّعةُ من بصمات بلا قيمِ مبالغ ⇒ تُنشر؛ وبصمةُ المبلغ تبقى "
                               "محلّيّةً في `sha16_local` (القاعدة ١٣: بصمةُ مبلغٍ ليست قناعاً)")}


def seal(start: Path | None = None) -> dict | None:
    """ما تقوله الشهادةُ المُلتزمة: بصمةُ المجموعة وعددُها **والمجمَّعةُ الخاليةُ من المال**.

    **والثالثُ هو قراءةُ العدد المنشور** (بوّابةُ التسليم · المقعد الثاني): كان يُكتب في الشهادة
    ولا يقرأه أحد ⇒ بعد أيّ `--build` على قرصٍ مُحرَّف يعود الحكمُ `PASS` و«الحزمةُ تشهد لنفسها».
    """
    ev = evidence_path(start)
    if ev is None:
        return None
    try:
        d = json.loads(ev.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"file": ev.name, "error": "شهادةٌ لا تُقرأ"}
    p = d.get("pack") or {}
    return {"file": ev.name, "sha256": p.get("pages_sha256"), "count": p.get("pages_count"),
            "page_seal_aggregate": ((p.get("page_seal") or {}).get("aggregate_sha16")),
            "tree": str(repo_root(start))}          # **يُعلَن من أيّ شجرةٍ قُرئ** (S-2)


def seal_violation(facts: dict, live_seal: dict | None = None,
                   start: Path | None = None) -> str | None:
    """مقابلةُ الحزمة الحيّة بالختم المُلتزم — ورسالةُ مخالفةٍ مُسمّاة، أو None إن طابق.

    و`live_seal` (إن مُرِّر) يُدخل **المجمَّعةَ الخاليةَ من المال** في المقابلة ⇒ صار للعدد المنشور قارئ.
    """
    s = seal(start)
    if s is None:
        return "لا شهادةَ مُلتزمة ⇒ الختمُ بلا قارئ (شغّل tools/pack_evidence.py وحدِّث الشهادة)"
    if s.get("error"):
        return f"الشهادةُ المُلتزمة لا تُقرأ ({s['file']})"
    live = pages_sha256(facts["pages"])
    if s.get("count") != len(facts["pages"]) or s.get("sha256") != live:
        return (f"ختمُ الحزمة لا يطابق الشهادة المُلتزمة ({s['file']}): "
                f"المُلتزم {str(s.get('sha256'))[:16]}×{s.get('count')} ≠ الحيّ {live[:16]}×{len(facts['pages'])}")
    if live_seal is not None and s.get("page_seal_aggregate") \
            and s["page_seal_aggregate"] != live_seal.get("aggregate_sha16"):
        return (f"المجمَّعةُ المُلتزمة لمحتوى الصفحات تخالف الحيّة ({s['file']}): "
                f"المُلتزم {s['page_seal_aggregate']} ≠ الحيّ {live_seal.get('aggregate_sha16')} "
                "⇒ محتوى القرص تغيّر بعد الشهادة — أَعِد الشهادةَ بأمرٍ معلَن "
                "(`tools/pack_evidence.py`) أو حقِّق في المسّ")
    return None
