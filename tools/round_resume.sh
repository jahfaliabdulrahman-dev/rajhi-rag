#!/bin/bash
# استئناف جولة قراءة طويلة تحت **مشرف دائم** (launchd) لا تحت جلسة الوكيل.
#
# لماذا هذا الملف
# ---------------
# عمليات terminal(background) في هرمز *مرتبطة بالجلسة*: عند دوران الجلسة تُقتل
# جماعياً بـSIGTERM. جولة 629 صفحة توقفت عند الصفحة 284 بهذا السبب بالضبط
# (`exit_code -15` · `termination_source: agent_close`) وكلفتها المدفوعة معلّقة.
# المشرف الدائم يستأنف من الكاش: كل صفحة قُرئت لا تُقرأ ثانية ولا يُدفع ثمنها،
# و`KeepAlive` يرفعها إن سقطت. وحين تكتمل الجولة يخرج الأمر بنجاح فلا تُرفع.
#
#   bash tools/round_resume.sh --install     # يُسجّل الخدمة ويبدأ الآن
#   bash tools/round_resume.sh --status      # نبض + حالة الجولة
#   bash tools/round_resume.sh --uninstall   # يوقف الخدمة ويرفع تسجيلها
#
# ملاحظة أمان: مفتاح OpenRouter يُقرأ من `.env` في جذر المشروع (ملف)، لا من
# البيئة — فلا سرّ في ملف الخدمة. وPATH يُكتب صراحةً لأن launchd لا يرث بيئة
# الصدفة (أدوات Homebrew تختفي من المسار عند غيابه).
set -euo pipefail

PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.jahfali.rajhi-round-v2"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOGDIR="$HOME/Library/Logs"
LOG="$LOGDIR/rajhi-round-v2.log"
SRC="$PROJ/data/local_sample/slice_629p/slice_629p.pdf"
OUT="$PROJ/data/local_sample/slice_629p_v2"
PY="$PROJ/.venv/bin/python"
MAX_COST="${MAX_COST:-12}"

write_plist() {
  mkdir -p "$HOME/Library/LaunchAgents" "$LOGDIR"
  cat > "$PLIST" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$PROJ/tools/round_resume.sh</string>
    <string>--run</string>
  </array>
  <key>WorkingDirectory</key><string>$PROJ</string>
  <key>RunAtLoad</key><true/>
  <!-- يُرفع من جديد عند السقوط، ولا يُرفع بعد خروج ناجح (جولة مكتملة) -->
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
</dict>
</plist>
XML
  chmod 600 "$PLIST"
}

case "${1:---status}" in
  --install)
    pkill -f "scale_slice.py.*slice_629p_v2" 2>/dev/null || true
    write_plist
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST"
    sleep 4
    launchctl list | grep "$LABEL" || { echo "لم تُسجَّل الخدمة"; exit 1; }
    echo "سُجّلت وبدأت · السجل: $LOG"
    ;;
  --uninstall)
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "أُوقفت وأُزيلت."
    ;;
  --status)
    launchctl list | grep "$LABEL" || echo "(الخدمة غير مسجّلة)"
    echo "── الجولة ──"
    "$PY" "$PROJ/tools/round_status.py" "$OUT"
    echo "── آخر ثلاثة أسطر من السجل ──"
    tail -3 "$LOG" 2>/dev/null || echo "(لا سجل)"
    ;;
  --run)
    cd "$PROJ"
    exec caffeinate -i "$PY" tools/scale_slice.py \
      --source "$SRC" --first 1 --count 629 --out "$OUT" \
      --max-cost "$MAX_COST" --page-gate warn --retry-errors
    ;;
  *)
    echo "استعمال: $0 [--install|--status|--uninstall|--run]" >&2
    exit 2
    ;;
esac
