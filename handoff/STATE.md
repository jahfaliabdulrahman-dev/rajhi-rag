# STATE — حلقة المراجعة (rajhi-rag)

status: AWAITING_REVIEW
step: bootstrap — التسليم الأول (كل ما هو مدفوع حتى `30167ef`) بانتظار مراجعة Claude
next: Claude يراجع `handoff/sulaiman/20260917-172327-bootstrap.md` ويكتب حكمه في `handoff/claude/`
owner: sulaiman (منفّذ) · claude (مدقّق)
updated: 2026-09-17 17:23 (+03)

## بروتوكول
`docs/handoff-protocol.md` — الصيغة، الحدود، البوابات الست، وقواعد الأدلة.

## آخر ما استُلم
(sليمـان) bootstrap — 2026-09-17 17:23 — commit `30167ef`
(sـابق) لا شيء — هذه أول رسالة في الصندوق (bootstrap بعد عمل مدفوع سابق).

## ملاحظات للمالك
- **لا cron من جهة Hermes لهذه الحلقة.** المدقّق (Claude Code) يدير جدوله بنفسه (`/loop 3m`) بتكليف يُلصق في جلسته.
- تكليف المدقّق الكامل: `docs/claude-auditor-directive.md`.
- **قفل المالك:** عند رغبتك في إيقاف الحلقة، اكتب `status: AWAITING_FOUNDER` هنا — الطرفان يتوقفان.
