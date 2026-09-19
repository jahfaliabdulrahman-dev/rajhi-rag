"""أرقام الصفحات المطبوعة: مقروءةً حيث قُرئت، ومشتقّةً بالحساب حيث لا تُقرأ.

القاعدة التي تجعل الاشتقاق مشروعاً: الترقيم المطبوع **يتسلسل** — يزيد واحداً مع كل
صفحة ملف، ويقفز فقط حيث تغيب ورقة من المسح. فمن مرساةٍ مقروءة، رقم أي صفحة في
مقطعها = المرساة + فرق الترتيب. ولا يُسمّى المشتقُّ مقروءاً: كل رقم يحمل مصدره،
ويُصدَّر بلفظه — وهذا ما يجعل إحالة العميل إلى الورق أمانةً لا تخميناً.
"""
from __future__ import annotations


def build_map(anchors: dict[int, int], last_page: int,
              gap_after: set[int] | None = None) -> dict[int, dict]:
    """مرساة (صفحة ملف ⇒ رقم مطبوع) ⇒ خريطة كاملة بأرقام ومصادر.

    ``gap_after``: صفحات ملف يليها نقص في الترقيم (ورقة غائبة) — تُقطع عندها
    المقاطع، فلا يُمدّ اشتقاقٌ عبر فجوة.

    يُرجع {صفحة: {"printed": int, "source": "read"|"derived"|"extrapolated"}}.
    """
    gaps = gap_after or set()
    if not anchors:
        return {}
    ordered = sorted(anchors)
    segments: list[dict] = []
    for page in ordered:
        offset = anchors[page] - page
        current = segments[-1] if segments else None
        if current is None or current["offset"] != offset or \
                any(g in range(current["last"], page) for g in gaps):
            segments.append({"offset": offset, "first": page, "last": page})
        else:
            current["last"] = page

    out: dict[int, dict] = {}
    for seg in segments:
        for page in range(seg["first"], seg["last"] + 1):
            src = "read" if page in anchors else "derived"
            out[page] = {"printed": page + seg["offset"], "source": src}
    # امتداد طرفي: المقطع الأول قبل أول مرساة، والأخير بعد آخر مرساة — موسومٌ أنه امتداد
    first, last = segments[0], segments[-1]
    for page in range(1, first["first"]):
        out[page] = {"printed": page + first["offset"], "source": "extrapolated"}
    for page in range(last["last"] + 1, last_page + 1):
        out[page] = {"printed": page + last["offset"], "source": "extrapolated"}
    return out


def conflicts(map_: dict[int, dict], anchors: dict[int, int]) -> list[tuple[int, int, int]]:
    """(صفحة، مقروء، مشتق) لكل مرساة تخالف اشتقاقها ⇒ كاشف عطل في خريطة الفجوات.

    لا يُصلح شيئاً: يُعلن. لأن اختلاف رقمين مقروءين في مقطع واحد يعني أن فجوةً
    لم نكتشفها أو أن قراءةً أخطأت — وكلاهما لا يُمرّ صامتاً.
    """
    out = []
    for page, printed in sorted(anchors.items()):
        derived = (map_.get(page) or {}).get("printed")
        if derived is not None and derived != printed:
            out.append((page, printed, derived))
    return out
