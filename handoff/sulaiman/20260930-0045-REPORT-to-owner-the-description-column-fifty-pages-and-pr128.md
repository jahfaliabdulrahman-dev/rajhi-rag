# تقريرٌ للمالك — جولة البيان: العمودُ الوصفي (٥٠ صفحة) والخطوةُ التالية

> **النوع:** تقريرٌ للمالك — **لا يُجيب حُكماً** (مُعلَنٌ في `NON_ANSWER_FILES_SINCE_RULE`).
> **المنفّذ:** سليمان · **زمنُ الوصول (زمنُ الاسم):** 20260930-0045 (+03) · **المُودِع:** الجلسةُ التنفيذيّة.
> **إيداعٌ متأخّر — وسببُه مُعلَن:** هذا التقريرُ سُلِّم إلى المالك **في المحادثة** وقتَ وقوعه
> (2026-09-27 ~10:15 (+03))، ولم يُودَع في الصندوق. أُودِع الآن تنفيذًا لبند الإيداع **R69-2**. **وتعارضُ التسمية مُعلَن** (قاعدةُ السجلّ: «تعارضُ تسميةٍ مُعلَن
> لا يُخفى»): في مراجعة ٦٩ (سطر ٤١) كان `R69-2` يعني «مراجعةُ ٦٨ لم تهبط»، وفي مراجعة ٧٢ (سطر ١٩ و٩٨)
> صار يُلحِق هذا البندَ بالإيداع نفسِه (نصُّه: «وهو R69-2 نفسُه، ما زال مفتوحًا»). **ونصُّ التقرير هو ما نقله المالك، بلا إعادةِ صياغة.**
> **وحدُّ الإيداع:** ما تحت هذا السطر هو متنُ التقرير كما سُلِّم؛ والترويسةُ وحدَها من اليوم.
> **وقاعدةُ الاسم:** زمنُ الاسم = زمنُ الإيداع (لا زمنُ الحدث) — تُقاس بـ`tests/test_report_names.py`.

---

## The 50-page test (new pages, not in the first sample)
- **Accuracy:** the new descriptions matched the reference (a separate crop per row) on **422 of 437 rows**. The rest were spacing, reference-code differences, and one row where the reference itself was wrong. The current reading matched on 323.
- **Continuations:** the current reading cut the description in all 32 cases, and in 28 of them attached the cut-off text to the first row of the next page. The new method kept all 32 with their own row.
- **Description shifts in the current reading:** on 4 of the 50 pages (302, 456, 457, 591) descriptions slid one row, so purchases were attached to the wrong merchant while the amounts stayed correct. I confirmed page 456 visually. Together with pages 6 and 7 from the first sample, that's about 9% of pages.
- **Reliability:** no failures, and every page returned exactly the right number of descriptions.
- **Cost:** everything spent comes to **$2.48** of your $9. The new method adds about $0.008 per page, roughly $5 for the 629-page file.

## What was built
- **In the app:** numbers and dates still come from the full-page reading, and descriptions come from the description column. Dates are settled before the description is replaced, so dates recovered from the old description text are kept. Continuations are only joined between pages the arithmetic proves are consecutive, and any failure keeps the old description and is named in the summary.
- **For large files (like your 629-page statement):** a separate tool, `tools/desc_pass.py`, writes the descriptions to side files without touching the saved cache. The Excel export only uses them with the `--desc-column` flag; without it the output is exactly as before. The eval pack, seals, published numbers and `scale_slice.py` are untouched.

## Checks and syncing with `main`
- **Checks:** 68 new tests in total, and every deliberate error I planted was caught.
- **A real-amount catch:** the real-amount guard caught a test number I'd picked that matches an amount in your real statement. I replaced it.
- **Syncing:**
  - Sulaiman's work had landed in `main` (PR #127, no open PRs).
  - Rebasing was refused as a history rewrite, so I merged `main` into the branch instead.
  - The only conflicts were the test-count lines, which I re-measured: 964 on your setup, fully green in a clean copy.
  - For the two CI counts (778 and 718) I built a copy of the CI setup; it reproduced `main`'s numbers with a constant offset of +10, already documented in the workflow.
- **Before pushing:** the privacy guard (tree and history), the static checks, the CI test list and the landing probe in both time zones all passed in a clean copy.

## What's left
- **CI has to finish on PR #128.** It's the only real proof of the two CI counts (778 and 718). If either is off, CI shows the correct value and I fix it.
- **Merge:** auto-merge is disabled for the repo. I'll merge with a merge commit, which keeps every commit and its measurements. Tell me when CI is green and I'll do it, or turn on automatic CI fixing on the PR so I get woken if it fails.

