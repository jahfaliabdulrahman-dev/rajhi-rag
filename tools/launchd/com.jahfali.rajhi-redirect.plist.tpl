<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<!-- TEMPLATE — rendered with real paths by tools/install_services.sh
     (__REPO_DIR__ / __HOME__ placeholders keep personal paths out of git). -->
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jahfali.rajhi-redirect</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>__REPO_DIR__/tools/redirect_7867.py</string>
        <string>7867</string>
        <string>http://127.0.0.1:7860</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>__HOME__/Library/Logs/rajhi-redirect.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/Library/Logs/rajhi-redirect.log</string>
</dict>
</plist>
