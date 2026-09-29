# تقريرٌ للمالك — R70-1 وR70-2 أُصلحا وهبطا في `34fe838`

> **النوع:** تقريرٌ للمالك — **لا يُجيب حُكماً** (مُعلَنٌ في `NON_ANSWER_FILES_SINCE_RULE`).
> **المنفّذ:** سليمان · **زمنُ الوصول (زمنُ الاسم):** 20260930-0044 (+03) · **المُودِع:** الجلسةُ التنفيذيّة.
> **إيداعٌ متأخّر — وسببُه مُعلَن:** هذا التقريرُ سُلِّم إلى المالك **في المحادثة** وقتَ وقوعه
> (2026-09-27 ~10:18 (+03))، ولم يُودَع في الصندوق. أُودِع الآن تنفيذًا لـ**R69-2** («إيداعُ تقارير جولة البيان في
> المستودع» — مراجعة ٦٩، وأُعيد في مراجعة ٧٢). **ونصُّ التقرير هو ما نقله المالك، بلا إعادةِ صياغة.**
> **وحدُّ الإيداع:** ما تحت هذا السطر هو متنُ التقرير كما سُلِّم؛ والترويسةُ وحدَها من اليوم.
> **وقاعدةُ الاسم:** زمنُ الاسم = زمنُ الإيداع (لا زمنُ الحدث) — تُقاس بـ`tests/test_report_names.py`.

---

Review 70 is addressed and the work is on `main` at `34fe838`. It landed by path (a): a fast-forward from `9197a52` with no merge commit. CI passed on that exact commit both on its branch and on `main`.

## R70-1: the footer order needs a second witness
- **The order is decided after reading, not before.** The printed page number and proven adjacency only exist once the rows are read, so the app now reads footers first, then rows in file order (same number of paid calls), then decides the order, then derives and checks.
- **The footer order is applied only when** it has no conflicts, no duplicates, and every page it moves has a second witness: proven adjacency to a neighbour, or its printed page number sitting between its neighbours'. Otherwise the file order stands and the summary says why.
- **Replayed on the real 629 footers:** 40 one-digit misreads in debit totals. 21 of them moved the footer order, one by 208 positions, and one of those raised no conflict. All 40 now keep the file order; the unmodified footers keep it too.

## R70-2: the footer pass has the read's limits
The cost cap is checked before each footer call. After 5 consecutive failures the run stops with a clear message, no rows are read, and the previous file's results are cleared. Footers that failed to read are named in the summary.

## Tests
New tests cover a planted one-digit misread (unit and app level), moves with and without a witness, conflicts and duplicates, and both footer-pass stops. Every deliberate regression I planted was caught.

## Lighter items
- **Accuracy harness:** `tools/desc_accuracy.py`, with `reference` / `column` / `compare`. `compare` needs no extra packages and writes counts only.
- **Evidence files:** `docs/evidence/desc_accuracy_20p.json` and `_50p.json`, holding the page lists and per-page counts. They reproduce the figures: column matches the reference on 422/437 rows, the full-page reading on 323/437, and the description shifts are on pages 6, 7, 302, 456, 457 and 591. There's a test that no description text or amount leaks into them.
- **CI list:** `tests/test_footer_order.py` is added to the workflow and to `docs/GATES.md` (a test requires the two to match).

## Something I found: the "+10" is pyflakes
The workflow comment explains a constant +10 between local and runner counts. The actual cause is `pyflakes==3.4.0`: CI installs it in the static-gate step, which makes the 10 tests in `test_static_gate.py` collectable. With it, my CI replica reproduces `main`'s 685/745 exactly. Published counts now: full 975 · ci-light 789 · ci-claims 729, all confirmed by CI's own snapshot check. The workflow comment still gives the old explanation; I left it alone since it wasn't in the review, so it's worth correcting in a later round.

## Landing
- **Linear history:** the rebase was refused as a history rewrite, so I built a new branch from `main` and cherry-picked the feature commits onto it. The code matched the old branch exactly apart from the count lines.
- **PR #128 closed, not merged:** its branch contained the sync merge commit that path (a) excludes. I left a comment pointing to `34fe838`.
- **Branches:** both remote branches are deleted. The local branches are still in this worktree.

The experiment crops and texts are only in the session's temporary folder, never in the repo. I can delete them if you like.

