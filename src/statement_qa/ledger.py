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

import re
import sqlite3
from pathlib import Path

#: مسارُ الدفتر: **مُهمَلٌ ولا يُتتبَّع أبدًا** (قرارُ المالك) — **والدعوى صارت واقعةً يُقاس بها**
#: (مقعدُ المعايير F1 · مُثبت): أُضيف `**/data/ledgers/` إلى `.gitignore`، ويقيس ذلك ضابطٌ في
#: `tests/test_ledger.py` بـ`git check-ignore` (لا بالنصّ)، **لأنّه كان مكتوبًا هنا ومخالفًا للواقع**:
#: `git status` كان يُظهر `?? data/ledgers/` و`git add` كان يقبله.
#: **وحراستُه بالامتداد مقيسةٌ لا مُدّعاة** (F2): `tools/publish_guard.py` يحجب `.sqlite` بـ
#: `OPAQUE_EXTS` (قِيس: `publish_guard --tree` على ملفٍّ مُتتبَّعٍ ⇒ `BLOCK opaque_binary`)،
#: **وحارسُ المبالغ لا يحجب `.sqlite`** (قِيس: `undeclared_binaries()` ⇒ `[]`) — فالتغطيةُ حارسٌ
#: واحدٌ + الإهمال، وهذا ما يُقال لا «حارسان».
LEDGER_SUBDIR = ("data", "ledgers")

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
CREATE TABLE IF NOT EXISTS pages (
    pg            INTEGER PRIMARY KEY,
    printed_page  TEXT,
    verdict       TEXT NOT NULL CHECK (verdict IN
                      ('ok','gap','mismatch','absent','unchecked','other')),
    rows_count    INTEGER NOT NULL DEFAULT 0,
    cost_usd      TEXT,                       -- كلفةُ الصفحة: TEXT لا REAL (المالُ لا يُطبَع عائمًا)
    CHECK (cost_usd IS NULL OR typeof(cost_usd) = 'text')
);

-- الجدولُ المُتحقَّق منه: أعمدةُ الرندر **الاثنان والعشرون** نفسُها (فيُقابَل صفًّا بصفّ).
CREATE TABLE IF NOT EXISTS rows_verified (
    id               INTEGER PRIMARY KEY,
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


def open_ledger(path: Path, *, create: bool = True) -> sqlite3.Connection:
    """يفتح الدفترَ أو يُنشئه، **ويُسمّي العطب** بدل أن يرفع خطأً خامًّا.

    والتفريقُ مقصود: `missing` (لا ملفّ) و`corrupt` (ملفٌّ ليس قاعدةً أو بنيتُه مكسورة) —
    لأنّ علاجَهما مختلف: الأوّل يعيد المستخدمُ التشغيلَ، والثاني يعني ملفًّا أُفسِد.
    """
    path = Path(path)
    if not path.exists():
        if not create:
            raise LedgerUnavailable(MISSING, path)
        path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        # **ودالّةُ التطبيع تُسجَّل قبل المخطَّط**: العمودُ المُشتقُّ `desc_norm` يعتمد عليها،
        # و`deterministic=True` شرطٌ في أعمدة SQLite المُولَّدة (وبلا الشرط يرفضها المحرّك).
        conn.create_function("norm_ar", 1, lambda s: norm_ar(s), deterministic=True)
        conn.executescript(SCHEMA)
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
    """يفتح الدفترَ **للقراءة ولا يُنشئه**: قاعدةٌ غائبةٌ تُعلَن `missing` لا تُخترع فارغة.

    **العِلّة (مقعدا المواصفة والبنية):** كان `open_ledger` يُنشئ ملفًّا فارغًا افتراضًا ⇒ فقارئٌ
    يسأل عن كشفٍ لم يُقرأ بعد يحصل على «قاعدة» فارغةٍ بدل الخطأ المسمّى الذي تنصّ عليه المواصفة.
    """
    return open_ledger(Path(path), create=False)


def _text(value) -> str | None:
    """**كلُّ مبلغٍ نصٌّ** — يمرّ من هنا وحدَه، فلا يُنسى قيدُ `TEXT` في موضع."""
    return None if value is None else str(value)


def ingest(conn: sqlite3.Connection, rows: list[dict], pages: dict[int, dict],
           report: dict | None = None) -> dict:
    """يكتب الجدولَ المُتحقَّق منه وأحكامَ الصفحات في معاملةٍ واحدة.

    **والمصدرُ هو مخرَجُ `tools/to_xlsx.load` نفسُه** لا نسخةً ثانيةً منه: نسخةٌ ثانيةٌ من بناء
    الصفوف تعني حكمين يُفترقان صامتين، والبوّابةُ («يُقرأ صفًّا بصفّ») تُقابِل مصدرًا بمصدر.
    """
    written = 0
    with conn:
        for pg, entry in sorted(pages.items()):
            verdict = (entry.get("footer") or "other")
            if verdict not in {"ok", "gap", "mismatch", "absent", "unchecked"}:
                verdict = "other"
            cost = (entry.get("usage") or {}).get("cost") if isinstance(entry.get("usage"), dict) else None
            conn.execute(
                "INSERT INTO pages(pg, printed_page, verdict, rows_count, cost_usd) "
                "VALUES(?,?,?,?,?) ON CONFLICT(pg) DO UPDATE SET "
                "printed_page=excluded.printed_page, verdict=excluded.verdict, "
                "rows_count=excluded.rows_count, cost_usd=excluded.cost_usd",
                (pg, str(entry.get("page_no")) if entry.get("page_no") else None, verdict,
                 int(entry.get("rows") or 0), _text(cost)),
            )
        sets = ", ".join(f"{c}=excluded.{c}" for c in INS_COLUMNS if c not in ("pg", "row_no"))
        for r in rows:
            # **`ON CONFLICT … DO UPDATE` لا `INSERT OR REPLACE` (مقعدا المواصفة والبنية · مُثبت):**
            # `OR REPLACE` يحذف الصفَّ ثمّ يُدرجه ⇒ يتبدّل `id`، و`ON DELETE CASCADE` يمسح
            # `qa_evidence` ⇒ **فقدانُ دليلِ الأسئلة صامتًا** عند إعادة قراءة كشفٍ سُئل عنه.
            # والتحديثُ يُبقي المعرّفَ فيبقى الدليل.
            conn.execute(
                f"INSERT INTO rows_verified({', '.join(INS_COLUMNS)}) "
                f"VALUES({', '.join('?' for _ in INS_COLUMNS)}) "
                f"ON CONFLICT(pg, row_no) DO UPDATE SET {sets}",
                _row_values(r),
            )
            written += 1
    return {"pages": len(pages), "rows": written}


def read_rows(conn: sqlite3.Connection, pg: int | None = None) -> list[dict]:
    """يُعيد الصفوفَ بأسماء الرندر نفسها — **لتُقابَل صفًّا بصفّ** (البوّابةُ الحاسمة)."""
    sql = f"SELECT {', '.join(COLUMNS)} FROM rows_verified"
    args: tuple = ()
    if pg is not None:
        sql += " WHERE pg = ?"
        args = (pg,)
    sql += " ORDER BY pg, row_no"
    return [dict(row) for row in conn.execute(sql, args)]


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

