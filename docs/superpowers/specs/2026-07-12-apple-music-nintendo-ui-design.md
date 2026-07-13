# Apple Music x Nintendo Learning UI Design

## Goal

Make Vocaby feel like a compact native iPhone learning app: Apple Music supplies navigation and list density; Nintendo Switch Parental Controls supplies a friendly, local activity summary.

## Constraints

- iOS 17+, SwiftUI, system SF typography, Dynamic Type, native `TabView`, `NavigationStack`, `List`, and system materials.
- No custom floating tab bar, login, account, backend, iCloud sync, or network functionality.
- Keep the existing `Accent` teal and `ReviewAmber` semantic colour roles.
- Cards are reserved for focused interaction only. Ordinary metadata and lists remain plain list rows.
- The local Settings sheet is the My Learning entry. It is not membership or account management.

## Navigation and Header

- Today, Review, and Library retain native large navigation titles. Their lists use native large-title collapse on scroll.
- Every root tab has the same trailing My Learning button. It opens the existing local Settings sheet.
- The system `TabView` remains responsible for material, selection, safe area, and Dynamic Type. No MiniPlayer or fourth tab is added.
- Library remains the only tab that may add contextual header actions in the future. Search and Learned/Saved stay in the content hierarchy, not a permanently crowded toolbar.

## Screen Design

### Today

- One focused daily-practice surface: a small generated study cover, compact date/progress/streak summary, progress bar, and the sole prominent action.
- Review becomes a one-line navigation row: `待複習 10 · 約 4 分鐘` with the next expression as supporting text.
- Vocabulary totals move behind a compact navigation row instead of a full visible level table.

### Review

- Display `待複習 N · 約 M 分鐘` as the summary row.
- Keep one compact prominent start action and show up to three upcoming expressions as normal rows.
- The empty state explains that no review is needed and directs the learner to Today.

### Library

- Use the native searchable list and an inline Learned/Saved segmented control.
- Each word row has exactly two content lines: upgraded expression, then `plain expression · status`.
- Remove enclosing dashboard cards around search, scope selection, and the word list.

### My Learning

- Reuse `SettingsView` as the local My Learning sheet.
- Group level, reminders, language, and source notices as clear native settings sections.

## Artwork

- Create three text-free 1:1 study covers: Daily Focus, Review, and Library.
- They use warm paper-like abstract forms, restrained teal/amber accents, generous negative space, no people, no logos, no gradients that compete with text, and no embedded text.
- Artwork appears only in focused top-level surfaces, never inside every list row.

## Validation

- Verify navigation titles collapse with scroll and settings are reachable from all tabs.
- Verify normal and accessibility Dynamic Type; all row content remains legible or wraps cleanly.
- Verify dark and light appearance, all existing localization checks, and the full iOS test suite.
- Reinstall the current 10,021-word build before final device screenshots.
