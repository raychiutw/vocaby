# Manual Verification Checklist - Vocaby

Use this checklist before TestFlight builds and after changes touching UI, notifications, widgets, localization, or routing.

## Build Under Test

- Date:
- Commit:
- Xcode:
- iOS simulator/device:
- Tester:

Required setup:

- Start from a fresh install for first-run checks.
- Test at least one run in `zh-Hant` and one run in English.
- Test Dynamic Type at default size and one accessibility size.
- Capture screenshots for failed visual checks and for widget small/medium layouts.
- Complete `docs/content-review.md` before TestFlight if seed content changed.

## Notification Permission States

### Skipped Reminder

- [ ] Fresh install.
- [ ] Complete onboarding and choose Skip on reminder setup.
- [ ] Expected: onboarding completes, Today opens, reminders are off, no second prompt appears in the same flow.
- Evidence:

### Authorized Reminder

- [ ] Fresh install or reset notification permission.
- [ ] Complete onboarding, enable reminder, and allow system permission.
- [ ] Expected: Settings shows reminders enabled with the selected time.
- [ ] Expected: one pending request uses the Vocaby daily reminder identifier.
- [ ] Expected: tapping a delivered notification opens Today.
- Evidence:

### Denied Reminder

- [ ] Fresh install or reset notification permission.
- [ ] Complete onboarding, enable reminder, and deny system permission.
- [ ] Expected: onboarding still completes.
- [ ] Expected: reminder UI shows a denied/off state and offers a path to system Settings.
- [ ] Expected: no pending Vocaby reminder remains scheduled.
- Evidence:

### Reminder Reschedule And Off

- [ ] Enable reminders in Settings.
- [ ] Change the reminder time.
- [ ] Expected: old pending request is cancelled and replaced by one Vocaby reminder.
- [ ] Turn reminders off.
- [ ] Expected: pending and delivered Vocaby reminders are removed without affecting unrelated notifications.
- Evidence:

## Widget

### Empty Or Stale Snapshot

- [ ] Install app without starting today's session.
- [ ] Add small widget.
- [ ] Add medium widget.
- [ ] Expected small: app name and `0/10` progress render without clipped text.
- [ ] Expected medium: intentional empty state renders without clipped text.
- Evidence:

### Today Snapshot

- [ ] Start today's session.
- [ ] Answer at least one item.
- [ ] Return to Home Screen and wait for widget refresh if needed.
- [ ] Expected small: today's completed/total progress updates.
- [ ] Expected medium: one expression upgrade and progress are visible.
- Evidence:

### Widget Deep Links

- [ ] Tap small widget.
- [ ] Expected: app opens Today.
- [ ] From a test URL or widget-supported entry point, open `vocaby://review`.
- [ ] Expected: app opens Review.
- [ ] From a test URL or widget-supported entry point, open `vocaby://word/{id}` for a bundled seed item.
- [ ] Expected: app opens Library detail for that item.
- Evidence:

## Localization And Dynamic Type

### Traditional Chinese

- [ ] Set app/device language to Traditional Chinese.
- [ ] Run onboarding at default Dynamic Type.
- [ ] Run Today, Practice, Review, Library, Settings, and widget at default Dynamic Type.
- [ ] Repeat high-risk screens at an accessibility Dynamic Type size.
- [ ] Expected: primary buttons, tab labels, quiz options, Settings rows, and widget text do not clip or overlap.
- Evidence:

### English

- [ ] Set app/device language to English.
- [ ] Run onboarding at default Dynamic Type.
- [ ] Run Today, Practice, Review, Library, Settings, and widget at default Dynamic Type.
- [ ] Repeat high-risk screens at an accessibility Dynamic Type size.
- [ ] Expected: primary buttons, tab labels, quiz options, Settings rows, and widget text do not clip or overlap.
- Evidence:

## Core Flow Smoke Test

- [ ] Fresh install completes onboarding in under 60 seconds.
- [ ] Today has one obvious primary action.
- [ ] Start today's session.
- [ ] Answer at least one correct and one wrong quiz option.
- [ ] Expected: answered options freeze, correct/wrong states include icon or text reinforcement, and Next is explicit.
- [ ] Complete the session.
- [ ] Expected: completed items appear in Library learned list.
- [ ] Expected: wrong daily answers appear in same-day Review after completion.
- [ ] Save an item from Library detail.
- [ ] Expected: item appears in Saved.
- Evidence:

## Date And Seed Edge Cases

- [ ] Change device time zone before creating today's session.
- [ ] Expected: new local day key is used for new sessions.
- [ ] Move device date backward to an existing completed day.
- [ ] Expected: existing session is reused and no duplicate daily credit is granted.
- [ ] Use a level with fewer than 10 remaining unseen items.
- [ ] Expected: Today explains the smaller count and fills with due review items when available.
- Evidence:

## Sign-Off

- [ ] All required sections pass.
- [ ] Failed items have linked issue IDs or follow-up commits.
- [ ] TestFlight build is blocked if notification permission, widget layout, localization clipping, or core flow checks fail.

Reviewer:

Date:
