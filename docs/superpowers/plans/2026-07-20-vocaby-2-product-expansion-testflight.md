# Vocaby 2.0 Product Expansion and TestFlight Plan

**Goal:** Evolve Vocaby from a fixed ten-expression daily coach into a local-first English vocabulary and expression learning app, then release the completed experience to TestFlight.

**Release target:** `2.0.0`. This changes the product positioning, navigation, persisted review model, learning interaction, and progress experience.

**Reference:** LingoLearn supplies interaction and progress ideas. Vocaby keeps its reviewed offline vocabulary bank, Traditional Chinese-first content, existing expression-upgrade questions, local persistence, notification and widget architecture.

## Product contract

- Learn both vocabulary and practical expressions through one daily queue.
- Use five native tabs: Home, Learn, Practice, Progress, My.
- Let users set a daily goal from 10 to 100 in steps of 5; changes apply to the next uncreated daily session.
- Present two-sided learning cards with 3D flip, TTS, save, right/left/up swipe grading, and equivalent accessible buttons.
- Combine vocabulary meaning, spelling and listening questions with expression upgrade, expression meaning and expression spelling questions.
- Replace the fixed review ladder with SM-2 state persisted per item.
- Add 7/30-day charts, a 15-week heatmap, state distribution, achievements, restrained brand gradients, haptics, and achievement confetti.
- Keep all learning data local. The app remains the sole writer of the App Group widget snapshot.

## Interaction rules

- Right swipe means known (`q = 5`), left means unknown (`q = 1`), up means save and known (`q = 4`).
- Crossing a swipe threshold previews the semantic color, stamp and haptic; persistence happens once after the card exits.
- Bottom xmark, star and checkmark buttons perform exactly the same actions as swipes.
- Reduce Motion replaces 3D flip, card flight, shake and confetti with short opacity transitions.
- VoiceOver exposes front/back state, reveal action, pronunciation, save state and all grading actions without requiring gestures.
- Haptics accompany meaningful discrete actions. Continuous scrolling, text entry and system back navigation do not generate repeated haptics.
- Quiz timeout records an incorrect answer and freezes the question until the learner chooses Next.

## Data model

### Task 1: Persist SM-2 and daily analytics

**Files:** `Vocaby/Models/PersistenceModels.swift`, `Vocaby/Services/ReviewScheduler.swift`, `Vocaby/Services/ProgressPersistenceService.swift`, focused tests.

- Add `easeFactor`, `repetitionCount`, `intervalDays`, `nextReviewAt`, `lastQuality`, and mastery state to `WordProgress` with migration-safe defaults.
- Preserve existing `firstSeenAt`, `lastReviewedAt`, correct/wrong counts, saved state and stable item identity.
- Add per-day counters needed by charts: newly learned, reviewed, practiced, correct, incorrect and elapsed practice seconds.
- Map existing progress into SM-2 defaults without clearing due dates or learned state.
- Implement SM-2 as a pure function with quality clamping, EF floor 1.3, 1-day and 6-day first intervals, multiplied later intervals, same-day retry for `q < 3`, and mastery at four repetitions plus a 21-day interval.

**Acceptance:** migration preserves existing rows; eight SM-2 boundary tests pass; duplicate answer submission cannot apply SM-2 twice.

### Task 2: Unify vocabulary and expression content

**Files:** `Vocaby/Models/VocabularyModels.swift`, `Vocaby/Services/SeedLoader.swift`, vocabulary validation tests.

- Add an explicit learning-item kind while preserving compatibility with the existing 18,603-entry seed.
- Treat existing rich vocabulary entries as vocabulary items.
- Represent expression upgrades with plain expression, upgraded expression, localized explanation, example and translation.
- Use one stable item ID and one progress model for both kinds.
- Reject missing fields conditionally by item kind and continue enforcing uniqueness and reviewed Traditional Chinese content.

**Acceptance:** old seed loads unchanged; mixed fixture loads; duplicate IDs and incomplete kind-specific records fail validation.

## Preferences and services

### Task 3: Expand user preferences

**Files:** `Vocaby/Services/UserPreferencesStore.swift`, `Vocaby/Features/Settings/SettingsView.swift`, tests.

- Persist daily goal, autoplay pronunciation and appearance.
- Daily goal range is 10...100, step 5, default 10.
- Apply a changed goal only when creating a future session; never resize an in-progress session.
- Keep reminder, level and app-language behavior.

**Acceptance:** invalid stored values clamp safely; old preferences decode with defaults; setting changes survive relaunch.

### Task 4: Centralize haptic and speech behavior

**Files:** existing pronunciation code plus a small shared feedback service, focused tests where logic is pure.

- Reuse AVSpeechSynthesizer for `en-US` pronunciation and support autoplay on card appearance.
- Define selection, light, medium, success, warning and error feedback semantics.
- No-op safely when hardware or the execution environment cannot provide haptics.

## Navigation and screens

### Task 5: Replace root navigation

**Files:** `Vocaby/Features/Root/RootTabView.swift`, tab destinations, localization tests.

- Create Home, Learn, Practice, Progress and My tabs with SF Symbols.
- Put due-review count on Learn's tab badge.
- Route notification and widget deep links to the matching tab and destination.
- Keep Settings under My and available from the Home toolbar.

**Acceptance:** all five tabs remain reachable at accessibility sizes; deep links select the correct tab; tab bar does not minimize.

### Task 6: Redesign Home

**Files:** `Vocaby/Features/Today/TodayView.swift`, shared components, theme and localization.

- Add gradient circular daily progress with completed/goal labels.
- Show streak in the toolbar, an amber due-review pill, one primary resume action, quick review/test actions and a one-row daily summary.
- Preserve loading, insufficient-content, complete, no-review and database-error states.

**Acceptance:** no nested dashboard-card mosaic; every state has one clear next action; progress and summary values match persistence.

### Task 7: Build Learn queue and two-sided card

**Files:** new focused Learn views, shared vocabulary content, persistence services and UI tests.

- Build a queue of at most ten items per round from new and due content.
- Add front/back 3D flip with spring animation and Reduce Motion fallback.
- Add right/left/up drag thresholds, tilt, semantic gradient, stamps and single-fire haptic feedback.
- Add equivalent accessible xmark/star/checkmark buttons.
- Persist grade and save state immediately after each card commits.
- Show round completion with known-rate ring, known/saved/unknown counts and another-round action.

**Acceptance:** interruption after any committed card retains progress; sub-threshold drag writes nothing; VoiceOver completes the entire flow without drag gestures.

### Task 8: Integrate the quiz modes

**Files:** `Vocaby/Services/QuizEngine.swift`, `Vocaby/Features/Practice/PracticeView.swift`, tests.

- Support vocabulary meaning, vocabulary spelling, vocabulary listening, expression upgrade, expression meaning and expression spelling plus mixed mode.
- Configure 5/10/15/20 questions, unlimited or 10/15/20/30 seconds, item kind, level and source scope.
- Keep unique distractors and deterministic behavior under injected randomness.
- Add red final-30-percent timer state, success/check animation, wrong/shake feedback, correct-answer reveal and explicit Next.
- Extend results with accuracy ring, elapsed time, counts, replayable wrong list, retry wrong and new round.

**Acceptance:** mixed mode distributes all eligible modes; undersized pools degrade without duplicates or crashes; timeout is recorded exactly once.

### Task 9: Add Progress

**Files:** new Progress feature, analytics service, Swift Charts views and tests.

- Add 7/30-day learned-count LineMark plus AreaMark.
- Add a Monday-aligned, five-level, horizontally scrolling 15-week heatmap anchored to the latest week with today outline.
- Add SectorMark distribution for new, learning and mastered.
- Add vocabulary/expression filter and accessible chart summaries.
- Provide intentional no-data state.

**Acceptance:** timezone changes and DST do not shift day buckets; VoiceOver can obtain the same totals and trends without interpreting color.

### Task 10: Add achievements and celebration

**Files:** achievement model/service, Progress/My views, confetti component and tests.

- Add ten idempotent achievements: first study, 3/7/30-day streak, 100/500 learned, 100 mastered, 10 saved, perfect quiz and 50 items in one day.
- Present a badge wall with locked, unlocked and unlock-date states.
- On first unlock only, show badge bounce, 1.5-second Canvas confetti and success haptic.
- Reduce Motion uses fade and glow without particles.

**Acceptance:** repeated evaluation never re-presents or duplicates an achievement; thresholds are tested at below/equal/above boundaries.

### Task 11: Finish My and Settings

**Files:** `Vocaby/Features/Library/LibraryView.swift`, `Vocaby/Features/Settings/SettingsView.swift`, persistence reset service and tests.

- Preserve search, learned, saved and item detail.
- Add vocabulary/expression and level statistics.
- Add daily-goal slider, autoplay, appearance and reminder controls.
- Add two-stage destructive reset that clears learning progress and achievements while keeping seed content and preferences.

**Acceptance:** reset targets are explicit and tested; notification denial still links to system Settings.

## Design system and integrations

### Task 12: Update the design system

**Files:** `DESIGN.md`, `Vocaby/Design/Theme.swift`, named color assets and shared controls.

- Adopt sky `#0EA5E9` and teal `#14B8A6` brand gradient.
- Restrict gradients to primary actions, progress, selected chart emphasis and achievement celebration.
- Keep system semantic surfaces/text and separate correct/wrong/review colors.
- Document five-tab information architecture, motion, card gestures, haptic semantics, charts, achievements and accessibility.

### Task 13: Update Widget and notifications

**Files:** `Vocaby/Services/WidgetSnapshotWriter.swift`, `VocabyWidget/VocabyWidget.swift`, `Vocaby/Services/NotificationScheduler.swift`, tests.

- Write configurable goal, completed count, streak and next item into the derived snapshot.
- Keep app-only snapshot writes and fallback/version handling.
- Use the configured goal in calm localized notification copy without private answer details.

## Verification and release

### Task 14: Localization and automated verification

- Add Traditional Chinese and English strings for every new tab, mode, setting, state, achievement and accessibility label.
- Extend localization budget tests for tab labels, buttons, quiz choices, cards, widgets and settings.
- Run `git diff --check`.
- Run Swift tests on an iPhone 17 Pro simulator through `xcodebuild test`.
- Run `python3 -m unittest discover -s tools -p 'test_*.py'` with OpenCC available.
- Verify light/dark, normal/accessibility Dynamic Type, Reduce Motion, VoiceOver labels, notification states, small/medium widgets and cold-start migration.

### Task 15: Release 2.0.0 to TestFlight

- Set `VERSION` and every app/widget `MARKETING_VERSION` to `2.0.0`.
- Add the release entry to `CHANGELOG.md`.
- Commit only intentional product, test, documentation and version files.
- Push `main` and wait for CI success.
- Dispatch `.github/workflows/testflight.yml` on `main` with the available macOS runner.
- Use `GITHUB_RUN_ID` as the build number.
- Verify the workflow test and deploy jobs succeed and `wait_for_testflight.rb` observes version `2.0.0` with the matching build number in App Store Connect.
- Record the workflow URL, build number and processed TestFlight status in the release handoff.

## Completion gate

The project is complete only when every task acceptance condition is evidenced by code, tests, manual checks or App Store Connect state, the repository is clean on `main`, CI is green, and TestFlight shows the uploaded `2.0.0` build.
