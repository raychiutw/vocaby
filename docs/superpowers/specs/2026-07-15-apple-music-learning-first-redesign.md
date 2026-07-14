# Apple Music Learning-First Redesign

Date: 2026-07-15
Status: approved for implementation by the user's direct-edit authorization and continuing completion goal

## Objective

Bring every Vocaby screen to Apple Music-level native hierarchy and Apple HIG conventions without imitating music-specific decoration. Remove redundant labels, values, empty surfaces, and fixed artwork. Redesign vocabulary learning and quizzes for Traditional Chinese users learning English.

## Design position

Use Apple Music as a reference for native navigation, content-first hierarchy, compact scannable rows, one prominent action, and progressive disclosure. Keep Vocaby's learning identity. Do not represent vocabulary screens as albums, players, or decorative artwork.

## Global rules

- Preserve the native three-tab `TabView`: Today, Review, Library.
- Preserve native `NavigationStack`, system search, segmented controls, sheets, forms, and Dynamic Type.
- Use cards only for an actual learning or answer interaction.
- A screen has at most one prominent action.
- Remove a field label when typography, placement, control type, or surrounding context already identifies the value.
- Do not show empty previews, zero-value summaries, disabled primary actions, or duplicate scope status.
- Put secondary definitions, extra senses, and review history behind disclosure or navigation.
- Use `gearshape` for Settings; Vocaby has no account or profile.
- Keep all controls at least 44 pt and preserve semantic accessibility labels and reading order.
- Support Traditional Chinese and English localization, Dark Mode, and accessibility Dynamic Type.

## Information architecture

### Today

The first viewport answers only: what should I do now?

- Show completed/total count, progress, and one Start or Continue button.
- Show due review only when the count is greater than zero.
- Show a next-word preview only when a word is available.
- Remove fixed artwork, duplicate action copy, empty preview rows, and per-level vocabulary totals.
- Keep free practice as a compact secondary navigation row below the daily task.

### Review

- Empty: show “今天不用複習” and one short useful next-step sentence. No artwork, duration, count, or disabled CTA.
- Non-empty: show one compact count-and-duration sentence plus one Start button.
- Completion is brief and returns to Review.

### Library

- Remove fixed artwork.
- Keep learned/saved segmented scope.
- Show search only when there is content to search.
- Rows show upgraded expression and one useful subtitle: plain expression or Traditional Chinese meaning.
- Do not repeat `已學` or `已儲存` inside its own scope. Show mastered only as an exceptional compact status.
- Empty states use native content-unavailable hierarchy and no filler rows.

### Vocabulary detail

- Display the upgraded expression once.
- Put bookmark in the toolbar.
- Use the same learner-first content component as practice.
- Condense progress to one sentence such as “答對 3 次 · 下次 7/20”.
- Do not expose internal day-key formatting.
- Extra senses and detailed review history are secondary disclosure content.

### Free practice

- Default to mixed, 10 questions, retry wrong answers.
- Remove the read-only level row.
- Keep optional mode, count, timer, and retry settings in one compact native adjustment surface.
- Starting practice remains the only prominent action.

### Settings

- Keep native grouped settings rows; label/value is correct for editable preferences.
- Use a gear icon from every top-level screen.

## Learner-first vocabulary card

The primary sequence is:

1. Upgraded English expression.
2. Pronunciation action, IPA, and inline part of speech.
3. Traditional Chinese core meaning.
4. Plain-to-natural English comparison.
5. English example and Traditional Chinese translation.
6. Optional English definition and additional senses under More.

Target hierarchy:

```text
3 / 10

give me a hand                         🔊
/ɡɪv mi ə hænd/ · 片語

幫我一下；協助我

help me  →  give me a hand

Could you give me a hand with this?
你可以幫我處理這件事嗎？

更多意思
```

Do not display standalone labels for pronunciation, English meaning, Traditional Chinese meaning, or example when the layout already communicates them.

## Quiz design

### Question

- Use one focused question surface instead of nested cards.
- Show compact progress and, where enabled, a compact clock value.
- Use plain full-width answer rows with neutral appearance before selection.
- Only selected, correct, and wrong answers receive semantic styling.
- Spelling fields use an ASCII-capable keyboard, no capitalization, and no autocorrection.
- Daily first-exposure learning is untimed. Optional timing remains available in free practice and review.

### Feedback

- Correct: one brief confirmation.
- Wrong or timeout: correct English, Traditional Chinese meaning, and one bilingual example.
- Do not append the full vocabulary-detail component inline.
- Full detail is an optional action.
- Next is the only prominent action and must not obscure scroll content, keyboard, or the tab bar.

### Distractors

- Expression-choice and listening-choice modes use validated authored English options when available.
- Meaning-choice uses semantically plausible Traditional Chinese options, preferring authored localized options when available.
- Never use arbitrary same-level words merely because they share a level.
- Spelling mode has no distractors.
- Correct-answer persistence indices remain deterministic and valid.

### Completion

- Summarize as one line such as “10/10 完成 · 答對 8 題”.
- Show scheduled-review count only when it is nonzero.
- De-emphasize streak unless it changed.
- Show one completion action.

## Onboarding

- Preserve the three product steps unless `DESIGN.md` is explicitly changed later.
- Level: one title and native checkmark rows; picker label is accessibility-only.
- Reminder: compact “每天 [time]”; remove explanatory duplication.
- Continue/Enable is the single prominent bottom action; Skip is plain secondary.

## Verification contract

Completion requires all of the following from a current build:

- Unit tests prove authored quiz options are used, arbitrary same-level distractors are rejected, and existing quiz persistence behavior remains correct.
- Localization coverage tests pass for Traditional Chinese and English.
- Full build and test suite pass without new warnings.
- Screenshots cover onboarding, Today, empty/non-empty Review, empty/non-empty Library, vocabulary detail, free-practice setup, learner card, all quiz modes, correct/wrong/timeout feedback, completion, and Settings.
- The same critical screens are checked in Light and Dark Mode and at an accessibility Dynamic Type size.
- VoiceOver order, 44 pt targets, keyboard choice, safe-area behavior, and content visibility are manually checked.
- A final source scan finds no report-style `LabeledContent` outside settings or a justified editable form.

## Non-goals

- No custom tab bar or navigation framework.
- No new dependency. A shared learner-presentation component or system is allowed when at least two screens need the same hierarchy or behavior; do not create speculative framework layers.
- No account/profile feature.
- No backend, sync, analytics, or content-schema expansion solely for this redesign.
- No literal Apple Music album/player metaphor.
