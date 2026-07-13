# Simulator and qa-ios Smoke QA - Vocaby

Last run: 2026-07-11

## Build Under Test

- Branch: `codex/complete-v1` working tree.
- Simulator: `iPhone 17 Pro`, iOS 26.5.
- Simulator ID: `642EFBFD-4D1B-4946-8BD4-8FE6A852E59A`.
- Formal scheme/bundle: `Vocaby` / `com.raychiutw.Vocaby`.
- QA scheme/bundle: `VocabyQA` / `com.raychiutw.Vocaby.QA`.

`VocabyQA` is an independent internal target. Only its Debug
configuration defines `GSTACK_IOS_QA` and links the repo-local `DebugBridge`
package. The formal target has no DebugBridge product dependency.

## Commands Run

```sh
xcrun simctl terminate \
  642EFBFD-4D1B-4946-8BD4-8FE6A852E59A \
  com.raychiutw.Vocaby.QA 2>/dev/null || true
swift test --package-path DebugBridge

xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A' \
  -only-testing:VocabyTests \
  CODE_SIGNING_ALLOWED=NO

xcodebuild build \
  -project Vocaby.xcodeproj \
  -scheme VocabyQA \
  -configuration Debug \
  -destination 'platform=iOS Simulator,id=642EFBFD-4D1B-4946-8BD4-8FE6A852E59A' \
  CODE_SIGNING_ALLOWED=NO

xcodebuild build \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -configuration Release \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO
```

## Bridge Contract

- State server listens on port 9999 and requires a one-time boot token followed
  by bearer-token rotation.
- Stop any running QA build before the macOS package tests because both use the
  intentionally fixed local port 9999.
- Mutation endpoints additionally require an acquired `X-Session-ID`.
- `/healthz`, `/auth/rotate`, `/session/acquire`, `/elements`, `/screenshot`, and
  `/tap` were exercised against a fresh QA install.
- `/elements` returned the visible SwiftUI accessibility tree in under 0.1 s.
- Bridge touch completed onboarding and reached the Today screen.

## Results

- DebugBridge package: 3 tests passed, 0 failed.
- Formal iOS unit suite: 92 tests passed, 0 failed or skipped.
- QA Debug simulator build: passed.
- Formal Release simulator build: passed.
- Fresh QA launch and onboarding: passed in Traditional Chinese.
- Today screen and native `TabView`: visually inspected from bridge screenshot.
- Formal Release bundle contains `VocabularySeed.json`, notices, localization,
  assets, and the widget only; no DebugBridge marker, raw/imported source,
  manifest, or provenance artifact was found.

Screenshots and endpoint responses are kept under `/tmp/wording-qa-*` for the
local run and are not committed.

## Not Covered

- Notification permission denied and authorized system-alert branches.
- Widget small and medium placement on the Home Screen.
- Real-device CoreDevice tunnel; the authenticated simulator path is verified.
