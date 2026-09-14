# كيف تستأنف في 10 دقائق

> هذا الملف يجيب سؤال «من أين أكمل؟» بعد انقطاع. المسار: خدمة سليمة → بوابة خضراء → حالة مفهومة → ابدأ من المهمة المؤشرة في `PLAN.md`.

## ١. الخدمة تعمل؟ (دقيقة)

```bash
python3 tools/health_check.py
```

إن ظهر ✗ استخدم `tools/install_services.sh` — **ولا تفعل `kickstart` أثناء احتمال تشغيل جارٍ** (يقتل المهمة).

## ٢. الجودة سليمة؟ (٣–٥ دقائق)

```bash
source .venv/bin/activate
python tools/qa_gate.py --full
```

أي FAIL = لا عمل جديد على أساس معطوب. أصلح أولاً.

## ٣. أين وصلنا؟ (دقيقتان)

- آخر commits: `git log --oneline -10`
- المرحلة الحالية: `PLAN.md` (التأشيرات داخله)
- الحالة الأدق والأحدث: `~/.hermes/skills/ai-study-mentoring/references/rajhi-rag-state.md`
- آخر تقرير سلايس: `data/local_sample/slice_*/slice_report.md`

## ٤. خريطة الملفات المهمة (دقيقة)

| ماذا تريد؟ | أين؟ |
|---|---|
| القارئ (VLM + التطبيع الحتمي) | `src/statement_qa/vlm_reader.py` + `legacy/arabic_digit_parser.py` |
| السلسلة الرصيدية (الحَكَم) | `vlm_reader.chain_derive` |
| أوراكل الفوتر | `src/statement_qa/footer_oracle.py` |
| كاشف الصيغ + الترتيب | `src/statement_qa/era.py` · `ordering.py` |
| الأنواع (تصنيف الوصف) | `src/statement_qa/classify.py` |
| أدوات السؤال الحتمية | `src/statement_qa/qa_tools.py` + `qa.py` |
| الواجهة | `app.py` |
| بوابة الجودة | `tools/qa_gate.py` + `docs/QA_CHECKLIST.md` |
| بوابة النشر | `tools/publish_guard.py` + `.publish-allowlist` |
| التوسع المقيس | `tools/scale_slice.py` |
| صحة الخدمة | `tools/health_check.py` + سجل `~/Library/Logs/rajhi-health.log` |
| عقود G2/G3 | `docs/OPERATIONS.md` |

## ٥. قواعد لا تُنسى

1. **لا `kickstart`** للخدمة أثناء احتمال تشغيل المالك — يقتل مهمته الجارية.
2. **لا بيانات حقيقية في git** — بوابة pre-push تمنع؛ والاستثناء بسبب مكتوب في `.publish-allowlist` فقط.
3. **كل «تم» تحتاجه البوابة**: `qa_gate --full` + عين على الرندر للأرقام الجديدة.
4. **البرومبتات المجمّدة لا تُلمس** إلا ببروتوكول G2 (`docs/OPERATIONS.md`).
