# تقريرٌ للمالك — الجولة ٦٩: ثلاثةٌ من القرارات نُفِّذت، والرابعُ يحتاج المالك

> **النوع:** تقريرٌ للمالك — **لا يُجيب حُكماً** (مُعلَنٌ في `NON_ANSWER_FILES_SINCE_RULE`).
> **المنفّذ:** سليمان · **زمنُ الوصول (زمنُ الاسم):** 20260930-0044 (+03) · **المُودِع:** الجلسةُ التنفيذيّة.
> **إيداعٌ متأخّر — وسببُه مُعلَن:** هذا التقريرُ سُلِّم إلى المالك **في المحادثة** وقتَ وقوعه
> (2026-09-26 ~22:04 (+03))، ولم يُودَع في الصندوق. أُودِع الآن تنفيذًا لبند الإيداع **R69-2**. **وتعارضُ التسمية مُعلَن** (قاعدةُ السجلّ: «تعارضُ تسميةٍ مُعلَن
> لا يُخفى»): في مراجعة ٦٩ (سطر ٤١) كان `R69-2` يعني «مراجعةُ ٦٨ لم تهبط»، وفي مراجعة ٧٢ (سطر ١٩ و٩٨)
> صار يُلحِق هذا البندَ بالإيداع نفسِه (نصُّه: «وهو R69-2 نفسُه، ما زال مفتوحًا»). **ونصُّ التقرير هو ما نقله المالك، بلا إعادةِ صياغة.**
> **وحدُّ الإيداع:** ما تحت هذا السطر هو متنُ التقرير كما سُلِّم؛ والترويسةُ وحدَها من اليوم.
> **وقاعدةُ الاسم:** زمنُ الاسم = زمنُ الإيداع (لا زمنُ الحدث) — تُقاس بـ`tests/test_report_names.py`.

---

## نفّذتُ ثلاثةً من القرارات، والرابعُ يحتاجك أوّلًا

**١. دمجُ PR ‏#127: تمّ.**
- دمجتُه بإعادة التركيب (rebase)، فصار كلُّ عمل سليمان من الجولات ٦٤–٦٨ في `main`.
- محتوى `main` مطابقٌ حرفيًّا للنسخة التي راجعتُها، والـCI أخضر.
- حارسُ النشر المُصلَح يعمل الآن على `main` نفسِه ويقرأ التاريخ (3405 كائنًا).

**٢. هبوطُ مراجعتَي ٦٨ و٦٩: تمّ،** بالدفع المباشر الذي وافقتَ عليه:
- دفعتُ الالتزامَ أوّلًا إلى فرعٍ مؤقّت، وانتظرتُ حتى اخضرّ الفحصُ عليه.
- ثم دفعتُه نفسَه إلى `main`، ثم حذفتُ الفرعَ المؤقّت. ولم يُفتح أيّ PR.
- قبل الدفع جرّبتُ كلَّ شيء في نسخٍ منفصلة، النقيّة وبياناتك الكاملة، والفحوصُ كلُّها خضراء.
- `main` الآن `9197a52`، والـCI أخضرُ عليه، وأداةُ `ci_report` تؤكّد ذلك.

**٣. قرارُ مسار §٢٧: سُجّل.** أضفتُه بنده السابع في بروتوكول التسليم، مؤرَّخًا اليوم وباسمك:
- المسارُ الرسميّ هو الدفعُ المباشر بعد اخضرار الفحص، بلا PR.
- وسطرُ ١٩ سبتمبر القديم صار متجاوَزًا، فانتهى التعارض.

**٤. لم يُنفَّذ، ويحتاجك:**
- **تثبيتُ شجرة البيانات:** تطبيقك `app.py` يعمل من ذلك المجلّد منذ ٩ أيّام. لو بدّلتُ الكودَ تحته قد يتعطّل، فتوقّفت.
  أوقِف التطبيقَ وأخبرني وأنفّذ التثبيتَ فورًا، أو نفّذه بنفسك بهذا الأمر:
  ```bash
  git -C ~/Projects/rajhi-rag switch --detach origin/main
  ```
- **النسخةُ الثانية من الأرشيف (R63-2):** لا قرصَ خارجيًّا موصولًا بالجهاز، وحفظُها في Bitwarden يحتاج كلمةَ مرورك، ولا أُدخلها.
  صِل قرصًا وأخبرني، وأنسخ `~/Hermes_Archive/2026-09-26_rajhi-pre-rewrite/` إليه وأتحقّق من سلامة النسخة.

**عن الفروع، بوضوح:**
- فرعُ سليمان `feat/r64-p5-tool-and-protocol` دُمج بالكامل، وبقاؤه على GitHub لا يضرّ `main` بشيء. لم أحذفه لأنّه فرعُ عمله.
- توصيتي الوحيدة: يبدأ سليمان جولتَه القادمة من `main` المحدَّث، لا من فرعه القديم. هكذا لا يتأخّر فرعٌ عن `main` ولا يحدث تعارض.

وسجّلتُ كلَّ ذلك في ملفّ حالتي على `main`، ولم يبقَ أيُّ نسخةٍ مؤقّتةٍ من بياناتك في مجلّد الجلسة.

You ran the pin yourself, and the data tree is now at `9197a52`. Checking that it's in good shape: clean, data still ignored, and whether `app.py` is still running on the old code.

The pin worked — the data tree matches origin/main at `9197a52` with all data folders and the key intact and still git-ignored, but app.py is still running the old code from 9 days ago even though the files on disk are updated. I'll record the pin in my STATE locally now, to be pushed with my next review.

The data tree is pinned: it's on `9197a52`, the same commit as `main`, with nothing modified and no untracked files. Your data folders and key are still in place and still ignored by git, so none of them can be committed by accident.

**Restart `app.py` when convenient.** You pinned without stopping it, so it has been running for 9 days on the old code, which is still what it has in memory. The files on disk are now the new version. It hasn't crashed, but if it loads a changed file mid-request it could mix two versions. Stop it and start it the way you usually do; I'm leaving that to you because I don't know the settings it was started with.

I recorded the pin in my STATE file as a local commit only (`ccced8e`), with no push. It will land with my next review.

That leaves only **R63-2** (the second copy of the archive): connect an external disk and tell me, and I'll copy the archive and verify the copy.

