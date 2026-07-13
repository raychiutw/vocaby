# iOS 26 Apple Music Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Vocaby's titles, tabs, primary actions, contrast, and bottom action chrome match native Apple Music-style iOS 26 behavior while preserving the app's teal identity and iOS 17 minimum deployment target.

**Architecture:** Keep the native `TabView` and three `NavigationStack` roots. Use modern `Tab` declarations plus iOS 26 tab minimization on iOS 26, retain the legacy tab declarations on iOS 17-25, add availability-gated modifiers in shared SwiftUI chrome, and use an asset-backed appearance-aware label color.

**Tech Stack:** SwiftUI, Xcode 26.6, iOS 17+, iOS 26 `tabBarMinimizeBehavior` and `glassProminent`, XCTest, CoreSimulator, CoreDevice.

## Global Constraints

- Preserve `DESIGN.md`: native `TabView`, native controls, restrained teal accent, no custom tab bar, no decorative gradients.
- Keep iOS 17 as the deployment target; every iOS 26-only API must be availability-gated.
- Use semantic primary/secondary text outside prominent actions.
- Do not add a MiniPlayer, tab accessory, dependency, or new navigation abstraction.
- Preserve the user's existing `.codebase-memory` changes.
- Do not commit or push unless the user separately asks.

---

### Task 1: Shared iOS 26 primary action chrome and contrast tokens

**Files:**
- Create: `Vocaby/Assets.xcassets/ProminentInk.colorset/Contents.json`
- Modify: `Vocaby/Assets.xcassets/ReviewAmber.colorset/Contents.json`
- Modify: `Vocaby/Design/Theme.swift`
- Modify: `Vocaby/Features/Shared/LearningChrome.swift`

**Interfaces:**
- Produces: `AppTheme.prominentInk: Color`
- Produces: `View.prominentActionStyle(tint: Color = AppTheme.accent) -> some View`
- Produces: `View.bottomActionChrome() -> some View`

- [x] **Step 1: Record the failing contrast baseline**

Run a local WCAG calculation for current assets. Expected baseline: white on dark Accent `1.83:1`, white on light ReviewAmber `4.28:1`, white on dark ReviewAmber `1.72:1`.

- [x] **Step 2: Add the appearance-aware label token**

Create `ProminentInk.colorset` with white (`1,1,1`) in light appearance and black (`0,0,0`) in dark appearance. Add:

```swift
static let prominentInk = Color("ProminentInk")
```

to `AppTheme`.

- [x] **Step 3: Tune light ReviewAmber**

Change only the light asset components to `#AA6400` (`red 0.667`, `green 0.392`, `blue 0.000`). Keep dark `#FFB84D` unchanged.

- [x] **Step 4: Add shared native action modifiers**

Add to the existing `View` extension in `LearningChrome.swift`:

```swift
@ViewBuilder
func prominentActionStyle(tint: Color = AppTheme.accent) -> some View {
    if #available(iOS 26.0, *) {
        self
            .buttonStyle(.glassProminent)
            .tint(tint)
            .foregroundStyle(AppTheme.prominentInk)
    } else {
        self
            .buttonStyle(.borderedProminent)
            .tint(tint)
            .foregroundStyle(AppTheme.prominentInk)
    }
}

@ViewBuilder
func bottomActionChrome() -> some View {
    if #available(iOS 26.0, *) {
        self
    } else {
        self.background(.regularMaterial)
    }
}
```

- [x] **Step 5: Verify asset contrast**

Expected: white on light Accent `5.24:1`; black on dark Accent `11.48:1`; white on light ReviewAmber `4.63:1`; black on dark ReviewAmber `12.22:1`.

### Task 2: Apple Music-style navigation hierarchy

**Files:**
- Modify: `Vocaby/Features/Root/RootTabView.swift`
- Modify: `Vocaby/Features/Library/LibraryView.swift`

**Interfaces:**
- Consumes: existing `RootTab`, `selectedTab`, and `route(_:)`
- Produces: iOS 26 on-scroll tab minimization with unchanged iOS 17-25 layout

- [x] **Step 1: Capture the current always-expanded tab baseline**

Use the clean iOS 26 simulator and scroll Today. Expected failure: the native tab bar remains expanded.

- [x] **Step 2: Availability-gate tab minimization**

Use modern `Tab` declarations on iOS 26 so the tab bar participates fully in the current `TabContentBuilder` behavior. Keep the original `.tabItem` declarations as the iOS 17-25 fallback, share the three navigation roots, and keep deep-link handlers outside the availability branch:

```swift
var body: some View {
    Group {
        if #available(iOS 26.0, *) {
            modernTabs
                .tabBarMinimizeBehavior(.onScrollDown)
        } else {
            legacyTabs
        }
    }
    // Shared URL and internal-notification routing.
}
```

- [x] **Step 3: Remove the duplicate Library title**

Delete only the content-row `Text("library.title").font(.headline)`. Keep the native `.navigationTitle("library.title")`, cover art, and compact progress.

- [x] **Step 4: Compile the availability branch**

Run:

```bash
xcodebuild -project Vocaby.xcodeproj -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=Vocaby iOS26 Audit' \
  CODE_SIGNING_ALLOWED=NO build
```

Expected: `** BUILD SUCCEEDED **` with deployment target still iOS 17.

### Task 3: Apply native prominent actions and remove legacy iOS 26 footer slabs

**Files:**
- Modify: `Vocaby/Features/Onboarding/OnboardingView.swift`
- Modify: `Vocaby/Features/Today/TodayView.swift`
- Modify: `Vocaby/Features/Review/ReviewView.swift`
- Modify: `Vocaby/Features/Practice/PracticeView.swift`

**Interfaces:**
- Consumes: `prominentActionStyle(tint:)` and `bottomActionChrome()` from Task 1
- Produces: native iOS 26 glass-prominent primary actions and legacy fallbacks

- [x] **Step 1: Replace all nine bordered-prominent call sites**

Replace `.buttonStyle(.borderedProminent)` plus adjacent `.tint(...)` with `.prominentActionStyle(tint: ...)`. Onboarding uses the default accent. Do not change bordered quiz options or plain buttons.

- [x] **Step 2: Remove only the iOS 26 opaque footer layer**

In the two practice `safeAreaInset` footers, replace `.background(.regularMaterial)` with `.bottomActionChrome()`. This retains material on iOS 17-25 and leaves iOS 26 glass-prominent buttons floating without a second slab.

- [x] **Step 3: Verify source coverage**

Search production Swift files. Expected: no remaining `.buttonStyle(.borderedProminent)` and exactly zero direct `.background(.regularMaterial)` occurrences in practice footers; both behaviors are centralized in `LearningChrome.swift`.

### Task 4: Full verification and physical-device delivery

**Files:**
- Update: `/Users/ray/.gstack/projects/raychiutw-vocaby/ios-design-review-2026-07-13.md`
- Create screenshots under: `/Users/ray/.gstack/projects/raychiutw-vocaby/ios-design-review-2026-07-13-assets/`

**Interfaces:**
- Consumes: all prior UI changes
- Produces: verified simulator evidence and an updated build installed on `Ray的iPhone`

- [ ] **Step 1: Run the full test suite**

```bash
xcodebuild test -project Vocaby.xcodeproj -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=Vocaby iOS26 Audit' \
  CODE_SIGNING_ALLOWED=NO
```

Expected: `** TEST SUCCEEDED **` and zero test failures.

- [ ] **Step 2: Capture light and dark screenshots**

Capture Today at top, Today after a downward scroll, Library, Review, and dark Today. Verify the tab minimizes after scroll, Library has one title, and prominent labels are legible.

- [ ] **Step 3: Build for the paired iPhone**

Use the existing HouseStore team and current local provisioning profiles. Until Xcode has a logged-in account capable of regenerating App Group profiles, pass `DEVELOPMENT_TEAM=G56X2626SD CODE_SIGN_ENTITLEMENTS=` as the same temporary device-build override used by the verified install flow.

- [ ] **Step 4: Install and verify the app inventory**

Install with `xcrun devicectl device install app` to device `77F2E6C0-ECF9-5E25-81E4-5554094C6960`, then verify `Vocaby 1.0 (1)` is listed. Launch if the phone is unlocked; otherwise report only the lock-state limitation.

- [ ] **Step 5: Close the report**

Append an after-state section with screenshots, final scores, changed files, test/build/install evidence, and any remaining App Group limitation. Mark the review `DONE` only when every acceptance criterion is evidenced.
