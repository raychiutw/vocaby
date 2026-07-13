# Apple Music x Nintendo Learning UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace dashboard-card tab layouts with a native Apple Music-style navigation and list hierarchy, plus Nintendo-inspired local learning summaries.

**Architecture:** Keep SwiftUI `TabView`, `NavigationStack`, `List`, and the existing SwiftData services. Add one reusable local-settings toolbar modifier and one compact row style. Today, Review, and Library consume those shared primitives while retaining all current selection, review, and practice persistence services.

**Tech Stack:** Swift 5, SwiftUI, SwiftData, Xcode test, generated PNG assets in `Assets.xcassets`.

## Global Constraints

- iOS 17+; no login, backend, network, iCloud, or new dependency.
- Preserve Dynamic Type, 44pt targets, native large-title collapse, and dark/light system surfaces.
- Do not replace `TabView` with a custom tab bar.
- One primary focused surface per screen; ordinary metadata and vocabulary lists use plain rows.
- Stage and commit only intentional files when a commit is explicitly requested.

---

### Task 1: Shared local-profile toolbar and compact row components

**Files:**
- Create: `Vocaby/Features/Shared/LearningChrome.swift`
- Modify: `Vocaby/Features/Today/TodayView.swift`
- Modify: `Vocaby/Features/Review/ReviewView.swift`
- Modify: `Vocaby/Features/Library/LibraryView.swift`
- Test: `VocabyTests/LocalizationCoverageTests.swift`

**Interfaces:**
- Produces `View.learningSettingsSheet()` to attach one My Learning button and Settings sheet to a tab root.
- Produces `CompactMetadataRow(title:subtitle:systemImage:tint:)` for two-line native rows.

- [ ] **Step 1: Write the failing localization test**

```swift
func testAppleMusicChromeStringsHaveEnglishAndTraditionalChineseTranslations() throws {
    let catalog = try loadCatalog()
    for key in ["learning.profile.accessibility", "review.estimatedTime"] {
        let value = try XCTUnwrap(catalog.strings[key])
        XCTAssertFalse(value.localizations["en"]?.stringUnit.value.isEmpty ?? true)
        XCTAssertFalse(value.localizations["zh-Hant"]?.stringUnit.value.isEmpty ?? true)
    }
}
```

- [ ] **Step 2: Run the focused test and confirm it fails for the new keys**

Run: `xcodebuild test -quiet -project Vocaby.xcodeproj -scheme Vocaby -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:VocabyTests/LocalizationCoverageTests`

Expected: failure naming the missing localization keys.

- [ ] **Step 3: Add the minimal shared SwiftUI components**

```swift
struct LearningSettingsSheet: ViewModifier {
    @State private var isShowingSettings = false
    func body(content: Content) -> some View {
        content
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { isShowingSettings = true } label: {
                        Image(systemName: "person.crop.circle")
                    }
                    .accessibilityLabel(Text("learning.profile.accessibility"))
                }
            }
            .sheet(isPresented: $isShowingSettings) {
                NavigationStack { SettingsView() }
            }
    }
}

extension View {
    func learningSettingsSheet() -> some View { modifier(LearningSettingsSheet()) }
}
```

- [ ] **Step 4: Replace Today’s inline gear toolbar with `.learningSettingsSheet()` and apply the same modifier to Review and Library**

Use the modifier after each root view’s navigation configuration. Do not attach it to detail views.

- [ ] **Step 5: Add the two localizations and run focused tests**

Run the command from Step 2.

Expected: `LocalizationCoverageTests` passes.

### Task 2: Generate and add focused study-cover assets

**Files:**
- Create: `Vocaby/Resources/Assets.xcassets/DailyFocusCover.imageset/`
- Create: `Vocaby/Resources/Assets.xcassets/ReviewCover.imageset/`
- Create: `Vocaby/Resources/Assets.xcassets/LibraryCover.imageset/`

**Interfaces:**
- Produces `Image("DailyFocusCover")`, `Image("ReviewCover")`, and `Image("LibraryCover")` for top-level focused surfaces.

- [ ] **Step 1: Generate three text-free square PNG assets**

Generate Daily Focus, Review, and Library variants with the approved warm abstract study-art direction. Inspect each image for legibility at 72pt and reject embedded text, logos, people, or busy detail.

- [ ] **Step 2: Add images as universal image sets**

Each `Contents.json` must use the image at 1x only with `preserves-vector-representation` omitted because these are raster assets.

- [ ] **Step 3: Build the app to verify asset compilation**

Run: `xcodebuild build -quiet -project Vocaby.xcodeproj -scheme Vocaby -destination 'platform=iOS Simulator,name=iPhone 17 Pro'`

Expected: build succeeds and no missing-image warnings occur.

### Task 3: Rebuild Today as a compact daily-focus screen

**Files:**
- Modify: `Vocaby/Features/Today/TodayView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`
- Test: `VocabyTests/LocalizationCoverageTests.swift`

**Interfaces:**
- Keeps `startPractice()`, `refreshToday()`, `PracticeCenterView`, `ReviewView` routing, and `PracticeProgressService` unchanged.
- Produces `DailyFocusRow` and compact review/library navigation rows inside Today.

- [ ] **Step 1: Add failing copy-coverage assertions for the compact summary keys**

```swift
try assertLocalized([
    "today.compactSummary.format",
    "today.review.estimatedTime.format",
    "today.libraryProgress.row"
])
```

- [ ] **Step 2: Run the localization test and confirm failure**

Run the focused command from Task 1.

- [ ] **Step 3: Replace the multi-section dashboard layout with one focused section and plain navigation rows**

```swift
Section {
    HStack(spacing: 12) {
        Image("DailyFocusCover").resizable().scaledToFill().frame(width: 64, height: 64).clipShape(RoundedRectangle(cornerRadius: 12))
        VStack(alignment: .leading, spacing: 4) {
            Text("today.compactSummary.format", arguments: [progressText, streakCount])
                .font(.subheadline).foregroundStyle(.secondary)
            Text(primaryButtonTitle).font(.headline)
        }
    }
    ProgressView(value: Double(completedCount), total: Double(totalCount)).tint(AppTheme.accent)
    Button {
        if todaySession != nil && completedCount == totalCount {
            isShowingExtraPractice = true
        } else {
            startPractice()
        }
    } label: {
        Text(todaySession != nil && completedCount == totalCount
            ? "today.extraPractice.button"
            : primaryButtonTitle)
            .frame(maxWidth: .infinity)
    }
        .buttonStyle(.borderedProminent).tint(AppTheme.accent)
}

Section {
    NavigationLink { ReviewView() } label: {
        CompactMetadataRow(title: "review.title", subtitle: reviewSummary, systemImage: "arrow.triangle.2.circlepath", tint: AppTheme.reviewAmber)
    }
    LabeledContent("today.vocabularyProgress.title", value: progressText(for: vocabularyProgress.total))
}
```

Keep the visible level table out of the initial screen. Use `.listStyle(.plain)`.

- [ ] **Step 4: Add localized summary strings and run focused tests**

Expected: localized test passes.

### Task 4: Rebuild Review as a compact queue

**Files:**
- Modify: `Vocaby/Features/Review/ReviewView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`
- Test: `VocabyTests/LocalizationCoverageTests.swift`

**Interfaces:**
- Keeps `ReviewSessionView`, `ReviewScheduler`, and `persistAnswer(_:)` unchanged.
- Uses `dueItems.prefix(3)` to render a next-up preview without changing queue order.

- [ ] **Step 1: Add a failing localization assertion for `review.nextUp.title` and `review.estimatedTime.format`**
- [ ] **Step 2: Run the focused localization test and confirm failure**
- [ ] **Step 3: Implement plain summary and preview rows**

```swift
Section {
    HStack { Text("review.due.title").font(.headline); Spacer(); Text("\\(dueItems.count)").monospacedDigit().foregroundStyle(AppTheme.reviewAmber) }
    Text("review.estimatedTime.format", arguments: [max(1, dueItems.count / 3 + 1)])
        .font(.subheadline).foregroundStyle(.secondary)
    Button("review.start.button") { isShowingReview = true }
        .buttonStyle(.borderedProminent).tint(AppTheme.reviewAmber)
        .disabled(dueItems.isEmpty)
}
Section("review.nextUp.title") { ForEach(dueItems.prefix(3)) { item in Text(item.upgradedExpression) } }
```

- [ ] **Step 4: Use `Image("ReviewCover")` only in the focused summary section and set `.listStyle(.plain)`**
- [ ] **Step 5: Run focused tests**

### Task 5: Rebuild Library as a dense Apple Music-style list

**Files:**
- Modify: `Vocaby/Features/Library/LibraryView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`
- Test: `VocabyTests/LocalizationCoverageTests.swift`

**Interfaces:**
- Keeps `LibraryService`, `LibraryDetailView`, deep-link handling, and `LibraryScope` filtering unchanged.
- Changes `LibraryRowView` to expose exactly two visible text lines.

- [ ] **Step 1: Add a failing localization assertion for `library.compactProgress.format`**
- [ ] **Step 2: Run the focused test and confirm failure**
- [ ] **Step 3: Convert the list to plain style and collapse each row**

```swift
VStack(alignment: .leading, spacing: 4) {
    Text(item.seedItem.upgradedExpression).font(.body.weight(.semibold))
    Text("\\(item.seedItem.plainExpression) · \\(String(localized: statusText))")
        .font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
}
.padding(.vertical, 6)
```

Keep the segmented picker inline, remove enclosing card-like section styling, and use `Image("LibraryCover")` only as a small leading visual in the compact progress header.

- [ ] **Step 4: Run focused localization tests**

### Task 6: Full verification and device review

**Files:**
- Modify: `docs/offline-vocabulary-release-audit-2026-07-11.md` only if the existing audit format has a UI verification section; otherwise no docs change.

- [ ] **Step 1: Run code quality checks**

Run: `git diff --check`

Expected: no output.

- [ ] **Step 2: Run the full test suite**

Run: `xcodebuild test -quiet -project Vocaby.xcodeproj -scheme Vocaby -destination 'platform=iOS Simulator,id=1D057E15-7F4F-4885-A638-5EF1FD299B65' -derivedDataPath /tmp/WDUIDesignTest -resultBundlePath /tmp/WDUIDesignTest.xcresult`

Expected: all tests pass.

- [ ] **Step 3: Build and install the QA app on the connected phone**

Run the existing `VocabyQA` device build/install flow; then capture Today, Review, Library, collapsed-title state, and My Learning screenshots.

- [ ] **Step 4: Compare against the design-review report**

Confirm: no dashboard-card nesting, titles collapse, all tabs expose My Learning, vocabulary rows are two-line, and the app reports the current 10,021-word seed.
