"""فحصُ الكشف قبل القراءة المدفوعة — ما يُطلب من العميل قبل أن يُدفع شيء.

## لماذا

طلبُ المالك: **حدٌّ أدنى من المتطلبات** قبل المعالجة. يُفحص الملفُّ المرفوع أولًا، ويُبلَّغ
العميلُ بالصفحات المتضرّرة ليعيد تصويرها — لا أن تُدفع كلفةُ قراءتها ثم تُعلَن «غيرَ مثبتة».
كانت البوابةُ موجودةً أداةً (`tools/page_gate.py`) ومواصفةً (`docs/SCAN_QUALITY_SPEC.md`)،
لكن التطبيقَ لم يستدعِها.

## الطبقاتُ الثلاث (بترتيب كلفتها)

1. **جودةُ الصورة** — `page_gate.check_page`، محلّي مجاني. `reject` بعيبٍ في صورةٍ فيها حبر
   (أفقية · اهتزاز · ميل) ⇒ **تُعاد تصويرًا**، والقراءةُ لا تبدأ ولا يُدفع شيء؛ إلا إن اختار
   العميلُ المتابعةَ مع استبعادها. **والورقةُ الفارغة تُترك وحدها ولا تمنع**: ملفُّ الـ٦٢٩ صفحة
   فيه ثلاثُ أوراقٍ بيضاء (١٧٢ · ٤٨٤ · ٦٠٢، حبرُها ٠٫٠) — منعُ الرفع بسببها كان سيوقف كشفَ
   المالك نفسه، ولا شيءَ فيها يُعاد تصويره. `warn` ⇒ تُقرأ ويُسمّى عيبُها.
2. **شكلُ الصفحة** — `row_bands.analyze_page`، محلّي مجاني. صفحةٌ لا تطابق قالبَ الكشف
   الممسوح (صورةُ كاميرا، قصٌّ مختلف) **تُسمّى ولا تُمنع**: القراءةُ لا تعتمد على القالب بعد.
3. **ترتيبُ الأوراق** — `ordering.footer_order` على التذييلات (قصاصةٌ صغيرةٌ لكلّ صفحة). تُقرأ
   قبل القراءة الكاملة **وتُستعمَل فيها** فلا تُدفع مرّتين، والصفحاتُ تُعالَج بترتيبها الحقيقي.

## ما لا يكشفه هذا الفحص

**الورقةُ الغائبة**: التذييلُ التراكميُّ يبقى متّسقًا عبرها، فلا تُرى قبل القراءة. تُكشف أثناءها
(قفزةُ الرقم المطبوع، ودلتا التذييل مقابل حركات الصفحة) وتُسمّى في الملخّص.
"""
from __future__ import annotations

from dataclasses import dataclass, field

REJECT, WARN = "reject", "warn"
BLANK = "blank"                # رمزُ السبب في page_gate (R_BLANK)


@dataclass
class Intake:
    gate: dict[int, dict] = field(default_factory=dict)   # موضع ⇒ حكمُ page_gate
    kinds: dict[int, str] = field(default_factory=dict)   # موضع ⇒ نوعُ الصفحة (row_bands)

    def _with(self, verdict: str) -> list[int]:
        return sorted(p for p, g in self.gate.items() if g.get("verdict") == verdict)

    def rejected(self) -> list[int]:
        return self._with(REJECT)

    def blank(self) -> list[int]:
        """مرفوضةٌ لأنها فارغة — تُترك بلا قراءة، ولا تمنع."""
        return [p for p in self.rejected() if BLANK in (self.gate[p].get("reasons") or [])]

    def reshoot(self) -> list[int]:
        """مرفوضةٌ بعيبٍ في صورةٍ فيها حبر — هذه ما يُعاد تصويره."""
        blank = set(self.blank())
        return [p for p in self.rejected() if p not in blank]

    def warned(self) -> list[int]:
        return self._with(WARN)

    def unmatched(self) -> list[int]:
        return sorted(p for p, k in self.kinds.items() if k == "unknown")

    def reason(self, pos: int) -> str:
        ar = self.gate.get(pos, {}).get("reasons_ar") or []
        return ar[0] if ar else "غير محدّد"


def inspect_locally(images: list[str], gate_fn, kind_fn) -> Intake:
    """الطبقتان المجانيتان على كلّ صفحة. `images[i]` هي الموضع i+1.

    عطلٌ في فحص صفحةٍ لا يُسقط التشغيل ولا يُخفى: تُعلَّم «تحذيرًا» بسببٍ مكتوب — فلا تُرفض
    صفحةٌ سليمة بعطلٍ في الأداة، ولا تمرّ صامتة.
    """
    intake = Intake()
    for pos, img in enumerate(images, start=1):
        try:
            intake.gate[pos] = gate_fn(img)
        except Exception as e:                                  # noqa: BLE001
            intake.gate[pos] = {"verdict": WARN,
                                "reasons_ar": [f"تعذّر فحصُ جودتها ({type(e).__name__})"]}
        try:
            intake.kinds[pos] = kind_fn(img)
        except Exception:                                       # noqa: BLE001
            intake.kinds[pos] = "unknown"
    return intake


def plan(intake: Intake, skip_rejected: bool) -> dict:
    """{blocked, process, skipped, blank}: ما يُقرأ، وهل تبدأ القراءةُ أصلًا."""
    reshoot, blank = intake.reshoot(), intake.blank()
    process = [p for p in sorted(intake.gate) if p not in reshoot and p not in blank]
    # الاستبعادُ حين لا يبقى شيء ليس متابعة: لا تبدأ قراءةٌ بلا صفحات.
    if (reshoot and not skip_rejected) or not process:
        return {"blocked": True, "process": [], "skipped": reshoot, "blank": blank}
    return {"blocked": False, "process": process, "skipped": reshoot, "blank": blank}


def _pages_with_reasons(intake: Intake, pages: list[int], cap: int = 8) -> str:
    items = [f"ص{p}: {intake.reason(p)}" for p in pages[:cap]]
    more = f" … و{len(pages) - cap} غيرها" if len(pages) > cap else ""
    return "؛ ".join(items) + more


def blocked_message_ar(intake: Intake) -> str:
    """ما يراه العميلُ حين لا تبدأ القراءة — ولماذا، وما يفعله."""
    rej = intake.reshoot()
    if not rej:
        return (f"⛔ **لم تبدأ القراءة ولم يُدفع شيء.** لا صفحةَ فيها ما يُقرأ — "
                f"{_pages_with_reasons(intake, intake.blank())}.")
    return (f"⛔ **لم تبدأ القراءة ولم يُدفع شيء.** {len(rej)} من {len(intake.gate)} "
            f"صفحة تحتاج إعادة تصوير — {_pages_with_reasons(intake, rej)}. "
            f"أعد تصويرها وارفع الملف من جديد، أو فعّل «متابعة مع استبعاد الصفحات "
            f"المرفوضة» لتُقرأ البقيةُ وتُسمّى المستبعدة في الملخّص.")


def summary_ar(intake: Intake, skipped: list[int]) -> str:
    """سطرُ الملخّص: ما وجده الفحصُ قبل القراءة، بلغة العميل."""
    n = len(intake.gate)
    seg = (f"فحصُ ما قبل القراءة: {n} صفحة — مقبولة "
           f"{n - len(intake.warned()) - len(intake.rejected())}")
    if intake.warned():
        seg += f" · بتحذير {len(intake.warned())} ({_pages_with_reasons(intake, intake.warned(), 4)})"
    if skipped:
        seg += f" · ⚠ مستبعدة بلا قراءة {len(skipped)} ({_pages_with_reasons(intake, skipped, 4)})"
    if intake.blank():
        seg += (f" · أوراقٌ فارغة تُركت بلا قراءة: "
                f"{'، '.join(f'ص{p}' for p in intake.blank()[:8])}")
    if intake.unmatched():
        pages = "، ".join(f"ص{p}" for p in intake.unmatched()[:8])
        seg += f" · شكلٌ لا يطابق قالبَ الكشف الممسوح: {pages}"
    return seg
