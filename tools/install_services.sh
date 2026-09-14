#!/bin/sh
# install_services.sh — render the launchd templates with REAL paths and
# (re)load the services. The templates keep personal paths out of git; this
# script is the only place paths materialize, locally.
#
# Ops rule (learned the hard way): NEVER restart the app service while the
# owner may be mid-run — a restart kills his in-flight job. This script
# therefore leaves an ALREADY-RUNNING app service untouched; only missing
# services are bootstrapped, and the redirect/healthcheck rails get reloaded.
set -eu

REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs"
UID_="$(id -u)"
mkdir -p "$AGENTS" "$LOGS"

render() { # <tpl> <dst>
    sed -e "s|__REPO_DIR__|$REPO|g" -e "s|__HOME__|$HOME|g" "$1" > "$2"
}

for name in rajhi-rag rajhi-redirect rajhi-healthcheck; do
    tpl="$REPO/tools/launchd/com.jahfali.$name.plist.tpl"
    [ -f "$tpl" ] || continue
    dst="$AGENTS/com.jahfali.$name.plist"
    label="com.jahfali.$name"
    render "$tpl" "$dst"
    if launchctl list "$label" >/dev/null 2>&1; then
        if [ "$name" = "rajhi-rag" ]; then
            echo "[skip] $label يعمل الآن — تُرك كما هو (إعادة التشغيل تقتل مهمة جارية)."
        else
            launchctl bootout "gui/$UID_" "$dst" 2>/dev/null || true
            launchctl bootstrap "gui/$UID_" "$dst"
            echo "[reload] $label"
        fi
    else
        launchctl bootstrap "gui/$UID_" "$dst"
        echo "[load] $label"
    fi
done

echo "تم. للتحقق: launchctl list | grep jahfali"
