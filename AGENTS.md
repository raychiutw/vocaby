# Agent Instructions - Vocaby

## Product Scope

Vocaby is a local-first native iOS app for English vocabulary and practical-expression learning. It targets Traditional Chinese users first, with English content and Traditional Chinese support.

V1 scope:

- SwiftUI native iOS app, iOS 17+.
- Fully local storage.
- No account, sign-in, backend, iCloud sync, or sync-ready scaffolding.
- Configurable 10-100-item daily vocabulary and expression learning.
- SM-2 review, quizzes, progress charts, achievements, local notification, and WidgetKit widgets.
- App UI localizations: Traditional Chinese and English.

## Design Rules

Always read `DESIGN.md` before making UI, visual, copy, widget, notification, accessibility, or localization decisions.

Do not deviate from `DESIGN.md` without explicit user approval.

Key constraints:

- Use native SwiftUI controls before custom controls.
- Use `TabView` for Home, Learn, Practice, Progress, My.
- Do not build a custom tab bar.
- Keep the UI Apple-native, energetic, and task-focused.
- No mascot, leaderboard, game economy, or generic dashboard-card mosaic. Restrict brand gradients and celebration to the uses defined in `DESIGN.md`.
- Cards are only for actual interactions, such as practice cards or quiz options.

## Architecture Rules

- Keep bundled seed content DTOs separate from SwiftData `@Model` app state.
- Use small pure services for day keys, daily selection, review scheduling, seed loading/validation, notifications, and widget snapshots.
- The app is the only writer of the App Group widget snapshot.
- The widget reads a small derived snapshot, not SwiftData.
- Notification scheduling must use Vocaby-specific request identifiers.
- Do not add network, repository, dependency-injection, or sync abstractions in v1.

## GStack Context

Primary plan artifact:

- `~/.gstack/projects/raychiutw-vocaby/ray-main-design-20260710-110304.md`

Review artifacts:

- `~/.gstack/projects/raychiutw-vocaby/ray-main-eng-review-test-plan-20260710-112635.md`
- `~/.gstack/projects/raychiutw-vocaby/tasks-eng-review-20260710-112635.jsonl`
- `~/.gstack/projects/raychiutw-vocaby/tasks-design-review-20260710-112635.jsonl`

The current plan review state is cleared for planning:

- Eng Review: clear.
- Design Review: clear.
- No unresolved decisions.

## Testing Expectations

When app code exists, add focused tests for:

- `DayKeyService`: DST, timezone changes, backward date, missed-day streak.
- Daily selection: level filtering, sort order, seed exhaustion, due review fill.
- Review scheduling: correct-count ladder, wrong-answer behavior, mastered exclusion.
- Seed validation: duplicate IDs, invalid correct option, missing fields, sort order.
- Widget snapshot encoding and fallback state.
- Notification scheduler identifiers and cancellation behavior.

Manual or UI checks must cover:

- Notification permission denied/skipped/authorized states.
- Widget small and medium layouts.
- Traditional Chinese and English strings at normal and accessibility Dynamic Type sizes.

## Git Rules

- Keep changes scoped to the current task.
- Do not revert user changes.
- Stage only intentional files.
- Before commit, run `git diff --check`.
- If the user asks `commit + push`, finish both steps and verify `git status --short --branch`.

## Versioning and Releases

- `1.0.0` to `1.0.1`: bug fixes, small visual changes, and App Icon updates.
- `1.0.0` to `1.1.0`: new backward-compatible functionality.
- Increase the major version only for breaking changes after `1.0.0`.
- Keep `VERSION` and every app/widget `MARKETING_VERSION` equal.
- For a formal release, update `VERSION`, `CHANGELOG.md`, and all `MARKETING_VERSION` values, then create the matching `vX.Y.Z` tag.
- Manual TestFlight uploads keep the public version and override the build number with `GITHUB_RUN_ID`.
