"""**سجلُّ اللاحتميّةِ مُتتبَّع، وميزانيّتُه تُحمّر البوّابة** (شرطُ مراجعة ٥٨ · تبنٍّ بشرط).

**لماذا وُجد:** سياسةُ اللاحتميّة (قراءةٌ ثانيةٌ **نظيفةٌ غيرُ أنحفَ ومطابقةُ الفوتر** تُبرّئ عطباً ظهر في
قراءةٍ واحدة) **مُعلَنةٌ ومقيسة** في `tools/qa_gate.py`، لكنّ وسمَ `[flaky_read]` كان **يُطبع ولا يُعدّ**
⇒ عطبٌ متذبذبٌ يصير عاديًّا بلا أن يسأل أحد — وهو درسُ R13: الأحمرُ صار عاديًّا يومين ونصفًا حتى صارت
البوّابةُ لا تعني شيئًا. فالشرطُ: **سجلٌّ مُتتبَّعٌ يُضاف إليه كلُّ وسم** + **ميزانيّةٌ مُعلَنة** تحمرّ إن
تجاوزتها اللاحتميّةُ في آخر N تشغيل. وهذا الملفُّ هو البوّابةُ (والسجلُّ `handoff/FLAKY_READS.md`).

**الحدودُ المُعلَنة (ما لم يُثبت):**
1. النافذةُ تُقرأ من **ملفّات أدلّةٍ محفوظة** (`handoff/sulaiman/*gate-evidence-*.txt`) ⇒ تشغيلٌ لم تُحفظ
   أدلّتُه **خارج النافذة** (فالنافذةُ «آخر N تشغيلٍ محفوظ»، لا «آخر N تشغيل»).
2. وغيابُ الوسم من ملفّ الدليل = نظافة **فقط إن كان الملفُّ يحمل المخرجَ كاملًا** (وهو كذلك: `tee` لمخرج
   `qa_gate --full` في سطرٍ واحد) — ولو كان مقتطعًا لصار الغيابُ صمتًا لا دليلًا.
3. **والتسجيلُ بيد المنفّذ لا بيد الأداة:** البوّابةُ لا تكتب في الشجرة المتتبَّعة (تشغيلٌ نظيفٌ لا يجوز أن
   يوسّخ المستودع) ⇒ فالثابتُ المعلَن هو ما يمنع الإضافةَ الصامتة، لا الكتابةُ الآلية.
4. **وأثرُ ما قبل السجلّ لا يُحسب** (فتحُ حسابٍ على الماضي يُغرق الراتشت بأثرٍ لا يُصلَح) — يُذكر في متن
   السجلّ للتاريخ فقط.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from qa_gate import FLAKY_MARK  # noqa: E402  ← **مصدرٌ واحد**: المنتجُ يبنيه والحارسُ يستورده (مراجعة ٥٩)

LEDGER = ROOT / "handoff" / "FLAKY_READS.md"
GATES = ROOT / "docs" / "GATES.md"
EVIDENCE_DIR = ROOT / "handoff" / "sulaiman"
EVIDENCE_GLOB = "*gate-evidence-*.txt"
#: **الميزانيّةُ المُعلَنة** (تُقاس بها البوّابةُ، ويوازيها نصُّ السجلّ في اختبارٍ أدناه).
WINDOW = 5
MAX_FLAKY_RUNS_IN_WINDOW = 1
#: **عددُ قيود السجلّ المُعلَن** — إضافةُ قيدٍ بلا رفعِ هذا الثابت في الالتزام نفسه ⇒ حمراء (راتشت).
DECLARED_LEDGER_ENTRIES = 0
#: صفُّ قيدٍ حقيقيّ في جدول السجلّ: يبدأ بالرقم ثمّ التاريخ (وصفُ «لا قيدَ» ليس قيدًا).
ENTRY_RE = r"^\|\s*\d+\s*\|"
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _number_after(text: str, anchor: str) -> int | None:
    """أوّلُ عددٍ يلي المرساةَ في النصّ (والأرقامُ العربيةُ تُوحَّد) — أو `None` إن غابت المرساة."""
    m = re.search(anchor + r"[^\d]{0,24}?(\d+)", text.translate(ARABIC_DIGITS))
    return int(m.group(1)) if m else None


def declared_pairs(ledger: str, gates: str) -> dict[str, int | None]:
    """**أرقامُ النافذة والميزانيّة كما تنطقها الوثيقتان** — لا كما في الثوابت (فالمقابلةُ تُكشِف التقادم).

    كان الفحصُ `str(n) in text` ⇒ «حضورُ نصّ» لا مساواة: `5` يمرّ في `15`، و`1` يمرّ في `10` (قاسه
    ثلاثةُ مقاعد في مراجعة ٥٩: S-4 · F5 · P2-3). الآن يُستخرَج **العددُ نفسُه** من الجملة المُعلَنة في
    السجلّ، ومن صفّ السجلّ في `docs/GATES.md` (بالعربية أو بالهندية — تُوحَّد).
    """
    row = next((ln for ln in gates.splitlines() if ln.startswith("| 14 |")), "")
    return {
        "ledger_budget": _number_after(ledger, r"أقصى"),
        "ledger_window": _number_after(ledger, r"نافذة\s*\*{0,2}\s*آخر"),
        "gates_budget": _number_after(row, r"المُلوَّثة"),
        "gates_window": _number_after(row, r"نافذة\s*\*{0,2}\s*آخر"),
    }


def ledger_entries(text: str) -> list[str]:
    """صفوفُ القيود الحقيقيّة في السجلّ (بلا صفّ العنونة ولا صفّ «لا قيدَ حتى الآن»)."""
    out: list[str] = []
    for ln in text.splitlines():
        row = ln.strip()
        if not row.startswith("|"):
            continue
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        out.append(row)
    return out


def evidence_runs(root: Path = ROOT) -> list[tuple[str, str]]:
    """(اسمُ ملفّ الدليل، نصُّه) لكلّ تشغيلٍ محفوظ — مرتَّبًا بالاسم (والاسمُ يبدأ بالتاريخ ⇒ ترتيبٌ زمنيّ)."""
    d = root / "handoff" / "sulaiman"
    files = sorted(p for p in d.glob(EVIDENCE_GLOB) if p.is_file())
    return [(p.name, p.read_text(encoding="utf-8", errors="replace")) for p in files]


def over_budget(runs: list[tuple[str, str]], window: int = WINDOW,
                budget: int = MAX_FLAKY_RUNS_IN_WINDOW) -> list[str]:
    """التشغيلاتُ المُلوَّثة داخل **آخر** `window` تشغيلٍ محفوظ — إن تجاوزت `budget` فالقائمةُ غيرُ فارغة.

    دالّةٌ خالصةٌ ⇒ تُقاس بسمٍّ مصنوع (لا بالشجرة الحيّة وحدها).
    """
    tail = runs[-window:] if window > 0 else runs
    dirty = [name for name, body in tail if FLAKY_MARK in body]
    if len(dirty) <= budget:
        return []
    return dirty


def test_a_flaky_run_must_be_entered_in_the_ledger():
    """**كلُّ وسمٍ في تشغيلٍ محفوظ له قيدٌ في السجلّ** — والعدُّ يُقابَل بثابتٍ مُعلَن (لا إضافةَ صامتة)."""
    runs = evidence_runs()
    assert runs, ("لا ملفَّ دليلِ تشغيلٍ محفوظ ⇒ لا نافذةَ تُقاس ⇒ فشلٌ مُغلَق (احفظ مخرج qa_gate --full "
                  "في handoff/sulaiman/*gate-evidence-*.txt)")
    assert LEDGER.exists(), "لا سجلَّ لاحتميّة ⇒ وسمٌ يُطبع ولا يُقيَّد"
    entries = ledger_entries(LEDGER.read_text(encoding="utf-8"))
    dirty = [name for name, body in runs if FLAKY_MARK in body]
    for name in dirty:
        assert any(name in e for e in entries), (
            f"تشغيلٌ مُلوَّثٌ «{name}» بلا قيدٍ في {LEDGER.name} ⇒ سجّلْه (بالهويّة والقراءةِ الثانية)")
    assert len(entries) == DECLARED_LEDGER_ENTRIES, (
        f"قيودُ السجلّ تغيّرت: المُقاس {len(entries)} والمُعلَن {DECLARED_LEDGER_ENTRIES} ⇒ يُحدَّث الثابتُ "
        f"`DECLARED_LEDGER_ENTRIES` في الالتزام نفسه (وإلّا صارت الإضافةُ صامتة)")


def test_the_declared_budget_is_not_exceeded_in_the_window():
    """**والميزانيّةُ تحمرّ**: تجاوزُ {MAX_FLAKY_RUNS_IN_WINDOW} تشغيلٍ مُلوَّثٍ في نافذة {WINDOW} ⇒ أحمر مُسمّى."""
    runs = evidence_runs()
    bad = over_budget(runs)
    assert not bad, (
        f"اللاحتميّةُ تجاوزت الميزانيّةَ المُعلَنة ({len(bad)} تشغيلٍ مُلوَّث في آخر {WINDOW}): {bad} ⇒ "
        f"لا تصير «المتذبذب» عاديًّا: أصلِح العطبَ الجذريّ أو ارفعِ الميزانيّةَ **مُعلَنةً** في الالتزام نفسه")


def test_the_budget_actually_bites_on_a_synthetic_window():
    """**سمٌّ مصنوع** (بلا تسجيلٍ صار ادّعاءً): نافذةٌ فيها تشغيلان مُلوَّثان وثلاثةُ نظيفة ⇒ تُكشَف."""
    clean = ("r1.txt", "5/5 passed"), ("r2.txt", "5/5 passed"), ("r3.txt", "5/5 passed")
    assert over_budget([*clean, ("r4.txt", FLAKY_MARK + " page 3 row 12"), ("r5.txt", "5/5")]) == []
    two_dirty = [*clean, ("r4.txt", FLAKY_MARK + " x"), ("r5.txt", FLAKY_MARK + " y")]
    assert over_budget(two_dirty) == ["r4.txt", "r5.txt"], "تجاوزُ الميزانيّة لم يُكتشَف"
    # **والنافذةُ تُقصّ**: تشغيلٌ قذرٌ **قديمٌ** خارج النافذة لا يُحمّر اليوم (وإلّا صار التاريخُ سجناً)
    old = [("r0.txt", FLAKY_MARK + " قديم")] + [("r%d.txt" % i, "5/5") for i in range(1, 6)]
    assert over_budget(old, window=5, budget=1) == [], "قيدٌ قديمٌ خارج النافذة حُمِّر خطأً"


def test_the_ledger_prose_matches_the_constants_it_declares():
    """**الوثيقةُ تُقابَل بمصدرها بالرموز** (لا «حضورُ نصّ»): أرقامُ السجلّ **وصفُّ `GATES.md`** تساوي الثوابت.

    والسمُّ في الذاكرة: نصٌّ يقول «أقصى 3 … نافذة آخر 15» لا يمرّ — وكان `in` يمرّره.
    """
    text = LEDGER.read_text(encoding="utf-8")
    gates = GATES.read_text(encoding="utf-8")
    assert FLAKY_MARK in text, "السجلُّ لا يسمّي الوسمَ الذي يُقيَّد"
    pairs = declared_pairs(text, gates)
    for where, b_key, w_key in (("السجلّ", "ledger_budget", "ledger_window"),
                               ("صفُّ GATES.md", "gates_budget", "gates_window")):
        assert pairs[b_key] == MAX_FLAKY_RUNS_IN_WINDOW, (
            f"{where}: الميزانيّةُ المنطوقة {pairs[b_key]} تخالف الثابت {MAX_FLAKY_RUNS_IN_WINDOW} "
            f"(والمقيسُ: {pairs}) ⇒ نصٌّ مُتقادم")
        assert pairs[w_key] == WINDOW, (
            f"{where}: النافذةُ المنطوقة {pairs[w_key]} تخالف الثابت {WINDOW} (والمقيسُ: {pairs})")
    # **والسمُّ**: ميزانيّةٌ ونافذةٌ مُوسَّعتان في نصّ السجلّ تُكشَفان (وكان `str(n) in text` يمرّرهما).
    #  ويُبنى **من المقيس** لا من حرف النثر (فلا يتقادم مع إعادة صياغة السجلّ): نُبدّل العددَين بـ3 و15.
    fake = re.sub(r"(أقصى\s*\*{0,2})\d+", r"\g<1>3", text, count=1)
    fake = re.sub(r"(نافذة\s*\*{0,2}آخر\s*\*{0,2})\d+", r"\g<1>15", fake, count=1)
    assert fake != text, "السمُّ لم يجد جملةَ السجلّ ⇒ الفحصُ ادّعاءٌ لا قياس"
    fake_pairs = declared_pairs(fake, gates)
    assert (fake_pairs["ledger_budget"], fake_pairs["ledger_window"]) != (MAX_FLAKY_RUNS_IN_WINDOW, WINDOW), (
        "نصٌّ وسّع الميزانيّةَ والنافذةَ مرّ صامتاً — وهو الصنفُ الذي وُجد السجلُّ لأجله")
    assert "DECLARED_LEDGER_ENTRIES" in text, "السجلُّ لا يُعلن ثابتَ عدد القيود ⇒ إضافةٌ صامتة ممكنة"
    # **وحدُّ ما قبل السجلّ مُعلَن**: لا يُحسب أثرُ الماضي
    assert "قبل" in text and "لا يُقيَّد" in text, "السجلُّ لا يُعلن حدَّه الزمنيّ (أثرُ ما قبل السياسة)"
