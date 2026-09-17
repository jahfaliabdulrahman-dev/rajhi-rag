# STATE — حلقة المراجعة (rajhi-rag)

status: AWAITING_REVIEW
step: البوابة 5 — تنفيذ حكمك: حدود الكلمات في بوابة النطاق + قاعدة join + رفض بدل وسم + سجلات التحكيم تفرّق قبل من بعد + لقطة الأرقام تعمل في CI
next: sulaiman يعالج بندَي المنع (بوابة النطاق: «ساب» داخل «حساب» · `concat_digits` لا يرى `join`)
      + ثلاثة بنود سريعة، ثم يسلّم sha جديداً
owner: sulaiman (منفّذ) · claude (مدقّق)
updated: 2026-09-17 21:40 (+03)

## بروتوكول
`docs/handoff-protocol.md` — الصيغة، الحدود، البوابات الست، وقواعد الأدلة.

## آخر ما استُلم
(claude) REVIEW — 2026-09-17 21:40 — `handoff/claude/20260917-214008-review.md` — **REQUEST_CHANGES** على `6f56405`
(sليمـان) audit-request — 2026-09-17 21:22 — commit `6f56405` (تنفيذ البوابات الأربع + عنقان)
(claude) Deep Audit — 2026-09-17 17:40 — `handoff/claude/audit/` — 24 بنداً، بندان STOP
(sليمـان) bootstrap — 2026-09-17 17:23 — commit `30167ef` (لم يعد يُحلّ: أُعيدت كتابة التاريخ في بوابة 0)

## ملاحظات للمالك
- **لا cron من جهة Hermes لهذه الحلقة.** المدقّق (Claude Code) يدير جدوله بنفسه (`/loop 3m`) بتكليف يُلصق في جلسته.
- تكليف المدقّق الكامل: `docs/claude-auditor-directive.md`.
- **قفل المالك:** عند رغبتك في إيقاف الحلقة، اكتب `status: AWAITING_FOUNDER` هنا — الطرفان يتوقفان.
- **بوابة 0 مُثبتة:** بحثتُ عن السلسلة المسرَّبة في 504 كائناً + رسائل الالتزام والمؤلفين + `logs/HEAD`
  و`packed-refs` و`ORIG_HEAD` ⇒ **صفر ظهور**. إعادة كتابة التاريخ نجحت.
- **يحتاج فعلاً منك:** `.claude/worktrees/rajhi-rag-deep-audit-91bd79/` يحمل في فهرسه تعديلاً معلّقاً
  يُعيد القيمة القديمة إلى `tests/test_publish_guard.py` (بقية من إعادة الكتابة — لم يُلتزم ولم يُدفع).
  احذف الـworktree بـ`git worktree remove` ثم `prune` — لا `rm -rf`.
