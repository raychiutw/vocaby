---
name: wording-daily-vocabulary-import
description: Import or re-import one external vocabulary source into Wording Daily's repository-only candidate pool. 適用於使用者要求匯入新詞庫, 新增字庫來源, 重跑來源檔, verify vocabulary checksum, parse CSV TSV XLSX ZIP TAR TEI JSON or CMUdict, generate candidate JSONL, or promote an already reviewed local bank. Verifies provenance and license evidence, runs the deterministic importer, reports counts, and keeps raw/generated source data out of the iOS target. Do not use for runtime downloads, login/sync work, ordinary seed copy edits, generic scraping, or bypassing editorial and rights review.
version: 2026.7.11
homepage: https://github.com/raychiutw/wording-daily
license: Proprietary
metadata: {"author":"Wording Daily"}
---

# Wording Daily vocabulary import

This skill owns the maintainer workflow that turns one external source snapshot
into reproducible, repository-only candidate JSONL. It does not turn third-party
rows directly into shipping lessons. The app remains offline and reads only its
reviewed bundled seed.

## Single responsibility

- Primary job: verify and normalize one declared external vocabulary source with the repository's deterministic importer.
- Not this skill's job: download data at app runtime, invent translations/examples, approve licenses, or design quiz UI.
- Split / handoff rule: use a browser or spreadsheet skill only to obtain or inspect an upstream artifact, then return here for manifest, import, report, and release gates.

<role>
Act as the Wording Daily content-pipeline maintainer. Preserve exact upstream
snapshots, fail closed on rights or integrity uncertainty, and keep candidate
data separate from reviewed App content.
</role>

<decision_boundary>
Use when:
- adding a new dictionary, word list, pronunciation list, or lexical dataset;
- re-running a source after its file/version/checksum changes;
- checking source integrity, candidate counts, duplicate headwords, or build exclusion;
- promoting a separately reviewed seed and provenance file.

Do not use when:
- changing UI, quiz behavior, notification behavior, or SwiftData;
- editing a few Wording Daily-authored seed items with no external source;
- scraping an unrelated website or transforming a generic spreadsheet;
- adding any network, account, credential, sync, or remote-bank path to the app.

Inputs:
- repository root containing `tools/vocabulary_sources.py`;
- one raw source file plus canonical source/version/license evidence;
- for promotion only, reviewed seed JSON and provenance JSON.

Successful output:
- the source snapshot is declared and checksum-verified;
- a repeatable one-source command produces deterministic candidate JSONL;
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
3. **Promote reviewed content**
   - Triggers: "把審核完成的批次放入 App", "promote the reviewed local bank".
   - Inputs: complete reviewed seed and provenance.
   - Done: every rights/reviewer/schema gate passes and only the requested bundled seed changes.

## Routing boundaries

- No repo-local skill overlaps this workflow.
- `spreadsheets` may inspect XLSX/CSV but does not own source rights, checksums, canonical JSONL, or promotion.
- `scrape` may retrieve an official page but does not own vocabulary normalization or App gates.
- `skillify` captures browser flows; it does not import lexical data.
- Negative triggers: generic CSV cleanup, app runtime downloads, translation writing, UI work, and login/sync tasks.

## Language and host coverage

- Trigger languages: Traditional Chinese, English, and mixed prompts such as "重跑 OEWN JSON ZIP".
- Treat 字庫, 詞庫, 題庫來源, source file, dataset, dictionary, import, ingest, and re-import as equivalent routing terms in this repository.
- Primary host: Codex working in this repository. The Markdown workflow is portable to other filesystem agents that can run Python 3.
- Mutable outputs live under ignored `Content/Sources/Imported/` and `Content/Sources/Reports/`, never inside this skill folder.

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
- Stop on unknown, account-gated, non-commercial, no-derivatives, or conflicting terms.

Step 2: Declare the source
- Compute SHA-256 and byte count for the raw file and every evidence file.
- Add exactly one unique entry to `Content/Sources/source-manifest.json`.
- Reuse an existing adapter when its real file format matches. Add the smallest parser branch and one failing test first only when no adapter matches.
- Declare non-UTF-8 encodings explicitly; do not guess silently.

Step 3: Verify before parsing
- Run `python3 tools/vocabulary_sources.py verify --source <source-id>`.
- On a mismatch, leave the old manifest untouched until the changed upstream file/version/license is understood.
- Confirm `Content/Sources` is absent from `WordingDailyApp.xcodeproj/project.pbxproj`.

Step 4: Import exactly one source
- Run `python3 tools/vocabulary_sources.py import-source <source-id>`.
- Run the same command again and compare output checksums when changing an adapter.
- Treat JSONL as candidate evidence only. Do not edit `VocabularySeed.json` in this step.

Step 5: Report and review
- Run `python3 tools/vocabulary_sources.py report`.
- Report source records, normalized unique headwords, CEFR coverage, zh-Hant coverage, and current `appUse` decision.
- Explain that counts include overlaps, inflections, senses, non-English records, and unsuitable material.

Step 6: Promote only separately reviewed content
- Run `promote` only when the user asked for shipping-bank work and supplied complete reviewed seed and provenance files.
- Require every source right, item status, reviewer field, language field, ID match, sort order, and duplicate gate to pass.
- A manifest source marked `reference_only` or `blocked` cannot be promoted. Stop and report the exact gate; never weaken it to finish the task.

Step 7: Final QA
- Run `python3 -m unittest tools/test_vocabulary_sources.py`.
- Run `python3 tools/vocabulary_sources.py verify`.
- Run `git diff --check` and inspect staged paths. Raw snapshots and evidence may be committed; generated `Imported/` and `Reports/` must remain ignored.
- If App content changed, also run the repository's Swift tests and content-review checklist.
</workflow>

<output_contract>
Return these four short sections in order:
1. Source: ID, version, canonical URL, raw path.
2. Import result: record count, unique headword count when available, output path.
3. Gates: integrity, rights/app-use, editorial review, Xcode exclusion.
4. Verification: exact commands and pass/fail result.

Never describe candidate rows as approved App lessons. If blocked, name the
failed gate and leave shipping files unchanged.
</output_contract>

<tool_rules>
- Use `tools/vocabulary_sources.py` as the single executable source of truth; do not duplicate importer logic inside this skill.
- Use Python standard library only unless a new format proves impossible to parse safely.
- Source downloads are maintainer-time actions. App code and build resources must contain no downloader, endpoint, token, or credential.
- Writes to raw snapshots, manifest, tests, and reviewed artifacts are in scope when the user asks to add/import a source.
- Promotion is a distinct side effect and requires an explicit shipping-bank request plus complete reviewed inputs.
- Never rewrite a checksum merely to make verification pass.
</tool_rules>

<default_follow_through_policy>
- Directly do: inspect local files, compute checksums, add a declared source, verify, import, report, test, and commit when version-control inclusion was requested.
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

Should not trigger:
- 修改 Today 頁面的按鈕
- 幫我翻譯這十句英文
- 清理一般銷售 CSV
- 新增登入
- 寫一個網頁爬蟲但不涉及 Wording Daily 詞庫
- 調整 widget 排版
- 修正 SwiftData migration
- 查目前 App 有多少已學單字

Functional gates:
- wrong checksum fails before parsing;
- declared Latin-1 input imports without replacement characters;
- same input creates byte-identical JSONL;
- unapproved rights fail before seed output;
- all ten retained snapshots verify and import;
- Xcode project contains no `Content/Sources` path.

Baseline evidence and the paired eval prompts live in
`assets/evals/baseline.md` and `assets/evals/evals.json`. Release checks are
defined in `assets/evals/regression_gates.json` and recorded in
`references/quality_checklist.md`.

## Troubleshooting

- `checksum mismatch`: confirm upstream version and file identity; do not update the hash blindly.
- `UnicodeDecodeError`: identify the actual encoding, add it to the manifest, and add a failing fixture before changing the shared parser.
- `unknown adapter`: inspect the real container/data format, then add one minimal adapter plus a deterministic test.
- promotion rejected: fix the reviewed content or provenance; do not change the gate.
