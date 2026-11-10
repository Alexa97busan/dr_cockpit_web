#!/bin/bash
# icon.png(정사각형 이미지)를 DR-COCKPIT.app의 아이콘으로 적용한다. 이미지를 바꾼 뒤 다시 실행하면 됩니다.
BASE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$BASE/icon/icon.png" ]; then
  SRC="$BASE/icon/icon.png"
else
  SRC="$BASE/icon.png"
fi
APP="$BASE/DR-COCKPIT.app"
ICONSET="$BASE/icon.iconset"

if [ ! -f "$SRC" ]; then
  echo "icon 폴더(또는 dr_cockpit 폴더)에 icon.png 파일을 넣어 주세요. (정사각형, 1024x1024 권장)"
  read -r -p "Enter를 누르면 창이 닫힙니다..."
  exit 1
fi

rm -rf "$ICONSET" && mkdir "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s "$SRC" --out "$ICONSET/icon_${s}x${s}.png" > /dev/null
  d=$((s * 2))
  sips -z $d $d "$SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" > /dev/null
done

mkdir -p "$APP/Contents/Resources"
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
rm -rf "$ICONSET"

PLIST="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Delete :CFBundleIconFile" "$PLIST" 2>/dev/null
/usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$PLIST"
touch "$APP"

echo ""
echo "아이콘 적용 완료. 바로 안 보이면 Dock에서 앱을 뺐다가 다시 추가해 보세요."
read -r -p "Enter를 누르면 창이 닫힙니다..."
