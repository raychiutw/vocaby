# 100,000-Lesson Offline Vocabulary Bank and TestFlight Design

**Date:** 2026-07-17
**Status:** Approved for implementation
**Release target:** TestFlight `1.1.0`
**Supersedes for final scope:**
`2026-07-17-vocabulary-quality-cefr-pronunciation-design.md`

## Context

Vocaby currently ships 14,064 complete lessons from 15 approved or blocked
source snapshots. The current source report contains 904,681 canonical records
and 583,652 normalized unique headwords, so source capacity is not the limiting
factor. The limiting factor is the intersection of learner-useful English
senses, Taiwan Traditional Chinese meaning, complete bilingual examples,
verified pronunciation, CEFR evidence, quiz content, source rights, and review.

The previously approved quality plan remains mandatory as the first content
phase. It repairs the current bank, restores exact CEFR, completes pronunciation
for the 1,272 deterministic rejections, and produces 15,336 approved lessons.
The new target then adds 84,664 approved lessons for an exact final total of
100,000.

The user selected the full-content target: every one of the 100,000 entries must
be directly usable by daily practice. A searchable headword-only tier does not
satisfy this requirement. The user also approved a mixture of exact and
traceable inferred CEFR and selected the source-first, generate-only-missing
approach.

## Goals

- Ship exactly 100,000 complete, reviewed, offline lessons.
- Preserve all existing stable lesson IDs so SwiftData progress remains valid.
- Prefer approved source fields and generate only fields that remain missing.
- Keep exact CEFR when present; allow reviewed inferred CEFR with recorded
  evidence, method, model/tool fingerprint, confidence, and reviewer identity.
- Keep the three App levels derived from CEFR:
  - A1 and A2 -> `basic`;
  - B1 and B2 -> `intermediate`;
  - C1 and C2 -> `advanced`.
- Replace whole-bank JSON loading with a bundled read-only SQLite content store.
- Keep SwiftData as the only user-progress store.
- Preserve the native three-tab design and non-minimizing tab bar.
- Review every 20 completed enrichment batches, then commit and push that
  checkpoint. Review and commit the final partial boundary as well.
- Release the completed feature as TestFlight `1.1.0` and verify Apple reports
  both `processingState=VALID` and `internalBuildState=IN_BETA_TESTING`.

## Non-goals

- No App runtime download, backend, account, credential, API client, sync, or
  update service.
- No user-importable or editable official bank.
- No full upstream Wiktionary dump in the App, Xcode target, or Git history.
- No Google Translate scraping or redistributed Google pronunciation data.
- No source, Agent, Apple Translation, or Foundation Models draft is called an
  approved lesson before review and promotion gates pass.
- No weakening of pronunciation, bilingual content, quiz, rights, source,
  deterministic-build, or review gates to reach the numeric target.
- No forced equal distribution among the three App levels.
- No separate source-specific enrichment or promotion pipeline.
- No third-party iOS database dependency, repository abstraction, remote-bank
  scaffolding, or dependency-injection framework.

## Source Capacity and Rights

The current pinned source report is the baseline:

- 904,681 canonical records;
- 583,652 normalized unique headwords;
- 185,082 Open English WordNet records;
- 126,052 CMUdict pronunciation records;
- 118,295 CC-CEDICT records;
- 79,811 Chinese Open WordNet records;
- 76,604 Tatoeba English-Mandarin parallel records;
- 31,535 current-target Wiktextract records;
- 17,750 CEFR-bearing source rows before overlap.

Only manifest sources with `appUse: approved` may contribute shipping fields.
Blocked sources remain research-only and cannot supply levels, meanings,
examples, pronunciations, or quiz content.

### Existing approved snapshots

Retain the exact current versions and decisions for CEFR-J, CC-CEDICT,
CMUdict, Chinese Open WordNet, FreeDict, WortUniversum, the OMW ILI map, Open
English WordNet, Tatoeba, and Wiktextract. Preserve every required notice and
per-item source reference.

The current Wiktextract file is a current-target-only snapshot. After the
100,000 target expressions are deterministically selected, stream the same
pinned 2026-07-06 enwiktionary extraction and replace the snapshot with a
superset containing the old targets plus all selected new targets. Record the
new exact byte count and SHA-256 before changing its manifest entry. Exclude
quotations, audio, images, and externally licensed or fair-use media exactly as
the current decision requires.

### Moby Pronunciator II

Complete the previously approved Moby source addition before expanding the
target universe. Pin the Project Gutenberg artifact and public-domain evidence:

- URL: `https://www.gutenberg.org/files/3205/files/mpron.txt`
- retrieved: 2026-07-17
- rows: 177,266
- bytes: 5,493,251
- SHA-256:
  `55580c3b258873723fed33497fe3a438b26167370bbe016431b3fc65fea67f2d`

The source remains non-shipping until manifest, checksum, adapter, notation,
notice, deterministic-import, and review gates pass.

### Generated fields

Apple Translation and Foundation Models are maintainer-time tools only. Their
output is a draft attributed to `vocaby-original`, with the exact input hash,
tool mode, helper source hash, OS/model availability fingerprint, checkpoint
ID, and reviewer fields recorded. Generated output is not source evidence for
an upstream claim and is not accepted until the same reviewed-row gates pass.

## Target Universe

### Stable baseline

First execute the earlier A/C/B quality phases and reach the deterministic
15,336-row bank without changing existing lesson identity. The new target
selector treats those expressions and IDs as immutable retained rows.

### Additional 84,664 lessons

Form candidates from approved canonical imports only. A target is eligible when:

- its normalized expression is unique and is not already retained;
- it has an approved English lexical sense and supported part of speech;
- it has at least one verified pronunciation candidate from CMUdict,
  Wiktextract, Moby, or another separately approved pronunciation source;
- it is an English word or learner-useful expression of at most eight tokens;
- it is not a proper name, spelling error, raw inflection duplicate,
  abbreviation-only entry, obsolete/archaic-only sense, slur, or source-tagged
  non-lexical artifact;
- its selected sense can be expressed with a concise English meaning and a
  complete example sentence;
- all fields can be attributed either to an approved source or reviewed
  `vocaby-original` content.

Order eligible candidates deterministically by:

1. retained existing lesson order;
2. exact CEFR evidence before inferred CEFR at the same band;
3. CEFR band from A1 through C2;
4. number and quality of independent approved lexical/translation/example/
   pronunciation references;
5. approved-corpus occurrence evidence, when available;
6. normalized expression and stable source entry reference.

The selector emits more than 84,664 candidates so rejected rows can be replaced
without lowering gates. Selection stops only when 100,000 approved rows exist,
not when 100,000 draft rows have been attempted.

## CEFR Policy

### Exact CEFR

Exact CEFR-J or approved explicit CEFR evidence is authoritative for the
intended part of speech and sense. Conflicting exact sources enter review and do
not silently choose the easier or harder value.

### Inferred CEFR

When no exact source exists, the shared review stage proposes CEFR using a
documented Taiwan-learner rubric rather than spelling length or frequency alone.
The proposal considers:

- everyday versus specialized domain and register;
- sense transparency, idiomaticity, and polysemy;
- grammar and collocation complexity in the selected example;
- approved-source usage labels and lexical relations;
- approved-corpus occurrence evidence;
- relation to exact lower-level plain expressions and same-sense synonyms;
- a local Foundation Models classification draft when available.

Each inferred row records `cefrMethod: inferred`, the rubric evidence, a
confidence value, the tool/helper fingerprint when a model contributed, and a
reviewer. High confidence requires agreeing independent signals. Medium or low
confidence enters review; unresolved low confidence is rejected and replaced.

The reviewed artifact is the canonical decision. Rebuilding the SQLite database
from that artifact is byte-deterministic even though regenerating a model draft
is not expected to reproduce its wording.

No level quota is imposed. Counts may skew heavily toward `advanced` because a
100,000-entry English bank necessarily contains many C1/C2 senses.

## Rich Lesson Contract

Every approved lesson contains:

- stable ID, level, contiguous level sort order, exact A1-C2 value, and CEFR
  method/evidence in repository provenance;
- content language `en` and support language `zh-Hant`;
- learner-friendly plain expression and upgraded expression;
- one to three common senses with stable IDs and supported parts of speech;
- concise English and Taiwan Traditional Chinese meanings for every sense;
- a natural complete English example containing the target or an accepted
  inflection and a faithful full-sentence zh-Hant translation for every sense;
- one or more verified IPA pronunciations with locale/region labels and stable
  IDs;
- nonempty per-sense pronunciation references;
- an English and zh-Hant quiz prompt;
- exactly four unique level-appropriate options and one aligned correct answer;
- source references, validation source IDs, review status, reviewers, review
  date, and change description.

Known generic teaching templates, fragments wrapped in templates, usage notes
used as translations, duplicated quiz options, mismatched senses, uncertain
pronunciation, and empty reviewer fields are invalid.

## Shared Enrichment and Review Flow

Use the existing shared commands and extend them once at their common boundary:

```text
pinned raw sources
  -> verified canonical JSONL
  -> deterministic target queue
  -> source-field merge
  -> Apple Translation for missing zh-Hant drafts
  -> Foundation Models for missing example/plain-expression/quiz/CEFR drafts
  -> fail-closed rich validation
  -> reviewed checkpoint shard
  -> reviewed shard index
  -> deterministic SQLite compiler
  -> bundled read-only VocabularyContent.sqlite
```

Field precedence is:

1. exact approved sense-aligned source field;
2. reviewed adaptation of approved source content;
3. reviewed `vocaby-original` field generated only because the source field was
   missing;
4. rejection.

Pronunciation never uses an unverified model draft. Resolve it through exact
approved IPA, converted Moby notation, conservative reviewed derivation from an
exact base, or individual `vocaby-original` review with auditory cross-check.
Uncertainty rejects the row.

## Batch, Review, Commit, and Push Cadence

Retain the current default enrichment batch size of 10 lessons. The additional
84,664 lessons therefore require 8,467 batches:

- 423 complete 20-batch boundaries of 200 lessons;
- one final partial boundary of 7 batches / 64 lessons;
- 424 reviewed checkpoint commits and pushes after the 15,336 baseline is
  complete.

At every boundary:

1. require contiguous, unique batch IDs and exact input/output ID parity;
2. require zero unresolved helper, translation, enrichment, or validation rows;
3. validate every sense, pronunciation reference, CEFR decision, quiz, source
   right, reviewer field, and target uniqueness;
4. scan the boundary and cumulative bank for generic templates and duplicate
   expressions;
5. review a deterministic sample for natural English, Taiwan zh-Hant, intended
   sense, level reasonableness, pronunciation, and distractor quality;
6. write a progress entry containing input hash, output hash, counts, rejection
   reasons, level/CEFR distribution, sample IDs, and reviewer;
7. run focused Python tests, source verification, `git diff --check`, and scoped
   diff review;
8. commit only the reviewed shard, progress/index update, source evidence or
   code/tests needed by that boundary;
9. push the checkpoint branch before beginning the next 20 batches.

The process is resumable. A completed shard is reusable only when its input,
source manifest, helper source, and configuration fingerprints match.

## Repository Artifact Layout

A single 100,000-row rich JSON file would exceed GitHub's practical single-file
limit. The canonical reviewed bank is therefore sharded by the user-approved
checkpoint boundary:

```text
Content/Reviews/vocabulary-100k/
  index.json
  baseline-15336.jsonl
  checkpoint-0001.jsonl
  checkpoint-0002.jsonl
  ...
  checkpoint-0424.jsonl
```

`index.json` records shard order, item count, SHA-256, first/last IDs, cumulative
count, source-manifest hash, and review status. Each checkpoint file contains at
most 200 rich rows. The index is the only accepted input to the release
compiler; unindexed files and mismatched hashes fail closed.

Generated `Content/Sources/Imported` and `Reports` remain ignored. Raw source
snapshots and rights evidence are tracked. No source, review, report, manifest,
or provenance path is added as an App resource.

## SQLite Content Database

### Build artifact

`VocabularyContent.sqlite` is a deterministic derived build artifact, not a
large binary committed at every checkpoint. A Python standard-library compiler
reads the reviewed shard index, validates the complete bank, writes a temporary
SQLite database inside one transaction, runs `PRAGMA integrity_check` and
foreign-key checks, closes it, verifies metadata/counts, and atomically replaces
the requested output.

The Xcode build invokes the compiler through one focused build script and places
the resulting database in the built App resources. The script references only
the compiler entry point in the project file; it does not add `Content/Reviews`
to an Xcode group or Copy Bundle Resources phase. Declared inputs/outputs let
Xcode skip an unchanged database build.

### Schema

Use native SQLite with no third-party iOS dependency. Keep the approved compact
schema:

- `metadata`: schema version, bank version, item count, reviewed-index SHA-256,
  source-manifest SHA-256, and creation/build format version;
- `lessons`: stable identity, three-level value, CEFR, sort order, languages,
  expressions, primary sense ID, and compact quiz payload;
- `senses`: lesson ID, stable sense ID/order, POS, bilingual meaning/example,
  and ordered pronunciation-ID payload;
- `pronunciations`: lesson ID, stable pronunciation ID/order, IPA, locale, and
  region.

Require primary/foreign keys and indexes on `(level, sort_order)`, normalized
expression, and child lesson/order fields. Store only promoted runtime fields;
full source provenance remains repository-only.

### Runtime access

Replace production whole-bank `SeedLoader.loadBundledSeed()` calls with one
concrete read-only `VocabularyContentStore` using the system SQLite module. Do
not add a generic repository interface.

The store:

- opens the bundled database read-only;
- validates schema version, count, and required metadata;
- reads only lightweight lesson index rows for selection/count operations;
- fetches complete lesson DTOs only for requested IDs;
- exposes level counts and bounded ordered candidate pages;
- never writes the bundled database;
- returns a localized unavailable-content state instead of partial data when
  validation or decoding fails.

Keep daily selection, review scheduling, day keys, and progress calculations as
small pure services. They consume bounded metadata/DTO results rather than
owning SQLite. SwiftData remains the only writer of first-seen, saved, learned,
quiz, and review state. Stable lesson IDs preserve all existing progress.

The App continues to use system speech for playback; IPA is display/reference
content, not bundled audio.

## App Behavior

- Today still selects 10 unseen lessons for the chosen level and fills with due
  review IDs according to the existing scheduling rules.
- My shows three level totals from SQLite and learned totals from SwiftData.
- Learned and Saved searches query only the relevant stable IDs and then fetch
  their content; no screen decodes all 100,000 lessons.
- Existing navigation, `TabView`, accessibility, localization, and
  `.tabBarMinimizeBehavior(.never)` behavior remain unchanged.
- No new dashboard, tab, custom tab bar, account, or online dictionary UI is
  introduced.

## Failure and Resume Behavior

- Source identity, rights, checksum, or required-notice failure stops before
  canonical import.
- Expanded Wiktextract snapshot mismatch leaves the current manifest and
  snapshot unchanged.
- Unknown Moby notation rejects the row with the exact source reference and
  symbol.
- Missing, duplicate, or extra enrichment/translation IDs fail the boundary.
- A worker failure preserves the last atomic checkpoint and resumes pending IDs.
- A draft with missing/low-confidence CEFR, pronunciation uncertainty, generic
  wording, or semantic mismatch is rejected and replaced by the next target.
- A reviewed-shard hash/count/order mismatch blocks cumulative audit and SQLite
  compilation.
- SQLite compilation writes no release artifact unless the full transaction,
  integrity checks, exact 100,000 count, and metadata checks pass.
- App database failure produces a clear localized unavailable state; it never
  silently falls back to an incomplete or stale partial bank.
- TestFlight upload success alone is not completion. The release remains active
  until Apple beta readiness is verified.

## Testing Strategy

Implementation follows test-driven development.

### Source and target tests

- Moby parsing/conversion, legacy encoding, unknown-symbol rejection, exact
  matching, and deterministic output.
- Existing and expanded Wiktextract targets reconcile exactly and exclude
  quotations/audio/images.
- Target selection preserves every retained ID, rejects ineligible tags, emits
  deterministic reserve candidates, and never duplicates an expression.
- Repeated canonical imports and target selection are byte-identical.

### Rich content and CEFR tests

- Every selected sense has its own enrichment and translation result.
- Known generic templates and incomplete examples fail.
- Exact CEFR overrides inference for the intended sense/POS.
- Inferred CEFR requires method, evidence, confidence, and reviewer metadata.
- A1/A2, B1/B2, and C1/C2 map to the three levels.
- Missing or conflicting unresolved CEFR fails.
- Quiz options are four unique same-level choices with one exact answer.
- Pronunciation IDs are nonempty, unique, valid, and applicable per sense.

### Shard and compiler tests

- Twenty 10-row batches produce one ordered 200-row checkpoint shard.
- The final 64-row partial checkpoint is accepted only at cumulative 100,000.
- Missing, reordered, duplicated, tampered, or unindexed shards fail.
- The compiler creates the four approved tables, expected indexes, valid foreign
  keys, exact metadata, and exactly 100,000 lesson rows.
- Two builds from the same index are byte-identical after canonical SQLite
  settings and deterministic insertion order.
- An error leaves the previous output unchanged.

### Swift tests

- Open/metadata validation and invalid-schema/count behavior.
- Level counts and index pagination.
- Complete lesson reconstruction with one to three senses and pronunciations.
- Missing child rows, invalid quiz payload, and bad pronunciation references
  fail closed.
- Daily selection preserves level/language/order, unseen, due-review, and
  exhaustion behavior using lightweight metadata.
- My level totals combine SQLite totals with SwiftData learned state.
- Existing progress IDs still resolve after content-store migration.
- The unavailable-content state is localized and accessible.

### Performance and manual QA

On a supported real iPhone and a release build:

- database open plus metadata validation completes in under one second;
- Today fetches its 10 lessons in under 200 ms;
- My count/search first-page queries complete in under 200 ms;
- Instruments confirms no whole-bank DTO decode or 100,000-row full-content
  allocation;
- normal and accessibility Dynamic Type pass in zh-Hant and English;
- the tab bar remains fully visible while scrolling;
- Today, Review, My, practice, pronunciation, quiz, notification, and widget
  flows remain functional offline.

## Release Plan

This is backward-compatible new functionality, so update the public version
from `1.0.0` to `1.1.0`:

- `VERSION` -> `1.1.0`;
- every App and widget `MARKETING_VERSION` -> `1.1.0`;
- add the `1.1.0` CHANGELOG entry;
- retain local `CURRENT_PROJECT_VERSION = 1`;
- let the manual TestFlight workflow override the build number with
  `GITHUB_RUN_ID`;
- do not create a `v1.1.0` tag for an internal TestFlight-only deployment.

Before dispatch:

1. verify all source snapshots and reviewed-shard index;
2. run the complete Python suite;
3. compile the database twice and compare it byte for byte;
4. run the complete Swift suite;
5. run a Release generic-iOS build;
6. inspect the built bundle for `VocabularyContent.sqlite` and
   `ThirdPartyNotices.txt` and the absence of seed/source/review/provenance data;
7. run `git diff --check` and verify clean branch status;
8. merge the reviewed implementation to `main` and push;
9. dispatch `.github/workflows/testflight.yml` on `main`;
10. monitor GitHub jobs and Apple processing until the helper reports both
    `processingState=VALID` and `internalBuildState=IN_BETA_TESTING` for public
    version `1.1.0` and build number equal to that run's `GITHUB_RUN_ID`.

## Acceptance Criteria

- Exactly 100,000 promoted lessons exist in the reviewed shard index and the
  bundled SQLite database.
- All original 14,064 IDs remain present; the deterministic 15,336 baseline
  quality plan is complete before expansion.
- Every lesson satisfies the rich contract and is directly usable by daily
  practice.
- Every lesson has exact or reviewed inferred CEFR evidence; App level matches
  CEFR and sort order is contiguous/deterministic within the level.
- Every lesson has at least one verified pronunciation and every sense has
  valid pronunciation references.
- No known generic template remains.
- Every contributing source is approved, checksum-valid, attributed, and
  represented in notices/provenance.
- The canonical reviewed bank is sharded, indexed, hash-verified, and committed
  at all 424 required post-baseline boundaries.
- Every 20 batches and the final partial boundary were reviewed, committed, and
  pushed before later work began.
- The App bundles the read-only SQLite database and notices but not
  `VocabularySeed.json`, raw sources, imports, reports, reviews, manifest, or
  provenance.
- SwiftData progress remains attached to stable lesson IDs.
- All automated, deterministic-build, performance, accessibility, localization,
  offline, Release-build, and bundle-content gates pass.
- `VERSION`, App/widget marketing versions, and CHANGELOG all report `1.1.0`.
- The final implementation is on `main`, pushed, and the exact GitHub Actions
  build is confirmed by Apple as `VALID` and `IN_BETA_TESTING`.

## Expected Implementation Surface

Keep source and review work in the current shared pipeline:

- `tools/vocabulary_sources.py` and its existing tests for Moby, target
  selection, exact/inferred CEFR validation, source verification, canonical
  imports, and promotion;
- `tools/review_vocabulary.py`, `tools/apple_language_services.swift`, and their
  existing tests for all-sense drafts, local translation/enrichment,
  checkpointing, rich validation, and shard construction;
- one focused standard-library SQLite compiler plus one focused test module;
- `Content/Sources`, the source manifest, reviewed checkpoint shards/index,
  provenance, notices, source/count policy, review/rejection/progress reports;
- one concrete Swift read-only content store and focused tests;
- minimal adaptations to the existing pure selection/library services and the
  three existing views that currently load the full seed;
- one Xcode resource-generation build phase using the compiler;
- `VERSION`, `CHANGELOG.md`, Xcode marketing versions, and existing TestFlight
  workflow verification.

Do not add parallel source-specific pipelines, runtime networking, a generic
repository layer, or a second user-progress database.
