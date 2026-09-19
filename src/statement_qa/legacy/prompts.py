"""Frozen VLM prompt set — inherited verbatim from the 629-page case
(scanned-pdf-ocr-pipeline skill, 2026-08-15/16). The owner directed rajhi-rag
to build ON TOP of that legacy instead of re-deriving prompts: "العلم تراكمي".

Source of truth:
- references/manual-anchor-validation.md (structure-aware red-band prompt)
- references/frontier-pass-workflow.md (era-neutral copy-exactly prompt)
- templates/marker_json_row_parser.py (row semantics + chain indexing)

These strings are FROZEN — proven on 629/629 pages. Do not paraphrase.
Only tune the parts marked [PROJECT-SPECIFIC].
"""

# --- Frontier pass: era-neutral, copy-exactly row extraction -------------------
# Proven: 509-page recovery pass lifted reconciliation 68% -> 94.7%.
FRONTIER_PROMPT = """أنت ناسخ أرقام دقيق لمستند مصرفي سعودي قديم. الصورة صفحة كشف حساب.
المطلوب: استخرج كل صف حركة. أعد JSON مصفوفة فقط بلا أي تعليق. لكل صف:
{"greg": "التاريخ الميلادي إن ظهر وإلا null", "desc": "البيان",
 "amount": "المبلغ تماماً كما هو مطبوع — انسخ أرقامه حرفياً بلا أي تحويل ولا حذف أصفار ولا إضافة فواصل",
 "balance": "الرصيد تماماً كما هو مطبوع إن وُجد وإلا null"}.
قواعد صارمة: (1) انسخ سلاسل الأرقام حرفياً مهما بدت غريبة، (2) لا تختلق أي رقم — null للباهت،
(3) لا تكتب التاريخ في خانة المبلغ أبداً، (4) JSON فقط،
(5) في **أول صف فقط** أضف مفتاحاً إضافياً "page_no": رقم الصفحة المطبوع في أعلى الصفحة
(أرقام عربية-هندية كما هي، وهو على نفس سطر مربع «بداية ونهاية معاملات الصفحة») — أو null إن لم يظهر."""

# --- Frontier pass v2: the printed COLUMN as an independent witness ------------
# [PROJECT-SPECIFIC change, 2026-09-18] The owner's contract rule (4.1/4.3): the
# bank prints two POSITIVE columns (مدين/دائن), so the direction is READ, not
# inferred. With the chain also deriving direction, every row then has two
# independent witnesses — and a disagreement is a defect signal, not a guess.
# V1 above stays untouched for comparison runs.
FRONTIER_PROMPT_V2 = """أنت ناسخ أرقام دقيق لمستند مصرفي سعودي قديم. الصورة صفحة كشف حساب.
المطلوب: استخرج كل صف حركة. أعد JSON مصفوفة فقط بلا أي تعليق. لكل صف:
{"greg": "التاريخ الميلادي إن ظهر وإلا null", "desc": "البيان",
 "col": "debit" أو "credit" أو null — العمود المطبوع الذي فيه المبلغ، لا تخمّنه من الإشارة",
 "amount": "المبلغ تماماً كما هو مطبوع — انسخ أرقامه حرفياً بلا أي تحويل ولا حذف أصفار ولا إضافة فواصل",
 "balance": "الرصيد تماماً كما هو مطبوع إن وُجد وإلا null"}.
قواعد صارمة: (1) انسخ سلاسل الأرقام حرفياً مهما بدت غريبة، (2) لا تختلق أي رقم — null للباهت،
(3) لا تكتب التاريخ في خانة المبلغ أبداً، (4) JSON فقط،
(5) في **أول صف فقط** أضف مفتاحاً إضافياً "page_no": رقم الصفحة المطبوع في أعلى الصفحة
(أرقام عربية-هندية كما هي، وهو على نفس سطر مربع «بداية ونهاية معاملات الصفحة») — أو null إن لم يظهر،
(6) العمود: إن كان المبلغ في عمود المدين فـ"debit"، وإن كان في عمود الدائن فـ"credit" — وإن لم تستطع
البتّ فـnull (لا تخمين، فالشاهد الكاذب أسوأ من غيابه).

**[تعليمة من مراجعة خارجية]** سطور **الإجماليات والملخص ليست حركات** ولا تُدرج في rows:
ما لا يحمل **رصيداً جارياً** مطبوعاً ليس حركة — مثل «اجمالي الايداعات» و«اجمالي السحوبات»
و«رصيد الاقفال» و«الرصيد الافتتاحي/الافتتاحى» و«الرصيد المتاح اليوم» و«أجمالي قيود محجوزة».
وأدرجها في حقل ``summary_lines`` بنصّها ومبلغها. وإدراجها في rows يُدخل سطوراً لا سلسلة
عليها فتُعلَن «غير مثبتة» وتُقرأ تواريخها مفقودةً — وقد وقع هذا في الصفحة الختامية (١٧ سطراً)."""

# --- Structure-aware re-read: owner's red-band anatomy ------------------------
# Reads ONLY transaction bands; ignores noise lines (W-/TOACCT..., branch names);
# captures the BLUE footer (cumulative totals + closing) as a per-page oracle.
STRUCTURE_AWARE_PROMPT = """Read ONLY what is inside each band. Ignore noise lines above/below the band.
For every row band in order: date as printed, MAIN Arabic operation name,
amount EXACT digits, balance EXACT digits. Footer totals if present.
Reply ONLY strict JSON: {"rows":[{"date","desc_main","amount","balance"}],
"footer":{"debits","credits","balance"}}. Arabic-Indic digits AS PRINTED.
null if unreadable. No prose."""

# --- Targeted top-band re-read (Trap 5 boundary recovery) ---------------------
TOP_BAND_PROMPT = """These are the FIRST transaction rows at the top of the movement table
on page {page_no} of an Al Rajhi statement. The PREVIOUS page ended with balance {prev_closing}.
List the first 3 transaction rows as JSON:
{{"rows":[{{"movement":"...","balance":"..."}}]}}
copy digits EXACTLY as printed in Arabic-Indic, null if unreadable, JSON only."""

# --- Hard rules extracted from the case (do not relearn these) ----------------
HARD_RULES = {
    "copy_exactly": "Never instruct a scale convention; 'copy EXACTLY, no conversion' — "
                    "instructing scale makes the model invent decimals.",
    "persian_digits": "Gemini mixes Persian ۰-۹ with Arabic-Indic ٠-٩ in ONE output — "
                      "translate BOTH tables or amounts silently vanish.",
    "chain_index": "balance prints AFTER the transaction: amt[i+1] == bal[i] − bal[i+1] "
                   "(NOT amt[i]). Wrong index read 0/9 on perfect data.",
    "offsetting_pairs": "Equal debit+credit pairs net to zero — invisible to chains "
                        "AND pages. Arithmetic + owner's eye, never budget re-reads.",
    "single_stream": "One OpenRouter vision stream per key; jittered backoff ≥10s "
                     "doubling to 60s on 429 (mass 429s killed 624/629 pages once).",
    "digit_guards": "Reject >8-digit strings (card/terminal numbers), 8-digit "
                    "strings starting 20/14 (dates), per-delta |d| < 2,000,000.",
    "footer_everywhere": "The blue footer exists on ALL eras (87/87 old pages) — "
                         "only ~5 pages truly lack it (172, 359, 484, 573, 602).",
    "desc_shift": "Descriptions shift by ONE row while amounts stay correct; "
                  "semantic-direction conflicts reveal it, realign by amount match.",
}
