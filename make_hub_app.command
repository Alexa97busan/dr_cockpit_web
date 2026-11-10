#!/bin/bash
# 바탕화면에 DR-HUB 아이콘을 만든다. 이 아이콘을 더블클릭하면 start_all.command(문제풀이 + 웹채팅 실행)가 바로 켜진다.
# 한 번만 실행하면 됩니다. 아이콘 이미지를 바꾸고 싶으면 icon/icon.png 를 바꾼 뒤 다시 실행하세요.
BASE="$(cd "$(dirname "$0")" && pwd)"
SRC="$BASE/icon/icon.png"
[ -f "$SRC" ] || SRC="$BASE/icon/appiconimg2.png"
DEST="$HOME/Desktop/DR-HUB.app"
TMP="$(mktemp -d)"
ICONSET="$TMP/AppIcon.iconset"

if [ ! -f "$BASE/start_all.command" ] || [ ! -f "$SRC" ]; then
  echo "start_all.command 또는 icon 이미지를 찾지 못했습니다."
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

cat > "$DEST/Contents/MacOS/DR-HUB" <<LAUNCH
#!/bin/bash
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
exec /bin/bash "$BASE/start_all.command"
LAUNCH
chmod +x "$DEST/Contents/MacOS/DR-HUB"

cat > "$DEST/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleDisplayName</key>
	<string>DR-HUB</string>
	<key>CFBundleExecutable</key>
	<string>DR-HUB</string>
	<key>CFBundleIconFile</key>
	<string>AppIcon</string>
	<key>CFBundleIdentifier</key>
	<string>com.drcockpit.hub</string>
	<key>CFBundleName</key>
	<string>DR-HUB</string>
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
echo "바탕화면에 DR-HUB 아이콘을 만들었습니다."
echo "처음 실행 때 '확인되지 않은 개발자' 경고가 뜨면 아이콘을 우클릭 → 열기 를 누르세요."
read -r -p "Enter를 누르면 창이 닫힙니다..."
