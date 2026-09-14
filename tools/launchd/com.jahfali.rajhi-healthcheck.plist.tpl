<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- TEMPLATE — rendered with real paths by tools/install_services.sh
     (__REPO_DIR__ / __HOME__ placeholders keep personal paths out of git). -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jahfali.rajhi-healthcheck</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>__REPO_DIR__/tools/health_monitor.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>600</integer>
    <key>StandardOutPath</key>
    <string>__HOME__/Library/Logs/rajhi-health.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/Library/Logs/rajhi-health.log</string>
</dict>
</plist>
