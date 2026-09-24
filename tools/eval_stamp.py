#!/usr/bin/env python3
"""قاعدةُ النشر الواحدة للبصمة — موضعٌ واحد تستدعيه كلُّ أداةٍ تقرأ سجلات تقييم.

**الدرسُ المدفوع (مراجعةُ المقاعد الثلاثة، ٢٠٢٦-٠٩-٢٤):** أداتان في المستودع نفسِه كانتا تقولان **العكس**:
`--rescore` في `tools/eval_questions.py` كان يعدّ البصمةَ **الغائبة** مطابقةً (`not in (None, cur)`)،
و`tools/eval_run_compare.py` يعدّها متقادمة (`unstamped` ⇒ `rc=1`). فقاعدةٌ مكتوبةٌ في موضعين تنقسم.

**والقاعدة:** الغيابُ **لا يُعدّ اتفاقاً**. سجلٌّ بلا بصمةٍ أسوأُ من سجلٍّ ببصمةٍ قديمة: الأولُ لا يُثبت أنّه
أُجيب عن نصٍّ بعينه أصلاً، والثاني يُثبت أنّه أُجيب عن نصٍّ آخر. وكلاهما **لا يُنشر رقمُه**.
"""

from __future__ import annotations

import re

PLACEHOLDER = "؟"          # قيمةٌ بديلةٌ تُرجعت عند تعذّر التقطيع — لا تصلح بصمةً

# **البصمةُ تُعرَف بصيغتها لا بقيمةٍ بعينها.** الدرسُ المدفوع (الجولة ٤٩): كانت القاعدةُ تقارن بمُبدَّلٍ
# عربيٍّ واحد (`؟`) بينما المُنتِجُ في `eval_questions._spec_sha` يُخرج **لاتينيّةً** (`?`) عند فشل القراءة
# ⇒ مرّت بصمةُ الفشل وحُكم بالسجلّ أنه «مطابقٌ للنصّ» وهو لم يُقرأ أصلاً. فالقاعدةُ الآن على **الصيغة**
# (١٢ خانةً ست عشريّة) ⇒ تموت العلّةُ كلُّها لا موضعٌ منها.
SHA_RE = re.compile(r"^[0-9a-f]{12}$")


def is_publishable(rec: dict, cur_sha: str) -> bool:
    """**مطابقةٌ حرفيّةٌ وحسب**، وبصمتَان صحيحتان صيغةً: بلا بصمةٍ (أو بصيغةٍ فاسدةٍ أو بديلة) ⇐ غيرُ قابلةٍ للنشر."""
    v, cur = rec.get("spec_sha"), cur_sha
    return (isinstance(v, str) and isinstance(cur, str)
            and SHA_RE.match(v) is not None and SHA_RE.match(cur) is not None
            and v == cur)


# **قاعدتان مشتركتان** (تُستدعيان من كلّ أداةٍ تقرأ سجلات — فلا تنقسم قاعدةٌ بين موضعين):
# (١) الأثرُ المشكوكُ قصُّه: ٤٠ مرجعًا **بلا `trace_len`** ⇒ كُتب قبل إصلاح القصّ، ويحتمل أن يكون مقطوعًا.
#     كانت هذه القاعدةُ في `--rescore` وحدها ⇒ سجلٌّ لم يُعَد حكمُه يمرّ نظيفًا في أداة المقارنة.
# (٢) السجلُّ المحكوم: لا نائبٌ (`ok is None`) ولا مشكوكُ القصّ.
TRACE_CAP = 40


def is_trace_suspect(rec: dict) -> bool:
    return rec.get("trace_len") is None and len(rec.get("used_row_nos") or []) == TRACE_CAP


def is_substitute(rec: dict) -> bool:
    """نائبٌ لا جواب: مهلةٌ/عطبٌ ⇒ `<...>` أو `ok is None` أو وسمٌ صريحٌ من `--rescore`.

    **ولماذا موضعٌ واحد:** أداةُ المقارنة تقرأ سجلاتٍ **خامّة** لا تحمل وسمَ `--rescore` ⇒ قراءةُ الوسم
    وحده كانت تُدخل النوائبَ في مقامها (٢٧/٤٠ مقابل ٢٧/٣٨) — وهي نفسُ علّة «قاعدةٍ في موضعين» التي
    أمسكتها الجولة ٥٠ في الأثر المشكوك.
    """
    if rec.get("substitute") or rec.get("ok") is None:
        return True
    return str(rec.get("answer") or "").strip().startswith("<")


def is_judged(rec: dict) -> bool:
    """**المحكومُ فعلًا** = لا نائبٌ ولا مشكوكُ القصّ. وهذا **تعريفٌ واحدٌ يستهلكه الجميع**:

    كان `ok is not None and not is_trace_suspect` ⇒ عدّادٌ ثانٍ للمقام يُخالف ما تعدّه أدواتُ القراءة
    (أداةُ المقارنة تطبع ٢٧/٣٨ و`_print_metrics` تطبع ٤٠ من ٥٠ للملفّ نفسه) — وهي علّةُ «مالكين لقاعدة»
    التي أمسكتها مراجعة ٥٠ مرّتين: مرّةً في النائب ومرّةً في المقام.
    """
    return not is_substitute(rec) and not is_trace_suspect(rec)


def classify(records: list[dict], cur_sha: str) -> tuple[list[str], list[str], list[str]]:
    """(المطابقة، البلا-بصمة، المخالفة) — **ثلاثةُ أصنافٍ لا صنفان**: البلا-بصمة يُعدّ ويُسمّى، فلا يُدمج."""
    ok: list[str] = []
    unstamped: list[str] = []
    stale: list[str] = []
    for r in records:
        if is_publishable(r, cur_sha):
            ok.append(str(r.get("id")))
        elif r.get("spec_sha") in (None, "", PLACEHOLDER):
            unstamped.append(str(r.get("id")))
        else:
            stale.append(str(r.get("id")))
    return ok, unstamped, stale


def publishable_or_why(records: list[dict], cur_sha: str) -> tuple[list[dict], str]:
    """قائمةُ السجلات القابلةِ للنشر، أو (`[]`، سببٌ صريح) — **السببُ يُطبع لا يُخفى**."""
    ok, unstamped, stale = classify(records, cur_sha)
    if unstamped or stale:
        return [], (f"⛔ {len(unstamped)} سجلاً **بلا بصمة** · {len(stale)} **ببصمةٍ مخالفة** "
                    f"(المطلوب {cur_sha}) ⇒ **لا يُنشر رقمٌ منها** — أعِد الطرح.")
    return [r for r in records if is_publishable(r, cur_sha)], f"{len(ok)} سجلاً مطابقاً للبصمة {cur_sha}"
