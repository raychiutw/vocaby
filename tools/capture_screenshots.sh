#!/bin/bash
# 深淺模式擷圖比對。用法: tools/capture_screenshots.sh [--update]
#   預設:擷圖後與 docs/screenshots/baseline 比對,差異報告寫到 .build/screenshots/report
#   --update:用本次擷圖取代基準圖
# 使用專用模擬器 "Vocaby-Shots",每個外觀前都會 erase,確保從全新安裝(onboarding)開始。
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="Vocaby-Shots"
OUT=".build/screenshots"
BASELINE="docs/screenshots/baseline"

udid=$(xcrun simctl list devices | grep -F "$NAME (" | head -1 | sed -E 's/.*\(([0-9A-F-]{36})\).*/\1/' || true)
if [ -z "$udid" ]; then
  runtime=$(xcrun simctl list runtimes | grep -E '^iOS ' | tail -1 | sed -E 's/.* - //')
  udid=$(xcrun simctl create "$NAME" "iPhone 17" "$runtime")
fi

rm -rf "$OUT/current"
mkdir -p "$OUT/current"
for appearance in light dark; do
  xcrun simctl shutdown "$udid" 2>/dev/null || true
  xcrun simctl erase "$udid"
  xcrun simctl bootstatus "$udid" -b >/dev/null
  xcrun simctl ui "$udid" appearance "$appearance"
  xcrun simctl status_bar "$udid" override --time 9:41 --batteryState charged --batteryLevel 100 --wifiBars 3 --cellularBars 4
  TEST_RUNNER_VOCABY_APPEARANCE="$appearance" \
  TEST_RUNNER_VOCABY_SHOT_DIR="$PWD/$OUT/current" \
    xcodebuild test -project Vocaby.xcodeproj -scheme VocabyUITests \
      -destination "platform=iOS Simulator,id=$udid" \
      -derivedDataPath "$OUT/DerivedData" CODE_SIGNING_ALLOWED=NO -quiet
done
xcrun simctl shutdown "$udid" 2>/dev/null || true

if [ "${1:-}" = "--update" ]; then
  python3 tools/compare_screenshots.py "$BASELINE" "$OUT/current" "$OUT/report" --update
  echo "基準圖已更新: $BASELINE"
else
  python3 tools/compare_screenshots.py "$BASELINE" "$OUT/current" "$OUT/report"
fi
