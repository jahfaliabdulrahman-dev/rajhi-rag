"""**الجوابُ يُسمّي شاهدَه** — الحارسُ الذي حلَّ محلَّ `tests/test_review_landing.py` (R57-1).

**العلّةُ المقيسة** (قاسها المدقّق في مراجعة ٥٧ وسمّاها *the witness cannot land*): الحارسُ السابق اشترط أن
يكون **كلُّ** ملفٍّ في `handoff/claude/` موجوداً في `origin/main` **مسبقاً** — شرطٌ لا يملكه الفرعُ الذي
يحمل المراجعةَ الجديدة **بحكم تعريفه** ⇒ كلُّ مراجعةٍ جديدة تُسقط الـCI، وحمايةُ `main` تشترط الفحصَ الأخضر
(`strict` · `enforce_admins`) ⇒ **يُمنَع هبوطُ المراجعة، ويُمنَع الامتثالُ لِـ§٢٧ بالحارسِ المكتوبِ لفرضها** —
وهو الصنفُ نفسُه الذي سُحب في `231f17f`. وعلى `main` نفسِه كان ينجح **دون أن يقيس شيئاً**: كلُّ ملفٍّ فيه
موجودٌ فيه بحكم التعريف. أي أنّ العطبَ **الجذريَّ** لم يكن في التنفيذ بل في **الاتّجاه**: حارسٌ يقيس
**مكانَ الوجود** (سؤالٌ لا يملك الفرعُ جوابَه) بدل أن يقيس **الرابطَ** (سؤالٌ يملكه الطرفان).

**الثابتُ الجديد:** كلُّ جوابٍ على مراجعة (ملفٌّ في `handoff/sulaiman/` اسمُه يحمل `REPORT-to-claude`)
**يُعلن شاهدَه** بحقلِ `in-reply-to: <مسار>`، **والمسارُ موجودٌ في الشجرة المدفوعة نفسِها** (هدفُ §٢٧:
«الشاهدُ يُدفَع قبل أن يُجاب»). وهذا الفحصُ **مُتاحٌ للفرع** — لا يطلب من الفرع ما لا يملكه — ويسقط عند
الانحدار: جوابٌ يشير إلى مراجعةٍ لم تهبط ⇒ **يسقط**، والفرعُ الذي يُنزل المراجعةَ **يمرّ**.

**الحدودُ المُعلَنة (وإلّا صار الحارسُ ادّعاءً أوسعَ من مداه):**
1. القاعدةُ تسري على ما هبط **بعد** `WITNESS_FROM`؛ وما قبله **دَينٌ تاريخيٌّ معلَن** (`PRE_RULE_ANSWERS`
   يُقاس ويُقابَل — لا يُخفى ولا يُوصَف «نظافة»).
2. عددُ المُخاطَبين بالقاعدة يُقاس ويُقابَل بالثابت (`SUBJECTS_LANDED`) ⇒ لا قاعدةَ صامتةٌ على فراغ
   (وحين يهبط أوّلُ جوابٍ يصرخ الضابطُ فيُقرَن الشاهدُ ويُحدَّث الثابتُ في الالتزام نفسه — وهو صنفُ
   «سقفِ معدّلِ المعرّفات الغريبة» القائم في المستودع).
3. يُقابَل **وجودُ المسار**، لا صحّةُ كونِه المراجعةَ المقصودة (غيرُ قابلٍ للقياس آليّاً — يُعلَن).
4. والقياسُ على **الشجرة المُودَعة (`HEAD`)** لا على قرص الكاتب: ما لم يُودَع لا يُقاس. وهذا حدُّ الاتّجاهين
   معاً — لا «تذكيرٌ محلّيّ» يُتجاهَل، ولا موتٌ دائريٌّ للفروع.
5. صندوقُ المدقّق (`handoff/claude/`) خارج هذا الاتّجاه: المراجعةُ **تُصدر** حُكماً ولا تُجيب عنه.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOX = "handoff/sulaiman/"
ANSWER_MARK = "REPORT-to-claude"
#: حقلُ الشاهد: سطرٌ يبدأ بالحقل ويحمل مساراً واحداً بلا فراغ (اصطلاحُ ترقيم هذا المستودع).
WITNESS_RE = re.compile(r"^in-reply-to:\s*(\S+)\s*$", re.M)
#: زمنُ الإيداع من الاسم (`YYYYMMDD-HHMM`) — يُقارَن نصّاً (والترتيبُ النصّيُّ ترتيبٌ زمنيّ هنا).
STAMP_RE = re.compile(r"^(\d{8}-\d{4})")
#: لحظةُ كتابة القاعدة: ما هبط بعدها يحمل شاهدَه. وما قبلها دَينٌ تاريخيٌّ يُقاس (البند ١).
#: (وهي **دقيقةُ الالتزام الذي فيه هذا الحارس** — لا لحظةٌ مُختارةٌ لتُعفِي جواباً بعينه: أيُّ جوابٍ يهبط
#: معه أو بعده مُخاطَبٌ بالقاعدة.)
WITNESS_FROM = "20260925-0446"
#: **الثابتان المُقابَلان بالقياس** (لا ادّعاءَ بلا معدود): دَينُ ما قبل القاعدة، وعددُ المُخاطَبين بها.
PRE_RULE_ANSWERS = 15
SUBJECTS_LANDED = 0
#: الحارسُ الدائريُّ الذي سُحب — يُقاس غيابُه فلا يعود صامتاً من بابٍ خلفيّ (البندُ ٤ من عِلّته).
RETIRED_GATE = "tests/test_review_landing.py"


def tree_files(root: Path = ROOT) -> set[str]:
    """ملفّاتُ الشجرة المُودَعة (`HEAD`) — فشلٌ **مُغلَق** إن تعذّر القياس (قاعدة ٢٦: لا فحصَ بلا مصدر)."""
    proc = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", "HEAD"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(f"تعذّر قراءة الشجرة المُودَعة ⇒ لا قياس: {proc.stderr.strip()[:160]}")
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def _in_index(path: str, root: Path = ROOT) -> bool:
    """هل الملفُّ في **الفهرس** (الشجرةُ التي ستُودَع)؟ — المقياسُ الصحيحُ لِـ«أُعيد إدخالُه».

    (لا `HEAD`: حذفٌ مُدرَجٌ لم يُودَع بعد ليس عودةً للدائرة، والأهمُّ أنّ الفهرسَ هو ما سيصير الشجرةَ.)
    """
    proc = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--", path],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(f"تعذّر قراءة الفهرس ⇒ لا قياس: {proc.stderr.strip()[:160]}")
    return bool(proc.stdout.strip())


def box_answers(tree: set[str]) -> dict[str, str]:
    """(المسارُ، النصُّ) لكل جوابٍ للمنفّذ في الشجرة المُودَعة — يُقرأ من الشجرة لا من اسمٍ مكتوب."""
    out: dict[str, str] = {}
    for path in sorted(tree):
        if not path.startswith(BOX) or ANSWER_MARK not in path or not path.endswith(".md"):
            continue
        out[path] = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    return out


def stamp_of(path: str) -> str:
    """زمنُ الإيداع المُعلَن في الاسم — `""` يعني اسماً بلا زمنٍ (قديمٌ قبل اصطلاح الترقيم)."""
    m = STAMP_RE.match(Path(path).name)
    return m.group(1) if m else ""


def ungated_answers(answers: dict[str, str], tree: set[str], since: str = WITNESS_FROM) -> list[str]:
    """كلُّ جوابٍ هبط بعد القاعدة **ولا يُعلن شاهداً موجوداً في الشجرة** — (دالّةٌ خالصةٌ ⇒ تُقاس بسمّ).

    وهي **قلبُ الاتّجاه**: تسقط على الجواب الذي يشير إلى مراجعةٍ لم تهبط، وتمرّ على الفرع الذي أنزلها.
    """
    out: list[str] = []
    for path, body in answers.items():
        stamp = stamp_of(path)
        if not stamp or stamp < since:                       # دَينٌ تاريخيٌّ قبل القاعدة (البندُ ١)
            continue
        m = WITNESS_RE.search(body)
        if not m:
            out.append(f"{path} · بلا إعلانِ شاهد (`in-reply-to:`)")
            continue
        witness = m.group(1).strip()
        if witness not in tree:
            out.append(f"{path} · يشير إلى {witness} وهو غيرُ موجودٍ في الشجرة المدفوعة")
    return sorted(out)


def _subjects(answers: dict[str, str], since: str = WITNESS_FROM) -> list[str]:
    return sorted(p for p in answers if (s := stamp_of(p)) and s >= since)


def test_every_landed_answer_names_a_witness_in_the_same_tree():
    """الجوابُ يُعلن شاهدَه، والشاهدُ في الشجرة نفسِها ⇒ لا يُجاب حُكمٌ لم يهبط (نصُّ §٢٧)."""
    tree = tree_files()
    answers = box_answers(tree)
    assert answers, "لم أقرأ أيَّ جوابٍ للمنفّذ من الشجرة المُودَعة ⇒ فشلٌ مُغلَق (لا أُعلن حَرْساً على فراغ)"
    bad = ungated_answers(answers, tree)
    assert not bad, ("أجوبةٌ لا تُسمّي شاهداً موجوداً في الشجرة ⇒ يُجاب حُكمٌ لم يهبط (P-9):\n  "
                     + "\n  ".join(bad))


def test_the_rule_is_not_silent_about_its_subjects():
    """**لا ادّعاءَ حَرْسٍ بلا معدود**: العددُ المُقاس يُقابَل بالثابت المُعلَن في الاتّجاهين.

    فحين يهبط أوّلُ جوابٍ بعد القاعدة يصرخ هذا الضابطُ (فلا تمرّ قاعدةٌ فارغةٌ بصمت)، وحين يُنزَع جوابٌ
    قديمٌ من الشجرة يقول «كشفٌ فقدناه». والثابتُ يُحدَّث **في الالتزام نفسه** — لا في جولةٍ لاحقة.
    """
    answers = box_answers(tree_files())
    pre = [p for p in answers if not (s := stamp_of(p)) or s < WITNESS_FROM]
    assert len(pre) == PRE_RULE_ANSWERS, (
        f"دَينُ ما قبل القاعدة تغيّر: المُقاس {len(pre)} والمُعلَن {PRE_RULE_ANSWERS} ⇒ هبط جوابٌ قديمٌ أو "
        f"نُزع (المُنزَّعُ يُعلَن في `handoff/RENAMES.md`)")
    subjects = _subjects(answers)
    assert len(subjects) == SUBJECTS_LANDED, (
        f"المُخاطَبون بالقاعدة تغيّروا: المُقاس {len(subjects)} والمُعلَن {SUBJECTS_LANDED} ⇒ "
        f"حدِّث الثابتَ في الالتزام نفسِه: {subjects}")


def test_the_gate_bites_on_the_class_it_closes():
    """**السمُّ في الذاكرة** — ثلاث حالات، وبدونها يصير الحارسُ ادّعاءً:

    (أ) جوابٌ يشير إلى مراجعةٍ **لم تهبط** ⇒ يسقط (وهو بعينه ما كانت تفعله البوّابةُ الدائريّة بالفرع،
    لكن بالعكس: كانت تُسقط الفرعَ الذي **يحمل** المراجعة، وهذه تُسقط الجوابَ الذي **يدّعي** وجودها).
    (ب) الشاهدُ في الشجرة ⇒ يمرّ (فالفرعُ الذي أنزل المراجعةَ لا يُعاقَب).
    (ج) جوابٌ **بلا** إعلانِ شاهدٍ ⇒ يسقط (وإلّا فالحقلُ زينةٌ يُسقَط بالسكوت عنه).
    """
    tree = {"handoff/sulaiman/20260925-0600-REPORT-to-claude-x.md",
            "handoff/claude/20260925-0559-third-eye-review-58-ar.md"}
    assert ungated_answers({}, tree) == []
    # (أ) الشاهدُ غائبٌ عن الشجرة ⇒ يسقط، **وهو الحالةُ التي كان الفرعُ يموت بها قبل الإصلاح**
    absent = {"handoff/sulaiman/20260925-0601-REPORT-to-claude-y.md":
              "id: y\nin-reply-to: handoff/claude/20260925-0700-third-eye-review-59.md\n"}
    assert ungated_answers(absent, tree) == [
        "handoff/sulaiman/20260925-0601-REPORT-to-claude-y.md · يشير إلى "
        "handoff/claude/20260925-0700-third-eye-review-59.md وهو غيرُ موجودٍ في الشجرة المدفوعة"]
    # (ب) الشاهدُ موجودٌ ⇒ يمرّ (فلا موتَ دائريّاً للفروع)
    present = {"handoff/sulaiman/20260925-0602-REPORT-to-claude-z.md":
               "in-reply-to: handoff/claude/20260925-0559-third-eye-review-58-ar.md\n"}
    assert ungated_answers(present, tree) == []
    # (ج) بلا إعلانٍ أصلاً ⇒ يسقط
    silent = {"handoff/sulaiman/20260925-0603-REPORT-to-claude-w.md": "لا حقلَ شاهد\n"}
    assert ungated_answers(silent, tree) == [
        "handoff/sulaiman/20260925-0603-REPORT-to-claude-w.md · بلا إعلانِ شاهد (`in-reply-to:`)"]
    # (هـ) شاهدٌ **موجودٌ في الشجرة** لسطرٍ سليم ⇒ لا يسقط (ولا يُسقط جيرانَه): القياسُ لكلّ جوابٍ وحده
    assert ungated_answers({**present, **absent}, tree) == [
        "handoff/sulaiman/20260925-0601-REPORT-to-claude-y.md · يشير إلى "
        "handoff/claude/20260925-0700-third-eye-review-59.md وهو غيرُ موجودٍ في الشجرة المدفوعة"]
    # (د) ما قبل القاعدة لا يُطالَب بشيء (البند ١) — وإلّا لَطوّقنا التاريخَ بأثرٍ رجعيّ
    assert ungated_answers({"handoff/sulaiman/20260925-0400-REPORT-to-claude-old.md": "قديمٌ"}, tree) == []


def test_the_circular_gate_is_retired_and_cannot_return_silently():
    """**الصنفُ لا يُعاد**: الحارسُ الذي يقيس مكانَ الوجود (مقابل `origin/main`) سُحب ⇒ يُقاس غيابُه.

    (ولماذا يحرس الضابطُ شيئاً منزوعاً: لأنّ إعادةَ إدخالِه هي الطريقُ الأقصرُ لِـ«إصلاح» أيّ فشلٍ مستقبليّ
    في الـCI — فتُعاد الدائرةُ التي منعت مراجعةَ ٥٦ و٥٧ من الهبوط. والغيابُ المقيسُ يمنع ذلك.)

    **والمقياسُ: الفهرسُ والقرصُ لا `HEAD`** — لأنّ المقياسَ الصحيحَ هو «الشجرةُ التي ستُودَع» (وهو نفسُ
    منهجِ خطّاف ما قبل الالتزام: `--staged`)، ولأنّ حذفاً مُدرَجاً لم يُودَع بعد **ليس عودةً للدائرة**.
    """
    on_disk = (ROOT / RETIRED_GATE).exists()
    staged = _in_index(RETIRED_GATE)
    assert not on_disk and not staged, (
        f"{RETIRED_GATE} عاد إلى الشجرة (قرص={on_disk} · فهرس={staged}) ⇒ البوّابةُ الدائريّةُ التي يُعلَن "
        f"عنها في مراجعة ٥٧ عادت (شرطُ «موجودٌ في `origin/main` مسبقاً» لا يملكه فرعٌ يحمل مراجعةً جديدة)")
    for wf in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        text = wf.read_text(encoding="utf-8")
        assert Path(RETIRED_GATE).name not in text, f"{Path(RETIRED_GATE).name} ما زال في قائمة الـCI ({wf.name})"
    doc = (ROOT / "docs" / "GATES.md").read_text(encoding="utf-8")
    assert Path(RETIRED_GATE).name not in doc, (
        "السجلُّ ما زال يشير إلى الحارس الدائريّ ⇒ وثيقةٌ تُرسل القارئَ إلى حَرْسٍ منزوع")
