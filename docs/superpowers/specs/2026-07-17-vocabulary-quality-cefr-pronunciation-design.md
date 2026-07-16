# Vocabulary Quality, Exact CEFR, and Pronunciation Completion Design

**Date:** 2026-07-17
**Status:** Approved design direction; implementation pending
**Target bank version:** `2026.07.6`

## Context

Vocaby currently ships 14,064 approved lessons:

- basic: 1,742
- intermediate: 3,312
- advanced: 9,010

The complete deterministic candidate queue contains 15,336 lessons. The 1,272
candidate lessons that are not yet shipping all fail closed for the same reason:
`no-verified-pronunciation`.

A content audit found two additional quality problems in the current 14,064-row
reviewed bank:

- 3,831 senses in 3,401 lessons use one of two generic teaching templates rather
  than a natural example sentence.
- The reviewed builder replaces exact source CEFR with a level-wide constant:
  basic becomes A2, intermediate becomes B2, and advanced becomes C1.

The root causes are in the shared review path, not in the generated seed:

- `prepare_review` requests enrichment only for `senses[:1]`.
- `finish_enrichment` fabricates examples for secondary senses with
  `source_example`.
- deterministic repair data is also prepared only for the primary sense.
- `build_reviewed` hardcodes CEFR from the app level instead of reading the
  reviewed packet's exact CEFR evidence.

The approved direction is to fix the shared path once and execute the work in
this order:

1. A — repair examples and translations.
2. C — restore exact CEFR and derive the three app levels from it.
3. B — add verified pronunciation for all 1,272 rejected candidates and promote
   those lessons.

Every 20 completed enrichment batches must be reviewed before a progress commit.
The final partial boundary receives the same review and its own commit.

## Goals

### A — natural examples for every selected sense

- Replace every known generic template in the shipping bank with a natural,
  complete English sentence and a corresponding Taiwan Traditional Chinese
  translation.
- Make every sense, not only the primary sense, an explicit enrichment item.
- Prevent the shared pipeline from silently reintroducing either template.
- Preserve non-target lesson content and stable lesson identity.

### C — exact CEFR as the level authority

- Preserve exact A1, A2, B1, B2, and C1 evidence for every reviewed lesson.
- Derive app levels with the existing mapping:
  - A1 and A2 -> basic
  - B1 and B2 -> intermediate
  - C1 and C2 -> advanced
- Reclassify the 85 current lessons whose stored app level conflicts with their
  exact CEFR.
- Keep every lesson ID stable so local learning progress remains attached to the
  same concept.

### B — complete pronunciation coverage and import the rejected lessons

- Add an approved, pinned pronunciation source with useful new coverage.
- Complete pronunciation review for all 1,272 currently rejected candidates.
- Promote all 1,272 after they pass the same sense, bilingual content, quiz,
  rights, and deterministic-build gates as the existing bank.
- Finish with 15,336 shipping lessons and no candidate rejected solely for
  missing pronunciation.

## Non-goals

- Do not scrape, copy, or redistribute Google Translate pronunciations.
- Do not add runtime networking, a backend, an API client, or a pronunciation
  service to the app.
- Do not weaken source-rights, pronunciation, bilingual-content, or promotion
  validation to force a candidate into the bank.
- Do not regenerate unrelated meanings, quiz content, or reviewed examples while
  repairing the targeted template fields.
- Do not add a new workflow framework, database, dependency-injection layer, or
  generalized patch engine.
- Do not add `ipa-dict` for its single new overlap or restricted research-only
  pronunciation dictionaries that do not materially advance the target set.

## Source and Rights Policy

### Existing sources

The existing 15 manifest entries retain their current rights decisions. The
current CMUdict snapshot is already the latest upstream `master` commit
`74790861f652b15e4ac49015a90074ad62a27690`; updating it would add no data.

The 2026-07-06 English Wiktionary snapshot remains approved for selected IPA and
lexical evidence under its existing CC BY-SA 4.0 decision. Audio, images,
quotations, and externally licensed media remain excluded.

### Moby Pronunciator II

Add one manifest entry for the official Project Gutenberg distribution of Moby
Pronunciator II. Its documentation states that the database is public-domain
material by grant from the author.

Pin the exact downloaded artifact:

- canonical artifact: `https://www.gutenberg.org/files/3205/files/mpron.txt`
- retrieved: 2026-07-17
- rows: 177,266
- bytes: 5,493,251
- SHA-256:
  `55580c3b258873723fed33497fe3a438b26167370bbe016431b3fc65fea67f2d`

Store the public-domain grant and applicable distribution terms as local license
evidence. The source is not approved for app use until manifest verification,
checksum verification, notice review, adapter tests, and source review all pass.

An exact normalized-headword comparison currently finds 636 of the 1,272 rejected
candidates in Moby. This is expected coverage, not an acceptance count: entries
with unsupported notation, ambiguous identity, or failed review remain rejected.

### Derived and manually reviewed pronunciation

After direct approved-source matches, a deterministic derivation stage may
produce pronunciation candidates only for transparent inflections or derivations
whose base pronunciation is already verified. The initial audit finds 212 such
candidates using conservative forms such as `-ly`, `-ness`, `-ing`, `-ed`,
`-ment`, `-able`/`-ible`, and `-ize`/`-ise`.

Each derived candidate must:

- identify an exact verified base expression;
- apply a tested suffix rule, including allomorph selection where required;
- retain the base pronunciation source reference;
- add a `vocaby-original` review reference for the derivation;
- pass individual human content review before approval.

No rule is added solely to increase coverage. Opaque derivations, stress-changing
suffixes, uncertain stems, and unknown pronunciations remain in manual review.

The remaining expected 424 candidates are reviewed individually. Google
Translate or system speech may be used manually as an auditory cross-check, but
neither is a redistributable data source and neither appears in source references.
The approved IPA is recorded as reviewed `vocaby-original` content and must be
cross-checked against available approved lexical evidence. Uncertain rows fail
closed until resolved.

## Proposed Data Flow

### 1. Freeze and audit the current inputs

Before changing code or content:

1. Verify all current source snapshots and the current seed/provenance parity.
2. Record checksums for the full 15,336-row queue, current 14,064-row reviewed
   bank, seed, provenance, and notices.
3. Recompute target sets from content rather than a hand-maintained ID list:
   - template repair IDs;
   - exact CEFR evidence by ID;
   - pronunciation rejection IDs.
4. Require exact reconciliation with the audited counts in this design.

Any count or checksum drift is investigated before the repair run begins.

### 2. Fix all-sense enrichment at the shared stage

Change the existing review functions rather than adding a side pipeline:

- `prepare_review` emits one enrichment item for every selected sense.
- `finish_enrichment` expects the exact full set of lesson/sense IDs.
- secondary senses consume their own reviewed enrichment result instead of a
  primary-sense result plus `source_example`.
- deterministic repair preparation also covers every selected sense.

The known generic templates are invalid enrichment output. A source example may
be used only when it is already a complete natural sentence that contains the
target form. A fragment must not be wrapped in a generic teaching template.
Missing valid content fails closed and remains resumable for another review pass.

### 3. Run the targeted A repair

Build a deterministic repair queue for the 3,401 current lessons containing at
least one known template. Those lessons contain 5,221 selected senses. With the
existing batch size of 10, the repair has 523 enrichment batches.

Run at most 20 new batches per boundary. At each boundary:

1. verify completed batch IDs are contiguous and unique;
2. require exact input/output enrichment ID parity;
3. run enrichment validation for every completed item;
4. require zero unresolved error rows;
5. sample naturalness, target use, sense alignment, and Taiwan Traditional
   Chinese translation quality;
6. record boundary counts and output checksum in the progress artifact;
7. run `git diff --check`, review the scoped diff, and commit the checkpoint.

Boundaries occur after batches 20, 40, and so on through 520. Batches 521-523
form the final reviewed boundary and commit.

After enrichment, translate the new examples through the existing checkpointed
translation path. Deterministically merge only the approved example text and
`zh-Hant` example translation into the baseline reviewed rows. Meanings,
pronunciations, quiz content, source identity, and non-target rows remain
unchanged in phase A.

The merge is a tested shared command or function operating by stable lesson and
sense ID. It is not a manual JSON edit. Missing IDs, duplicate IDs, changed sense
identity, or an attempted change outside the approved example fields fails the
merge.

### 4. Apply exact CEFR and reclassify phase C

Read exact CEFR from the full review packet by stable ID. Do not infer CEFR from
the current app level.

For the current 14,064 lessons, the exact distribution is:

- A1: 836
- A2: 957
- B1: 1,667
- B2: 1,607
- C1: 8,997

This reclassifies 85 current lessons and produces these intermediate app counts:

- basic: 1,793
- intermediate: 3,274
- advanced: 8,997

Keep IDs unchanged. Reassign contiguous `sortOrder` values within each derived
app level by the lesson's previous global bank order, with ID as the final
deterministic tie-breaker. Preserve meanings, examples, pronunciations, and quiz
content.

Update reviewed CEFR and level, seed level and sort order, and provenance CEFR,
app level, and review metadata together. Exact CEFR coverage, app-level mapping,
seed/provenance ID parity, and contiguous sort order are promotion gates.

### 5. Import and convert Moby pronunciation

Add the smallest source adapter needed for Moby's documented ASCII
pronunciation notation:

1. decode the source artifact with its documented legacy byte encoding;
2. split headword, optional part-of-speech suffix, and pronunciation exactly;
3. replace source underscores with expression spaces;
4. normalize only through the existing expression normalizer;
5. convert documented phones, stress, syllable, and word boundaries to IPA;
6. emit canonical pronunciation records with exact source references.

Unknown source symbols, malformed stress, empty output, unsupported headwords,
and ambiguous part-of-speech identity are rejected with counted reasons. Moby
pronunciations are labeled `General`, using the app's existing General-English
locale convention rather than claiming unsupported US or UK specificity.

The adapter participates in the existing `verify`, `import-source`,
`import-all`, reporting, review, and provenance paths. No Moby-only promotion
path is added.

### 6. Complete the remaining B pronunciation review

Resolve pronunciation candidates in this order:

1. exact approved source IPA;
2. exact Moby entry converted by the reviewed adapter;
3. conservative derivation from an exact verified base pronunciation;
4. individual `vocaby-original` review with auditory cross-checks.

Rebuild the full queue with the new pronunciation evidence. All 1,272 previous
rejections must either become accepted or remain explicitly blocked with a
specific unresolved review reason. The requested outcome is reached only when all
1,272 are approved; lowering the pronunciation gate is not an alternative.

Run the newly accepted lessons through the same all-sense enrichment,
translation, audit, and 20-batch review/commit cadence. Preserve their existing
deterministic queue IDs. After promotion, the full exact CEFR distribution is:

- A1: 836
- A2: 957
- B1: 1,668
- B2: 1,611
- C1: 10,264

The final app-level counts are therefore:

- basic: 1,793
- intermediate: 3,279
- advanced: 10,264

Total: 15,336.

### 7. Build and promote atomically

Create a new dated full reviewed artifact for 2026-07-17 and remove the replaced
dated artifact in the same change so the repository retains one canonical full
review bank at HEAD.

Build seed, provenance, and notices twice from the same reviewed artifact into
separate temporary directories. Require byte-identical outputs, then promote all
three together:

- `Vocaby/Resources/VocabularySeed.json`
- `Content/VocabularyProvenance.json`
- `Vocaby/Resources/ThirdPartyNotices.txt`

Set provenance `bankVersion` to `2026.07.6`. Update source/count documentation and
the final quality/pronunciation progress report from generated evidence. A failed
audit or nondeterministic build leaves the previously shipping resources intact.

## Failure and Resume Behavior

- Source checksum, license, or manifest failure stops before import.
- Unknown Moby notation fails that row and reports the exact symbol and source
  entry reference.
- Missing, extra, or duplicate enrichment/translation IDs fail the boundary.
- Template output is invalid; deterministic template fallback is not allowed.
- A completed checkpoint is reusable only when its input and helper fingerprint
  match.
- A worker failure preserves the last valid atomic checkpoint.
- CEFR missing from any of the 15,336 packets, a CEFR/app-level mismatch, or
  noncontiguous sort order blocks promotion.
- Manual pronunciation review never cites Google Translate as source evidence.
- Review uncertainty remains an explicit rejection; validators are not weakened.
- Promotion is all-or-nothing.

## Testing Strategy

Implementation follows test-driven development.

### All-sense and example repair tests

- A two-sense packet emits two deterministic enrichment IDs.
- Every sense must have exactly one enrichment result.
- Secondary senses use their own enrichment result.
- Missing, extra, and duplicate sense IDs fail closed.
- Both known generic templates are rejected.
- A natural source sentence containing the target remains acceptable.
- Targeted merge changes only example text and Traditional Chinese example
  translation for approved lesson/sense IDs.
- Non-target rows and disallowed fields remain byte-equivalent in content.

### Exact CEFR tests

- `build_reviewed` reads packet CEFR rather than a level-wide constant.
- A1/A2, B1/B2, and C1/C2 map to the three app levels correctly.
- The 85-row mismatch fixture is reclassified without changing IDs.
- Reclassification preserves previous global order and creates contiguous level
  sort orders.
- Missing, invalid, or conflicting CEFR fails closed.
- Reviewed, seed, and provenance CEFR/app-level fields remain consistent.

### Moby adapter tests

- The parser handles headwords, phrases, optional part-of-speech suffixes, and
  legacy bytes.
- The documented phone inventory converts to expected IPA.
- Primary/secondary stress and word boundaries are retained.
- Unknown symbols and malformed records fail with actionable errors.
- Shuffled input produces byte-identical canonical JSONL.
- Exact target matching produces source references and never fuzzy-matches a
  neighboring headword.

### Pronunciation derivation tests

- Each enabled suffix rule has one positive and one unsafe negative example.
- `-ed` allomorph selection follows the verified final base phone.
- No derivation occurs without an exact verified base and source reference.
- Derived output carries base evidence plus `vocaby-original` review evidence.
- Opaque or stress-changing derivations remain manual-review rejections.

### Pipeline verification

Run at minimum:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest \
  tools/test_vocabulary_sources.py \
  tools/test_review_vocabulary.py
python3 tools/vocabulary_sources.py verify
python3 tools/vocabulary_sources.py audit-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-17.jsonl
```

Then:

- prove no known template remains in any reviewed sense;
- prove exact CEFR and final app-level counts for all 15,336 rows;
- prove all reviewed rows have at least one valid pronunciation;
- prove selected plus rejected accounting reconciles with 15,336 candidates;
- build and promote twice and compare seed, provenance, and notices byte for
  byte;
- run the full Swift test suite;
- build the app in Release configuration;
- inspect the built bundle for the exact canonical seed and notices and the
  absence of source, review, report, and provenance artifacts;
- run `git diff --check` and review the complete scoped diff.

## Acceptance Criteria

- The final reviewed bank, seed, and provenance contain exactly 15,336 matching
  stable IDs.
- No original 14,064 lesson ID is removed or replaced.
- All 1,272 prior pronunciation rejections are promoted with reviewed
  pronunciation evidence.
- Every final lesson has at least one valid pronunciation.
- No known generic teaching template remains in any sense.
- Every selected sense has a natural English example and Taiwan Traditional
  Chinese example translation.
- Exact CEFR counts are A1 836, A2 957, B1 1,668, B2 1,611, and C1 10,264.
- Final app-level counts are basic 1,793, intermediate 3,279, and advanced
  10,264.
- The 85 existing CEFR/app-level conflicts are resolved by deriving app level
  from exact CEFR.
- IDs remain stable and all level sort orders are contiguous and deterministic.
- Moby source integrity, rights evidence, adapter output, attribution, and notice
  pass the existing source gates.
- Google Translate does not appear in source references, provenance, notices, or
  redistributed content.
- Every 20-batch boundary and final partial boundary has reviewed evidence and a
  progress commit.
- Repeated builds are byte-identical, all automated tests pass, the Release build
  passes, and the App bundle contains no non-runtime source or review artifacts.

## Expected Code and Artifact Surface

Keep the implementation in the existing vocabulary pipeline:

- `tools/review_vocabulary.py` for all-sense enrichment, validation, resume, and
  targeted reviewed-field merge;
- `tools/vocabulary_sources.py` for exact CEFR, deterministic reclassification,
  the Moby adapter, conservative pronunciation derivation, source verification,
  and promotion;
- focused additions to the existing Python vocabulary/review test modules;
- one new Moby raw snapshot and its local rights evidence;
- the source manifest, normalized import, dated reviewed bank, rejection/progress
  reports, seed, provenance, notices, and source/count documentation.

No app runtime code change is expected. The current Swift models, local storage,
three-level UI, system speech, and learning-progress identity remain unchanged.
