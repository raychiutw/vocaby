# Content Review Checklist - Vocaby

Use this shared checklist after `build-reviewed`, before `promote`, and before
TestFlight whenever `VocabularySeed.json` changes. It applies to every source
after canonical JSONL; do not create source-specific review rules.

Automated tests prove structure and traceability. This review catches naturalness,
sense alignment, Taiwan usage, and weak questions that schemas cannot prove.

## Review Build

- Date:
- Commit:
- Agent/content reviewer:
- Human release reviewer:
- Draft:
- Seed:
- Provenance:
- Notices:
- Bank version:
- Item count:

## Full-Bank Mechanical Review

- [ ] `verify`, importer/review tests, and two clean deterministic imports pass.
- [ ] `prepare-enrichment` fills every requested level quota without duplicates.
- [ ] `review_vocabulary.py build-reviewed` emits the tracked review JSONL and
  rejection report; `audit-reviewed` passes before seed generation.
- [ ] `vocabulary_sources.py build-reviewed` emits seed, provenance, and notices
  from that same reviewed JSONL.
- [ ] `promote` passes rights, notice, reviewer, language, CEFR, sort-order,
  concept, expression, quiz-answer, and one-to-one provenance gates.
- [ ] Every item has one to three verified pronunciations and one to three
  senses. Every sense has POS, valid pronunciation IDs, non-empty English and
  zh-Hant meanings, an English full-sentence example, a faithful zh-Hant
  full-sentence translation, and localized prompts.
- [ ] Every contributing source is `appUse: approved`; reference-only and blocked
  sources contribute no shipping fields.
- [ ] Built App resources contain the seed and notices, but no `Content/Sources`,
  `Content/Reviews`, imports, reports, source manifest, or provenance file.

## Content Review by Level and Source

Review in deterministic level/sort order. Inspect all rejected or corrected
records plus a representative sample from each level and each contributing source
combination. Increase the sample until no new repeated issue appears.

- [ ] Basic: 980 items represented.
- [ ] Intermediate: 1,630 items represented.
- [ ] Advanced: 2,611 approved items plus all 219 pronunciation rejections represented.
- [ ] Legacy project-owned items represented.
- [ ] COW + OMW ILI + OEWN sense-aligned items represented.
- [ ] CEFR-J, CC-CEDICT, and Tatoeba evidence combinations represented.
- [ ] First, middle, last, and deterministic random samples recorded per level.

Evidence:

- Sample IDs:
- Repeated issues found:
- Shared rule or data correction applied:
- Clean rerun result:

## Per-Item Checks

For every reviewed item, verify:

- [ ] Source references identify the exact approved evidence used for this sense.
- [ ] Exact CEFR and App level agree.
- [ ] Plain and upgraded expressions express a useful, teachable relationship.
- [ ] The upgraded expression is natural English, not obscure synonym swapping.
- [ ] The English definition matches the intended expression sense.
- [ ] Taiwan Traditional Chinese is natural, accurate, and uses Taiwan wording.
- [ ] The example is realistic and demonstrates the same intended sense.
- [ ] The full-sentence zh-Hant translation is natural and faithful, whether it
  comes from an aligned Tatoeba pair or the local maintainer translation stage.
- [ ] English and zh-Hant prompts ask the intended question without revealing the answer.
- [ ] Each sense references only an existing pronunciation ID; selected IPA is
  complete, locale/region labels are supported by evidence, and the correct quiz
  option equals the upgraded expression.
- [ ] Same-level distractors are plausible but not alternative correct answers.
- [ ] The item can be understood in under 30 seconds.

## Reject and Fix in the Shared Stage

Reject an item before promotion when it contains:

- machine-like Traditional Chinese, Mainland-only wording, or mixed scripts;
- an unrelated or zero-overlap translation for the selected English sense;
- obscure thesaurus English, a non-expression fragment, or unusable proper name;
- a plain/upgraded pair that does not teach an actual upgrade;
- a vague, malformed, or sense-mismatched example;
- more than three senses, an unknown pronunciation ID, malformed IPA, a
  Wiktextract quotation/audio field, or a usage-note translation promoted as
  teaching content;
- a prompt that reveals the answer or allows multiple correct answers;
- duplicate concept keys or normalized upgraded expressions;
- missing source reference, required notice, approved right, reviewer field, or
  exact CEFR;
- any content produced by a blocked or reference-only source.

Fix repeated issues in the common selector, enrichment, review rule, or source
rights data, add a failing regression test, and regenerate the whole batch. Do
not patch one generated seed row or add a source-specific post-adapter exception.

## Review Notes

| Item ID | Issue | Shared Fix | Status |
|---|---|---|---|
| | | | |

## Sign-Off

- [ ] Every automated gate passed after the final correction.
- [ ] No unresolved repeated issue remains in the review samples.
- [ ] Seed, provenance, and notices were regenerated together and match the
  committed bank.
- [ ] Taiwan Traditional Chinese received native-speaker release review; an Agent
  review identifier is not represented as human sign-off.
- [ ] The App passed offline, localization, Dynamic Type, and source-notice checks.

Agent/content reviewer:

Human release reviewer:

Date:

## 2026-07-11 Agent Review Run

- Agent/content reviewer: `codex-content-review-2026-07-11`
- Human release reviewer: pending explicit approval
- Reviewed draft: `Content/Reviews/vocabulary-rich-2026-07-11.jsonl`
- Rejections: `docs/vocabulary-rejections-2026-07-11.md`
- Approved items: 5,221
- Levels: 980 basic, 1,630 intermediate, 2,611 advanced
- Rejected source slots: 219, all for missing verified or composable pronunciation
- Multiple-sense items: 2,191
- Multiple-pronunciation items: 2,631
- Complete teaching-sentence wrappers: 2,682

Mechanical results:

- `audit-reviewed`: 5,221 approved, no duplicate ID or expression.
- Every item has one to two senses and one to three verified pronunciations.
- IPA fragment/optional-marker audit: 0.
- Non-standard region mislabeled as US/UK audit: 0.
- Translation request/output IDs: exact one-to-one match.
- Two clean builds produced byte-identical Seed, Provenance, and Notices.
- Seed SHA-256: `58ed8c4162e89c5c76ff08dc3137cc4f319857910ab81c74249826cc151a149d`.
- Provenance SHA-256: `85c46c2eaff277d0b234c354ef1a419821bcffc66b3ad1c622b56300c7fa8fd0`.
- Notices SHA-256: `1587f422bcfdf560dece186bc693fd025056fa2607811c7c8d1dab609230ca91`.

Deterministic samples reviewed: first, middle, and last item in each level,
including `basic-001`, `bank-basic-0461`, `bank-basic-0950`,
`intermediate-001`, `bank-intermediate-0786`, `bank-intermediate-1600`,
`advanced-001`, `bank-advanced-1378`, and `bank-advanced-2800`.

Repeated corrections applied in the shared stage:

| Issue | Shared correction | Result |
|---|---|---|
| Entry-level Wiktextract translations were omitted | Merge entry and sense translations before canonical deduplication | Covered by adapter regression test |
| IPA fragments such as `ɪkˈsæs-` and regional variants were selected | Reject prefix/suffix fragments, normalize optional markers, and retain only US/General/UK/RP | Zero fragment or region audit failures |
| Source examples such as `Italian cooking.` were phrases, not sentences | Wrap source usage phrases in a complete teaching sentence and provide a faithful zh-Hant sentence | 2,682 corrected examples |
| Legacy records exposed `phrase` instead of the lexical part of speech | Infer the primary POS from exact OEWN evidence | Legacy samples now expose noun/verb/adjective as applicable |

Human Taiwan Traditional Chinese release review and physical-device offline QA
remain intentionally unsigned; Agent approval is not represented as human sign-off.
