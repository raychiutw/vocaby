# Design System - Wording Daily

## Product Context

- **What this is:** Wording Daily is a native iOS app for daily English vocabulary practice. Its core loop is a 10-item daily expression-upgrade session, quick quiz, lightweight review, and habit support through reminders and a small widget.
- **Who it is for:** Traditional Chinese users learning practical English expressions. The first content pair is English with Traditional Chinese support.
- **Project type:** Native iOS utility and learning app, not a marketing site, course platform, game, or dictionary.
- **Memorable thing:** It should feel like a calm daily expression coach: open it, finish today's 10 upgrades, leave with phrases you can use tomorrow.

## Design Thesis

Wording Daily should feel native, quiet, and habit-forming. It borrows the discipline of Apple Fitness' daily completion loop, but without gamified pressure. The app is a compact study surface, not a dashboard and not a card gallery.

## Aesthetic Direction

- **Direction:** Calm native study utility.
- **Decoration level:** Minimal. Typography, spacing, progress, and native materials do the work.
- **Mood:** Focused, warm, and low-friction. The interface should disappear quickly so the user can practice.
- **Energy:** Daily momentum without mascot, leaderboard, confetti-heavy reward, or streak anxiety.

## Platform Rules

- Use SwiftUI-native components before custom controls.
- Use `TabView` for the three top-level areas: Today, Review, Library.
- Use a `NavigationStack` inside each tab for detail flows.
- Use toolbar buttons for settings and contextual actions. Do not put action buttons inside the tab bar.
- Use sheets for Settings and focused setup flows.
- Use system permission UI for notifications, with a native fallback state when permission is denied.
- The widget is glanceable only. It does not contain practice interactions in v1.

## Typography

Use Apple platform typography. Do not import web fonts into the app.

- **Large title:** SwiftUI `.largeTitle`, semibold where hierarchy needs weight.
- **Screen title:** `.title2` or `.title3`, semibold.
- **Section title:** `.headline`.
- **Primary learning expression:** `.title2`, semibold, supports Dynamic Type.
- **Plain expression / supporting explanation:** `.body`.
- **Quiz options:** `.body`, medium where needed.
- **Metadata and helper text:** `.subheadline` or `.footnote`.
- **Numbers and progress:** use monospaced digits where alignment matters, for example `.monospacedDigit()`.

Rules:

- Preserve Dynamic Type. Do not hard-code font sizes for core learning content.
- Use `lineLimit` only when the full content is available in a detail view.
- Use SF Symbols for toolbar/tab icons. Do not draw custom icons for standard actions.
- Traditional Chinese strings are allowed to be longer than English. Layout must absorb longer labels without clipping at normal and accessibility text sizes.

## Color

Use system colors for surfaces and text, plus one restrained accent. Define these as named color assets so light and dark appearances can be tuned.

| Token | Light | Dark | Usage |
|------|-------|------|-------|
| `Accent` | `#0A7A6B` | `#4DD4BE` | Primary action, selected tab, progress fill |
| `ProminentInk` | `#FFFFFF` | `#000000` | Appearance-aware label color on prominent tinted actions |
| `AccentSoft` | `#DDF4EF` | `#123A35` | Subtle selected states and progress background |
| `FocusInk` | `#17211F` | `#F3F7F5` | Primary text when a custom token is needed |
| `MutedInk` | `#60716B` | `#A9B7B2` | Secondary text |
| `ReviewAmber` | `#AA6400` | `#FFB84D` | Due review count and review emphasis |
| `WrongRed` | `#B42318` | `#FF6B61` | Wrong answer state |
| `CorrectGreen` | `#157F3B` | `#60D394` | Correct answer state |

System colors:

- Primary background: `Color(.systemBackground)`.
- Grouped areas: `Color(.secondarySystemGroupedBackground)` inside `Color(.systemGroupedBackground)`.
- Separator: `Color(.separator)`.
- Labels: `Color(.label)`, `Color(.secondaryLabel)`, `Color(.tertiaryLabel)`.

Rules:

- Accent is meaningful, not decorative. Use it for progress, primary actions, and selected state.
- Avoid purple/blue gradients, colorful decorative blobs, and heavy shadow palettes.
- Dark mode must be designed with system colors first, not by inverting light mode.
- Semantic answer colors always include text or icon reinforcement. Never rely on color alone.

## Layout

- **Approach:** Native grouped layout with one primary task per screen.
- **Base spacing:** 8 pt.
- **Spacing scale:** 4, 8, 12, 16, 24, 32, 48.
- **Minimum touch target:** 44 x 44 pt.
- **Primary content width:** Full width on iPhone with standard margins; max 640 pt centered on iPad.
- **Screen margins:** 16 pt compact, 24 pt regular.
- **Cards:** Use cards only when the card is the interaction, such as a practice card or quiz option group. Do not make every section a card.
- **Corner radius:** 8 pt for compact controls, 12 pt for practice cards, 16 pt only for large focused surfaces.

## Navigation Architecture

```
App
├── Onboarding
│   ├── Welcome
│   ├── Level choice
│   └── Reminder setup
└── Main TabView
    ├── Today
    │   ├── Today overview
    │   ├── Practice session
    │   ├── Completion summary
    │   └── Settings sheet
    ├── Review
    │   ├── Due queue
    │   └── Review session
    └── Library
        ├── Learned list
        ├── Saved list
        ├── Search results
        └── Word detail
```

Tab labels:

- Today: `calendar` or `sun.max`.
- Review: `arrow.triangle.2.circlepath` or `clock.arrow.circlepath`.
- Library: `books.vertical` or `book.closed`.

Do not add a Progress tab in v1. Progress belongs inside Today and Library.

## Screen Hierarchy

### Onboarding

Onboarding is short and task-specific. Each screen has one primary action.

1. Welcome: app name, one sentence of value, primary action to continue.
2. Level choice: Basic, Intermediate, Advanced as native selection rows or buttons; primary action stays disabled until a level is selected.
3. Reminder setup: time picker plus primary action to enable reminders; secondary action to skip.
4. Permission denied or skipped: show reminders as off, explain that practice still works, and offer a Settings path later from the Settings sheet.

Do not add a language picker in onboarding v1. App language follows system/app language settings.

### Today

1. Date and streak/progress summary.
2. One primary action: start or resume today's session.
3. Due review count, if relevant.
4. Preview of one expression upgrade, if the session exists.
5. Small settings entry in the toolbar, not inline chrome.

Empty states:

- No items due and daily session complete: "今天完成了" plus a subtle next-review hint.
- Seed exhausted: explain that fewer than 10 items are available and show the exact count.
- No notification permission: reminder UI remains usable but shows a disabled state and a path to Settings.

### Practice Session

1. Progress indicator, for example `3/10`.
2. Upgraded expression as the main object.
3. Plain expression and Traditional Chinese explanation.
4. Example sentence.
5. Pronunciation button.
6. Quiz choices.

Rules:

- Learn may show the upgraded expression and supporting answer content. Quiz must not reveal a standalone correct answer before the learner responds.
- Quiz supports four concrete modes: choose the upgraded expression from a plain-expression prompt, choose the meaning from an upgraded-expression prompt, listen and choose the expression, and spell the upgraded expression from its localized meaning. Mixed mode distributes those four modes across a run.
- Quiz timers use 10, 15, 20, or 30 seconds. Expiry freezes the question with time-up feedback; it does not advance automatically.
- The practice card may be a focused card surface. The whole screen must not become nested cards.
- Quiz choices must have stable height and clear selected/correct/wrong states.
- The pronunciation button uses a speaker SF Symbol with a text label for clarity.
- After the user answers, freeze all quiz options, reveal correct/wrong state, and show a primary `Next` action. Do not auto-advance in v1.
- If the selected answer is wrong, keep the correct answer visible before the user moves on.
- Results list the most recent round's wrong answers. When retry is enabled, retry only those questions while preserving their modes.

Practice Center remains a destination under Today, not a fourth tab.

### Review

1. Due count.
2. Start review action.
3. Ordered due list preview when helpful.
4. Empty state when nothing is due.

### Library

1. Search.
2. Segmented control for Learned and Saved.
3. List rows with upgraded expression, plain expression, and small status metadata.
4. Word detail with save toggle and review stats.

## Components

### Primary Button

- Native prominent button style.
- Accent fill.
- Minimum height 44 pt.
- One action per screen should look primary.

### Secondary Button

- Native bordered or plain button depending on context.
- Use for skip, change reminder, or view detail.

### Practice Card

- Surface: secondary grouped background.
- Radius: 12 pt.
- Padding: 20 pt.
- Content order: upgraded expression, plain expression, localized meaning, example.
- Avoid decorative icons unless they clarify pronunciation, save state, or answer state.

### Quiz Option

- Full-width row button.
- Stable height, wraps to two lines when needed.
- Selected state uses `AccentSoft`.
- Correct state uses `CorrectGreen` plus checkmark.
- Wrong state uses `WrongRed` plus xmark.

### Progress

- Prefer compact progress bars and numeric labels.
- Use monospaced digits for `6/10`.
- Streak is secondary. Do not make streak visually louder than today's practice action.

## Widget Design

Widget v1 is glanceable.

- Small widget: today's progress and app name.
- Medium widget: one daily expression upgrade plus progress.
- Use standard widget margins.
- Keep text short enough for Traditional Chinese and English.
- No buttons except system-supported deep link behavior.
- Empty/stale snapshot state must look intentional, for example "今天還沒開始".

## Notification Design

- Copy is short and non-sensitive. Do not put private progress details in notification text.
- Traditional Chinese default tone: calm prompt, not guilt.
- Example zh-Hant: "今天的 10 個表達準備好了".
- Example English: "Today's 10 expression upgrades are ready."
- Tapping a notification opens Today.

## Motion

- **Approach:** Minimal functional.
- Use native navigation and sheet transitions.
- Practice card transitions can crossfade or slide lightly when moving to the next item.
- Correct/wrong feedback should appear quickly, 150-250 ms.
- Respect Reduce Motion.
- Avoid confetti in v1. Completion can use a subtle checkmark and progress completion state.

## Accessibility

- VoiceOver labels are required for pronunciation, save, quiz options, progress, and widget deep links.
- Every tappable control is at least 44 x 44 pt.
- All body text contrast must meet WCAG AA.
- Do not rely on color alone for correct/wrong/saved states.
- Test normal Dynamic Type and accessibility sizes.
- The practice flow must remain usable one-handed on iPhone.

## Localization

- App UI localizations: Traditional Chinese and English.
- Vocabulary content language pair is separate from app UI language.
- Avoid field names and UI labels that assume only English/Chinese forever.
- Do not put full labels only in placeholders.
- Favor concise labels that survive translation.
- Pseudo-long string QA must include primary buttons, quiz option rows, medium widget text, tab labels, notification text, and Settings rows.
- Seed content QA must reject machine-translated Traditional Chinese, unnatural Taiwanese phrasing, obscure thesaurus English, and distractors that are too obviously wrong.

## Copy Voice

- Calm, direct, and useful.
- Prefer "Start today's 10" over motivational slogans.
- Prefer "Review due words" over "Keep your streak alive".
- Use Traditional Chinese that feels native to Taiwan, not machine-translated.
- Avoid pressure language, guilt, and inflated achievement copy.

## Do / Don't

Do:

- Use native SwiftUI controls and spacing.
- Make Today the obvious first screen.
- Keep tabs stable and simple.
- Make the practice card the strongest visual object.
- Show all empty states with a next action or useful explanation.

Don't:

- Build a custom tab bar.
- Add mascots, badges, leaderboards, or Duolingo-style reward layers in v1.
- Use a generic dashboard-card mosaic.
- Use decorative gradients, blobs, or stock illustrations.
- Hide important labels behind icons only.
- Let widget or notification copy expose sensitive learning data.

## Implementation Notes

- Create named color assets for the tokens above.
- Prefer SwiftUI text styles over fixed font sizes.
- Keep shared widget data in an App Group snapshot, not in SwiftData.
- The app is the only writer of widget snapshots.
- Use previews for light mode, dark mode, zh-Hant, English, and accessibility text sizes.
- UI tests should include at least Today, Practice, Review empty state, Library empty state, and Settings sheet.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-10 | Initial design system created | Established the native iOS visual source of truth before plan design review. |
| 2026-07-10 | Use native TabView for Today, Review, Library | Current iOS patterns support top-level tabs when they represent stable app areas. |
| 2026-07-10 | Use Apple platform typography instead of imported fonts | Wording Daily is a native iOS app; platform text styles give Dynamic Type, localization, and accessibility behavior by default. |
| 2026-07-10 | Use restrained teal accent with system surfaces | Keeps the app calm and learning-focused while avoiding generic purple/blue AI palettes. |
| 2026-07-10 | Require explicit answered state with Next action | Prevents quiz auto-advance from hiding feedback before the learner can read it. |
| 2026-07-10 | Replace the multiple-choice-only quiz scope with four concrete modes plus mixed | The user approved expression, meaning, listening, and spelling practice with a mixed option. |
