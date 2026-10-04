# -*- coding: utf-8 -*-
"""مسبارُ أثر ذاكرة الحوار — **قابلٌ لإعادة الإنتاج** بنفس التصميم المانع للتلوّث.

**لماذا في المستودع لا في مخدع الجلسة:** البرهانُ في `docs/memory-effect-measurement.md` أُنتج من هنا؛
ونقلُه يجعل إعادةَ إنتاجه أمرًا واحدًا، فلا يبقى «برهانٌ شهد به مَن كتبه».

**التصميم (يمنع التلوّث):** الصفوفُ على **صفحتين** والسياقُ يعرض الاثنتين ⇒ سؤالُ المتابعة
«وما مجموع مبالغها؟» **مُبهمٌ فعلًا** بلا سجلّ. والفرقُ الوحيدُ بين الذراعين: `history` — **ولا `scope`
في أيّهما** (وكان `scope` في محاولتين سابقتين يحمل المرجعَ في الذراعين ⇒ أبطل المقابلة).

**ويستدعي نموذجًا حقيقيًّا ⇒ ذو كلفة.** فالسقفُ مُعلَن: دورتان لكلّ ذراع (٤ نداءاتٍ صغيرة).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from decimal import Decimal
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / "src")]

PAGE_ONE_TOTAL = "25.00"          # 10.00 + 15.00 — الجوابُ الصحيحُ للمقصود
ALL_FOUR_TOTAL = "70.00"          # 10+15+40+5 — جوابُ من لم يحلّ المرجع


def _row(pg: int, n: int, desc: str, side: str, amount: str, balance: str) -> dict:
    return {"page": pg, "row": n, "row_no": n, "description": desc, "balance": balance,
            "amount": amount, "debit": amount if side == "debit" else None,
            "credit": amount if side == "credit" else None, "kind": "txn", "side": side,
            "movement": Decimal(amount), "derived_movement": amount, "opening": False, "proven": True}


def _usage():
    from statement_qa.api_key import get_api_key
    for _ in range(3):
        try:
            req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                         headers={"Authorization": f"Bearer {get_api_key()}"})
            with urllib.request.urlopen(req, timeout=25) as h:
                return float(json.load(h)["data"]["usage"])
        except Exception:                                        # noqa: BLE001
            time.sleep(3)
    return None


def main() -> int:
    from statement_qa import qa

    rows = [_row(1, 1, "شراء", "debit", "10.00", "100.00"), _row(1, 2, "إيداع", "credit", "15.00", "115.00"),
            _row(2, 3, "رسوم", "debit", "40.00", "75.00"), _row(2, 4, "تحويل", "credit", "5.00", "80.00")]
    ctx = "صفحة ١: صفّان (شراء 10.00 · إيداع 15.00) — صفحة ٢: صفّان (رسوم 40.00 · تحويل 5.00)"
    prior = [("ما عدد الحركات في الصفحة ١؟", "في الصفحة ١ حركتان.")]
    question = "وما مجموع مبالغها؟"

    llm = qa.build_llm()
    before = _usage()
    with_mem = qa._answer_with_tools(llm, rows, ctx, question, history=prior)[0]
    without = qa._answer_with_tools(llm, rows, ctx, question)[0]
    time.sleep(8)
    after = _usage()

    resolved = "الصفحة ١" in with_mem and ("10.00" in with_mem and "15.00" in with_mem)
    confused = ALL_FOUR_TOTAL.replace(",", "") in without.replace(",", "")
    print("بذاكرة  :", with_mem.strip()[:200])
    print("بلا ذاكرة:", without.strip()[:200])
    print(f"الحكم: الذاكرةُ حلّت المرجع ⇒ {resolved} · وبلاها جمع الأربع ⇒ {confused}")
    print("الكلفة:", f"${after - before:.6f}" if (before and after and after >= before) else "**لم تُقس** (لا أُعلنها)")
    return 0 if (resolved and confused) else 1


if __name__ == "__main__":
    raise SystemExit(main())
