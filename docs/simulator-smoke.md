# Simulator Smoke QA - Wording Daily

Last run: 2026-07-10

## Build Under Test

- Commit: `1eb1083`
- Simulator: `iPhone 17 Pro (native-iOS)`
- Simulator ID: `F6E47DF4-6357-4304-B68F-7EB4A203C1DC`
- Bundle ID: `com.raychiutw.WordingDaily`
- Scope: first-screen simulator smoke, not full manual QA.

## Commands Run

```sh
xcrun simctl boot F6E47DF4-6357-4304-B68F-7EB4A203C1DC
xcrun simctl bootstatus F6E47DF4-6357-4304-B68F-7EB4A203C1DC -b
xcodebuild build -project WordingDailyApp.xcodeproj -scheme WordingDailyApp -destination 'platform=iOS Simulator,id=F6E47DF4-6357-4304-B68F-7EB4A203C1DC'
xcrun simctl uninstall F6E47DF4-6357-4304-B68F-7EB4A203C1DC com.raychiutw.WordingDaily
xcrun simctl install F6E47DF4-6357-4304-B68F-7EB4A203C1DC ~/Library/Developer/Xcode/DerivedData/WordingDailyApp-coqsiwlaszzetxeqkxycmzcggylc/Build/Products/Debug-iphonesimulator/WordingDailyApp.app
xcrun simctl launch F6E47DF4-6357-4304-B68F-7EB4A203C1DC com.raychiutw.WordingDaily
```

Screenshots were captured locally under `/tmp/wording-daily-qa/` for this run.
They are not committed to the repo.

## Results

- Build: passed with `** BUILD SUCCEEDED **`.
- Fresh launch: passed. App launched to onboarding welcome, not a blank screen or crash.
- Onboarding welcome zh-Hant: passed. Shows app name, one value sentence, and one primary continue action.
- Today zh-Hant normal size: passed. Shows Today tab, 0/10 progress, one primary start action, due review count, and native `TabView`.
- Today zh-Hant accessibility-extra-large: passed. Text expands without visible overlap or clipped primary action; primary button wraps to two lines.
- Today English normal size: passed. Text fits on Today first screen; native tab labels render as Today, Review, Library.
- Tab structure: passed by source and screenshot. `RootTabView` uses native `TabView` with `.tabItem`, not a custom tab bar.

## Not Covered

- Tapping through the full onboarding flow.
- Notification permission denied/skipped/authorized system prompts.
- Practice session answer states.
- Library detail save toggle.
- Widget small and medium placement on Home Screen.
- Real-device `ios-qa` DebugBridge run.
