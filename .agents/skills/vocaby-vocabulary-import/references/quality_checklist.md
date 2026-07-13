# Quality checklist

## Final gate

- Checked: 2026-07-11 rich-review revision
- Overall status: PASS
- Blocking issues: none
- Baseline: eval 5 against the previous skill was RED: 10 of 11 required
  Wiktextract rich-review requirements were absent. The revised skill passes all
  11 static expectations; the exact baseline is retained in
  `../assets/evals/baseline.md`.

## Evidence / commands run

- [x] `python3 /Users/ray/.agents/skills/skill-creator-advanced/scripts/format_check.py --strict .agents/skills/vocaby-vocabulary-import` — 0 errors, 0 warnings.
- [x] `python3 /Users/ray/.agents/skills/skill-creator-advanced/scripts/quick_validate.py .agents/skills/vocaby-vocabulary-import` — passed.
- [x] `python3 /Users/ray/.agents/skills/skill-creator-advanced/scripts/audit_openclaw_frontmatter.py .agents/skills/vocaby-vocabulary-import` — 0 issues.
- [x] `python3 /Users/ray/.agents/skills/skill-creator-advanced/scripts/audit_skill_references.py .agents/skills/vocaby-vocabulary-import` — 0 issues.
- [x] `python3 /Users/ray/.agents/skills/skill-creator-advanced/scripts/audit_unreferenced_files.py .agents/skills/vocaby-vocabulary-import` — 0 issues.
- [x] `python3 /Users/ray/.agents/skills/skill-creator-advanced/scripts/prepare_eval_workspace.py .agents/skills/vocaby-vocabulary-import --workspace /tmp/vocaby-vocabulary-import-workspace --iteration iteration-2026-07-11-rich --baseline-label old_skill` — paired workspace prepared outside the repository.
- [x] `package_skill.py` plus `unzip -t` — `vocaby-vocabulary-import.skill` packaged and archive-integrity check passed in `/tmp/vocaby-vocabulary-import-package`.
- [x] `python3 -m unittest tools/test_vocabulary_sources.py tools/test_review_vocabulary.py` — 54 tests passed.
- [x] `python3 tools/vocabulary_sources.py verify` — 14 sources verified.
- [x] `python3 tools/vocabulary_sources.py audit-reviewed --input Content/Reviews/vocabulary-rich-2026-07-11.jsonl` — 5,221 approved: 980 basic, 1,630 intermediate, 2,611 advanced.

The paired-agent benchmark is not claimed: delegated/subagent execution is
disabled in this environment. The recorded RED/GREEN static contract and the
deterministic source/review gates are the available verification evidence.

## Format checks

- [x] Folder name is kebab-case; `SKILL.md` has valid YAML frontmatter and
  single-line JSON metadata.
- [x] The description routes source import, rich review JSONL, Wiktextract,
  CMUdict, OEWN, and promotion work without claiming generic spreadsheet, UI,
  runtime download, account, or sync work.
- [x] All files under `references/` and `assets/` are referenced; no README,
  mutable cache, missing path, or orphaned file exists in the skill folder.
- [x] This checklist records this revision's actual commands and outcomes.

## Requirement and policy checks

- [x] One primary job: source-specific raw adapters end at canonical JSONL, then
  every source shares enrichment, review, audit, deterministic build, notices,
  and promotion.
- [x] Target-only `snapshot-wiktextract` records the official source and license
  evidence; quotations, audio, images, and outside media are excluded.
- [x] The canonical rich contract requires structured pronunciations and no more
  than three senses; every sense has POS, English/zh-Hant meaning, complete
  bilingual example, and valid pronunciation IDs.
- [x] CMUdict inline comments are stripped before pronunciation comparison; OEWN
  plus the ILI map remains the sense cross-check.
- [x] Agent/local language-service output is unapproved until `audit-reviewed`,
  deterministic build/promotion, and release review pass. Usage-note
  translations cannot become shipped teaching content.
- [x] Raw snapshots and review JSONL are maintainer artifacts; neither, nor
  provenance, is in an Xcode target or App bundle.
- [x] The App remains fully local and offline: no runtime network, login,
  credential, sync, cloud, or remote-bank path is permitted.

## Functional and current-bank checks

- [x] Wrong checksums fail before parsing; manifest-declared Latin-1 imports
  without replacement characters; canonical imports are deterministic.
- [x] CMUdict comments/variants and Wiktextract target filtering, POS, senses,
  and IPA have regression coverage.
- [x] Reviewed items fail closed for incomplete bilingual senses, unknown
  pronunciation IDs, malformed IPA, invalid levels, review status, or missing
  source evidence.
- [x] Current bank has 2,191 multi-sense items, 2,631 multi-pronunciation items,
  at most two selected senses, and at most three pronunciations per item.
- [x] 219 source slots lacking verified/composable pronunciation are documented
  in `docs/vocabulary-rejections-2026-07-11.md`, not silently replaced.
- [x] Current resource hashes: Seed
  `58ed8c4162e89c5c76ff08dc3137cc4f319857910ab81c74249826cc151a149d`,
  Provenance `85c46c2eaff277d0b234c354ef1a419821bcffc66b3ad1c622b56300c7fa8fd0`,
  Notices `1587f422bcfdf560dece186bc693fd025056fa2607811c7c8d1dab609230ca91`.

## Common error checks

- [x] No source-specific post-adapter translation, example, question, review, or
  promotion branch is allowed.
- [x] Checksums and rights fields are never rewritten merely to make a release
  pass.
- [x] Reference-only or blocked sources cannot contribute shipping fields.
- [x] Promotion remains a distinct, explicit shipping-bank side effect.
