# Apple Music Learning-First Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Vocaby screen content-first and Apple-native while redesigning vocabulary cards and quizzes for Traditional Chinese users learning English.

**Architecture:** Keep the existing native SwiftUI navigation and state flow. Simplify existing view bodies in place, reuse one learner-first presentation component across practice, feedback, and detail, and correct quiz-option generation at the existing `QuizEngine` choke point. A small shared presentation system is allowed when real reuse requires it; add no dependencies or speculative framework layers.

**Tech Stack:** Swift 6, SwiftUI, SwiftData, XCTest, Python `unittest`, Xcode/iOS 26 simulator, idb.

## Global Constraints

- iOS 17+ and native SwiftUI controls.
- Preserve Today, Review, and Library in the native `TabView`.
- No custom tab bar, account/profile, backend, sync, or new dependency. New shared presentation components are allowed when used by at least two screens.
- One prominent action per screen; cards only for actual learning or answer interactions.
- Traditional Chinese learner order: English expression, pronunciation/IPA, Chinese meaning, plain-to-natural comparison, bilingual example, optional details.
- Keep 44 pt targets, Dynamic Type, VoiceOver semantics, Dark Mode, and Traditional Chinese/English localization.
- Settings forms may use label/value rows; content and completion screens may not.

---

### Task 1: Authored quiz choices and untimed daily practice

**Files:**
- Modify: `VocabyTests/QuizEngineTests.swift`
- Modify: `Vocaby/Services/QuizEngine.swift`

**Interfaces:**
- Consumes: `VocabularySeedItem.quiz.options`, `VocabularyQuiz.correctOptionIndex`, `VocabularySense.meaning`.
- Produces: `QuizEngine.makeQuestions(...)` with authored options; `PracticeConfiguration.daily.timeLimitSeconds == 0` meaning untimed.

- [ ] **Step 1: Replace random-distractor expectations with failing authored-option tests**

Add tests that make the authored values visibly different from the candidate pool:

```swift
func testExpressionChoiceUsesAuthoredQuizOptions() throws {
    var items = makeItems(count: 5)
    items[0].quiz.options = ["authored-a", items[0].upgradedExpression, "authored-b", "authored-c"]
    items[0].quiz.correctOptionIndex = 1
    var random = IncrementingRandomNumberGenerator()

    let question = try XCTUnwrap(QuizEngine().makeQuestions(
        for: [items[0]], candidates: items, mode: .expressionChoice,
        supportLanguageCode: "zh-Hant", using: &random
    ).first)

    XCTAssertEqual(Set(question.options), Set(items[0].quiz.options))
    XCTAssertEqual(question.correctAnswer, items[0].upgradedExpression)
}

func testMeaningChoiceMapsAuthoredExpressionsToLocalizedMeanings() throws {
    var items = makeItems(count: 4)
    items[0].quiz.options = items.map(\.upgradedExpression)
    items[0].quiz.correctOptionIndex = 0
    var random = IncrementingRandomNumberGenerator()

    let question = try XCTUnwrap(QuizEngine().makeQuestions(
        for: [items[0]], candidates: items, mode: .meaningChoice,
        supportLanguageCode: "zh-Hant", using: &random
    ).first)

    XCTAssertEqual(Set(question.options), Set(items.map { $0.primarySense.meaning["zh-Hant"]! }))
}

func testDailyPracticeIsUntimed() {
    XCTAssertEqual(PracticeConfiguration.daily.timeLimitSeconds, 0)
}
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
xcodebuild test -project Vocaby.xcodeproj -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=Vocaby iOS26 Audit' \
  -only-testing:VocabyTests/QuizEngineTests
```

Expected: authored-option and daily-untimed assertions fail against current behavior.

- [ ] **Step 3: Route all choice modes through authored options**

Implement one private helper in `QuizEngine`:

```swift
private func authoredOptions(
    for item: VocabularySeedItem,
    candidates: [VocabularySeedItem],
    mode: PracticeMode,
    supportLanguageCode: String
) -> [String] {
    guard mode == .meaningChoice else { return item.quiz.options }

    let itemsByExpression = Dictionary(
        candidates.map { ($0.upgradedExpression.lowercased(), $0) },
        uniquingKeysWith: { first, _ in first }
    )
    return item.quiz.options.compactMap {
        itemsByExpression[$0.lowercased()].map {
            localizedMeaning(for: $0, supportLanguageCode: supportLanguageCode)
        }
    }
}
```

In `makeQuestions`, use this result, ensure the correct answer is present, deduplicate visible text, shuffle it with the injected generator, and never refill with arbitrary same-level words. Keep spelling options empty. Change `PracticeConfiguration.daily.timeLimitSeconds` from `15` to `0`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the Task 1 command again. Expected: all `QuizEngineTests` pass.

- [ ] **Step 5: Commit**

```bash
git add Vocaby/Services/QuizEngine.swift VocabyTests/QuizEngineTests.swift
git commit -m "fix: use authored quiz choices"
```

### Task 2: Add a source-level UI hierarchy regression guard

**Files:**
- Create: `tools/test_learning_ui_contract.py`

**Interfaces:**
- Consumes: production Swift source as text.
- Produces: executable guard for forbidden report-style patterns and required accessibility/input fixes.

- [ ] **Step 1: Write the failing contract test**

```python
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LearningUIContractTests(unittest.TestCase):
    def source(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_content_screens_do_not_use_report_style_labeled_content(self):
        for relative in (
            "Vocaby/Features/Today/TodayView.swift",
            "Vocaby/Features/Review/ReviewView.swift",
            "Vocaby/Features/Library/LibraryView.swift",
            "Vocaby/Features/Practice/PracticeView.swift",
            "Vocaby/Features/Shared/VocabularyEntryContentView.swift",
        ):
            with self.subTest(relative=relative):
                self.assertNotIn("LabeledContent(", self.source(relative))

    def test_settings_entry_uses_settings_semantics(self):
        source = self.source("Vocaby/Features/Shared/LearningChrome.swift")
        self.assertIn('Image(systemName: "gearshape")', source)
        self.assertNotIn("person.crop.circle", source)

    def test_spelling_uses_ascii_capable_keyboard(self):
        source = self.source("Vocaby/Features/Practice/PracticeView.swift")
        self.assertIn(".keyboardType(.asciiCapable)", source)

    def test_quiz_feedback_does_not_embed_full_dictionary(self):
        source = self.source("Vocaby/Features/Practice/PracticeView.swift")
        feedback = source[source.index("if let feedback = runState.currentFeedback"):]
        feedback = feedback[:feedback.index("private var resultContent")]
        self.assertNotIn("VocabularyEntryContentView(", feedback)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify RED**

Run: `python3 -m unittest tools.test_learning_ui_contract -v`

Expected: failures for current `LabeledContent`, profile icon, missing ASCII keyboard, and full feedback dictionary.

- [ ] **Step 3: Leave the test red until Tasks 3–6 complete**

Do not weaken the assertions. This single guard is the runnable check for the requested global hierarchy rules.

### Task 3: Simplify global chrome and onboarding

**Files:**
- Modify: `Vocaby/Features/Shared/LearningChrome.swift`
- Modify: `Vocaby/Features/Onboarding/OnboardingView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`

**Interfaces:**
- Consumes: existing settings sheet, level binding, reminder completion flow.
- Produces: semantically correct gear entry and non-redundant three-step onboarding.

- [ ] **Step 1: Change Settings entry semantics**

Replace `person.crop.circle` with `gearshape` and its accessibility key with a Settings-specific localized key.

- [ ] **Step 2: Remove duplicate onboarding labels**

Keep one visible level title. Render the three levels as native selectable rows with a trailing checkmark, each at least 44 pt. Keep the overall three-step flow and one prominent Continue action.

For reminder, render a compact row equivalent to:

```swift
DatePicker("onboarding.reminder.everyDay", selection: $reminderTime, displayedComponents: .hourAndMinute)
```

Remove the repeated section header/footer. Keep Enable prominent and Skip plain.

- [ ] **Step 3: Add Traditional Chinese and English strings**

Add only the new Settings accessibility label and compact reminder copy. Remove no localization key until all references are gone.

- [ ] **Step 4: Run build and localization coverage**

```bash
xcodebuild test -project Vocaby.xcodeproj -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=Vocaby iOS26 Audit' \
  -only-testing:VocabyTests/LocalizationCoverageTests
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Vocaby/Features/Shared/LearningChrome.swift \
  Vocaby/Features/Onboarding/OnboardingView.swift Vocaby/Resources/Localizable.xcstrings
git commit -m "refactor: simplify onboarding hierarchy"
```

### Task 4: Make Today and Review task-focused

**Files:**
- Modify: `Vocaby/Features/Today/TodayView.swift`
- Modify: `Vocaby/Features/Review/ReviewView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`

**Interfaces:**
- Consumes: existing daily progress, due items, navigation destinations, and refresh actions.
- Produces: one-action Today; truthful empty/non-empty Review states.

- [ ] **Step 1: Reduce Today to actionable state**

Delete `DailyFocusCover`, duplicate primary-action text, empty preview row, and all four vocabulary-progress `LabeledContent` rows. Keep:

```text
completed/10
ProgressView
[Start or Continue]
```

Conditionally show due review only when nonzero and a next-item preview only when it exists. Keep free practice as a compact navigation row.

- [ ] **Step 2: Split Review empty and non-empty presentation**

When `dueItems.isEmpty`, show a native content-unavailable state with “今天不用複習” and one short next-step description. Do not render artwork, count, duration, or a disabled button.

When non-empty, show a compact sentence using the real count and computed duration, followed by one Start button.

- [ ] **Step 3: Update localization**

Add concise empty-state and count-duration formats in both locales. Reuse existing Start/Continue keys where wording remains accurate.

- [ ] **Step 4: Run the red UI contract to confirm remaining failures are scoped**

Run: `python3 -m unittest tools.test_learning_ui_contract -v`

Expected: Today/Review no longer fail the `LabeledContent` assertion; other pending screens still fail.

- [ ] **Step 5: Commit**

```bash
git add Vocaby/Features/Today/TodayView.swift Vocaby/Features/Review/ReviewView.swift \
  Vocaby/Resources/Localizable.xcstrings
git commit -m "refactor: focus daily and review screens"
```

### Task 5: Build the learner-first vocabulary presentation

**Files:**
- Modify: `Vocaby/Features/Shared/VocabularyEntryContentView.swift`
- Modify: `Vocaby/Features/Library/LibraryView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`

**Interfaces:**
- Consumes: selected `VocabularySense`, pronunciation, localized meaning, bilingual example, progress.
- Produces: one shared learner-first content flow for practice and Library detail.

- [ ] **Step 1: Reorder the shared vocabulary content**

Render the selected sense in this order without field labels:

```swift
VStack(alignment: .leading, spacing: 16) {
    expressionAndPronunciation
    Text(localized(sense.meaning))
        .font(.title3.weight(.semibold))
    Text("\(item.plainExpression)  →  \(item.upgradedExpression)")
        .font(.body)
    exampleAndTranslation
    additionalDetailsDisclosure
}
```

Keep IPA and part of speech inline with the expression. Put English definition and additional senses in one `DisclosureGroup`. Do not introduce a new presentation model.

- [ ] **Step 2: Simplify Library root and rows**

Remove `LibraryCover`. Hide `.searchable` when both learned and saved content are empty. Keep the segmented picker. Use `ContentUnavailableView` for empty states. Row subtitle is plain expression or localized meaning; do not repeat current scope status.

- [ ] **Step 3: Simplify Library detail**

Move saved state to a toolbar bookmark button. Do not repeat the upgraded expression inside content if it is the navigation title. Condense review state into one localized sentence and put any extra history under disclosure.

- [ ] **Step 4: Run the UI contract**

Run: `python3 -m unittest tools.test_learning_ui_contract -v`

Expected: shared vocabulary and Library no longer fail `LabeledContent`; Practice still fails until Task 6.

- [ ] **Step 5: Commit**

```bash
git add Vocaby/Features/Shared/VocabularyEntryContentView.swift \
  Vocaby/Features/Library/LibraryView.swift Vocaby/Resources/Localizable.xcstrings
git commit -m "refactor: prioritize learner vocabulary content"
```

### Task 6: Redesign quiz, feedback, free-practice setup, and completion

**Files:**
- Modify: `Vocaby/Features/Practice/PracticeView.swift`
- Modify: `Vocaby/Features/Review/ReviewView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`

**Interfaces:**
- Consumes: `QuizRunState`, `PracticeConfiguration`, `QuizQuestion`, shared pronunciation speaker.
- Produces: focused quiz flow, compact feedback, ASCII spelling input, concise completion.

- [ ] **Step 1: Make timer optional through the existing integer**

Treat `timeLimitSeconds == 0` as untimed: do not render `TimelineView`, do not call timeout, and do not reset a meaningful deadline. For timed runs show only a compact clock symbol and `0:12`-style value with an accessibility label.

- [ ] **Step 2: Flatten question and answer layout**

Keep one question section. Render answer options as plain full-width rows; neutral before submission, semantic green/red only afterward. Remove the pre-answer accent tint from every option.

For spelling add:

```swift
.keyboardType(.asciiCapable)
.textInputAutocapitalization(.never)
.autocorrectionDisabled()
```

- [ ] **Step 3: Replace full dictionary feedback**

Delete the feedback-path `VocabularyEntryContentView`. Correct feedback is a short confirmation. Wrong/timeout feedback shows:

```text
correct English expression
Traditional Chinese meaning
English example
Traditional Chinese translation
```

Keep the existing bottom Next action, but give the List enough safe-area content spacing so it never obscures feedback.

- [ ] **Step 4: Simplify free-practice setup and completion**

Remove the read-only level `LabeledContent`. Keep optional mode/count/timer/retry controls in one compact adjustment section and one Start action. Replace four completion label/value rows with one summary sentence; only show scheduled review when nonzero.

- [ ] **Step 5: Make Review completion concise**

Render one completion message and one Done action; do not add a report summary.

- [ ] **Step 6: Run UI contract and localization tests; verify GREEN**

```bash
python3 -m unittest tools.test_learning_ui_contract -v
xcodebuild test -project Vocaby.xcodeproj -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=Vocaby iOS26 Audit' \
  -only-testing:VocabyTests/LocalizationCoverageTests
```

Expected: both commands pass.

- [ ] **Step 7: Commit**

```bash
git add tools/test_learning_ui_contract.py Vocaby/Features/Practice/PracticeView.swift \
  Vocaby/Features/Review/ReviewView.swift Vocaby/Resources/Localizable.xcstrings
git commit -m "refactor: redesign learner quiz flow"
```

### Task 7: Full automated verification and source audit

**Files:**
- Modify only if a test reveals an in-scope regression.

- [ ] **Step 1: Run repository checks**

```bash
python3 -m unittest discover -s tools -p 'test_*.py' -v
xcodebuild test -project Vocaby.xcodeproj -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=Vocaby iOS26 Audit'
git diff --check
```

Expected: all tests pass and `git diff --check` is silent.

- [ ] **Step 2: Scan forbidden patterns**

```bash
rg -n 'LabeledContent\(' Vocaby/Features
rg -n 'person\.crop\.circle|DailyFocusCover|ReviewCover|LibraryCover' Vocaby/Features
```

Expected: `LabeledContent` only in `SettingsView` or a justified editable settings form; no profile icon or fixed cover usage in content screens.

- [ ] **Step 3: Build the exact audit app**

```bash
xcodebuild -project Vocaby.xcodeproj -scheme Vocaby \
  -destination 'platform=iOS Simulator,name=Vocaby iOS26 Audit' \
  -derivedDataPath /tmp/VocabyDesignAudit CODE_SIGNING_ALLOWED=NO build
xcrun simctl install booted /tmp/VocabyDesignAudit/Build/Products/Debug-iphonesimulator/Vocaby.app
xcrun simctl launch booted com.raychiutw.Vocaby
```

Expected: build succeeds, install succeeds, app launches.

### Task 8: Page-by-page visual and accessibility acceptance

**Files:**
- Update: `/Users/ray/.gstack/projects/raychiutw-vocaby/ios-design-review-2026-07-15.md`
- Create screenshots under: `/Users/ray/.gstack/projects/raychiutw-vocaby/designs/ios-design-audit-20260715/after/`

- [ ] **Step 1: Capture every required state**

Capture welcome, level, reminder, Today, empty/non-empty Review, empty/non-empty Library, detail, free-practice setup, learner card, four quiz modes, correct/wrong/timeout, completion, and Settings.

- [ ] **Step 2: Repeat critical screens in Dark Mode and accessibility Dynamic Type**

At minimum: Today, learner card, choice quiz, spelling keyboard, wrong feedback, Library detail.

- [ ] **Step 3: Verify interaction semantics**

Use idb accessibility hierarchy and manual interaction to confirm reading order, 44 pt targets, gear semantics, ASCII keyboard, one prominent action, and no content hidden by keyboard/tab/safe-area actions.

- [ ] **Step 4: Update the audit report with before/after evidence and final scores**

Do not claim compliance for a state without a current screenshot or accessibility hierarchy.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test: verify learning-first interface"
git status --short --branch
```

Expected: clean worktree on `main`, ahead of origin only by intentional commits.
