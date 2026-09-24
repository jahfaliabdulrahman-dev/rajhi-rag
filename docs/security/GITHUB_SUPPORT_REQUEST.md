# طلبُ دعم GitHub — تنقية `refs/pull/*` (مُعدّ 2026-09-23)

**لماذا هذا الملفّ:** إصلاحُ التاريخ مرّ ثلاث مرّات (`git filter-repo`) فنظّف `refs/heads/*`، لكنّ
مراجع `refs/pull/*` عند GitHub **خارجَ متناول الفكّ من جهة العميل** — فهي لا تزال تحمل الالتزامات
قبل الإصلاح. والعددُ **يتغيّر مع كل طلب سحب**، فيُعاد قياسه يوم الإرسال.

**يُرسَل** من الحساب المالك للمستودع عبر `https://support.github.com/` ← «Repository / Remove or purge data».
**ولا يُنسخ** قسمُ «ملاحظات» أدناه.

---

## النصّ الجاهز للإرسال

**Subject:** Purge pull-request refs that still hold data removed by a history rewrite

Hello,

Repository: `jahfaliabdulrahman-dev/rajhi-rag` (public).

I rewrote this repository's history with `git filter-repo` to remove two things a commit had
published by mistake: a secret I have since rotated and consider burned, and a list of real
financial figures. The rewrite cleaned the branch history, and `git filter-repo` removed the
remote, so the old commits are no longer reachable from `refs/heads/*`.

They **are** still reachable from the pull-request refs. `git ls-remote` reports **116**
`refs/pull/*` refs on the remote (measured 2026-09-23, at sending time; the count grows by one for
every pull request, so please treat it as a lower bound). An external audit of those refs found at least
**6** carrying the burned secret and at least **9** carrying the published figures. These refs are
immutable from the client side, so I cannot remove them myself.

**Measured on 2026-09-23 at sending time:** a `git clone --mirror` of the repository — which fetches
`refs/pull/*` as well — still exposes **623** commits, against **226** on the rewritten `main` and
**250** across all rewritten branch refs. Both files removed from the branch history are still
reachable through the pull refs: `data/.amount-guard-key` in **4** commits and
`docs/security/amount-denylist.json` in **10**. Scanning that bare clone with this repository's own amount scanner finds **123**
occurrences of real financial figures inside **1,334** blobs still visible through the pull refs
(`tools/amount_guard.py --history-audit --mirror <bare clone>`; it exits non-zero when it finds any).
An earlier external audit, by a different method, likewise found at least **9** pull refs carrying the
published figures. A plain `git clone` (branches only) is already clean, so the exposure is
limited to anyone who explicitly fetches the pull-request refs.

**Request:** please purge or expire the repository's `refs/pull/*` refs, or run a garbage
collection that makes the pre-rewrite commits unretrievable, and confirm when it is done.

If purging every PR ref is not possible, please purge as many as you can and tell me which ones
cannot be touched, so I can decide how to treat the remainder.

I understand that anything already fetched, forked or cached cannot be recalled. I am asking for
what the platform can still control.

Thank you,
Abdulrahman Jahfali
jahfaliabdulrahman-dev (repository owner)

---

## ملاحظات (لا تُنسخ مع الطلب)

- **لا سِرَّ في الطلب:** لا يذكر المفتاحَ ولا أيّ رقمٍ ماليّ — يُسمّي الصنفَ لا القيمة.
- **مصدرُ الأرقام:** `git ls-remote origin 'refs/pull/*' | wc -l` ⇒ **116** يومَ الإرسال (وكان ١١٣
  قبل دمجَي #115/#116). ومَن أجرى فحصَ المحتوى هو **مدقّقٌ خارجيّ** في مراجعاتٍ سابقة
  (٦ مراجع بالمفتاح المحروق · ٩ بالقائمة المنشورة) — والطلبُ يذكرها بصيغة «at least» لأنّي لا أستطيع
  إعادةَ قياس المحتوى اليوم (المفتاحُ أُبطل ودُوِّر).
- **قياسُ «١٢٣» يومَ الإرسال:** أداةُ الحارس نفسُها (`--history-audit --mirror`) على `git clone --mirror`
  ⇒ **١٢٣ صيغةً داخل ١٣٣٤ blobاً ⇒ rc=5**. (وقياسي الأوّل بالكوربوس أعطى ٦٥ لأنّي قابلتُه بأرقام الكاش
  المعتمد وحدها (٣٢٠١) بينما مجموعةُ الحارس أوسع (٤٢٧٢ صيغةً) ⇒ **عددُ الأداة هو الحَكَم**، والـ٦٥ صُحِّح.) **ولا تُطبع قيمة.**
- **عطبٌ أُمسك ثم أُصلح في هذه الجولة (مراجعة ٤٣):** `--history-audit` كان **يُهمل `--mirror`** فيقرأ
  المستودعَ الحاليّ ⇒ «PASS» بـ**نفس عدد الكائنات (١١١٣)** على مرآةٍ زُرع فيها رقمٌ حقيقيّ (rc=0).
  أُصلح: الوجهةُ تُمرَّر (`-C`) وسطحُ المسح **يُعلن**، ومستودعٌ غيرُ صالح ⇒ فشلٌ مُغلَق، ومعه اختبارٌ
  بزرعٍ من الكوربوس + **ضبطٌ سالب** (وهميٌّ يمرّ). وبعد الإصلاح: **١٢٣ صيغةً في ١٣٣٤ blobاً**.
- **ما لا يُصلحه هذا:** النسخُ المُفرَّعة (forks)، والكاش، وأيّ نسخةٍ سُحبت قبل التنقية. **التدويرُ هو
  العلاجُ الفعليّ**، والطلبُ تنظيفٌ لنسخةٍ واحدةٍ عند منصّةٍ واحدة.
- **حالةُ الطلب — مُحدَّثة (تذكرة `4785819`):** أُرسل من حساب المالك عبر مسار «المستودعات ← cached views»
  (فُتحت ١١:٤٣ UTC). وردُّ الدعم (Finch · ١٢:٤٠ UTC): أداتُهم وجدت مراجعَ للالتزام الحسّاس في
  **`pr_numbers = [101..108]`**، و«To remove the sensitive data from pull requests, we'll need to delete
  the pull requests entirely» — وإزالةُ المراجع وحدها «requires significant backend processing, time and
  effort» ⇒ **القرارُ المطلوبُ من المالك: الموافقةُ على حذف ١٠١–١٠٨**.
  (وكلُّها **مدمجة** — لا كودَ يُفقد؛ ومحتوى نقاشاتها مُلتزمٌ كملفّاتٍ في `handoff/claude/` و`handoff/sulaiman/`
  ⇒ الحذفُ لا يُفقد شيئاً ذا قيمة، وهو ما صرّح به الطلبُ الأصليّ.)
- **الانكشافُ المقيسُ قبل تنفيذهم (2026-09-23 · `tools/refs_exposure_probe.py`):** `⛔ STILL EXPOSED` —
  `refs/pull/*` = **١٢٢** · التزاماتُ المرآة **٦٤٩** مقابل `main` المعاد كتابتِه **٢٣١** ·
  **١٢٣ صيغةَ مبلغٍ حقيقيّةً داخل ١٤٤٠ blobاً مرئيّةٌ عبر المرآة** · والتزاماتُ ما قبل التنقية الثلاثة
  تُرجع **HTTP 200** (معرّفاتُها وأوصافُها في `data/security/refs-cached-shas.json` — **غيرُ مُتتبَّع**، §٧).
  ⇒ **الانكشافُ اليومَ ليس المفتاحَ وحدَه بل مبالغَ الكشف أيضاً** — وهذا هو وزنُ الموافقة.
- **نصُّ الردّ المُقترح (يُرسله المالك):** «Thanks Finch — please proceed with deleting pull requests
  #101–#108. All eight are already merged (their changes are in `main`), and every artifact we need from
  those threads is already committed as files inside the repository, so nothing of value is lost.
  One request while you are in there: **the refs still resolve — please expire them** (and the cached
  views for the pre-rewrite commits) so the old commits are no longer retrievable through `refs/pull/*`.
  The credential was rotated and is considered burned.»
- **القياسُ بعدهم (لا يُغلق البند بوعد):** `python3 tools/refs_exposure_probe.py` ⇒ `PURGED` (rc=0) أو
  `STILL EXPOSED` (rc=1) أو `UNMEASURED` (rc=2: تعذّر الجلب ⇒ **فشلٌ مُغلَق**).  ← ونُفِّذ في §٦ أدناه.

---

## ردُّ الدعم وقياسُه — **جزئيّ لا كامل** (٢٠٢٦-٠٩-٢٤)

**قال الدعم (Finch · ٢٤ سبتمبر ٠٨:٢٩ UTC · التذكرة `4785819`):** «I have deleted the pull requests and
cleared out unreferenced commits. The dangling commits are now removed from GitHub.»

**وما قِيس بأيدينا بعد الردّ (لا بوعد):**

| المقياس | قبل الطلب | بعد ردّ الدعم | الحكم |
|---|---|---|---|
| `refs/pull/*` على الريموت | ١٢٢ | **١١٣** | انخفض ٩ |
| الـPRs المطلوب حذفها (`101..108`) | قائمة | **HTTP 404 للثمانية** | ✓ نُفِّذ |
| الالتزاماتُ المرئيّة عبر مرآة كاملة | ٦٤٩ | **٦٥٢** (و`main` ٢٨٠) | **لم تنقص** |
| صيغُ مبالغَ حقيقيّة مرئيه عبر المرآة | ١٢٣ داخل ١٤٤٠ blobاً | **١٢٣ داخل ١٥٦٤ blobاً** | **لم تنقص** |
| `cached views` لالتزامات ما قبل التنقية (٣) | ٣ × HTTP 200 | **الأول ⇒ 404 ✓ · الثاني ⇒ 200 · الثالث ⇒ 200** (الأسماءُ في الملفّ غير المُتتبَّع، §٧) | جزئيّ |

**الحكمُ المقيس:** حُذفت **طلباتُ السحب** وطُويت واحدةٌ من ثلاث `cached views`، لكنّ **الكائناتَ نفسَها
لا تزال قابلةً للسحب** عبر المراجع الباقية — فلا يُغلق البند. الأمرُ القاطع:

```bash
.venv/bin/python tools/refs_exposure_probe.py --json     # ⇒ verdict: STILL EXPOSED · rc=1
```

### نصُّ الردّ المُقترح (يرسله المالك — نفسُ التذكرة)

> **قبل الإرسال**: تُملأ `<SHA-A>/<SHA-B>/<SHA-C>` من `data/security/refs-cached-shas.json`
> (**غيرُ مُتتبَّع**). المعرّفاتُ لا تُكتَب هنا ولا في أيّ ملفٍّ مُتتبَّع: كتابتُها تنشر **رابطاً موسوماً**
> إلى ما لم يُطهَّر (إسقاطٌ أمنيّ أمسكه المدقّق في مراجعة ٥٣ — §٧).

```
Hi Finch — thank you for deleting #101–#108: those pull requests now return 404 on our side, confirmed.

However the underlying commits are still retrievable. Re-measured today with the same tooling as the
original request:

- `git ls-remote` on the repo still reports 113 `refs/pull/*` refs.
- A full `git clone --mirror` (which fetches those refs) still exposes 652 commits against 280 on the
  rewritten `main`, and our amount scanner still finds 123 occurrences of real financial figures inside
  1,564 blobs reachable through them.
- Two of the three pre-rewrite commit URLs still resolve with HTTP 200: <SHA-B> and <SHA-C>
  (the third, <SHA-A>, now correctly returns 404).

So the pull requests are gone but their commits are not: they are still reachable through the remaining
pull-request refs and cached views.

Request: please expire the remaining `refs/pull/*` refs — or run the garbage collection that makes the
pre-rewrite commits unretrievable — and clear the cached commit views for <SHA-B> and <SHA-C>.
Please confirm when done; we re-measure after every change.

The credential was rotated and is considered burned; what remains exposed is the financial-figures class.
Thank you.
```

### عطبٌ أُمسك في هذه الجولة وأُصلح (وأثرُه أمنيّ)

**الحيّازُ كان يُرجع `rc=0` مع حكم `STILL EXPOSED` في وضع `--json`** (`return 1` سكن فرعَ المخرَج النصّيّ)
⇒ أيُّ مستهلكٍ آليّ يقرأ صفرًا **يمرّ على سطحٍ مكشوف**: فشلٌ **مفتوح** في الأداة التي يُقرَّر بها إغلاقُ
بند الانكشاف نفسِه. أُصلح: الحكمُ هو الحكمُ في الوضعين، والضابطُ سلوكيّ (يشغّل `main()` بشبكةٍ مزيّفة
عبر `_run`/`_http_code`) — `tests/test_refs_probe_exit_code.py` (٣ ضوابط: `PURGED=0` و`STILL EXPOSED=1`
في الوضعين، و`cached view = 200` وحدَه يكفي للانكشاف).

---

## كيف نتجنّب الصنفَ كلَّه (لا الحادثةَ وحدها)

**الجذرُ البنيويّ:** ما دخل **التزامًا** في مستودعٍ عام يبقى قابلًا للسحب عبر `refs/pull/*`، وهي
**غيرُ قابلةٍ للفكّ من جهة العميل**. وقِيس ذلك بعد تنقيةٍ ثلاثيّة (`filter-repo`) **وبعد حذف الفرع
و٨ طلباتِ سحب**: لا يزال **١١٣** مرجعاً و**٦٥٤** التزاماً و**١٢٣** شكلاً من مبالغَ حقيقيّة داخل
**١٥٦٤** blobاً مرئيّة. وما قِيس أيضاً: **لا فرعَ ريموتيٌّ يحمل الالتزامات ما قبل التنقية**
(`git branch -r --contains` للثلاثة ⇒ فارغ) ⇒ الانكشافُ محصورٌ في مراجعِ پول والكاش: **لا يُصلحه حذفُ فروع**.

| الطبقة | الأداة | ما تمنعه/تقيسه | الحالة |
|---|---|---|---|
| ١ · **قبل وجود الكائن** | `.githooks/pre-commit` (جديد) + `tools/secret_scan.py` | مساراتُ الأدلّة/السرّ بالاسم · **١٢ صنفاً من الأسرار بنمطٍ لكلّ صنف** (لا نمطٌ واحد يمرّر الأشكالَ ذاتَ الشَّرطات) · أشكالُ مبالغَ حقيقيّة (بحارس المبالغ) | ✓ سمٌّ يدويٌّ: ٤/٤ + **٦ أصنافٍ من المفاتيح تعضّ** + `tests/test_hook_gates.py` (٥) · `tests/test_secret_scan.py` (٦) |
| ٢ · عند الدفع | `.githooks/pre-push` (قائم) | ما يُنشر فعلًا: حارسُ النشر + حارسُ المبالغ على المدى + البوّابةُ الساكنة | ✓ |
| ٣ · في CI | `.github/workflows/publish-guard.yml` | الشجرةُ والتاريخُ ورسائلُ الالتزامات — **لكن نطاقُه مقيسٌ ومحدود**: `rev-list --objects --all` **داخل نسخة العمل**، و`actions/checkout` يجلب المرجعَ المدقَّقَ وحده ⇒ **`refs/pull/*` خارجَ مسح CI** | ⚠ عينٌ عمياء مقيسة |
| ٤ · **دوريّاً على مرآة كاملة** | مهمّةُ Hermes `refs-exposure-watch` (كلَّ اثنين ٩ص) تشغّل `tools/refs_exposure_probe.py` + `amount_guard --history-audit --mirror` | العينُ التي ترى ما لا يراه CI (يحتاج المانيفستَ غيرَ المنشور ⇒ محلّيّة) | ✓ مُنشأة (`484614c81063`) · **صمتٌ = صفرُ انكشاف**، وتنبيهٌ عند `STILL EXPOSED`/`UNMEASURED` · والقياسُ شُغِّل يدويًّا فأخرج التنبيه |

**وقواعدُ أربع تُختصر بها الحادثةُ كلُّها:**
1. **المنعُ قبل الالتزام لا التنقيةُ بعده** — التنقيةُ لا تُصلح `refs/pull/*`، والتدويرُ وحدَه يعالج السرّ.
2. **لا تُدفع أدلّةٌ في فرعٍ إلى مستودعٍ عام**، ولو مؤقّتًا لمراجعة (هكذا دخلت أوّلًا).
3. **المقياسُ من كود الخروج** — «مُنع» أو «نُظّف» دعوى تُقبَل بـ`rc`، لا بنصٍّ في رسالة.
4. **الفرعُ يُحذف بعد الدمج** (نُفِّذ لِـ`feat/item4-pack-free-capture-44`) — تقليلُ مراجعَ حاملة، لا إصلاحٌ لما في مراجع پول.
5. **لا تنشر معرّفاً موسوماً لِما لم يُطهَّر** — «أيّ التزامٍ يفكّ البيانات» دليلٌ بالقدر الذي فيه المحتوى؛
   والمعرّفاتُ في ملفٍّ **غيرِ مُتتبَّع**، وغيابُه **فشلٌ مُغلَق** لا قياسٌ ناقصٌ صامت.

---

## ٧ · مراجعة ٥٣ — ثلاثةُ إسقاطاتٍ أُمسكت على البوّابة الجديدة وأُصلحت من جذورها (٢٠٢٦-٠٩-٢٥)

مدقّقٌ مستقلّ هاجم **البوّابةَ الجديدة نفسَها** بمفاتيحَ مصطنعة وبنسخةٍ نقيّة. ثلاثةُ عطوبٍ — أُصلحت **بالصنف**،
لكلٍّ سمٌّ وضابط:

| العطبُ المقيس | الأثر | الإصلاحُ الجذريّ |
|---|---|---|
| `pre-commit` كان يمرّر `sk-or-v1-…` و`sk-ant-…` (**صنفُ الرمز الذي تسرّب فعلًا**) و`sk-proj-…` و`github_pat_…` — النمطُ الواحد توقّف عند أوّل شَرطة (قِيس: **٥ من ٦ تمرّ صامتة**) | بوّابةٌ شكلية على أخطر صنف | `tools/secret_scan.py`: **نمطٌ لكلّ صنف** (١٢) · القيمةُ **لا تُطبع** (رقمُ السطر والصنف فقط) · غيابُ الفحص ⇒ `rc=2` **فشلٌ مُغلَق** · وضابطٌ يقيس **ما يجب ألّا يُطابَق** |
| معرّفاتُ الالتزامات الثلاثة **بأوصافها** كانت في `tools/refs_exposure_probe.py` **المُتتبَّع** ⇒ من قرأه عرف **أيّ التزامٍ يفكّ البيانات** | الانكشافُ صار **رابطاً موسوماً** | المعرّفاتُ والأوصافُ في `data/security/refs-cached-shas.json` (**غيرُ مُتتبَّع** · `data/security/` مُهمَل) · وغيابُها ⇒ `UNMEASURED` (rc=2) · والنصُّ الإنجليزيّ يستعمل `<SHA-A…C>` تُملأ قبل الإرسال |
| `tools/guard_bite_sweep.py`: مسارُ المفسّر مكتوبٌ + **أيُّ رمزٍ غيرِ صفر = «عَضّت»** | **يشهد لبوّاباتٍ لم تُقَس**: سقوطُ الأداة يخرج 1، و`python3 -m pytest` بلا pytest يخرج 1 أيضاً | المفسّرُ يُحلّ (الشجرة ← المستودع الرئيسيّ ← `python3`) · والتصنيفُ من **علامة pytest** (`FAILED` / `N failed`) ⇒ «سقط» · «لم يسقط» · **«تعذّر التشغيل» يُحسب عطباً** |

**والرابعُ يخصُّ الاكتشافَ لا الحكم:** في **نسخةٍ نقيّة** كان ضابطُ وجود الخطّافات يسقط، لأنّ
`core.hooksPath` **إعدادٌ محلّيّ لا ينتقل مع الاستنساخ** ⇒ صار الضابطُ يقبل `""` كذلك (حالٌ معلومة: الخطّافاتُ
لا تحرس تلك النسخة، وCI وحدَه يعمل عند الجميع)، وأُضيف ضابطٌ يقرأ **سطرَ التركيب من ملفّ الخطّاف نفسه**
(بوّابةٌ لا تُركَّب لا تحرس). والقياسُ النهائيّ يُعاد في **نسخةٍ نقيّة**: صفرُ إسقاط.

**والخامسُ الأخطرُ في صنفه — رقمُ الاختبارات كان بيئيّاً:** نسخةٌ نقيّة من المستودع أعطت
`7 failed, 613 passed` (لا إسقاطٌ واحدٌ كما ظنّ المدقّق): أربعةٌ منها فحوصٌ **تشترط وجودَ الأدلّة المحلّيّة**
(`data/` لا يُنشر بالتصميم) ⇒ العدّادُ يصلح في نسخة صاحبه وحدها، وهذا سببٌ مشروعٌ لعدم الثقة به.
⇒ `tests/_local_evidence.py` تُعلن **تخطّياً بسببٍ مكتوب** حيث لا أدلّة، و٣ فحوصٍ أُصلحت حتميًّا (تُوفّر
ملفَّ المعرّفات بدل الاعتماد على ملفٍّ محلّيّ) ⇒ **النسخةُ النقيّة: `616 passed · 55 skipped · 0 failed`**.
*(والدرسُ العامّ: مقياسٌ لا يُعلن بيئتَه دعوى — P-5 في تقرير الجولة.)*

**الحدُّ المتبقّي (مُعلَن لا مُخفى):** المعرّفاتُ الثلاثة **مذكورةٌ في تاريخ المستودع** من جولاتٍ سابقة — لا
تُنقّى بلا إعادة كتابة، وليست أدلّةً بذاتها، ولا نُعيد دورةَ تنقيةٍ رابعة (القاعدة ٥).

