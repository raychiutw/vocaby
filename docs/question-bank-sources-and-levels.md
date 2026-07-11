# Question Bank Sources and Level Calibration

Status: implemented V1 policy
Last reviewed: 2026-07-11

This document defines how Wording Daily imports, enriches, reviews, levels, and
ships vocabulary content. It is an engineering and editorial policy, not legal
advice.

## Product Boundary

- The SwiftUI app reads only `WordingDailyApp/Resources/VocabularySeed.json` and
  the bundled `ThirdPartyNotices.txt`.
- The app has no runtime vocabulary download, account, sign-in, credential, API
  key, backend, iCloud, or sync path.
- Maintainers obtain and process sources locally. New content reaches users only
  in a new App build.
- Users can browse and practice the official bank but cannot edit, import, or
  replace it.
- `Content/Sources/Raw`, generated imports/reports, the source manifest, and
  `Content/VocabularyProvenance.json` are repository-only and must not be added
  to an Xcode target.

## Current Bundled Bank

Audit target: `WordingDailyApp/Resources/VocabularySeed.json` on 2026-07-11.

| App level | CEFR range | Items |
|---|---|---:|
| `basic` | A1-A2 | 1,030 |
| `intermediate` | B1-B2 | 1,630 |
| `advanced` | C1-C2 | 2,740 |
| **Total** | A1-C2 | **5,400** |

All 5,400 IDs, upgraded expressions, and concept keys are unique. Sort order is
contiguous within each level. The 90 project-owned legacy items were cleaned and
preserved; the other 5,310 items were selected from approved local source data
and passed the shared enrichment and promotion gates.

## Source Inventory and Shipping Decisions

Ten exact upstream snapshots and their evidence are tracked under
`Content/Sources/Raw`. A source being public or locally imported does not make it
eligible to ship.

| Source ID | Pipeline use | App use |
|---|---|---|
| `cefr-j-1.6` | exact CEFR calibration | approved |
| `freedict-eng-zho-2025.11.23` | Chinese meaning evidence | approved |
| `oewn-2025` | English senses, definitions, examples, lexical relations | approved |
| `cmudict-7479086` | pronunciation research | reference only |
| `cow-0.9` | frequency research | reference only |
| `bsl-1.2` | research candidate list | blocked |
| `gcide-0.54` | dictionary research | blocked |
| `nawl-1.2` | research candidate list | blocked |
| `ngsl-1.2` | research candidate list | blocked |
| `tsl-1.2` | research candidate list | blocked |

The shipping provenance catalog also contains `wording-daily-original` for the
90 project-owned legacy items. Exact versions, canonical URLs, hashes, license
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

Adapters may parse CSV, TSV, dict, XLSX ZIP, JSON ZIP, TEI TAR, GCIDE TAR, or
CMUdict. They must not contain source-specific translation, example, question,
reviewer, notice, or promotion behavior. After canonical JSONL, every source uses
the same commands and validation rules.

The common pipeline must keep the intended sense aligned across:

- upgraded expression and plain expression;
- English meaning and Taiwan Traditional Chinese meaning;
- example and example translation;
- pronunciation text;
- English and zh-Hant prompts;
- correct option and distractor generation;
- exact CEFR, App level, source references, and reviewer fields.

## Three-Level Model

Level the intended sense and usage, not spelling length or a frequency rank.

| App level | CEFR | Content profile |
|---|---|---|
| `basic` | A1-A2 | frequent everyday communication, transparent meaning, neutral register, simple grammar |
| `intermediate` | B1-B2 | common collocations and phrasal language, moderate idiomaticity, clearer register choices |
| `advanced` | C1-C2 | nuanced or context-sensitive register, lower-frequency collocations, polysemy, opaque idioms |

The shared selector uses CEFR-J evidence to propose the App level. Content review
must verify the selected OEWN sense, FreeDict meaning, example, and prompts all
teach that same sense. Automated CEFR mapping is a release gate, not a claim of
official learner certification.

## Repository-Only Provenance and Notices

`Content/VocabularyProvenance.json` contains one record for every seed ID and a
catalog entry for every shipping source. It records source entry references,
change description, concept key, exact CEFR, App level, difficulty rubric,
Taiwan usefulness, reviewer identifiers, review date, and status.

The provenance file is never decoded by the App. Promotion requires a one-to-one
ID match between provenance and seed and rejects unapproved sources or incomplete
review fields.

`WordingDailyApp/Resources/ThirdPartyNotices.txt` is generated deterministically
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
  --output /tmp/wording-draft.jsonl
python3 tools/vocabulary_sources.py build-reviewed \
  --input /tmp/wording-draft.jsonl \
  --existing-seed Content/Baselines/legacy-90.json \
  --seed-output /tmp/wording-seed.json \
  --provenance-output /tmp/wording-provenance.json \
  --notices-output /tmp/wording-notices.txt
python3 tools/vocabulary_sources.py promote \
  --reviewed /tmp/wording-seed.json \
  --provenance /tmp/wording-provenance.json \
  --notices /tmp/wording-notices.txt \
  --output /tmp/VocabularySeed.json
```

For a new format, add one failing adapter test, implement only raw-to-canonical
normalization, and then rejoin this same workflow. The reusable operational guide
is `.agents/skills/wording-daily-vocabulary-import/SKILL.md`.

## Release Gates

Promotion fails before writing the output unless all of these hold:

- source files and evidence match declared size and SHA-256;
- every contributing source has approved rights and every required notice exists;
- seed and provenance IDs are unique and match one-to-one;
- concept keys and upgraded expressions are unique;
- required English and zh-Hant meanings, examples, translations, prompts, and
  pronunciation text are non-empty;
- exact CEFR maps to the declared App level;
- sort order is unique, ascending, and contiguous within each level;
- correct quiz answers and pronunciation align with the item;
- source references, reviewer fields, status, and review date are complete;
- generated seed, provenance, and notices are byte-deterministic;
- the built App contains only the seed and notices, not raw/import/provenance data.

Automated gates prove structure, traceability, and deterministic behavior. The
shared review in `docs/content-review.md` separately checks natural English,
Taiwan Traditional Chinese, example quality, intended sense, and question
usefulness.

## Acceptance Criteria

- A clean install completes Today, Review, Library, five Practice Center modes,
  local TTS, notifications, and widget flows without a network or account.
- Every displayed word, meaning, example, prompt, and answer comes from the
  bundled bank.
- All 5,400 items have traceable approved source records and common review fields.
- A clean two-run import/build produces byte-identical canonical and shipping
  artifacts.
- App resources contain no source snapshots, imports, reports, source manifest,
  or provenance database.

## Non-Goals

- On-device crawling, generation, translation, bank updates, or level inference.
- A remote content-management system, editable official bank, account, sync
  layer, or sync-ready abstraction.
- Treating a frequency rank or automated score as final CEFR certification.
