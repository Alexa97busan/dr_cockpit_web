#!/bin/bash
# 바탕화면에 DR-STOP 아이콘을 만든다. 더블클릭하면 stop_all.command(DR 서버 3개 종료)가 실행된다.
# 한 번만 실행하면 됩니다. 폴더를 옮기면 다시 실행하세요.
BASE="$(cd "$(dirname "$0")" && pwd)"
SRC="$BASE/icon/icon.png"
[ -f "$SRC" ] || SRC="$BASE/icon/appiconimg2.png"
DEST="$HOME/Desktop/DR-STOP.app"
TMP="$(mktemp -d)"
ICONSET="$TMP/AppIcon.iconset"

if [ ! -f "$BASE/stop_all.command" ] || [ ! -f "$SRC" ]; then
  echo "stop_all.command 또는 icon 이미지를 찾지 못했습니다."
  read -r -p "Enter를 누르면 창이 닫힙니다..."
  exit 1
fi

mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$SRC" --out "$ICONSET/icon_${s}x${s}.png" > /dev/null
  d=$((s * 2))
  sips -z $d $d "$SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" > /dev/null
done

rm -rf "$DEST"
mkdir -p "$DEST/Contents/MacOS" "$DEST/Contents/Resources"
iconutil -c icns "$ICONSET" -o "$DEST/Contents/Resources/AppIcon.icns"
rm -rf "$TMP"

cat > "$DEST/Contents/MacOS/DR-STOP" <<LAUNCH
#!/bin/bash
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
exec /bin/bash "$BASE/stop_all.command"
LAUNCH
chmod +x "$DEST/Contents/MacOS/DR-STOP"

cat > "$DEST/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDisplayName</key>
	<string>DR-STOP</string>
	<key>CFBundleExecutable</key>
	<string>DR-STOP</string>
	<key>CFBundleIconFile</key>
	<string>AppIcon</string>
	<key>CFBundleIdentifier</key>
	<string>com.drcockpit.stop</string>
	<key>CFBundleName</key>
	<string>DR-STOP</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>1.0</string>
	<key>CFBundleVersion</key>
	<string>1.0</string>
	<key>LSMinimumSystemVersion</key>
	<string>11.0</string>
	<key>NSHighResolutionCapable</key>
	<true/>
</dict>
</plist>
PLIST

touch "$DEST"
echo ""
echo "바탕화면에 DR-STOP 아이콘을 만들었습니다."
echo "처음 실행 때 경고가 뜨면 아이콘을 우클릭 → 열기 를 누르세요."
read -r -p "Enter를 누르면 창이 닫힙니다..."
