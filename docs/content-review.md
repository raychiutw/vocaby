# Content Review Checklist - Wording Daily

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

- [ ] `verify`, importer tests, and two clean deterministic imports pass.
- [ ] `prepare-enrichment` fills every requested level quota without duplicates.
- [ ] `build-reviewed` emits seed, provenance, and notices from the same draft.
- [ ] `promote` passes rights, notice, reviewer, language, CEFR, sort-order,
  concept, expression, quiz-answer, and one-to-one provenance gates.
- [ ] Every item has non-empty English and zh-Hant meanings, example,
  translation, pronunciation text, and localized prompts.
- [ ] Every contributing source is `appUse: approved`; reference-only and blocked
  sources contribute no shipping fields.
- [ ] Built App resources contain the seed and notices, but no `Content/Sources`,
  imports, reports, source manifest, or provenance file.

## Content Review by Level and Source

Review in deterministic level/sort order. Inspect all rejected or corrected
records plus a representative sample from each level and each contributing source
combination. Increase the sample until no new repeated issue appears.

- [ ] Basic: 980 items represented.
- [ ] Intermediate: 1,630 items represented.
- [ ] Advanced: 2,830 items represented.
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
- [ ] A Tatoeba full-sentence translation is natural and faithful; otherwise the
  generated zh-Hant usage note accurately identifies the target and meaning.
- [ ] English and zh-Hant prompts ask the intended question without revealing the answer.
- [ ] Pronunciation and the correct quiz option equal the upgraded expression.
- [ ] Same-level distractors are plausible but not alternative correct answers.
- [ ] The item can be understood in under 30 seconds.

## Reject and Fix in the Shared Stage

Reject an item before promotion when it contains:

- machine-like Traditional Chinese, Mainland-only wording, or mixed scripts;
- an unrelated or zero-overlap translation for the selected English sense;
- obscure thesaurus English, a non-expression fragment, or unusable proper name;
- a plain/upgraded pair that does not teach an actual upgrade;
- a vague, malformed, or sense-mismatched example;
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
