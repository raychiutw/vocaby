# Offline Vocabulary Validation and Rich Entry Design

**Status:** approved design
**Date:** 2026-07-11

## Goal

Clean and revalidate the complete bundled vocabulary bank before release so that
every quiz item has trustworthy English and Taiwan Traditional Chinese content,
one or more labeled pronunciations, part of speech, a primary sense, up to two
additional common senses, and a bilingual example for each shipped sense.

This work happens only in the maintainer pipeline. The SwiftUI app remains fully
offline, requires no account or credential, and never downloads or modifies the
official question bank.

## Product Boundary

- Maintainers may download exact, versioned source snapshots during content
  preparation.
- Raw snapshots, imported JSONL, reports, review queues, and provenance remain
  repository-only and are excluded from every Xcode target.
- The App bundles only promoted vocabulary data and required source notices.
- App execution contains no translation API, HTTP client, account, login,
  credential, remote question bank, or update path.
- Users can search, learn, hear, and answer bundled entries but cannot add, edit,
  import, delete, or replace official content.
- Google Translate is not a release dependency. It may be used manually for an
  isolated editorial comparison, but its output is neither authoritative nor
  required to reproduce the bank.

## Source Strategy

Use a structured, offline multi-source consensus instead of one translation
service:

| Source | Purpose |
|---|---|
| Wiktextract/Kaikki English snapshot | Structured headwords, parts of speech, senses, IPA, region labels, and source examples |
| Open English WordNet | English lemma, sense, definition, example, and lexical relation validation |
| CMUdict | Independent American pronunciation check after comment removal and ARPABET normalization |
| COW and OMW ILI map | Exact English-to-Chinese sense alignment where available |
| CC-CEDICT | Secondary Taiwan Chinese gloss review only when the intended sense matches |
| Tatoeba | Context-aligned bilingual example evidence |
| CEFR-J | Existing CEFR and App-level calibration |

Every snapshot must have an exact version, URL, size, SHA-256, license evidence,
required notice, and `appUse` decision in `source-manifest.json`. Store only the
minimum upstream shard or archive needed for the selected English entries under
`Content/Sources/Raw`. It is tracked in Git but never added to an App target.

Wiktextract-derived data starts as `reference_only`. It may contribute a shipped
field only after the existing rights gate confirms reproduction, adaptation,
commercial use, attribution, and notice requirements for the underlying data.
No checksum or rights field may be weakened to make promotion pass.

## Canonical Data Model

Source-specific formats end at the existing canonical candidate JSONL boundary.
The common enrichment stage produces the following logical seed shape:

```text
VocabularySeedItem
├── id, level, sortOrder
├── plainExpression
├── upgradedExpression
├── primarySenseID
├── pronunciations[]
│   ├── id
│   ├── ipa
│   ├── speechLocale       en-US, en-GB, or another approved English locale
│   └── region             optional display label
├── senses[]               one primary plus at most two common additions
│   ├── id
│   ├── partOfSpeech
│   ├── meaning            English and zh-Hant
│   ├── example            English and zh-Hant full sentences
│   └── pronunciationIDs[]
└── quiz
    ├── localizedPrompt
    ├── options
    └── correctIndex
```

The singular `meaning`, `example`, and `pronunciationText` fields are replaced by
the structured collections rather than maintained as duplicate sources of truth.
`primarySenseID` drives the current question. Each sense references only the
pronunciations that apply to that sense, which distinguishes homographs such as
noun and verb readings.

Each item has one to three shipped senses. The selected question sense is always
shown first after an answer; the remaining common senses are supplemental. IDs
are stable and never reused for a different lemma or sense. Removing a rejected
item does not reassign its ID to replacement content.

## Shared Cleaning and Validation Flow

```text
raw source snapshots
    -> one adapter per source format
    -> canonical candidate JSONL
    -> shared sense/pronunciation/translation/example enrichment
    -> shared deterministic validation
    -> pass, review, and reject reports
    -> human release sign-off
    -> atomic promotion to bundled seed and notices
```

Adapters parse containers and normalize source fields only. They must not contain
source-specific translation, example, quiz, reviewer, or promotion behavior.
All sources rejoin the same shared stage after canonical JSONL.

The shared stage:

1. Normalizes headwords, parts of speech, IPA, region labels, source references,
   and CMUdict records. Inline CMUdict comments are removed before pronunciation
   comparison.
2. Selects the intended OEWN sense and keeps the existing exact ILI mapping when
   available.
3. Chooses the question's primary sense and at most two additional frequent,
   useful senses. Obscure, proper-name-only, offensive-without-context, malformed,
   or duplicate senses are rejected.
4. Produces English and Taiwan Traditional Chinese meaning pairs for the same
   sense. OpenCC remains a maintainer-time normalization tool, not a translator.
5. Requires a natural bilingual full-sentence example for each shipped sense.
   A Chinese usage note is not accepted as an example translation.
6. Requires `plainExpression` to be a natural simpler expression, not a copied
   dictionary definition.
7. Generates quiz prompts and distractors only after sense alignment succeeds.

### Promotion verdicts

- **Pass:** all required fields, rights, sense alignment, examples, questions,
  provenance, and deterministic checks succeed.
- **Review:** sources disagree, only one weak source supports a field, a reading
  cannot be associated with a sense, or semantic alignment is below threshold.
- **Reject:** invalid spelling, unusable expression, missing approved rights,
  malformed IPA, mismatched translation or example, duplicate identity, or
  multiple correct quiz answers.

Review and reject records are repository-only. Promotion fails before replacing
the bundled seed if any intended shipping item remains unresolved. A failed run
leaves the previous App resource untouched.

## Pronunciation Playback

Every item has at least one pronunciation. The App displays IPA and a region
label when present, with an independent speaker button for each reading.

Playback uses `AVSpeechSynthesizer` and an already available on-device English
voice. The pronunciation's IPA is supplied through the native IPA speech
attribute when supported. If the requested locale or IPA override is unavailable,
the App speaks `upgradedExpression` with the closest installed English voice and
keeps the IPA visible. It never requests a voice download or makes a network
call.

Pronunciation buttons have VoiceOver labels containing the expression, region,
and IPA. They retain the 44-point minimum touch target and respect system audio
and accessibility behavior.

## Quiz and Library Presentation

Quiz options remain hidden from explanation content until the learner answers.
After answering, options freeze and the existing correct/wrong state remains
visible. Before `Next`, the screen shows:

1. the expression and every applicable pronunciation button;
2. the question sense's part of speech;
3. its English and Traditional Chinese meanings;
4. its English and Traditional Chinese example sentences; and
5. up to two additional common senses in a native `DisclosureGroup`.

The learning screen and Library detail reuse the same ordered seed content. They
do not perform a separate lookup or translation. The native disclosure keeps the
quiz surface compact while making additional meanings available. No new tab,
custom tab bar, dashboard, or content editing screen is introduced.

## Validation and Tests

### Maintainer pipeline

- Add a focused Wiktextract adapter fixture covering two parts of speech, two
  pronunciations, region labels, multiple senses, and an example.
- Verify CMUdict comments are removed and multiple ARPABET readings remain
  distinct before comparison.
- Verify every source format rejoins the same enrichment and promotion path.
- Run two clean full-bank generations and require byte-identical canonical,
  report, seed, provenance, and notice outputs.
- Require one-to-one stable IDs between promoted seed and provenance.
- Reject missing or malformed IPA, dangling pronunciation IDs, missing part of
  speech, duplicated senses, more than three senses, empty bilingual meanings,
  non-sentence translations, sense-mismatched examples, and ambiguous quizzes.
- Confirm every shipped field cites an approved source and that reference-only
  sources contribute no shipped value.

### Swift and UI

- Decode the complete seed and validate a nonempty pronunciation list, one to
  three senses, a valid `primarySenseID`, and valid pronunciation references for
  every item.
- Verify `QuizEngine` preserves the selected sense through answer feedback.
- Verify the post-answer state exposes bilingual meaning, part of speech,
  bilingual example, pronunciations, and additional senses only after answering.
- Verify pronunciation fallback selects an installed English voice without a
  remote dependency.
- Check Traditional Chinese and English at normal and accessibility Dynamic Type,
  VoiceOver labels, and 44-point pronunciation targets.

### Offline acceptance

- Build resources contain only the promoted seed and required notices, never raw
  snapshots, imports, reports, manifest, or provenance.
- Static checks find no App runtime networking, translation API, login, account,
  credential, or remote content code.
- On a physical iPhone with Wi-Fi and cellular disabled, every sampled reading
  plays, all five quiz modes complete, and answer feedback shows the required
  bilingual content.
- The promoted bank retains at least 5,000 entries. The original 5,440 selection
  slots may be reduced only by documented validation rejections; the audited
  release contains 5,221 approved entries and 219 source slots rejected for
  missing verified or composable pronunciation.

## Non-Goals

- Shipping dictionary source archives or a full dictionary browser.
- On-device content generation, translation, validation, or bank updates.
- Recording custom audio files when native speech covers the approved reading.
- Supporting user-created vocabulary or editable official content.
- Adding a network, repository, dependency-injection, sync, or CMS abstraction.
