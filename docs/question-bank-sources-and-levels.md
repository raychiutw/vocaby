# Question Bank Sources and Level Calibration

Status: V1 design baseline
Last reviewed: 2026-07-10

This document defines how Wording Daily creates, levels, reviews, and ships
vocabulary content. It is an engineering and editorial policy, not legal advice.

## Product Decision

- The shipping app reads only its bundled local question bank.
- There is no runtime download, account, sign-in, credential, API key, backend,
  iCloud, or sync path.
- New content is prepared and reviewed locally, committed to the repository, and
  delivered only in a new app build.
- V1 accepts Wording Daily-authored content, or content for which Wording Daily
  has documented redistribution and adaptation rights.
- External references may help validate meaning, usage, frequency, or CEFR level,
  but reference use does not permit copying definitions, examples, translations,
  audio, or level lists into the bank.
- `VocabularySeed.json` remains separate from SwiftData. A repository-only
  provenance manifest records editorial and rights evidence; it is not a runtime
  data source.

## Current Local Bank Audit

Audit target: `WordingDailyApp/Resources/VocabularySeed.json` on 2026-07-10.

| Level | Items | Unique IDs | Unique upgraded expressions | Unique English meanings | Unique zh-Hant meanings | Missing en / zh-Hant meanings |
|---|---:|---:|---:|---:|---:|---:|
| `basic` | 30 | 30 | 27 | 30 | 30 | 0 / 0 |
| `intermediate` | 30 | 30 | 27 | 29 | 30 | 0 / 0 |
| `advanced` | 30 | 30 | 29 | 30 | 30 | 0 / 0 |

Duplicate upgraded-expression groups:

- `basic`: `I'm not sure` (`basic-008`, `basic-022`), `give me a hand`
  (`basic-002`, `basic-020`), and `hold on` (`basic-006`, `basic-021`).
- `intermediate`: `discuss` (`intermediate-004`, `intermediate-011`),
  `due to` (`intermediate-006`, `intermediate-025`), and `improve`
  (`intermediate-003`, `intermediate-014`).
- `advanced`: `ambiguous` (`advanced-003`, `advanced-027`).
- `intermediate-003` and `intermediate-014` also share the same English meaning.

Five of the seven duplicate upgraded-expression groups have exactly the same
plain/upgraded pair. Whether they are the same concept still requires human
semantic review. Every level has enough distinct same-level values to build
four-option expression, listening, and localized-meaning questions. Spelling has
no distractor requirement. `QuizEngine`
must continue deduplicating displayed values, but that is not a substitute for
removing duplicate concepts during content review.

The embedded `quiz.options` values are legacy seed fields. New runtime questions
must continue to use same-level options generated from the local bank, never those
legacy options. Removing the legacy fields requires a separate schema migration.

The current `SeedValidator` checks duplicate IDs, required values, the legacy quiz
index, and ascending level order. It does not yet check normalized duplicates,
same-level option capacity, provenance, bank version, or CEFR calibration. Those
checks are implementation work, not properties of the current bank.

## Source Policy

### Admission rules

A source may contribute content only when all of the following are recorded before
the content edit:

1. Owner and canonical source URL.
2. Exact source version or retrieval date.
3. License name and canonical license URL.
4. Permission for commercial use, reproduction, redistribution, and modification.
5. Attribution, notice, and indication-of-change requirements.
6. Permission to distribute an adapted Traditional Chinese explanation or
   translation.
7. A stable source-entry reference for every copied or adapted item.

Reject unknown-license, scraped, account-gated, non-commercial-only,
no-derivatives, or incompatible share-alike material. Do not infer a license from
public availability. Legal review is required before the first release containing
externally derived content.

### Source decisions

| Source | Owner / canonical reference | Rights summary | Wording Daily decision |
|---|---|---|---|
| Wording Daily original content | Wording Daily; repository history and rights record | Project-owned or commissioned rights must cover English, zh-Hant, examples, quiz copy, and redistribution | **Preferred V1 source.** No external attribution when ownership is documented. |
| CEFR levels and descriptors | Council of Europe: [levels](https://www.coe.int/en/web/common-european-framework-reference-languages/level-descriptions) and [descriptors](https://www.coe.int/en/web/common-european-framework-reference-languages/cefr-descriptors) | CEFR defines six proficiency levels and illustrative can-do descriptors; this design does not treat the descriptors as an open content license | **Calibration only.** Cite the framework; do not copy descriptor text into seed content. |
| English Vocabulary Profile | Cambridge English Profile: [EVP user guide](https://www.englishprofile.org/images/pdf/evp%20user%20guide.pdf) | Copyrighted research reference; no open redistribution license is established for importing its entries | **Calibration only.** Check sense-level plausibility manually; do not copy entries, examples, audio, or lists. |
| Open English WordNet | Global WordNet Association: [project](https://github.com/globalwordnet/english-wordnet) and [complete LICENSE](https://github.com/globalwordnet/english-wordnet/blob/main/LICENSE.md) | A composite obligation: underlying Princeton WordNet terms continue to apply, while later Open English WordNet work is CC BY 4.0. Distribution must preserve the Princeton notices and credit both Princeton WordNet and the Open English WordNet team, plus the CC BY license link and change indication | **Conditional lexical reference.** The manifest must record both licenses and both attribution parties. No direct import in V1. |
| Princeton WordNet 3.0 | Princeton University: [license and commercial use](https://wordnet.princeton.edu/license-and-commercial-use) | Commercial use, copying, modification, and distribution are permitted when the complete required copyright, license, and disclaimer notices are preserved | **Conditional lexical reference.** No direct import until notices and per-item provenance are implemented and reviewed. |
| New General Service List | Browne, Culligan, and Phillips: [NGSL](https://www.newgeneralservicelist.com/new-general-service-list) | CC BY-SA 4.0 requires attribution and share-alike treatment for adaptations | **No direct V1 import.** May inform a manual frequency check only; do not copy its list, ranks, definitions, or derived bank. |
| Tatoeba sentences and audio | Tatoeba Association: [terms of use](https://tatoeba.org/en/terms_of_use) | Text defaults to CC BY 2.0 FR with author attribution; individual text and audio licenses can differ, and audio can add commercial or adaptation restrictions | **No V1 import.** Per-item author/license and translation-chain tracking is too costly for the local bank; use original examples and system TTS instead. |
| LingoLearn-iOS reference repository | `win4r/LingoLearn-iOS` | No visible license was found during the 2026-07-10 review | **Ideas only.** Do not copy code, UI, text, assets, or vocabulary. |

If a source's license changes, existing approved content remains tied to the exact
recorded source version and license evidence. New content stops until the new terms
are reviewed.

## Three-Level Model

The app keeps the existing `VocabularyLevel` enum. Each item also receives one
exact editorial CEFR band in the provenance manifest so a future bank can be
recalibrated without changing runtime models.

`itemID` is a permanent opaque identity. Existing IDs contain a historical level
prefix, but code and editors must not infer the current level from that prefix or
rename the ID when an item is recalibrated.

| App level | CEFR range | Content profile |
|---|---|---|
| `basic` | A1-A2 | High-frequency everyday communication, transparent meaning, neutral register, and simple grammar. |
| `intermediate` | B1-B2 | Common collocations and phrasal language, meaningful register choices, moderate idiomaticity, and broader context. |
| `advanced` | C1-C2 | Nuanced or context-sensitive register, lower-frequency collocations, opaque idioms, polysemy, and precise pragmatic use. |

Level the intended sense and usage, not the spelling of a headword. A common word
can be advanced when its sense or expression is idiomatic. A long expression is
not automatically advanced.

### Difficulty and usefulness rubric

Score the first five dimensions from 0 to 2. Their sum is the difficulty score.
Score Taiwan-learner usefulness separately; it is an admission and priority gate,
not a way to make a difficult item appear easier.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Frequency | Very common in everyday general English | Common but context-dependent | Lower-frequency or domain-limited |
| Semantic transparency | Literal and immediately inferable | Partly figurative or collocational | Opaque idiom or non-obvious sense |
| Grammar complexity | Simple word or fixed short pattern | Phrasal/collocational pattern or moderate syntax | Complex complementation, constraints, or form changes |
| Register and pragmatics | Neutral and broadly interchangeable | Clear formal, informal, politeness, or tone constraint | Nuanced stance, implication, irony, or audience sensitivity |
| Polysemy and context | One clear target sense | Several common senses, target remains identifiable | Meaning strongly depends on context or collocation |
| Taiwan-learner usefulness | Rare need or poor product fit: reject | Useful in a recurring but narrower situation | Broadly useful for real speaking, writing, work, study, or travel |

Initial mapping:

- Difficulty 0-3: `basic` / A1-A2.
- Difficulty 4-7: `intermediate` / B1-B2.
- Difficulty 8-10: `advanced` / C1-C2.
- Usefulness 0: reject from the bank regardless of difficulty.

The score proposes a level; it does not approve one. A human level reviewer must
assign an exact CEFR band and may move an item one adjacent app level with a written
rationale. Moving directly between `basic` and `advanced` requires two level
reviewers. Examples, meanings, and quiz prompts must demonstrate the same intended
sense used for calibration.

## Build-Time Provenance Manifest

Create `Content/VocabularyProvenance.json` when the next content batch is built.
Do not add it to the app target and do not decode it at runtime. Keep one source
catalog and one record per seed item in the same file:

```json
{
  "schemaVersion": 1,
  "bankVersion": "2026.07.1",
  "sources": [
    {
      "id": "wording-daily-original",
      "owner": "Wording Daily",
      "sourceURL": null,
      "sourceVersion": "2026.07.1",
      "retrievedAt": null,
      "licenses": [
        {
          "name": "Project-owned",
          "version": null,
          "url": null,
          "evidence": "rights-record-id",
          "requiredNotice": null
        }
      ],
      "attributionParties": [],
      "attributionText": null,
      "rights": {
        "commercialUse": "approved",
        "reproduction": "approved",
        "redistribution": "approved",
        "modification": "approved",
        "translatedDerivatives": "approved"
      },
      "rightsReviewer": "reviewer-id",
      "rightsVerifiedAt": "2026-07-10"
    }
  ],
  "items": [
    {
      "itemID": "basic-001",
      "sourceID": "wording-daily-original",
      "origin": "authored",
      "sourceEntryRef": null,
      "changesMade": null,
      "cefr": "A2",
      "appLevel": "basic",
      "revision": 1,
      "difficulty": {
        "frequency": 0,
        "transparency": 0,
        "grammar": 0,
        "register": 0,
        "polysemy": 0
      },
      "taiwanUsefulness": 2,
      "englishReviewer": "reviewer-id",
      "zhHantReviewer": "reviewer-id",
      "levelReviewer": "reviewer-id",
      "rightsReviewer": "reviewer-id",
      "reviewedAt": "2026-07-10",
      "levelOverrideReason": null,
      "status": "approved"
    }
  ]
}
```

Each `rights` value is one of `approved`, `blocked`, or `unknown`; packaging
requires all five values to be `approved`. Every applicable license, including an
upstream license such as Princeton WordNet inside Open English WordNet, gets its
own `licenses` entry with exact version, official URL, locally retained evidence,
and required notice. `attributionParties` and `attributionText` must cover the
combined obligations.

For copied or adapted content, `sourceURL`, `sourceEntryRef`, and `changesMade` are
mandatory in addition to complete source rights. Reviewer identifiers may be
stable initials or team IDs; no account system is added to the app.

If an approved external source requires notices, a deterministic local build step
must generate a bundled acknowledgements file. The app still performs no network
request. Until that generator and an in-app notice location exist, external
material remains blocked.

### First permanent identity baseline

This V1 design assumes the current 90-item bank has not yet been released to users
whose local progress must be preserved. Before the first data-preserving TestFlight
or public build, development installs may be reset and duplicate rows may be
rewritten as distinct, reviewed concepts. The clean 90-item bank must then be
recorded as `Content/Baselines/1.0.0.json`. If that
assumption is false, content release stops until a tested SwiftData migration is
designed.

The baseline contains an append-only ID registry with `itemID`, an immutable
editor-assigned `conceptKey`, `firstBankVersion`, `status`, and `canonicalItemID`.
Every later bank compares against the latest committed baseline. During V1 after
the baseline:

- An existing ID may receive copy, translation, example, or level corrections only
  when it remains the same concept.
- Removing, reusing, retiring, or redirecting an existing ID is blocked.
- New IDs are appended and become permanent in the next baseline snapshot.

A future retirement/merge feature must add an old-ID-to-canonical-ID mapping and
explicit conflict rules for `WordProgress`, `DailySessionItem`, and `QuizResult`,
with migration tests, before the gate can be relaxed. This design deliberately
does not guess those persistence rules.

## Local Authoring and Release Workflow

1. Add a candidate to a local editorial file; do not edit the shipping JSON first.
2. Add or select its source record and pass the rights gate.
3. Author the English definition, example, prompt, and Taiwan Traditional Chinese
   explanation/translation. Do not machine-translate without native review.
4. Score the item, assign an exact CEFR band, and select the mapped app level.
5. Run structural and question-capacity validation.
6. Complete English, zh-Hant, level, and duplicate-concept human reviews.
7. Generate `VocabularySeed.json` and any required attribution notice locally in a
   deterministic order.
8. Run tests, an offline simulator build, and the checklist in
   `docs/content-review.md`.
9. Commit the seed, provenance manifest, generated notice, tests, and bank-version
   change together. Ship them only in a new app version.

There is no over-the-air bank update. Source research happens outside the app.
Only approved input artifacts whose licenses permit repository redistribution are
vendored with provenance. Build and runtime code must not contain a remote
endpoint, downloader, token, or credential.

## Automated Import and Release Gates

The next question-bank implementation must fail before packaging when any gate
below fails:

- Seed and provenance IDs are unique and have a one-to-one match.
- The current manifest and seed preserve every ID and `conceptKey` from the latest
  permanent baseline. V1 rejects removal, reuse, retirement, or redirection.
- Every source has `approved` commercial-use, reproduction, redistribution,
  modification, and translated-derivative rights. Externally derived items contain
  every applicable license/version/evidence entry, source-entry reference,
  attribution party, required notice, and change record.
- `contentLanguageCode` is `en`; English and `zh-Hant` meanings are non-empty;
  `zh-Hant` is declared as a support language; examples, translations,
  pronunciation text, and prompts are non-empty.
- The exact CEFR band belongs to the app-level range and all rubric/reviewer fields
  are present.
- `sortOrder` is unique, ascending, and contiguous inside each level.
- Each level has at least four distinct upgraded expressions and four distinct
  meanings in every supported question language.
- New or changed items do not introduce duplicate normalized upgraded expressions,
  duplicate concepts, or alternative answers that make a question ambiguous.
- Correct answers appear exactly once after displayed-value normalization.
- Generated attribution contains every required source and is deterministic.
- The bundled seed decodes and validates with networking disabled.

Displayed-value normalization means Unicode compatibility normalization,
locale-stable case folding, trimming and collapsing whitespace, and treating
straight/curly apostrophes and equivalent dash forms consistently. The validator
must report both item IDs when it finds a collision.

The current seven duplicate upgraded-expression groups are a pre-baseline migration
backlog. They must be resolved before the first permanent identity baseline or any
bank expansion.

## Existing 90-Item Migration

1. Confirm that no external build has local progress requiring preservation. If
   one exists, stop and design the three-model SwiftData migration first.
2. Do not label the current bank `authored` until ownership is confirmed from
   repository history or another rights record. Use a temporary `legacy-local-v1`
   source whose five rights fields remain `unknown` during the audit.
3. Replace the seven duplicate upgraded-expression rows with distinct, fully
   reviewed concepts and resolve the duplicated intermediate English meaning.
   Keep the current 30-per-level contract; pre-baseline development data may be
   reset rather than silently merged.
4. Create one provenance row for all 90 IDs, assign exact A1-C2 bands, and
   confirm English sense, Taiwan Traditional Chinese, rights, and level.
5. Run the full content review and capacity checks, then write the first permanent
   ID baseline. From that point onward, V1 blocks removal, reuse, or redirection.

## Acceptance Criteria

- A clean install completes Today, Review, Library, Practice Center, TTS, and widget
  flows in airplane mode with no account or credential prompt.
- All new words and distractors are traceable to bundled seed IDs.
- Every seed item has approved rights, exact CEFR, rubric, and four human review
  records in the provenance manifest.
- Automated validation rejects missing language fields, provenance mismatches,
  unsupported licenses, unstable IDs, sort-order gaps, and insufficient unique
  local distractors.
- Human review confirms natural English, natural Taiwan Traditional Chinese,
  realistic examples, correct sense/level, plausible distractors, and accessible
  copy at normal and accessibility Dynamic Type sizes.

## Non-Goals

- Importing a third-party word list in this design task.
- On-device crawling, generation, translation, bank updates, or level inference.
- A remote content-management system, account, sync layer, or sync-ready
  abstraction.
- Treating a frequency rank or automated score as final CEFR certification.
