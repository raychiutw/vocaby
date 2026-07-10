# Agent Instructions - Wording Daily

## Product Scope

Wording Daily is a native iOS app for daily English vocabulary practice. It targets Traditional Chinese users first, with English vocabulary content and Traditional Chinese support.

V1 scope:

- SwiftUI native iOS app, iOS 17+.
- Fully local storage.
- No account, sign-in, backend, iCloud sync, or sync-ready scaffolding.
- Daily 10-item expression-upgrade practice.
- Review queue, Library, local notification, and minimal WidgetKit widget.
- App UI localizations: Traditional Chinese and English.

## Design Rules

Always read `DESIGN.md` before making UI, visual, copy, widget, notification, accessibility, or localization decisions.

Do not deviate from `DESIGN.md` without explicit user approval.

Key constraints:

- Use native SwiftUI controls before custom controls.
- Use `TabView` for Today, Review, Library.
- Do not build a custom tab bar.
- Keep the UI calm, Apple-native, and task-focused.
- No mascot, leaderboard, game economy, decorative gradients, or generic dashboard-card mosaic.
- Cards are only for actual interactions, such as practice cards or quiz options.

## Architecture Rules

- Keep bundled seed content DTOs separate from SwiftData `@Model` app state.
- Use small pure services for day keys, daily selection, review scheduling, seed loading/validation, notifications, and widget snapshots.
- The app is the only writer of the App Group widget snapshot.
- The widget reads a small derived snapshot, not SwiftData.
- Notification scheduling must use Wording Daily-specific request identifiers.
- Do not add network, repository, dependency-injection, or sync abstractions in v1.

## GStack Context

Primary plan artifact:

- `~/.gstack/projects/raychiutw-wording-daily/ray-main-design-20260710-110304.md`

Review artifacts:

- `~/.gstack/projects/raychiutw-wording-daily/ray-main-eng-review-test-plan-20260710-112635.md`
- `~/.gstack/projects/raychiutw-wording-daily/tasks-eng-review-20260710-112635.jsonl`
- `~/.gstack/projects/raychiutw-wording-daily/tasks-design-review-20260710-112635.jsonl`

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
