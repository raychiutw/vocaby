# Question Bank Sources and Level Calibration

Status: implemented V1 policy
Last reviewed: 2026-07-17

This document defines how Vocaby imports, enriches, reviews, levels, and
ships vocabulary content. It is an engineering and editorial policy, not legal
advice.

## Product Boundary

- The SwiftUI app reads only `Vocaby/Resources/VocabularySeed.json` and
  the bundled `ThirdPartyNotices.txt`.
- The app has no runtime vocabulary download, account, sign-in, credential, API
  key, backend, iCloud, or sync path.
- Maintainers obtain and process sources locally. New content reaches users only
  in a new App build.
- Users can browse and practice the official bank but cannot edit, import, or
  replace it.
- `Content/Sources/Raw`, generated imports/reports, `Content/Reviews`, the
  source manifest, and `Content/VocabularyProvenance.json` are repository-only
  and must not be added to an Xcode target.

## Current Bundled Bank

Audit target: `Vocaby/Resources/VocabularySeed.json` on 2026-07-16.

| App level | CEFR range | Items |
|---|---|---:|
| `basic` | A1-A2 | 1,742 |
| `intermediate` | B1-B2 | 3,312 |
| `advanced` | C1-C2 | 9,010 |
| **Total** | A1-C2 | **14,064** |

All 14,064 IDs, upgraded expressions, and concept keys are unique. Sort order is
contiguous within each level. All 13,336 previously shipped item identities,
levels, sort orders, and upgraded expressions were preserved; 728 additional
reviewed items were added after expanding the approved pronunciation snapshot.
The review run rejected 1,272 of 15,336 candidates that lacked a verified or
composable pronunciation.

## Source Inventory and Shipping Decisions

Sixteen exact upstream snapshots and their evidence are tracked under
`Content/Sources/Raw`. A source being public or locally imported does not make it
eligible to ship.

| Source ID | Pipeline use | App use |
|---|---|---|
| `cefr-j-1.6` | exact CEFR calibration | approved |
| `cc-cedict-2026-07-11` | secondary Chinese gloss review | approved |
| `cow-0.9` | Chinese meaning tied to a PWN 3.0 sense | approved |
| `omw-ili-map-e3b5ac1` | exact PWN 3.0 to OEWN ILI alignment | approved |
| `oewn-2025` | English senses, definitions, examples, lexical relations | approved |
| `tatoeba-eng-cmn-2026-07-04` | context-aligned example translations | approved |
| `freedict-eng-zho-2025.11.23` | Chinese dictionary evidence; 1,532 selected references in this release | approved |
| `cmudict-7479086` | pronunciation cross-check; inline comments stripped before comparison | approved |
| `moby-pronunciator-ii-3205` | public-domain pronunciation coverage | approved |
| `grundwortschatz-voc-en-004977a` | English vocabulary and explicit A1-B2 evidence | approved |
| `bsl-1.2` | research candidate list | blocked |
| `gcide-0.54` | dictionary research | blocked |
| `nawl-1.2` | research candidate list | blocked |
| `ngsl-1.2` | research candidate list | blocked |
| `tsl-1.2` | research candidate list | blocked |
| `wiktextract-en-2026-07-09` | 108,000-target English Wiktionary POS, gloss, example, and IPA evidence in 10 verified shards | approved |

The shipping provenance catalog also contains `vocaby-original` for continuity
with the existing app bank. Exact versions, canonical URLs, hashes, license
evidence, rights fields, required notices, and current `appUse` decisions live in
`Content/Sources/source-manifest.json`.

An approved source must document commercial use, reproduction, redistribution,
modification, translated derivatives, attribution, notices, and indication of
changes. Reject unknown-license, account-gated, non-commercial-only,
no-derivatives, or incompatible material. Never change a checksum or rights field
only to make a release pass.

## Adapter Boundary and Shared Pipeline

Every raw source may have a different container, encoding, and record format.
That difference is intentionally confined to its adapter:

```text
raw snapshot -> source adapter -> canonical candidate JSONL
                                   |
                                   v
              shared selection and enrichment preparation
                                   |
                                   v
              shared Agent content build and review
                                   |
                                   v
              shared rights/provenance/notices/promotion gates
                                   |
                                   v
              bundled VocabularySeed.json + ThirdPartyNotices.txt
```

Adapters may parse CSV, TSV, dict, XLSX ZIP, JSON ZIP, gzip, bzip2, TEI TAR,
GCIDE TAR, ILI maps, or CMUdict. A source may declare one or several raw files.
Adapters must not contain source-specific translation, example, question,
reviewer, notice, or promotion behavior. After canonical JSONL, every source
uses the same commands and validation rules.

The common pipeline must keep the intended sense aligned across:

- upgraded expression and plain expression;
- English meaning and Taiwan Traditional Chinese meaning;
- example and example translation;
- one to three verified pronunciations and their locale/region labels;
- one to three common senses, each with POS and references to its applicable
  pronunciation IDs;
- English and zh-Hant prompts;
- correct option and distractor generation;
- exact CEFR, App level, source references, and reviewer fields.

Wiktextract is first snapshot-filtered to current seed targets with
`snapshot-wiktextract`; this avoids committing a full dump. Its manifest records
the exact dump/extractor identity and CC BY-SA evidence. Quotations, audio,
images, and externally licensed or fair-use media are excluded. CMUdict is
cross-check evidence only after stripping inline comments; OEWN plus the ILI map
anchors the intended sense. A usage note is never promoted as a meaning or an
example translation.

## Three-Level Model

Level the intended sense and usage, not spelling length or a frequency rank.

| App level | CEFR | Content profile |
|---|---|---|
| `basic` | A1-A2 | frequent everyday communication, transparent meaning, neutral register, simple grammar |
| `intermediate` | B1-B2 | common collocations and phrasal language, moderate idiomaticity, clearer register choices |
| `advanced` | C1-C2 | nuanced or context-sensitive register, lower-frequency collocations, polysemy, opaque idioms |

The shared selector uses CEFR-J evidence to propose the App level. It aligns the
COW PWN 3.0 sense to OEWN through an exact ILI mapping, checks definition
similarity locally with Apple's `NaturalLanguage`, and uses CC-CEDICT/Tatoeba as
secondary review evidence only when the intended sense and context agree.
Content review must verify the meaning, example, and prompts all teach that same
sense. Automated CEFR mapping is a release gate, not a claim of official learner
certification.

## Repository-Only Provenance and Notices

`Content/VocabularyProvenance.json` contains one record for every seed ID and a
catalog entry for every shipping source. It records source entry references,
change description, concept key, exact CEFR, App level, difficulty rubric,
Taiwan usefulness, reviewer identifiers, review date, and status.

The provenance file is never decoded by the App. Promotion requires a one-to-one
ID match between provenance and seed and rejects unapproved sources or incomplete
review fields.

`Vocaby/Resources/ThirdPartyNotices.txt` is generated deterministically
from required notices and retained license files. The App exposes it through a
native Settings screen; it does not open a web page or fetch license text.

## Repeatable Maintainer Workflow

Run from the repository root:

```sh
python3 tools/vocabulary_sources.py verify
python3 tools/vocabulary_sources.py import-all
python3 tools/vocabulary_sources.py report
python3 tools/vocabulary_sources.py prepare-enrichment \
  --input-dir Content/Sources/Imported \
  --existing-seed Content/Baselines/legacy-90.json \
  --current-seed Vocaby/Resources/VocabularySeed.json \
  --output /tmp/vocabulary-rich-review-queue.jsonl
python3 tools/review_vocabulary.py prepare \
  --queue /tmp/vocabulary-rich-review-queue.jsonl \
  --cmudict Content/Sources/Imported/cmudict-7479086.jsonl \
  --work-dir /tmp/wording-rich-review --batch-size 20
python3 tools/review_vocabulary.py run-local \
  --work-dir /tmp/wording-rich-review --workers 2
python3 tools/review_vocabulary.py build-reviewed \
  --work-dir /tmp/wording-rich-review \
  --output Content/Reviews/vocabulary-rich-2026-07-15.jsonl \
  --rejection-report docs/vocabulary-rejections-2026-07-15.md
python3 tools/vocabulary_sources.py audit-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-15.jsonl
python3 tools/vocabulary_sources.py build-reviewed \
  --input Content/Reviews/vocabulary-rich-2026-07-15.jsonl \
  --existing-seed Vocaby/Resources/VocabularySeed.json \
  --seed-output /tmp/VocabularySeed.rich.json \
  --provenance-output /tmp/VocabularyProvenance.rich.json \
  --notices-output /tmp/ThirdPartyNotices.rich.txt
python3 tools/vocabulary_sources.py promote \
  --reviewed /tmp/VocabularySeed.rich.json \
  --provenance /tmp/VocabularyProvenance.rich.json \
  --notices /tmp/ThirdPartyNotices.rich.txt \
  --output /tmp/VocabularySeed.promoted.json
```

For a new format, add one failing adapter test, implement only raw-to-canonical
normalization, and then rejoin this same workflow. Canonical source records may
carry `pronunciations` and `senses`; the shared review stage selects no more than
three useful senses and requires POS, bilingual meanings, full bilingual
examples, and valid per-sense pronunciation IDs. The resulting review JSONL is
tracked for maintainers but never linked to the app. Agent or local language
service output is not approved until `audit-reviewed`, deterministic
seed/provenance/notices builds, promotion, and release review pass. The reusable
operational guide is `.agents/skills/vocaby-vocabulary-import/SKILL.md`.

## Release Gates

Promotion fails before writing the output unless all of these hold:

- source files and evidence match declared size and SHA-256;
- every contributing source has approved rights and every required notice exists;
- seed and provenance IDs are unique and match one-to-one;
- concept keys and upgraded expressions are unique;
- every item has one to three valid pronunciations and one to three senses; each
  sense has a POS, valid pronunciation IDs, English and zh-Hant meanings, and
  complete bilingual example sentences;
- exact CEFR maps to the declared App level;
- sort order is unique, ascending, and contiguous within each level;
- correct quiz answers and pronunciation align with the item;
- source references, reviewer fields, status, and review date are complete;
- generated seed, provenance, and notices are byte-deterministic;
- generated questions contain four unique same-level options, and each generated
  example contains the target expression or an accepted inflection;
- the built App contains only the seed and notices, not raw/import/review/
  provenance data.

Automated gates prove structure, traceability, and deterministic behavior. The
shared review in `docs/content-review.md` separately checks natural English,
Taiwan Traditional Chinese, example quality, intended sense, and question
usefulness.

## Acceptance Criteria

- A clean install completes Today, Review, Library, five Practice Center modes,
  local TTS, notifications, and widget flows without a network or account.
- Every displayed word, meaning, example, prompt, and answer comes from the
  bundled bank.
- All 14,064 approved items have traceable approved source records and common
  review fields; every rejected source slot is documented.
- A clean two-run import/build produces byte-identical canonical and shipping
  artifacts.
- App resources contain no source snapshots, imports, reports, source manifest,
  or provenance database.

## Non-Goals

- On-device crawling, generation, translation, bank updates, or level inference.
- A remote content-management system, editable official bank, account, sync
  layer, or sync-ready abstraction.
- Treating a frequency rank or automated score as final CEFR certification.
