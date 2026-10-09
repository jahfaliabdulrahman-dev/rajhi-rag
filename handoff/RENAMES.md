# سجلُّ النقل والحذف تحت `handoff/` — **إعلانٌ إلزاميّ لا اختياريّ**

> **القاعدة (مُختبَرةٌ آليًّا):** `tests/test_mailbox_ownership.py` يقرأ كلَّ نقلٍ (`R`) أو حذفٍ (`D`)
> تحت `handoff/` في مدى `origin/main..HEAD` ويطالب بأن يكون مسارُه مذكورًا **في هذا الملفّ**.
> والسببُ في القاعدة الحديديّة ١ من `docs/handoff-protocol.md` §١: **لا أحد يعدّل ملفات الطرف الآخر
> ولا يحذفها** — والنقلُ يُخرج شاهدًا من صندوق صاحبه، فهو تعديلٌ بالمعنى الأعمّ. فإمّا لا نقلَ، وإمّا
> نقلٌ **مُعلَنٌ باسمه وسببه** (وهذا هو أسلوبُ المستودع نفسه: استثناءٌ مُسمّى لا صمت).

| التاريخ | الملفّ — من → إلى / حُذف | ماذا | السبب (مُعلَن) | أُعلن في |
|---|---|---|---|---|
| 2026-09-24 | `handoff/claude/20260924-1415-REPORT-to-claude-round50-triage-seats-and-fixes.md` → `handoff/claude/20260924-1350-REPORT-to-claude-round50-triage-seats-and-fixes.md` | إعادةُ تسمية | **مخالفةٌ مُعلَنة للقاعدة الحديديّة ١** وقعت في `1bb07a8`: أُعيدت تسميةُ ملفٍّ داخل **صندوق المدقّق** لأنّ زمنَ الالتزام في الاسم كان متأخّرًا عن زمنه الحقيقيّ. أُعلنت هنا ولم تُخفَ، ولا تُكرَّر: أيُّ تصحيحٍ لاحقٍ للاسم يجري في **صندوق صاحبه** ثمّ يُدفع. | مراجعة ٥٢ · هذا السجلّ |
| 2026-09-24 | `handoff/sulaiman/20260924-0800-REPORT-48-fix-first-executed.md` → `handoff/sulaiman/20260924-0621-REPORT-48-fix-first-executed.md` | إعادةُ تسمية | تصحيحُ زمنٍ في اسم تقريرٍ **داخل صندوق المنفّذ نفسه** (لا يعبُر صندوقًا) — وهي الإعادةُ المشروعة. | مراجعة ٥٢ · هذا السجلّ |
| 2026-09-24 | `handoff/claude/20260924-0155-REPORT-item4-review-fixes-and-measured-runs.md` → `handoff/sulaiman/20260924-0155-REPORT-item4-review-fixes-and-measured-runs.md` | نقل | تقريرُ المنفّذ إلى المدقّق كان يسكن صندوقَ المدقّق (سادسةَ مرّة) ⇒ نُقل إلى صندوق صاحبه. والمدقّق يقرأ من الصندوقين، فلا حاجةَ لنسخةٍ في صندوقه. | مراجعة ٥٢ · إصلاح R52-5 |
| 2026-09-24 | `handoff/claude/20260924-1242-REPORT-to-claude-round49-triage-and-fixes.md` → `handoff/sulaiman/20260924-1242-REPORT-to-claude-round49-triage-and-fixes.md` | نقل | كما فوق (R52-5). | مراجعة ٥٢ · إصلاح R52-5 |
| 2026-09-24 | `handoff/claude/20260924-1350-REPORT-to-claude-round50-triage-seats-and-fixes.md` → `handoff/sulaiman/20260924-1350-REPORT-to-claude-round50-triage-seats-and-fixes.md` | نقل | كما فوق (R52-5). | مراجعة ٥٢ · إصلاح R52-5 |
| 2026-09-24 | `handoff/claude/20260924-1421-REPORT-to-claude-round51-stop-control-exit-codes-and-three-missing-controls.md` → `handoff/sulaiman/20260924-1421-REPORT-to-claude-round51-stop-control-exit-codes-and-three-missing-controls.md` | نقل | كما فوق (R52-5). | مراجعة ٥٢ · إصلاح R52-5 |
| 2026-09-24 | `handoff/claude/20260924-2110-REPORT-item4-proof-rows-closed-with-one-declared-exception.md` → `handoff/sulaiman/20260924-2110-REPORT-item4-proof-rows-closed-with-one-declared-exception.md` | نقل | كما فوق (R52-5). | مراجعة ٥٢ · إصلاح R52-5 |
| 2026-09-24 | `handoff/claude/20260923-2238-REPORT-to-claude-review-47-closure-and-the-delivery-gate.md` | **بقيت — لا تُحذف** | قِيس بـ`cmp` ⇒ نسخةٌ **مكرّرةٌ بايتًا بايتًا** (12,052) من نسخةٍ قائمةٍ في `handoff/sulaiman/`. وحاولتُ حذفها أوّلًا فأمسكها مقعدان مستقلّان (المعايير · المواصفة): **الحذفُ من صندوق المدقّق كسرٌ للقاعدة الحديديّة ١ التي وُلد هذا الضابطُ منها** — ولو كان الملفُّ مكرّرًا. ⇒ أُعيدت، و**أُعلنت استثناءً مُسمّى** في `tests/test_mailbox_ownership.py` (`DECLARED_INTRUDERS`) مع ضابطٍ **يكشف الاستثناء المتقادم** إن زال الملفّ. والمرجعُ هو نسخةُ صاحبها في `handoff/sulaiman/`. | مراجعة ٥٢ · إصلاح R52-5 · وردُّ مقعدَي المراجعة |
| 2026-10-07 | `handoff/claude/20261007-1730-request-REQ-93-01-re-measure-the-fifty-after-the-memory-fix.md` → `handoff/sulaiman/20261007-1730-request-REQ-93-01-re-measure-the-fifty-after-the-memory-fix.md` | نقل | **طلبٌ كتبه المنفّذ وسكن صندوقَ المدقّق** (خطأُ موضعٍ لا مُلكيّة) ⇒ نُقل إلى صندوق صاحبه بنصّ إصلاح R94-8. **والحركةُ مُعلَنةٌ هنا** كما تفرض القاعدةُ الحديديّة ١. | مراجعة ٩٤ · إصلاح R94-8 · هذا السجلّ |

## للطرفين — ما يتغيّر من الآن
1. **اكتب في صندوقك فقط**: `handoff/sulaiman/` للمنفّذ، `handoff/claude/` للمدقّق. والطرفُ الآخر **يقرأ** من صندوقك؛ لا نسخةَ تُدفع إلى صندوقه.
2. **لا تعدّل ملفًّا في صندوق الطرف الآخر ولا تحذفه ولا تُعِد تسميته.** أيُّ حركةٍ تحت `handoff/` تُعلَن هنا بالسبب.
3. اسمُ الملفّ يبدأ بزمن الالتزام **المقيس** (`git log -1 --format=%cd`)، لا بزمن كتابة الرسالة — وهذا يُلغي الحاجةَ إلى إعادة تسميةٍ لاحقة.

## 2026-09-25 — تصحيحُ زمنِ اسم تقرير (ملاحظةُ مراجعة ٥٤)

- `handoff/sulaiman/20260925-0130-REPORT-to-claude-round53-gate-attacked-and-root-fixed.md`
  → `handoff/sulaiman/20260925-0118-REPORT-to-claude-round53-gate-attacked-and-root-fixed.md`
- **السبب:** القاعدة «اسمُ التقرير يحمل زمنَ وصوله» (البروتوكول ٢٤): الملفُّ أُودِع في `01:18` واسمُه قال `0130`.
  والنقلُ بـ`git mv` يحفظ التاريخَ (والقياسُ عبر `--follow`)، والاسمُ الجديد يطابق زمنَ الإيداع.

## 2026-09-25 — تصحيحُ زمنِ اسمِ التزامِ إغلاق بنود المقاعد (`a6c905d`)

- `handoff/sulaiman/20260925-1520-REPORT-to-owner-three-seat-closures-on-the-flake-policy-and-the-deliberate-relaxation.md`
  → `handoff/sulaiman/20260925-1340-REPORT-to-owner-three-seat-closures-on-the-flake-policy-and-the-deliberate-relaxation.md`
- **السبب:** كتبتُ الاسمَ بزمنٍ مُقدَّر (١٥:٢٠) قبل القياس، وزمنُ الإيداع الفعليّ **١٣:٣٦** (فسقط حارسُ الأسماء،
  وصحّحتُه بـ`git mv` كما تنصّ القاعدة). ولا شيءَ غيرُ الاسم تغيّر.

## 2026-09-26 — تصحيحُ زمنِ اسمَي ملفَّي تسليم جولة ٦٨د (`84a60b9`)

- `handoff/sulaiman/20260927-0015-PLAN-round68d-closing-the-seats-findings.md`
  → `handoff/sulaiman/20260926-2345-PLAN-round68d-closing-the-seats-findings.md`
- `handoff/sulaiman/20260927-0130-SEATS-round68d-the-three-seats-and-the-closure-of-their-findings.md`
  → `handoff/sulaiman/20260926-2352-SEATS-round68d-the-three-seats-and-the-closure-of-their-findings.md`
- **السبب:** كتبتُ الزمنين من ساعتي المحلّيّة (بعد منتصف الليل محليًّا) بينما نطاقُ التسمية في المستودع
  هو `+03:00` بزمن الالتزام ⇒ فوقع الاسمُ في اليوم التالي (٢٧) وزمنُ الهبوط ٢٦-٠٩ ٢٣:٤٥ و٢٣:٥٢.
  النقلُ بـ`git mv` كما ينصّ حارسُ الأسماء، **ولا شيءَ غيرُ الاسم تغيّر**، والقائمةُ في
  `NON_ANSWER_FILES_SINCE_RULE` حُدِّثت بالأسماء الجديدة.
| 2026-10-04 | `handoff/sulaiman/20261004-0300-REPORT-to-claude-a3-a4-consolidated-six-landings-and-the-pending-paid-decision.md` → `handoff/sulaiman/20261004-0623-REPORT-to-claude-a3-a4-consolidated-six-landings-the-paid-price-and-the-class-defect.md` → `handoff/sulaiman/20261004-0711-REPORT-to-claude-a3-a4-six-landings-the-paid-fifty-and-the-corrected-comparison.md` → `handoff/sulaiman/20261004-0613-REPORT-to-claude-a3-a4-six-landings-the-paid-fifty-and-the-corrected-comparison.md` | إعادةُ تسمية (ثلاثُ مرّات) | **تصحيحُ الاسم ليطابق زمنَ الإيداع** (تسامحُ `test_report_names` ٢٠ دقيقة) — والملفّ **لم يعبُر صندوقًا** (بقِي في صندوق المنفّذ) والمحتوى لم يتغيّر. | مراجعة ٩١ · هذا السجلّ |
| 2026-10-07 | `handoff/sulaiman/20261007-2225-REQUEST-REQ-96-01-one-shared-contract-row-builder.md` → `handoff/sulaiman/20261007-2216-REQUEST-REQ-96-01-one-shared-contract-row-builder.md` | إعادةُ تسمية | **تصحيحُ الاسم ليطابق زمنَ الإيداع** (الحارسُ يشترط الاسمَ على زمن الهبوط) — والملفّ **لم يعبُر صندوقًا** والمحتوى لم يتغيّر؛ والقائمةُ في `NON_ANSWER_FILES_SINCE_RULE` حُدِّثت بالاسم الجديد. | الجولةُ R96 · هذا السجلّ |
| 2026-10-09 | `handoff/sulaiman/20261009-1830-REPORT-to-owner-r101-the-correction-p-a-and-the-three-seats-closed.md` → `handoff/sulaiman/20261009-1757-REPORT-to-owner-r101-the-correction-p-a-and-the-three-seats-closed.md` | إعادةُ تسمية | **تصحيحُ الاسم ليطابق زمنَ الإيداع** (قِيس: الهبوط 17:57 والاسم قال 1830 — أُسقطه `test_report_names` بفارق ٣٣ دقيقة على تسامح ٢٠). والملفّ **لم يعبُر صندوقًا** (بقِي في صندوق المنفّذ) والمحتوى لم يتغيّر إلّا في حقل `id:`؛ و`NON_ANSWER_FILES_SINCE_RULE` والمؤشّرُ في `qa.py` حُدِّثا بالاسم الجديد. | جولةُ R101 · هذا السجلّ |
| 2026-10-09 | `handoff/sulaiman/20261009-1835-SEATS-r101-three-isolated-seats-verbatim.md` → `handoff/sulaiman/20261009-1757-SEATS-r101-three-isolated-seats-verbatim.md` | إعادةُ تسمية | كما فوق (نفسُ السبب ونفسُ الجولة): تصحيحُ زمنِ الاسم على زمن الهبوط — ولا عبورَ صندوقٍ ولا تغييرَ محتوى إلّا `id:`. | جولةُ R101 · هذا السجلّ |
