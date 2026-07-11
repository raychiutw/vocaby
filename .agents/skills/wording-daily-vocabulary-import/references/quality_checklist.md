# Quality checklist

## Final gate

- Current version reviewed: 2026.7.11
- Overall status: PASS
- Blocking issues: none
- Baseline: the pre-skill workflow had no executable importer or manifest; see `../assets/evals/baseline.md`.
- Functional evidence:
  - `python3 -m unittest tools/test_vocabulary_sources.py`: 5 tests passed.
  - `python3 tools/vocabulary_sources.py verify`: 10 sources passed checksum, size, evidence, and Xcode-exclusion checks.
  - Two full `import-all` runs: 10 of 10 JSONL checksums identical; 478,923 records and 348,889 normalized unique headwords.
- Skill evidence:
  - strict format check: 0 errors, 0 warnings.
  - quick validation, OpenClaw frontmatter, reference, and unreferenced-file audits: passed.
  - package creation and `unzip -t`: passed.

## Format checks

- [x] Folder name is kebab-case.
- [x] `SKILL.md` exists with valid YAML frontmatter.
- [x] Frontmatter includes name, decision-boundary description, date version, homepage, license, and single-line JSON metadata.
- [x] Frontmatter contains no angle brackets.
- [x] This checklist is present and current.
- [x] Every file under `references/` and `assets/` is referenced.
- [x] No README or mutable cache exists inside the skill folder.

## Requirement and policy checks

- [x] Eight Traditional Chinese, English, and mixed should-trigger cases are listed.
- [x] Eight unrelated and near-miss should-not-trigger cases are listed.
- [x] The description distinguishes this workflow from spreadsheet, scrape, and skillify work.
- [x] The skill has one primary job: one-source repository import.
- [x] Every workflow stage states an action and mechanical validation.
- [x] Integrity, encoding, parser, rights, review, promotion, and Xcode-exclusion errors have actionable stops.
- [x] The four-section output contract is explicit.
- [x] Direct-action, ask-first, and stop policies are explicit.
- [x] Codex is the primary host and filesystem-agent portability is documented.
- [x] App runtime network, login, credentials, sync, and remote-bank paths are forbidden.
- [x] Generated state stays in ignored repository directories, outside the skill folder and Xcode target.

## Functional checks

- [x] Wrong checksums fail before parsing.
- [x] Manifest-declared Latin-1 imports without replacement characters.
- [x] Normalized duplicate source rows merge deterministically.
- [x] Rights not fully approved fail before output.
- [x] A fully reviewed approved fixture promotes successfully.
- [x] All retained CSV, TSV, dict, XLSX ZIP, JSON ZIP, TEI TAR, and GCIDE TAR snapshots import.
- [x] Candidate records remain distinct from shipping seed content.

## Common error checks

- [x] No missing local skill references.
- [x] No orphaned skill files.
- [x] No contradictory workflow/tool/follow-through rules.
- [x] No unresolved placeholders in user-facing instructions.
- [x] No hidden side effects bypass promotion or rights approval.
- [x] Checksums are never rewritten merely to make verification pass.

## Maintenance and ROI

- [x] Date version is present.
- [x] Three eval scenarios and regression gates are saved.
- [x] Baseline and GREEN evidence are retained.
- [x] The long workflow is split into identity, declaration, verification, import, report, promotion, and QA gates.
- [x] The skill reuses one repository program instead of duplicating parser code.
- [x] ROI is positive: the prior manual process became one repeatable command path; added runtime dependencies: zero.
- [x] Paired agent benchmark is intentionally omitted because this run disallowed delegated/subagent work; deterministic functional and static gates cover release behavior.
