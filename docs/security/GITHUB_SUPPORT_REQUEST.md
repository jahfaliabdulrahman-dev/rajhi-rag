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

They **are** still reachable from the pull-request refs. `git ls-remote` reports **113**
`refs/pull/*` refs on the remote (measured 2026-09-23, later the same day: 113; the count grows by one for every pull
request, so please treat it as a lower bound). An external audit of those refs found at least
**6** carrying the burned secret and at least **9** carrying the published figures. These refs are
immutable from the client side, so I cannot remove them myself.

**Measured after the rewrite (2026-09-23):** `git clone --mirror` of the repository — which fetches
`refs/pull/*` as well — still exposes **598** commits, against **221** on the rewritten `main`
and **266** across all rewritten branch refs, and an automated scan of that clone finds **123** distinct real financial figures and
**2** removed paths (`data/.amount-guard-key`, `docs/security/amount-denylist.json`) still
reachable. A plain `git clone` (branches only) is already clean, so the exposure is limited to
anyone who explicitly fetches the pull-request refs.

**Request:** please purge or expire the repository's `refs/pull/*` refs, or run a garbage
collection that makes the pre-rewrite commits unretrievable, and confirm when it is done.

If purging every PR ref is not possible, please purge as many as you can and tell me which ones
cannot be touched, so I can decide how to treat the remainder.

I understand that anything already fetched, forked or cached cannot be recalled. I am asking for
what the platform can still control.

Thank you,
<الاسم>

---

## ملاحظات (لا تُنسخ مع الطلب)

- **لا سِرَّ في الطلب:** لا يذكر المفتاحَ ولا أيّ رقمٍ ماليّ — يُسمّي الصنفَ لا القيمة.
- **مصدرُ الأرقام:** `git ls-remote origin 'refs/pull/*' | wc -l` ⇒ **113** في 2026-09-23 (وكان 101
  قبل الدمجات الثلاثة لهذه الجولة). ومَن أجرى فحصَ المحتوى هو **مدقّقٌ خارجيّ** في مراجعاتٍ سابقة
  (٦ مراجع بالمفتاح المحروق · ٩ بالقائمة المنشورة) — والطلبُ يذكرها بصيغة «at least» لأنّي لا أستطيع
  إعادةَ قياس المحتوى اليوم (المفتاحُ أُبطل ودُوِّر).
- **ما لا يُصلحه هذا:** النسخُ المُفرَّعة (forks)، والكاش، وأيّ نسخةٍ سُحبت قبل التنقية. **التدويرُ هو
  العلاجُ الفعليّ**، والطلبُ تنظيفٌ لنسخةٍ واحدةٍ عند منصّةٍ واحدة.
- **بعد الجواب:** يُسجَّل الردُّ وتاريخه في المستودع، ويُغلق البند — **لا يُترك مفتوحاً بعد أن يُقاس**.
