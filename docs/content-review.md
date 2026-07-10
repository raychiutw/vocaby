# Content Review Checklist - Wording Daily

Use this checklist before TestFlight and after changing `VocabularySeed.json`.

The goal is to catch content that tests cannot prove: unnatural Taiwanese
Traditional Chinese, obscure thesaurus English, weak expression upgrades, and
quiz distractors that make the answer too obvious.

## Review Build

- Date:
- Commit:
- Reviewer:
- Seed file: `WordingDailyApp/Resources/VocabularySeed.json`
- Bank version:
- Provenance manifest: `Content/VocabularyProvenance.json`

Required scope:

- Review all 90 bundled seed items before TestFlight.
- Review by level, in `sortOrder`.
- Treat this as a human gate. Automated seed validation only proves structure.

## Batch Coverage

- [ ] Basic `basic-001` to `basic-030`
- [ ] Intermediate `intermediate-001` to `intermediate-030`
- [ ] Advanced `advanced-001` to `advanced-030`

Evidence:

- Generated same-level candidate matrix:
- Ambiguity reviewer:

## Per-Item Checks

For every item, verify:

- [ ] The item has an approved source, redistribution/adaptation rights, and any
  required attribution or indication of changes.
- [ ] The provenance row matches the seed ID and records exact CEFR, rubric scores,
  reviewer IDs, and review date.
- [ ] The plain expression is something a learner might actually say.
- [ ] The upgraded expression is natural English, not obscure synonym swapping.
- [ ] The Traditional Chinese explanation sounds native to Taiwan.
- [ ] The explanation teaches usage, not only translation.
- [ ] The English definition matches the upgraded expression.
- [ ] The example sentence is realistic and shows the expression in context.
- [ ] The Traditional Chinese example translation is natural and accurate.
- [ ] Expression choice tests plain-to-upgraded usage without revealing the answer.
- [ ] Meaning choice tests the intended localized sense.
- [ ] Listening choice can be answered from local TTS without showing the answer.
- [ ] Spelling accepts the intended expression and no materially different answer.
- [ ] Same-level dynamic distractors are plausible but clearly wrong after reading the prompt.
- [ ] The candidate matrix records every same-level item whose answer could also
  plausibly satisfy this prompt, and each ambiguity is resolved before approval.
- [ ] The item can be understood in under 30 seconds.

## Reject Immediately

Reject the item and fix it before TestFlight if any of these appear:

- Machine-translated Traditional Chinese, including unnatural word order.
- Mainland-only phrasing when a Taiwan user would expect a different wording.
- English that sounds like GRE trivia or thesaurus output.
- A plain/upgraded pair that is only a single-word dictionary translation.
- Distractors that are obviously unrelated or accidentally also correct.
- Examples that are too vague to teach usage.
- Any content that feels judgmental, guilt-driven, or motivational instead of useful.
- Missing, unknown, non-commercial-only, no-derivatives, or incompatible
  share-alike source rights.
- A copied or adapted item without a stable source-entry reference and attribution.
- A CEFR/app-level assignment based only on word length, a frequency rank, or an
  automated score.
- A reused ID whose meaning or concept changed, or a removed ID without an explicit
  local-data migration.

## Review Notes

Record item IDs and the required fix. Do not approve the batch until every item
below is fixed or explicitly accepted by the reviewer.

| Item ID | Issue | Fix Needed | Status |
|---|---|---|---|
| | | | |

## Sign-Off

- [ ] All 90 items were reviewed.
- [ ] Every rejected item has been fixed or explicitly accepted.
- [ ] The seed JSON still passes automated validation after fixes.
- [ ] Seed and provenance contain the same IDs and the bank version was updated.
- [ ] Every item has approved rights and an exact CEFR band in the documented app-level range.
- [ ] Each level can generate four unique same-level options for every choice mode and supported language.
- [ ] Duplicate upgraded expressions and duplicate concepts were resolved before the approved baseline.
- [ ] Required attribution output is complete and deterministic.
- [ ] This review used native Taiwan Traditional Chinese judgment, not machine translation alone.

Reviewer:

Date:
