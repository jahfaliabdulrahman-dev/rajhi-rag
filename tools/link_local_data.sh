#!/bin/bash
# وصلُ البيانات المحلية إلى worktree — **عادةٌ تُعاد، لا إصلاحٌ لمرّة**.
#
# السبب (RCA مُقاس · 2026-09-21): المستودع لا يلتزم بيانات الكشوف الحقيقية
# (`data/local_sample/*` مُتجاهَلة عمداً)، و`git worktree` **لا يحمل المُتجاهَل**.
# فمن يراجع من worktree (المدقّق الخارجي) تُخطَّى عنده ثلاثةُ اختبارات بلا أن
# يدري: اثنان يحرسان المسحة الحقيقية (‎test_page_gate‎) وواحدٌ يحرس الكشف الرقمي
# (‎test_text_reader‎) — أي أنّ **تغطيةَ المراجعة دالّةٌ على البيئة لا على العدد**.
#
# القياس: نفس الشيفرة ونفس المفسّر ⇒ **قبل**: 3 تُخطّى · **بعد**: 0 تُخطّى.
#
#     bash tools/link_local_data.sh .claude/worktrees/<name>
set -euo pipefail

WT="${1:?استعمال: bash tools/link_local_data.sh <worktree-path>}"
# ⚠️ المستودعُ الأصلي من `git rev-parse --git-common-dir` **لا من مسار السكربت**:
# المدقّقُ في worktree يستعمل نسخةً من هذا السكربت **داخله**، فلو اشتُقّ المسار من
# نفسه لقال «لا مسحة محلية في المستودع الأصلي» وكذب — وهي **الحالة الوحيدة التي
# وُجد السكربت لها**، فيظنّ المدقّق أن البيانات غير موجودة فيمضي بتغطيةٍ ناقصة.
# (مأخذ المدقّق · الجولة ٢١ — قِيس: من داخل worktree كان يخرج بـ1.)
COMMON="$(git -C "$WT" rev-parse --git-common-dir 2>/dev/null || true)"
if [ -z "$COMMON" ]; then echo "لا مستودع في: $WT"; exit 1; fi
case "$COMMON" in /*) ;; *) COMMON="$WT/$COMMON" ;; esac
MAIN="$(cd "$(dirname "$COMMON")" && pwd)"
LO="$MAIN/data/local_sample"

[ -d "$WT" ] || { echo "لا مسار: $WT"; exit 1; }
[ -d "$LO/slice_629p" ] || { echo "لا مسحة محلية في المستودع الأصلي — لا شيء يُوصل"; exit 1; }

mkdir -p "$WT/data/local_sample"
for item in slice_629p digital; do
  if [ -e "$LO/$item" ]; then
    ln -sfn "$LO/$item" "$WT/data/local_sample/$item"
    echo "  وُصل: data/local_sample/$item"
  fi
done
echo "[link-local-data] تمّ — أعِد تشغيل المجموعة، وتوقّع **0 تُخطّى** (كانت 3)."
