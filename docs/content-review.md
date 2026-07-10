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

Required scope:

- Review all 90 bundled seed items before TestFlight.
- Review by level, in `sortOrder`.
- Treat this as a human gate. Automated seed validation only proves structure.

## Batch Coverage

- [ ] Basic `basic-001` to `basic-030`
- [ ] Intermediate `intermediate-001` to `intermediate-030`
- [ ] Advanced `advanced-001` to `advanced-030`

Evidence:

## Per-Item Checks

For every item, verify:

- [ ] The plain expression is something a learner might actually say.
- [ ] The upgraded expression is natural English, not obscure synonym swapping.
- [ ] The Traditional Chinese explanation sounds native to Taiwan.
- [ ] The explanation teaches usage, not only translation.
- [ ] The English definition matches the upgraded expression.
- [ ] The example sentence is realistic and shows the expression in context.
- [ ] The Traditional Chinese example translation is natural and accurate.
- [ ] The quiz prompt tests meaning or usage, not spelling trivia.
- [ ] All distractors are plausible but clearly wrong after reading the item.
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
- [ ] This review used native Taiwan Traditional Chinese judgment, not machine translation alone.

Reviewer:

Date:
