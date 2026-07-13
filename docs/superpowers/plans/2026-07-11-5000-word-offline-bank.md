# 5,000+ Offline Vocabulary Bank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship at least 5,000 reviewed, read-only vocabulary items inside the offline iOS app while keeping all upstream file-format handling before one shared enrichment, review, and promotion pipeline.

**Architecture:** Every source-specific adapter emits the same candidate JSONL schema. A single post-adapter pipeline selects candidates, enriches them into App seed fields, records multi-source provenance, validates rights/content/level/duplicate gates, generates notices, and promotes deterministic resources. The App never reads raw/imported/editorial files and never performs network or account work.

**Tech Stack:** Python 3 standard library for source/build tooling, OpenCC 1.4.0 with `s2twp.json` for maintainer-time Taiwan Traditional Chinese conversion, Swift/Foundation and SwiftUI for the native iOS app, XCTest for App validation.

## Global Constraints

- iOS 17+, native SwiftUI, Traditional Chinese and English UI.
- Fully local storage; no account, sign-in, backend, iCloud, remote question bank, credential, token, or runtime network path.
- `Content/Sources/Raw` is tracked but never included in an Xcode target.
- Users cannot add, edit, delete, or replace official bank content.
- Source-specific code ends at candidate JSONL; translation, example, question, provenance, review, and promotion logic is shared.
- Final bank count is at least 5,000 and every item passes the same deterministic structural gate.
- Use existing `VocabularySeedItem`; do not add sync, repository, DI, or speculative content-management abstractions.
- Preserve the existing 90 item IDs and local progress compatibility.
- Add no App runtime dependency. OpenCC is allowed only for maintainer-time bank regeneration; generated resources are committed so normal App builds do not require it.

---

### Task 1: Extend the canonical candidate schema

**Files:**
- Modify: `tools/test_vocabulary_sources.py`
- Modify: `tools/vocabulary_sources.py`

**Interfaces:**
- Produces candidate records with `definitions: [String]`, `examples: [String]`, `relatedTerms: [String]`, and existing provenance fields.
- All adapters emit the same keys; adapters that lack a field emit an empty collection.

- [ ] **Step 1: Write the failing OEWN fixture test**

Create a temporary ZIP containing one `entries-a.json` and one `adj.all.json`. Assert `import-source` returns the definition, example, and both synset members in `relatedTerms`.

- [ ] **Step 2: Verify RED**

Run `python3 -m unittest tools.test_vocabulary_sources.VocabularySourcesTests.test_oewn_candidate_contains_shared_enrichment_inputs`.

Expected: FAIL because candidates currently omit `examples` and `relatedTerms` and OEWN entries do not join synsets.

- [ ] **Step 3: Implement the smallest shared schema change**

Add empty arrays in `empty_record`, load OEWN synset JSON once, and merge each entry's referenced synset definition/example/members. Extend `merge_records` list merging to the two new fields.

- [ ] **Step 4: Verify GREEN and all adapters**

Run `python3 -m unittest tools/test_vocabulary_sources.py` and one full `import-all`; expect all tests and all ten adapters to pass.

- [ ] **Step 5: Commit**

Commit as `feat: enrich canonical vocabulary candidates`.

### Task 2: Add the one shared enrichment and review pipeline

**Files:**
- Modify: `tools/test_vocabulary_sources.py`
- Modify: `tools/vocabulary_sources.py`
- Modify: `.gitignore`

**Interfaces:**
- `prepare-enrichment --input-dir PATH --existing-seed PATH --count 5310 --output PATH` writes source-neutral enrichment candidates.
- `build-reviewed --input PATH --seed-output PATH --provenance-output PATH --notices-output PATH` uses one enrichment implementation for every source.
- Output seed uses the existing `VocabularySeedItem` JSON shape; provenance records `sourceIDs: [String]`.

- [ ] **Step 1: Write failing shared-pipeline tests**

Use small canonical fixtures from differently named sources. Assert both pass through the same command and receive complete `plainExpression`, `upgradedExpression`, English/zh-Hant meanings, matched example/translation, pronunciation, localized prompts, options, CEFR/app level, and multi-source provenance. Assert duplicate targets and insufficient level quotas fail.

- [ ] **Step 2: Verify RED**

Run the two new unittest methods; expect argparse to reject the missing commands.

- [ ] **Step 3: Implement selection and enrichment**

Index canonical OEWN, FreeDict, and CEFR-J records by normalized headword/POS. Preserve the existing 90 items, select exactly 5,310 new unique targets with deterministic quotas of 1,000 basic, 1,600 intermediate, and 2,710 advanced, and prefer candidates with real source definitions/examples and a distinct simpler synonym. Use the definition only when no valid synonym exists.

Convert draft Chinese through one OpenCC 1.4.0 `s2twp.json` batch, then apply the fixed Taiwan substitutions `軟件→軟體`, `計算機→電腦`, `信息→資訊`, `網絡→網路`, `程序→程式`, `打印→列印`, and `質量→品質`. The same enrichment function creates every App field; no adapter-specific translation/example/question branch is allowed. Fail with an install command when OpenCC is unavailable.

- [ ] **Step 4: Implement shared review outputs**

Write deterministic reviewed seed, `Content/VocabularyProvenance.json`, and `ThirdPartyNotices.txt`. Mark generated content `agent-enriched`, record all contributing source IDs and source entry references, and use stable reviewer ID `codex-content-review-2026-07-11`.

- [ ] **Step 5: Verify GREEN and determinism**

Run the unittest file, generate twice into separate temporary directories, and compare SHA-256 for seed/provenance/notices. Expect byte-identical outputs and 5,400 total seed items.

- [ ] **Step 6: Commit**

Commit as `feat: add shared vocabulary enrichment pipeline`.

### Task 3: Strengthen the common promotion gate

**Files:**
- Modify: `tools/test_vocabulary_sources.py`
- Modify: `tools/vocabulary_sources.py`
- Modify: `Content/Sources/source-manifest.json`
- Modify: `Content/Sources/README.md`

**Interfaces:**
- `promote` accepts provenance `sourceIDs` and validates every referenced source.
- App-use approval remains source catalog data, not adapter behavior.

- [ ] **Step 1: Write failing multi-source rights tests**

Assert promotion fails when any source in `sourceIDs` is blocked, any required notice is absent, CEFR does not belong to the app level, example/translation/prompt fields are empty, or normalized upgraded expressions collide.

- [ ] **Step 2: Verify RED**

Run only the new tests; expect failures because `promote` currently reads one `sourceID` and does not validate all shared content gates.

- [ ] **Step 3: Implement minimal common validation**

Validate all `sourceIDs`, all required seed subfields, A1-A2/basic, B1-B2/intermediate, C1-C2/advanced mapping, reviewer/status fields, contiguous sort order, unique IDs/concepts/upgraded expressions, and required notices. Do not add a per-source validator.

- [ ] **Step 4: Record approved use decisions**

Set exact reviewed versions of OEWN, FreeDict, and CEFR-J to `approved` only for the documented adapted bank workflow; retain other sources as reference-only or blocked. Update README with attribution/share-alike handling.

- [ ] **Step 5: Verify GREEN**

Run all Python tests, `verify`, `promote` into a temporary file, and compare it byte-for-byte with the generated seed.

- [ ] **Step 6: Commit**

Commit as `feat: validate reviewed vocabulary promotion`.

### Task 4: Ship the 5,400-item local bank and notices

**Files:**
- Modify: `Vocaby/Resources/VocabularySeed.json`
- Create: `Vocaby/Resources/ThirdPartyNotices.txt`
- Create: `Content/VocabularyProvenance.json`
- Modify: `Vocaby.xcodeproj/project.pbxproj`
- Modify: `VocabyTests/VocabularySeedValidationTests.swift`

**Interfaces:**
- `SeedLoader.loadBundledSeed()` remains unchanged and decodes 5,400 bundled items.
- App bundles only `VocabularySeed.json` and `ThirdPartyNotices.txt`; provenance and all source folders stay repository-only.

- [ ] **Step 1: Write the failing App bank test**

Change the expected total to 5,400 and assert level counts 1,030 basic, 1,630 intermediate, and 2,740 advanced, all IDs/expressions unique, every level has enough distractors, and no generated item has empty zh-Hant/example/prompt fields.

- [ ] **Step 2: Verify RED**

Run the vocabulary seed XCTest; expect 90 instead of 5,400 and no notices resource.

- [ ] **Step 3: Generate and add resources**

Run the common pipeline, promote to `VocabularySeed.json`, add only `ThirdPartyNotices.txt` to the App Resources group/build phase, and leave `Content/VocabularyProvenance.json` outside the project.

- [ ] **Step 4: Verify GREEN**

Run the focused XCTest and inspect the built `.app`: seed and notices must exist; `Content/Sources`, raw archives, manifest, imported JSONL, and provenance must not exist.

- [ ] **Step 5: Commit**

Commit as `feat: ship 5400-word offline bank`.

### Task 5: Add the native read-only source notice screen

**Files:**
- Modify: `Vocaby/Features/Settings/SettingsView.swift`
- Modify: `Vocaby/Resources/Localizable.xcstrings`
- Modify: `VocabyTests/LocalizationCoverageTests.swift`

**Interfaces:**
- `ThirdPartyNoticesView` reads the bundled text with `Data(contentsOf:)`/`String(contentsOf:)` only.
- Settings exposes one native `NavigationLink`; there are no edit/import/download controls.

- [ ] **Step 1: Write failing localization coverage expectations**

Require zh-Hant/en keys for source notices title, row label, and fallback text.

- [ ] **Step 2: Verify RED**

Run localization tests; expect missing keys.

- [ ] **Step 3: Add the minimal native UI**

Add a Settings `Section` with a `NavigationLink` and a `ScrollView`/`Text` detail. Load only the bundled notice, preserve Dynamic Type/selectability, and show localized fallback on read failure.

- [ ] **Step 4: Verify GREEN**

Run localization/unit tests and simulator checks in zh-Hant, English, and accessibility Dynamic Type. Confirm no official-bank edit affordance exists.

- [ ] **Step 5: Commit**

Commit as `feat: show vocabulary source notices`.

### Task 6: Update the reusable skill and documentation

**Files:**
- Modify: `.agents/skills/vocaby-vocabulary-import/SKILL.md`
- Modify: `.agents/skills/vocaby-vocabulary-import/assets/evals/evals.json`
- Modify: `.agents/skills/vocaby-vocabulary-import/references/quality_checklist.md`
- Modify: `docs/question-bank-sources-and-levels.md`
- Modify: `docs/content-review.md`

**Interfaces:**
- The skill names the adapter boundary, shared candidate schema, common Agent enrichment, common review, and common promote commands.

- [ ] **Step 1: Add a failing eval expectation**

Add a prompt with two different source formats and require one shared post-adapter enrichment/review flow. The old skill text is the RED evidence because it does not yet name `prepare-enrichment`/`build-reviewed`.

- [ ] **Step 2: Update workflow and review docs**

Document that source-specific behavior ends at candidate JSONL and that all translations, examples, questions, reviewer IDs, provenance, notices, and release gates are common.

- [ ] **Step 3: Run skill checks**

Run strict format, quick validation, OpenClaw frontmatter, references, unreferenced files, packaging, and archive integrity checks; update the quality checklist with exact evidence.

- [ ] **Step 4: Commit**

Commit as `docs: document shared vocabulary enrichment`.

### Task 7: Full completion audit

**Files:**
- Modify only files required by failures found in this task.

- [ ] **Step 1: Run all deterministic content checks**

Run Python unit tests, source verification, two clean full generations with checksum comparison, promotion, bank/provenance count and one-to-one ID checks, duplicate scan, and Xcode resource exclusion scan.

- [ ] **Step 2: Run the complete iOS verification stack**

Run a clean simulator XCTest build for all test targets and a Release simulator build. Inspect the built App and widget bundles for forbidden source/runtime-network artifacts.

- [ ] **Step 3: Run offline/security/static checks**

Search Swift/project/entitlements for URLSession, HTTP endpoints, WebSocket, Network, CloudKit, iCloud, login, account, credential, API key, and source-folder references. Confirm no matches beyond non-runtime documentation/local Settings APIs.

- [ ] **Step 4: Run manual simulator QA**

Verify Today, Review, Library search/detail, all five practice modes, source notices, zh-Hant/en, normal/accessibility Dynamic Type, and airplane/offline behavior.

- [ ] **Step 5: Audit requirements and commit fixes**

Map every user requirement and acceptance criterion to evidence. Fix any missing item with RED-GREEN before claiming completion. Run `git diff --check`, ensure a clean branch, and do not push unless requested.
