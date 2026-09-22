```
id:      20260920-231400-claude
from:    claude
to:      sulaiman
type:    PROPOSAL
step:    التعديلات المطلوبة على البناء الحالي قبل تسليم الجامعة — مقيسة من الكود، لا مقترحة من الذاكرة
commit:  56a673b (origin/main وقت القراءة)
verdict: -
```

> **قاعدة هذه الوثيقة:** كل ادّعاء عن الكود مقيسٌ بأمرٍ مكتوب بجانبه. وكل ادّعاء عن
> إطارٍ خارجي موثَّقٌ برابطه. وما لم أقِسه قلتُ «لم يُقَس».

---

## ١) ما قرأته — البنية كما هي فعلاً

```
app.py (871 سطراً · Gradio عربي RTL)
 ├─ تبويب ١: قراءة وتحقق
 │    process_pdf → _process_pdf_locked (job_lock)
 │    _pages_to_pngs (pdf2image · 200dpi)
 │    → vlm_reader.read_rows_vlm  ── HTTP خام → OpenRouter
 │                                   MODEL = google/gemini-3.7-flash
 │    → chain_derive · recover_anchor · reread_boundary · fill_missing_dates
 │    → footer_oracle · ordering · era · row_audit · scope · bank_check
 │    → chunk_rows → build_index (FAISS + intfloat/multilingual-e5-small)
 └─ تبويب ٢: سؤال وجواب
      qa.answer → وكيل LangChain + qa_tools حتمية + أثر تنفيذ (trace)

tools/  to_xlsx(1109) · scale_slice(733) · publish_guard(634) · to_pdf(613)
        verify_close(292 · 25 فحصاً) · injection_test · page_gate · qa_gate …
tests/  ~282 اختباراً · test_gate_bites.py (24 سمّاً + 4 حرّاس)
البيانات: data/local_sample/slice_629p/results/pg-NNN.json   ← الحقيقة الفعلية (gitignored)
```

### ثلاثة قياسات تحكم كل ما بعدها

| # | المقيس | الأمر |
|---|---|---|
| **أ** | `profiles/al-rajhi.json` يقرؤه **ملفٌ واحد**: `tools/verify_close.py`. و**`src/statement_qa/` لا تقرؤه إطلاقاً** | `grep -rln "profiles/" src tools` |
| **ب** | قوائم الأوصاف **مكرّرة**: `row_audit.py:21` وفي العقد معاً | `grep -n "DEBIT_ONLY" src/statement_qa/row_audit.py` |
| **ج** | سطح LangChain كله **٤ مواضع**: `ChatOpenAI` · `create_agent` (qa.py) · `@tool` (qa_tools.py) · `HuggingFaceEmbeddings`+`FAISS` (retriever.py) | `grep -rn "langchain" --include="*.py" src tools app.py` |

**(أ) هي الأهمّ:** العقد اليوم **عقد بوابة**، لا محوِّل بنك. فإضافة بنكٍ ثانٍ تعني تعديل بايثون.

**(ج) خبرٌ سارّ:** الهجرة عن LangChain — إن اخترتها — أربعة استبدالات، لا إعادة كتابة.

---

## ٢) قرارٌ واحد يسبق الجدول

اشترطتَ إطاراً واحداً، وأنت محقّ — وأنا الذي بعثرتُ. لكن الاختيار يتوقّف على سؤالٍ **لا أستطيع التحقّق منه**: هل تشترط الجامعة LangChain بالاسم؟

| | **مسار أ — الإبقاء** | **مسار ب — PydanticAI فقط** |
|---|---|---|
| متى | إن كان LangChain **مطلوباً بالاسم** في التوصيف | إن كان المطلوب «مشروع ذكاء اصطناعي» |
| العمل | حصره في تبويب السؤال وحده · لا يمسّ الاستخراج | استبدال ٤ مواضع (§ج) |
| التبعيات | تبقى ١٦ | تنزل إلى **٩** |
| الكلفة | صفر | ١–٢ يوم |
| للتجاري | يُزال لاحقاً | جاهز |

**توصيتي: مسار ب** — وسببها مقيس، لا ذوق:

| ما يحتاجه مشروعك | PydanticAI v2 | المصدر |
|---|---|---|
| OpenRouter (مزوّدك الحالي) | مدعوم أصلاً: `Agent('openrouter:…')` أو `OpenRouterProvider` | [docs](https://pydantic.dev/docs/ai/models/openai/) |
| إدخال صور | `BinaryContent` · `ImageUrl` | [docs](https://pydantic.dev/docs/ai/advanced-features/input/) |
| مخرَج مقيَّد بمخطَّط | `output_type` + `ToolOutput`/`NativeOutput`/`PromptedOutput` | [docs](https://pydantic.dev/docs/ai/output/) |
| **إعادة القراءة عند فشل التحقّق** | `@agent.output_validator` + `ModelRetry` + ميزانية `retries` | [docs](https://pydantic.dev/docs/ai/output/) |
| الاستقرار | **v2 صدر 23 يونيو 2026** · v1 منذ سبتمبر 2025 | [releases](https://github.com/pydantic/pydantic-ai/releases) |

**والسطر الأخير هو الحجّة الحقيقية:** `recover_anchor` و`reread_boundary` عندك — ٦٦ سطراً من منطق «اقرأ، فإن لم تُقفل السلسلة أعد القراءة بشرط» — يصيران:

```python
@reader.output_validator
def chain_must_close(ctx, rows: PageRead) -> PageRead:
    bad = [r for r in derive(rows, ctx.deps.prev_balance) if not r.closes]
    if bad:
        raise ModelRetry(f"الصفوف {[r.no for r in bad]} لا تُقفل السلسلة — أعد قراءة مبالغها")
    return rows
```

**وقاعدتك «السلسلة حَكَم» تنتقل من كودٍ يُصان إلى شرطٍ في العقد.** هذا هو المكسب، لا حذف مكتبة.

> **ولستُ أوصي بـLangGraph ولا DSPy ولا CrewAI.** كانت تشتيتاً منّي. **إطارٌ واحد: PydanticAI.**

---

## ٣) جدول التعديلات

مرتَّب بالأولوية. `ج`=جامعة · `ت`=تجاري. الكلفة تقديرية.

| # | التعديل | لماذا (مقيس) | ج | ت | كلفة |
|---|---|---|---|---|---|
| **١** | **دفتر SQLite** مصدراً · الإكسل والـPDF رَندراً | البوابة تقرأ **عناوين أعمدة عربية** كعقد بيانات — وهو ما أنتج الفحص الميت الذي مرّ على تناقض ×333 | ✓✓ | ✓✓ | ٣–٤ ي |
| **٢** | **`Measured`**: القيمة وإثباتها كائنٌ واحد | كل عيبٍ خطير في ٩ جولات كان **نسبةَ رقمٍ إلى شاهده**. عمود «مصدر إثبات الحركة» علاجٌ بالعرض؛ هذا بالنوع | ✓✓ | ✓✓ | يومان |
| **٣** | **القلب يقرأ العقد** · حذف التكرار من `row_audit.py:21` | العقد يقرؤه ملفٌ واحد (§أ) ⇒ بنكٌ جديد = تعديل بايثون | ✓ | ✓✓✓ | يومان |
| **٤** | **حزمة تقييم مجمّدة**: ٢٠٠ صفحة + ٥٠ سؤالاً + ٣ مقاييس | عندك حقيقةٌ أرضية نادرة (٥٬٧٩١ صفّاً بقيدٍ رياضي) وتضيع بلا مقياس | ✓✓✓ | ✓✓ | يومان |
| **٥** | **PydanticAI بدل LangChain** (٤ مواضع) | §٢ — والفائدة الكبرى `output_validator` | ✓✓ | ✓✓ | ١–٢ ي |
| **٦** | **التقاط عيّنات التدريب** | **لا يُسترجَع بأثر رجعي.** تفصيله في خارطة الطريق | — | ✓✓✓ | يوم |
| **٧** | **واجهة PDF الرقمي** + مصنِّف `text/image/ocr_overlay` | أكّدتَ أن كشف التطبيق فيه رصيد جارٍ ⇒ يمرّ من نفس البوابة | ✓ | ✓✓✓ | ٣ ي |
| **٨** | **وحدة أرقام عربية واحدة** بجدول حالات | الفاصلة `,` عشرية/آلاف · `٫` · ٣ مجموعات. أنتجت **٣٨٥ فرقاً كاذباً** عندك و**٤٠٩** عندي | ✓ | ✓✓ | يوم |
| **٩** | **موازاة الصفحات** | 15.97 ث × 629 ≈ **2.8 ساعة** تسلسلياً · الصفحات مستقلّة | — | ✓✓ | يوم |

**نواة تسليم الجامعة = ١+٢+٤+٥ ≈ ٨–١٠ أيام عمل.**

---

## ٤) مخطّط SQL

**القاعدة الحاكمة — سطرٌ واحد:**

> **كل مبلغ `TEXT` لا `REAL`.** SQLite ليس فيه `DECIMAL`، و`REAL` عائم — وعائمٌ واحد يهدم «رقم بلا دليل لا يُقال».

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE source_document (
  doc_id        TEXT PRIMARY KEY,                 -- sha256 للملف
  bank          TEXT NOT NULL,
  layout        TEXT NOT NULL,                    -- branch_scan | app_digital
  source_kind   TEXT NOT NULL CHECK (source_kind IN ('scan','digital')),
  page_count    INTEGER NOT NULL,
  ingested_at   TEXT NOT NULL
);

CREATE TABLE page (
  doc_id         TEXT NOT NULL REFERENCES source_document(doc_id),
  page_no        INTEGER NOT NULL,
  printed_no     TEXT,                            -- نصّ: قد يكون '426 · 427'
  printed_no_src TEXT CHECK (printed_no_src IN ('read','derived','extrapolated')),
  content_kind   TEXT NOT NULL CHECK (content_kind IN ('text','image','ocr_overlay')),
  read_key       TEXT,        -- sha256(صورة + نسخة التلقينة + معرّف النموذج)
  model_id       TEXT, prompt_version TEXT,
  cost_usd       TEXT, ms_read INTEGER,
  PRIMARY KEY (doc_id, page_no)
);

CREATE TABLE printed_footer (                     -- شاهدٌ مستقل، لا يُشتقّ
  doc_id TEXT, page_no INTEGER,
  debits TEXT, credits TEXT, balance TEXT,
  PRIMARY KEY (doc_id, page_no),
  FOREIGN KEY (doc_id, page_no) REFERENCES page(doc_id, page_no)
);

CREATE TABLE ledger_row (
  row_id          INTEGER PRIMARY KEY,
  doc_id          TEXT NOT NULL, page_no INTEGER NOT NULL, row_no INTEGER NOT NULL,
  kind            TEXT NOT NULL CHECK (kind IN
                    ('movement','anchor','gap_entry','summary','opening')),
  date_iso        TEXT,
  date_source     TEXT CHECK (date_source IN ('cell','text','not_a_movement','missing')),
  descr           TEXT,
  printed_amount  TEXT,                           -- بخطّ الورق
  proven_amount   TEXT,
  proof_source    TEXT NOT NULL CHECK (proof_source IN
                    ('chain_delta','printed_paper','footer_residual')),
  proof_note      TEXT,                           -- «إعادة قراءة محكَّمة» …
  debit TEXT, credit TEXT, printed_balance TEXT, balance TEXT,
  UNIQUE (doc_id, page_no, row_no),
  FOREIGN KEY (doc_id, page_no) REFERENCES page(doc_id, page_no),
  -- قاعدةٌ كُتبت نثراً تسع جولات، تصير قيداً:
  CHECK (kind <> 'anchor' OR proof_source = 'printed_paper')
);

CREATE TABLE witness_verdict (
  row_id   INTEGER NOT NULL REFERENCES ledger_row(row_id),
  witness  TEXT NOT NULL CHECK (witness IN
             ('chain','page_footer','printed_column','position_ink','bank_summary')),
  verdict  TEXT NOT NULL CHECK (verdict IN ('agree','clash','not_applicable')),
  evidence TEXT, cost_usd TEXT,
  PRIMARY KEY (row_id, witness)
);

CREATE TABLE superseded_read (                    -- «لا يُحذف دليل» بنيةً لا نيّة
  row_id INTEGER NOT NULL REFERENCES ledger_row(row_id),
  field TEXT NOT NULL, old_value TEXT, new_value TEXT,
  reason TEXT NOT NULL, at TEXT NOT NULL
);

-- بحثٌ نصّي بلا تبعيات: FTS5 مدمج في SQLite
CREATE VIRTUAL TABLE row_fts USING fts5(
  descr, content='ledger_row', content_rowid='row_id', tokenize='unicode61'
);
```

**والمكسب في المناظير — «ما لم يُثبت» يُشتقّ ولا يُكتب:**

```sql
CREATE VIEW coverage AS
SELECT r.row_id,
       COALESCE(SUM(w.verdict='agree'),0) AS agree,
       COALESCE(SUM(w.verdict='clash'),0) AS clash
FROM ledger_row r LEFT JOIN witness_verdict w USING (row_id)
GROUP BY r.row_id;

CREATE VIEW unproven AS
SELECT r.* FROM ledger_row r JOIN coverage c USING (row_id)
WHERE r.kind IN ('movement','anchor') AND c.agree = 0;
```

> صفّا ٤٢٧ و٦٢٦ — اللذان استغرقا **خمس جولات** — كانا سيظهران في `coverage` **يوم بنائها**: `agree=0` و`kind='anchor'`.

---

## ٥) تفاصيل البنود الحرجة

### ٥·١ الهجرة إلى PydanticAI — المواضع الأربعة

| الموضع الحالي | البديل |
|---|---|
| `qa.py` → `ChatOpenAI` + `create_agent` | `Agent('openrouter:…', deps_type=…, output_type=…)` |
| `qa_tools.py` → `@tool` | `@agent.tool` (والأثر يُلتقط في `deps`) |
| `retriever.py` → `HuggingFaceEmbeddings` + `FAISS` | **SQLite FTS5** (أدناه) |
| `vlm_reader.py` → HTTP خام | `Agent` بـ`BinaryContent` + `output_type=PageRead` |

**وقرار FTS5 مقابل FAISS — قِسه ولا تفترضه:**

| | FAISS + e5 | FTS5 |
|---|---|---|
| التبعيات | `sentence-transformers` + `faiss-cpu` + `langchain-huggingface` (تجرّ torch ≈ GB) | **صفر** — داخل SQLite |
| يُحسن | التشابه الدلالي («مصاريف سفر» ↔ «حجز طيران») | المطابقة اللفظية (أسماء · تجّار · أنواع) |
| أوصاف الكشف | أكثرها **أسماء وعبارات ثابتة** | — |

**الافتراضي: FTS5.** وقِسه على الخمسين سؤالاً؛ فإن خسرتَ أكثر من ٥٪ في أسئلة البحث الوصفي، أعِد FAISS لتلك وحدها. **لا تحذف قبل القياس ولا تُبقِ بلا قياس.**

### ٥·٢ حزمة التقييم — وهي قسم النتائج في رسالتك

```
مجموعة أ — القراءة:   ٢٠٠ صفحة مجمّدة + حقيقتها الأرضية (من السلسلة)
                       المقياس: نسبة إغلاق السلسلة · مطابقة التذييل · إغلاق الهوية
مجموعة ب — السؤال:    ٥٠ سؤالاً + إجاباتها + صفوفها الصحيحة
                       ١) دقّة الرقم
                       ٢) صدق الاستشهاد ← نسبة الإجابات التي صفوفها المستشهَدة
                          هي التي بَنَت الرقم فعلاً (من الأثر، لا من النصّ)
                       ٣) صحّة الامتناع ← نسبة ما لا جواب له وامتنع عنه
```

**المقياس الثاني هو أطروحتك.** لا يقيسه أحدٌ عادةً لأنه يحتاج ما عندك: أثرُ تنفيذٍ يسجّل **ما بنى الرقم**. وهو مكتوبٌ في رأس `qa.py` منذ اليوم الأول — فحوّله من عقدٍ في تعليق إلى **رقمٍ في جدول**.

### ٥·٣ العقد الموسَّع (للبنك الثاني، وهو عندك اليوم)

```jsonc
{
  "bank": "al-rajhi",
  "layout": "branch_scan",            // ← بنكٌ واحد، تصميمان
  "source_kind": "scan",
  "statement": {
    "amount_model": "two_columns",    // two_columns | signed_single | amount_plus_type
    "balance_column": { "present": true, "running": true },   // ⚠ الأخطر
    "date": { "calendar": "gregorian", "also_printed": ["hijri"] },
    "row_model": "single_line",
    "footer": { "role": "cumulative_printed_totals" },        // | per_page | absent
    "labels": { "debit_only": [...], "credit_only": [...] }   // ← المصدر الوحيد
  },
  "witnesses": {
    "chain":          { "available": true },
    "page_footer":    { "available": true },
    "printed_column": { "available": true },
    "position_ink":   { "available": true, "cost_usd_per_page": "0.006" },
    "bank_summary":   { "available": true, "page": "last" }
  }
}
```

**وأول خطوة عملية تكشف بقيّة التسريبات:**

```python
# احذف الثابتين من row_audit.py ومرّرهما
def desc_direction_clash(rows, *, debit_only, credit_only): ...
```

كل موضعٍ يشتكي عند التمرير هو موضعُ تسريبٍ آخر. **اتبع الأعطال، لا التخمين.**

---

## ٦) المحظورات

| ⛔ | لماذا |
|---|---|
| **`REAL` لأي مبلغ** | يهدم الأساس. `TEXT` + `Decimal` دائماً |
| **أكثر من إطار** | PydanticAI وحده. ولا LangGraph ولا DSPy ولا CrewAI |
| **حذف FAISS قبل قياس FTS5** | ولا إبقاؤه بلا قياس |
| **الثقة بالمسار الرقمي بلا بوابة** | أخطر قرار في البند ٧ |
| **عناوين إكسل عربية كمفاتيح برمجية** | مصدر الفحص الميت |
| **تعديل `FRONTIER_PROMPT` بلا مفتاح نسخة** | يخلط الأجيال — كما خلط «5,606/5,607» على كوربوس ٥٬٧١٨ لم يعد قائماً |
| **إضافة فحصٍ للبوابة بلا سمّ** | `test_every_gate_check_has_a_poison` يُسقطه — أبقِه |
| **بيانات حقيقية في git** | `publish_guard` يمسكها — لا تُضعفه |

---

## ٧) بوابة قبول هذه الدفعة

```bash
V=~/Projects/rajhi-rag/.venv/bin/python
$V -m pytest -q                                   # لا تراجع
$V tools/verify_close.py --run … --xlsx … | tail -1   # ALL PASS ✓
$V tools/injection_test.py --xlsx … --run …       # 3/3
$V tools/publish_guard.py | tail -1               # آمن
# والثوابت لا تتزحزح:
# 5,811 · Σمدين 594,683.32 · Σدائن 382,772.74 · 570.59 · 5,791 حركة · 5,791 تاريخاً
```

**وزيادةٌ تخصّ هذه الدفعة:** بعد بناء الدفتر، **رَندِر الإكسل منه وقابله بالملف الحالي صفّاً بصفّ.** فرقٌ واحد = توقّف. الترحيل لا يُقبل بـ«يبدو صحيحاً».

---

next: قرار §٢ (مسار أ أم ب) أولاً — فهو يحدّد البند ٥. وبعده ١ و٢ معاً، فهما تعديلٌ واحد.
      وخارطة الطريق إلى النموذج في `20260920-231400-roadmap-to-specialist-model.md`.
