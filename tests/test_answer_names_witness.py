"""**الجوابُ يُسمّي شاهدَه** — الحارسُ الذي حلَّ محلَّ `tests/test_review_landing.py` (R57-1).

**العلّةُ المقيسة** (قاسها المدقّق في مراجعة ٥٧ وسمّاها *the witness cannot land*): الحارسُ السابق اشترط أن
يكون **كلُّ** ملفٍّ في `handoff/claude/` موجوداً في `origin/main` **مسبقاً** — شرطٌ لا يملكه الفرعُ الذي
يحمل المراجعةَ الجديدة **بحكم تعريفه** ⇒ كلُّ مراجعةٍ جديدة تُسقط الـCI، وحمايةُ `main` تشترط الفحصَ الأخضر
(`strict` · `enforce_admins`) ⇒ **يُمنَع هبوطُ المراجعة، ويُمنَع الامتثالُ لِـ§٢٧ بالحارسِ المكتوبِ لفرضها** —
وهو الصنفُ نفسُه الذي سُحب في `231f17f`. وعلى `main` نفسِه كان ينجح **دون أن يقيس شيئاً**: كلُّ ملفٍّ فيه
موجودٌ فيه بحكم التعريف. أي أنّ العطبَ **الجذريَّ** لم يكن في التنفيذ بل في **الاتّجاه**: حارسٌ يقيس
**مكانَ الوجود** (سؤالٌ لا يملك الفرعُ جوابَه) بدل أن يقيس **الرابطَ** (سؤالٌ يملكه الطرفان).

**الثابتُ الجديد:** كلُّ جوابٍ على مراجعة (ملفٌّ في `handoff/sulaiman/` اسمُه يحمل `REPORT-to-claude`)
**يُعلن شاهدَه** بحقلِ `in-reply-to:` بمسار المراجعة، **والمسارُ موجودٌ في الشجرة المدفوعة نفسِها** (هدفُ
§٢٧: «الشاهدُ يُدفَع قبل أن يُجاب»). وهذا الفحصُ **مُتاحٌ للفرع** — لا يطلب من الفرع ما لا يملكه — ويسقط عند
الانحدار: جوابٌ يشير إلى مراجعةٍ لم تهبط ⇒ **يسقط**، والفرعُ الذي يُنزل المراجعةَ **يمرّ**.

**وصيغةُ الحقل المقبولة (ST-5 · قاسه مقعد البنية):** سطرٌ يبدأ بـ`in-reply-to:` (**غيرُ حسّاسٍ لحالة
الأحرف**) وقيمتُه **مسارٌ واحد** بلا فراغ، أو مغلَّفٌ زاويّاً `<مسار>` كما تكتبه الوثيقة، **وما بعد المسار
يُهمَل** (تعليقٌ/مرجع). وكان المفهومُ من الوثيقة (`<مسار>`) يُسقط الـCI **برسالةٍ تُشخّص الخطأَ خطأً**
(«يشير إلى `<مسار>` وهو غيرُ موجود») ⇒ الآن رسالتان مختلفتان: «بلا إعلان»، و«يشير إلى مسارٍ غيرِ موجود».

**الحدودُ المُعلَنة (وإلّا صار الحارسُ ادّعاءً أوسعَ من مداه):**
1. القاعدةُ تسري على ما هبط **بعد** `WITNESS_FROM`؛ وما قبله **دَينٌ تاريخيٌّ معلَن** (`PRE_RULE_ANSWERS`
   يُقاس ويُقابَل — لا يُخفى ولا يُوصَف «نظافة»).
2. عددُ المُخاطَبين بالقاعدة يُقاس ويُقابَل بالثابت (`SUBJECTS_LANDED`) ⇒ لا قاعدةَ صامتةٌ على فراغ
   (وحين يهبط أوّلُ جوابٍ يصرخ الضابطُ فيُقرَن الشاهدُ ويُحدَّث الثابتُ في الالتزام نفسه — وهو صنفُ
   «سقفِ معدّلِ المعرّفات الغريبة» القائم في المستودع).
3. يُقابَل **وجودُ المسار** و**مقامُه** (تحت `handoff/claude/`: الحُكمُ يُصدره المدقّق)، لا صحّةُ كونِه
   المراجعةَ **المقصودة بعينها** (غيرُ قابلٍ للقياس آليّاً — يُعلَن).
4. والقياسُ على **الشجرة المُودَعة (`HEAD`)** لا على قرص الكاتب: ما لم يُودَع لا يُقاس. وهذا حدُّ الاتّجاهين
   معاً — لا «تذكيرٌ محلّيّ» يُتجاهَل، ولا موتٌ دائريٌّ للفروع.
5. صندوقُ المدقّق (`handoff/claude/`) خارج هذا الاتّجاه: المراجعةُ **تُصدر** حُكماً ولا تُجيب عنه.
6. **وحدُّ الصنف (SP-2 · قاسه مقعد المواصفة):** المُخاطَبون = ما اسمُه يحمل `ANSWER_MARK`؛ وجوابٌ سُمّي بغير
   ذلك (`…-ANSWER-58-…`) لا يُطالَب — **لكنّه حدٌّ يُقاس لا صامت** (`NON_ANSWER_FILES_SINCE_RULE`): كلُّ
   ملفٍّ في الصندوق هبط بعد القاعدة وليس من الصنف يُقابَل بالعدّاد، فالزيادةُ تُصرخ ليقرّر الكاتبُ: يُسمّيه
   جواباً بشاهد، أو يُعلن صنفَه ويُحدّث العدّاد في الالتزام نفسِه.
7. و`WITNESS_FROM` **مكتوبٌ بيدٍ لا مُشتقّ** (الالتزامُ الحاملُ للحارس قد يُعاد تركيبُه فيتغيّر زمنُه) —
   ويُقاس **موضعُه** بدلاً من وصْفِه: بعد آخرِ جوابٍ قديم، ولا جوابَ في الفراغ بينهما.
8. **والشاهدُ الذاتيُّ لا يعدو دليلَه (R58-2 · قاسه المدقّق في مراجعة ٥٨):** `in-reply-to` يشير إلى **الملفّ
   نفسِه**، أو إلى **قرار المنفّذ**، أو إلى أيّ مسارٍ خارج صندوق الأحكام ⇒ **يُسقط** (وكان الثلاثةُ تمرّ:
   شرطُ «أيُّ مسارٍ موجود» فقط). ومن **أعلن صنفَه** («لا يُجيب حُكمًا») لا يُطالَب بشاهدِ حُكم — **ويُقابَل
   بعدّاد** (`DECLARED_NON_VERDICT_ANSWERS`)، فلا إعفاءَ صامت.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOX = "handoff/sulaiman/"
ANSWER_MARK = "REPORT-to-claude"
#: حقلُ الشاهد: سطرٌ يبدأ بالحقل، وقيمتُه مسارٌ واحد (أو مغلَّفٌ `<…>`)، وما بعد المسار يُهمَل (ST-5).
WITNESS_RE = re.compile(r"^in-reply-to:\s*(.+?)\s*$", re.M | re.I)
#: **الشاهدُ حُكمٌ لا أيُّ مسار (R58-2 · قاسه المدقّق في مراجعة ٥٨):** كان الفحصُ يقبل أيَّ مسارٍ موجودٍ في
#: الشجرة — **قرارَ المنفّذ نفسِه** · `README.md` · وحتى **الجوابَ نفسَه** ⇒ فقاعدةُ §٢٧ («يُسمّي الحُكمَ
#: الذي يُجيبه») لم تكن مقيسةً أصلًا. والشاهدُ الآن **تحت صندوق الأحكام** حصرًا.
WITNESS_ROOT = "handoff/claude/"
#: **وصنفٌ مُعلَنٌ بديل — بالهويّة لا بالعدد (S-3 · P2-5 · مقعدا المعايير والبنية):** تقريرٌ إلى المدقّق
#: **لا يُجيب حُكمًا** يُعلن ذلك **بحقلٍ في ترويسته** (`class:`)، ويُقابَل **باسمِ الملفّ** لا بعدّادٍ ⇒
#: فلا يُنقل الإعلانُ إلى جوابٍ آخر، ولا تُغطّي عبارةٌ في متنٍ إعفاءً (كان `CLASS_DECL_RE` يطابق نصًّا حيث
#: ورد — ونقلُ العبارة مع ثبات العدّاد كان يمرّ صامتاً).
CLASS_DECL_RE = re.compile(r"^\s*class\s*:\s*\S+", re.M | re.I)
#: ملفُّ الصنف المُعلَن **بالاسم** — ويُشترَط ألّا يحمل `in-reply-to` (وإلّا صار الإعلانُ غطاءً على حُكم).
DECLARED_NON_VERDICT = (
    "handoff/sulaiman/20260925-0723-REPORT-to-claude-r13-green-gate-three-root-causes-and-three-seat-review.md",
)
#: **والشاهدُ يُدفَع قبل أن يُجاب (نصُّ §٢٧ حرفيًّا · مقعدُ المعايير S-1):** كان الفحصُ يقبل أيَّ حُكمٍ
#: موجود حتى لو أُودِع **بعد** الجواب ⇒ فيُصدّق الرابطَ الخطأ (حُكمٌ لاحقٌ لا يُجيب السؤالَ المطروح).
#: والآن يُقاس الزمنُ: زمنُ الحُكم ≤ زمنُ الجواب (والزمنُ من اسم الملفّ بمصدرٍ واحد: `stamp_of`).
#: لحظةُ كتابة القاعدة: ما هبط بعدها يحمل شاهدَه. وما قبلها دَينٌ تاريخيٌّ يُقاس (البند ١).
#: **والقيمةُ مكتوبةٌ بيدٍ لا مُشتقّةٍ من زمن الالتزام** (S-2: `--rebase`/`amend` تُغيّر زمنَه فلا يستقرّ
#: اشتقاقٌ منه) — وموضعُها مُقاسٌ بالبند ٧: دقيقتُها `20260925-0446` (والثابتُ بستّ خانات: `20260925-044600`)
#: هي دقيقةُ إغلاق الجولة، وقِيس أنّها بعد آخرِ
#: جوابٍ قديم (٠٣:٥٨) وبلا جوابٍ في الفراغ بينهما ⇒ **لا جوابَ يُعفى بحكم ترتيب الحدّ**.
WITNESS_FROM = "20260925-044600"
#: **الثوابت المُقابَلة بالقياس** (لا ادّعاءَ بلا معدود): دَينُ ما قبل القاعدة · عددُ المُخاطَبين بها ·
#: وملفّاتُ الصندوق بعد القاعدة خارج الصنف المُعلَن (البند ٦).
PRE_RULE_ANSWERS = 15
SUBJECTS_LANDED = 1
NON_ANSWER_FILES_SINCE_RULE = 5
#: (١ = تقريرُ الإغلاق إلى المالك `20260925-0520-REPORT-to-owner-…` · ٢ = قرارُ التكليف
#: `20260925-0540-DECISION-to-claude-…` · ٣ = تقريرُ البندين ①/② إلى المالك
#: `20260925-1330-REPORT-to-owner-flake-policy-closed-and-encrypted-backup-to-drive.md`
#: · ٤ = تقريرُ إغلاق بنود المقاعد الثلاثة `20260925-1340-REPORT-to-owner-three-seat-closures-…`
#: · ٥ = تقريرُ الجولة ٥٩ (إغلاقُ بنود مراجعة الكود) `20260925-1520-REPORT-to-owner-round-59-…`
#: — وكلُّها **صنفٌ مُعلَنٌ بالاسم** لا صامت.)
#: **ومُخاطَبٌ واحدٌ هبط بالقاعدة، وهو صنفٌ مُعلَنٌ بالاسم:** `20260925-0723-REPORT-to-claude-r13-…`
#: (يُعلن `class:` ولا يُجيب حُكماً — R58-2). وبعده (مراجعة ٥٩ · مقعدا المعايير والبنية) صار الشاهدُ في
#: حقله يُسقطه: **الإعلانُ مع استشهادٍ = غطاء، لا صنف** ⇒ فلم يبقَ مُخاطَبٌ بشاهدٍ حُكم في الشجرة،
#: والعدُّ **بالهويّة** لا بعدّاد (S-3/P2-5: نقلُ الإعلان إلى جوابٍ آخر كان يمرّ بعدّادٍ ثابت).
#: الحارسُ الدائريُّ الذي سُحب — يُقاس غيابُه فلا يعود صامتاً من بابٍ خلفيّ (البندُ ٤ من عِلّته).
RETIRED_GATE = "tests/test_review_landing.py"


def _turn():
    """`tools/turn.py` — **مصدرٌ واحد** لنمط الاسم وموحِّدِه (ST-4 · مقعد البنية: نسخةٌ ثانية محليّةٌ أضيقُ
    من مصدرها تُنتج تصنيفَين متناقضين للاسم نفسه — الثواني واصطلاحُ `24:00`).
    """
    spec = importlib.util.spec_from_file_location("turn", ROOT / "tools" / "turn.py")
    assert spec is not None and spec.loader is not None, "تعذّر تحميلُ `tools/turn.py` ⇒ لا قياس"
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_STAMP = _turn().stamp_of          # نمطُ الاسم وموحِّدُه: **مصدرٌ واحد** في `tools/turn.py` (ST-4)


def stamp_of(path: str) -> str | None:
    """زمنُ الإيداع المُعلَن في **الاسم** (بستّ خانات) — أو `None` إن كان الاسمُ بلا زمن.

    (والمصدرُ `tools/turn.py` — لا نسخةٌ محليّةٌ أضيقُ منه: قِيس تناقضٌ في اصطلاح `24:00` والثواني، ST-4.)
    """
    return _STAMP(Path(path).name)


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


def _witness_path(raw: str) -> str:
    """المسارُ من قيمة الحقل: يُقشَّر الغلافُ الزاويّ `<…>` (كما في الوثيقة) ويُقتطع أوّلُ رمزٍ (ST-5)."""
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1:value.index(">")].strip()
    parts = value.split()
    return parts[0] if parts else ""


def ungated_answers(answers: dict[str, str], tree: set[str], since: str = WITNESS_FROM) -> list[str]:
    """كلُّ جوابٍ هبط بعد القاعدة **ولا يُسمّي حُكماً موجوداً في الشجرة** — (دالّةٌ خالصةٌ ⇒ تُقاس بسمّ).

    وهي **قلبُ الاتّجاه**: تسقط على الجواب الذي يشير إلى مراجعةٍ لم تهبط، وتمرّ على الفرع الذي أنزلها.
    **وحدُّ الشاهد (R58-2):** مسارٌ تحت `handoff/claude/` — فقرارُ المنفّذ و`README.md` والجوابُ نفسُه
    تُسقطه (شاهدٌ لا يعدو دليلَه). **وثلاثةُ قيودٍ من مراجعة ٥٩ (كلُّها بقياس):** ‹١› **الشاهدُ يُدفَع قبل أن
    يُجاب** (زمنُ الحُكم ≤ زمنُ الجواب — S-1)، ‹٢› **والصنفُ المُعلَن بالهويّة**: ملفٌّ واحدٌ مُسمّى يُعلن
    `class:` فلا يُطالَب بشاهد، و**ولا يُقبل منه استشهاد** (إعلانٌ مع شاهد = غطاء — S-3)، ‹٣› و**فحصُ
    الشكل** (نمطُ الحقول) سقط من `tools/turn.py` لصالح فحص الهويّة، فلا معجمَ حقولٍ ثانياً يُقاس هنا.
    """
    out: list[str] = []
    for path, body in answers.items():
        stamp = stamp_of(path)
        if not stamp or stamp < since:                       # دَينٌ تاريخيٌّ قبل القاعدة (البندُ ١)
            continue
        declared = path in DECLARED_NON_VERDICT
        m = WITNESS_RE.search(body)
        if declared and m:
            out.append(f"{path} · الصنفُ المُعلَنُ يحمل شاهداً (`in-reply-to:`) — إعلانٌ مع استشهادٍ غطاءٌ "
                       f"لا صنف (فالصنفُ معناه: لا يُجيب حُكماً)")
            continue
        if not m:
            if declared:
                continue                                     # صنفٌ مُعلَنٌ **بالاسم** (لا إعفاءَ بعدّاد)
            out.append(f"{path} · بلا إعلانِ شاهد (`in-reply-to:`)")
            continue
        witness = _witness_path(m.group(1))
        if not witness:
            out.append(f"{path} · سطرُ الشاهد فارغ (لا مسار)")
            continue
        if witness == path:
            out.append(f"{path} · الشاهدُ هو الملفُّ نفسُه (شاهدٌ ذاتيّ لا يعدو دليلَه)")
            continue
        if witness not in tree:
            out.append(f"{path} · يشير إلى «{witness}» وهو غيرُ موجودٍ في الشجرة المدفوعة")
            continue
        if not witness.startswith(WITNESS_ROOT):
            out.append(f"{path} · الشاهدُ «{witness}» ليس حُكماً: لا يقع تحت `{WITNESS_ROOT}` "
                       f"(الحُكمُ يُصدِره المدقّق؛ والقرارُ والتوجيهُ ليسا حُكماً)")
            continue
        w_stamp = stamp_of(witness)
        if w_stamp and w_stamp > stamp:
            out.append(f"{path} · الشاهدُ «{witness}» أُودِع **بعد** الجواب ({w_stamp} > {stamp}) — "
                       f"§٢٧: الشاهدُ يُدفَع قبل أن يُجاب")
    return sorted(out)


def test_the_witness_must_be_a_verdict_not_any_path_in_the_tree():
    """**R58-2 (قاسه المدقّق في مراجعة ٥٨)** — كان الفحصُ يقبل **أيَّ** مسارٍ موجود: قرارَ المنفّذ ·
    `README.md` · وحتى الجوابَ نفسَه ⇒ فقاعدةُ §٢٧ («يُسمّي الحُكمَ الذي يُجيبه») لم تكن مقيسة. وهذه
    أشواكُها الأربعة صريحةً — ولها **رسالتان مختلفتان** (شاهدٌ ذاتيّ ≠ شاهدٌ ليس حُكماً).
    """
    witness = "handoff/claude/20260925-021953-third-eye-review-55-the-turn-that-cannot-see-me.md"
    self_path = "handoff/sulaiman/20260925-0601-REPORT-to-claude-s.md"
    decision = "handoff/sulaiman/20260925-0540-DECISION-to-claude-land-on-the-pushed-branch.md"
    tree = {self_path, witness, "README.md", decision}

    def only_one(target: str) -> str:
        got = ungated_answers({self_path: f"in-reply-to: {target}\n"}, tree)
        assert len(got) == 1, (target, got)
        return got[0]

    # (١) حُكمٌ حقيقيٌّ في صندوق المدقّق ⇒ يمرّ (فلا موتَ دائريّاً للفروع)
    assert ungated_answers({self_path: f"in-reply-to: {witness}\n"}, tree) == []
    # (٢) **قرارُ المنفّذ نفسِه** — الحالةُ الحقيقيّةُ التي كانت تمرّ في الشجرة ⇒ تسقط: ليس حُكماً
    assert "ليس حُكماً" in only_one(decision)
    # (٣) وثيقةٌ عامّةٌ في الجذر ⇒ تسقط للسبب نفسه
    assert "ليس حُكماً" in only_one("README.md")
    # (٤) والجوابُ نفسُه ⇒ **رسالةٌ مختلفة**: شاهدٌ ذاتيّ (لا يُشخَّص «ليس حُكماً»)
    assert "نفسُه" in only_one(self_path)
    # (٥) **وحُكمٌ أُودِع بعد الجواب (S-1 · مراجعة ٥٩)**: الموجودُ يكفي عند الفحص القديم فيُصدّق رابطةً لا
    #     تُجيب السؤال؛ والآن يُقاس الزمنُ (§٢٧: الشاهدُ يُدفَع **قبل** أن يُجاب).
    late = "handoff/claude/20260925-0900-third-eye-review-56-after-the-answer.md"
    got = ungated_answers({self_path: f"in-reply-to: {late}\n"}, tree | {late})
    assert len(got) == 1 and "بعد" in got[0], got


def test_the_declared_class_is_an_identity_and_admits_no_shield():
    """**الصنفُ المُعلَن (R58-2 · ثمّ الهويّة في مراجعة ٥٩ · S-3/P2-5):** تقريرٌ لا يُجيب حُكمًا يُعلن
    `class:` فيُعفى من الشاهد — **باسمِه لا بعبارةٍ في متنه**، و**ولا يُقبل منه استشهاد** (وإلّا صار الإعلانُ
    غطاءً يُجيز الإجابةَ ويُخفيها في آنٍ). وكان العدُّ بعدّادٍ ثابت: نقلُ العبارة إلى جوابٍ آخر + استشهادُ
    المُعلِن القديم بأيّ حُكمٍ موجود كان يمرّ صامتاً.
    """
    verdict = "handoff/claude/20260925-021953-third-eye-review-55-x.md"
    declared_path = DECLARED_NON_VERDICT[0]
    other = "handoff/sulaiman/20260925-0603-REPORT-to-claude-w.md"
    tree = {declared_path, other, verdict}
    body = "```\nid:      20260925-0723-sulaiman\nclass:   تقريرٌ لا يُجيب حُكماً\n```\n\nهذا تقريرُ إغلاقٍ\n"
    assert ungated_answers({declared_path: body}, tree) == [], "الصنفُ المُعلَنُ بالاسم لم يُقبل"
    # **والاستشهادُ مع الإعلان غطاء** (حتى لو كان الشاهدُ حُكماً حقيقياً موجوداً)
    got = ungated_answers({declared_path: body + f"in-reply-to: {verdict}\n"}, tree)
    assert len(got) == 1 and "غطاء" in got[0], got
    # **ونصُّ العبارة نفسُه في ملفٍّ غير مُعلَن لا يُعفي** (كان يُعفي حين كان المقياسُ النصّ لا الهويّة)
    got = ungated_answers({other: body}, tree)
    assert len(got) == 1 and "بلا إعلانِ شاهد" in got[0], got
    # **والشجرةُ الحقيقيّة تُقابَل بالهويّة**: كلُّ مُعلَنٍ بالاسم يحمل `class:` وبلا استشهاد — والعكس
    bodies = box_answers(tree_files())
    declared = sorted(p for p, t in bodies.items() if CLASS_DECL_RE.search(t) or p in DECLARED_NON_VERDICT)
    assert declared == sorted(DECLARED_NON_VERDICT), (
        f"المُعلِنون صنفَهم تغيّروا: المُقاس {declared} والمُعلَن {sorted(DECLARED_NON_VERDICT)} ⇒ "
        f"يُحدَّث الثابتُ في الالتزام نفسه (الإعلانُ صنفٌ مُعلَنٌ بالهويّة لا إعفاءٌ صامت)")
    for p in DECLARED_NON_VERDICT:
        assert CLASS_DECL_RE.search(bodies.get(p, "")), f"«{p}» مُعلَنٌ في الثابت بلا حقل `class:`"
        assert not WITNESS_RE.search(bodies.get(p, "")), f"«{p}» مُعلَنٌ صنفاً **ويستشهد** بحُكم (غطاء)"


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


def test_the_cutoff_exempts_no_answer_by_accident():
    """**S-2 (قاسه مقعد المعايير)**: الحدُّ مكتوبٌ بيدٍ لا مُشتقّ (وسببُه مُعلَن في ترويسته) — فيُقاس
    **موضعُه**: بعد آخرِ جوابٍ قديم، ولا جوابَ في الفراغ بينهما ⇒ **لا جوابَ يُعفى بحكم ترتيب الحدّ**
    (وهو ما كان قائماً: «٠٤:٤٦» قبل زمن الالتزام الحامل للحارس بـ٤ دقائق).
    """
    answers = box_answers(tree_files())
    stamps = sorted(s for p in answers if (s := stamp_of(p)))
    assert stamps, "لا جوابَ مُرقَّمٌ في الصندوق ⇒ فشلٌ مُغلَق"
    pre = [s for s in stamps if s < WITNESS_FROM]
    assert pre, "لا جوابَ قبل الحدّ ⇒ فشلٌ مُغلَق (حدٌّ بلا مقام)"
    gap = [s for s in stamps if max(pre) < s < WITNESS_FROM]
    assert not gap, (f"أجوبةٌ في فراغ الحدّ {gap} ⇒ إعفاءٌ بحكم ترتيب الحدّ لا بحكم القاعدة "
                     f"(الحدُّ {WITNESS_FROM} وآخرُ ما قبله {max(pre)})")


def test_the_answer_class_is_measured_not_assumed():
    """**SP-2 (قاسه مقعد المواصفة)**: الصنفُ المُخاطَب = ما اسمُه يحمل `ANSWER_MARK` — وهذا **يُقاس** بعد
    القاعدة: كلُّ ملفٍّ رقمٌ في الصندوق ليس من الصنف يُقابَل بالعدّاد، فالزيادةُ (صنفٌ جديد من الأجوبة)
    تُصرخ بدل أن تمرّ صامتةً خارجَ الحَرْس.
    """
    tree = tree_files()
    known = set(box_answers(tree))
    since = sorted(p for p in tree
                   if p.startswith(BOX) and p.endswith(".md")
                   and (s := stamp_of(p)) and s >= WITNESS_FROM)
    others = [p for p in since if p not in known]
    assert len(others) == NON_ANSWER_FILES_SINCE_RULE, (
        f"ملفّاتٌ في صندوق المنفّذ هبطت بعد القاعدة وليست من صنف `{ANSWER_MARK}`: {others} ⇒ "
        f"إمّا يُسمّى جواباً يُعلن شاهدَه، وإمّا يُعلن صنفُه بالعدّاد في الالتزام نفسِه")


def test_the_gate_bites_on_the_class_it_closes():
    """**السمُّ في الذاكرة** — حالاتٌ ستّ، وبدونها يصير الحارسُ ادّعاءً:

    (أ) جوابٌ يشير إلى مراجعةٍ **لم تهبط** ⇒ يسقط (وهو بعينه ما كانت تفعله البوّابةُ الدائريّة بالفرع،
    لكن بالعكس: كانت تُسقط الفرعَ الذي **يحمل** المراجعة، وهذه تُسقط الجوابَ الذي **يدّعي** وجودها).
    (ب) الشاهدُ في الشجرة ⇒ يمرّ (فالفرعُ الذي أنزل المراجعةَ لا يُعاقَب).
    (ج) جوابٌ **بلا** إعلانِ شاهدٍ ⇒ يسقط (وإلّا فالحقلُ زينةٌ يُسقَط بالسكوت عنه).
    (د) ما قبل القاعدة لا يُطالَب بشيء (البندُ ١) — لا أثرَ رجعيّ. و(هـ) تركيبةُ الإعلانين لا تُسقط جيرانَها.
    (و) الصيغةُ كما تكتبها الوثيقة `<مسار>` ومعها ذيلٌ ⇒ **تُقرأ** (ST-5)، وسطرُ شاهدٍ فارغٌ ⇒ يسقط برسالةٍ
    **مختلفةٍ** عن «بلا إعلان» (لا تُشخَّص الصيغةُ خطأً).
    """
    witness = "handoff/claude/20260925-0559-third-eye-review-58-ar.md"
    tree = {"handoff/sulaiman/20260925-0600-REPORT-to-claude-x.md", witness}
    assert ungated_answers({}, tree) == []
    # (أ) الشاهدُ غائبٌ عن الشجرة ⇒ يسقط، **وهو الحالةُ التي كان الفرعُ يموت بها قبل الإصلاح**
    absent = {"handoff/sulaiman/20260925-0601-REPORT-to-claude-y.md":
              "id: y\nin-reply-to: handoff/claude/20260925-0700-third-eye-review-59.md\n"}
    assert ungated_answers(absent, tree) == [
        "handoff/sulaiman/20260925-0601-REPORT-to-claude-y.md · يشير إلى "
        "«handoff/claude/20260925-0700-third-eye-review-59.md» وهو غيرُ موجودٍ في الشجرة المدفوعة"]
    # (ب) الشاهدُ موجودٌ ⇒ يمرّ (فلا موتَ دائريّاً للفروع)
    present = {"handoff/sulaiman/20260925-0602-REPORT-to-claude-z.md": f"in-reply-to: {witness}\n"}
    assert ungated_answers(present, tree) == []
    # (ج) بلا إعلانٍ أصلاً ⇒ يسقط
    silent = {"handoff/sulaiman/20260925-0603-REPORT-to-claude-w.md": "لا حقلَ شاهد\n"}
    assert ungated_answers(silent, tree) == [
        "handoff/sulaiman/20260925-0603-REPORT-to-claude-w.md · بلا إعلانِ شاهد (`in-reply-to:`)"]
    # (هـ) شاهدٌ سليمٌ لا يُسقط جيرانَه: القياسُ لكل جوابٍ وحده
    assert ungated_answers({**present, **absent}, tree) == [
        "handoff/sulaiman/20260925-0601-REPORT-to-claude-y.md · يشير إلى "
        "«handoff/claude/20260925-0700-third-eye-review-59.md» وهو غيرُ موجودٍ في الشجرة المدفوعة"]
    # (د) ما قبل القاعدة لا يُطالَب بشيء (البند ١) — وإلّا لَطوّقنا التاريخَ بأثرٍ رجعيّ
    assert ungated_answers({"handoff/sulaiman/20260925-0400-REPORT-to-claude-old.md": "قديمٌ"}, tree) == []
    # (و) الصيغةُ الموثَّقة `<مسار>` ومعها ذيلٌ ⇒ تُقرأ (ST-5: كان يُسقط الـCI برسالةٍ تُشخّص خطأً)
    docform = {"handoff/sulaiman/20260925-0604-REPORT-to-claude-v.md":
               f"in-reply-to: <{witness}> (R57-1)\n"}
    assert ungated_answers(docform, tree) == [], "صيغةُ الوثيقة `<مسار>` لم تُقرأ"
    bare = {"handoff/sulaiman/20260925-0605-REPORT-to-claude-u.md": "in-reply-to:   \n"}
    assert ungated_answers(bare, tree) == [
        "handoff/sulaiman/20260925-0605-REPORT-to-claude-u.md · سطرُ الشاهد فارغ (لا مسار)"], \
        "سطرُ شاهدٍ فارغٌ لا يُشخَّص «بلا إعلان» (رسالتان مختلفتان)"


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
