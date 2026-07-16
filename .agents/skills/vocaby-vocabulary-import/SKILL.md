---
name: vocaby-vocabulary-import
description: Use when importing or re-importing an external Vocaby vocabulary source, including Wiktextract, CMUdict, OEWN, CSV, TSV, XLSX, ZIP, TAR, TEI, or JSON; or when producing and auditing rich review JSONL before promoting the bundled bank. 適用於新增詞庫、重跑來源檔、補強多讀音多詞義、翻譯例句題目與審核上架；不適用於 App runtime 下載、登入同步、一般試算表整理或略過權利審核。
version: 2026.7.16
homepage: https://github.com/raychiutw/vocaby
license: Proprietary
metadata: {"author":"Vocaby"}
---

# Vocaby vocabulary import

This skill owns the maintainer pipeline that turns external source snapshots into
reproducible candidate JSONL and, when shipping was requested, passes candidates
through one shared enrichment, review, provenance, notice, and promotion path.
The app remains offline and reads only its reviewed bundled seed.

## Single responsibility

- Primary job: run the repository's repeatable source-to-reviewed-bank pipeline.
- Source-specific responsibility ends at canonical candidate JSONL. Translation, example, question, provenance, notice, review, and promotion logic is shared across every source.
- Not this skill's job: download data at app runtime, approve ambiguous licenses, or design quiz UI.
- Split / handoff rule: use a browser or spreadsheet skill only to obtain or inspect an upstream artifact, then return here for manifest, adapter, shared enrichment, review, and release gates.

<role>
Act as the Vocaby content-pipeline maintainer. Preserve exact upstream
snapshots, fail closed on rights or integrity uncertainty, and keep candidate
data separate from reviewed App content.
</role>

<decision_boundary>
Use when:
- adding a new dictionary, word list, pronunciation list, or lexical dataset;
- re-running a source after its file/version/checksum changes;
- checking source integrity, candidate counts, duplicate headwords, or build exclusion;
- enriching canonical candidates into App-shaped translations, examples, and questions;
- reviewing and promoting a local seed, provenance manifest, and notice file.

Do not use when:
- changing UI, quiz behavior, notification behavior, or SwiftData;
- editing a few Vocaby-authored seed items with no external source;
- scraping an unrelated website or transforming a generic spreadsheet;
- adding any network, account, credential, sync, or remote-bank path to the app.

Inputs:
- repository root containing `tools/vocabulary_sources.py`;
- one or more raw source files plus canonical source/version/license evidence;
- for enrichment, canonical JSONL plus the committed legacy baseline;
- for promotion, reviewed seed JSON, provenance JSON, and notices text.

Successful output:
- the source snapshot is declared and checksum-verified;
- a repeatable source adapter produces deterministic canonical candidate JSONL;
- all later fields are produced and reviewed by the common pipeline;
- current app-use status and all blocking gates are explicit;
- `Content/Sources` remains absent from the Xcode project.
</decision_boundary>

## Primary use cases

1. **Add one source**
   - Triggers: "匯入新的 CEFR 詞庫", "add this TEI dictionary source".
   - Inputs: upstream file, official URL, version, license evidence.
   - Done: raw snapshot and manifest are tracked; verify/import/report pass.
2. **Re-import a changed source**
   - Triggers: "這個 XLSX 更新了，重跑字庫", "refresh the OEWN archive".
   - Inputs: new exact file/version and reviewed license changes.
   - Done: old checksum fails before metadata changes; new snapshot imports deterministically.
3. **Build and promote reviewed content**
   - Triggers: "補強翻譯例句與題目後放入 App", "promote the reviewed local bank".
   - Inputs: canonical imports, legacy baseline, complete rights evidence.
   - Done: the common enrichment/review path emits seed, provenance, and notices; every promotion gate passes and only approved runtime resources are bundled.

## Routing boundaries

- No repo-local skill overlaps this workflow.
- `spreadsheets` may inspect XLSX/CSV but does not own source rights, checksums, canonical JSONL, or promotion.
- `scrape` may retrieve an official page but does not own vocabulary normalization or App gates.
- `skillify` captures browser flows; it does not import lexical data.
- Negative triggers: generic CSV cleanup, unrelated translation writing, app runtime downloads, UI work, and login/sync tasks.

## Language and host coverage

- Trigger languages: Traditional Chinese, English, and mixed prompts such as "重跑 OEWN JSON ZIP".
- Treat 字庫, 詞庫, 題庫來源, source file, dataset, dictionary, import, ingest, and re-import as equivalent routing terms in this repository.
- Primary host: Codex working in this repository. The Markdown workflow is portable to other filesystem agents that can run Python 3.
- Mutable candidate outputs live under ignored `Content/Sources/Imported/` and `Content/Sources/Reports/`. Reviewed JSONL lives under tracked `Content/Reviews/`. None belongs inside this skill folder or an Xcode target.

## Canonical rich contract

- A source adapter may emit structured `pronunciations` and `senses`, but it stops at canonical candidate JSONL.
- A reviewed item has one to three common senses and one or more verified pronunciations. Each sense has a stable ID, supported part of speech, English and Taiwan Traditional Chinese meanings, a complete English example and faithful full-sentence zh-Hant translation, and nonempty `pronunciationIDs` that reference the item's pronunciations.
- Wiktextract contributes cleaned POS, gloss, translation, example, and IPA evidence only. Exclude quotations, audio, images, and usage-note translations.
- Cross-check intended senses with exact OEWN/ILI evidence. Cross-check pronunciation with Wiktextract and CMUdict; strip CMUdict inline ` #...` comments before comparing variants.
- Agent or local Apple language-service output is a draft. It is not approved App content until the complete review JSONL passes `audit-reviewed`, deterministic build/promotion, and release review.

<workflow>
Step 0: Read the repository contract
- Read `AGENTS.md`, `Content/Sources/README.md`, `Content/Sources/source-manifest.json`, and the relevant source policy in `docs/question-bank-sources-and-levels.md`.
- Inspect current Git status and preserve unrelated user changes.
- Stop if the request implies an App runtime download, credential, login, or remote bank.

Step 1: Establish source identity and rights
- Prefer an already provided local file. Browse/download only when the user explicitly asks for a new external source.
- Use the owner's canonical URL; record exact version or retrieval date and retain license evidence beside the raw file.
- Put the exact snapshot under `Content/Sources/Raw/<source-id>/`.
- Default `appUse` to `reference_only` or `blocked`. Never infer `approved` from public availability, a permissive code license, or a source page alone.
- For Wiktextract, retain official Wiktextract/Wiktionary license evidence and record the exact dump and extractor revisions. The manifest decision must exclude quotations, audio, images, and externally licensed or fair-use media.
- Stop on unknown, account-gated, non-commercial, no-derivatives, or conflicting terms.

Step 2: Declare the source
- Compute SHA-256 and byte count for every raw file and evidence file. Use
  `rawFiles` when one logical source requires several linked archives.
- Add exactly one unique entry to `Content/Sources/source-manifest.json`.
- Reuse an existing adapter when its real file format matches. Add the smallest parser branch and one failing test first only when no adapter matches.
- Declare non-UTF-8 encodings explicitly; do not guess silently.
- For a large Wiktextract dump, snapshot only current seed targets instead of committing the full dump:

```sh
python3 tools/vocabulary_sources.py snapshot-wiktextract \
  --source-url <official-jsonl-gz-url> \
  --seed Vocaby/Resources/VocabularySeed.json \
  --output Content/Sources/Raw/wiktextract-en/<snapshot>.jsonl.gz
```

Record the printed byte count and SHA-256 in the manifest before verification.

Step 3: Verify before parsing
- Run `python3 tools/vocabulary_sources.py verify --source <source-id>`.
- On a mismatch, leave the old manifest untouched until the changed upstream file/version/license is understood.
- Confirm `Content/Sources` is absent from `Vocaby.xcodeproj/project.pbxproj`.

Step 4: Import exactly one source
- Run `python3 tools/vocabulary_sources.py import-source <source-id> --output Content/Sources/Imported/<source-id>.jsonl`.
- Run the same command again and compare output checksums when changing an adapter.
- Treat JSONL as candidate evidence only. Do not edit `VocabularySeed.json` in this step.
- Stop source-specific code here. Do not add a per-source translator, example writer, question generator, reviewer, or promotion branch.
- For Wiktextract, preserve POS, per-sense gloss/example/translation evidence and all valid IPA variants in canonical `senses` and `pronunciations`; do not import quotation or audio fields. For CMUdict, remove inline comments before variant comparison.

Step 5: Report and review
- Run `python3 tools/vocabulary_sources.py report`.
- Report source records, normalized unique headwords, CEFR coverage, zh-Hant coverage, and current `appUse` decision.
- Explain that counts include overlaps, inflections, senses, non-English records, and unsuitable material.

Step 6: Prepare the shared enrichment batch
- Only when shipping-bank work was requested, run:

```sh
python3 tools/vocabulary_sources.py prepare-enrichment \
  --input-dir Content/Sources/Imported \
  --existing-seed Content/Baselines/legacy-90.json \
  --current-seed Vocaby/Resources/VocabularySeed.json \
  --output /tmp/vocabulary-rich-review-queue.jsonl
```

- Select quotas by App level through command arguments; do not encode source-specific field generation in an adapter.
- Require `opencc` with `s2twp.json` and Xcode's macOS Swift toolchain. The shared
  stage uses Apple's offline `NaturalLanguage` embeddings to reject mismatched
  sense evidence; these maintainer tools never enter the App target.
- Review the draft for intended English sense, exact OEWN/ILI alignment, source references, CEFR, translation match, duplicates, and Taiwan learner usefulness. Select one primary and no more than two additional common senses. Reject ambiguous candidates before continuing.

Step 7: Build shared reviewed artifacts
- Prepare and finish the one shared local review workspace:

```sh
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
```

- `run-local` uses installed Apple language services only. If a maintainer instead completes the checkpointed enrichment/translation files with an Agent, use the same workspace and final `build-reviewed` command.
- Require every selected sense to contain POS, bilingual meanings, complete bilingual examples, and applicable pronunciation IDs. Never promote a usage-note translation as a meaning or example translation.
- Require source references and `appUse: approved` for every shipping field. Reference-only sources may support research but may not contribute definitions, translations, examples, questions, or levels.
- Do not claim that adapter, Agent, or Apple-language-service output is editorially approved.

Step 8: Promote reviewed artifacts
- Audit the full tracked review file before building anything:

```sh
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

- Repeat `build-reviewed` into a second temporary set and require byte-identical seed, provenance, and notices before release review. Replace the three repository artifacts together only after that review passes.
- Require every source right, required notice, item status, reviewer field, language field, ID match, sort order, CEFR mapping, quiz-answer alignment, and duplicate gate to pass.
- A manifest source marked `reference_only` or `blocked` cannot be promoted. Stop and report the exact gate; never weaken it to finish the task.

Step 9: Final QA
- Run `python3 -m unittest tools/test_vocabulary_sources.py tools/test_review_vocabulary.py`.
- Run `python3 tools/vocabulary_sources.py verify`.
- Run `git diff --check` and inspect staged paths. Raw snapshots, evidence, and `Content/Reviews/*.jsonl` may be committed; generated `Imported/` and `Reports/` remain ignored.
- If App content changed, run the repository's Swift tests, the content-review checklist, and a release build. Inspect the built App bundle to confirm it contains the seed and notices but no `Raw`, `Imported`, source manifest, or provenance file.
- Confirm `Vocaby.xcodeproj/project.pbxproj` contains no `Content/Sources`, `Content/Reviews`, or `VocabularyProvenance` path.
</workflow>

<output_contract>
Return these four short sections in order:
1. Source: ID, version, canonical URL, raw path.
2. Import result: record count, unique headword count when available, canonical JSONL path.
3. Shared pipeline: enrichment/review artifact paths and item counts, or why this phase was not requested.
4. Gates and verification: integrity, rights/app-use, notices, editorial review, promotion, Xcode exclusion, exact commands, and pass/fail result.

Never describe candidate rows as approved App lessons. If blocked, name the
failed gate and leave shipping files unchanged.
</output_contract>

<tool_rules>
- Use `tools/vocabulary_sources.py` as the single executable source of truth; do not duplicate importer logic inside this skill.
- Keep source adapters on the Python standard library. Shared enrichment may call
  the approved system `opencc` executable and the repository's macOS Swift
  `NaturalLanguage` helper; do not add either as an iOS runtime dependency.
- Keep adapters limited to raw-format parsing and canonical normalization. Route every canonical record through the same `prepare-enrichment`, `review_vocabulary.py`, `audit-reviewed`, `build-reviewed`, and `promote` commands.
- Source downloads are maintainer-time actions. App code and build resources must contain no downloader, endpoint, token, or credential.
- The App never reads `Content/Sources/Raw`, `Imported`, `Reports`, `source-manifest.json`, `Content/Reviews`, or `Content/VocabularyProvenance.json`.
- Writes to raw snapshots, manifest, tests, and reviewed artifacts are in scope when the user asks to add/import a source.
- Promotion is a distinct side effect and requires an explicit shipping-bank request plus complete reviewed seed, provenance, and notices.
- Never rewrite a checksum merely to make verification pass.
</tool_rules>

<default_follow_through_policy>
- Directly do: inspect local files, compute checksums, add a declared source, verify, import, report, run the shared enrichment/review path when shipping was requested, test, and commit when version-control inclusion was requested.
- Ask first: only when source identity/license is ambiguous or promotion would overwrite reviewed App content without an explicit request.
- Stop and report: checksum/version mismatch, missing evidence, unapproved app use, failed review fields, ambiguous duplicates, or Xcode inclusion of source folders.
</default_follow_through_policy>

## Trigger and functional tests

Should trigger:
- 匯入一個新的外部詞庫
- 把這份字典來源加進 manifest
- 重跑 CEFR-J XLSX
- 驗證這十個來源的 checksum
- normalize this TEI dictionary to JSONL
- import the new CMUdict snapshot
- 產生來源候選報告
- promote the fully reviewed vocabulary batch
- 用兩種不同來源格式匯入後走同一套補強與審核流程
- 用 Wiktextract、CMUdict 與 OEWN 補強多讀音多詞義後建立 review JSONL

Should not trigger:
- 修改 Today 頁面的按鈕
- 幫我翻譯這十句英文
- 清理一般銷售 CSV
- 新增登入
- 寫一個網頁爬蟲但不涉及 Vocaby 詞庫
- 調整 widget 排版
- 修正 SwiftData migration
- 查目前 App 有多少已學單字

Functional gates:
- wrong checksum fails before parsing;
- declared Latin-1 input imports without replacement characters;
- same input creates byte-identical JSONL;
- unapproved rights fail before seed output;
- all fourteen retained sources verify and import;
- different raw formats use separate adapters but identical post-adapter enrichment/review/promotion stages;
- every reviewed sense references valid pronunciation IDs and contains complete bilingual meaning/example fields;
- Xcode project contains no `Content/Sources`, `Content/Reviews`, or `VocabularyProvenance` path.

Baseline evidence and the paired eval prompts live in
`assets/evals/baseline.md` and `assets/evals/evals.json`. Release checks are
defined in `assets/evals/regression_gates.json` and recorded in
`references/quality_checklist.md`.

## Troubleshooting

- `checksum mismatch`: confirm upstream version and file identity; do not update the hash blindly.
- `UnicodeDecodeError`: identify the actual encoding, add it to the manifest, and add a failing fixture before changing the shared parser.
- `unknown adapter`: inspect the real container/data format, then add one minimal adapter plus a deterministic test.
- promotion rejected: fix the reviewed content or provenance; do not change the gate.
