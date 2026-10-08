```
id:      20261008-2358-sulaiman
class:   خطةُ جولةٍ (وثيقةُ تنفيذٍ قبل العمل) — لا تُجيب حُكماً ولا تُودِع شاهداً
to:      المالك · المدقّق
scope:   fix/closure-2026-10-08 @ 90069b3 (رأسُ الفرع) مقابل 8ebe827
```

# PLAN — إغلاق ملاحظات مراجعة ٩٩ (R99-1 · R99-2 · R99-3 + الصغائر الأربع)

**المُدخَل:** مراجعةُ ٩٩ على الفرع (`90069b3`) — `APPROVE WITH FIXES`، ثلاثُ P2 و أربعُ P3.
**المُخرَج المنتظر:** إصلاحٌ محروسٌ بضابطَين على الـ fixture `chat` · إعلانُ ملفّات الصندوق في
guardِ الأسماء · قياسُ ما بعد الإصلاح · تقريرٌ شامل.

## ١ · ما قِيس قبل كتابة سطر (Fatabayyanu — بلا تخمين API)

بيئةُ القياس: `~/Projects/rajhi-rag/.venv` (langchain 1.4.0 · langchain_core 1.6.3 · gradio 6.27.0 · langgraph 1.x).

| ما قِيس | الأمر | النتيجة |
| :--- | :--- | :--- |
| رسمٌ بحافظةٍ لا يُنادى بلا `thread_id` | `agent.invoke(...)` على `create_agent(checkpointer=MemorySaver())` | `ValueError: Checkpointer requires … thread_id` ⇒ **النداءُ يكتب أو يفشل** |
| `update_state` يكتب زوجًا | `agent.update_state(cfg, {"messages": [Human, AI]})` | يُلحق ✅ |
| `update_state` + `RemoveMessage` | حذفُ كلّ القديم ثمّ زوجٌ جديد | يبقى الزوجُ الجديدُ وحده ✅ |
| `HumanMessage`/`AIMessage` بعد الكتابة | `get_state(cfg).values["messages"]` | `id` لكلٍّ منها ✅ (فالقصُّ بالـid يبقى عاملًا) |
| `dynamic_prompt` + `context_schema` | `create_agent(middleware=[...], context_schema=Ctx)` + `invoke(context=Ctx(chunks=…))` | القطعُ في **رسالة النظام** والسؤالُ البشريُّ وحدَه ✅ (وبلا `context` ⇒ القالبُ كما هو) |
| استيرادُ الوسطاء | `langchain.agents.middleware` | `dynamic_prompt` · `ContextEditingMiddleware` · `ClearToolUsesEdit` موجودة |
| خطُّ الأساس على الفرع | `pytest tests/test_memory_acceptance_gate.py tests/the_memory_reaches… tests/answer_names…` | **16 ناجح · 1 فاشل** والفاشلُ R99-3 بالحرف ✅ |

## ٢ · الحركة (بمكوّنات المكتبة · قاعدةُ «لا تُعِد اختراع العجلة»)

**المخزنُ يبقى `MemorySaver`** (مكوّن LangGraph) بمعرّف الخيط نفسه `_ledger_key()`. ويتغيّر **مَن يكتب وماذا**:

1. **`_thread_messages` تُقرأ بالواجهة العامّة** (`get_state`) عبر حاملٍ صغيرٍ من LangGraph
   (`StateGraph(MessagesState)`) مشحونٍ بالحافظة نفسها — لا `get_tuple().checkpoint["channel_values"]`
   (هشّةٌ عند الترقية · R99-7).
2. **`_run_agent` صار نداءً بلا حافظة** (`checkpointer=None`): يقرأ النافذةَ من المخزن، **يمرّرها
   رسائلَ** في المدخل، ويستدعي. ⇒ لا كتابةَ لكلّ خطوة (لا محاولةَ مرفوضة، لا نتائجَ أدوات، لا
   `Answer` في الحافظة — R99-6 يسقط بالبناء).
3. **القطعُ تُحقن بخطّافٍ تشحنه LangChain** (`@dynamic_prompt` + `context_schema`): تُمرَّر في **سياق
   النداء** لا في الحالة ⇒ **لا تُحفظ** (R99-2). والسؤالُ البشريُّ المحفوظُ صار **السؤالَ وحدَه**.
4. **الكتابةُ واحدةٌ لكلّ سؤالِ مستخدم:** `_remember(thread_id, question, answer)` تكتب
   `[RemoveMessage(…الساقط…), HumanMessage(سؤالُ المستخدم), AIMessage(الجوابُ المعروض)]` بـ`update_state`.
   ونقطةُ النداء **`answer_question`** وحدَها (وحدَتُ الذاكرة = سؤالُ المستخدم) ⇒ المركّبُ **دورةٌ واحدة**،
   والمحاولةُ المرفوضةُ وتوجيهُ «استخدم أداة» **لا تُحفظ** (R99-1).
5. `_answer_one` ينادي `_answer_with_tools(remember=False)` — فالمحاولاتُ لا تُثبَّت، والصالحُ وحدَه يُكتب
   عند البوّابة العليا. (و`_run_agent` و`_answer_with_tools` يبقيان `remember=True` افتراضًا: عقدُ
   «دورةٌ تدخل ⇒ دورةٌ تُحفظ» الذي تقيسه ضوابطُهما القائمة **بلا تعديل** — ومسبارُ أثر الذاكرة يبقى صحيحًا.)
6. **`ContextEditingMiddleware` لا يُحتاج:** لا نتيجةَ أداةٍ تُحفظ أصلًا (الشرطُ «إن لزم» مقيسٌ نفيًا).

## ٣ · الضابطان (على الـ fixture `chat` في `tests/test_memory_acceptance_gate.py`)

- **R99-1:** سؤالٌ رقميّ يُجاب بلا أداة (يُرفض) ⇒ ثمّ سؤالٌ تابع ⇒ `REFUSED` **لا يبلغ النداءَ التالي**.
- **R99-2:** ثلاثةُ أسئلةٍ متتالية بقطعٍ **مُعلَّمةٍ بسؤالها** ⇒ النداءُ الثالثُ يحمل قطعَ سؤاله **وحدَه**،
  ولا يحمل قطعَ سؤالٍ سابقٍ ولا قطعًا محفوظةً في الرسائل.

## ٤ · الترتيب وحواجزُه

① الخطة (هذه) → ② التنفيذ + الضابطان → ③ فحوصُ الجودة (المجموعةُ كاملةً · `render_claims --check` ·
طفراتُ الضابطين) → ④ `/code-review-elite` بثلاثة مقاعدَ معزولة → ⑤ خطةُ الإغلاق + تنفيذُها →
⑥ التقريرُ الشامل + إعلانُ الملفّات في guardِ الأسماء + الالتزامُ والدفعُ إلى **الفرع** وقياسُ `ci_report`.
**ولا هبوطَ على `main` ولا كلفةَ بلا كلمة المالك.**
