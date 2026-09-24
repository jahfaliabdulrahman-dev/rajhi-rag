# سجلُّ البوّابات — بوّابةٌ لا تُعرَف ليست بوّابة

**P-8 · تبنّاه المدقّق في مراجعة ٥٥.** سببه المقيس: بوّابتان محلّيّتان لا تعملان إلا في نسخةٍ مُهيّأة
(`core.hooksPath` **لا ينتقل** مع `clone`)، والـCI يشغّل **أربعة** ملفّات اختبارٍ فقط — ولو كان هذا السجلُّ
موجوداً لظهر الفرقُ من أوّل نظرةٍ لا بعد جولة.

**وكيف يُحرَس هذا الملفّ نفسه:** `tests/test_gate_registry.py` يقيس كلَّ صفٍّ هنا في الاتّجاهين —
(١) كلُّ ملفٍّ في `.githooks/` وكلُّ أداةٍ تُنادى منه أو من الـCI **مذكورةٌ**؛ (٢) و**ما يذكره هذا الملفُّ عن
الـCI يطابق نصَّ الـworkflow** (لا وصفاً من الذاكرة). فالسجلُّ وثيقةٌ **مُقابَلةٌ بمصدرها**، لا قائمةٌ حُرّة.

## ١ · طبقاتُ التشغيل (حيث تعمل فعلاً)

| الطبقة | الملفّ | متى | حاجزٌ حقيقيّ؟ |
| :--- | :--- | :--- | :--- |
| **ما قبل الالتزام** | `.githooks/pre-commit` | على الفهرس (`--staged`) | ⚠ **محلّيّ فقط** — يحتاج `git config core.hooksPath .githooks`، **ولا يُورَث بالنسخ** |
| **ما قبل الدفع** | `.githooks/pre-push` | على مراجع الدفع | ⚠ محلّيّ فقط (نفسُ الشرط) |
| **CI** | `.github/workflows/publish-guard.yml` | كلُّ `push` و`pull_request` | ✅ غيرُ قابل للتجاوز (مع حماية الفرع) — لكنّه **أضيقُ مدىً** |
| **دوريّ** (خارج المستودع) | مهمّةُ Hermes `refs-exposure-watch` · الاثنين ٩ص | أسبوعيّاً | ✅ يعمل والبوّاباتُ الأخرى **عمياء** عن مداه |

## ٢ · البوّابات

| # | البوّابة | ما تُمسكه | تعمل في | سمُّها (الضابطُ الذي يُثبت أنّها تعضّ) | الفشل |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `tools/secret_scan.py` | ١٢ صنفَ سرٍّ · **المعرّفاتُ الغريبة** (`--foreign-ids`: معرّفٌ لا وجودَ له في رسم المستودع) | pre-commit (المُدرَج) · الـCI لا يشغّله | `tests/test_secret_scan.py` (٦ ضوابط منها ضابطان سالبان) | `rc=2` فشلٌ **مُغلَق** (تعذّرُ الفحص ليس نظافة) |
| 2 | `tools/publish_guard.py` | بياناتٌ حقيقيّة/PII في الشجرة **والتاريخ ورسائل الالتزام** | pre-push · الـCI (`--tree --history --ci`) | `tests/test_publish_guard.py` · `tests/test_gate_bites.py` | `exit 1` |
| 3 | `tools/amount_guard.py` | شكلُ مبلغٍ حقيقيٍّ في أيّ ملفٍّ مُتتبَّع أو غيرِ مُهمَل | pre-commit (لكلّ ملفٍّ مُدرَج) · pre-push · الـCI | `tests/test_amount_guard.py` | `exit 1` · غيابُ المفتاح ⇒ يُعلَن ما فُحص |
| 4 | `tools/static_gate.py` | اسمٌ لا يُحلّ · ربطٌ لا يُقرأ · استيرادٌ بلا مستعمل | pre-push (**إن وُجد `pyflakes`**) · الـCI | `tests/test_gate_registry.py` (يقرأ أسماءَ القواعد من الأداة) | `BLOCK` |
| 5 | `tools/render_claims.py --check` | رقمٌ منشورٌ خالف مصدرَه | الـCI | `tests/test_public_claims.py` | `exit 1` |
| 6 | `tools/turn.py --check` | **قيمةُ دورٍ محفوظة** في `handoff/STATE.md` (وتُقاس الطبقةُ الثانية: التقادُم) | **لا خطّافَ — الاختبارات فقط** | `tests/test_turn_derivation.py` · `tests/test_report_names.py` | `1` · `2` تعذّرُ القياس |
| 7 | اسمُ التقرير يحمل زمنَ إيداعه | انزياحُ الاسم عن زمن الالتزام (±٢٠ د) بعد `CUTOFF` | ⚠ **الاختبارات فقط · والـCI شغّل ٤ ملفّاتٍ لا تشمله** | `tests/test_report_names.py::test_every_recent_report_name_matches_when_it_landed` | فشلُ اختبار |
| 8 | الأدلّةُ لا تُدفَع | ملفّاتُ بيانات/Eval مُتتبَّعة | الـCI (خطوةٌ مستقلّة) + pre-commit (المسارات المحرّمة) | `tests/test_gate_registry.py` | `exit 1` |
| 9 | `tools/guard_bite_sweep.py` | **هل تعضّ كلُّ بوّابةٍ فعلاً؟** (تصنيفٌ ثلاثيّ من علامة pytest) | يدويًّا (١٤/١٤) | `tests/test_guard_bite_sweep_logic.py` | يُعلن «تعذّر التشغيل» عطباً لا نجاحاً |
| 10 | `tools/refs_exposure_probe.py` | مراجعُ `refs/pull/*` والتزاماتُ ما قبل التنقية | **مهمّةُ Hermes الأسبوعيّة** (لا CI — قرارُ المالك: سجلٌّ عامٌّ لا يُعلَن فيه ما لم يُطهَّر) | `tests/test_refs_probe_exit_code.py` | `rc=1` + `STILL EXPOSED` |

## ٣ · ما يقيسه الـCI بالضبط (لا وصفاً — يُقابَل بالملفّ)

`tools/publish_guard.py --tree --history --ci` · `tools/amount_guard.py --ci` · `tools/static_gate.py` ·
`tools/render_claims.py --check` · وخطوةُ الأدلّة، ثم **هذه الملفّات بالضبط**:

```
tests/test_compile_all.py
tests/test_requirements_lock.py
tests/test_public_claims.py
tests/test_gate_bites.py
tests/test_gate_registry.py
tests/test_secret_scan.py
tests/test_report_names.py
tests/test_turn_derivation.py
```

**وحدُّ ذلك مُعلَن:** `pytest` في المستودع يشغّل **٦٨٥** ضابطاً؛ والـCI يشغّل **هذه الثمانية** ⇒ منعُ
الانكشاف (الطبقتان ١ و٢) ما زال محمولاً بـ**الخطّافات المحلّيّة**، أي بأمانة النسخةِ المُهيّأة. ولذلك
**وُسِّعت قائمةُ الـCI في الجولة ٥٥** بثلاثة: `test_turn_derivation.py` · `test_report_names.py` ·
`test_secret_scan.py` (+ ملفُّ السجلّ نفسه) — فبوّابةٌ في فرعٍ لا يعبره الـCI **ليست بوّابة**.

## ٤ · ما لم يُثبت

- أنّ كلَّ نسخةٍ محليّة **مُهيّأة**: `core.hooksPath` يُضبط يدويًّا؛ والسجلُّ يذكر ذلك ولا يفرضه.
- أنّ الـCI يغطّي بقيةَ المستودع: **لا** — يشغّل ٤ ملفّات (أعلاه) وسجلُّ البوّابة الأسبوعيّة خارجَ الـCI بقرار.
- أنّ `static_gate` يعمل في pre-push بلا `pyflakes`: يتخطّى ويُعلن (وهذا ليس حراسة).
