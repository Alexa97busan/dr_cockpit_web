#!/bin/bash
# 한 번만 실행하면 됩니다. 10분마다 인터넷을 확인하고, 자료가 바뀌었을 때만 DB를 갱신합니다.
# 항상 홈의 dr_cockpit 폴더만 기준으로 쓴다 (바탕화면 등 다른 위치의 복사본을 기준으로 잡지 않도록)
BASE="$HOME/dr_cockpit"
if [ ! -f "$BASE/auto_build.sh" ]; then
  echo "~/dr_cockpit 폴더에서 auto_build.sh를 찾지 못했습니다. 폴더를 먼저 옮겨 주세요."
  read -r -p "Enter를 누르면 창이 닫힙니다..."
  exit 1
fi
chmod +x "$BASE/auto_build.sh"
PLIST="$HOME/Library/LaunchAgents/com.drcockpit.autobuild.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.drcockpit.autobuild</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$BASE/auto_build.sh</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>600</integer>
  <key>StandardOutPath</key><string>$BASE/auto_build.launchd.log</string>
  <key>StandardErrorPath</key><string>$BASE/auto_build.launchd.log</string>
</dict>
</plist>
PLISTEOF
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
echo ""
echo "설치 완료. 10분마다 인터넷을 확인하고, 매뉴얼 자료가 바뀌었을 때만 DB를 갱신합니다."
echo "진행 기록: $BASE/auto_build.log"
echo ""
read -r -p "Enter를 누르면 창이 닫힙니다..."
