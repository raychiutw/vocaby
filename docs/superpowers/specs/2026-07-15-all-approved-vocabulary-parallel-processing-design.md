# All-Approved Vocabulary Expansion and Parallel Processing Design

**Date:** 2026-07-15
**Status:** Approved design direction; implementation pending
**Target bank version:** `2026.07.4`

## Context

Vocaby currently ships 10,021 reviewed vocabulary lessons in `VocabularySeed.json`. The shipping provenance covers nine approved external sources. The source manifest contains 15 external sources in total: ten are approved for app use and five are blocked from shipping use. The remaining approved source, FreeDict English–Chinese, is imported and license-approved but does not yet contribute evidence to the shipping bank.

The existing preparation command has two modes that do not meet the requested outcome:

- With a current seed, it refreshes only the existing 10,021 lessons and cannot append new lessons.
- Without a current seed, it builds a quota-limited replacement bank, which would churn stable lesson identities and could disrupt local learning progress.

The local review pipeline already parallelizes enrichment, but `run-local --workers` performs translation in one serial helper invocation. A separate translation command already has parallel, checkpointed behavior and should be reused rather than duplicated.

## Goal

Build the largest deterministic, reviewable vocabulary bank that can legally and safely ship from the current source manifest, while preserving every existing lesson identity and processing both enrichment and translation with bounded parallel workers.

“All available” means every unique candidate produced by the shared import and preparation pipeline that passes all of the following gates:

- The contributing source is approved for app use.
- The source snapshot matches its pinned integrity metadata.
- The candidate can form an English expression-upgrade lesson rather than merely a raw dictionary row.
- CEFR level, sense, pronunciation, Traditional Chinese meaning, bilingual example, quiz answer, and distractors satisfy the existing validation rules.
- The candidate does not duplicate an existing or newly selected lesson identity.
- The evidence and attribution needed for every shipping field are traceable.

Raw dictionary entries, translations, pronunciation rows, or frequency records are evidence inputs; they are not automatically app lessons. A rejected candidate is counted and reported, not silently treated as imported content.

## Non-goals

- Do not bundle raw source snapshots, normalized imports, review work directories, or provenance audit data in the app.
- Do not add runtime networking, runtime importing, a backend, or a repository abstraction.
- Do not replace stable existing lesson IDs or reorder existing lessons.
- Do not make the five blocked sources contribute shipping fields, validation evidence, notices, or provenance catalog entries.
- Do not add a new concurrency framework, dependency, or multiple processes writing the same review work directory.
- Do not guarantee that every raw source row becomes a lesson.

## Source and Licensing Policy

All 15 manifest entries remain subject to checksum, metadata, and import-integrity verification. Only these ten approved external sources may contribute app content:

- `cefr-j-1.6`
- `cc-cedict-2026-07-11`
- `cmudict-7479086`
- `cow-0.9`
- `freedict-eng-zho-2025.11.23`
- `grundwortschatz-voc-en-004977a`
- `omw-ili-map-e3b5ac1`
- `oewn-2025`
- `tatoeba-eng-cmn-2026-07-04`
- `wiktextract-en-2026-07-09`

The following sources remain reference-only and must not appear in any shipping item's `sourceRefs` or `validationSourceIDs`, the shipping source catalog, or `ThirdPartyNotices.txt`:

- `bsl-1.2`
- `gcide-0.54`
- `nawl-1.2`
- `ngsl-1.2`
- `tsl-1.2`

Notices are evidence-driven: an approved source appears in the generated notice and provenance catalog only when at least one shipping item actually uses it. FreeDict's CC BY-SA 3.0 attribution must therefore be emitted when, and only when, aligned FreeDict evidence enters the final bank.

## Proposed Data Flow

### 1. Verify and normalize every source

Run manifest verification across all 15 sources. Import each pinned snapshot through the shared normalizer into canonical JSONL. Repeat normalization and compare outputs or checksums so source-specific ordering cannot affect the bank.

Any checksum, license classification, manifest ID, or normalized-schema mismatch fails closed before review work begins.

### 2. Add an append-all preparation mode

Extend `prepare-enrichment` with an explicit `--all-available` option used together with `--current-seed`.

The existing default behaviors remain unchanged. In append-all mode:

1. Load the current seed as the immutable identity base.
2. Produce review packets for all existing lessons so evidence can be rebuilt consistently.
3. Evaluate every remaining deterministic candidate from approved sources without basic/intermediate/advanced quotas.
4. Exclude candidates whose normalized lesson identity is already represented by an existing or newly selected lesson.
5. Preserve every existing ID and sort order.
6. Append new IDs deterministically and assign sort order after the current maximum within each level.
7. Emit selected and rejected accounting sufficient to prove that every candidate was handled.

The final count is not a preset target. It equals the existing 10,021 lessons plus every newly eligible unique lesson found by this mode.

### 3. Align FreeDict evidence conservatively

FreeDict translations use the normalized `zh` field and are converted to Traditional Chinese by the existing conversion path. They may support a lesson only when all relevant evidence aligns:

- normalized English headword or expression matches;
- part of speech is compatible when present;
- definition or sense evidence overlaps the selected English sense;
- the converted Chinese wording remains valid for that selected sense.

Stronger sense-aligned COW or CEDICT evidence remains preferred. FreeDict may be selected as fallback when stronger aligned Chinese evidence is absent, or recorded as corroborating evidence when it independently validates the chosen meaning. It enters `sourceRefs` only when its evidence materially contributes to the reviewed item. Headword-only matches or mismatched senses are rejected.

This logic belongs at the shared translation-selection and evidence-alignment point. It must not create a FreeDict-only side pipeline.

### 4. Run bounded parallel local review

Prepare a fresh dated work directory from the immutable review input. Run one review process with two workers:

- enrichment batches use the existing thread-pool execution;
- translation reuses the existing `run_local_translation(..., workers)` implementation so the same worker count, exact-ID validation, atomic checkpointing, and resume behavior apply.

Use two workers initially to balance throughput and local memory pressure. Do not launch two review CLIs against the same work directory because their last-writer-wins checkpoints are not a multi-process coordination mechanism.

A resume is valid only when the input artifact and helper source are unchanged. Otherwise, start a new dated work directory.

### 5. Review, reject, and audit

Create the tracked rich review artifact:

`Content/Reviews/vocabulary-rich-2026-07-15.jsonl`

Every selected row must be fully reviewed and approved before promotion. Record candidates that cannot pass the lesson contract in:

`docs/vocabulary-rejections-2026-07-15.md`

The rejection report must group failures by reason and source, include counts, and make selected plus rejected totals reconcile with the candidate set. It must not contain unbounded copies of copyrighted source text.

Run the rich-review audit before building any shipping resource. Missing fields, invalid correct options, duplicate IDs, non-approved source references, incomplete attribution, or source/sense mismatch block promotion.

### 6. Build deterministically and promote atomically

Build seed, provenance, and notices twice from the same reviewed artifact into separate temporary output directories. Require byte-identical outputs.

After both builds and audits pass, promote the three generated resources together:

- `Vocaby/Resources/VocabularySeed.json`
- `Content/VocabularyProvenance.json`
- `Vocaby/Resources/ThirdPartyNotices.txt`

Set provenance `bankVersion` to `2026.07.4` and update dated review metadata to 2026-07-15. Update `docs/question-bank-sources-and-levels.md` from generated final counts rather than retaining stale totals.

No partial output is promoted. A failure leaves all currently shipping resources untouched.

### 7. Keep the app bundle narrow

The runtime remains unchanged: `SeedLoader` decodes the bundled seed, and the app presents generated notices. The Xcode target must include only the shipping seed and notices from this workflow.

The following remain excluded from the app bundle:

- `Content/Sources/**`
- `Content/Reviews/**`
- `Content/VocabularyProvenance.json`
- review work directories and reports

## Failure and Resume Behavior

- Source integrity, license, or manifest failures stop before candidate preparation.
- Worker failures preserve the last atomic checkpoint and report the failed batch or chunk.
- Missing or duplicate translation IDs fail the local review run rather than producing partial rows.
- A rejected candidate is documented with a reason and never weakens validation to force inclusion.
- Audit or deterministic-build differences stop promotion.
- Promotion is all-or-nothing; the previous bank remains usable after any failed run.

## Testing Strategy

Implementation follows test-driven development for the new nontrivial behavior.

### Preparation tests

- Append-all mode preserves every existing ID, level, and sort order.
- It appends every eligible unique candidate and ignores the existing level quotas.
- New IDs and sort orders are deterministic across repeated runs and shuffled source input.
- Existing default quota and current-seed behavior remain unchanged when `--all-available` is absent.
- Duplicate, invalid CEFR, incomplete lesson, and blocked-source candidates are excluded and counted.

### FreeDict tests

- An aligned FreeDict translation can be selected and is attributed.
- A mismatched sense or part of speech is excluded.
- Simplified Chinese input follows the existing Traditional Chinese conversion path.
- FreeDict appears in the source catalog and notices only when at least one final item actually references it.
- Blocked source IDs cannot enter source references, validation evidence, catalog, or notices.

### Worker tests

- `run-local --workers 2` forwards the same worker count to translation.
- Parallel translation returns exactly one result per expected ID.
- Translation resumes from a valid checkpoint without recomputing completed IDs.
- A worker exception or missing/duplicate ID fails without corrupting the checkpoint.

### Pipeline verification

Run at minimum:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tools/test_vocabulary_sources.py tools/test_review_vocabulary.py
python3 tools/vocabulary_sources.py verify
python3 tools/vocabulary_sources.py audit-reviewed --input Content/Reviews/vocabulary-rich-2026-07-15.jsonl
```

Then build the reviewed artifact twice, compare the generated files byte-for-byte, promote, and rerun verification against the promoted resources.

Finally:

- run the full Xcode test suite;
- build the app in Release configuration;
- inspect the built app bundle and confirm it contains the seed and notices but no raw sources, review artifacts, or provenance audit file;
- run `git diff --check` and review the final scoped diff.

## Acceptance Criteria

- All original 10,021 lesson IDs remain present with unchanged identity, level, and sort order.
- The final bank contains those 10,021 lessons plus every newly eligible unique candidate discovered by append-all mode.
- Selected and rejected accounting reconciles with the complete candidate set.
- All ten approved external sources are represented by actual evidence in the final shipping provenance; FreeDict has at least one legitimate final `sourceRef`.
- No blocked source ID appears in final `sourceRefs`, `validationSourceIDs`, source catalog, or notices.
- Every newly added item passes the complete rich-review and seed-validation contracts.
- Repeated builds from the same review artifact are byte-identical.
- The app bundle contains only the required generated seed and notices, with no raw or audit content.
- Automated tests, source verification, rich-review audit, Release build, and bundle inspection all pass before the work is considered complete.

## Expected Code Surface

Keep the implementation scoped to the existing shared pipeline:

- `tools/vocabulary_sources.py` for append-all selection, FreeDict alignment, deterministic build metadata, and CLI wiring;
- `tools/review_vocabulary.py` to reuse parallel translation from `run-local`;
- focused tests in the existing vocabulary and review test modules;
- generated review, rejection, seed, provenance, notices, and source-count documentation artifacts.

No app runtime code change is expected unless verification reveals a seed-size or decoding regression.
