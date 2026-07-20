# Design System - Vocaby

## Product Context

- **What this is:** Vocaby is a local-first native iOS app for learning English vocabulary and practical expression upgrades. Its core loop combines a configurable daily learning queue, two-sided study cards, quizzes, SM-2 review, progress tracking, achievements, reminders, and widgets.
- **Who it is for:** Traditional Chinese users learning practical English expressions. The first content pair is English with Traditional Chinese support.
- **Project type:** Native iOS utility and learning app, not a marketing site, course platform, game, or dictionary.
- **Memorable thing:** It turns individual words into usable English: learn the word, see how it upgrades an expression, practise it, and meet it again at the right time.

## Design Thesis

Vocaby should feel native, energetic, and habit-forming without becoming noisy. Brand gradients, tactile card gestures, progress charts, and achievements make progress visible; content and the next learning action remain more prominent than decoration.

## Aesthetic Direction

- **Direction:** Native learning companion with tactile study cards and visible progress.
- **Decoration level:** Focused. Gradients and celebration are reserved for progress, primary actions, and first-time achievement unlocks.
- **Mood:** Clear, encouraging, and low-friction.
- **Energy:** Daily momentum through goals, streaks, charts, badges, and brief celebrations without leaderboards, currencies, or guilt.

## Platform Rules

- Use SwiftUI-native components before custom controls.
- Use `TabView` for the five top-level areas: Home, Learn, Practice, Progress, My.
- The tab bar remains fully visible while scrolling; on iOS 26 and later use `.tabBarMinimizeBehavior(.never)`.
- Use a `NavigationStack` inside each tab for detail flows.
- Use toolbar buttons for settings and contextual actions. Do not put action buttons inside the tab bar.
- Keep Settings under My and expose a toolbar shortcut from Home. Use sheets for focused setup and confirmation flows.
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
| `Accent` | `#0EA5E9` | `#38BDF8` | Primary action, selected tab, progress fill |
| `BrandTeal` | `#14B8A6` | `#2DD4BF` | Brand gradient endpoint and secondary chart emphasis |
| `ProminentInk` | `#FFFFFF` | `#FFFFFF` | Label color on prominent gradient actions |
| `AccentSoft` | `#E0F2FE` | `#0C3445` | Subtle selected states and progress background |
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

- Use the Accent-to-BrandTeal gradient only for primary actions, progress, selected chart emphasis, and achievement celebration.
- Avoid decorative blobs, gradients on ordinary list rows, and heavy shadow palettes.
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
│   ├── Level and daily-goal choice
│   └── Reminder setup
└── Main TabView
    ├── Home
    │   ├── Daily overview and summary
    │   └── Quick review/test routes
    ├── Learn
    │   ├── Daily and due queues
    │   ├── Two-sided card session
    │   └── Round summary
    ├── Practice
    │   ├── Quiz configuration
    │   ├── Quiz run
    │   └── Results and wrong-answer retry
    ├── Progress
    │   ├── 7/30-day trend
    │   ├── 15-week heatmap
    │   ├── learning-state distribution
    │   └── Achievement wall
    └── My
        ├── Search and vocabulary/expression filters
        ├── Learned and saved lists
        ├── Item detail
        └── Settings
```

Tab labels:

- Home: `house`.
- Learn: `rectangle.stack` with a system badge for due items.
- Practice: `checkmark.circle`.
- Progress: `chart.xyaxis.line`.
- My: `person.crop.circle`.

## Screen Hierarchy

### Onboarding

Onboarding is short and task-specific. Each screen has one primary action.

1. Welcome: app name, one sentence of value, primary action to continue.
2. Level choice: Basic, Intermediate, Advanced as native selection rows or buttons; primary action stays disabled until a level is selected.
3. Reminder setup: time picker plus primary action to enable reminders; secondary action to skip.
4. Permission denied or skipped: show reminders as off, explain that practice still works, and offer a Settings path later from the Settings sheet.

Do not add a language picker in onboarding v1. App language follows system/app language settings.

### Home

1. Date and a secondary streak badge in the toolbar.
2. Gradient circular progress for today's completed count and configured goal.
3. One primary action: start or resume today's session.
4. Amber due-review pill and quick routes to review and random practice.
5. One-row summary for newly learned, reviewed, and practice results.
6. Preview of the next vocabulary or expression item.

Empty states:

- No items due and daily session complete: "今天完成了" plus a subtle next-review hint.
- Seed exhausted: explain that fewer than 10 items are available and show the exact count.
- No notification permission: reminder UI remains usable but shows a disabled state and a path to Settings.

### Learn Session

1. Progress indicator and a two-sided learning card.
2. Front: vocabulary/expression, IPA when available, pronunciation, and save state.
3. Back: localized meaning, plain/upgraded expression context, example, and translation.
4. Tap flips the card in 3D; Reduce Motion crossfades instead.
5. Right swipe grades known (`q = 5`), left grades unknown (`q = 1`), and up saves and grades (`q = 4`).
6. Equivalent xmark, star, and checkmark buttons are mandatory for accessibility.
7. A committed card writes progress immediately; an interrupted round never loses committed answers.
8. Completion presents known rate and known/saved/unknown counts.

### Practice Session

1. Progress indicator, for example `3/10`.
2. Upgraded expression as the main object.
3. Plain expression and Traditional Chinese explanation.
4. Example sentence.
5. Pronunciation button.
6. Quiz choices.

Rules:

- Learn may show the upgraded expression and supporting answer content. Quiz must not reveal a standalone correct answer before the learner responds.
- Quiz supports vocabulary meaning, vocabulary spelling, vocabulary listening, expression upgrade, expression meaning, and expression spelling. Mixed mode distributes all eligible modes across a run.
- Quiz timers use unlimited, 10, 15, 20, or 30 seconds. Expiry records an incorrect answer and freezes the question with time-up feedback; it does not advance automatically.
- The practice card may be a focused card surface. The whole screen must not become nested cards.
- Quiz choices must have stable height and clear selected/correct/wrong states.
- The pronunciation button uses a speaker SF Symbol with a text label for clarity.
- After the user answers, freeze all quiz options, reveal correct/wrong state, and show a primary `Next` action. Do not auto-advance in v1.
- If the selected answer is wrong, keep the correct answer visible before the user moves on.
- Results list the most recent round's wrong answers. When retry is enabled, retry only those questions while preserving their modes.

Practice is a top-level tab. Daily learning remains distinct from configurable quiz practice.

### Progress

1. 7/30-day learned-item LineMark and AreaMark chart.
2. Monday-aligned 15-week heatmap with five levels, today outline, and latest-week anchoring.
3. SectorMark distribution for new, learning, and mastered items.
4. Vocabulary/expression filtering and equivalent accessible text summaries.
5. Ten-achievement badge wall with locked, unlocked, and unlock-date states.

### My

1. Vocabulary progress for Basic, Intermediate, and Advanced.
2. Search.
3. Segmented control for Learned and Saved.
4. List rows with upgraded expression, plain expression, and small status metadata.
5. Word detail with save toggle and review stats.

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

## Motion and Haptics

- **Approach:** Tactile and purposeful.
- Use native navigation and sheet transitions.
- Learning cards use spring-backed 3D flip, swipe tilt, semantic stamps, and card-exit motion.
- Correct/wrong feedback should appear quickly, 150-250 ms.
- First-time achievement unlocks may use a badge bounce and a 1.5-second Canvas confetti effect.
- Respect Reduce Motion by replacing rotation, shake, flight, bounce, and particles with short opacity changes.
- Meaningful discrete actions provide semantic haptics. Do not generate repeated haptics during scrolling, continuous drag movement, or text entry.

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
- Add mascots, leaderboards, currencies, or punishment mechanics.
- Use a generic dashboard-card mosaic.
- Apply gradients to ordinary list rows or system surfaces.
- Hide important labels behind icons only.
- Let widget or notification copy expose sensitive learning data.

## Implementation Notes

- Create named color assets for the tokens above.
- Prefer SwiftUI text styles over fixed font sizes.
- Keep shared widget data in an App Group snapshot, not in SwiftData.
- The app is the only writer of widget snapshots.
- Use previews for light mode, dark mode, zh-Hant, English, and accessibility text sizes.
- UI tests should include at least Today, Practice, Review empty state, My empty state, and Settings sheet.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-10 | Initial design system created | Established the native iOS visual source of truth before plan design review. |
| 2026-07-10 | Use native TabView for Today, Review, My | Current iOS patterns support top-level tabs when they represent stable app areas. |
| 2026-07-10 | Use Apple platform typography instead of imported fonts | Vocaby is a native iOS app; platform text styles give Dynamic Type, localization, and accessibility behavior by default. |
| 2026-07-10 | Use restrained teal accent with system surfaces | Keeps the app calm and learning-focused while avoiding generic purple/blue AI palettes. |
| 2026-07-10 | Require explicit answered state with Next action | Prevents quiz auto-advance from hiding feedback before the learner can read it. |
| 2026-07-10 | Replace the multiple-choice-only quiz scope with four concrete modes plus mixed | The user approved expression, meaning, listening, and spelling practice with a mixed option. |
| 2026-07-15 | Rename Library to My, show three per-level learned/total summaries, and keep the tab bar fully visible | The user approved a personal progress destination and a non-minimizing native tab bar. |
| 2026-07-20 | Expand Vocaby to vocabulary plus practical expressions and adopt five top-level tabs | The user explicitly replaced the earlier narrow V1 positioning and navigation. |
| 2026-07-20 | Adopt SM-2, configurable 10-100 goals, 3D cards, three-way swipe grading, charts, achievements, gradients, haptics, and brief confetti | These are required parts of the Vocaby 2.0 learning and progress experience; accessibility and Reduce Motion alternatives remain mandatory. |
