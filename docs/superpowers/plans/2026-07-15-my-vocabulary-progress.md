# My Vocabulary Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the Library destination to My, keep the tab bar visible while scrolling, and show learned-versus-total counts for Basic, Intermediate, and Advanced vocabulary.

**Architecture:** Keep the existing `LibraryView`, `LibraryService`, persistence models, and deep links. Add one pure summary value and calculation to `LibraryService`, render the three results as native list rows above the existing Library controls, and update only public copy/icon/tab-bar configuration. The UI derives totals and learned counts from the same in-memory seed and quiz-result snapshot already used by the learned list.

**Tech Stack:** Swift 6, SwiftUI, SwiftData, XCTest, String Catalogs, iOS 17+ with an iOS 26 tab-bar behavior branch.

## Global Constraints

- Follow `AGENTS.md` and the approved design in `docs/superpowers/specs/2026-07-15-my-vocabulary-progress-design.md`.
- Read and update `DESIGN.md`; the user explicitly approved replacing the public Library destination name with My and disabling tab-bar minimization.
- Keep the native three-tab `TabView`; do not add a fourth tab or custom tab bar.
- Keep internal `LibraryView`, `LibraryService`, `LibraryScope`, `RootTab.library`, file paths, and deep-link identifiers unchanged.
- Preserve the existing learned/saved segmented control, search, list, detail, and deep-link behavior.
- Learned means at least one persisted `QuizResult` for an eligible seed item; saved-only items do not count.
- Repeated quiz results for one item count once; unknown quiz item IDs are ignored.
- The summary must always order Basic, Intermediate, Advanced and must safely represent a zero-total level as `0 / 0` with zero progress.
- Filter summary totals by content language `en` and support language `zh-Hant`, matching the existing Library list.
- Use system SwiftUI controls, existing color tokens, Dynamic Type, monospaced digits, and VoiceOver value text.
- Add no dependency, persistence model, migration, analytics, network call, background job, level filter, or charting abstraction.
- Use test-driven development, stage only intentional files, run `git diff --check`, and do not push.

---

## File Map

- `Vocaby/Services/LibraryService.swift`: owns the pure per-level summary value and calculation.
- `VocabyTests/LibraryServiceTests.swift`: proves totals, distinct learned semantics, ordering, language filtering, unknown-ID handling, and zero progress.
- `Vocaby/Features/Library/LibraryView.swift`: renders the native three-row summary from the already loaded seed and quiz results.
- `Vocaby/Features/Root/RootTabView.swift`: changes the public icon and disables iOS 26 tab minimization.
- `Vocaby/Resources/Localizable.xcstrings`: changes Library copy to My and adds summary copy in English and Traditional Chinese.
- `VocabyTests/LocalizationCoverageTests.swift`: locks public My copy, summary translations, tab icon, and `.never` behavior.
- `DESIGN.md`: records the approved My destination and persistent-tab behavior.

---

### Task 1: Pure per-level vocabulary summary

**Files:**
- Modify: `Vocaby/Services/LibraryService.swift`
- Modify: `VocabyTests/LibraryServiceTests.swift`

**Interfaces:**
- Consumes: `[VocabularySeedItem]`, `[QuizResult]`, `contentLanguageCode: String`, and `supportLanguageCode: String`.
- Produces: `LibraryLevelSummary` and `LibraryService.levelSummaries(from:quizResults:contentLanguageCode:supportLanguageCode:) -> [LibraryLevelSummary]` for Task 2.

- [ ] **Step 1: Extend the test item factory so tests can create every level**

Change the helper signature and seed construction in `VocabyTests/LibraryServiceTests.swift`:

```swift
private func item(
    _ id: String,
    level: VocabularyLevel = .basic,
    sortOrder: Int,
    plainExpression: String = "plain",
    upgradedExpression: String = "upgraded",
    contentLanguageCode: String = "en",
    supportLanguageCodes: [String] = ["zh-Hant"]
) -> VocabularySeedItem {
    // Keep the existing pronunciation, sense, and quiz fixtures.
    return VocabularySeedItem(
        id: id,
        level: level,
        sortOrder: sortOrder,
        contentLanguageCode: contentLanguageCode,
        supportLanguageCodes: supportLanguageCodes,
        plainExpression: plainExpression,
        upgradedExpression: upgradedExpression,
        primarySenseID: senseID,
        pronunciations: [.init(id: pronunciationID, ipa: "tɛst", speechLocale: "en-US", region: "US")],
        senses: [.init(
            id: senseID,
            partOfSpeech: upgradedExpression.contains(" ") ? .phrase : .noun,
            meaning: ["en": "meaning", "zh-Hant": "meaning"],
            example: .init(text: "Example.", translation: ["zh-Hant": "例句。"]),
            pronunciationIDs: [pronunciationID]
        )],
        quiz: VocabularyQuiz(
            prompt: ["en": "prompt", "zh-Hant": "prompt"],
            options: ["A", "B"],
            correctOptionIndex: 0
        )
    )
}
```

Expected: existing tests still compile after call sites continue using the default `.basic` value.

- [ ] **Step 2: Write failing summary tests**

Add these tests to `LibraryServiceTests`:

```swift
func testLevelSummariesCountEligibleTotalsAndDistinctLearnedItems() {
    let seedItems = [
        item("basic-001", level: .basic, sortOrder: 1),
        item("basic-002", level: .basic, sortOrder: 2),
        item("intermediate-001", level: .intermediate, sortOrder: 1),
        item("advanced-001", level: .advanced, sortOrder: 1),
        item("advanced-ja-001", level: .advanced, sortOrder: 2, supportLanguageCodes: ["ja"]),
        item("advanced-fr-001", level: .advanced, sortOrder: 3, contentLanguageCode: "fr")
    ]
    let quizResults = [
        QuizResult(dayKey: "2026-07-10", itemID: "basic-001", selectedOptionIndex: 0, correctOptionIndex: 0),
        QuizResult(dayKey: "2026-07-11", itemID: "basic-001", selectedOptionIndex: 1, correctOptionIndex: 0),
        QuizResult(dayKey: "2026-07-10", itemID: "advanced-001", selectedOptionIndex: 0, correctOptionIndex: 0),
        QuizResult(dayKey: "2026-07-10", itemID: "removed-001", selectedOptionIndex: 0, correctOptionIndex: 0),
        QuizResult(dayKey: "2026-07-10", itemID: "advanced-ja-001", selectedOptionIndex: 0, correctOptionIndex: 0)
    ]

    let summaries = LibraryService().levelSummaries(
        from: seedItems,
        quizResults: quizResults,
        contentLanguageCode: "en",
        supportLanguageCode: "zh-Hant"
    )

    XCTAssertEqual(summaries, [
        .init(level: .basic, learnedCount: 1, totalCount: 2),
        .init(level: .intermediate, learnedCount: 0, totalCount: 1),
        .init(level: .advanced, learnedCount: 1, totalCount: 1)
    ])
}

func testLevelSummariesIncludeZeroTotalLevelsWithZeroProgress() {
    let summaries = LibraryService().levelSummaries(
        from: [item("basic-001", level: .basic, sortOrder: 1)],
        quizResults: [],
        contentLanguageCode: "en",
        supportLanguageCode: "zh-Hant"
    )

    XCTAssertEqual(summaries.map(\.level), [.basic, .intermediate, .advanced])
    XCTAssertEqual(summaries[0].progress, 0)
    XCTAssertEqual(summaries[1], .init(level: .intermediate, learnedCount: 0, totalCount: 0))
    XCTAssertEqual(summaries[1].progress, 0)
    XCTAssertEqual(summaries[2].progress, 0)
}

func testSavedOnlyItemDoesNotCountAsLearned() {
    let seedItems = [item("basic-001", level: .basic, sortOrder: 1)]
    let savedProgress = [WordProgress(itemID: "basic-001", level: .basic, isSaved: true)]
    let service = LibraryService()

    let savedRows = service.items(
        from: seedItems,
        progressRows: savedProgress,
        quizResults: [],
        scope: .saved,
        query: "",
        contentLanguageCode: "en",
        supportLanguageCode: "zh-Hant"
    )
    let summaries = service.levelSummaries(
        from: seedItems,
        quizResults: [],
        contentLanguageCode: "en",
        supportLanguageCode: "zh-Hant"
    )

    XCTAssertEqual(savedRows.map(\.id), ["basic-001"])
    XCTAssertEqual(summaries[0], .init(level: .basic, learnedCount: 0, totalCount: 1))
}
```

The first test also proves incorrect answers still count as learned, matching the existing learned-list definition: the existence of a quiz result is sufficient.

- [ ] **Step 3: Run the focused test to prove RED**

Run:

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath /tmp/vocaby-my-progress-red \
  -only-testing:VocabyTests/LibraryServiceTests \
  CODE_SIGNING_ALLOWED=NO
```

Expected: build fails because `LibraryLevelSummary` and `levelSummaries` do not exist. Do not change production code before observing this failure.

- [ ] **Step 4: Add the minimal pure summary implementation**

Add immediately above `LibraryService` in `Vocaby/Services/LibraryService.swift`:

```swift
struct LibraryLevelSummary: Equatable, Identifiable {
    let level: VocabularyLevel
    let learnedCount: Int
    let totalCount: Int

    var id: VocabularyLevel { level }

    var progress: Double {
        guard totalCount > 0 else { return 0 }
        return Double(learnedCount) / Double(totalCount)
    }
}
```

Add to `LibraryService`:

```swift
func levelSummaries(
    from seedItems: [VocabularySeedItem],
    quizResults: [QuizResult],
    contentLanguageCode: String,
    supportLanguageCode: String
) -> [LibraryLevelSummary] {
    let learnedIDs = Set(quizResults.map(\.itemID))
    let eligibleItems = seedItems.filter { item in
        item.contentLanguageCode == contentLanguageCode
            && item.supportLanguageCodes.contains(supportLanguageCode)
    }

    return VocabularyLevel.allCases.map { level in
        let levelItems = eligibleItems.filter { $0.level == level }
        let learnedCount = levelItems.lazy.filter { learnedIDs.contains($0.id) }.count
        return LibraryLevelSummary(
            level: level,
            learnedCount: learnedCount,
            totalCount: levelItems.count
        )
    }
}
```

Do not add caching or persist these derived values.

- [ ] **Step 5: Run focused and neighboring service tests to prove GREEN**

Run:

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath /tmp/vocaby-my-progress-task1 \
  -only-testing:VocabyTests/LibraryServiceTests \
  CODE_SIGNING_ALLOWED=NO
git diff --check
```

Expected: all `LibraryServiceTests` pass and `git diff --check` reports no error.

- [ ] **Step 6: Commit the pure service change**

Run:

```sh
git add Vocaby/Services/LibraryService.swift VocabyTests/LibraryServiceTests.swift
git commit -m "feat: summarize vocabulary progress by level"
```

Expected: one scoped commit; do not push.

---

### Task 2: My screen, persistent tab bar, localization, and design source of truth

**Files:**
- Modify: `Vocaby/Features/Library/LibraryView.swift`
- Modify: `Vocaby/Features/Root/RootTabView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`
- Modify: `VocabyTests/LocalizationCoverageTests.swift`
- Modify: `DESIGN.md`

**Interfaces:**
- Consumes: Task 1's `LibraryLevelSummary` and `LibraryService.levelSummaries(from:quizResults:contentLanguageCode:supportLanguageCode:)`.
- Produces: a three-row native summary on the My screen; public `My`/`我的` copy; `person.crop.circle`; `.tabBarMinimizeBehavior(.never)`.

- [ ] **Step 1: Write failing localization and root-tab contract tests**

Add to `LocalizationCoverageTests`:

```swift
func testMyVocabularyProgressCopyIsLocalized() throws {
    let catalog = try loadCatalog()
    let expected: [String: (en: String, zhHant: String)] = [
        "library.tab.title": ("My", "我的"),
        "library.title": ("My", "我的"),
        "library.scope.accessibility": ("My filter", "我的篩選"),
        "my.progress.title": ("Vocabulary progress", "詞彙進度"),
        "my.progress.count.format": ("%lld of %lld learned", "已學習 %lld／%lld")
    ]

    for (key, value) in expected {
        XCTAssertEqual(catalog.strings[key]?.localizations["en"]?.stringUnit.value, value.en, key)
        XCTAssertEqual(catalog.strings[key]?.localizations["zh-Hant"]?.stringUnit.value, value.zhHant, key)
    }
}

func testMyTabUsesProfileIconAndNeverMinimizes() throws {
    let testFile = URL(fileURLWithPath: #filePath)
    let projectRoot = testFile.deletingLastPathComponent().deletingLastPathComponent()
    let source = try String(
        contentsOf: projectRoot
            .appendingPathComponent("Vocaby")
            .appendingPathComponent("Features")
            .appendingPathComponent("Root")
            .appendingPathComponent("RootTabView.swift"),
        encoding: .utf8
    )

    XCTAssertEqual(source.components(separatedBy: "systemImage: \"person.crop.circle\"").count - 1, 2)
    XCTAssertTrue(source.contains(".tabBarMinimizeBehavior(.never)"))
    XCTAssertFalse(source.contains(".tabBarMinimizeBehavior(.onScrollDown)"))
}
```

This intentionally treats the declarative tab configuration as a source-level contract; no extra UI-test target or runtime abstraction is warranted.

- [ ] **Step 2: Run the focused tests to prove RED**

Run:

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath /tmp/vocaby-my-ui-red \
  -only-testing:VocabyTests/LocalizationCoverageTests \
  CODE_SIGNING_ALLOWED=NO
```

Expected: the copy and tab-contract tests fail on Library copy, the books icon, and `.onScrollDown`.

- [ ] **Step 3: Change the root tab's public icon and scroll behavior**

In both modern and legacy tab declarations in `Vocaby/Features/Root/RootTabView.swift`, replace `books.vertical` with `person.crop.circle`. In the iOS 26 branch, replace:

```swift
.tabBarMinimizeBehavior(.onScrollDown)
```

with:

```swift
.tabBarMinimizeBehavior(.never)
```

Keep `RootTab.library`, `libraryRoot`, and deep-link routing unchanged.

- [ ] **Step 4: Render the three summaries above the existing controls**

Add this computed property to `LibraryView`:

```swift
private var levelSummaries: [LibraryLevelSummary] {
    libraryService.levelSummaries(
        from: seedItems,
        quizResults: quizResults,
        contentLanguageCode: contentLanguageCode,
        supportLanguageCode: supportLanguageCode
    )
}
```

At the top of `libraryList`, before the existing `Picker`, add:

```swift
if !seedItems.isEmpty {
    Section("my.progress.title") {
        ForEach(levelSummaries) { summary in
            MyLevelProgressRow(summary: summary)
        }
    }
}
```

Hiding the section while `seedItems` is empty prevents fabricated `0 / 0` values before loading or after a load error. A genuinely empty individual level still appears because the loaded seed contains other levels.

Add this private view near `LibraryRowView`:

```swift
private struct MyLevelProgressRow: View {
    let summary: LibraryLevelSummary

    private var levelTitleKey: LocalizedStringKey {
        switch summary.level {
        case .basic: "settings.level.basic"
        case .intermediate: "settings.level.intermediate"
        case .advanced: "settings.level.advanced"
        }
    }

    private var countText: String {
        String.localizedStringWithFormat(
            String(localized: "my.progress.count.format"),
            summary.learnedCount,
            summary.totalCount
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(levelTitleKey)
                    .font(.body.weight(.semibold))
                Spacer(minLength: 12)
                Text(countText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
            }

            ProgressView(value: summary.progress)
                .tint(Color("Accent"))
                .accessibilityHidden(true)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(Text(levelTitleKey))
        .accessibilityValue(Text(countText))
    }
}
```

Do not wrap these rows in custom cards and do not make them navigation links.

- [ ] **Step 5: Update the String Catalog**

Use `apply_patch` to make these exact localization values in `Vocaby/Resources/Localizable.xcstrings`:

```text
library.tab.title              en: My                         zh-Hant: 我的
library.title                  en: My                         zh-Hant: 我的
library.scope.accessibility    en: My filter                  zh-Hant: 我的篩選
my.progress.title              en: Vocabulary progress        zh-Hant: 詞彙進度
my.progress.count.format       en: %lld of %lld learned       zh-Hant: 已學習 %lld／%lld
```

Retain the internal `library.*` keys to avoid cosmetic churn. Reuse the existing `settings.level.basic`, `settings.level.intermediate`, and `settings.level.advanced` strings.

- [ ] **Step 6: Update `DESIGN.md` to match the approved behavior**

Use `apply_patch` for these exact policy changes:

- Replace the public top-level Library destination with My in Platform Rules, Navigation Architecture, Tab labels, Screen Hierarchy, progress placement, and UI-test wording.
- Describe My as the progress summary followed by search, learned/saved segmentation, list, and detail.
- Set the My tab icon to `person.crop.circle`.
- Add: "The tab bar remains fully visible while scrolling; on iOS 26 and later use `.tabBarMinimizeBehavior(.never)`."
- Add a 2026-07-15 decision-log row stating that the user approved My plus three per-level learned/total summaries and a non-minimizing tab bar.
- Leave internal implementation names out of the design-system terminology.

- [ ] **Step 7: Run focused service/localization tests and inspect the diff**

Run:

```sh
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath /tmp/vocaby-my-ui-green \
  -only-testing:VocabyTests/LibraryServiceTests \
  -only-testing:VocabyTests/LocalizationCoverageTests \
  CODE_SIGNING_ALLOWED=NO
git diff --check
git diff -- Vocaby/Features/Library/LibraryView.swift Vocaby/Features/Root/RootTabView.swift Vocaby/Resources/Localizable.xcstrings VocabyTests/LocalizationCoverageTests.swift DESIGN.md
```

Expected: both test classes pass; the diff contains only the approved My screen, localization, fixed tab behavior, and design documentation.

- [ ] **Step 8: Commit the UI and design-system change**

Run:

```sh
git add \
  DESIGN.md \
  Vocaby/Features/Library/LibraryView.swift \
  Vocaby/Features/Root/RootTabView.swift \
  Vocaby/Resources/Localizable.xcstrings \
  VocabyTests/LocalizationCoverageTests.swift
git commit -m "feat: show vocabulary progress in My"
```

Expected: one scoped commit; do not push.

---

### Task 3: Accessibility/manual checks and release verification

**Files:**
- Modify only if a check exposes a scoped defect in Task 1 or Task 2.
- Test: the full existing Swift and Python suites.

**Interfaces:**
- Consumes: the complete My screen from Tasks 1 and 2 and the final expanded `VocabularySeed.json` from the all-approved-vocabulary work.
- Produces: verified simulator/release artifacts with no new persisted or bundled intermediate data.

- [ ] **Step 1: Verify exact expanded-seed totals drive the summary inputs**

Run:

```sh
python3 - <<'PY'
import json
from collections import Counter

seed = json.load(open("Vocaby/Resources/VocabularySeed.json", encoding="utf-8"))
counts = Counter(item["level"] for item in seed)
assert set(counts) == {"basic", "intermediate", "advanced"}
assert sum(counts.values()) == len(seed)
print({**dict(counts), "total": len(seed)})
PY
```

Expected: all three levels are non-empty and sum exactly to the final seed total. Record the emitted values in the task report; do not hard-code them into the UI.

- [ ] **Step 2: Run the complete Python and Swift test suites**

Run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tools -p 'test_*.py'
xcodebuild test \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro,OS=latest' \
  -derivedDataPath /tmp/vocaby-my-progress-all-tests \
  CODE_SIGNING_ALLOWED=NO
```

Expected: every Python test passes and Xcode reports `** TEST SUCCEEDED **`.

- [ ] **Step 3: Perform the required visual/accessibility checks**

Launch the app in the iPhone 17 Pro simulator and verify:

1. zh-Hant: the third tab and navigation title both read `我的`.
2. English: the third tab and navigation title both read `My`.
3. The tab icon is `person.crop.circle` in both supported tab APIs.
4. Scroll the My list downward on an iOS 26 simulator; the tab bar remains full-size and visible.
5. Basic, Intermediate, and Advanced appear in order with learned/total values matching a controlled local test state.
6. Repeating a quiz for one item does not increase the learned count a second time.
7. Saved-only vocabulary appears under Saved but does not increase learned count.
8. Search, learned/saved switching, detail navigation, save toggle, and deep-linked detail still work.
9. Check light/dark mode, normal Dynamic Type, and an accessibility Dynamic Type size; level names and count text remain readable without horizontal clipping.
10. With VoiceOver, each row announces level plus learned and total values once.

Expected: all checks pass. If a check fails, use `superpowers:systematic-debugging`, add the smallest automated regression where practical, and keep the fix within this feature's files.

- [ ] **Step 4: Build Release and inspect the app bundle**

Run:

```sh
xcodebuild build \
  -project Vocaby.xcodeproj \
  -scheme Vocaby \
  -configuration Release \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath /tmp/vocaby-my-progress-release \
  CODE_SIGNING_ALLOWED=NO
APP=/tmp/vocaby-my-progress-release/Build/Products/Release-iphonesimulator/Vocaby.app
test -f "$APP/VocabularySeed.json"
test -f "$APP/ThirdPartyNotices.txt"
test -z "$(find "$APP" -type f \( \
  -path '*/Content/Sources/*' -o \
  -path '*/Content/Reviews/*' -o \
  -name 'VocabularyProvenance.json' -o \
  -name 'source-manifest.json' \
\) -print -quit)"
git diff --check
git status --short --branch
```

Expected: `** BUILD SUCCEEDED **`; only the seed and notices ship from the vocabulary pipeline; no raw, review, provenance, or manifest file is bundled; the worktree contains only intentional changes or is clean after commits.

- [ ] **Step 5: Commit only a scoped verification fix if one was required**

If Steps 1-4 required no edit, do not create an empty commit. If a scoped fix was required, stage only its exact files, review `git diff --cached`, and commit:

```sh
git commit -m "fix: polish My vocabulary progress"
```

Do not push. Hand the branch back for final whole-branch review.
