# My Vocabulary Progress Design

Date: 2026-07-15

## Goal

Rename the existing Library destination to My and show the learner's vocabulary coverage for all three vocabulary levels without removing the existing learned, saved, search, or detail features.

## Approved Product Decisions

- The third tab and its navigation title use `我的` in Traditional Chinese and `My` in English.
- The tab uses the native `person.crop.circle` SF Symbol.
- The tab bar remains fully visible while scrolling. On iOS 26 and later, the root `TabView` uses `.tabBarMinimizeBehavior(.never)`.
- A native summary section appears above the existing Library controls and list.
- The summary always shows Basic, Intermediate, and Advanced as three rows in that order.
- A vocabulary item is learned after at least one persisted `QuizResult` exists for its ID. Saved-only items do not count as learned.
- The existing learned/saved segmented control, search, list rows, deep links, and vocabulary detail screen remain available below the summary.

These decisions are an explicit user-approved update to the Library naming and tab-bar behavior currently documented in `DESIGN.md`.

## User Interface

The My screen remains a native SwiftUI `List`. Its first section contains one row for each `VocabularyLevel`:

1. Basic
2. Intermediate
3. Advanced

Each row shows the localized level name, a localized learned-versus-total count, and a linear progress indicator. The count uses monospaced digits so values remain aligned. The progress indicator has an accessible label and value; the interface does not rely on color alone.

The summary is not a card dashboard. It uses standard list sections, system typography, system spacing, and the existing accent color. Rows must support English, Traditional Chinese, dark mode, and accessibility Dynamic Type without truncating the count.

## Data and State

`LibraryService` gains a small pure summary operation. Inputs are the already-loaded `[VocabularySeedItem]` and `[QuizResult]`; the operation performs no fetch and owns no state.

For each level:

- `total` is the number of bundled seed items at that level for the current English content and Traditional Chinese support-language pair.
- `learned` is the number of distinct quiz-result item IDs that resolve to an eligible seed item at that level.
- Repeated quiz results for the same item count once.
- Quiz results whose item IDs no longer exist in the bundled seed are ignored.
- The learned value can never exceed total.

`LibraryView.refreshLibrary()` continues to load the seed and fetch progress and quiz rows. After those values update, the summary is derived from the same in-memory snapshot, so the counts and learned list share one definition and refresh together.

## Empty and Error States

- A level with no vocabulary displays `0 / 0` and zero progress without division by zero.
- A level with vocabulary but no learned items displays `0 / total`.
- Seed or SwiftData loading failures continue to use the existing localized Library load-error presentation; no partial or fabricated counts are shown.
- The summary remains visible when the learned or saved list is empty, so a new learner can see the available vocabulary totals.

## Localization and Accessibility

Add Traditional Chinese and English strings for My, the progress section, each level label where an existing reusable label is unavailable, and the learned-versus-total accessibility value. Existing Library-prefixed localization keys may remain internal implementation names; public copy changes to My.

VoiceOver reads the level followed by learned and total counts. Dynamic Type testing covers normal and accessibility sizes. The native progress view exposes the same numeric value as visible text.

## Testing

Focused service tests cover:

- totals for Basic, Intermediate, and Advanced;
- distinct learned counts from quiz results;
- duplicate quiz results counting once;
- saved-only progress not counting as learned;
- unknown quiz-result IDs being ignored;
- zero-item levels producing safe zero progress;
- content/support-language filtering matching the existing Library list.

UI/configuration verification covers:

- the tab and navigation title in Traditional Chinese and English;
- the `person.crop.circle` tab icon;
- `.tabBarMinimizeBehavior(.never)` on iOS 26 and later;
- all three summary rows at normal and accessibility Dynamic Type sizes;
- the existing learned/saved search and detail flows remaining functional.

The full Swift test suite and a release build must pass before completion.

## Scope Boundaries

- No new tab, dashboard, charting dependency, persistence model, migration, analytics, network call, or background job.
- No changes to how quiz results are stored.
- No per-level navigation or filtering in this change.
- No renaming of internal `LibraryView`, `LibraryService`, deep-link cases, or source directories solely for cosmetic consistency.
