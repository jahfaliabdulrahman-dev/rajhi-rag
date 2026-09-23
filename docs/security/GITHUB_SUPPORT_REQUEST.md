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
- **بعد الجواب:** يُسجَّل الردُّ وتاريخه في المستودع، ويُغلق البند — **لا يُترك مفتوحاً بعد أن يُقاس**.
