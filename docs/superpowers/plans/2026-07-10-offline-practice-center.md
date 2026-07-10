# Offline Practice Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the answer-leaking daily quiz with a Learn → Quiz flow and add an offline Practice Center modeled on the useful concepts in LingoLearn-iOS without copying its code, UI, copy, or content.

**Architecture:** Keep the bundled vocabulary DTOs as the only question corpus and add one pure `QuizEngine` that selects local items, builds real same-level distractors, randomizes modes/options, and evaluates spelling. One native SwiftUI practice flow serves both the fixed 10-item daily session and free practice; only daily first attempts write SwiftData and the existing review schedule. Free practice is ephemeral, configurable, and never changes daily completion.

**Tech Stack:** Swift 6, SwiftUI, SwiftData, AVFoundation `AVSpeechSynthesizer`, WidgetKit, UserNotifications, XCTest, iOS 17+.

## Global Constraints

- The app remains fully local: no network calls, account, sign-in, credentials, backend, iCloud, sync, or sync-ready abstraction.
- New words and every distractor come only from `WordingDailyApp/Resources/VocabularySeed.json`.
- Keep the bundled seed DTOs separate from SwiftData `@Model` state.
- Today remains a fixed 10-item daily session; Practice Center counts are 5, 10, 15, or 20.
- Practice Center modes are expression choice, meaning choice, listening choice, spelling, and mixed.
- Timers are 10, 15, 20, or 30 seconds; default is 15 seconds.
- Daily mode defaults to mixed, 10 items, 15 seconds, and wrong-answer retry.
- New daily items are shown in a Learn phase before Quiz; review-fill items are not re-taught.
- Choice distractors are unique local items from the same vocabulary level, and the correct answer is shuffled instead of always occupying index 0.
- A timeout is a wrong answer, freezes feedback, and still requires the explicit `Next` action. Never auto-advance.
- Wrong-answer retry happens only after the result screen and does not schedule review a second time.
- Keep the native `TabView` with Today, Review, and Library. Practice Center is reached from Today, not a new tab.
- Follow `DESIGN.md`: native SwiftUI controls, calm surfaces, Dynamic Type, 44 pt targets, semantic answer colors plus icons/text, and no custom tab bar or game layer.
- App UI strings have English and Traditional Chinese localizations.
- Reference repository `/tmp/lingolearn-ios-reference` has no visible LICENSE; do not copy source, text, UI, assets, or vocabulary.

---

### Task 3: Pure local quiz engine

**Files:**
- Create: `WordingDailyApp/Services/QuizEngine.swift`
- Create: `WordingDailyAppTests/QuizEngineTests.swift`
- Modify: `WordingDailyApp.xcodeproj/project.pbxproj`

**Interfaces:**
- Produces: `PracticeMode`, `PracticeConfiguration`, `QuizQuestion`, `QuizAttempt`, and `QuizEngine`.
- `QuizEngine.selectPracticeItems(from:learnedItemIDs:count:using:)` chooses learned local items first and fills shortages from unseen local items.
- `QuizEngine.makeQuestions(for:candidates:mode:supportLanguageCode:using:)` creates questions and same-level local distractors.
- `QuizEngine.isCorrect(_:for:)` evaluates choices and case-insensitive, edge-trimmed spelling.

- [ ] **Step 1: Add failing engine tests**

```swift
final class QuizEngineTests: XCTestCase {
    func testPracticeSelectionUsesLearnedItemsThenFillsFromLocalSeed() {
        let items = makeItems(count: 6)
        var random = IncrementingRandomNumberGenerator()

        let selected = QuizEngine().selectPracticeItems(
            from: items,
            learnedItemIDs: [items[0].id, items[1].id],
            count: 5,
            using: &random
        )

        XCTAssertEqual(selected.count, 5)
        XCTAssertTrue(Set([items[0].id, items[1].id]).isSubset(of: Set(selected.map(\.id))))
        XCTAssertEqual(Set(selected.map(\.id)).count, 5)
    }

    func testExpressionChoiceUsesPlainPromptAndLocalUpgrades() throws {
        let items = makeItems(count: 5)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .expressionChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.prompt, items[0].plainExpression)
        XCTAssertEqual(question.correctAnswer, items[0].upgradedExpression)
        XCTAssertEqual(question.options.count, 4)
        XCTAssertEqual(Set(question.options).count, 4)
    }

    func testDistractorsStayInLevelAndDeduplicateVisibleText() throws {
        var items = makeItems(count: 6)
        items[4].level = .advanced
        items[5].upgradedExpression = items[1].upgradedExpression
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .expressionChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertFalse(question.options.contains(items[4].upgradedExpression))
        XCTAssertEqual(Set(question.options).count, question.options.count)
        XCTAssertEqual(question.options.filter { $0 == items[1].upgradedExpression }.count, 1)
    }

    func testMeaningChoiceUsesUpgradePromptAndLocalizedMeanings() throws {
        let items = makeItems(count: 5)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .meaningChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.prompt, items[0].upgradedExpression)
        XCTAssertEqual(question.correctAnswer, items[0].meaning["zh-Hant"])
        XCTAssertEqual(Set(question.options).count, 4)
    }

    func testListeningChoiceCarriesSpeechTextWithoutShowingAnswer() throws {
        let items = makeItems(count: 5)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .listeningChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.prompt, "")
        XCTAssertEqual(question.spokenText, items[0].pronunciationText)
        XCTAssertEqual(question.correctAnswer, items[0].upgradedExpression)
    }

    func testSpellingUsesMeaningAndIgnoresCaseAndEdgeWhitespace() throws {
        let items = makeItems(count: 1)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: items, candidates: items, mode: .spelling,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.prompt, items[0].meaning["zh-Hant"])
        XCTAssertTrue(QuizEngine().isCorrect("  \(items[0].upgradedExpression.uppercased())  ", for: question))
        XCTAssertFalse(QuizEngine().isCorrect("different answer", for: question))
    }

    func testMixedCreatesOnlyConcreteModesAndShufflesCorrectPositions() {
        let items = makeItems(count: 12)
        var random = IncrementingRandomNumberGenerator()
        let questions = QuizEngine().makeQuestions(
            for: items, candidates: items, mode: .mixed,
            supportLanguageCode: "zh-Hant", using: &random
        )

        XCTAssertEqual(Set(questions.prefix(4).map(\.mode)), Set(PracticeMode.allCases.filter { $0 != .mixed }))
        XCTAssertFalse(questions.contains { $0.mode == .mixed })
        XCTAssertGreaterThan(Set(questions.compactMap(\.correctOptionIndex)).count, 1)
    }

    func testQuestionGenerationUsesFewerUniqueOptionsWhenSeedIsExhausted() throws {
        let items = makeItems(count: 2)
        var random = IncrementingRandomNumberGenerator()
        let question = try XCTUnwrap(QuizEngine().makeQuestions(
            for: [items[0]], candidates: items, mode: .expressionChoice,
            supportLanguageCode: "zh-Hant", using: &random
        ).first)

        XCTAssertEqual(question.options.count, 2)
        XCTAssertEqual(Set(question.options).count, 2)
        XCTAssertTrue(question.options.contains(question.correctAnswer))
    }

    private func makeItems(count: Int) -> [VocabularySeedItem] {
        (1...count).map { index in
            VocabularySeedItem(
                id: "basic-\(index)", level: .basic, sortOrder: index,
                contentLanguageCode: "en", supportLanguageCodes: ["zh-Hant"],
                plainExpression: "plain \(index)", upgradedExpression: "upgrade \(index)",
                meaning: ["en": "definition \(index)", "zh-Hant": "意思 \(index)"],
                example: .init(text: "Example \(index).", translation: ["zh-Hant": "例句 \(index)。"]),
                pronunciationText: "upgrade \(index)",
                quiz: .init(prompt: ["zh-Hant": "legacy"], options: ["legacy A", "legacy B"], correctOptionIndex: 0)
            )
        }
    }
}

private struct IncrementingRandomNumberGenerator: RandomNumberGenerator {
    private var value: UInt64 = 0

    mutating func next() -> UInt64 {
        defer { value &+= 1 }
        return value
    }
}
```

- [ ] **Step 2: Run RED**

Run:

```bash
xcodebuild test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=F6E47DF4-6357-4304-B68F-7EB4A203C1DC' \
  -only-testing:WordingDailyAppTests/QuizEngineTests
```

Expected: FAIL because `QuizEngine` and its models do not exist.

- [ ] **Step 3: Add the minimum engine**

```swift
enum PracticeMode: String, CaseIterable, Codable, Identifiable {
    case mixed, expressionChoice, meaningChoice, listeningChoice, spelling
    var id: String { rawValue }
}

struct PracticeConfiguration: Equatable {
    static let questionCounts = [5, 10, 15, 20]
    static let timeLimits = [10, 15, 20, 30]
    static let daily = PracticeConfiguration(mode: .mixed, questionCount: 10, timeLimitSeconds: 15, retriesWrongAnswers: true)

    var mode: PracticeMode
    var questionCount: Int
    var timeLimitSeconds: Int
    var retriesWrongAnswers: Bool
}

struct QuizQuestion: Identifiable, Equatable {
    let id: String
    let itemID: String
    let mode: PracticeMode
    let prompt: String
    let options: [String]
    let correctAnswer: String
    let spokenText: String?

    var correctOptionIndex: Int? { options.firstIndex(of: correctAnswer) }
}

struct QuizAttempt: Equatable {
    let question: QuizQuestion
    let submittedAnswer: String
    let wasCorrect: Bool
    let timedOut: Bool
}
```

Use `SystemRandomNumberGenerator` in production and a generic `inout RandomNumberGenerator` overload in tests. Build four unique options when the local same-level pool has enough distinct values; otherwise return every unique available value. Do not read `VocabularyQuiz.options`.

- [ ] **Step 4: Run GREEN and the full suite**

Run the focused command above, then the full `xcodebuild test` command. Expected: focused tests pass and the suite exceeds the 59-test baseline with zero failures.

- [ ] **Step 5: Commit**

```bash
git add WordingDailyApp/Services/QuizEngine.swift WordingDailyAppTests/QuizEngineTests.swift WordingDailyApp.xcodeproj/project.pbxproj
git diff --check
git commit -m "feat: add offline quiz engine"
```

---

### Task 4: Add testable run, timeout, retry, and persistence mapping state

**Files:**
- Modify: `WordingDailyApp/Services/QuizEngine.swift`
- Modify: `WordingDailyAppTests/QuizEngineTests.swift`

**Interfaces:**
- Consumes: `QuizQuestion` and `QuizAttempt` from Task 3.
- Produces: `QuizRunState` whose first-attempt/retry boundary lets views avoid duplicate SwiftData and review-scheduler writes.

- [ ] **Step 1: Write failing state tests**

Add tests proving:

- `submit` freezes feedback on the same question.
- `advance` is the only transition to the next question.
- timeout produces a wrong `QuizAttempt` and still waits for `advance`.
- result retry contains only wrong questions, preserves each question's concrete mode, and marks `isFirstAttempt == false`.
- mixed uses a four-mode shuffle bag before repeating a mode.
- option questions expose their real selected/correct indices.
- spelling maps to synthetic persistence indices `correct = 1`, `selected = 1` when correct and `selected = 0` when wrong, so existing SwiftData schemas remain unchanged.

- [ ] **Step 2: Run RED**

Run `-only-testing:WordingDailyAppTests/QuizEngineTests`. Expected: compile failure for `QuizRunState` and the persistence-index mapping.

- [ ] **Step 3: Implement the smallest state machine**

`QuizRunState` owns only current-run questions, index, current feedback, first-attempt attempts, retry attempts, and the retry-round flag. It must not import SwiftData or call a scheduler. Views persist only when the returned attempt has `isFirstAttempt == true`.

```swift
struct QuizPersistenceIndices: Equatable {
    let selected: Int
    let correct: Int
}

extension QuizQuestion {
    func persistenceIndices(for submittedAnswer: String, wasCorrect: Bool) -> QuizPersistenceIndices {
        if mode == .spelling {
            return .init(selected: wasCorrect ? 1 : 0, correct: 1)
        }
        return .init(
            selected: options.firstIndex(of: submittedAnswer) ?? -1,
            correct: correctOptionIndex ?? -1
        )
    }
}
```

- [ ] **Step 4: Run GREEN and full tests**

Expected: engine/state tests and full suite pass. Confirm `git diff -- WordingDailyApp/Models WordingDailyApp/Services/ProgressPersistenceService.swift` is empty.

- [ ] **Step 5: Commit**

```bash
git add WordingDailyApp/Services/QuizEngine.swift WordingDailyAppTests/QuizEngineTests.swift
git diff --check
git commit -m "feat: add quiz run state"
```

---

### Task 5: Replace daily answer leakage with Learn → mixed Quiz

**Files:**
- Create: `WordingDailyApp/Features/Practice/PracticeView.swift`
- Modify: `WordingDailyApp/Features/Today/TodayView.swift`
- Modify: `WordingDailyApp/Features/Review/ReviewView.swift`
- Modify: `WordingDailyApp/Resources/Localizable.xcstrings`
- Modify: `WordingDailyAppTests/LocalizationCoverageTests.swift`
- Modify: `WordingDailyApp.xcodeproj/project.pbxproj`
- Modify: `DESIGN.md`

**Interfaces:**
- Consumes: the daily `DailySession`, bundled seed, `QuizEngine`, persistence service, and review scheduler.
- Produces: `DailyPracticeView` with Learn, Quiz, and Result phases.

- [ ] **Step 1: Add failing localization/layout coverage**

Add budget entries for the compact actions `practice.learn.startQuiz`, `practice.submit`, `practice.retry.button`, and `practice.center.button`. Run `LocalizationCoverageTests`; expected RED because the catalog keys are missing.

- [ ] **Step 2: Build the daily flow with native controls**

Move the private practice UI out of `TodayView.swift` and implement:

```swift
struct DailyPracticeView: View {
    let session: DailySession
    let seedItems: [VocabularySeedItem]
    let supportLanguageCode: String
    let streakCount: Int
    let scheduledReviewCount: Int
    let dueReviewCount: Int
    let onReview: () -> Void
    let onUpdate: () -> Void
}
```

Behavior:

1. Learn only unanswered `DailySessionItem`s where `isReviewFill == false`.
2. Show upgraded expression, plain expression, localized meaning, example, and speaker control during Learn.
3. After explicit `Start quiz`, generate mixed questions from the session items using all same-level bundled seed items as distractor candidates.
4. Never show upgraded expression before an expression-choice or listening answer.
5. Start a native timer at 15 seconds for each question. Timeout records a wrong answer and reveals feedback but does not advance.
6. Choice taps or `Check answer` freeze the current question. `Next` persists only the first daily attempt, applies the existing review context, and advances.
7. Result shows the existing completion counts and a wrong list. `Retry wrong answers` reuses the same question modes, records no second SwiftData result, and may repeat until no wrong questions remain.
8. Preserve the Review CTA and Done action.
9. Replace `ReviewSessionView`'s answer-leaking seed quiz with the same runner, without a Learn phase. Review first attempts keep `.review` scheduling, while wrong-answer retry performs no second scheduler or `QuizResult` write.

- [ ] **Step 3: Add exact English and Traditional Chinese copy**

Use concise keys for Learn progress, four prompts, replay audio, spelling placeholder, check answer, time remaining/time up, correct answer, result, and retry. Keep `practice.next` as the only post-answer primary action.

- [ ] **Step 4: Update `DESIGN.md`**

Document that the Learn phase may show the answer, Quiz must not; add the four concrete modes, mixed mode, configurable Practice Center, timer behavior, and result-based wrong retry. Add a 2026-07-10 decision-log row noting the user-approved replacement of multiple-choice-only scope.

- [ ] **Step 5: Run GREEN and full tests**

Run localization tests, full tests, and `xcodebuild build`. Expected: no missing localizations, build success, explicit Next still present, no answer leakage in the question branch.

- [ ] **Step 6: Commit**

```bash
git add WordingDailyApp/Features/Practice/PracticeView.swift WordingDailyApp/Features/Today/TodayView.swift WordingDailyApp/Features/Review/ReviewView.swift WordingDailyApp/Resources/Localizable.xcstrings WordingDailyAppTests/LocalizationCoverageTests.swift WordingDailyApp.xcodeproj/project.pbxproj DESIGN.md
git diff --check
git commit -m "feat: replace daily flow with mixed quiz"
```

---

### Task 6: Add the configurable offline Practice Center

**Files:**
- Modify: `WordingDailyApp/Features/Practice/PracticeView.swift`
- Modify: `WordingDailyApp/Features/Today/TodayView.swift`
- Modify: `WordingDailyApp/Resources/Localizable.xcstrings`
- Modify: `WordingDailyAppTests/LocalizationCoverageTests.swift`

**Interfaces:**
- Consumes: `QuizEngine`, `PracticeConfiguration`, selected vocabulary level, local progress, and bundled seed.
- Produces: `PracticeCenterView` inside Today navigation.

- [ ] **Step 1: Add the setup/run UI**

```swift
struct PracticeCenterView: View {
    let seedItems: [VocabularySeedItem]
    let selectedLevel: VocabularyLevel
    let supportLanguageCode: String
}
```

Use native `Picker` controls for the five modes, counts `[5, 10, 15, 20]`, and seconds `[10, 15, 20, 30]`; use a native `Toggle` for wrong retry. Defaults are mixed, 10, 15, and retry on. Disable Start only if the selected-level local pool is empty.

- [ ] **Step 2: Reuse the quiz runner**

Select learned items first using local `WordProgress.firstSeenAt`, fill with unseen bundled items, then generate questions with the full selected-level local corpus as distractor candidates. Free-practice attempts and retries are in-memory only and must not mutate `DailySession`, `QuizResult`, `WordProgress`, streak, widget, or review schedule.

- [ ] **Step 3: Add a secondary Today entry**

Add one native secondary `NavigationLink` labeled `practice.center.button` below the daily summary. Keep the daily start/resume control as the only prominent button.

- [ ] **Step 4: Verify and commit**

Run localization tests, full tests, and build. Then:

```bash
git add WordingDailyApp/Features/Practice/PracticeView.swift WordingDailyApp/Features/Today/TodayView.swift WordingDailyApp/Resources/Localizable.xcstrings WordingDailyAppTests/LocalizationCoverageTests.swift
git diff --check
git commit -m "feat: add offline practice center"
```

---

### Task 7: Finish widget stale/schema/completed states

**Files:**
- Modify: `WordingDailyApp/Services/WidgetSnapshotWriter.swift`
- Modify: `WordingDailyWidget/WordingDailyWidget.swift`
- Modify: `WordingDailyApp/Resources/Localizable.xcstrings`
- Modify: `WordingDailyAppTests/WidgetSnapshotWriterTests.swift`
- Modify: `WordingDailyAppTests/LocalizationCoverageTests.swift`

- [ ] **Step 1: Write RED tests**

Add tests proving `snapshotOrFallback` rejects a mismatched `version` and a stored `dayKey` different from the requested current day.

- [ ] **Step 2: Add the shared guard**

```swift
func snapshotOrFallback(dayKey: String, generatedAt: Date = Date()) -> WidgetSnapshot {
    guard let snapshot = read(),
          snapshot.version == WidgetSnapshot.currentVersion,
          snapshot.dayKey == dayKey else {
        return .fallback(dayKey: dayKey, generatedAt: generatedAt)
    }
    return snapshot
}
```

- [ ] **Step 3: Render completion intentionally**

When `progressTotal > 0 && progressCompleted >= progressTotal`, medium widget shows localized `widget.completed` instead of the not-started empty text. Keep the existing deep link and small/medium families.

- [ ] **Step 4: Verify and commit**

Run widget/localization tests, full tests, and build; commit as `fix: handle stale and completed widgets`.

---

### Task 8: Route notification taps to Today

**Files:**
- Modify: `WordingDailyApp/Services/NotificationScheduler.swift`
- Modify: `WordingDailyApp/App/WordingDailyApp.swift`
- Modify: `WordingDailyApp/Features/Root/RootTabView.swift`
- Modify: `WordingDailyAppTests/NotificationSchedulerTests.swift`

- [ ] **Step 1: Write RED test**

Assert `dailyReminderRequest(...).content.userInfo` contains the internal URL `wordingdaily://today` under a Wording Daily-specific key.

- [ ] **Step 2: Add minimal native routing**

Set the URL in the notification content. Add one `UIApplicationDelegate`/`UNUserNotificationCenterDelegate` in `WordingDailyApp.swift` that posts the URL through `NotificationCenter` when the Wording Daily reminder is tapped. Have `RootTabView` feed that URL through its existing `route(_:)` method so an already-running app changes back to Today.

- [ ] **Step 3: Verify and commit**

Run notification/deep-link tests, full tests, and build; commit as `fix: route reminder taps to Today`.

---

### Task 9: Close seed and Library content gaps

**Files:**
- Modify: `WordingDailyApp/Features/Library/LibraryView.swift`
- Modify: `WordingDailyApp/Resources/Localizable.xcstrings`
- Modify: `WordingDailyAppTests/VocabularySeedValidationTests.swift`
- Modify: `WordingDailyAppTests/LocalizationCoverageTests.swift`

- [ ] **Step 1: Add missing-field regression**

Clone `SeedLoader.sampleItems.first`, blank one required field such as `upgradedExpression`, and assert `SeedValidator.validate` throws `.missingRequiredField(item.id)`.

- [ ] **Step 2: Show the existing English definition**

In Library detail, show `meaning["en"]` under localized `library.detail.definition`, then the support-language explanation. Do not add or rewrite seed content because all 90 bundled items already contain English meanings.

- [ ] **Step 3: Verify and commit**

Run seed/localization tests, full tests, and build; commit as `fix: complete seed and Library coverage`.

---

### Task 10: Design question-bank sources and level calibration

**Files:**
- Create: `docs/question-bank-sources-and-levels.md`
- Modify: `docs/content-review.md`

- [ ] **Step 1: Audit the current local bank**

Record per-level item counts, duplicate IDs, duplicate upgraded expressions, missing English/zh-Hant meanings, and whether every level can supply four unique options for every mode. The known starting point is 30 items per level and duplicate upgraded-expression text that must be deduplicated by the engine.

- [ ] **Step 2: Research source licensing from authoritative pages**

For every recommended candidate source, record owner, canonical URL, current license URL, redistribution/attribution requirements, commercial-use status, and whether derived Traditional Chinese content may be distributed. Prefer public-domain, CC0, compatible CC BY, or content authored for Wording Daily. Reject unknown, non-commercial-only, share-alike-incompatible, scraped, or account-gated sources.

- [ ] **Step 3: Define the three-level model**

Use the existing app enum and map it explicitly:

- `basic`: CEFR A1-A2; high-frequency, transparent everyday expressions and simple grammar.
- `intermediate`: CEFR B1-B2; collocations, phrasal language, register choice, and moderate idiomaticity.
- `advanced`: CEFR C1-C2; nuanced register, lower-frequency collocations, idioms, and context-sensitive usage.

Specify a scoring rubric for frequency, semantic transparency, grammar complexity, register, polysemy, and Taiwan-learner usefulness. Require human review for every final level assignment.

- [ ] **Step 4: Define provenance and import gates**

Specify a build-time provenance manifest separate from SwiftData with source/license/CEFR/reviewer fields. Define validation gates for required languages, natural Taiwanese Traditional Chinese, unique display answers, local same-level distractor availability, sort order, duplicate concepts, and attribution output. Runtime remains bundled and offline; no remote fetch or credential is introduced.

- [ ] **Step 5: Review and commit the design**

Check the document against `AGENTS.md`, `DESIGN.md`, and `docs/content-review.md`. Do not import a third-party word list in this task. Commit as `docs: design question bank sources and levels`.

---

### Task 11: Full QA and final review

**Files:**
- Modify only if a verified defect requires a focused fix and regression test.

- [ ] **Step 1: Fresh automated verification**

```bash
set -o pipefail
xcodebuild test -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=F6E47DF4-6357-4304-B68F-7EB4A203C1DC'
xcodebuild build -project WordingDailyApp.xcodeproj -scheme WordingDailyApp \
  -destination 'platform=iOS Simulator,id=F6E47DF4-6357-4304-B68F-7EB4A203C1DC'
git diff --check
```

- [ ] **Step 2: Simulator/manual checks**

Verify Today → Learn → all four mixed question types → timeout → explicit Next → result → wrong retry; Practice Center mode/count/timer combinations; zh-Hant and English; normal and accessibility Dynamic Type; VoiceOver labels; widget small/medium not-started/in-progress/completed; notification denied/skipped/authorized and tap routing.

- [ ] **Step 3: Whole-branch review**

Review from the branch merge base through HEAD for spec compliance, code quality, offline guarantees, persistence migration safety, and UI rule compliance. Fix every Critical/Important issue with a focused regression test and re-review.

- [ ] **Step 4: Completion audit**

Confirm `git status --short --branch`, list commits, and leave the isolated branch ready for the user. Do not push or merge unless the user asks.
