# Project context — rajhi-rag

This file is read automatically when a session works inside this repository, so project state
lives here and in `docs/` instead of inside a Hermes skill (a skill-load used to be the only
way to reach the state, which made an unrelated skill the top attractor).
## Active build-along instance (moved out of the `ai-study-mentoring` skill)

Project documents in `docs/` (the five marked local-only carry real statement amounts, so `.gitignore`
keeps them out of this public repository; they exist only on the owner's machine):

- `docs/rajhi-rag-state.md` (local-only) — the live status is the `### CURRENT` block at the top; read that block
  first. REWRITE it when a gate closes or a decision lands; never append over a superseded state.
- `docs/rajhi-rag-landing-work.md` (local-only) — landing rules: pre-push guards, protected `main`, worktree verification.
- `docs/rajhi-rag-gate-engineering.md` · `docs/rajhi-rag-history.md` · `docs/rajhi-rag-product-decisions.md` (local-only).
- `docs/product-journey.md` (tracked) — the eight phases and the six qualification conditions.

- rajhi-rag (real Al Rajhi statements → OCR/parse → LangChain RAG agent): plan at
  `~/Projects/rajhi-rag/PLAN.md`. The owner pivoted this project onto the raw
  scanned PDF — the plan and the state reference must both reflect the pivot.
  - **شكل المنتج ورحلته مثبَّتان بقرار المالك** — الوحدة: كشف واحد · القارئ النهائي: إنسان ينظر · الذاكرة في ملف العميل · ولا تركيبة (بنك × نوع مدخل) تُفتح للعملاء قبل تأهيلها بشروط ستة، و**أي تغيير في التلقينة/النموذج/العتبات يُرجع خليّة التأهيل إلى «قيد إعادة التأهيل»**.
    المراحل الثماني، شروط التأهيل، أصناف الأرقام، والمستبعد بقرار: `docs/product-journey.md`.
  - Verified facts, resume point, and the current phase gate live in
    `docs/rajhi-rag-state.md`. Read it before resuming; REWRITE it when a
    gate closes or a decision lands — never append over a superseded state.
  - **Landing a change in this repo — the pre-push guards and the values they
    block, the protected `main` (check green on the EXACT commit before the
    push), verifying on the landed revision in a separate worktree, merging a
    long-lived branch INTO `main`, unblocking a stale-base guard BLOCK without
    `--no-verify`, and raising «everything» without republishing purged history:
    `docs/rajhi-rag-landing-work.md`.**
  - **تضييقُ نطاق قاعدةٍ حاكمة تغييرُ معنًى لا تصحيحُ وصف — يُعْلَن ولا يُقرَّر، ثمّ يُنفَّذ فورَ كلمة المالك.**
    الفرقُ عمليّ: تصحيحُ **وصف** (النصُّ يقول X والكودُ يفعل Y) عملُ المنفّذ؛ وأمّا تغييرُ **ما تعنيه** القاعدة
    فيُعرض على المالك بخيارَين مرقومَين ومع كلٍّ ثمنُه. وطلبه الثابت عند أيّ غموض: «**الأكثرُ حرصاً ووضوحاً**» =
    يُنفَّذ **الأضيقُ** (موضعٌ واحدٌ مُعلَن تُقرأ منه) **مع عرض ما يُهمَل** — وحدٌّ يُسقط صنفاً بصمتٍ أسوأُ من
    توقّفٍ زوريّ، لأنّ الصّامتَ يقرأه صاحبُه نجاحاً. وقبل التنفيذ **يُقاس عددُ ما سيُسقَط فعلًا في الشجرة**:
    صفرٌ ⇒ لا تغييرَ سلوكيّاً (أأمنُ تغييرٍ ممكن، وهو **بالقياس لا بالطمأنينة**). ويُشحن مع سطر رجوعٍ في
    ملفّه نفسه (`git revert <sha>`) وضابطٍ يحرس الحدَّ ذاته (ملفٌّ بلا عناوين، سياجٌ يتيم، سطرٌ يقتبس العلامة).
  - **حكمُ مراجعةٍ يُرقّم مرحلتين (`(أ)` و`(ب)`) التزامانِ لا شقٌّ واحد — تنفيذُ إحداهما انحرافٌ يُكمَل أو يُعلَن.**
    تُقرأ الحركةُ من جدول القرار في المراجعة **حرفيًّا**: إن نصَّ على «في التزامٍ واحد» فهو شرطٌ للهبوط، والأصغرُ
    وحدَه يبقى نقصًا يُكتشَف بمقعدٍ مستقلّ (قِيس: `P1` على جولةٍ أعلنت نجاحَها). وقبل أن تُقال «نُفِّذ»، عُدَّ
    الشقوقَ في نصّ المراجعة وسمِّ لكلٍّ الأمرَ الذي أنتجه — والمقعدُ المستقلُّ يقرأ نصَّ الحكم لا ملخّصك عنه.
  - **قبل أن تُقال «التاريخُ لا يضيع»: عُدَّ الأوعيةَ الخمسة بأمر، لا بسؤال الجلسة.** ① سجلُّ الجلسات · ② صندوقُ
    المراسلات في `handoff/` (مدفوعٌ ⇒ يعيش بعد الجلسة) · ③ **سجلّاتُ المقاعد المفوَّضة** — بلا حماية: تُكتب تحت مجلد
    cache قابلٍ للتقليم وبلا نسخةٍ في الأرشيف، فانسخها عند إغلاق المقعد (مسحُ أسرار + فهرس) · ④ **التزاماتٌ محليّةٌ
    غيرُ مدفوعةٍ على فروع أشجار العمل** — تَجمع مراجعةً كاملةً وحدها · ⑤ **الحافظة/المحادثة** — تقريرُ منفّذٍ قد لا
    يدخل المستودع أبدًا. والعدُّ بأوامر: `git log --all --diff-filter=A --name-only | grep <التاريخ>` (أيُّ ملفٍّ في أيّ
    مرجع) · `ls <كلّ شجرة>/handoff/<الصندوق>/` · `gh api repos/:owner/:repo/contents/handoff/<الصندوق>?ref=main --jq '.[].name'`
    (ما يراه العالم). وما وُجد في مرجعٍ محليٍّ فقط يُستخرَج بـ`git show <sha>:<path>` **ويُدفع أو يُؤرشف** — فالخلاصةُ في
    مذكّرةٍ سوداء أو شجرةِ عملٍ واحدة ليست سجلًّا. وقل الثغرةَ بقياسها لا بحسنِ الظنّ.
  - **دفعةُ تقاريرَ تُنقل إليك «للعلم فقط» دعوى اكتمالٍ لا سجلٌّ — تحقَّق من مجموعتها قبل أن تُلخّصها.** ثلاث خطواتٍ
    قبل أيّ تلخيص: أحجامُ ملفّات المرفقات مع `md5` (نسخةٌ مكرّرةٌ تُقرأ كردٍّ جديد تُحرّف عدّ الجولة) · العدُّ في المراجع
    (④ أعلاه) · والقائمةُ المنشورة على الريموت. و«بلا تنفيذ» تعني **قراءةً محضة**: `git log` · `git ls-remote` · `gh api` ·
    `ps` جائزة، وممنوعةٌ كلُّ كتابةٍ — و`git fetch` منها لأنّه يُحرّك `refs/remotes`، فيُعلَن أنّه لم يقع فيُعرَف مصدرُ
    الرقم. وكلُّ رقمٍ يُعرض يحمل مصدره: **مقيسٌ بأمرٍ الآن ≠ مقتبسٌ من تقرير**.
  - **ادّعاءُ عطبٍ في الجهاز (ساعةٌ · وكيلٌ · بيئة) يحتاج شاهداً خارجيّاً قبل أن يُنشر — والادّعاءُ الخاطئُ يُسحب في موضعه بتاريخه، لا يُمحى.**
    فرقُ قراءتين ليس عطلاً: قد يكون زمناً حقيقيّاً مضى بين جلسةٍ وأخرى (إقلاعٌ ثمّ دخولٌ يُنتجان فرقاً بالسّاعات بلا أيّ خلل في الساعة).
    فيُقاس بمرجعٍ مستقلّ — طابعُ بدءٍ على الريموت لكلّ التزام، أو سجلُّ الوكيل نفسه — **وقبل أن يُكتب الادّعاء**، لأنّ التصحيحَ بعده يعني
    سحباً في سجلٍّ منشور. ومتى وقع الخطأُ فالعلاجُ جملةُ سحبٍ في **نفس الموضع** مع تاريخها وشاهدها: الحذفُ الصامتُ يقرؤه القارئُ التالي
    كأنّ الادّعاءَ لم يكن، وهو أسوأُ من الخطأ الذي يُعلن.
  - **«هل يُغني المسارُ X المسارَ Y؟» يُجاب بجدول تقابلٍ من نصّ الخارطة لا برأي.** صفٌّ لكلّ بند: ما يعطيه
    للأوّل · **بنصّ** البند المقابل في الثاني · الحكم. وثلاثةُ أجزاء لا يُسقط أحدها: **حكمٌ بالعدّ** (كم بنداً يكسب
    الاثنين · كم مختلط · كم صافٍ للأوّل)، **والنقيضُ بأمانة** (ما لا يعطيه هذا المسار أبداً: الطلبُ يأتي من الناس
    لا من الكود — والحاجزُ المقيسُ يُذكر باسمه)، **وسطرُ «ما لم يُثبت»** (نفعٌ مُرجَّح بمنطق البنود ≠ مُثبتٌ بصفقة).
    ويُكتب في `docs/` لا في المحادثة، فيُقتبس في الجولات التالية بدل أن يُعاد اشتقاقه.
  - **«ما زال فيه الكثيرُ لم يُنفَّذ» في مسارٍ ما يُجاب عنه بقياسٍ لا بقائمة.** أعِد مسحَ كلّ بندٍ بأمرٍ
    صغيرٍ (`grep` عن الرمز الحاكم · `--verify`) بدل الاقتباس من الملفّ — فالملفُّ نفسه يحمل أوصافًا
    **متقادمة** (بندٌ مكتوبٌ «مُهيّأة لا مُختبرة» وقد قاسه الأمرُ الأخضر فعلًا)، وتصحيحُه يُكتَب في الملفّ
    في نفس الجولة. ثمّ قارِن **بتعريف «تمّ» المكتوب في الخارطة نفسها**، فكثيرًا ما يكون أربعةَ بنودٍ لا
    تسعةً ⇒ فالباقي **خارج المسار الحرج** ويُقال صريحًا. ولكلّ بندٍ ثلاثةُ حقول: ما ينقص بالضبط · **من
    يملكه** (قرارُ المالك أم عملٌ تقنيّ) · موقعُه من المسار الحرج. ولا تُدافع عن النشاط بعرض ما أُنجز —
    اعرض ما تبقّى بالأرقام، وأعطِه قائمةَ ثمارٍ كلُّ صفٍّ فيها بأمرٍ يُعيد إنتاجه، لا سردًا.
