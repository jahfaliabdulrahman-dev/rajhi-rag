<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- TEMPLATE — rendered with real paths by tools/install_services.sh
     (__REPO_DIR__ / __HOME__ placeholders keep personal paths out of git). -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jahfali.rajhi-rag</string>
    <key>ProgramArguments</key>
    <array>
        <string>__REPO_DIR__/.venv/bin/python</string>
        <string>__REPO_DIR__/app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>__REPO_DIR__</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>StandardOutPath</key>
    <string>__HOME__/Library/Logs/rajhi-rag.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/Library/Logs/rajhi-rag.log</string>
</dict>
</plist>
