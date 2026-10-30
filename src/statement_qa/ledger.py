"""دفترُ الكشف — SQLite محلّيّة، مصدراً للجدول المُتحقَّق منه (أ-٣).

**قرارُ المالك (2026-10-02 · `docs/COURSE_REQUIREMENTS.md:29,57`):** «قاعدةُ SQLite محلّيّة لكلّ كشف»
⇒ **ملفٌّ واحدٌ لكلّ كشفٍ على جهاز المستخدم، تحت مسارٍ مُهمَلٍ لا يُتتبَّع أبدًا**، يقرؤه الوكيلُ
باستعلاماتٍ ثابتةٍ في الكود. **والنموذجُ لا يكتب SQL**: عقدُ «النموذجُ لا يحسب» قائم.

**ولماذا دفترٌ لا ملفّات JSON** (`results/pg-*.json`): الملفّاتُ تصلح للتشغيل الواحد ولا تصلح لما
يُسأل عنه لاحقًا — «ما الذي لم يُثبت؟» يُجاب بمرورٍ على ٦٢٩ ملفًّا في كلّ سؤال، ولا سلسلةَ استعلاماتٍ
ولا فهرسَ نصّيّ. والدفترُ يجعل السؤالَ استعلامًا واحدًا **ومحصورًا في الكود** (لا يُولّده نموذج).

**وثلاثةُ قيودٍ تُبنى في المخطَّط لا في النيّة** (الخارطة أ-٣):
1. **المبالغُ `TEXT` لا `REAL`**: `CHECK(typeof(...))` ⇒ فلا يدخل رقمٌ عشريٌّ عائم ويُطبَع برقمٍ عائمٍ طويلٍ لا يُقرأ.
   والقيدُ **يعضّ** على الإدخال نفسه، لا يُنبَّه عليه في التوثيق.
2. **الفهرسُ لا ينطفئ صامتًا**: triggers على `INSERT/UPDATE/DELETE` تُبقي `row_fts` تابعًا؛ وبلاها
   يُدرَج صفٌّ فلا يُوجَد بالبحث أبدًا — عطبٌ صامتٌ لا شاهدَ له (الخارطةُ تنصّ عليه بالاسم).
3. **«ما لم يُثبت» يُشتقّ**: المنظارُ `unproven` هو مصدرُه الوحيد؛ فلا تُكتب القائمةُ بيدٍ في تقرير.

**والخطأُ مسمّى** (بندُ الإرشادات): قاعدةٌ غائبةٌ أو تالفة ⇒ `LedgerUnavailable` برسالةٍ تسمّي السبب،
**بلا انهيار** — لأنّ المستخدمَ النهائيّ إنسانٌ ينظر، لا مطوّرٌ يقرأ traceback.

**والاختبارُ الحاسم** (`tests/test_ledger.py`): ما يُكتب يُقرأ **صفًّا بصفّ** — قيدٌ واحدٌ يُخالف ⇒ أحمر.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

#: مسارُ الدفتر **داخل مجلّد بيانات المستخدم** — قرارُ المالك (R130 · الخيار ١): «القاعدةُ في مجلّد
#: بيانات المستخدم وحده، ولا تدخل المستودع». فالمسارُ الجذريُّ صار **مُعطًى من الخارج** (`root`)،
#: والتطبيقُ يمرّر `data_home()` لا جذرَ المستودع؛ وما بقي تحت `data/` في الشجرة **مُهمَلٌ** (حراسةٌ
#: ثانيةٌ للاختبارات والمسارات القديمة): `git check-ignore` يشهد، و`publish_guard` يحجب `.sqlite`.
LEDGER_SUBDIR = ("data", "ledgers")

#: **مجلّدُ بيانات المستخدم** — موضعٌ واحد: متغيّرُ بيئةٍ للتشغيل المعزول والاختبار، ثمّ مجلّدُ
#: التطبيق النظاميّ (macOS: `~/Library/Application Support`؛ غيرُه: `XDG_DATA_HOME`).
#: **ولماذا لا `<repo>/data`:** قرارُ المالك نصَّ على ألّا تدخل القاعدةُ المستودعَ؛ فالمسارُ هنا
#: خارجَ الشجرة بالبناء، والإهمالُ يبقى حراسةً لمن يمرّر جذرًا قديمًا.
APP_DIRNAME = "rajhi-rag"


def data_home() -> Path:
    """مجلّدُ بيانات المستخدم للتطبيق — يُنشأ عند الحاجة ولا يُخترع له مسارٌ ثالث."""
    env = os.environ.get("RAJHI_DATA_HOME")
    if env:
        return Path(env).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIRNAME
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_DIRNAME


def source_sha256(path) -> str:
    """تجزئةُ **بايتات ملفّ الكشف** — دالّةُ الهويّة الواحدة (R132-2).

    تُنادِيها المساراتُ الثلاثة: الواجهةُ عند القراءة · القارئُ عند كتابة التقرير · الـCLI عند
    البناء. و`hashlib.file_digest` (بايثون 3.11+) تقرأ بالكتل داخل المكتبة — لا حلقةَ تجزئةٍ يدويّة.
    """
    with open(path, "rb") as fh:
        return hashlib.file_digest(fh, "sha256").hexdigest()


def statement_key(source_sha: str) -> str:
    """مفتاحُ الكشف = تجزئةُ **هويّة المصدر** (`source_sha256`) — **وبلا هويّةٍ لا مفتاح.**

    **العِلّة (R130→R132):** كان المفتاحُ يُجزّئ بصمةَ صيغة الأرقام، فكشفان بالطول والصيغة نفسَيهما
    يتصادمان؛ ثم صار يُجزّئ بايتات الملفّ **مع احتياطيٍّ** إلى البصمة القديمة. والاحتياطيُّ هو العطبُ
    نفسُه: كلُّ تقريرٍ قائمٍ بلا `source` كان يقع عليه صامتًا. فحُذف: مصدرٌ بلا بايتاتٍ **لا يُعطي
    مفتاحًا** — والـCLI يرفض ويسمّي `--source`، والواجهةُ تُمرّر الملفَّ دائمًا.
    """
    if not source_sha:
        raise ValueError("هويّةُ الكشف مطلوبة — مصدرٌ بلا بايتاتٍ لا يُعطي مفتاحًا "
                         "(الـCLI: مرّر --source)")
    return "st_" + hashlib.sha1(str(source_sha).encode("utf-8")).hexdigest()[:10]


#: **حالةُ الدفتر** — القيمةُ الوحيدةُ التي تُنشر عن توفّره هي ما تقوله هذه الدالّة.
MISSING = "missing"
CORRUPT = "corrupt"
#: **وحالةٌ ثالثة (مقعدُ البنية P3 · مُثبت):** كان كلُّ `sqlite3.DatabaseError` يُسمّى «تالفة»،
#: فبيئةٌ بلا وحدة `fts5` (`no such module: fts5`) أو عطبٌ في البناء يُعرَض للمستخدم «قاعدتُك تالفة»
#: ⇒ **علاجٌ خاطئ** (يُعيد الملفَّ والصوابُ بناءُ البيئة). فالعطبُ الذي ليس «ليست قاعدةَ بيانات»
#: يُسمّى باسمه: `unsupported`.
UNSUPPORTED = "unsupported"
#: **وحالةٌ رابعةٌ بالقياس (مقعدُ التثبيت P3 · مُثبت):** `unable to open database file` ليست «البيئةُ لا
#: تدعم» — بل **مسارٌ أو إذن** (مجلّدٌ أُعطي كقاعدةٍ، أو ملفٌّ بلا إذن قراءة): قِيس أنّ الحالتين كانتا
#: تُسمّيان `unsupported` ⇒ **علاجٌ خاطئ** (بناءُ البيئة بدل تصحيح المسار). فلكلٍّ اسمُه.
UNREADABLE = "unreadable"
#: **والترقيم (أ-٣ · البندُ الرابع):** الدفترُ **بياناتٌ مُشتقّة** — فمسارُ ترقيته ليس هجرةً صامتةً
#: تُخمّن، بل: قاعدةٌ أقدمُ من الكود ⇒ `outdated` (أعدْ بناءَها من المصدر، وهو رخيصٌ ومُتاح)، وقاعدةٌ
#: أحدثُ من الكود ⇒ `newer` (لا يُقرأ بمخطَّطٍ لا يعرفه الكاتب). وما بينهما لا يُخمَّن أبدًا.
OUTDATED = "outdated"
NEWER = "newer"
#: نسخةُ المخطَّط الحاليّة. **تُرفع مع كلّ تغييرٍ بنيويّ،** ويُقيَّد الترقيمُ في `PRAGMA user_version`.
#: **v2 (R130):** `rows_verified.seq` (رقمُ الصفّ على مستوى الكشف) و`pages.footer_*` (أرقامُ التذييل
#: المطبوع كما ظهرت في الورقة) — فتُجيب أدواتُ الوكيل من القاعدة وحدَها: الأرقامَ وأحكامَ الصفحاتِ
#: وتذييلاتِها، بلا حالةِ واجهةٍ في الذاكرة. قاعدةٌ v1 تُعلَن `outdated` وتُعاد من المصدر (رخيصة).
SCHEMA_VERSION = 2


class LedgerUnavailable(RuntimeError):
    """**خطأٌ مسمّى** لقاعدةٍ غائبةٍ أو تالفة — يُعرَض للمستخدم بلفظه، لا يُسقِط التطبيق.

    **العِلّة:** بندُ الإرشادات يطلب «قاعدةٌ غيرُ متاحة ⇒ خطأٌ مسمّى»؛ و`sqlite3.OperationalError`
    الخام يقول «unable to open database file» — وهي رسالةٌ لمطوّرٍ لا لمستخدمِ كشفِ حساب.
    """

    def __init__(self, state: str, path: Path, detail: str = "") -> None:
        self.state, self.path, self.detail = state, path, detail
        why = {
            MISSING: "قاعدةُ البيانات غيرُ موجودة",
            CORRUPT: "قاعدةُ البيانات غيرُ قابلةٍ للقراءة (تالفة)",
            UNSUPPORTED: "قاعدةُ البيانات غيرُ مدعومةٍ في هذه البيئة",
            UNREADABLE: "قاعدةُ البيانات غيرُ قابلةٍ للفتح (مسارٌ أو إذن)",
            OUTDATED: "قاعدةُ البيانات أقدمُ من الكود (أعِدْ بناءَها من المصدر)",
            NEWER: "قاعدةُ البيانات أحدثُ من الكود (حدّث الكود أو أعِد البناء)",
        }.get(state, "قاعدةُ البيانات غيرُ متاحة")
        super().__init__(f"{why}: {path.name}" + (f" — {detail}" if detail else ""))


#: **التطبيعُ العربيّ**: ما يفترق في الورق ويتّحد في المعنى. و`remove_diacritics 2` في FTS5
#: يكفي للتشكيل وحده؛ وهذه الدالّة تُكمله بما لا يفعله: الهمزاتُ بأشكالها · التاءُ المربوطة ·
#: التطويل · الألفُ المقصورة · الأرقامُ العربيّةُ الهنديّة (تُقرأ في الورق وتُكتب في السؤال).
_AR_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و",
    "ة": "ه", "ـ": "", "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})
_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06dc\u06df-\u06e8\u06ea-\u06ed]")


def norm_ar(text: str | None) -> str:
    """الصورةُ المُطبَّعة: تُقابَل بها نصوصُ الصفوف وبها يُطبَّع السؤالُ قبل البحث.

    والقاعدةُ: **البحثُ لا يعتمد على ما كتبه المُدخِل** — «اجمالي الايداعات» و«إجماليّ الإيداعات»
    و«اجمالى الايداعات» صفٌّ واحدٌ في العين، فليكن صفًّا واحدًا في الفهرس أيضًا.
    """
    if not text:
        return ""
    return _DIACRITICS.sub("", str(text)).translate(_AR_MAP).strip()


#: **المخطَّط.** كلُّ قيدٍ فيه يحمل علّته بجانبه، لأنّ قيدًا بلا علّةٍ يُحذَف عند أوّل ضيق.
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- صفحاتُ الكشف: حكمُ التذييل لكلّ صفحة (قرارُ المالك: «أحكامَ التذييل لكلّ صفحة»).
-- **وأرقامُ التذييل المطبوع as-is (R130):** تُقرأ من الورقة، لا تُعاد للجمع؛ وأدواتُ الوكيل تقرؤها
-- من هنا (`page_footer`) فلا تعتمد على حالةٍ في الذاكرة. وفارغةٌ تعني «لم يُقرأ» لا «صفر».
CREATE TABLE IF NOT EXISTS pages (
    pg              INTEGER PRIMARY KEY,
    printed_page    TEXT,
    verdict         TEXT NOT NULL CHECK (verdict IN
                      ('ok','gap','mismatch','absent','unchecked','other')),
    rows_count      INTEGER NOT NULL DEFAULT 0,
    footer_debits   TEXT,
    footer_credits  TEXT,
    footer_balance  TEXT,
    footer_basis    TEXT,
    cost_usd        TEXT,                       -- كلفةُ الصفحة: TEXT لا REAL (المالُ لا يُطبَع عائمًا)
    CHECK (cost_usd IS NULL OR typeof(cost_usd) = 'text'),
    CHECK (footer_debits  IS NULL OR typeof(footer_debits)  = 'text'),
    CHECK (footer_credits IS NULL OR typeof(footer_credits) = 'text'),
    CHECK (footer_balance IS NULL OR typeof(footer_balance) = 'text')
);

-- الجدولُ المُتحقَّق منه: أعمدةُ الرندر **الاثنان والعشرون** نفسُها (فيُقابَل صفًّا بصفّ).
CREATE TABLE IF NOT EXISTS rows_verified (
    id               INTEGER PRIMARY KEY,
    -- **رقمُ الصفّ على مستوى الكشف (R130):** ترتيبُ الصفوف في المعالجة (المؤشّرُ الذي تستعمله
    -- الأدواتُ والمصادرُ وأرقامُ الصفحات)، مخزَّنًا فلا يعيد القارئُ اشتقاقَه من `pg` — فترتيبُ
    -- الملفّ قد يختلف عن ترتيب الكشف الحقيقيّ (صفحاتٌ مقلوبةٌ بشاهد). يُكتب في `ingest` من ترتيب
    -- الصفوف الوارد، ويُقرأ به `read_rows` ⇒ أرقامُ الأدوات من القاعدة تُطابق أرقامَ الشاشة.
    seq              INTEGER,
    pg               INTEGER NOT NULL REFERENCES pages(pg) ON DELETE CASCADE,
    row_no           INTEGER NOT NULL,
    printed_page     TEXT,
    date             TEXT,
    date_iso         TEXT,
    date_status      TEXT,
    date_source      TEXT,
    year             INTEGER,
    desc             TEXT,
    -- **العمودُ المُطبَّع مُشتقٌّ في القاعدة نفسِها** (`GENERATED ... STORED` بدالّة `norm_ar` المُسجَّلة
    -- في `open_ledger`): فلا يُكتب بيدٍ ولا يفترق عن `desc` بتحديثٍ مباشر. وكان يمكن أن يُكتب ويُنسى
    -- ⇒ يصير الفهرسُ يحمل نصًّا قديمًا **صامتًا** (قِيس: تحديثُ `desc` وحدَه ثمّ بحثٌ عن الجديد ⇒ صفر).
    desc_norm        TEXT GENERATED ALWAYS AS (norm_ar(desc)) STORED,
    printed_movement TEXT,
    printed_balance  TEXT,
    movement         TEXT,
    balance          TEXT,
    derived_movement TEXT,
    side             TEXT,
    opening          TEXT,
    chain_ok         INTEGER,
    row_state        TEXT,
    -- **والاسمُ من المواصفة لا من الرندر:** الخارطةُ سمّته `proof_source` (سطر ١٧٠) والرندرُ يقول
    -- `source`؛ فالعمودُ بالمواصفة، والترجمةُ مُعلَنةٌ في `_row_values` وفي مقابلة الاختبار.
    proof_source     TEXT,
    shift            TEXT,
    footer           TEXT,
    counted          INTEGER,
    -- **قيدُ المبلغ**: TEXT أو غيابٌ — ولا ثالث (فلا يُطبَع مبلغٌ برقمٍ عائمٍ طويلٍ في كشفٍ قانونيّ).
    CHECK (movement         IS NULL OR typeof(movement)         = 'text'),
    CHECK (printed_movement IS NULL OR typeof(printed_movement) = 'text'),
    CHECK (printed_balance  IS NULL OR typeof(printed_balance)  = 'text'),
    CHECK (balance          IS NULL OR typeof(balance)          = 'text'),
    CHECK (derived_movement IS NULL OR typeof(derived_movement) = 'text'),
    -- **قيدُ المرساة (أ-٣: «CHECK للمرساة + proof_source»)**: صفٌّ وُسم مرساةً **يجب** أن يعلن
    -- مصدرَ إثباته؛ وإلّا فهو ادّعاءٌ بلا شاهد — وهو بعينه ما تمنعه قاعدةُ «ما لم يُثبت».
    CHECK (row_state IS NULL OR row_state NOT LIKE '%مرساة%'
           OR (proof_source IS NOT NULL AND proof_source <> '')),
    UNIQUE (pg, row_no)
);

CREATE INDEX IF NOT EXISTS idx_rows_page  ON rows_verified(pg, row_no);
CREATE INDEX IF NOT EXISTS idx_rows_seq   ON rows_verified(seq);
CREATE INDEX IF NOT EXISTS idx_rows_date  ON rows_verified(date_iso);
CREATE INDEX IF NOT EXISTS idx_rows_state ON rows_verified(row_state);

-- سجلُّ الأسئلة والأجوبة مع صفوف الدليل (قرارُ المالك: «سجلَّ الأسئلة والأجوبة مع صفوف الدليل»).
CREATE TABLE IF NOT EXISTS qa (
    id         INTEGER PRIMARY KEY,
    asked_at   TEXT NOT NULL,
    question   TEXT NOT NULL,
    answer     TEXT,
    refused    INTEGER NOT NULL DEFAULT 0,   -- الامتناعُ نتيجةٌ مُعلَنة لا فراغ
    CHECK (refused IN (0, 1))
);

CREATE TABLE IF NOT EXISTS qa_evidence (
    qa_id  INTEGER NOT NULL REFERENCES qa(id) ON DELETE CASCADE,
    row_id INTEGER NOT NULL REFERENCES rows_verified(id) ON DELETE CASCADE,
    PRIMARY KEY (qa_id, row_id)
);

-- **الفهرسُ النصّيّ.** `remove_diacritics 2` يُسقط التشكيلَ من الطرفين، والعمودُ `desc_norm`
-- يحمل تطبيعَ الهمزات/التاء/التطويل الذي لا يفعله المُقطِّع.
CREATE VIRTUAL TABLE IF NOT EXISTS row_fts USING fts5(
    desc_norm, printed_movement, movement,
    content='rows_verified', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);

-- **والتبعُ إجباريّ**: بلا هذه الثلاثة ينطفئ الفهرسُ صامتًا (يُدرَج صفٌّ فلا يوجد أبدًا).
CREATE TRIGGER IF NOT EXISTS rows_ai AFTER INSERT ON rows_verified BEGIN
    INSERT INTO row_fts(rowid, desc_norm, printed_movement, movement)
    VALUES (new.id, new.desc_norm, new.printed_movement, new.movement);
END;
CREATE TRIGGER IF NOT EXISTS rows_ad AFTER DELETE ON rows_verified BEGIN
    INSERT INTO row_fts(row_fts, rowid, desc_norm, printed_movement, movement)
    VALUES ('delete', old.id, old.desc_norm, old.printed_movement, old.movement);
END;
CREATE TRIGGER IF NOT EXISTS rows_au AFTER UPDATE ON rows_verified BEGIN
    INSERT INTO row_fts(row_fts, rowid, desc_norm, printed_movement, movement)
    VALUES ('delete', old.id, old.desc_norm, old.printed_movement, old.movement);
    INSERT INTO row_fts(rowid, desc_norm, printed_movement, movement)
    VALUES (new.id, new.desc_norm, new.printed_movement, new.movement);
END;

-- **المنظاران المشتقّان** — «ما لم يُثبت» لا يُكتب بيدٍ في تقرير، بل يُقرأ من هنا.
CREATE VIEW IF NOT EXISTS coverage AS
    SELECT p.pg, p.printed_page, p.verdict, p.rows_count,
           (SELECT COUNT(*) FROM rows_verified r WHERE r.pg = p.pg)      AS rows_stored,
           (SELECT COUNT(*) FROM rows_verified r WHERE r.pg = p.pg
              AND r.counted = 1)                                          AS rows_counted,
           (SELECT COUNT(*) FROM rows_verified r WHERE r.pg = p.pg
              AND r.chain_ok = 0)                                         AS rows_broken_chain
      FROM pages p;

CREATE VIEW IF NOT EXISTS unproven AS
    SELECT r.id, r.pg, r.row_no, r.printed_page, r.desc,
           COALESCE(r.balance, r.printed_balance) AS amount,
           r.row_state, r.proof_source
      FROM rows_verified r
     WHERE (r.proof_source IS NULL OR r.proof_source = '')
       AND COALESCE(r.row_state, '') NOT LIKE '%ملخّص%';
"""

#: أعمدةُ الصفّ كما تُقرأ — **أسماءُ الرندر نفسُها** (فتُقابَل صفًّا بصفّ بلا ترجمة).
COLUMNS = (
    "pg", "row_no", "printed_page", "date", "date_iso", "date_status",
    "date_source", "year", "desc", "printed_movement", "printed_balance", "movement",
    "balance", "derived_movement", "side", "opening", "chain_ok", "row_state",
    "proof_source", "shift", "footer", "counted",
)

#: أعمدةُ الإدراج = أعمدةُ القراءة (و`desc_norm` عمودٌ مُشتقٌّ في القاعدة ⇒ لا يُدرَج).
INS_COLUMNS = COLUMNS


#: **سياسةُ الأنواع — مُقاسةٌ على 5809 صفًّا من مصدرك، لا مُفترَضة** (مقعدُ التثبيت P2 · مُثبت):
#:  · `BOOL` (`opening` · `chain_ok`): الرندرُ يحملها `bool`، وSQLite بلا نوعٍ منطقيّ ⇒ تُخزَّن `0/1`
#:    وتُقرأ `bool` — وإلا فـ`chain_suspect` (يشترط `is False`) **لا يصدُق على `0`**، وبناءُ الاشتقاق يسقط.
#:  · `INT` (`page` · `row_no` · `printed_page` · `year` · `counted`): تُقرأ أعدادًا — وإلا اختلفت الخليّةُ
#:    (نصٌّ `'1'` مقابل عددٍ `1`) في 11881 خليّةً (قِيس).
#:  · `DEC` (`derived_movement`): الرندرُ يحملها `Decimal` ⇒ تُخزَّن `TEXT` (دقّةٌ لا تفقد) وتُقرأ `Decimal`.
#:  · **والمالُ `str` في الرندر نفسِه** (قِيس: 5792 نصًّا) ⇒ `TEXT` مطابقٌ له لا مخالف.
#: والقاعدة: عمودٌ يقرؤه المستهلك بغير نوعه = **مصدرٌ ناقص**، ولو تساوت قيمتُه.
BOOL_COLUMNS = ("opening", "chain_ok")
INT_COLUMNS = ("pg", "row_no", "printed_page", "year", "counted")   # `pg` لا `page`: اسمُ العمود في الجدول
#: (مقعدُ الترتيب P3: كان مُدخَلًا خاملًا لا يُطابَق — فلا نوعَ يُفرَض على `pg`)
DEC_COLUMNS = ("derived_movement",)


def _typed(col: str, v):
    """يُعيد قيمةَ العمود بنوعه المُعلَن — و`None`/الفراغ يبقيان `None` (17 صفًّا بلا رصيدٍ في مصدرك)."""
    if v is None:
        return None
    if v == "" and col in (*BOOL_COLUMNS, *INT_COLUMNS, *DEC_COLUMNS):
        return None          # فراغٌ في عمودٍ مُقيَّمٍ = لا قيمة؛ وأمّا النصُّ فالفراغُ فيه قيمةٌ (قِيس)
    if col in BOOL_COLUMNS:
        return v if isinstance(v, bool) else bool(int(v))
    if col in INT_COLUMNS:
        return int(v)
    if col in DEC_COLUMNS:
        return Decimal(v)
    return v


def _row_values(r: dict) -> tuple:
    """صفُّ الرندر ⇒ أعمدةُ الإدراج — **والتحويلُ والترجمةُ في موضعٍ واحد**.

    **العِلّةُ المقيسة (أمسكتها بوّابةُ المقابلة صفًّا بصفّ على بيانات المالك):** صفوفُ الرندر تحمل
    `decimal.Decimal` للمبالغ، و`sqlite3` **لا يُسندها**: `ProgrammingError: Error binding parameter 14`.
    وكان الإدراجُ يمرّ في الاختبار الاصطناعيّ (صفوفٌ نصّيّةٌ بيد) ويسقط على المصدر الحقيقيّ — وهو بعينه
    ما تنصّ البوّابةُ عليه: تُقاس على المصدر لا على نموذجٍ منه.

    **والقاعدة:** المالُ نصٌّ (`str`) كما في عقد أ-٣ · والأعلامُ المنطقيّةُ `0/1` (لا `True/False`
    فتتفرّق القراءة) · والأعدادُ الصحيحةُ كما هي. **وما لا يُعرف نوعُه يُنصَّص** ولا يُمرَّر خامًّا.

    **واسمان مُترجَمان بالعِلّة (لا بالعادة):** الرندرُ يقول `page` والمواصفةُ سمّت `proof_source`
    (الخارطة أ-٣) والرندرُ يقول `source` — فالترجمةُ هنا **مُعلَنةٌ في موضعٍ واحد**، ويقابلها في
    الاختبار `_want`، ويُقاس تساوي العقدين في ضابطٍ مجموعيّ (لا بالاحتواء).
    """
    out: list = []
    for c in COLUMNS:
        if c == "pg":
            v = r.get("page")
        elif c == "proof_source":
            v = r.get("source")
        else:
            v = r.get(c)
        if isinstance(v, bool):
            v = int(v)
        elif v is not None and not isinstance(v, (int, str, bytes)):
            v = str(v)
        out.append(v)
    return tuple(out)


def ledger_path(root: Path, statement: str) -> Path:
    """مسارُ دفترِ كشفٍ واحد: `<root>/data/ledgers/<statement>.sqlite` (مُهمَلٌ ✗ يُتتبَّع)."""
    safe = re.sub(r"[^0-9A-Za-z_.\-]", "-", statement) or "statement"
    return root.joinpath(*LEDGER_SUBDIR, f"{safe}.sqlite")


def _has_tables(conn: sqlite3.Connection) -> bool:
    return any(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))


def _db_file(conn: sqlite3.Connection) -> Path:
    """مسارُ قاعدة المتّصل — **من المحرّك نفسِه لا من خريطةٍ عالميّة** (مقعدُ التثبيت P3 · مُثبت).

    **العِلّة:** كانت خريطةٌ عالميّة `{id(conn): path}` تنمو بلا تنظيف، و`id()` يُعاد استخدامُه بعد
    تحرير المتّصل ⇒ اسمُ ملفٍّ خاطئ في رسالة الخطأ. و`PRAGMA database_list` مصدرٌ لا يتسرّب ولا يخطئ.
    """
    try:
        for _seq, name, f in conn.execute("PRAGMA database_list"):
            if name == "main" and f:
                return Path(f)
    except sqlite3.Error:
        pass
    return Path(":memory:")


def open_ledger(path: Path, *, create: bool = True, readonly: bool = False) -> sqlite3.Connection:
    """يفتح الدفترَ أو يُنشئه، **ويُسمّي العطب** بدل أن يرفع خطأً خامًّا.

    والتفريقُ مقصود: `missing` (لا ملفّ) و`corrupt` (ملفٌّ ليس قاعدةً أو بنيتُه مكسورة) — لأنّ
    علاجَهما مختلف: الأوّل يعيد المستخدمُ التشغيلَ، والثاني يعني ملفًّا أُفسِد.

    **ولا كتابةَ على قاعدةٍ قائمة (إصلاحُ مقعدَي البنية والمعايير · مُثبت):** كان `executescript(SCHEMA)`
    و`PRAGMA user_version` يُنفَّذان في **كلّ فتحٍ** — وكلُّ سؤالٍ يفتح القاعدةَ للقراءة ⇒ قفلُ كتابةٍ
    على الملفّ الذي تحمله حافظةُ المحادثةُ بمتّصلٍ ثانٍ. فصار المخطَّطُ يُنفَّذ عند **الإنشاء** وحدَه،
    والقاعدةُ القائمةُ تُتحقَّق (ترقيمٌ + جداول) بلا كتابة؛ و`readonly=True` يفتحها بـ`mode=ro` فيمنع
    الكتابةَ من الأصل.
    """
    path = Path(path)
    # **ومجلّدٌ ليس قاعدة (إصلاحُ فتحٍ للقراءة P2):** `mode=ro` على مجلّدٍ يُرجع «disk I/O error»
    # فيُقرأ «تالفًا»؛ والحقيقةُ مسارٌ خاطئ — فتُسمّى قبل الاتّصال.
    if path.is_dir():
        raise LedgerUnavailable(UNREADABLE, path, "المسارُ مجلّدٌ لا ملفُّ قاعدة")
    fresh = not path.exists()
    if fresh:
        if not create:
            raise LedgerUnavailable(MISSING, path)
        if readonly:
            raise LedgerUnavailable(MISSING, path)
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if readonly:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        else:
            conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        # **ودالّةُ التطبيع تُسجَّل قبل المخطَّط**: العمودُ المُشتقُّ `desc_norm` يعتمد عليها،
        # و`deterministic=True` شرطٌ في أعمدة SQLite المُولَّدة (وبلا الشرط يرفضها المحرّك).
        conn.create_function("norm_ar", 1, lambda s: norm_ar(s), deterministic=True)
        # **الترقيمُ قبل البناء** (وإلا فقاعدةٌ أحدثُ تُقرأ بمخطَّطٍ لا يعرفه هذا الكود):
        have = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if have not in (0, SCHEMA_VERSION):
            state = OUTDATED if have < SCHEMA_VERSION else NEWER
            raise LedgerUnavailable(state, path, f"user_version={have} والكودُ {SCHEMA_VERSION}")
        if have == 0 and _has_tables(conn):
            # قاعدةٌ سبقت الترقيم: مخطَّطُها مجهولٌ بالنصّ ⇒ لا يُخمَّن، والدفترُ مُشتقٌّ فإعادتُه رخيصة.
            raise LedgerUnavailable(OUTDATED, path, "قاعدةٌ بلا ترقيم — أعدْ بناءَها من المصدر")
        if fresh or not _has_tables(conn):
            # ملفٌّ جديدٌ أو ملفٌّ فارغٌ موجود: هنا وحدَه يُنفَّذ المخطَّط.
            conn.executescript(SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            conn.commit()
        return conn
    except sqlite3.DatabaseError as e:
        # **والتفريقُ بين «ليست قاعدةَ بيانات» و«البيئةُ لا تدعمها» (مقعدُ البنية P3 · مُثبت):** ملفٌّ
        # ليس قاعدةً يرفع `file is not a database`، وغيابُ وحدةٍ (`no such module: fts5`) أو عطبُ
        # إمكانٍ يرفع غيرَه — وعلاجُهما مختلف: الأوّلُ يُعاد الملفُّ، والثاني يُبنى في البيئة. فكان
        # كلُّ عطبٍ يُسمّى «تالفة» ⇒ علاجٌ خاطئ.
        msg = str(e)
        low = msg.lower()
        if "no such module" in low or "not authorized" in low:
            state = UNSUPPORTED          # البيئةُ لا تدعم وحدةً (fts5) ⇒ يُبنى في البيئة
        elif "unable to open" in low:
            state = UNREADABLE           # مسارٌ أو إذن (مجلّدٌ كقاعدة) ⇒ يُصحَّح المسار، لا البيئة
        else:
            state = CORRUPT              # «ليست قاعدةَ بيانات» أو بنيةٌ مكسورة
        raise LedgerUnavailable(state, path, f"{type(e).__name__}: {msg}") from e


def read_ledger(path: Path) -> sqlite3.Connection:
    """يفتح الدفترَ **للقراءة وحدَها**: قاعدةٌ غائبةٌ تُعلَن `missing`، وقائمةٌ تُفتح بـ`mode=ro` فلا
    تأخذ قفلَ كتابةٍ ولا تُنفّذ مخطَّطًا (إصلاحُ مقعدَي البنية والمعايير — كلُّ سؤالٍ كان يكتب).
    """
    return open_ledger(Path(path), create=False, readonly=True)


def _text(value) -> str | None:
    """**كلُّ مبلغٍ نصٌّ** — يمرّ من هنا وحدَه، فلا يُنسى قيدُ `TEXT` في موضع."""
    return None if value is None else str(value)


def ingest(conn: sqlite3.Connection, rows: list[dict], pages: dict[int, dict],
           report: dict | None = None, n_pages: int | None = None) -> dict:
    """يكتب الجدولَ المُتحقَّق منه وأحكامَ الصفحات في معاملةٍ واحدة — **ويُزيل ما لم تعد القراءةُ تحمله.**

    **والمصدرُ هو مخرَجُ `tools/to_xlsx.load` نفسُه** لا نسخةً ثانيةً منه: نسخةٌ ثانيةٌ من بناء
    الصفوف تعني حكمين يُفترقان صامتين، والبوّابةُ («يُقرأ صفًّا بصفّ») تُقابِل مصدرًا بمصدر.

    **والحذفُ داخلَ المعاملة نفسِها (R130 · قرارُ المالك):** «إعادةُ القراءة تُحدّثها ولا تُبقي نسخةً
    قديمةً تحت «جاهز»». كان `ON CONFLICT DO UPDATE` يُحدّث الموجودَ **ويترك ما سقط من القراءة
    الجديدة** ⇒ قاعدةٌ تحمل صفوفًا من قراءةٍ سابقة بجانب صفوف اليوم، ولافتةُ «جاهز» تُقرأ عليها.
    فصار ما لم يعد في القراءة **يُحذف باسمه** (صفحاتٌ ثمّ صفوفٌ) في نفس المعاملة: إمّا أن تنطبق
    القراءةُ كلُّها أو لا شيء. **ولا يُحذف صفٌّ ثمّ يُعاد إدراجُه:** التحديثُ يحفظ `id` فيبقى
    `qa_evidence` (الدليلُ المرتبطُ بالسؤال) — والحذفُ لا يمسّ إلّا ما لا وجودَ له في القراءة الجديدة.
    """
    written = 0
    # **وعدُ الصفوف في الصفحة يُشتقّ من الصفوف نفسِها** (قاسته بوّابةُ المسارين): كان يُؤخذ من
    # `per_page` ⇒ فصفحةٌ حكمُها `absent` وفيها 17 صفًّا تُعَدّ صفرًا. فصارت للعمود **دلالةٌ واحدة**:
    # «كم صفًّا في الدفتر لهذه الصفحة». **والسببُ المقيسُ لذلك الفرق عدّادُ التقرير**
    # (`per_page[629] = {rows: 0, footer: 'absent'}`) — لا «صفوفٌ بلا صفحة» كما نسبتُ أوّلًا
    # (وعددُها صفر؛ التصحيحُ في `rows_without_page`). `pg INTEGER PRIMARY KEY` ⇒ **فصفٌّ بلا صفحة
    # لا يُمكِن إبقاؤه هنا**: يُستبعَد ويُعدّ في `dropped_no_page` بدل أن يُسقَط صامتًا أو يُخترع له رقم.
    dropped_no_page = sum(1 for r in rows if r.get("page") is None)
    rows = [r for r in rows if r.get("page") is not None]
    per_page_rows: dict = {}
    for r in rows:
        per_page_rows[r.get("page")] = per_page_rows.get(r.get("page"), 0) + 1
    kept_rows = {(int(r["page"]), int(r["row_no"])) for r in rows if r.get("row_no") is not None}
    # **والقاعدةُ تمثّل الوثيقةَ لا ما قُرئ منها (R132-1):** صفحةٌ لم تُقرأ هذه المرّة (لا صفوفَ
    # ولا تذييل) كان لها أثرٌ صفر ⇒ فبعد إعادة التشغيل يقول التطبيق «الكشف من صفحتين» عن كشفٍ من
    # ثلاث، ويُنكر صفحةً داخلة. فتُكتب **صفحةٌ لكلّ صفحةِ وثيقة** بحالة `unread`، ويبقى عدُّ الصفحات
    # ومعرفةُ «لم تُقرأ» بعد إعادة التشغيل كما في الجلسة.
    pages = dict(pages or {})
    kept_pages = {int(pg) for pg in pages}
    doc_pages = max([int(n_pages or 0), *kept_pages, 0])
    # **وبلا ترقيةِ مخطَّط — سببُها القيدُ لا قاعدةٌ قائمة:** `verdict` قيدُه CHECK لا يقبل قيمةً
    # جديدة، وترقيةُ v2⇒v3 تعني مسارَ هجرةٍ يُختبر ويُصان مقابلَ عمودٍ نصّيٍّ حرٍّ يكفي. فالوسمُ في
    # `footer_basis='unread'` والدالّةُ `unread_pages` تقرؤه، والحكمُ يبقى `other` فلا يكذب على قيدٍ
    # قائم. **ولا قاعدةَ للمالك في أيّ مكانٍ الآن** (لا مجلّدَ بياناتِ مستخدمٍ ولا `*.sqlite` في
    # مجلّدَي النشر والعمل — مقيسٌ في مراجعة ١٣٣): فالادّعاءُ بأنّ الترقيةَ «تُبطل قاعدةً حيّة» غيرُ
    # قائم، والتصميمُ يبقى لأنّه الأصغرُ لا لأنّه يتفادى إبطالًا.
    for pg in range(1, doc_pages + 1):
        pages.setdefault(pg, {"footer": "other", "basis": "unread", "page_no": None, "rows": 0})
    kept_pages = set(range(1, doc_pages + 1))
    pruned_rows = pruned_pages = 0
    with conn:
        for pg, entry in sorted(pages.items()):
            verdict = (entry.get("footer") or "other")
            if verdict not in {"ok", "gap", "mismatch", "absent", "unchecked", "other"}:
                verdict = "other"
            cost = (entry.get("usage") or {}).get("cost") if isinstance(entry.get("usage"), dict) else None
            conn.execute(
                "INSERT INTO pages(pg, printed_page, verdict, rows_count, cost_usd, "
                "                  footer_debits, footer_credits, footer_balance, footer_basis) "
                "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(pg) DO UPDATE SET "
                "printed_page=excluded.printed_page, verdict=excluded.verdict, "
                "rows_count=excluded.rows_count, cost_usd=excluded.cost_usd, "
                "footer_debits=excluded.footer_debits, footer_credits=excluded.footer_credits, "
                "footer_balance=excluded.footer_balance, footer_basis=excluded.footer_basis",
                (pg, str(entry.get("page_no")) if entry.get("page_no") else None, verdict,
                 int(per_page_rows.get(pg, 0)), _text(cost),
                 _text(entry.get("debits")), _text(entry.get("credits")),
                 _text(entry.get("balance")), _text(entry.get("basis"))),
            )
        sets = ", ".join(f"{c}=excluded.{c}" for c in INS_COLUMNS if c not in ("pg", "row_no"))
        for seq, r in enumerate(rows, start=1):
            # **`ON CONFLICT … DO UPDATE` لا `INSERT OR REPLACE` (مقعدا المواصفة والبنية · مُثبت):**
            # `OR REPLACE` يحذف الصفَّ ثمّ يُدرجه ⇒ يتبدّل `id`، و`ON DELETE CASCADE` يمسح
            # `qa_evidence` ⇒ **فقدانُ دليلِ الأسئلة صامتًا** عند إعادة قراءة كشفٍ سُئل عنه.
            # والتحديثُ يُبقي المعرّفَ فيبقى الدليل.
            conn.execute(
                f"INSERT INTO rows_verified(seq, {', '.join(INS_COLUMNS)}) "
                f"VALUES(?, {', '.join('?' for _ in INS_COLUMNS)}) "
                f"ON CONFLICT(pg, row_no) DO UPDATE SET seq=excluded.seq, {sets}",
                (seq, *_row_values(r)),
            )
            written += 1
        # **التقليمُ بعدهما:** المشطورُ القديمُ (صفحةٌ أو صفٌّ) لم تعد القراءةُ تحمله.
        # **السياسةُ الواحدة (R131-3):** ما لم تعد القراءةُ تحمله يُحذف — ولو كانت صفحةً تعثّرت
        # هذه المرّة. فصفوفُ القاعدة هي صفوفُ هذه القراءة، وترقيمُها متّصلٌ وفريد، والشاشةُ والأدواتُ
        # تقرأ الشيءَ نفسه. والصفحةُ المتعثّرة تُسمّى في سطر الحالة، ولا تُخدَم صفوفُ الأمس.
        for pid, pg, row_no in conn.execute(
                "SELECT id, pg, row_no FROM rows_verified").fetchall():
            if (int(pg), int(row_no)) not in kept_rows:
                conn.execute("DELETE FROM rows_verified WHERE id = ?", (pid,))
                pruned_rows += 1
        for (pg,) in conn.execute("SELECT pg FROM pages").fetchall():
            if int(pg) not in kept_pages:
                conn.execute("DELETE FROM pages WHERE pg = ?", (pg,))
                pruned_pages += 1
    return {"pages": len(pages), "doc_pages": doc_pages,
            "rows": written, "dropped_no_page": dropped_no_page,
            "pruned_rows": pruned_rows, "pruned_pages": pruned_pages,
            "unread_pages": [pg for pg in sorted(pages) if (pages[pg].get("basis") == "unread")]}


def read_rows(conn: sqlite3.Connection, pg: int | None = None) -> list[dict]:
    """يُعيد الصفوفَ بأسماء الرندر نفسها — **لتُقابَل صفًّا بصفّ** (البوّابةُ الحاسمة).

    **والترتيبُ بـ`seq` لا بـ`pg` (R130):** رقمُ الصفّ على مستوى الكشف هو ما تعرضه الشاشةُ وتستشهد
    به الأدواتُ؛ وترتيبُ الملفّ قد يختلف عن ترتيب الكشف الحقيقيّ. و`seq` يُكتب من ترتيب المعالجة،
    فالقارئُ من القاعدة يُرقّم كما تُرقّم الشاشة — لا كما تُرتّب أرقامُ الصفحات. و`COALESCE` يُبقي
    قاعدةً قديمةً بلا `seq` مقروءةً بترتيبٍ معقول بدل أن تُسقط الصفوف.
    """
    sql = f"SELECT COALESCE(seq, id) AS seq, {', '.join(COLUMNS)} FROM rows_verified"
    args: tuple = ()
    if pg is not None:
        sql += " WHERE pg = ?"
        args = (pg,)
    sql += " ORDER BY COALESCE(seq, id), pg, row_no"
    # **و`page` يُضاف إلى مخرَجِ القراءة (إصلاحُ العطب P0 · اتّفق عليه المقاعد الثلاثة):** القاعدةُ
    # تسمّي العمود `pg`، وكلُّ مستهلكٍ (إعادةُ بناء الحالة · حاجزُ النطاق · `ingest` عند إعادة البناء)
    # يقرأ `page` ⇒ كانت الصفوفُ تعود بلا صفحة فتُسقَط كلُّها وتُقلَّم. فالسطحُ يُخرج الاسمَين:
    # `page` للقرّاء (كما وعد تعليقُ الدالّة أصلاً) و`pg` لمن يخاطب SQL.
    # **و`source` كذلك (2026-10-30):** عكسُ الترجمتين في `_row_values` هنا بجانبها — كان `proof_source`
    # يعود باسم العمود وحدَه، فصفوفٌ مقروءةٌ تُعاد كتابتُها تكتب كلَّ إثباتٍ فارغًا (قِيس في
    # `test_a_ledger_rebuilt_from_its_own_rows_is_the_same_ledger`).
    return [{**{c: _typed(c, row[c]) for c in COLUMNS},
             "page": int(row["pg"]), "source": row["proof_source"], "seq": int(row["seq"])}
            for row in conn.execute(sql, args)]


def read_footers(conn: sqlite3.Connection) -> dict[int, dict]:
    """التذييلاتُ المطبوعة لكلّ صفحة **من القاعدة** — بالصيغة التي تستهلكها `qa_tools.page_footer`.

    **العِلّة (R130 · الخيار ١):** الأدواتُ صارت تقرأ من القاعدة نفسِها، فلا يكفي أن تُخزَّن أحكامُ
    الصفحات؛ الأرقامُ المطبوعة (مدين/دائن/رصيد) هي ما يُجيب عنه `page_footer`، وكانت في حالة
    التطبيق وحدَها. فتُكتب في `pages` وتُقرأ من هنا — **وتُترك `None` إن لم تُقرأ** (لا صفرَ يُخترع).
    """
    out: dict[int, dict] = {}
    for row in conn.execute(
            "SELECT pg, printed_page, verdict, footer_debits, footer_credits, "
            "       footer_balance, footer_basis FROM pages ORDER BY pg"):
        out[int(row["pg"])] = {
            "page": int(row["pg"]),
            "printed_page": row["printed_page"],
            "debits": row["footer_debits"],
            "credits": row["footer_credits"],
            "balance": row["footer_balance"],
            "verdict": str(row["verdict"] or "unchecked"),
            "basis": str(row["footer_basis"] or ""),
        }
    return out


def search(conn: sqlite3.Connection, query: str, limit: int = 20) -> list[dict]:
    """بحثٌ نصّيّ **باستعلامٍ ثابتٍ في الكود** — النموذجُ يمرّر نصًّا ولا يكتب SQL.

    **وزمنُ السؤال يُنقّى قبل دخوله صيغةَ FTS5 (مقعدُ المعايير F4 · مُثبت بالقياس):** كان النصُّ
    يُقحَم بين علامتَي تنصيصٍ بلا تهريب، فسؤالٌ فيه `"` يرفع
    `sqlite3.OperationalError: unterminated string` — انهيارٌ خامٌ على نصٍّ يكتبه نموذجٌ أو إنسان.
    والقاعدة: **يُستخرج الحرفُ والرقمُ وحدَهما** (`\\w` بـ`re.UNICODE`)، وكلُّ ما سواهما (تنصيص ·
    أقواس · `*` · `:` · `NEAR`) **يُحذف قبل الصيغة** — فلا تُبنى الصيغةُ من مدخلٍ إلّا من حروفه.
    """
    needle = norm_ar(query)
    tokens = [t for t in re.findall(r"\w+", needle, re.UNICODE) if t]
    if not tokens:
        return []
    match = " OR ".join(f'"{t}"' for t in tokens)
    try:
        rows = conn.execute(
            "SELECT r.id, r.pg, r.row_no, r.desc, r.printed_movement, r.movement "
            "FROM row_fts f JOIN rows_verified r ON r.id = f.rowid "
            "WHERE row_fts MATCH ? ORDER BY rank LIMIT ?",
            (match, limit),
        )
        return [dict(r) for r in rows]
    except sqlite3.DatabaseError as e:      # صيغةٌ رفضها المحرّك بعد التنقية ⇒ خطأٌ مسمّى لا انهيار
        raise LedgerUnavailable(UNSUPPORTED, _db_file(conn),
                                f"{type(e).__name__}: {e}") from e


def unproven(conn: sqlite3.Connection) -> list[dict]:
    """«ما لم يُثبت» — **من المنظار، لا من قائمةٍ مكتوبةٍ في تقرير**."""
    return [dict(r) for r in conn.execute(
        "SELECT id, pg, row_no, printed_page, desc, amount, row_state, proof_source FROM unproven")]


def record_qa(conn: sqlite3.Connection, asked_at: str, question: str, answer: str | None,
              row_ids: list[int], refused: bool = False) -> int:
    """يسجّل سؤالًا وجوابَه **وصفوفَ دليله** — فالجوابُ يُقابَل بأثره لا يُصدَّق بلفظه."""
    with conn:
        cur = conn.execute(
            "INSERT INTO qa(asked_at, question, answer, refused) VALUES(?,?,?,?)",
            (asked_at, question, answer, 1 if refused else 0))
        qid = int(cur.lastrowid)
        conn.executemany("INSERT OR IGNORE INTO qa_evidence(qa_id, row_id) VALUES(?,?)",
                         [(qid, int(i)) for i in row_ids if i is not None])
    return qid

#: **الأقصدُ الثابتة (البندُ الثاني · «النموذجُ لا يكتب SQL»).** وهذا هو الفرقُ العمليّ بين **وكيلٍ يقرأ
#: قاعدة** و**وكيلٍ يُنفّذ استعلاماتٍ مُخترَعة**: هنا تُعدَّد الأسئلةُ المسموحُ بها، ويُقبَل **معاملٌ بقيمةٍ
#: فقط** (`pg=`/`q=`) — فالوكيلُ يختار قصدًا ويُمرّي قيمةً، ولا يبني نصَّ SQL أبدًا. وما لا قصدَ له لا يُجاب.
INTENTS: tuple[str, ...] = ("coverage", "unproven", "totals", "search", "pages", "qa")


def _dec_sum(values) -> str:
    """جمعُ المال **بالعشريّ لا بالعائم** — ولو كان المجموعُ عمودًا نصّيًّا في SQLite.

    **العِلّة:** `SUM()` على عمودٍ نصّيٍّ في SQLite يُحوّل إلى `REAL` ⇒ كسرٌ ثنائيٌّ في المال، وهو
    أوّلُ ما يُسقِط التدقيق. فالجمعُ يُقرأ نصًّا ويُجمَع `Decimal`، والقيمةُ تُعاد نصًّا بلا فاصلةٍ زائدة.
    """
    total = sum((Decimal(v) for v in values if v not in (None, "")), Decimal("0"))
    return format(total, "f")


def answer(conn: sqlite3.Connection, intent: str, *, pg: int | None = None,
           q: str | None = None, limit: int = 20) -> dict:
    """يُجيب عن **قصدٍ من `INTENTS`** — ويُرفض ما ليس منها بالاسم (لا استعلامٌ حرّ).

    والقيمُ المعادة تشمل **الوسمَ** (`intent`) و**البيئةَ** (عدُّ ما قُرئ) ليقترن كلُّ رقمٍ بسياقه.
    """
    if intent not in INTENTS:
        raise ValueError(f"قصدٌ غيرُ مُعدَّد: {intent!r} — المسموح: {', '.join(INTENTS)}")
    if intent == "coverage":
        rows = conn.execute("SELECT COUNT(*) FROM rows_verified").fetchone()[0]
        pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        unproven_n = conn.execute("SELECT COUNT(*) FROM unproven").fetchone()[0]
        verdicts = {v: n for v, n in conn.execute(
            "SELECT COALESCE(verdict,'-'), COUNT(*) FROM pages GROUP BY 1 ORDER BY 2 DESC")}
        # **وتُسمّى الصفحاتُ غيرُ المقروءة بالرقم (R132-1):** عدُّها لا يكفي — واللافتةُ تحتاج
        # أسماءَها لئلّا تُقرأ «جاهزة» فوق فجوة.
        unread = [int(pg) for (pg,) in conn.execute(
            "SELECT pg FROM pages WHERE footer_basis = 'unread' ORDER BY pg")]
        return {"intent": intent, "rows": rows, "pages": pages,
                "unproven": unproven_n, "page_verdicts": verdicts, "unread_pages": unread}
    if intent == "unproven":
        got = unproven(conn)
        return {"intent": intent, "count": len(got), "rows": got[:limit]}
    if intent == "totals":
        rows = read_rows(conn)
        debit = [r["movement"] for r in rows if r["side"] == "debit"]
        credit = [r["movement"] for r in rows if r["side"] == "credit"]
        return {"intent": intent, "rows_counted": len(rows),
                "debit": _dec_sum(debit), "credit": _dec_sum(credit),
                "debit_rows": len(debit), "credit_rows": len(credit)}
    if intent == "search":
        return {"intent": intent, "query": q, "rows": search(conn, q or "", limit=limit)}
    if intent == "pages":
        sql = "SELECT pg, printed_page, verdict, rows_count, cost_usd FROM pages"
        args: tuple = ()
        if pg is not None:
            sql += " WHERE pg = ?"
            args = (pg,)
        return {"intent": intent, "pages": [dict(r) for r in conn.execute(sql + " ORDER BY pg", args)]}
    got = conn.execute(
        "SELECT q.id, q.asked_at, q.question, q.answer, q.refused, COUNT(e.row_id) AS evidence "
        "FROM qa q LEFT JOIN qa_evidence e ON e.qa_id = q.id GROUP BY q.id ORDER BY q.id DESC LIMIT ?",
        (limit,)).fetchall()
    return {"intent": intent, "qa": [dict(r) for r in got]}

def pages_of(rows: list[dict]) -> int:
    """عددُ صفحاتِ الكشف من صفوفه — تعريفٌ واحدٌ يُستعمل في التسمية والحالة والبناء."""
    return len({r.get("page") for r in (rows or []) if r.get("page") is not None})


def rows_without_page(rows: list[dict]) -> int:
    """صفوفٌ **بلا حقل صفحةٍ في المصدر** — تُعدّ وتُعلَن، ولا يُخترع لها صفحة.

    **وهي صفرٌ في مصدرك (قِيس: 0 من 5809)** — فلا تدّعِ أنّها سببُ فرقٍ ما. وأُبقي العدُّ لأنّ
    المخطَّطَ يمنع صفًّا بلا صفحة (`pg INTEGER PRIMARY KEY`) ⇒ فمتى وُجد صفٌّ كذلك **يُستبعَد
    ويُعدّ**، ولا يُسقَط بصمت.

    **وتصحيحُ نسبةٍ خاطئة (طعنَ فيه مقعدُ الواجهة وكان محقًّا · مُثبت):** كنتُ كتبتُ أنّ فرقَ
    `(629, 17)` مقابل `(629, 0)` سببه «17 صفًّا بلا صفحة» — **وهذا خطأٌ مقيس**: الصفوفُ السبعةَ
    عشر تحمل `page=629` نفسَها. والسببُ الحقيقيُّ **عدّادُ التقرير**: `per_page[629] = {rows: 0,
    footer: 'absent', page_no: 630}` في `slice_report.json`. ⇒ فالدعوى صُحّحت، والعدُّ بقي أداةً
    لحالةٍ أخرى (صفٌّ بلا صفحة) لا تفسيرًا لهذا الفرق.
    """
    return sum(1 for r in (rows or []) if r.get("page") is None)


def pages_from_state(rows: list[dict], footers: dict | None = None) -> dict[int, dict]:
    """مدخلاتُ `pages` كما يقرؤها `ingest` — **من حالة التطبيق الحيّة** (بلا polars وبلا نموذج).

    **ولماذا في الوحدة لا في `app.py` (وهو الذي يستدعيها):** هي **المصدرُ الثاني** لبناء الدفتر
    (الأوّل `tools/to_xlsx.load`)، ومصدران بلا ضابطٍ يفترقان صامتين. فالدالّةُ نقيّةٌ هنا، **وضابطٌ
    يقابل بينهما** (نفسُ الصفوف ونفسُ أحكام الصفحات) في `tests/test_ledger_ui.py`.

    **وحدُّها المُعلَن:** `cost_usd` **لا يُملأ** من هذا المسار — فحالةُ التطبيق تحمل كلفةً كلّيّةً لا
    كلفةَ صفحة، والعمودُ يعني كلفةَ الصفحة. فيبقى `None` (يُملأ في مسار الأداة من `to_xlsx`)، ولا
    يُخترع توزيعٌ على الصفحات. و«الرقمُ بلا بيئته دعوى»: فالمصدرُ يُعلَن مع كلّ رقمٍ يخرج من هنا.
    """
    per: dict[int, dict] = {}
    for r in rows or []:
        pg = r.get("page")
        if pg is None:
            continue
        e = per.setdefault(int(pg), {"page_no": None, "footer": "unchecked",
                                     "rows": 0, "usage": None})
        e["rows"] += 1
        if e["page_no"] is None and r.get("printed_page") is not None:
            e["page_no"] = r["printed_page"]          # الرقمُ المطبوعُ من الصفوف لا من مصدرٍ آخر
    for pg, f in (footers or {}).items():
        e = per.setdefault(int(pg), {"page_no": None, "footer": "unchecked",
                                     "rows": 0, "usage": None})
        f = f or {}
        e["footer"] = str(f.get("verdict") or "unchecked")
        # **والأرقامُ المطبوعة كما ظهرت (R130):** تُخزَّن في `pages` فيقرؤها `page_footer` من القاعدة.
        # و`None` يبقى `None` — «لم يُقرأ» لا «صفر».
        for key in ("debits", "credits", "balance"):
            if e.get(key) is None and f.get(key) is not None:
                e[key] = f.get(key)
        if f.get("basis") and not e.get("basis"):
            e["basis"] = str(f.get("basis"))
    return per


def pages_from_run(per_page: dict | list, flags: dict | None = None) -> dict[int, dict]:
    """مدخلاتُ `pages` من **تقرير تشغيل** (`to_xlsx.load`'s `per_page` + `flags`) — مسارُ الـCLI.

    **ولماذا دالّةٌ هنا لا في الأداة (R130 · مسارٌ واحد):** الواجهةُ ومسارُ سطر الأوامر يكتبان
    القاعدةَ نفسَها؛ فلا بدّ أن يُبنى مدخلُ الصفحات بالشكلِ نفسِه في الموضعين. الأرقامُ المطبوعة في
    تقرير التشغيل تحت `flags[pg]["printed"]` (قراءةُ التذييل)، والحكمُ تحت `per_page[pg]["footer"]`
    — فتُجمع هنا مرّةً واحدة، ويبقى `tools/ledger.py` توصيلًا لا بناءً ثانيًا.
    """
    entries = per_page.values() if isinstance(per_page, dict) else (per_page or [])
    flags = flags or {}
    out: dict[int, dict] = {}
    for e in entries:
        pg = int(e.get("page") or e.get("pg") or 0)
        if not pg:
            continue
        printed = (flags.get(pg) or {}).get("printed") or {}
        out[pg] = {
            "page_no": e.get("page_no"),
            "footer": str(e.get("footer") or e.get("verdict") or "unchecked"),
            "rows": int(e.get("rows") or e.get("rows_count") or 0),
            "usage": e.get("usage") or None,
            "debits": printed.get("debits"),
            "credits": printed.get("credits"),
            "balance": printed.get("balance"),
            "basis": e.get("basis") or "",
        }
    return out


def row_ids_for(conn: sqlite3.Connection, pairs) -> list[int]:
    """معرّفاتُ الصفوف من أزواج `(pg, row_no)` — يُترجَم بها «رقمُ الصفّ العامّ» إلى `qa_evidence`.

    **العِلّة:** الأدواتُ تُرجع أرقامَ الصفوف **العامة** (١..N على مستوى الكشف)، وجدولُ الدليل
    `qa_evidence` يشير إلى `rows_verified.id` (مفتاحٍ داخليّ). وكانت الترجمةُ غيرَ موجودة، فجدولُ
    الأسئلة لا يكتب دليلًا. والترجمةُ هنا بموضعٍ واحد لا في الشاشة.
    """
    out: list[int] = []
    for pg, row_no in pairs:
        row = conn.execute("SELECT id FROM rows_verified WHERE pg = ? AND row_no = ?",
                           (int(pg), int(row_no))).fetchone()
        if row is not None:
            out.append(int(row["id"]))
    return out


def delete_statement(path: Path) -> dict:
    """يمحو ملفَّ القاعدة وملفّاتَ WAL/SHM — **ويُعيد ما حُذف بعدده** (لا دعوى بلا عدّ).

    **والحذفُ لا يفتح القاعدةَ ولا يقرؤها:** الملفُّ قد يكون مفتوحًا في حافظةِ محادثةٍ أو في عمليةٍ
    أخرى؛ إغلاقُ الحافظة مسؤوليةُ من يملكها (`qa.clear_conversation`/`reset_memory`)، ثمّ يُنادى هذا
    فيجد الملفّات. وما لا وجودَ له لا يُعدّ.
    """
    path = Path(path)
    removed = []
    for suffix in ("", "-wal", "-shm"):
        f = Path(str(path) + suffix)
        if f.exists():
            f.unlink()
            removed.append(f.name)
    return {"removed": removed, "count": len(removed), "path": str(path)}
